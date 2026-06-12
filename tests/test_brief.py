from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from newsbeat_digest.config import Settings
from newsbeat_digest.db import Database
from newsbeat_digest.models import BriefContent, Item, ItemStatus, RawItem
from newsbeat_digest.pipeline.article import ArticleText, extract_article_text
from newsbeat_digest.pipeline.brief import (
    BRIEF_SCHEMA,
    generate_briefs,
    validate_brief_content,
)
from newsbeat_digest.sources.base import HttpClient


CONTENT: BriefContent = {
    "what_happened": "A lab released a model. It published benchmark details.",
    "why_it_matters": "The release may improve local workflows. The claims need independent testing.",
    "caution": "Only the publisher's evidence is currently available.",
}


def test_extract_article_text_prefers_article_and_removes_navigation() -> None:
    html = """
    <html><body><nav>This navigation text should be removed completely.</nav>
    <article>
      <h1>A significant model release for developers</h1>
      <p>The model adds a useful capability with documented benchmark results.</p>
      <p>Developers can test the release through the provider's public API.</p>
    </article></body></html>
    """

    text = extract_article_text(html)

    assert "significant model release" in text
    assert "documented benchmark" in text
    assert "navigation text" not in text


def test_generate_briefs_persists_validated_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _selected_database(tmp_path)
    settings = _settings(tmp_path, monkeypatch)

    class FakeGenerator:
        def generate(self, item: Item, article: ArticleText) -> BriefContent:
            assert item.status is ItemStatus.SELECTED
            assert article.extracted
            return CONTENT

    html = (
        "<article><p>"
        + ("Useful sourced article content for testing extraction. " * 8)
        + "</p></article>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, request=request)

    client = HttpClient(httpx.Client(transport=httpx.MockTransport(handler)))
    created, failed = generate_briefs(
        settings,
        database,
        generator=FakeGenerator(),
        client=client,
        now=datetime(2026, 6, 10, 9, tzinfo=ZoneInfo("Europe/Tallinn")),
    )

    assert (created, failed) == (1, 0)
    published = database.list_published_items(include_briefed=True)
    assert len(published) == 1
    assert published[0].item.status is ItemStatus.BRIEFED
    brief = published[0].brief
    assert brief.what_happened == CONTENT["what_happened"]
    assert brief.caution == CONTENT["caution"]
    # Summary-only briefs leave the social drafts unset; the app fills them in.
    assert brief.linkedin_hook is None
    assert brief.linkedin_points is None
    assert brief.instagram_slides is None
    assert brief.instagram_cta is None


def test_brief_validation_rejects_legacy_social_fields() -> None:
    invalid = {
        **CONTENT,
        "linkedin_angle": {
            "hook": "Old shape",
            "points": ["One", "Two", "Three"],
        },
    }

    with pytest.raises(ValueError, match="missing or unexpected fields"):
        validate_brief_content(invalid)


def test_anthropic_brief_schema_is_summary_only() -> None:
    assert set(BRIEF_SCHEMA["properties"]) == {
        "what_happened",
        "why_it_matters",
        "caution",
    }
    assert BRIEF_SCHEMA["required"] == [
        "what_happened",
        "why_it_matters",
        "caution",
    ]
    assert BRIEF_SCHEMA["additionalProperties"] is False


def test_article_failure_falls_back_and_does_not_block_brief(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _selected_database(tmp_path)
    settings = _settings(tmp_path, monkeypatch)

    class FakeGenerator:
        def generate(self, item: Item, article: ArticleText) -> BriefContent:
            assert not article.extracted
            assert "Full article text was unavailable" in article.text
            return CONTENT

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    client = HttpClient(httpx.Client(transport=httpx.MockTransport(handler)))
    created, failed = generate_briefs(
        settings,
        database,
        generator=FakeGenerator(),
        client=client,
        now=datetime(2026, 6, 10, 9, tzinfo=ZoneInfo("Europe/Tallinn")),
    )

    assert (created, failed) == (1, 0)


def _selected_database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "digest.db")
    database.initialize()
    item_id = database.insert_item(
        RawItem(
            title="A significant AI model release",
            url="https://example.com/release",
            published_at="2026-06-10T06:00:00+00:00",
            source="Example Lab",
            snippet="The publisher describes a new model.",
        )
    )
    assert item_id is not None
    with database.connect() as connection:
        connection.execute(
            """
            UPDATE items
            SET status = 'selected',
                llm_score = 9.1,
                llm_category = 'models',
                cluster_id = 'model-release'
            WHERE id = ?
            """,
            (item_id,),
        )
    return database


def _settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Settings:
    monkeypatch.setenv("AI_DIGEST_DATABASE_PATH", str(tmp_path / "digest.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return Settings.from_env(tmp_path)
