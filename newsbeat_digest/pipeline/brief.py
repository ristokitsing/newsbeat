"""Generate and persist structured social-content briefs."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from anthropic import Anthropic

from newsbeat_digest.config import Settings
from newsbeat_digest.db import Database
from newsbeat_digest.models import BriefContent, Item, ItemStatus
from newsbeat_digest.pipeline.article import ArticleText, fetch_article_text
from newsbeat_digest.pipeline.score import supports_temperature
from newsbeat_digest.sources.base import HttpClient


# The pipeline now produces a short factual summary only. LinkedIn and
# Instagram drafts are generated on demand in the app.
BRIEF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "what_happened": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "caution": {"type": "string"},
    },
    "required": [
        "what_happened",
        "why_it_matters",
        "caution",
    ],
}


class BriefGenerator(Protocol):
    def generate(self, item: Item, article: ArticleText) -> BriefContent:
        """Return a validated structured brief."""


class AnthropicBriefGenerator:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        client: Anthropic | None = None,
    ) -> None:
        self._client = client or Anthropic(api_key=api_key)
        self._model = model

    def generate(self, item: Item, article: ArticleText) -> BriefContent:
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                message = self._client.messages.create(
                    model=self._model,
                    max_tokens=700,
                    output_config={
                        "format": {
                            "type": "json_schema",
                            "schema": BRIEF_SCHEMA,
                        }
                    },
                    **(
                        {"temperature": 0}
                        if supports_temperature(self._model)
                        else {}
                    ),
                    system=(
                        "You create factual, concise AI news content briefs. "
                        "Use only the supplied source material. Never invent "
                        "facts, quotes, dates, numbers, or implications. If "
                        "the material is incomplete, say so in caution."
                    ),
                    messages=[
                        {
                            "role": "user",
                            "content": _brief_prompt(item, article),
                        }
                    ],
                )
                text = next(
                    block.text
                    for block in message.content
                    if block.type == "text"
                )
                return validate_brief_content(json.loads(text))
            except (Exception,) as exc:
                last_error = exc
                logging.getLogger(__name__).warning(
                    "Brief response failed validation: item_id=%d "
                    "attempt=%d error=%s",
                    item.id,
                    attempt + 1,
                    exc,
                )
        assert last_error is not None
        raise last_error


def generate_briefs(
    settings: Settings,
    database: Database,
    *,
    generator: BriefGenerator | None = None,
    client: HttpClient | None = None,
    now: datetime | None = None,
) -> tuple[int, int]:
    selected = database.list_items(ItemStatus.SELECTED)[: settings.max_items]
    if not selected:
        return 0, 0

    if generator is None:
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when selected items need briefs"
            )
        if not settings.brief_model:
            raise ValueError("AI_DIGEST_BRIEF_MODEL must not be empty")
        generator = AnthropicBriefGenerator(
            settings.anthropic_api_key,
            settings.brief_model,
        )

    local_now = now or datetime.now(ZoneInfo(settings.timezone))
    digest_slot = "am" if local_now.hour < 12 else "pm"
    own_client = client is None
    http_client = client or HttpClient()
    created = 0
    failed = 0
    logger = logging.getLogger(__name__)
    try:
        for item in selected:
            try:
                article = fetch_article_text(item, http_client)
                database.update_article_text(item.id, article.text)
                content = generator.generate(item, article)
                brief_id = database.insert_brief(
                    item.id,
                    content,
                    digest_date=local_now.date(),
                    digest_slot=digest_slot,
                )
                if brief_id is not None:
                    created += 1
            except Exception as exc:
                failed += 1
                logger.error(
                    "Brief generation failed: item_id=%d error=%s",
                    item.id,
                    exc,
                )
    finally:
        if own_client:
            http_client.close()
    return created, failed


def validate_brief_content(value: object) -> BriefContent:
    if not isinstance(value, Mapping):
        raise ValueError("brief must be a JSON object")
    required = {
        "what_happened",
        "why_it_matters",
        "caution",
    }
    if set(value) != required:
        raise ValueError("brief has missing or unexpected fields")

    result: BriefContent = {
        "what_happened": _text(value["what_happened"], "what_happened"),
        "why_it_matters": _text(value["why_it_matters"], "why_it_matters"),
        "caution": _text(value["caution"], "caution"),
    }
    return result


def _brief_prompt(item: Item, article: ArticleText) -> str:
    source_quality = (
        "Full article text was extracted."
        if article.extracted
        else (
            "Only a title or source snippet was available. The caution field "
            "must explicitly state that the source material was limited."
        )
    )
    return f"""Create one brief for this AI news story.

Title: {item.title}
Publisher/source: {item.source}
URL: {item.url}
Category: {item.llm_category or "unclassified"}
Source quality: {source_quality}

Source material:
<source>
{article.text}
</source>

Requirements:
- what_happened: two factual sentences.
- why_it_matters: two or three useful sentences.
- caution: one specific uncertainty, limitation, or source-quality warning.
- Do not repeat unsupported claims from the title as established fact.
"""


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()
