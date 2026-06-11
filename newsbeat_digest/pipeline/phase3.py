"""Orchestrate clustering, scoring, ranking, and selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from newsbeat_digest.config import Settings
from newsbeat_digest.db import Database
from newsbeat_digest.models import ItemStatus, RankedItem
from newsbeat_digest.pipeline.dedupe import cluster_new_items
from newsbeat_digest.pipeline.score import (
    AnthropicScoreClient,
    ScoreClient,
    score_items,
)
from newsbeat_digest.pipeline.select import select_items


@dataclass(frozen=True, slots=True)
class Phase3Result:
    clustered_representatives: int
    duplicate_items: int
    scored_items: int
    failed_items: int
    selected_items: int
    ranked: tuple[RankedItem, ...]


def score_and_select(
    settings: Settings,
    database: Database,
    *,
    score_client: ScoreClient | None = None,
    now: datetime | None = None,
) -> Phase3Result:
    if (
        database.count_items(ItemStatus.NEW)
        and score_client is None
        and not settings.anthropic_api_key
    ):
        raise ValueError(
            "ANTHROPIC_API_KEY is required when new items need scoring"
        )
    representatives, duplicates = cluster_new_items(database)
    pending = [
        item
        for item in database.list_items(ItemStatus.NEW)
        if item.cluster_representative
    ]
    failed = 0
    scored_count = 0
    if pending:
        if score_client is None:
            assert settings.anthropic_api_key is not None
            if not settings.score_model:
                raise ValueError("AI_DIGEST_SCORE_MODEL must not be empty")
            score_client = AnthropicScoreClient(
                settings.anthropic_api_key,
                settings.score_model,
            )
        profile_path = settings.project_root / "profile.md"
        profile = profile_path.read_text(encoding="utf-8")
        scores, failed = score_items(pending, profile, score_client)
        scored_count = database.save_scores(scores)

    ranked, selected_ids = select_items(
        database,
        max_items=settings.max_items,
        now=now,
    )
    refreshed = {item.id: item for item in database.list_items()}
    ranked = [
        RankedItem(item=refreshed[entry.item.id], rank=entry.rank)
        for entry in ranked
    ]
    return Phase3Result(
        clustered_representatives=representatives,
        duplicate_items=duplicates,
        scored_items=scored_count,
        failed_items=failed,
        selected_items=len(selected_ids),
        ranked=tuple(ranked),
    )
