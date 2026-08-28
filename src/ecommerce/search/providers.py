"""Native search providers and the e-commerce provider factory."""

from __future__ import annotations

import os
import threading
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from .adapters import (
    HttpJsonSearchProvider,
    _parse_datetime,
    _parse_embedded_datetime,
    _parse_price,
)
from .errors import (
    SearchConfigurationError,
    SearchEmptyResultError,
    SearchHTTPError,
    SearchResponseError,
    SearchTimeoutError,
)
from .models import SearchProvider, SearchResponse, SearchResult, utc_now


SUPPORTED_SEARCH_PROVIDERS = ("tavily", "searxng", "brave", "serper", "custom_http_json")
_PROVIDER_ALIASES = {
    "searx": "searxng",
    "brave_search": "brave",
    "custom": "custom_http_json",
    "http_json": "custom_http_json",
}


def _normalize_provider_name(value: str | None) -> str:
    name = (value or os.getenv("SEARCH_API") or "tavily").strip().lower()
    return _PROVIDER_ALIASES.get(name, name)


class NativeSearchProvider(SearchProvider):
    """Small HTTP base for providers whose request/response shapes differ."""

    source = "search"
    method = "GET"
    require_api_key = True
    allow_insecure_endpoint = False

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str | None = None,
        api_key_env: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 0,
        retry_backoff: float = 0.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.transport = transport
        self.request_count = 0
        self.attempt_count = 0
        self.last_request_metadata: dict[str, int | float | str | None] | None = None
        self._counter_lock = threading.Lock()

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        return list(self.search_with_metadata(query, max_results=max_results).results)

    def search_with_metadata(self, query: str, *, max_results: int = 5) -> SearchResponse:
        if not query.strip():
            raise SearchConfigurationError("Search query must not be empty")
        if not 1 <= max_results <= 100:
            raise SearchConfigurationError("max_results must be between 1 and 100")
        if self.max_retries < 0 or self.retry_backoff < 0:
            raise SearchConfigurationError("Search retry settings must be non-negative")
        parts = urlsplit(self.endpoint)
        if parts.scheme.lower() != "https" and not self.allow_insecure_endpoint:
            raise SearchConfigurationError("Search endpoint must use HTTPS")
        key = self.api_key or (os.getenv(self.api_key_env) if self.api_key_env else None)
        if self.require_api_key and not key:
            env_hint = self.api_key_env or "the configured provider key"
            raise SearchConfigurationError(f"Missing search API key; set {env_hint}")

        with self._counter_lock:
            self.request_count += 1
        started_at = time.perf_counter()
        attempts = 0
        status_code: int | None = None
        response: httpx.Response | None = None
        last_exception: httpx.HTTPError | None = None
        headers = {"Accept": "application/json"}
        headers.update(self._auth_headers(key))

        while attempts <= self.max_retries:
            attempts += 1
            with self._counter_lock:
                self.attempt_count += 1
            try:
                with httpx.Client(transport=self.transport, timeout=self.timeout) as client:
                    response = self._send(client, query.strip(), max_results, headers)
                status_code = response.status_code
                last_exception = None
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exception = exc
                status_code = None
                if attempts > self.max_retries:
                    metadata = self._set_metadata(started_at, attempts, status_code)
                    metadata["error_type"] = type(exc).__name__
                    self.last_request_metadata = metadata
                    if isinstance(exc, httpx.TimeoutException):
                        raise SearchTimeoutError("Search request timed out", details=metadata) from exc
                    raise SearchHTTPError(0, details={"reason": type(exc).__name__, **metadata}) from exc
                self._backoff(attempts)
                continue
            except httpx.HTTPError as exc:
                metadata = self._set_metadata(started_at, attempts, status_code)
                metadata["error_type"] = type(exc).__name__
                self.last_request_metadata = metadata
                raise SearchHTTPError(0, details={"reason": type(exc).__name__, **metadata}) from exc

            if response.status_code == 429 or response.status_code >= 500:
                if attempts <= self.max_retries:
                    self._backoff(attempts)
                    continue
            break

        metadata = self._set_metadata(started_at, attempts, status_code)
        if last_exception is not None:
            raise SearchHTTPError(0, details={"reason": type(last_exception).__name__, **metadata}) from last_exception
        assert response is not None
        if response.is_error:
            raise SearchHTTPError(response.status_code, details=metadata)
        try:
            body = response.json()
        except ValueError as exc:
            raise SearchResponseError("Search response was not valid JSON", details=metadata) from exc
        results = self._parse_results(body)
        if not results:
            raise SearchEmptyResultError("Search provider returned no usable results", details=metadata)
        self.last_request_metadata = {
            **metadata,
            "result_count": len(results),
            "returned_count": min(len(results), max_results),
        }
        return SearchResponse(
            results=tuple(results[:max_results]),
            metadata=dict(self.last_request_metadata),
        )

    def _send(
        self,
        client: httpx.Client,
        query: str,
        max_results: int,
        headers: dict[str, str],
    ) -> httpx.Response:
        if self.method == "POST":
            return client.post(
                self.endpoint,
                headers=headers,
                json=self._request_body(query, max_results),
            )
        return client.get(
            self.endpoint,
            headers=headers,
            params=self._request_params(query, max_results),
        )

    def _request_body(self, query: str, max_results: int) -> dict[str, Any]:
        return {"query": query, "max_results": max_results}

    def _request_params(self, query: str, max_results: int) -> dict[str, Any]:
        return {"q": query, "format": "json", "count": max_results}

    def _auth_headers(self, key: str | None) -> dict[str, str]:
        return {"Authorization": f"Bearer {key}"} if key else {}

    def _parse_results(self, body: Any) -> list[SearchResult]:
        raise NotImplementedError

    def _set_metadata(
        self, started_at: float, attempts: int, status_code: int | None
    ) -> dict[str, int | float | str | None]:
        metadata: dict[str, int | float | str | None] = {
            "latency_ms": round((time.perf_counter() - started_at) * 1000, 3),
            "attempts": attempts,
            "status_code": status_code,
        }
        self.last_request_metadata = metadata
        return metadata

    def _backoff(self, attempts: int) -> None:
        if self.retry_backoff:
            time.sleep(self.retry_backoff * (2 ** (attempts - 1)))

    def _result(
        self,
        *,
        title: str,
        url: str,
        snippet: str,
        score: float,
        price: Any = None,
        published_at: Any = None,
    ) -> SearchResult | None:
        if not title.strip() or not url.strip():
            return None
        clean_snippet = snippet.strip() or title.strip()
        try:
            normalized_score = min(1.0, max(0.0, float(score)))
        except (TypeError, ValueError):
            normalized_score = 0.0
        return SearchResult(
            title=title.strip(),
            url=url.strip(),
            snippet=clean_snippet,
            source=self.source,
            score=normalized_score,
            retrieved_at=utc_now(),
            published_at=_parse_datetime(published_at)
            or _parse_embedded_datetime(f"{title}\n{clean_snippet}"),
            price=_parse_price(price, clean_snippet, title),
        )

    def _deduplicate(self, results: list[SearchResult]) -> list[SearchResult]:
        normalized: dict[str, SearchResult] = {}
        for result in results:
            previous = normalized.get(result.canonical_url)
            if previous is None or result.score > previous.score:
                normalized[result.canonical_url] = result
        return list(normalized.values())


