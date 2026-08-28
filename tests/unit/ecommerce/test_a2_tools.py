"""Offline contract tests for the A2 price and ranking tools."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from src.ecommerce.tools import (
    HTTPPriceTool,
    HTTPRankTool,
    MockPriceTool,
    MockRankTool,
    PriceQuote,
    RankEntry,
    ToolHTTPError,
    ToolResponseError,
    ToolTimeoutError,
)


def test_mock_tools_are_stable_offline_and_mark_results_as_mock() -> None:
    first_prices = MockPriceTool().get_price("折叠露营桌")
    second_prices = MockPriceTool().get_price("折叠露营桌")
    first_ranks = MockRankTool().get_rankings("折叠露营桌", limit=2)
    second_ranks = MockRankTool().get_rankings("折叠露营桌", limit=2)

    assert first_prices == second_prices
    assert first_ranks == second_ranks
    assert first_prices[0].source_type == "mock"
    assert first_prices[0].source.startswith("mock://")
    assert all(item.source_type == "mock" for item in first_ranks)
    assert len(first_ranks) == 2


def test_mock_empty_results_are_a_safe_degradation_path() -> None:
    assert MockPriceTool(empty_results=True).get_price("商品") == []
    assert MockRankTool(empty_results=True).get_rankings("商品") == []
    assert MockPriceTool().get_price("") == []
    assert MockRankTool().get_rankings("", limit=10) == []


def test_results_convert_to_evidence_without_losing_provenance() -> None:
    retrieved_at = datetime(2026, 8, 16, 1, 2, 3, tzinfo=timezone.utc)
    quote = PriceQuote(
        product_id="sku-1",
        title="商品一",
        price=88.5,
        source="https://shop.example/items/1",
        retrieved_at=retrieved_at,
        evidence_id="price-evidence-1",
        supports=["price-band"],
        source_type="catalog",
    )
    entry = RankEntry(
        rank=1,
        product_id="sku-1",
        title="商品一",
        source="https://shop.example/rankings",
        retrieved_at=retrieved_at,
        evidence_id="rank-evidence-1",
        supports=["competition"],
        source_type="catalog",
    )

    price_evidence = quote.to_evidence(supports=["recommendation", "price-band"])
    rank_evidence = entry.to_evidence(supports=["competition"])

    assert price_evidence.source == quote.source
    assert price_evidence.retrieved_at == retrieved_at
    assert price_evidence.evidence_id == "price-evidence-1"
    assert price_evidence.supports == ["price-band", "recommendation"]
    assert rank_evidence.evidence_id == "rank-evidence-1"
    assert rank_evidence.supports == ["competition"]


def test_tool_models_have_json_serialization() -> None:
    quote = MockPriceTool().get_price("水杯")[0]
    entry = MockRankTool().get_rankings("水杯")[0]

    quote_json = quote.model_dump_json()
    entry_json = entry.model_dump_json()
    assert '"source_type":"mock"' in quote_json
    assert '"evidence_id":"mock-price-' in quote_json
    assert '"retrieved_at":"2026-01-01T00:00:00Z"' in quote_json
    assert '"rank":1' in entry_json
    assert '"supports":["ranking"]' in entry_json


def test_http_tools_parse_standard_json_with_mock_transport() -> None:
    retrieved_at = "2026-08-16T01:02:03Z"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/prices"):
            assert request.url.params["query"] == "水杯"
            return httpx.Response(
                200,
                json={
                    "quotes": [
                        {
                            "product_id": "sku-1",
                            "title": "水杯",
                            "price": 39.9,
                            "currency": "CNY",
                            "source": "https://shop.example/item/1",
                            "retrieved_at": retrieved_at,
                            "evidence_id": "http-price-1",
                            "supports": ["price-band"],
                        }
                    ]
                },
            )
        assert request.url.params["category"] == "水杯"
        assert request.url.params["limit"] == "2"
        return httpx.Response(
            200,
            json={
                "rankings": [
                    {
                        "rank": 1,
                        "product_id": "sku-1",
                        "title": "水杯",
                        "source": "https://shop.example/rank",
                        "retrieved_at": retrieved_at,
                        "evidence_id": "http-rank-1",
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    quote = HTTPPriceTool(
        "https://api.example.test/prices", transport=transport
    ).get_price("水杯")[0]
    entry = HTTPRankTool(
        "https://api.example.test/rankings", transport=transport
    ).get_rankings("水杯", limit=2)[0]

    assert quote.price == 39.9
    assert quote.source_type == "http"
    assert quote.to_evidence().evidence_id == "http-price-1"
    assert entry.rank == 1
    assert entry.retrieved_at.isoformat() == retrieved_at.replace("Z", "+00:00")
    assert entry.to_evidence().source == "https://shop.example/rank"


def test_http_tools_accept_injected_client_without_creating_a_network_client() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"data": {"prices": [{"id": "sku", "price": {"amount": 12}}]}},
            )
        )
    )
    try:
        result = HTTPPriceTool(
            "https://api.example.test/prices", client=client
        ).get_price("sku")
    finally:
        client.close()
    assert result[0].price == 12


def test_http_empty_results_are_returned_for_caller_fallback() -> None:
    tool = HTTPPriceTool(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"quotes": []})
        )
    )
    assert tool.get_price("暂无报价") == []


@pytest.mark.parametrize(
    ("status", "error_type"),
    [(429, ToolHTTPError), (503, ToolHTTPError)],
)
def test_http_tools_raise_stable_error_for_non_2xx(
    status: int, error_type: type[Exception]
) -> None:
    tool = HTTPPriceTool(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, json={"error": "no"})
        )
    )
    with pytest.raises(error_type) as error:
        tool.get_price("商品")
    assert error.value.to_dict()["code"] == "tool_http_error"
    assert error.value.to_dict()["details"]["status_code"] == status


def test_http_tools_raise_stable_errors_for_timeout_and_bad_json() -> None:
    timeout_tool = HTTPRankTool(
        transport=httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(
                httpx.ReadTimeout("offline", request=request)
            )
        )
    )
    with pytest.raises(ToolTimeoutError) as timeout_error:
        timeout_tool.get_rankings("商品")
    assert timeout_error.value.to_dict()["code"] == "tool_timeout"

    bad_json_tool = HTTPPriceTool(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"not-json")
        )
    )
    with pytest.raises(ToolResponseError) as response_error:
        bad_json_tool.get_price("商品")
    assert response_error.value.to_dict()["code"] == "tool_response_error"


@pytest.mark.parametrize("body", [{"unexpected": []}, {"quotes": [{"price": "bad"}]}])
def test_http_tools_raise_stable_error_for_bad_json_shape(body: object) -> None:
    tool = HTTPPriceTool(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    )
    with pytest.raises(ToolResponseError) as error:
        tool.get_price("商品")
    assert error.value.to_dict()["code"] == "tool_response_error"
