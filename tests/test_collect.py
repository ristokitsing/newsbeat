from __future__ import annotations

from pathlib import Path

import pytest

from newsbeat_digest.collect import collect_items
from newsbeat_digest.db import Database
from newsbeat_digest.models import RawItem
from newsbeat_digest.sources import SourceCollection


def test_collection_canonicalizes_and_deduplicates_urls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = Database(tmp_path / "digest.db")
    database.initialize()
    items = (
        RawItem(
            title="First",
            url="https://Example.com/story/?utm_source=one",
            published_at=None,
            source="test",
        ),
        RawItem(
            title="Duplicate",
            url="https://example.com/story?fbclid=two",
            published_at=None,
            source="test",
        ),
    )
    monkeypatch.setattr(
        "newsbeat_digest.collect.load_sources",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "newsbeat_digest.collect.fetch_all",
        lambda sources: SourceCollection(items, ()),
    )

    result = collect_items(database, tmp_path / "sources.yaml")

    assert len(result.inserted) == 1
    assert database.count_items() == 1
    assert database.list_items()[0].canonical_url == (
        "https://example.com/story"
    )
