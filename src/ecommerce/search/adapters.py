"""Tavily and compatible HTTP-JSON search adapters.

The adapters make requests only when ``search`` is explicitly called. API
credentials may be passed directly to the constructor or loaded from the
named environment variable; this module never loads ``.env`` files. Callers
must use an authorized endpoint, honor robots/rate-limit guidance, avoid
sending personal or confidential data, and comply with the provider's terms
of service and retention rules.
"""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.parse import urlsplit

import httpx

from .errors import (
    SearchConfigurationError,
    SearchEmptyResultError,
    SearchHTTPError,
    SearchResponseError,
    SearchTimeoutError,
)
from .models import SearchProvider, SearchResponse, SearchResult, utc_now


_NUMBER_PATTERN = r"(?:[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{1,2})?|[0-9]+(?:[.,][0-9]{1,2})?)"
_PRICE_PATTERN = re.compile(
    rf"(?:¥|￥|RMB\s*|人民币\s*)\s*({_NUMBER_PATTERN})"
    rf"|({_NUMBER_PATTERN})\s*(?:元|yuan|CNY)",
    re.IGNORECASE,
)
_PLAIN_PRICE_PATTERN = re.compile(rf"^\s*({_NUMBER_PATTERN})\s*$")
_PRICE_CONTEXT_PATTERN = re.compile(
    r"(?:售价|价格|价位|到手价|活动价|报价|零售价|单价|现价|券后价|券后)\s*(?:约|为|是|在|:|：)?\s*"
    rf"(?:¥|￥|RMB\s*|人民币\s*)?({_NUMBER_PATTERN})\s*(?:元|yuan|CNY)?",
    re.IGNORECASE,
)
_PRICE_NOISE_TERMS = (
    "市场规模", "调研报告", "研究报告", "报告价格", "页数", "章节", "美元", "亿元", "万件",
    "原价", "满减", "运费", "成本",
)
_PRICE_UNIT_PATTERN = re.compile(
    r"(?:售价|价格|价位|到手价|活动价|报价|零售价|单价|现价|券后价|券后)"
    r"\s*(?:约|为|是|在|:|：)?\s*(?:¥|￥|RMB\s*|人民币\s*)?"
    r"([0-9]+(?:[.,][0-9]+)?)\s*(万|千)\s*(?:元|yuan|CNY)?",
    re.IGNORECASE,
)
_EMBEDDED_DATE_PATTERN = re.compile(
    r"(?:发布时间|发布日期|更新时间|更新于|发布于|发表于|修订日期|published|updated)"
    r"\s*(?:为|是|于|:|：)?\s*"
    r"(\d{4}(?:[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?|年\d{1,2}月\d{1,2}日))",
    re.IGNORECASE,
)


def _parse_datetime(value: Any) -> datetime | None:
    """Parse common provider date formats without making freshness claims."""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _number_to_float(raw_number: str | None) -> float | None:
    if not raw_number:
        return None
    if "," in raw_number and "." in raw_number:
        normalized_number = raw_number.replace(",", "")
    elif re.fullmatch(r"[0-9]{1,3}(?:,[0-9]{3})+", raw_number):
        normalized_number = raw_number.replace(",", "")
    else:
        normalized_number = raw_number.replace(",", ".")
    try:
        parsed = float(normalized_number)
    except ValueError:
        return None
    return round(parsed, 2) if parsed >= 0 else None


def _parse_price(value: Any, text: str, title: str = "") -> float | None:
    """Extract an explicit price when the provider exposes one."""

    if isinstance(value, dict):
        value = value.get("amount") if value.get("amount") is not None else value.get("value")
    if isinstance(value, (int, float)) and value >= 0:
        return round(float(value), 2)
    value_text = value if isinstance(value, str) else ""
    if value_text:
        match = _PRICE_PATTERN.fullmatch(value_text.strip()) or _PLAIN_PRICE_PATTERN.fullmatch(value_text.strip())
        if match:
            return _number_to_float(match.group(1) or (match.group(2) if len(match.groups()) > 1 else None))

    combined_text = unescape(
        re.sub(r"<[^>]+>", " ", " ".join(part for part in (title, text) if part))
    )
    unit_match = _PRICE_UNIT_PATTERN.search(combined_text)
    if unit_match:
        base = _number_to_float(unit_match.group(1))
        if base is not None:
            return round(base * (10000 if unit_match.group(2).lower() == "万" else 1000), 2)
    contextual = _PRICE_CONTEXT_PATTERN.search(combined_text)
    if contextual:
        context = combined_text[max(0, contextual.start() - 32) : contextual.end() + 18]
        suffix = combined_text[contextual.end() : contextual.end() + 4]
        preferred = any(term in context for term in ("售价", "到手价", "活动价", "现价", "券后"))
        if (
            (not any(term in context for term in _PRICE_NOISE_TERMS) or preferred)
            and not any(term in context for term in ("价格范围", "价格由", "价格从", "区间"))
            and "起" not in suffix
        ):
            return _number_to_float(contextual.group(1))

    for match in _PRICE_PATTERN.finditer(combined_text):
        context = combined_text[max(0, match.start() - 32) : match.end() + 18]
        suffix = combined_text[match.end() : match.end() + 4]
        preferred = any(term in context for term in ("售价", "到手价", "活动价", "现价", "券后"))
        if any(term in context for term in _PRICE_NOISE_TERMS) and not preferred:
            continue
        if any(term in context for term in ("价格由", "价格从", "价格范围", "区间")):
            continue
        if "起" in suffix or "满" in context[-8:] or "减" in context[-8:]:
            continue
        raw_number = match.group(1) or (match.group(2) if len(match.groups()) > 1 else None)
        parsed = _number_to_float(raw_number)
        if parsed is not None:
            return parsed
    return None


