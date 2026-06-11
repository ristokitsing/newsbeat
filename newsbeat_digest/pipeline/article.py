"""Fetch and extract readable article text for selected stories."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from bs4 import BeautifulSoup

from newsbeat_digest.models import Item
from newsbeat_digest.sources.base import HttpClient


MAX_ARTICLE_CHARACTERS = 12_000
MIN_EXTRACTED_CHARACTERS = 200


@dataclass(frozen=True, slots=True)
class ArticleText:
    text: str
    extracted: bool


def fetch_article_text(item: Item, client: HttpClient) -> ArticleText:
    logger = logging.getLogger(__name__)
    try:
        response = client.get(item.url)
        extracted = extract_article_text(response.text)
        if len(extracted) >= MIN_EXTRACTED_CHARACTERS:
            return ArticleText(
                text=extracted[:MAX_ARTICLE_CHARACTERS],
                extracted=True,
            )
        logger.warning(
            "Article extraction produced too little text: item_id=%d url=%s",
            item.id,
            item.url,
        )
    except Exception as exc:
        logger.warning(
            "Article extraction failed: item_id=%d url=%s error=%s",
            item.id,
            item.url,
            exc,
        )
    return ArticleText(text=_fallback_text(item), extracted=False)


def extract_article_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "nav",
            "footer",
            "header",
            "aside",
            "form",
        ]
    ):
        element.decompose()

    container = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = [
        paragraph.get_text(" ", strip=True)
        for paragraph in container.find_all(["p", "h1", "h2", "li"])
    ]
    useful = [text for text in paragraphs if len(text) >= 30]
    return "\n\n".join(useful)


def _fallback_text(item: Item) -> str:
    parts = [f"Title: {item.title}"]
    if item.snippet:
        parts.append(f"Source snippet: {item.snippet}")
    parts.append(
        "Full article text was unavailable. Treat all conclusions cautiously."
    )
    return "\n\n".join(parts)
