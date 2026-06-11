from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from newsbeat_digest.config import Settings
from newsbeat_digest.db import Database
from newsbeat_digest.models import (
    BriefContent,
    Item,
    ItemStatus,
    RawItem,
    ScoreResult,
)
from newsbeat_digest.pipeline.article import ArticleText
from newsbeat_digest.pipeline.brief import generate_briefs
from newsbeat_digest.pipeline.phase3 import score_and_select
from newsbeat_digest.publish import publish_digest
from newsbeat_digest.sources.base import HttpClient


def test_pipeline_from_new_item_to_idempotent_feed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "profile.md").write_text(
        "# Profile\nPractical AI tools.",
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_DIGEST_DATABASE_PATH", str(tmp_path / "digest.db"))
    settings = Settings.from_env(tmp_path)
    database = Database(settings.database_path)
    database.initialize()
    database.insert_item(
        RawItem(
            title="A practical AI tool launches",
            url="https://example.com/tool",
            published_at="2026-06-10T08:00:00+00:00",
            source="Example",
            snippet="The tool automates a developer workflow.",
        )
    )

    class FakeScoreClient:
        def score_batch(
            self,
            items: Sequence[Item],
            profile: str,
        ) -> list[ScoreResult]:
            return [
                ScoreResult(item.id, "tools", 8, "Strong practical value.")
                for item in items
            ]

    class FakeBriefGenerator:
        def generate(
            self,
            item: Item,
            article: ArticleText,
        ) -> BriefContent:
            return {
                "what_happened": "A practical AI tool launched. The source describes its workflow.",
                "why_it_matters": "It may save developers time. Real-world reliability still needs testing.",
                "linkedin_angle": {
                    "hook": "AI tools matter when the workflow improves.",
                    "points": ["Time saved", "Quality retained", "Cost measured"],
                },
                "instagram_carousel": {
                    "slides": ["New AI tool", "The workflow", "Potential value", "What to test"],
                    "cta": "Would this improve your workflow?",
                },
                "caution": "The claims come from the launch source.",
            }

    html = "<article><p>" + ("Detailed launch information. " * 20) + "</p></article>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, request=request)

    now = datetime(2026, 6, 10, 15, tzinfo=ZoneInfo("Europe/Tallinn"))
    phase3 = score_and_select(
        settings,
        database,
        score_client=FakeScoreClient(),
        now=now,
    )
    created, failed = generate_briefs(
        settings,
        database,
        generator=FakeBriefGenerator(),
        client=HttpClient(
            httpx.Client(transport=httpx.MockTransport(handler))
        ),
        now=now,
    )
    first_publish = publish_digest(settings, database, now=now)
    second_publish = publish_digest(settings, database, now=now)

    payload = json.loads(
        first_publish.json_path.read_text(encoding="utf-8")
    )
    assert phase3.selected_items == 1
    assert (created, failed) == (1, 0)
    assert len(payload["items"]) == 1
    assert first_publish.delivered_items == 1
    assert second_publish.delivered_items == 0
    assert database.count_items(ItemStatus.DELIVERED) == 1
