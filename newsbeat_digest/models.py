"""Typed data models shared by the pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypedDict


class ItemStatus(StrEnum):
    NEW = "new"
    SCORED = "scored"
    SELECTED = "selected"
    REJECTED = "rejected"
    BRIEFED = "briefed"
    DELIVERED = "delivered"


@dataclass(frozen=True, slots=True)
class RawItem:
    title: str
    url: str
    published_at: str | None
    source: str
    snippet: str | None = None
    score_hint: float = 0.0


@dataclass(frozen=True, slots=True)
class Item:
    id: int
    url: str
    canonical_url: str
    title: str
    source: str
    snippet: str | None
    published_at: str | None
    score_hint: float
    first_seen_at: str
    cluster_id: str | None
    cluster_representative: bool
    llm_score: float | None
    llm_category: str | None
    llm_reason: str | None
    status: ItemStatus
    article_text: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Brief:
    id: int
    item_id: int
    what_happened: str
    why_it_matters: str
    linkedin_hook: str
    linkedin_points: tuple[str, ...]
    instagram_slides: tuple[str, ...]
    instagram_cta: str
    caution: str
    digest_date: str
    digest_slot: str
    created_at: str


class LinkedInAngle(TypedDict):
    hook: str
    points: list[str]


class InstagramCarousel(TypedDict):
    slides: list[str]
    cta: str


class BriefContent(TypedDict):
    what_happened: str
    why_it_matters: str
    linkedin_angle: LinkedInAngle
    instagram_carousel: InstagramCarousel
    caution: str


@dataclass(frozen=True, slots=True)
class PublishedItem:
    item: Item
    brief: Brief


@dataclass(frozen=True, slots=True)
class ScoreResult:
    item_id: int
    category: str
    relevance: float
    reason: str


@dataclass(frozen=True, slots=True)
class RankedItem:
    item: Item
    rank: float
