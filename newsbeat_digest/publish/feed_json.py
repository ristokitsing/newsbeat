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
    payload: dict[str, object] = {
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
        "caution": brief.caution,
    }
    # Legacy briefs inside the 7-day window keep their pre-generated drafts;
    # summary-only briefs omit these keys (the app generates them on demand).
    if brief.linkedin_hook is not None and brief.linkedin_points is not None:
        payload["linkedin_angle"] = {
            "hook": brief.linkedin_hook,
            "points": list(brief.linkedin_points),
        }
    if brief.instagram_slides is not None and brief.instagram_cta is not None:
        payload["instagram_carousel"] = {
            "slides": list(brief.instagram_slides),
            "cta": brief.instagram_cta,
        }
    return payload
