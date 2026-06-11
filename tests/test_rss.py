from __future__ import annotations

from datetime import UTC, datetime
from xml.etree import ElementTree

from newsbeat_digest.publish.feed_rss import render_rss_feed


def test_rss_xml_is_valid_rss_2() -> None:
    xml = render_rss_feed(
        [],
        generated_at=datetime(2026, 6, 10, 12, tzinfo=UTC),
        pages_url="https://example.com/newsbeat/",
    )

    root = ElementTree.fromstring(xml)
    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"
    assert root.findtext("./channel/title") == "newsbeat"
    assert root.findtext("./channel/link") == "https://example.com/newsbeat"
    assert root.find("./channel/lastBuildDate") is not None