def _parse_embedded_datetime(text: str) -> datetime | None:
    """Recover a full labeled date when providers omit structured metadata."""

    match = _EMBEDDED_DATE_PATTERN.search(text)
    if not match:
        return None
    raw_date = match.group(1).replace("年", "-").replace("月", "-").replace("日", "")
    raw_date = raw_date.replace("/", "-").replace(".", "-")
    parts = [part for part in raw_date.split("-") if part]
    if len(parts) != 3:
        return None
    try:
        year, month, day = (int(part) for part in parts)
        return datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None


@dataclass(slots=True)
class HttpJsonSearchProvider(SearchProvider):
    """POST a Tavily-shaped JSON request and normalize its result list.

    ``endpoint`` may point to a compatible service with the same JSON shape.
    Tests can inject an ``httpx.MockTransport`` through ``transport`` without
    making a real request. No dependency beyond the project's existing
    ``httpx`` package is required.
    """

    endpoint: str = "https://api.tavily.com/search"
    api_key: str | None = None
    api_key_env: str = "TAVILY_API_KEY"
    timeout: float = 10.0
    source: str = "tavily"
    parallel_safe: bool = True
    transport: httpx.BaseTransport | None = None
    request_count: int = 0
    attempt_count: int = 0
    max_retries: int = 0
    retry_backoff: float = 0.0
    auth_header: str = "Authorization"
    auth_prefix: str = "Bearer"
    require_api_key: bool = True
    allow_insecure_endpoint: bool = False
    last_request_metadata: dict[str, int | float | str | None] | None = None
    _counter_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        return list(self.search_with_metadata(query, max_results=max_results).results)

    def search_with_metadata(
        self, query: str, *, max_results: int = 5
    ) -> SearchResponse:
        """Search the configured endpoint with bounded, conservative retries.

        ``max_retries`` is the number of additional attempts after the first
        request and defaults to ``0`` for backwards-compatible behavior. Only
        timeouts, connection errors, HTTP 429, and HTTP 5xx responses are
        retried. Other 4xx responses are returned immediately because they
        usually indicate a request or authorization problem. Retries are
        immediate; callers should keep the value low and follow the provider's
        rate-limit guidance and ``Retry-After`` policy. Access must remain
        authorized and comply with the endpoint's terms of service.
        """
        if not query.strip():
            raise SearchConfigurationError("Search query must not be empty")
        if not 1 <= max_results <= 100:
            raise SearchConfigurationError("max_results must be between 1 and 100")
        if self.max_retries < 0:
            raise SearchConfigurationError("max_retries must be non-negative")
        if self.retry_backoff < 0:
            raise SearchConfigurationError("retry_backoff must be non-negative")
        endpoint_parts = urlsplit(self.endpoint)
        if endpoint_parts.scheme.lower() != "https" and not self.allow_insecure_endpoint:
            raise SearchConfigurationError(
                "Search endpoint must use HTTPS when sending a bearer API key"
            )
        key = self.api_key or os.getenv(self.api_key_env)
        if self.require_api_key and not key:
            raise SearchConfigurationError(
                f"Missing search API key; pass api_key or set {self.api_key_env}"
            )

        payload = {"query": query.strip(), "max_results": max_results}
        headers = {"Accept": "application/json"}
        if key:
            auth_value = f"{self.auth_prefix} {key}".strip()
            headers[self.auth_header] = auth_value
        with self._counter_lock:
            self.request_count += 1
        started_at = time.perf_counter()
        attempts = 0
        status_code: int | None = None
        response: httpx.Response | None = None
        last_exception: httpx.HTTPError | None = None

        while attempts <= self.max_retries:
            attempts += 1
            with self._counter_lock:
                self.attempt_count += 1
            try:
                with httpx.Client(transport=self.transport, timeout=self.timeout) as client:
                    response = client.post(
                        self.endpoint,
                        headers=headers,
                        json=payload,
                    )
                status_code = response.status_code
                last_exception = None
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exception = exc
                status_code = None
                if attempts > self.max_retries:
                    metadata = self._set_request_metadata(
                        started_at, attempts, status_code
                    )
                    if isinstance(exc, httpx.TimeoutException):
                        metadata["error_type"] = type(exc).__name__
                        self.last_request_metadata = metadata
                        raise SearchTimeoutError(
                            "Search request timed out", details=metadata
                        ) from exc
                    metadata["error_type"] = type(exc).__name__
                    self.last_request_metadata = metadata
                    raise SearchHTTPError(
                        0,
                        details={"reason": type(exc).__name__, **metadata},
                    ) from exc
                if self.retry_backoff:
                    time.sleep(self.retry_backoff * (2 ** (attempts - 1)))
                continue
            except httpx.HTTPError as exc:
                metadata = self._set_request_metadata(started_at, attempts, status_code)
                metadata["error_type"] = type(exc).__name__
                self.last_request_metadata = metadata
                raise SearchHTTPError(
                    0,
                    details={"reason": type(exc).__name__, **metadata},
                ) from exc

            if response.status_code == 429 or response.status_code >= 500:
                if attempts <= self.max_retries:
                    if self.retry_backoff:
                        time.sleep(self.retry_backoff * (2 ** (attempts - 1)))
                    continue
            break

        metadata = self._set_request_metadata(started_at, attempts, status_code)
        if last_exception is not None:
            raise SearchHTTPError(
                0,
                details={"reason": type(last_exception).__name__, **metadata},
            ) from last_exception
        assert response is not None
        if response.is_error:
            raise SearchHTTPError(response.status_code, details=metadata)
        try:
            body = response.json()
        except ValueError as exc:
            raise SearchResponseError(
                "Search response was not valid JSON", details=metadata
            ) from exc
        try:
            results = self._parse_results(body)
        except SearchResponseError as exc:
            raise SearchResponseError(exc.message, details=metadata) from exc
        if not results:
            raise SearchEmptyResultError(
                "Search provider returned no usable results", details=metadata
            )
        self.last_request_metadata = {
            **metadata,
            "result_count": len(results),
            "returned_count": min(len(results), max_results),
        }
        return SearchResponse(
            results=tuple(results[:max_results]),
            metadata=dict(self.last_request_metadata),
        )

    def _set_request_metadata(
        self, started_at: float, attempts: int, status_code: int | None
    ) -> dict[str, int | float | str | None]:
        """Store diagnostics that are safe to expose to callers.

        Deliberately excludes request headers, payloads, URLs with credentials,
        response bodies, and all API-key material. The returned dictionary is
        copied into provider errors so diagnostics remain safe by construction.
        """

        metadata: dict[str, int | float | None] = {
            "latency_ms": round((time.perf_counter() - started_at) * 1000, 3),
            "attempts": attempts,
            "status_code": status_code,
        }
        self.last_request_metadata = metadata
        return metadata

    def _parse_results(self, body: Any) -> list[SearchResult]:
        if not isinstance(body, dict) or not isinstance(body.get("results"), list):
            raise SearchResponseError("Search response must contain a results array")

        normalized_by_url: dict[str, SearchResult] = {}
        retrieved_at = utc_now()
        for index, item in enumerate(body["results"]):
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            url = item.get("url")
            if not isinstance(title, str) or not title.strip():
                continue
            if not isinstance(url, str) or not url.strip():
                continue
            text = item.get("content", item.get("snippet", ""))
            snippet = text.strip() if isinstance(text, str) else ""
            raw_score = item.get("score", 0.0)
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                score = 0.0
            result = SearchResult(
                title=title.strip(),
                url=url.strip(),
                snippet=snippet or title.strip(),
                source=str(item.get("source") or self.source),
                score=min(1.0, max(0.0, score)),
                retrieved_at=retrieved_at,
                published_at=_parse_datetime(
                    item.get("published_date")
                    or item.get("published_at")
                    or item.get("date")
                ) or _parse_embedded_datetime(f"{title}\n{snippet}"),
                price=_parse_price(
                    item["price"] if "price" in item else item.get("price_value"),
                    snippet or title,
                    title,
                ),
            )
            canonical_url = result.canonical_url
            previous = normalized_by_url.get(canonical_url)
            if previous is None or result.score > previous.score:
                normalized_by_url[canonical_url] = result
            if index >= 100:
                break
        return list(normalized_by_url.values())


TavilySearchProvider = HttpJsonSearchProvider
