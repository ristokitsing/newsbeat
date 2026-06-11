"""Render a human-readable Markdown digest archive."""

from __future__ import annotations

from datetime import date

from newsbeat_digest.models import PublishedItem


def render_markdown_digest(
    items: list[PublishedItem],
    *,
    digest_date: date,
    digest_slot: str,
) -> str:
    period = "Morning" if digest_slot == "am" else "Afternoon"
    lines = [
        f"# newsbeat: {digest_date.isoformat()} {period}",
        "",
    ]
    if not items:
        lines.extend(
            [
                "No stories met the selection threshold for this digest.",
                "",
            ]
        )
        return "\n".join(lines)

    for entry in items:
        item = entry.item
        brief = entry.brief
        lines.extend(
            [
                f"## {item.title}",
                "",
                f"Source: [{item.source}]({item.url})",
                "",
                "### What happened",
                "",
                brief.what_happened,
                "",
                "### Why it matters",
                "",
                brief.why_it_matters,
                "",
                "### LinkedIn angle",
                "",
                f"**{brief.linkedin_hook}**",
                "",
            ]
        )
        lines.extend(f"- {point}" for point in brief.linkedin_points)
        lines.extend(
            [
                "",
                "### Instagram carousel",
                "",
            ]
        )
        lines.extend(
            f"{index}. {slide}"
            for index, slide in enumerate(brief.instagram_slides, start=1)
        )
        lines.extend(
            [
                "",
                f"CTA: {brief.instagram_cta}",
                "",
                f"**Caution:** {brief.caution}",
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines)
