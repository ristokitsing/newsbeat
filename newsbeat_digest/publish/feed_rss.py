"""Render a valid RSS 2.0 digest feed."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import format_datetime
from xml.etree import ElementTree

from newsbeat_digest.models import PublishedItem


def render_rss_feed(
    items: list[PublishedItem],
    *,
    generated_at: datetime,
    pages_url: str | None,
) -> str:
    base_url = (pages_url or "https://example.invalid/newsbeat").rstrip("/")
    rss = ElementTree.Element("rss", {"version": "2.0"})
    channel = ElementTree.SubElement(rss, "channel")
    _element(channel, "title", "newsbeat")
    _element(channel, "link", base_url)
    _element(
        channel,
        "description",
        "Curated AI news and reusable social content briefs from newsbeat.",
    )
    _element(channel, "language", "en")
    _element(channel, "lastBuildDate", _rss_date(generated_at))

    for entry in items:
        node = ElementTree.SubElement(channel, "item")
        _element(node, "title", entry.item.title)
        _element(node, "link", entry.item.url)
        guid = _element(node, "guid", entry.item.canonical_url)
        guid.set("isPermaLink", "true")
        _element(
            node,
            "description",
            (
                f"{entry.brief.what_happened}\n\n"
                f"Why it matters: {entry.brief.why_it_matters}\n\n"
                f"Caution: {entry.brief.caution}"
            ),
        )
        published = _parse_datetime(entry.item.published_at)
        if published is None:
            published = _parse_datetime(entry.brief.created_at)
        _element(node, "pubDate", _rss_date(published or generated_at))
        if entry.item.llm_category:
            _element(node, "category", entry.item.llm_category)

    ElementTree.indent(rss, space="  ")
    xml = ElementTree.tostring(
        rss,
        encoding="unicode",
        xml_declaration=True,
    )
    return xml + "\n"


def _element(
    parent: ElementTree.Element,
    name: str,
    text: str,
) -> ElementTree.Element:
    child = ElementTree.SubElement(parent, name)
    child.text = text
    return child


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _rss_date(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return format_datetime(value.astimezone(UTC), usegmt=True)
