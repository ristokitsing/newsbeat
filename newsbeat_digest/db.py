"""SQLite persistence for collected items and generated briefs."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

from newsbeat_digest.models import (
    Brief,
    BriefContent,
    Item,
    ItemStatus,
    PublishedItem,
    RawItem,
    ScoreResult,
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
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
    status TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN (
            'new', 'scored', 'selected', 'rejected', 'briefed', 'delivered'
        )),
    article_text TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS briefs (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL,
    what_happened TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    linkedin_hook TEXT,
    linkedin_points_json TEXT,
    instagram_slides_json TEXT,
    instagram_cta TEXT,
    caution TEXT NOT NULL,
    digest_date TEXT NOT NULL,
    digest_slot TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS delivered_clusters (
    id INTEGER PRIMARY KEY,
    cluster_id TEXT NOT NULL,
    delivered_at TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    FOREIGN KEY(item_id) REFERENCES items(id)
);

CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_cluster_id ON items(cluster_id);
CREATE INDEX IF NOT EXISTS idx_briefs_digest_date ON briefs(digest_date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_briefs_item_id ON briefs(item_id);
CREATE INDEX IF NOT EXISTS idx_delivered_clusters_cluster
    ON delivered_clusters(cluster_id, delivered_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_delivered_clusters_item_id
    ON delivered_clusters(item_id);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            _migrate(connection)

    def insert_item(
        self,
        raw_item: RawItem,
        canonical_url: str | None = None,
    ) -> int | None:
        now = _utc_now()
        normalized_url = canonical_url or raw_item.url
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO items (
                    url,
                    canonical_url,
                    title,
                    source,
                    snippet,
                    published_at,
                    score_hint,
                    first_seen_at,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    raw_item.url,
                    normalized_url,
                    raw_item.title,
                    raw_item.source,
                    raw_item.snippet,
                    raw_item.published_at,
                    raw_item.score_hint,
                    now,
                    ItemStatus.NEW.value,
                    now,
                    now,
                ),
            )
            if cursor.rowcount == 0:
                return None
            return int(cursor.lastrowid)

    def count_items(self, status: ItemStatus | None = None) -> int:
        query = "SELECT COUNT(*) FROM items"
        parameters: tuple[str, ...] = ()
        if status is not None:
            query += " WHERE status = ?"
            parameters = (status.value,)

        with self.connect() as connection:
            row = connection.execute(query, parameters).fetchone()
        return int(row[0])

    def list_items(self, status: ItemStatus | None = None) -> list[Item]:
        query = "SELECT * FROM items"
        parameters: tuple[str, ...] = ()
        if status is not None:
            query += " WHERE status = ?"
            parameters = (status.value,)
        query += " ORDER BY first_seen_at DESC, id DESC"

        with self.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [_row_to_item(row) for row in rows]

    def set_clusters(
        self,
        assignments: list[tuple[int, str, bool]],
    ) -> None:
        if not assignments:
            return
        now = _utc_now()
        with self.connect() as connection:
            for item_id, cluster_id, representative in assignments:
                connection.execute(
                    """
                    UPDATE items
                    SET cluster_id = ?,
                        cluster_representative = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (cluster_id, int(representative), now, item_id),
                )

    def reject_new_cluster_duplicates(self) -> int:
        now = _utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE items
                SET status = ?, updated_at = ?
                WHERE status = ? AND cluster_representative = 0
                """,
                (
                    ItemStatus.REJECTED.value,
                    now,
                    ItemStatus.NEW.value,
                ),
            )
        return cursor.rowcount

    def save_scores(self, scores: list[ScoreResult]) -> int:
        if not scores:
            return 0
        now = _utc_now()
        updated = 0
        with self.connect() as connection:
            for score in scores:
                cursor = connection.execute(
                    """
                    UPDATE items
                    SET llm_score = ?,
                        llm_category = ?,
                        llm_reason = ?,
                        status = ?,
                        updated_at = ?
                    WHERE id = ?
                      AND status = ?
                      AND cluster_representative = 1
                    """,
                    (
                        score.relevance,
                        score.category,
                        score.reason,
                        ItemStatus.SCORED.value,
                        now,
                        score.item_id,
                        ItemStatus.NEW.value,
                    ),
                )
                updated += cursor.rowcount
        return updated

    def select_scored_items(
        self,
        selected_ids: list[int],
        considered_ids: list[int],
    ) -> None:
        if not considered_ids:
            return
        now = _utc_now()
        selected = set(selected_ids)
        with self.connect() as connection:
            for item_id in considered_ids:
                status = (
                    ItemStatus.SELECTED
                    if item_id in selected
                    else ItemStatus.REJECTED
                )
                connection.execute(
                    """
                    UPDATE items
                    SET status = ?, updated_at = ?
                    WHERE id = ? AND status = ?
                    """,
                    (
                        status.value,
                        now,
                        item_id,
                        ItemStatus.SCORED.value,
                    ),
                )

    def recent_delivered_cluster_ids(self, since: datetime) -> set[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT cluster_id
                FROM delivered_clusters
                WHERE delivered_at >= ?
                """,
                (since.astimezone(UTC).isoformat(),),
            ).fetchall()
        return {str(row["cluster_id"]) for row in rows}

    def update_article_text(self, item_id: int, article_text: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE items
                SET article_text = ?, updated_at = ?
                WHERE id = ?
                """,
                (article_text, _utc_now(), item_id),
            )

    def insert_brief(
        self,
        item_id: int,
        content: BriefContent,
        *,
        digest_date: date,
        digest_slot: str,
    ) -> int | None:
        now = _utc_now()
        with self.connect() as connection:
            selected = connection.execute(
                "SELECT 1 FROM items WHERE id = ? AND status = ?",
                (item_id, ItemStatus.SELECTED.value),
            ).fetchone()
            if selected is None:
                return None
            linkedin = content.get("linkedin_angle")
            instagram = content.get("instagram_carousel")
            linkedin_hook = linkedin["hook"] if linkedin is not None else None
            linkedin_points_json = (
                json.dumps(linkedin["points"], ensure_ascii=False)
                if linkedin is not None
                else None
            )
            instagram_slides_json = (
                json.dumps(instagram["slides"], ensure_ascii=False)
                if instagram is not None
                else None
            )
            instagram_cta = instagram["cta"] if instagram is not None else None
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO briefs (
                    item_id,
                    what_happened,
                    why_it_matters,
                    linkedin_hook,
                    linkedin_points_json,
                    instagram_slides_json,
                    instagram_cta,
                    caution,
                    digest_date,
                    digest_slot,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    content["what_happened"],
                    content["why_it_matters"],
                    linkedin_hook,
                    linkedin_points_json,
                    instagram_slides_json,
                    instagram_cta,
                    content["caution"],
                    digest_date.isoformat(),
                    digest_slot,
                    now,
                ),
            )
            if cursor.rowcount == 0:
                return None
            connection.execute(
                """
                UPDATE items
                SET status = ?, updated_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    ItemStatus.BRIEFED.value,
                    now,
                    item_id,
                    ItemStatus.SELECTED.value,
                ),
            )
            return int(cursor.lastrowid)

    def list_published_items(
        self,
        *,
        since_date: date | None = None,
        include_briefed: bool = False,
        digest_date: date | None = None,
        digest_slot: str | None = None,
    ) -> list[PublishedItem]:
        statuses = [ItemStatus.DELIVERED.value]
        if include_briefed:
            statuses.append(ItemStatus.BRIEFED.value)
        placeholders = ", ".join("?" for _ in statuses)
        query = f"""
            SELECT
                i.*,
                b.id AS brief_id,
                b.item_id AS brief_item_id,
                b.what_happened,
                b.why_it_matters,
                b.linkedin_hook,
                b.linkedin_points_json,
                b.instagram_slides_json,
                b.instagram_cta,
                b.caution,
                b.digest_date,
                b.digest_slot,
                b.created_at AS brief_created_at
            FROM briefs b
            JOIN items i ON i.id = b.item_id
            WHERE i.status IN ({placeholders})
        """
        parameters: list[str] = list(statuses)
        if since_date is not None:
            query += " AND b.digest_date >= ?"
            parameters.append(since_date.isoformat())
        if digest_date is not None:
            query += " AND b.digest_date = ?"
            parameters.append(digest_date.isoformat())
        if digest_slot is not None:
            query += " AND b.digest_slot = ?"
            parameters.append(digest_slot)
        query += (
            " ORDER BY b.digest_date DESC, b.digest_slot DESC,"
            " i.llm_score DESC, i.id DESC"
        )

        with self.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [_row_to_published_item(row) for row in rows]

    def mark_briefed_items_delivered(self, item_ids: list[int]) -> int:
        if not item_ids:
            return 0
        now = _utc_now()
        delivered_count = 0
        with self.connect() as connection:
            for item_id in item_ids:
                row = connection.execute(
                    """
                    SELECT canonical_url, cluster_id
                    FROM items
                    WHERE id = ? AND status = ?
                    """,
                    (item_id, ItemStatus.BRIEFED.value),
                ).fetchone()
                if row is None:
                    continue
                cluster_id = row["cluster_id"] or f"url:{row['canonical_url']}"
                connection.execute(
                    """
                    INSERT OR IGNORE INTO delivered_clusters (
                        cluster_id, delivered_at, item_id
                    )
                    VALUES (?, ?, ?)
                    """,
                    (cluster_id, now, item_id),
                )
                connection.execute(
                    """
                    UPDATE items
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (ItemStatus.DELIVERED.value, now, item_id),
                )
                delivered_count += 1
        return delivered_count


USER_VERSION = 1


def _migrate(connection: sqlite3.Connection) -> None:
    """Bring an existing database up to the current schema version.

    Version 1 makes the four social columns on ``briefs`` nullable so the
    pipeline can store summary-only briefs (LinkedIn/Instagram drafts are now
    generated on demand in the app). New databases already match the nullable
    schema, so only pre-existing ``NOT NULL`` tables need a rebuild.
    """
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version < 1:
        if _briefs_social_columns_not_null(connection):
            _rebuild_briefs_nullable(connection)
        # PRAGMA does not accept bound parameters; the value is a constant.
        connection.execute(f"PRAGMA user_version = {USER_VERSION}")


def _briefs_social_columns_not_null(connection: sqlite3.Connection) -> bool:
    rows = connection.execute("PRAGMA table_info(briefs)").fetchall()
    for row in rows:
        if row["name"] == "linkedin_hook":
            return bool(row["notnull"])
    return False


def _rebuild_briefs_nullable(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE briefs_new (
            id INTEGER PRIMARY KEY,
            item_id INTEGER NOT NULL,
            what_happened TEXT NOT NULL,
            why_it_matters TEXT NOT NULL,
            linkedin_hook TEXT,
            linkedin_points_json TEXT,
            instagram_slides_json TEXT,
            instagram_cta TEXT,
            caution TEXT NOT NULL,
            digest_date TEXT NOT NULL,
            digest_slot TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(item_id) REFERENCES items(id)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO briefs_new (
            id, item_id, what_happened, why_it_matters, linkedin_hook,
            linkedin_points_json, instagram_slides_json, instagram_cta,
            caution, digest_date, digest_slot, created_at
        )
        SELECT
            id, item_id, what_happened, why_it_matters, linkedin_hook,
            linkedin_points_json, instagram_slides_json, instagram_cta,
            caution, digest_date, digest_slot, created_at
        FROM briefs
        """
    )
    connection.execute("DROP TABLE briefs")
    connection.execute("ALTER TABLE briefs_new RENAME TO briefs")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_briefs_digest_date"
        " ON briefs(digest_date)"
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_briefs_item_id"
        " ON briefs(item_id)"
    )