class SearXNGSearchProvider(NativeSearchProvider):
    source = "searxng"
    require_api_key = False
    allow_insecure_endpoint = True

    def __init__(self, *, endpoint: str = "http://localhost:8080/search", **kwargs: Any) -> None:
        endpoint = endpoint.rstrip("/")
        if not endpoint.endswith("/search"):
            endpoint = f"{endpoint}/search"
        super().__init__(endpoint=endpoint, **kwargs)

    def _request_params(self, query: str, max_results: int) -> dict[str, Any]:
        return {"q": query, "format": "json", "count": max_results}

    def _auth_headers(self, key: str | None) -> dict[str, str]:
        return {"X-API-Key": key} if key else {}

    def _parse_results(self, body: Any) -> list[SearchResult]:
        if not isinstance(body, dict) or not isinstance(body.get("results"), list):
            raise SearchResponseError("SearXNG response must contain a results array")
        results: list[SearchResult] = []
        for index, item in enumerate(body["results"][:100]):
            if not isinstance(item, dict):
                continue
            result = self._result(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=str(item.get("content") or item.get("snippet") or ""),
                score=item.get("score", max(0.1, 1.0 - index * 0.05)),
                price=item.get("price"),
                published_at=item.get("publishedDate") or item.get("published_date"),
            )
            if result:
                results.append(result)
        return self._deduplicate(results)


