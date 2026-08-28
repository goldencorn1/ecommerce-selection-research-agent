"""Offline tests for the e-commerce search adapter boundary."""

from __future__ import annotations

import httpx
import pytest
from datetime import timezone

from src.ecommerce.models import Evidence
from src.ecommerce.search import (
    HttpJsonSearchProvider,
    MockSearchProvider,
    SearchConfigurationError,
    SearchEmptyResultError,
    SearchHTTPError,
    SearchCache,
    SearchResponseError,
    SearchResponse,
    SearchResult,
    SearchTimeoutError,
    search_result_to_evidence,
    run_search_preflight,
)
from src.ecommerce.search.adapters import _parse_price


def make_provider(handler, monkeypatch) -> HttpJsonSearchProvider:
    transport = httpx.MockTransport(handler)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    return HttpJsonSearchProvider(api_key="unit-test-key", transport=transport)


def test_mock_provider_is_stable_and_offline() -> None:
    provider = MockSearchProvider()
    first = provider.search("可折叠露营桌", max_results=2)
    second = provider.search("可折叠露营桌", max_results=2)
    assert first == second
    assert first[0].source == "mock-search"


def test_search_cache_is_bounded_and_preserves_response_objects() -> None:
    cache = SearchCache(ttl_seconds=60, max_entries=1)
    response = SearchResponse(results=(), metadata={"attempts": 1})

    cache.set("first", response)
    hit = cache.get("first")
    assert hit is not None
    assert hit.response == response
    assert hit.age_seconds >= 0

    cache.set("second", SearchResponse(results=(), metadata={"attempts": 1}))
    assert cache.get("first") is None


def test_price_parser_prefers_labeled_sale_and_rejects_common_amount_noise() -> None:
    assert _parse_price(None, "商品原价 ¥299，券后 ¥199", "折叠桌") == 199.0
    assert _parse_price(None, "市场规模达到 10 亿元，报告价格 ¥8800", "行业研究报告") is None
    assert _parse_price(None, "商品 ¥99 起，另有 ¥199 运费说明", "折叠桌") is None
    assert _parse_price(None, "价格范围 ¥99-199", "折叠桌") is None


def test_price_parser_handles_markup_currency_spacing_and_chinese_units() -> None:
    assert _parse_price(None, "<strong>到手价：¥ 1,299</strong>&nbsp;", "平板电脑") == 1299.0
    assert _parse_price(None, "售价 1.2 万元", "高端设备") == 12000.0


def test_http_provider_success_and_evidence_mapping(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://api.tavily.com/search"
        assert request.read() != b""
        assert request.headers["Authorization"] == "Bearer unit-test-key"
        assert b"unit-test-key" not in request.content
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "露营桌评测",
                        "url": "https://example.test/table",
                        "content": "轻量、可折叠。",
                        "score": 0.8,
                    }
                ]
            },
        )

    result = make_provider(handler, monkeypatch).search("露营桌")
    assert len(result) == 1
    assert isinstance(result[0], SearchResult)
    evidence = search_result_to_evidence(result[0], supports=["trend"])
    assert isinstance(evidence, Evidence)
    assert evidence.source == "https://example.test/table"
    assert evidence.confidence == 0.8
    assert evidence.supports == ["trend"]
    assert evidence.source_type == "tavily"
    assert evidence.retrieved_at == result[0].retrieved_at


def test_http_provider_exposes_per_call_metadata_without_shared_state(monkeypatch) -> None:
    provider = make_provider(
        lambda request: httpx.Response(
            200,
            json={"results": [{"title": "结果", "url": "https://example.test/result"}]},
        ),
        monkeypatch,
    )

    response = provider.search_with_metadata("独立元数据")

    assert isinstance(response, SearchResponse)
    assert response.results[0].title == "结果"
    assert response.metadata["attempts"] == 1
    assert response.metadata == provider.last_request_metadata


def test_http_provider_deduplicates_urls_and_extracts_optional_metadata(monkeypatch) -> None:
    provider = make_provider(
        lambda request: httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "低分重复结果",
                        "url": "https://www.example.test/table?utm_source=x",
                        "content": "售价 ¥129",
                        "score": 0.4,
                    },
                    {
                        "title": "高分商品结果",
                        "url": "https://example.test/table#reviews",
                        "content": "售价 ¥169",
                        "score": 0.9,
                        "price": "1,299",
                        "published_date": "2026-08-01T12:00:00Z",
                    },
                ]
            },
        ),
        monkeypatch,
    )

    result = provider.search("带价格的露营桌")

    assert len(result) == 1
    assert result[0].title == "高分商品结果"
    assert result[0].price == 1299.0
    assert result[0].published_at is not None
    assert result[0].published_at.tzinfo == timezone.utc
    assert provider.last_request_metadata["result_count"] == 1
    assert provider.last_request_metadata["returned_count"] == 1


def test_http_provider_recovers_labeled_date_from_page_text(monkeypatch) -> None:
    provider = make_provider(
        lambda request: httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "露营桌选购指南",
                        "url": "https://example.test/camping-table",
                        "content": "更新时间：2025年3月13日。轻量折叠设计。",
                        "score": 0.8,
                    }
                ]
            },
        ),
        monkeypatch,
    )

    result = provider.search("露营桌日期")

    assert result[0].published_at is not None
    assert result[0].published_at.isoformat() == "2025-03-13T00:00:00+00:00"


def test_http_provider_empty_results(monkeypatch) -> None:
    provider = make_provider(lambda request: httpx.Response(200, json={"results": []}), monkeypatch)
    with pytest.raises(SearchEmptyResultError) as error:
        provider.search("无结果")
    assert error.value.to_dict()["code"] == "search_empty_result"