def _row_to_item(row: sqlite3.Row) -> Item:
    return Item(
        id=int(row["id"]),
        url=str(row["url"]),
        canonical_url=str(row["canonical_url"]),
        title=str(row["title"]),
        source=str(row["source"]),
        snippet=row["snippet"],
        published_at=row["published_at"],
        score_hint=float(row["score_hint"]),
        first_seen_at=str(row["first_seen_at"]),
        cluster_id=row["cluster_id"],
        cluster_representative=bool(row["cluster_representative"]),
        llm_score=row["llm_score"],
        llm_category=row["llm_category"],
        llm_reason=row["llm_reason"],
        status=ItemStatus(row["status"]),
        article_text=row["article_text"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_published_item(row: sqlite3.Row) -> PublishedItem:
    linkedin_points = (
        tuple(json.loads(row["linkedin_points_json"]))
        if row["linkedin_points_json"] is not None
        else None
    )
    instagram_slides = (
        tuple(json.loads(row["instagram_slides_json"]))
        if row["instagram_slides_json"] is not None
        else None
    )
    return PublishedItem(
        item=_row_to_item(row),
        brief=Brief(
            id=int(row["brief_id"]),
            item_id=int(row["brief_item_id"]),
            what_happened=str(row["what_happened"]),
            why_it_matters=str(row["why_it_matters"]),
            linkedin_hook=row["linkedin_hook"],
            linkedin_points=linkedin_points,
            instagram_slides=instagram_slides,
            instagram_cta=row["instagram_cta"],
            caution=str(row["caution"]),
            digest_date=str(row["digest_date"]),
            digest_slot=str(row["digest_slot"]),
            created_at=str(row["brief_created_at"]),
        ),
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