class BraveSearchProvider(NativeSearchProvider):
    source = "brave"

    def __init__(
        self,
        *,
        endpoint: str = "https://api.search.brave.com/res/v1/web/search",
        api_key_env: str = "BRAVE_SEARCH_API_KEY",
        **kwargs: Any,
    ) -> None:
        super().__init__(endpoint=endpoint, api_key_env=api_key_env, **kwargs)

    def _request_params(self, query: str, max_results: int) -> dict[str, Any]:
        return {"q": query, "count": max_results}

    def _auth_headers(self, key: str | None) -> dict[str, str]:
        return {"X-Subscription-Token": key} if key else {}

    def _parse_results(self, body: Any) -> list[SearchResult]:
        if not isinstance(body, dict) or not isinstance(body.get("web"), dict):
            raise SearchResponseError("Brave response must contain a web object")
        items = body["web"].get("results")
        if not isinstance(items, list):
            raise SearchResponseError("Brave response must contain web.results")
        results: list[SearchResult] = []
        for index, item in enumerate(items[:100]):
            if not isinstance(item, dict):
                continue
            result = self._result(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=str(item.get("description") or item.get("snippet") or ""),
                score=max(0.1, 1.0 - index * 0.05),
                published_at=item.get("page_age") or item.get("age"),
            )
            if result:
                results.append(result)
        return self._deduplicate(results)


class SerperSearchProvider(NativeSearchProvider):
    source = "serper"
    method = "POST"

    def __init__(
        self,
        *,
        endpoint: str = "https://google.serper.dev/search",
        api_key_env: str = "SERPER_API_KEY",
        **kwargs: Any,
    ) -> None:
        super().__init__(endpoint=endpoint, api_key_env=api_key_env, **kwargs)

    def _auth_headers(self, key: str | None) -> dict[str, str]:
        return {"X-API-KEY": key} if key else {}

    def _request_body(self, query: str, max_results: int) -> dict[str, Any]:
        return {"q": query, "num": max_results}

    def _parse_results(self, body: Any) -> list[SearchResult]:
        if not isinstance(body, dict) or not isinstance(body.get("organic"), list):
            raise SearchResponseError("Serper response must contain an organic array")
        results: list[SearchResult] = []
        for index, item in enumerate(body["organic"][:100]):
            if not isinstance(item, dict):
                continue
            result = self._result(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=str(item.get("snippet") or ""),
                score=max(0.1, 1.0 - index * 0.05),
                published_at=item.get("date"),
            )
            if result:
                results.append(result)
        return self._deduplicate(results)


def build_search_provider(config: dict[str, Any] | None = None) -> SearchProvider:
    """Build a configured e-commerce search provider without making a request."""

    options = dict(config or {})
    provider = _normalize_provider_name(options.get("provider"))
    if provider not in SUPPORTED_SEARCH_PROVIDERS:
        supported = ", ".join(SUPPORTED_SEARCH_PROVIDERS)
        raise SearchConfigurationError(
            f"Unsupported search provider '{provider}'. Supported providers: {supported}"
        )
    common = {
        "timeout": float(options.get("timeout", 10.0)),
        "max_retries": int(options.get("max_retries", 0)),
        "retry_backoff": float(options.get("retry_backoff", 0.0)),
        "transport": options.get("transport"),
    }
    if provider == "tavily":
        return HttpJsonSearchProvider(
            endpoint=options.get("endpoint") or os.getenv("TAVILY_SEARCH_URL", "https://api.tavily.com/search"),
            api_key=options.get("api_key"),
            api_key_env=options.get("api_key_env", "TAVILY_API_KEY"),
            source="tavily",
            **common,
        )
    if provider == "searxng":
        return SearXNGSearchProvider(
            endpoint=options.get("endpoint")
            or os.getenv("SEARXNG_URL")
            or os.getenv("SEARXNG_HOST")
            or os.getenv("SEARX_HOST")
            or "http://localhost:8080/search",
            api_key=options.get("api_key"),
            api_key_env=options.get("api_key_env", "SEARXNG_API_KEY"),
            **common,
        )
    if provider == "brave":
        return BraveSearchProvider(
            endpoint=options.get("endpoint") or "https://api.search.brave.com/res/v1/web/search",
            api_key=options.get("api_key"),
            api_key_env=options.get("api_key_env", "BRAVE_SEARCH_API_KEY"),
            **common,
        )
    if provider == "serper":
        return SerperSearchProvider(
            endpoint=options.get("endpoint") or "https://google.serper.dev/search",
            api_key=options.get("api_key"),
            api_key_env=options.get("api_key_env", "SERPER_API_KEY"),
            **common,
        )
    return HttpJsonSearchProvider(
        endpoint=options.get("endpoint") or os.getenv("SEARCH_API_URL") or "https://example.invalid/search",
        api_key=options.get("api_key"),
        api_key_env=options.get("api_key_env", "SEARCH_API_KEY"),
        source="custom_http_json",
        auth_header=options.get("auth_header", "Authorization"),
        auth_prefix=options.get("auth_prefix", "Bearer"),
        require_api_key=bool(options.get("require_api_key", True)),
        allow_insecure_endpoint=bool(options.get("allow_insecure_endpoint", False)),
        **common,
    )
