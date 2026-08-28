"""Offline regression tests for the B3 multi-provider search factory."""

from __future__ import annotations

import json

import httpx
import pytest

from src.ecommerce.search import (
    BraveSearchProvider,
    SearchConfigurationError,
    SearXNGSearchProvider,
    SerperSearchProvider,
    build_search_provider,
    run_search_preflight,
)


def test_searxng_provider_uses_json_get_without_an_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/search"
        assert request.url.params["q"] == "露营桌"
        assert request.url.params["format"] == "json"
        assert "authorization" not in request.headers
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "SearXNG 结果",
                        "url": "https://example.test/searxng",
                        "content": "售价 ¥199",
                    }
                ]
            },
        )

    provider = SearXNGSearchProvider(
        endpoint="http://searxng.test",
        transport=httpx.MockTransport(handler),
    )
    result = provider.search("露营桌")

    assert result[0].source == "searxng"
    assert result[0].price == 199.0


def test_brave_provider_maps_native_response_and_header(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.params["count"] == "2"
        assert request.headers["X-Subscription-Token"] == "brave-test-key"
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "title": "Brave 结果",
                            "url": "https://example.test/brave",
                            "description": "活动价 ¥89",
                        }
                    ]
                }
            },
        )

    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    provider = BraveSearchProvider(
        api_key="brave-test-key",
        transport=httpx.MockTransport(handler),
    )
    result = provider.search("露营桌", max_results=2)

    assert result[0].source == "brave"
    assert result[0].price == 89.0


def test_serper_provider_maps_native_response_and_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.headers["X-API-KEY"] == "serper-test-key"
        assert json.loads(request.content) == {"q": "露营桌", "num": 3}
        return httpx.Response(
            200,
            json={
                "organic": [
                    {
                        "title": "Serper 结果",
                        "link": "https://example.test/serper",
                        "snippet": "售价 129 元",
                    }
                ]
            },
        )

    provider = SerperSearchProvider(
        api_key="serper-test-key",
        transport=httpx.MockTransport(handler),
    )
    result = provider.search("露营桌", max_results=3)

    assert result[0].source == "serper"
    assert result[0].price == 129.0


def test_factory_preserves_tavily_default_and_supports_custom_auth() -> None:
    tavily = build_search_provider({"provider": "tavily", "api_key": "key"})
    assert tavily.source == "tavily"

    custom = build_search_provider(
        {
            "provider": "custom",
            "endpoint": "https://search.example.test/query",
            "api_key": "custom-key",
            "auth_header": "X-API-Key",
            "auth_prefix": "Token",
        }
    )
    assert custom.source == "custom_http_json"
    assert custom.endpoint == "https://search.example.test/query"
    assert custom.auth_header == "X-API-Key"
    assert custom.auth_prefix == "Token"


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(SearchConfigurationError, match="Unsupported search provider"):
        build_search_provider({"provider": "unknown"})


def test_searxng_preflight_is_secret_safe_and_does_not_require_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # The real preflight intentionally uses the configured endpoint. This test
    # verifies that a missing SearXNG key is not treated as a configuration error
    # before the network request is attempted.
    monkeypatch.delenv("SEARXNG_API_KEY", raising=False)
    result = run_search_preflight(
        "露营桌",
        provider="searxng",
        endpoint="http://127.0.0.1:9/search",
        timeout=0.01,
    )

    assert result["provider"] == "searxng"
    assert result["api_key_configured"] is True
    assert result["status"] == "error"
    assert "SEARXNG_API_KEY" not in str(result)
