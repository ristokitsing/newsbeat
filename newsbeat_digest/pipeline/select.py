"""Rank scored stories and apply digest selection constraints."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from newsbeat_digest.db import Database
from newsbeat_digest.models import Item, ItemStatus, RankedItem


MIN_RELEVANCE = 6.0
MAX_PER_CATEGORY = 2
REDELIVERY_WINDOW_DAYS = 7


def rank_items(items: Sequence[Item]) -> list[RankedItem]:
    ranked = [
        RankedItem(item=item, rank=ranking_score(item))
        for item in items
        if item.llm_score is not None
    ]
    return sorted(
        ranked,
        key=lambda entry: (entry.rank, entry.item.score_hint, entry.item.id),
        reverse=True,
    )


def ranking_score(item: Item) -> float:
    relevance = item.llm_score or 0.0
    return relevance * 2.0 + math.log(max(item.score_hint, 0.0) + 1.0)


def select_items(
    database: Database,
    *,
    max_items: int,
    now: datetime | None = None,
) -> tuple[list[RankedItem], list[int]]:
    candidates = [
        item
        for item in database.list_items(ItemStatus.SCORED)
        if item.cluster_representative
    ]
    ranked = rank_items(candidates)
    if not ranked:
        return [], []

    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)
    delivered_clusters = database.recent_delivered_cluster_ids(
        current_time - timedelta(days=REDELIVERY_WINDOW_DAYS)
    )
    already_selected = database.list_items(ItemStatus.SELECTED)
    category_counts = Counter(
        item.llm_category or "other" for item in already_selected
    )
    remaining = max(0, max_items - len(already_selected))
    selected_ids: list[int] = []

    for entry in ranked:
        item = entry.item
        category = item.llm_category or "other"
        if remaining == 0:
            break
        if (item.llm_score or 0.0) < MIN_RELEVANCE:
            continue
        if item.cluster_id in delivered_clusters:
            continue
        if category_counts[category] >= MAX_PER_CATEGORY:
            continue
        selected_ids.append(item.id)
        category_counts[category] += 1
        remaining -= 1

    database.select_scored_items(
        selected_ids,
        [entry.item.id for entry in ranked],
    )
    return ranked, selected_ids
