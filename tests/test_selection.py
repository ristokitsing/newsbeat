from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from newsbeat_digest.db import Database
from newsbeat_digest.models import ItemStatus, RawItem
from newsbeat_digest.pipeline.select import select_items


def test_selection_respects_max_two_per_category(tmp_path: Path) -> None:
    database = _database_with_scored_items(
        tmp_path,
        [
            ("Model one", "models", 10),
            ("Model two", "models", 9),
            ("Model three", "models", 8),
            ("Policy one", "policy", 7),
        ],
    )

    _, selected_ids = select_items(database, max_items=4)

    selected = database.list_items(ItemStatus.SELECTED)
    assert len(selected_ids) == 3
    assert sum(item.llm_category == "models" for item in selected) == 2
    assert sum(item.llm_category == "policy" for item in selected) == 1


def test_delivered_cluster_is_not_redelivered_within_seven_days(
    tmp_path: Path,
) -> None:
    database = _database_with_scored_items(
        tmp_path,
        [
            ("Already delivered topic", "models", 9),
            ("Fresh topic", "tools", 8),
        ],
    )
    items = database.list_items(ItemStatus.SCORED)
    blocked = next(item for item in items if item.title == "Already delivered topic")
    now = datetime(2026, 6, 10, 12, tzinfo=UTC)
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO delivered_clusters (cluster_id, delivered_at, item_id)
            VALUES (?, ?, ?)
            """,
            (
                blocked.cluster_id,
                (now - timedelta(days=3)).isoformat(),
                blocked.id,
            ),
        )

    _, selected_ids = select_items(database, max_items=2, now=now)

    selected = database.list_items(ItemStatus.SELECTED)
    assert blocked.id not in selected_ids
    assert [item.title for item in selected] == ["Fresh topic"]


def test_selection_does_not_pad_below_minimum_relevance(
    tmp_path: Path,
) -> None:
    database = _database_with_scored_items(
        tmp_path,
        [
            ("Strong", "tools", 8),
            ("Weak", "research", 5),
        ],
    )

    _, selected_ids = select_items(database, max_items=8)

    assert len(selected_ids) == 1
    assert database.list_items(ItemStatus.SELECTED)[0].title == "Strong"


def _database_with_scored_items(
    tmp_path: Path,
    definitions: list[tuple[str, str, float]],
) -> Database:
    database = Database(tmp_path / "digest.db")
    database.initialize()
    for index, (title, category, score) in enumerate(definitions):
        item_id = database.insert_item(
            RawItem(
                title=title,
                url=f"https://example.com/{index}",
                published_at=None,
                source="Example",
                score_hint=float(100 - index),
            )
        )
        assert item_id is not None
        with database.connect() as connection:
            connection.execute(
                """
                UPDATE items
                SET cluster_id = ?,
                    cluster_representative = 1,
                    llm_score = ?,
                    llm_category = ?,
                    llm_reason = 'Test score',
                    status = 'scored'
                WHERE id = ?
                """,
                (f"cluster-{index}", score, category, item_id),
            )
    return database
