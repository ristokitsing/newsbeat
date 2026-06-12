import sqlite3
from datetime import date
from pathlib import Path

from newsbeat_digest.db import Database
from newsbeat_digest.models import BriefContent, ItemStatus, RawItem


# The pre-migration schema (user_version 0) declared the four social columns
# NOT NULL. The migration in Database.initialize() must relax them in place
# without losing existing rows.
_OLD_ITEMS_DDL = """
CREATE TABLE items (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    snippet TEXT,
    published_at TEXT,
    score_hint REAL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    cluster_id TEXT,
    cluster_representative INTEGER DEFAULT 1,
    llm_score REAL,
    llm_category TEXT,
    llm_reason TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    article_text TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_OLD_BRIEFS_DDL = """
CREATE TABLE briefs (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL,
    what_happened TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    linkedin_hook TEXT NOT NULL,
    linkedin_points_json TEXT NOT NULL,
    instagram_slides_json TEXT NOT NULL,
    instagram_cta TEXT NOT NULL,
    caution TEXT NOT NULL,
    digest_date TEXT NOT NULL,
    digest_slot TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(item_id) REFERENCES items(id)
);
"""


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


def test_migration_relaxes_social_columns_and_keeps_rows(tmp_path: Path) -> None:
    path = tmp_path / "digest.db"
    now = "2026-06-10T08:00:00+00:00"
    connection = sqlite3.connect(path)
    try:
        connection.executescript(_OLD_ITEMS_DDL + _OLD_BRIEFS_DDL)
        connection.execute(
            """
            INSERT INTO items (
                url, canonical_url, title, source, first_seen_at,
                status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'briefed', ?, ?)
            """,
            (
                "https://example.com/legacy",
                "https://example.com/legacy",
                "Legacy story",
                "Example",
                now,
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO briefs (
                item_id, what_happened, why_it_matters, linkedin_hook,
                linkedin_points_json, instagram_slides_json, instagram_cta,
                caution, digest_date, digest_slot, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'am', ?)
            """,
            (
                1,
                "It happened.",
                "It matters.",
                "Legacy hook",
                '["a", "b", "c"]',
                '["s1", "s2", "s3", "s4"]',
                "Legacy CTA",
                "Be careful.",
                "2026-06-10",
                now,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    database = Database(path)
    database.initialize()

    with database.connect() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert version == 1

    published = database.list_published_items(include_briefed=True)
    assert len(published) == 1
    brief = published[0].brief
    assert brief.linkedin_hook == "Legacy hook"
    assert brief.linkedin_points == ("a", "b", "c")
    assert brief.instagram_slides == ("s1", "s2", "s3", "s4")

    # A new summary-only brief inserts with NULL social columns.
    item_id = database.insert_item(
        RawItem(
            title="Fresh story",
            url="https://example.com/fresh",
            published_at=None,
            source="Example",
        )
    )
    assert item_id is not None
    with database.connect() as connection:
        connection.execute(
            "UPDATE items SET status = 'selected' WHERE id = ?",
            (item_id,),
        )
    summary: BriefContent = {
        "what_happened": "A new thing happened.",
        "why_it_matters": "It is relevant.",
        "caution": "Limited source material.",
    }
    brief_id = database.insert_brief(
        item_id,
        summary,
        digest_date=date(2026, 6, 10),
        digest_slot="am",
    )
    assert brief_id is not None


def test_new_database_starts_at_user_version_one(tmp_path: Path) -> None:
    database = Database(tmp_path / "digest.db")
    database.initialize()

    with database.connect() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert version == 1
