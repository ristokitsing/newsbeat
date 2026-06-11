from pathlib import Path

from newsbeat_digest.db import Database
from newsbeat_digest.models import ItemStatus, RawItem
from newsbeat_digest.pipeline.dedupe import cluster_new_items, title_similarity


def test_similar_titles_share_cluster_and_keep_stronger_representative(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "digest.db")
    database.initialize()
    first_id = database.insert_item(
        RawItem(
            title="Anthropic releases Claude model for developers",
            url="https://example.com/first",
            published_at=None,
            source="First",
            score_hint=10,
        )
    )
    second_id = database.insert_item(
        RawItem(
            title="Anthropic releases Claude model for developers today",
            url="https://example.com/second",
            published_at=None,
            source="Second",
            score_hint=80,
        )
    )
    assert first_id is not None
    assert second_id is not None

    representatives, duplicates = cluster_new_items(database)

    items = {item.id: item for item in database.list_items()}
    assert title_similarity(items[first_id].title, items[second_id].title) >= 0.78
    assert representatives == 1
    assert duplicates == 1
    assert items[first_id].cluster_id == items[second_id].cluster_id
    assert items[first_id].status is ItemStatus.REJECTED
    assert items[second_id].status is ItemStatus.NEW
    assert items[second_id].cluster_representative


def test_cluster_assignment_is_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "digest.db")
    database.initialize()
    database.insert_item(
        RawItem(
            title="A new practical AI tool",
            url="https://example.com/tool",
            published_at=None,
            source="Example",
        )
    )

    first = cluster_new_items(database)
    cluster_id = database.list_items(ItemStatus.NEW)[0].cluster_id
    second = cluster_new_items(database)

    assert first == (1, 0)
    assert second == (1, 0)
    assert database.list_items(ItemStatus.NEW)[0].cluster_id == cluster_id
