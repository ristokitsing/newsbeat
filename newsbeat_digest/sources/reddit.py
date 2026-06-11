"""Reddit collection through public JSON endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from newsbeat_digest.models import RawItem
from newsbeat_digest.sources.base import HttpClient, Source


class RedditSource(Source):
    def __init__(
        self,
        subreddit: str,
        client: HttpClient,
        *,
        min_score: int = 100,
        lookback_hours: int = 12,
    ) -> None:
        self.subreddit = subreddit
        self.client = client
        self.min_score = min_score
        self.lookback_hours = lookback_hours
        self.name = f"Reddit r/{subreddit}"

    def fetch(self) -> list[RawItem]:
        payload = self.client.get_json(
            f"https://www.reddit.com/r/{self.subreddit}/top.json",
            params={"t": "day", "limit": 100, "raw_json": 1},
        )
        cutoff = datetime.now(UTC) - timedelta(hours=self.lookback_hours)
        items: list[RawItem] = []
        children = payload.get("data", {}).get("children", [])
        for child in children:
            data: dict[str, Any] = child.get("data", {})
            score = float(data.get("score") or 0)
            created_at = datetime.fromtimestamp(
                float(data.get("created_utc") or 0),
                tz=UTC,
            )
            if score < self.min_score or created_at < cutoff:
                continue
            title = str(data.get("title") or "").strip()
            url = str(
                data.get("url_overridden_by_dest")
                or data.get("url")
                or ""
            ).strip()
            if not url:
                permalink = str(data.get("permalink") or "")
                url = f"https://www.reddit.com{permalink}"
            if not title or not url:
                continue
            snippet = str(data.get("selftext") or "").strip() or None
            items.append(
                RawItem(
                    title=title,
                    url=url,
                    published_at=created_at.isoformat(),
                    source=self.name,
                    snippet=snippet,
                    score_hint=score,
                )
            )
        return items
