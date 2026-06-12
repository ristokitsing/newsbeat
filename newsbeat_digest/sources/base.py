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
# Cap buffered response bodies so a hostile or oversized article URL cannot
# exhaust the 384 MB worker. Applies to every source and to article fetching,
# since both go through this client.
MAX_RESPONSE_BYTES = 5_000_000


class ResponseTooLargeError(Exception):
    """Raised when a response body exceeds MAX_RESPONSE_BYTES."""


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
                return self._get_capped(url, params)
            except ResponseTooLargeError as exc:
                # A hostile or oversized body will not shrink on retry, and
                # re-downloading it wastes bandwidth, so fail fast.
                self._logger.warning("Response too large: url=%s %s", url, exc)
                raise
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

    def _get_capped(
        self,
        url: str,
        params: Mapping[str, str | int] | None,
    ) -> httpx.Response:
        with self._client.stream("GET", url, params=params) as response:
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise ResponseTooLargeError(
                        f"exceeded {MAX_RESPONSE_BYTES} bytes"
                    )
                chunks.append(chunk)
            # iter_bytes() decodes content-encoding, so drop the now-stale
            # encoding/length headers and hand back identity-encoded bytes.
            headers = {
                key: value
                for key, value in response.headers.items()
                if key.lower() not in ("content-encoding", "content-length")
            }
            return httpx.Response(
                status_code=response.status_code,
                headers=headers,
                content=b"".join(chunks),
                request=response.request,
            )

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
