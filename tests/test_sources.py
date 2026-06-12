from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
from newsbeat_digest.models import RawItem
from newsbeat_digest.sources import fetch_all, load_sources
from newsbeat_digest.sources.base import HttpClient, Source
from newsbeat_digest.sources.hn import HackerNewsSource
from newsbeat_digest.sources.reddit import RedditSource
from newsbeat_digest.sources.rss import RssSource


def _client(handler: httpx.MockTransport) -> HttpClient:
    return HttpClient(httpx.Client(transport=handler))


def test_http_client_retries_once() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    client = _client(httpx.MockTransport(handler))

    assert client.get_json("https://example.com") == {"ok": True}
    assert attempts == 2


def test_hacker_news_prefers_original_story_url() -> None:
    now = datetime.now(UTC).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "objectID": "123",
                        "title": "Anthropic releases a new Claude model",
                        "url": "https://example.com/release?utm_source=hn",
                        "created_at": now,
                        "points": 15,
                        "story_text": "<p>Release details</p>",
                    }
                ]
            },
            request=request,
        )

    source = HackerNewsSource(
        _client(httpx.MockTransport(handler)),
        keywords=("anthropic",),
    )

    items = source.fetch()

    assert len(items) == 1
    assert items[0].url == "https://example.com/release?utm_source=hn"
    assert items[0].score_hint == 15
    assert items[0].snippet == "Release details"


def test_hacker_news_rejects_search_matches_without_keyword_in_title() -> None:
    now = datetime.now(UTC).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "objectID": "456",
                        "title": "Britain became as poor as Mississippi",
                        "url": "https://example.com/economy",
                        "created_at": now,
                        "points": 500,
                    }
                ]
            },
            request=request,
        )

    source = HackerNewsSource(
        _client(httpx.MockTransport(handler)),
        keywords=("rag",),
    )

    assert source.fetch() == []


def test_rss_source_parses_recent_entries() -> None:
    rss = b"""<?xml version="1.0"?>
    <rss version="2.0"><channel><title>Example</title>
      <item>
        <title>New AI tool</title>
        <link>https://example.com/tool</link>
        <description><![CDATA[<p>Useful details.</p>]]></description>
      </item>
    </channel></rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=rss, request=request)

    source = RssSource(
        "Example feed",
        "https://example.com/feed.xml",
        _client(httpx.MockTransport(handler)),
    )

    assert source.fetch() == [
        RawItem(
            title="New AI tool",
            url="https://example.com/tool",
            published_at=None,
            source="Example feed",
            snippet="Useful details.",
        )
    ]


def test_reddit_applies_score_and_age_thresholds() -> None:
    now = datetime.now(UTC).timestamp()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "children": [
                        {
                            "data": {
                                "title": "A practical local model",
                                "url": "https://example.com/model",
                                "score": 150,
                                "created_utc": now,
                                "selftext": "Benchmarks and notes",
                            }
                        },
                        {
                            "data": {
                                "title": "Low score",
                                "url": "https://example.com/low",
                                "score": 20,
                                "created_utc": now,
                            }
                        },
                    ]
                }
            },
            request=request,
        )

    source = RedditSource(
        "LocalLLaMA",
        _client(httpx.MockTransport(handler)),
        min_score=100,
    )

    items = source.fetch()

    assert len(items) == 1
    assert items[0].score_hint == 150


def test_failed_source_does_not_block_other_sources() -> None:
    class BrokenSource(Source):
        name = "broken"

        def fetch(self) -> list[RawItem]:
            raise RuntimeError("unavailable")

    class WorkingSource(Source):
        name = "working"

        def fetch(self) -> list[RawItem]:
            return [
                RawItem(
                    title="Story",
                    url="https://example.com/story",
                    published_at=None,
                    source=self.name,
                )
            ]

    result = fetch_all([BrokenSource(), WorkingSource()])

    assert len(result.items) == 1
    assert result.failed_sources == ("broken",)


def test_source_configuration_enables_validated_feeds() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sources = load_sources(
        project_root / "sources.yaml",
        _client(
            httpx.MockTransport(
                lambda request: httpx.Response(200, request=request)
            )
        ),
        lookback_hours=12,
    )

    assert {
        "Google Research",
        "Microsoft Research",
        "NVIDIA Developer Blog",
        "AWS Machine Learning",
        "MIT Technology Review AI",
        "IEEE Spectrum AI",
    } <= {source.name for source in sources}
