"""Coordinate static digest publishing and delivery persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from newsbeat_digest.config import Settings
from newsbeat_digest.db import Database
from newsbeat_digest.models import ItemStatus
from newsbeat_digest.publish.archive import render_markdown_digest
from newsbeat_digest.publish.feed_json import render_json_feed
from newsbeat_digest.publish.feed_rss import render_rss_feed


FEED_HISTORY_DAYS = 7


@dataclass(frozen=True, slots=True)
class PublishResult:
    feed_items: int
    delivered_items: int
    json_path: Path
    rss_path: Path
    archive_path: Path


def publish_digest(
    settings: Settings,
    database: Database,
    *,
    now: datetime | None = None,
) -> PublishResult:
    local_now = now or datetime.now(ZoneInfo(settings.timezone))
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=ZoneInfo(settings.timezone))
    generated_at = local_now.astimezone(UTC)
    digest_date = local_now.date()
    digest_slot = "am" if local_now.hour < 12 else "pm"
    since_date = digest_date - timedelta(days=FEED_HISTORY_DAYS - 1)

    feed_items = database.list_published_items(
        since_date=since_date,
        include_briefed=True,
    )
    archive_items = database.list_published_items(
        include_briefed=True,
        digest_date=digest_date,
        digest_slot=digest_slot,
    )
    briefed_ids = [
        entry.item.id
        for entry in feed_items
        if entry.item.status is ItemStatus.BRIEFED
    ]

    json_path = settings.project_root / "feed" / "digest.json"
    rss_path = settings.project_root / "feed" / "digest.xml"
    archive_path = (
        settings.project_root
        / "digests"
        / f"{digest_date.isoformat()}-{digest_slot}.md"
    )
    _atomic_write(
        json_path,
        render_json_feed(
            feed_items,
            generated_at=generated_at,
            timezone=settings.timezone,
        ),
    )
    _atomic_write(
        rss_path,
        render_rss_feed(
            feed_items,
            generated_at=generated_at,
            pages_url=settings.pages_url,
        ),
    )
    _atomic_write(
        archive_path,
        render_markdown_digest(
            archive_items,
            digest_date=digest_date,
            digest_slot=digest_slot,
        ),
    )
    delivered = database.mark_briefed_items_delivered(briefed_ids)
    return PublishResult(
        feed_items=len(feed_items),
        delivered_items=delivered,
        json_path=json_path,
        rss_path=rss_path,
        archive_path=archive_path,
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
