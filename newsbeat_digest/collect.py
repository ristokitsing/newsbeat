"""Collection stage orchestration and database persistence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from newsbeat_digest.db import Database
from newsbeat_digest.models import RawItem
from newsbeat_digest.pipeline.normalize import canonicalize_url
from newsbeat_digest.sources import fetch_all, load_sources
from newsbeat_digest.sources.base import HttpClient


@dataclass(frozen=True, slots=True)
class InsertedItem:
    id: int
    item: RawItem


@dataclass(frozen=True, slots=True)
class CollectionResult:
    inserted: tuple[InsertedItem, ...]
    fetched_count: int
    failed_sources: tuple[str, ...]


def collect_items(
    database: Database,
    sources_path: Path,
    *,
    lookback_hours: int = 12,
) -> CollectionResult:
    with HttpClient() as client:
        sources = load_sources(
            sources_path,
            client,
            lookback_hours=lookback_hours,
        )
        fetched = fetch_all(sources)

    inserted: list[InsertedItem] = []
    for raw_item in fetched.items:
        canonical_url = canonicalize_url(raw_item.url)
        item_id = database.insert_item(raw_item, canonical_url=canonical_url)
        if item_id is not None:
            inserted.append(InsertedItem(item_id, raw_item))
    return CollectionResult(
        inserted=tuple(inserted),
        fetched_count=len(fetched.items),
        failed_sources=fetched.failed_sources,
    )
