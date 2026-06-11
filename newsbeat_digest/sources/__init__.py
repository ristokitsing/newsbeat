"""Source configuration, construction, and failure-isolated collection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from newsbeat_digest.models import RawItem
from newsbeat_digest.sources.arxiv import ArxivSource
from newsbeat_digest.sources.base import HttpClient, Source
from newsbeat_digest.sources.hn import HackerNewsSource
from newsbeat_digest.sources.reddit import RedditSource
from newsbeat_digest.sources.rss import RssSource


@dataclass(frozen=True, slots=True)
class SourceCollection:
    items: tuple[RawItem, ...]
    failed_sources: tuple[str, ...]


def load_sources(
    path: Path,
    client: HttpClient,
    *,
    lookback_hours: int,
) -> list[Source]:
    if not path.is_file():
        raise FileNotFoundError(f"Source configuration not found: {path}")
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, dict):
        raise ValueError("sources.yaml must contain a mapping")

    sources: list[Source] = []
    hackernews = _mapping(document.get("hackernews"))
    if hackernews.get("enabled", False):
        sources.append(
            HackerNewsSource(
                client,
                lookback_hours=lookback_hours,
                min_points_default=int(
                    hackernews.get("min_points_default", 30)
                ),
                min_points_strong_keyword=int(
                    hackernews.get("min_points_strong_keyword", 10)
                ),
            )
        )

    for entry in _list(document.get("rss")):
        config = _mapping(entry)
        if config.get("enabled", False):
            sources.append(
                RssSource(
                    name=str(config["name"]),
                    url=str(config["url"]),
                    client=client,
                    lookback_hours=lookback_hours,
                )
            )

    for entry in _list(document.get("reddit")):
        config = _mapping(entry)
        if config.get("enabled", False):
            sources.append(
                RedditSource(
                    subreddit=str(config["subreddit"]),
                    client=client,
                    min_score=int(config.get("min_score", 100)),
                    lookback_hours=lookback_hours,
                )
            )

    arxiv = _mapping(document.get("arxiv"))
    if arxiv.get("enabled", False):
        sources.append(ArxivSource())
    return sources


def fetch_all(sources: list[Source]) -> SourceCollection:
    logger = logging.getLogger(__name__)
    items: list[RawItem] = []
    failed_sources: list[str] = []
    for source in sources:
        try:
            source_items = source.fetch()
        except Exception as exc:
            failed_sources.append(source.name)
            logger.error(
                "Source failed: source=%s error=%s",
                source.name,
                exc,
            )
            continue
        items.extend(source_items)
        logger.info(
            "Source fetched: source=%s item_count=%d",
            source.name,
            len(source_items),
        )
    return SourceCollection(tuple(items), tuple(failed_sources))


def _mapping(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Source configuration entry must be a mapping")
    return value


def _list(value: object) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Source configuration section must be a list")
    return value
