"""Configurable RSS and Atom feed source."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime, timedelta
from time import struct_time
from typing import Any

import feedparser

from newsbeat_digest.models import RawItem
from newsbeat_digest.sources.base import HttpClient, Source
from newsbeat_digest.sources.hn import _plain_text


class RssSource(Source):
    def __init__(
        self,
        name: str,
        url: str,
        client: HttpClient,
        *,
        lookback_hours: int = 12,
    ) -> None:
        self.name = name
        self.url = url
        self.client = client
        self.lookback_hours = lookback_hours

    def fetch(self) -> list[RawItem]:
        response = self.client.get(self.url)
        feed = feedparser.parse(response.content)
        if feed.bozo and not feed.entries:
            raise ValueError(f"Malformed feed: {feed.bozo_exception}")

        cutoff = datetime.now(UTC) - timedelta(hours=self.lookback_hours)
        items: list[RawItem] = []
        for entry in feed.entries:
            published = _entry_datetime(entry)
            if published is not None and published < cutoff:
                continue
            title = _plain_text(entry.get("title")) or ""
            url = str(entry.get("link") or "").strip()
            if not title or not url:
                continue
            summary = _plain_text(
                entry.get("summary") or entry.get("description")
            )
            items.append(
                RawItem(
                    title=title,
                    url=url,
                    published_at=published.isoformat() if published else None,
                    source=self.name,
                    snippet=summary,
                )
            )
        return items


def _entry_datetime(entry: Any) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not isinstance(parsed, struct_time):
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)
