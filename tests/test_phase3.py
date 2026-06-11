from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from newsbeat_digest.config import Settings
from newsbeat_digest.db import Database
from newsbeat_digest.models import Item, ItemStatus, RawItem, ScoreResult
from newsbeat_digest.pipeline.phase3 import score_and_select


def test_phase3_clusters_scores_and_selects_without_live_llm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "profile.md").write_text(
        "# Profile\nPractical AI tools and EU policy.",
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_DIGEST_DATABASE_PATH", str(tmp_path / "digest.db"))
    settings = Settings.from_env(tmp_path)
    database = Database(settings.database_path)
    database.initialize()
    for index, title in enumerate(
        [
            "European Commission publishes AI Office guidance",
            "A practical AI coding tool launches",
        ]
    ):
        database.insert_item(
            RawItem(
                title=title,
                url=f"https://example.com/{index}",
                published_at=None,
                source="Example",
            )
        )

    class FakeScoreClient:
        def score_batch(
            self,
            items: Sequence[Item],
            profile: str,
        ) -> list[ScoreResult]:
            assert "Practical AI tools" in profile
            return [
                ScoreResult(
                    item_id=item.id,
                    category="policy" if "Commission" in item.title else "tools",
                    relevance=7,
                    reason="Relevant to the profile.",
                )
                for item in items
            ]

    result = score_and_select(
        settings,
        database,
        score_client=FakeScoreClient(),
        now=datetime(2026, 6, 10, tzinfo=UTC),
    )

    selected = database.list_items(ItemStatus.SELECTED)
    assert result.scored_items == 2
    assert result.selected_items == 2
    assert len(selected) == 2
    policy = next(item for item in selected if item.llm_category == "policy")
    assert policy.llm_score == 9
