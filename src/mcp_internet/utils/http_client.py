"""Shared, bounded HTTP access with URL and redirect validation."""
import asyncio
import ipaddress
import json
import logging
import random
import socket
import time
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

logger = logging.getLogger(__name__)
MAX_URL_LENGTH = 4096
MAX_HTML_BYTES = 2_000_000
MAX_JSON_BYTES = 1_000_000
MAX_PDF_BYTES = 15_000_000
MAX_REDIRECTS = 8

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
]
GOOGLEBOT_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)", "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_client: httpx.AsyncClient | None = None


class UnsafeURLError(ValueError):
    """The URL is invalid or targets a non-public address."""


class ResponseLimitError(ValueError):
    """The response exceeded its size/content-type budget."""


def _get_default_headers() -> dict[str, str]:
    return {"User-Agent": random.choice(_USER_AGENTS), "Accept": "text/html,application/xhtml+xml,application/json,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.5"}


class DomainRateLimiter:
    """Rate limit each host independently without sleeping under a global lock."""
    def __init__(self, max_per_second: float = 2.0):
        self._min_interval = 1.0 / max_per_second
        self._last_request: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()

    async def wait(self, url: str) -> None:
        host = (urlsplit(url).hostname or "unknown").lower()
        async with self._lock:
            lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            delay = self._min_interval - (now - self._last_request.get(host, 0.0))
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_request[host] = time.monotonic()


_rate_limiter = DomainRateLimiter()


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=False, headers=_get_default_headers(), http2=True)
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _validate_url(url: str) -> tuple[str, str]:
    if not isinstance(url, str) or len(url) > MAX_URL_LENGTH:
        raise UnsafeURLError("URL is missing or exceeds the 4096 character limit")
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise UnsafeURLError("Only absolute HTTP(S) URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeURLError("Credentials in URLs are not allowed")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise UnsafeURLError("Local hostnames are not allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise UnsafeURLError("Non-public IP destinations are not allowed")
    return url, host


async def _validate_destination(host: str, port: int) -> None:
    try:
        ipaddress.ip_address(host)
        return
    except ValueError:
        pass
    try:
        records = await asyncio.to_thread(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise UnsafeURLError("Hostname could not be resolved") from exc
    addresses = {record[4][0].split("%")[0] for record in records}
    if not addresses or any(not ipaddress.ip_address(value).is_global for value in addresses):
        raise UnsafeURLError("Hostname resolves to a non-public IP address")


async def _request_bytes(url: str, *, headers: dict[str, str] | None, timeout: float,
                         limit: int, accepted_types: tuple[str, ...], retries: int,
                         rate_limit: bool, follow_redirects: bool = True) -> tuple[bytes, str, str]:
    if rate_limit:
        await _rate_limiter.wait(url)
    client = await get_client()
    current = url
    for redirect in range(MAX_REDIRECTS + 1):
        _, host = _validate_url(current)
        parsed = urlsplit(current)
        await _validate_destination(host, parsed.port or (443 if parsed.scheme == "https" else 80))
        request_headers = {**_get_default_headers(), **(headers or {})}
        for attempt in range(max(0, min(retries, 4)) + 1):
            try:
                async with client.stream("GET", current, headers=request_headers,
                                         timeout=httpx.Timeout(timeout, connect=min(timeout, 10)), follow_redirects=False) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        if not follow_redirects:
                            response.raise_for_status()
                        location = response.headers.get("location")
                        if not location or redirect == MAX_REDIRECTS:
                            raise httpx.HTTPStatusError("Invalid or excessive redirects", request=response.request, response=response)
                        current = urljoin(current, location)
                        break
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < retries:
                            await asyncio.sleep(min(2 ** attempt, 4))
                            continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    if not any(content_type == item or content_type.startswith(item + "/") for item in accepted_types):
                        raise ResponseLimitError(f"Unexpected content type: {content_type or 'missing'}")
                    length = response.headers.get("content-length")
                    if length and int(length) > limit:
                        raise ResponseLimitError(f"Response exceeds {limit} byte limit")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > limit:
                            raise ResponseLimitError(f"Response exceeds {limit} byte limit")
                    return bytes(body), content_type, current
            except (UnsafeURLError, ResponseLimitError):
                raise
            except httpx.HTTPStatusError as exc:
                logger.warning("HTTP status %s while fetching host %s", exc.response.status_code, host)
                raise
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.warning("HTTP request failed for host %s (%s)", host, type(exc).__name__)
                if attempt >= retries:
                    raise
                await asyncio.sleep(min(0.5 * (2 ** attempt), 2))
        else:
            continue
        # Redirect branch: revalidate target on next loop.
        continue
    raise UnsafeURLError("Too many redirects")


async def fetch_bytes(url: str, *, limit: int = MAX_PDF_BYTES,
                      accepted_types: tuple[str, ...] = ("application/pdf",), timeout: float = 30,
                      retries: int = 1) -> bytes:
    body, _, _ = await _request_bytes(url, headers=None, timeout=timeout, limit=limit,
                                      accepted_types=accepted_types, retries=retries, rate_limit=True)
    return body


async def fetch_url(url: str, headers: dict[str, str] | None = None, timeout: float = 30.0,
                    follow_redirects: bool = True, retries: int = 2, rate_limit: bool = True,
                    max_bytes: int = MAX_HTML_BYTES) -> str | None:
    try:
        body, content_type, _ = await _request_bytes(url, headers=headers, timeout=timeout, limit=max_bytes,
            accepted_types=("text/html", "application/xhtml+xml", "text/plain", "application/xml", "text/xml", "application/rss+xml"),
            retries=retries, rate_limit=rate_limit, follow_redirects=follow_redirects)
        encoding = "utf-8"
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            return body.decode("utf-8", errors="replace")
    except (UnsafeURLError, ResponseLimitError, httpx.HTTPError, OSError, ValueError) as exc:
        logger.warning("Unable to fetch URL (%s)", type(exc).__name__)
        return None


async def fetch_json(url: str, headers: dict[str, str] | None = None, timeout: float = 30.0,
                     params: dict[str, Any] | None = None, retries: int = 2,
                     rate_limit: bool = True) -> dict[str, Any] | list | None:
    if params:
        from urllib.parse import urlencode
        url += ("&" if "?" in url else "?") + urlencode(params, doseq=True)
    try:
        body, _, _ = await _request_bytes(url, headers={"Accept": "application/json", **(headers or {})},
            timeout=timeout, limit=MAX_JSON_BYTES, accepted_types=("application/json", "application/ld+json"),
            retries=retries, rate_limit=rate_limit)
        parsed = json.loads(body)
        return parsed if isinstance(parsed, (dict, list)) else None
    except (UnsafeURLError, ResponseLimitError, httpx.HTTPError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Unable to fetch JSON (%s)", type(exc).__name__)
        return None


async def fetch_multiple(urls: list[str], max_concurrent: int = 5, timeout: float = 20.0,
                         retries: int = 1) -> dict[str, str | None]:
    semaphore = asyncio.Semaphore(max(1, min(max_concurrent, 10)))
    async def one(url: str) -> tuple[str, str | None]:
        async with semaphore:
            return url, await fetch_url(url, timeout=timeout, retries=retries)
    pairs = await asyncio.gather(*(one(url) for url in urls), return_exceptions=True)
    return {item[0]: item[1] for item in pairs if not isinstance(item, BaseException)}
