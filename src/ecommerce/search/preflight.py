"""One-request, secret-safe preflight for an authorized search provider."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .errors import SearchProviderError
from .providers import build_search_provider


def _safe_url(url: str) -> str:
    """Remove query, fragment and credentials before showing a result URL."""

    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def run_search_preflight(
    query: str,
    *,
    provider: str | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
    api_key_env: str | None = None,
    timeout: float = 10.0,
    max_retries: int = 0,
    retry_backoff: float = 0.0,
    max_results: int = 3,
) -> dict[str, Any]:
    """Make one authorized request and return diagnostics without secrets."""

    selected_provider = (provider or os.getenv("SEARCH_API") or "tavily").lower()
    provider_config: dict[str, Any] = {
        "provider": selected_provider,
        "endpoint": endpoint,
        "api_key": api_key,
        "timeout": timeout,
        "max_retries": max_retries,
        "retry_backoff": retry_backoff,
    }
    if api_key_env:
        provider_config["api_key_env"] = api_key_env
    try:
        search_provider = build_search_provider(provider_config)
        key_configured = not getattr(search_provider, "require_api_key", True) or bool(
            api_key or os.getenv(getattr(search_provider, "api_key_env", ""))
        )
        results = search_provider.search(query, max_results=max_results)
    except SearchProviderError as exc:
        metadata = getattr(search_provider, "last_request_metadata", None) if "search_provider" in locals() else {}
        metadata = metadata or {}
        return {
            "status": "error",
            "provider": getattr(search_provider, "source", selected_provider),
            "api_key_configured": bool(locals().get("key_configured", False)),
            "configured": bool(locals().get("key_configured", False)),
            "reachable": False,
            "error_code": exc.code,
            "latency_ms": metadata.get("latency_ms"),
            "request_metadata": metadata,
        }
    metadata = search_provider.last_request_metadata or {}
    return {
        "status": "success",
        "provider": search_provider.source,
        "api_key_configured": key_configured,
        "configured": key_configured,
        "reachable": True,
        "latency_ms": metadata.get("latency_ms"),
        "result_count": len(results),
        "request_metadata": metadata,
        "sample_results": [
            {
                "title": result.title,
                "url": _safe_url(result.url),
                "score": result.score,
                "published_at": result.published_at.isoformat()
                if result.published_at
                else None,
                "has_price": result.price is not None,
            }
            for result in results
        ],
    }
