"""Batch LLM scoring with local validation and deterministic policy boosts."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from anthropic import Anthropic

from newsbeat_digest.models import Item, ScoreResult


ALLOWED_CATEGORIES = {
    "models",
    "tools",
    "research",
    "policy",
    "business",
    "other",
}
POLICY_SIGNALS = (
    "eu ai act",
    "european commission",
    "estonia",
    "estonian",
    "e-estonia",
    "european union",
    "brussels",
    "ai office",
)
SCORE_BATCH_SIZE = 30

SCORE_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "id": {"type": "integer"},
            "category": {
                "type": "string",
                "enum": sorted(ALLOWED_CATEGORIES),
            },
            "relevance": {
                "type": "number",
                "description": (
                    "Relevance score from 0 through 10, inclusive. "
                    "The application validates this range."
                ),
            },
            "reason": {"type": "string"},
        },
        "required": ["id", "category", "relevance", "reason"],
    },
}


class ScoreClient(Protocol):
    def score_batch(
        self,
        items: Sequence[Item],
        profile: str,
    ) -> list[ScoreResult]:
        """Score every supplied item or raise when the batch is invalid."""


class AnthropicScoreClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        client: Anthropic | None = None,
    ) -> None:
        self._client = client or Anthropic(api_key=api_key)
        self._model = model

    def score_batch(
        self,
        items: Sequence[Item],
        profile: str,
    ) -> list[ScoreResult]:
        last_error: Exception | None = None
        expected_ids = {item.id for item in items}
        for attempt in range(2):
            try:
                message = self._client.messages.create(
                    model=self._model,
                    max_tokens=2_500,
                    temperature=0,
                    output_config={
                        "format": {
                            "type": "json_schema",
                            "schema": SCORE_SCHEMA,
                        }
                    },
                    system=(
                        "You rank AI news for one reader. Use only the supplied "
                        "title, snippet, source, and interest profile. Return "
                        "one score for every item. Favor consequential model "
                        "releases, practical tools, meaningful research, and "
                        "EU or Estonia AI policy. Deprioritize hype, generic "
                        "opinion, listicles, and thin announcements."
                    ),
                    messages=[
                        {
                            "role": "user",
                            "content": _score_prompt(items, profile),
                        }
                    ],
                )
                text = next(
                    block.text
                    for block in message.content
                    if block.type == "text"
                )
                return validate_score_results(
                    json.loads(text),
                    expected_ids=expected_ids,
                )
            except Exception as exc:
                last_error = exc
                logging.getLogger(__name__).warning(
                    "Score response failed validation: attempt=%d error=%s",
                    attempt + 1,
                    exc,
                )
        assert last_error is not None
        raise last_error


def score_items(
    items: Sequence[Item],
    profile: str,
    client: ScoreClient,
) -> tuple[list[ScoreResult], int]:
    results: list[ScoreResult] = []
    failed = 0
    logger = logging.getLogger(__name__)
    for start in range(0, len(items), SCORE_BATCH_SIZE):
        batch = items[start : start + SCORE_BATCH_SIZE]
        try:
            scores = client.score_batch(batch, profile)
            validated = validate_score_results(
                [
                    {
                        "id": score.item_id,
                        "category": score.category,
                        "relevance": score.relevance,
                        "reason": score.reason,
                    }
                    for score in scores
                ],
                expected_ids={item.id for item in batch},
            )
            results.extend(
                apply_policy_boost(score, _item_by_id(batch, score.item_id))
                for score in validated
            )
        except Exception as exc:
            failed += len(batch)
            logger.error(
                "Scoring batch failed: item_ids=%s error=%s",
                ",".join(str(item.id) for item in batch),
                exc,
            )
    return results, failed


def validate_score_results(
    value: object,
    *,
    expected_ids: set[int],
) -> list[ScoreResult]:
    if not isinstance(value, list):
        raise ValueError("score response must be a JSON array")
    results: list[ScoreResult] = []
    seen_ids: set[int] = set()
    for entry in value:
        if not isinstance(entry, Mapping):
            raise ValueError("each score must be an object")
        if set(entry) != {"id", "category", "relevance", "reason"}:
            raise ValueError("score has missing or unexpected fields")
        item_id = entry["id"]
        relevance = entry["relevance"]
        reason = entry["reason"]
        category = entry["category"]
        if not isinstance(item_id, int) or isinstance(item_id, bool):
            raise ValueError("score id must be an integer")
        if (
            not isinstance(relevance, (int, float))
            or isinstance(relevance, bool)
            or not 0 <= float(relevance) <= 10
        ):
            raise ValueError("relevance must be between 0 and 10")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        if not isinstance(category, str):
            raise ValueError("category must be a string")
        if item_id in seen_ids:
            raise ValueError(f"duplicate score id: {item_id}")
        seen_ids.add(item_id)
        results.append(
            ScoreResult(
                item_id=item_id,
                category=(
                    category if category in ALLOWED_CATEGORIES else "other"
                ),
                relevance=float(relevance),
                reason=reason.strip(),
            )
        )
    if seen_ids != expected_ids:
        raise ValueError("score response does not contain every requested id")
    return results


def apply_policy_boost(score: ScoreResult, item: Item) -> ScoreResult:
    text = " ".join(
        part for part in (item.title, item.snippet, item.source) if part
    ).casefold()
    if not any(signal in text for signal in POLICY_SIGNALS):
        return score
    return ScoreResult(
        item_id=score.item_id,
        category=score.category,
        relevance=min(10.0, score.relevance + 2.0),
        reason=f"{score.reason} EU/Estonia policy relevance boost applied.",
    )


def _score_prompt(items: Sequence[Item], profile: str) -> str:
    item_payload = [
        {
            "id": item.id,
            "title": item.title,
            "source": item.source,
            "snippet": item.snippet,
            "score_hint": item.score_hint,
            "published_at": item.published_at,
        }
        for item in items
    ]
    return (
        "Interest profile:\n<profile>\n"
        f"{profile}\n</profile>\n\n"
        "Score each item from 0 to 10 for this profile. Categories are "
        "models, tools, research, policy, business, or other. A 6 means "
        "strong enough to consider for a limited digest; reserve 9-10 for "
        "exceptional stories.\n\nItems:\n"
        f"{json.dumps(item_payload, ensure_ascii=False)}"
    )


def _item_by_id(items: Sequence[Item], item_id: int) -> Item:
    return next(item for item in items if item.id == item_id)
