from pathlib import Path

from newsbeat_digest.db import Database
from newsbeat_digest.models import ItemStatus, RawItem


def test_database_initialization_is_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "digest.db")

    database.initialize()
    database.initialize()

    assert database.count_items() == 0


def test_duplicate_canonical_url_is_not_inserted_twice(tmp_path: Path) -> None:
    database = Database(tmp_path / "digest.db")
    database.initialize()
    item = RawItem(
        title="Example AI release",
        url="https://example.com/story?utm_source=test",
        published_at=None,
        source="Example",
    )

    first_id = database.insert_item(item, canonical_url="https://example.com/story")
    second_id = database.insert_item(item, canonical_url="https://example.com/story")

    assert first_id is not None
    assert second_id is None
    assert database.count_items(ItemStatus.NEW) == 1
    assert database.list_items()[0].title == "Example AI release"
