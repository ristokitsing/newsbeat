import json
from types import SimpleNamespace

import pytest

from newsbeat_digest.models import Item, ItemStatus, ScoreResult
from newsbeat_digest.pipeline.score import (
    SCORE_SCHEMA,
    AnthropicScoreClient,
    apply_policy_boost,
    validate_score_results,
)


def test_score_validation_maps_unknown_category_to_other() -> None:
    result = validate_score_results(
        [
            {
                "id": 12,
                "category": "security",
                "relevance": 7,
                "reason": "Meaningful impact.",
            }
        ],
        expected_ids={12},
    )

    assert result == [
        ScoreResult(
            item_id=12,
            category="other",
            relevance=7.0,
            reason="Meaningful impact.",
        )
    ]


def test_score_validation_requires_every_requested_id() -> None:
    with pytest.raises(ValueError, match="every requested id"):
        validate_score_results([], expected_ids={1})


def test_anthropic_score_schema_avoids_unsupported_numeric_constraints() -> None:
    relevance = SCORE_SCHEMA["items"]["properties"]["relevance"]

    assert relevance["type"] == "number"
    assert "minimum" not in relevance
    assert "maximum" not in relevance


def test_eu_policy_boost_is_deterministic_and_capped() -> None:
    item = _item(
        title="European Commission publishes EU AI Act guidance",
    )
    score = ScoreResult(1, "policy", 9.0, "Important guidance.")

    boosted = apply_policy_boost(score, item)

    assert boosted.relevance == 10.0
    assert "boost applied" in boosted.reason


def test_anthropic_score_client_retries_invalid_response_once() -> None:
    attempts = 0

    class FakeMessages:
        def create(self, **kwargs: object) -> object:
            nonlocal attempts
            attempts += 1
            payload = (
                []
                if attempts == 1
                else [
                    {
                        "id": 1,
                        "category": "tools",
                        "relevance": 8,
                        "reason": "Practical impact.",
                    }
                ]
            )
            return SimpleNamespace(
                content=[
                    SimpleNamespace(type="text", text=json.dumps(payload))
                ]
            )

    fake_client = SimpleNamespace(messages=FakeMessages())
    client = AnthropicScoreClient(
        "test-key",
        "test-model",
        client=fake_client,
    )

    result = client.score_batch([_item(title="Useful AI tool")], "# Profile")

    assert attempts == 2
    assert result[0].relevance == 8


def _item(*, title: str) -> Item:
    return Item(
        id=1,
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        title=title,
        source="Example",
        snippet=None,
        published_at=None,
        score_hint=0,
        first_seen_at="2026-06-10T00:00:00+00:00",
        cluster_id="cluster",
        cluster_representative=True,
        llm_score=None,
        llm_category=None,
        llm_reason=None,
        status=ItemStatus.NEW,
        article_text=None,
        created_at="2026-06-10T00:00:00+00:00",
        updated_at="2026-06-10T00:00:00+00:00",
    )