def test_http_provider_http_error(monkeypatch) -> None:
    provider = make_provider(lambda request: httpx.Response(429, json={"error": "rate"}), monkeypatch)
    with pytest.raises(SearchHTTPError) as error:
        provider.search("限流")
    assert error.value.status_code == 429
    assert "api_key" not in str(error.value.to_dict())


def test_http_provider_invalid_json(monkeypatch) -> None:
    provider = make_provider(lambda request: httpx.Response(200, content=b"not-json"), monkeypatch)
    with pytest.raises(SearchResponseError):
        provider.search("坏响应")


def test_http_provider_timeout(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("offline timeout", request=request)

    provider = make_provider(handler, monkeypatch)
    with pytest.raises(SearchTimeoutError):
        provider.search("超时")


def test_http_provider_requires_key_without_reading_dotenv(monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    provider = HttpJsonSearchProvider(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    with pytest.raises(SearchConfigurationError):
        provider.search("需要密钥")


def test_search_preflight_reports_missing_key_without_secret(monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    result = run_search_preflight("可折叠露营桌", max_results=1)

    assert result["status"] == "error"
    assert result["api_key_configured"] is False
    assert result["error_code"] == "search_configuration_error"
    assert "tvly-" not in str(result)


def test_http_provider_rejects_non_https_endpoint(monkeypatch) -> None:
    provider = HttpJsonSearchProvider(
        endpoint="http://example.test/search",
        api_key="unit-test-key",
        transport=httpx.MockTransport(lambda request: httpx.Response(200)),
    )

    with pytest.raises(SearchConfigurationError, match="HTTPS"):
        provider.search("明文 endpoint")


def test_http_provider_reads_only_the_named_environment_variable(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer dummy-unit-test-key"
        assert b"dummy-unit-test-key" not in request.content
        return httpx.Response(
            200,
            json={"results": [{"title": "结果", "url": "https://example.test"}]},
        )

    monkeypatch.setenv("UNIT_TEST_SEARCH_KEY", "dummy-unit-test-key")
    provider = HttpJsonSearchProvider(
        api_key_env="UNIT_TEST_SEARCH_KEY",
        transport=httpx.MockTransport(handler),
    )
    assert provider.search("环境变量")[0].title == "结果"


def test_http_provider_rejects_invalid_results_shape(monkeypatch) -> None:
    provider = make_provider(lambda request: httpx.Response(200, json={"items": []}), monkeypatch)
    with pytest.raises(SearchResponseError):
        provider.search("错误结构")


def test_http_provider_retries_transient_status_then_succeeds(monkeypatch) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(
            200,
            json={"results": [{"title": "恢复", "url": "https://example.test/recovered"}]},
        )

    provider = make_provider(handler, monkeypatch)
    provider.max_retries = 1
    result = provider.search("重试成功")

    assert calls == 2
    assert provider.request_count == 1
    assert provider.attempt_count == 2
    assert result[0].title == "恢复"
    assert provider.last_request_metadata == {
        "latency_ms": provider.last_request_metadata["latency_ms"],
        "attempts": 2,
        "status_code": 200,
        "result_count": 1,
        "returned_count": 1,
    }


def test_http_provider_retries_timeout_then_succeeds(monkeypatch) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("offline timeout", request=request)
        return httpx.Response(
            200,
            json={"results": [{"title": "超时恢复", "url": "https://example.test/timeout"}]},
        )

    provider = make_provider(handler, monkeypatch)
    provider.max_retries = 1
    assert provider.search("超时重试")[0].title == "超时恢复"
    assert calls == 2
    assert provider.attempt_count == 2
    assert provider.last_request_metadata["attempts"] == 2
    assert provider.last_request_metadata["status_code"] == 200


def test_http_provider_retries_until_exhausted(monkeypatch) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, json={"error": "rate"})

    provider = make_provider(handler, monkeypatch)
    provider.max_retries = 2
    with pytest.raises(SearchHTTPError) as error:
        provider.search("重试耗尽")

    assert calls == 3
    assert provider.request_count == 1
    assert provider.attempt_count == 3
    assert error.value.details["attempts"] == 3
    assert error.value.details["status_code"] == 429


def test_http_provider_does_not_retry_client_errors(monkeypatch) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": "bad request"})

    provider = make_provider(handler, monkeypatch)
    provider.max_retries = 3
    with pytest.raises(SearchHTTPError) as error:
        provider.search("四百错误")

    assert calls == 1
    assert error.value.details["attempts"] == 1
    assert error.value.details["status_code"] == 400


def test_http_provider_metadata_excludes_api_key(monkeypatch) -> None:
    secret = "unit-secret-never-in-metadata"
    provider = HttpJsonSearchProvider(
        api_key=secret,
        max_retries=1,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(503, json={"error": "temporary"})
        ),
    )

    with pytest.raises(SearchHTTPError) as error:
        provider.search("安全元数据")

    assert set(provider.last_request_metadata or {}) == {
        "latency_ms",
        "attempts",
        "status_code",
    }
    assert secret not in str(provider.last_request_metadata)
    assert secret not in str(error.value.to_dict())


def test_http_provider_exposes_safe_transport_error_type(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection failure", request=request)

    provider = HttpJsonSearchProvider(
        api_key="unit-secret",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(SearchHTTPError) as error:
        provider.search("连接诊断")

    assert provider.last_request_metadata["status_code"] is None
    assert provider.last_request_metadata["error_type"] == "ConnectError"
    assert error.value.details["reason"] == "ConnectError"
