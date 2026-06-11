"""Common source interface and resilient HTTP client."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

import httpx

from newsbeat_digest.models import RawItem


USER_AGENT = "newsbeat-digest/0.2 (+personal AI news digest)"
HTTP_TIMEOUT_SECONDS = 15.0


class HttpClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        self._logger = logging.getLogger(__name__)

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = self._client.get(url, params=params)
                response.raise_for_status()
                return response
            except (httpx.HTTPError, OSError) as exc:
                last_error = exc
                self._logger.warning(
                    "HTTP request failed: url=%s attempt=%d error=%s",
                    url,
                    attempt + 1,
                    exc,
                )
        assert last_error is not None
        raise last_error

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> Any:
        return self.get(url, params=params).json()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class Source(ABC):
    name: str

    @abstractmethod
    def fetch(self) -> list[RawItem]:
        """Return recent source items or raise a source-specific error."""
