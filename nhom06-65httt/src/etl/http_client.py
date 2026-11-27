"""Shared, source-agnostic HTTP GET client for ETL collectors."""

import logging
import math
import socket
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Iterator, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .config import Settings


_RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}
_RETRY_AFTER_STATUSES = {429, 503}


@dataclass(frozen=True)
class HttpResponse:
    """Buffered HTTP response returned by the shared client."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes
    url: str


class PaginationError(ValueError):
    """Raised for invalid or unsafe pagination links."""


class PaginationLimitError(PaginationError):
    """Raised when a source continues paging past the configured limit."""


class HttpClient:
    """HTTP GET transport with bounded retries, safe logs, and generic paging."""

    def __init__(
        self,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
        max_retry_delay_seconds: float = 60.0,
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and greater than zero")
        if type(max_retries) is not int or not 0 <= max_retries <= 10:
            raise ValueError("max_retries must be an integer between 0 and 10")
        if not math.isfinite(backoff_seconds) or backoff_seconds < 0:
            raise ValueError("backoff_seconds must be finite and nonnegative")
        if (
            not math.isfinite(max_retry_delay_seconds)
            or max_retry_delay_seconds <= 0
        ):
            raise ValueError(
                "max_retry_delay_seconds must be finite and greater than zero"
            )
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.max_retry_delay_seconds = max_retry_delay_seconds
        self._logger = logging.getLogger("etl.http_client")

    @classmethod
    def from_settings(cls, settings: Settings) -> "HttpClient":
        """Create a client using HTTP settings loaded from the environment."""
        return cls(
            timeout=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
            backoff_seconds=settings.http_backoff_seconds,
            max_retry_delay_seconds=settings.http_max_retry_delay_seconds,
        )

    def get(
        self,
        url: str,
        *,
        params: Optional[Mapping[str, object]] = None,
        headers: Optional[Mapping[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> HttpResponse:
        """Perform a GET request and return its complete response body."""
        request_url = _append_query_parameters(url, params)
        host = _validated_host(request_url)
        request_timeout = self.timeout if timeout is None else timeout
        if not math.isfinite(request_timeout) or request_timeout <= 0:
            raise ValueError("timeout must be finite and greater than zero")
        request = Request(
            request_url,
            headers=dict(headers or {}),
            method="GET",
        )

        for attempt in range(self.max_retries + 1):
            started_at = time.perf_counter()
            try:
                with urlopen(request, timeout=request_timeout) as response:
                    body = response.read()
                    status_code = response.status
                    response_headers = dict(response.headers.items())
                    response_url = response.geturl()
                self._log_request(
                    host, status_code, started_at, attempt + 1
                )
                return HttpResponse(
                    status_code=status_code,
                    headers=response_headers,
                    body=body,
                    url=response_url,
                )
            except HTTPError as error:
                self._log_request(host, error.code, started_at, attempt + 1)
                if (
                    error.code not in _RETRYABLE_STATUSES
                    or attempt >= self.max_retries
                ):
                    error.close()
                    raise

                retry_after = self._retry_after(error)
                if retry_after is not None:
                    if retry_after > self.max_retry_delay_seconds:
                        error.close()
                        raise
                    delay = retry_after
                else:
                    delay = self._backoff_delay(attempt)
                error.close()
                time.sleep(delay)
            except (URLError, TimeoutError, socket.timeout, ConnectionError) as error:
                self._log_request(
                    host, "network_error", started_at, attempt + 1
                )
                if isinstance(error, URLError) and isinstance(
                    error.reason, ssl.SSLError
                ):
                    raise
                if attempt >= self.max_retries:
                    raise
                time.sleep(self._backoff_delay(attempt))

        raise RuntimeError("HTTP retry loop exited unexpectedly")

    def iter_pages(
        self,
        url: str,
        next_page_url: Callable[[HttpResponse], Optional[str]],
        *,
        params: Optional[Mapping[str, object]] = None,
        headers: Optional[Mapping[str, str]] = None,
        timeout: Optional[float] = None,
        max_pages: int = 100,
    ) -> Iterator[HttpResponse]:
        """Iterate pages using a caller-supplied, source-specific next-link parser."""
        if type(max_pages) is not int or max_pages < 1:
            raise ValueError("max_pages must be a positive integer")
        initial_url = _append_query_parameters(url, params)
        origin = _origin(initial_url)
        current_url = initial_url
        visited_urls = set()

        for page_number in range(max_pages):
            if current_url in visited_urls:
                raise PaginationError("pagination returned a repeated URL")
            visited_urls.add(current_url)
            response = self.get(
                current_url,
                headers=headers,
                timeout=timeout,
            )
            yield response

            next_url = next_page_url(response)
            if next_url is None:
                return
            if not isinstance(next_url, str) or not next_url:
                raise PaginationError("next page URL must be a non-empty string")
            next_url = urljoin(response.url, next_url)
            if _origin(next_url) != origin:
                raise PaginationError("pagination cannot change request origin")
            if page_number + 1 == max_pages:
                raise PaginationLimitError(
                    f"pagination exceeded the limit of {max_pages} pages"
                )
            current_url = next_url

    def _retry_after(self, error: HTTPError) -> Optional[float]:
        if error.code not in _RETRY_AFTER_STATUSES:
            return None
        value = error.headers.get("Retry-After") if error.headers else None
        if value is None:
            return None
        try:
            delay = float(value)
            if math.isfinite(delay) and delay >= 0:
                return delay
        except ValueError:
            pass
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(
            0.0,
            (retry_at - datetime.now(timezone.utc)).total_seconds(),
        )

    def _backoff_delay(self, attempt: int) -> float:
        return min(
            self.backoff_seconds * (2**attempt),
            self.max_retry_delay_seconds,
        )

    def _log_request(
        self, host: str, status: object, started_at: float, attempt: int
    ) -> None:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        self._logger.info(
            "http_request method=GET host=%s status=%s response_time_ms=%.1f "
            "attempt=%d",
            host,
            status,
            elapsed_ms,
            attempt,
        )


def _append_query_parameters(
    url: str, params: Optional[Mapping[str, object]]
) -> str:
    _validated_host(url)
    if not params:
        return url
    parsed = urlsplit(url)
    query = urlencode(params, doseq=True)
    combined_query = f"{parsed.query}&{query}" if parsed.query else query
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, combined_query, parsed.fragment)
    )


def _validated_host(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("url must be an HTTP(S) URL without embedded credentials")
    return parsed.hostname


def _origin(url: str) -> tuple[str, str, Optional[int]]:
    _validated_host(url)
    parsed = urlsplit(url)
    return parsed.scheme, parsed.hostname or "", parsed.port
