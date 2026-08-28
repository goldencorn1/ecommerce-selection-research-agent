from datetime import datetime, timezone
import importlib
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.ecommerce.product_data import InfoQuestProductEnricher, run_infoquest_preflight
from src.ecommerce.search.models import SearchResult
from src.server.app import app


def _result() -> SearchResult:
    return SearchResult(
        title="折叠桌商品页",
        url="https://shop.example/product-1",
        snippet="搜索摘要",
        source="tavily",
        score=0.9,
        retrieved_at=datetime.now(timezone.utc),
    )


def test_infoquest_enricher_extracts_page_price_without_claiming_sales(monkeypatch):
    monkeypatch.setenv("INFOQUEST_API_KEY", "configured-for-test")

    class FakeClient:
        def crawl(self, url, return_format):
            assert url.endswith("product-1")
            assert return_format == "html"
            return "<html><body><h1>折叠桌</h1><p>售价：129 元，轻便耐用</p></body></html>"

    enriched, details = InfoQuestProductEnricher(client=FakeClient()).enrich([_result()])
    assert details["data_status"] == "success"
    assert details["data_success_count"] == 1
    assert enriched[0].price == 129.0
    assert "售价" in enriched[0].snippet
    assert enriched[0].source == "tavily+infoquest"


def test_infoquest_enricher_is_explicitly_not_configured(monkeypatch):
    monkeypatch.delenv("INFOQUEST_API_KEY", raising=False)
    original = _result()
    enriched, details = InfoQuestProductEnricher(client=SimpleNamespace()).enrich([original])
    assert details["data_status"] == "not_configured"
    assert enriched == [original]


def test_infoquest_preflight_is_secret_safe(monkeypatch):
    monkeypatch.delenv("INFOQUEST_API_KEY", raising=False)
    result = run_infoquest_preflight()
    assert result["status"] == "error"
    assert result["error_code"] == "config_error"
    assert "configured-for-test" not in str(result)


def test_capability_and_data_preflight_endpoint(monkeypatch):
    app_module = importlib.import_module("src.server.app")
    monkeypatch.setenv("INFOQUEST_API_KEY", "configured-for-test")
    monkeypatch.setattr(
        app_module,
        "run_infoquest_preflight",
        lambda url, timeout: {
            "status": "success",
            "provider": "infoquest",
            "configured": True,
            "reachable": True,
            "url": url,
            "timeout": timeout,
        },
    )
    with TestClient(app) as client:
        capabilities = client.get("/api/ecommerce/capabilities").json()["capabilities"]
        infoquest = next(item for item in capabilities["data_sources"] if item["id"] == "infoquest")
        assert infoquest["configured"] is True

        response = client.post(
            "/api/ecommerce/preflight",
            json={"provider": "data", "data_source": "infoquest"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["checks"]["data"]["provider"] == "infoquest"
