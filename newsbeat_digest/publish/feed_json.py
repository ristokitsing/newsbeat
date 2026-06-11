"""Render the app's source-of-truth JSON feed."""

from __future__ import annotations

import json
from datetime import datetime

from newsbeat_digest.models import PublishedItem


def render_json_feed(
    items: list[PublishedItem],
    *,
    generated_at: datetime,
    timezone: str,
) -> str:
    payload = {
        "version": 1,
        "generated_at": generated_at.isoformat(),
        "timezone": timezone,
        "items": [_feed_item(entry) for entry in items],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _feed_item(entry: PublishedItem) -> dict[str, object]:
    item = entry.item
    brief = entry.brief
    return {
        "id": item.id,
        "title": item.title,
        "url": item.url,
        "canonical_url": item.canonical_url,
        "source": item.source,
        "published_at": item.published_at,
        "digest_date": brief.digest_date,
        "digest_slot": brief.digest_slot,
        "category": item.llm_category,
        "score": item.llm_score,
        "what_happened": brief.what_happened,
        "why_it_matters": brief.why_it_matters,
        "linkedin_angle": {
            "hook": brief.linkedin_hook,
            "points": list(brief.linkedin_points),
        },
        "instagram_carousel": {
            "slides": list(brief.instagram_slides),
            "cta": brief.instagram_cta,
        },
        "caution": brief.caution,
    }
