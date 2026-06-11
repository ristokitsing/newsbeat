"""Hacker News collection through the Algolia API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
import re
from typing import Any

from newsbeat_digest.models import RawItem
from newsbeat_digest.sources.base import HttpClient, Source


ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"
DEFAULT_KEYWORDS = (
    "claude",
    "anthropic",
    "openai",
    "gpt",
    "llm",
    "gemini",
    "deepmind",
    "mistral",
    "llama",
    "diffusion",
    "transformer",
    "ai act",
    "ai regulation",
    "agents",
    "rag",
    "fine-tuning",
    "inference",
)
STRONG_KEYWORDS = {
    "anthropic",
    "claude",
    "deepmind",
    "gemini",
    "gpt",
    "llama",
    "mistral",
    "openai",
    "ai act",
    "ai regulation",
}


class HackerNewsSource(Source):
    name = "Hacker News"

    def __init__(
        self,
        client: HttpClient,
        *,
        lookback_hours: int = 12,
        min_points_default: int = 30,
        min_points_strong_keyword: int = 10,
        keywords: tuple[str, ...] = DEFAULT_KEYWORDS,
    ) -> None:
        self.client = client
        self.lookback_hours = lookback_hours
        self.min_points_default = min_points_default
        self.min_points_strong_keyword = min_points_strong_keyword
        self.keywords = keywords

    def fetch(self) -> list[RawItem]:
        since = datetime.now(UTC) - timedelta(hours=self.lookback_hours)
        hits_by_id: dict[str, dict[str, Any]] = {}
        for keyword in self.keywords:
            payload = self.client.get_json(
                ALGOLIA_URL,
                params={
                    "query": keyword,
                    "tags": "story",
                    "numericFilters": (
                        f"created_at_i>{int(since.timestamp())},"
                        f"points>={self.min_points_strong_keyword}"
                    ),
                    "hitsPerPage": 50,
                },
            )
            for hit in payload.get("hits", []):
                object_id = str(hit.get("objectID", ""))
                if object_id:
                    hits_by_id[object_id] = hit

        items: list[RawItem] = []
        for object_id, hit in hits_by_id.items():
            title = str(hit.get("title") or "").strip()
            points = float(hit.get("points") or 0)
            if not _contains_ai_keyword(title, self.keywords):
                continue
            threshold = (
                self.min_points_strong_keyword
                if _contains_strong_keyword(title)
                else self.min_points_default
            )
            if not title or points < threshold:
                continue

            story_url = str(hit.get("url") or "").strip()
            url = story_url or f"https://news.ycombinator.com/item?id={object_id}"
            items.append(
                RawItem(
                    title=title,
                    url=url,
                    published_at=_normalize_datetime(hit.get("created_at")),
                    source=self.name,
                    snippet=_plain_text(hit.get("story_text")),
                    score_hint=points,
                )
            )
        return items


def _contains_strong_keyword(title: str) -> bool:
    return any(_has_term(title, keyword) for keyword in STRONG_KEYWORDS)


def _contains_ai_keyword(title: str, keywords: tuple[str, ...]) -> bool:
    return any(_has_term(title, keyword) for keyword in keywords)


def _has_term(text: str, term: str) -> bool:
    pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _normalize_datetime(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone(UTC).isoformat()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self.parts.append(stripped)


def _plain_text(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parser = _TextExtractor()
    parser.feed(value)
    return " ".join(parser.parts)
