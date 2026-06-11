"""Disabled arXiv source placeholder for a later version."""

from __future__ import annotations

from newsbeat_digest.models import RawItem
from newsbeat_digest.sources.base import Source


class ArxivSource(Source):
    name = "arXiv"

    def fetch(self) -> list[RawItem]:
        return []
