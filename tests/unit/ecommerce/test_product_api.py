import importlib
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.ecommerce.product_api import ProductApiConfig, probe_product_api

app_module = importlib.import_module("src.server.app")


def test_product_api_rejects_ssrf_targets_and_allows_local_demo() -> None:
    with pytest.raises(ValueError):
        ProductApiConfig(endpoint="http://169.254.169.254/latest/meta-data")
    with pytest.raises(ValueError):
        ProductApiConfig(endpoint="https://127.0.0.1/private")
    with pytest.raises(ValueError):
        ProductApiConfig(endpoint="https://localhost/private")
    assert ProductApiConfig(endpoint="http://127.0.0.1:9999/products").endpoint.startswith(
        "http://127.0.0.1"
    )


def test_product_api_normalizes_sample_and_keeps_key_out_of_result() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "sku-1",
                        "name": "轻量露营桌",
                        "amount": "199.00",
                        "detail": "https://shop.example.com/p/1",
                    }
                ]
            },
        )

    config = ProductApiConfig(
        endpoint="https://api.example.com/products",
        api_key="unit-secret",
        category="露营桌",
        field_map={"title": "name", "price": "amount", "url": "detail", "sku": "id"},
    )
    result = probe_product_api(
        config,
        owner_id="workspace-a",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result["status"] == "success"
    assert result["result_count"] == 1
    assert result["products"][0]["title"] == "轻量露营桌"
    assert result["products"][0]["price"] == 199.0
    assert observed["authorization"] == "Bearer unit-secret"
    assert "unit-secret" not in json.dumps(result, ensure_ascii=False)
    assert "%E9%9C%B2%E8%90%A5%E6%A1%8C" in str(observed["url"])
    assert result["commercial_decision_ready"] is False
    assert result["data_validation"]["status"] == "blocked"


def test_product_api_supports_custom_header_and_post_payload() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["method"] = request.method
        observed["header"] = request.headers.get("x-api-key")
        observed["body"] = json.loads(request.content)
        return httpx.Response(200, json={"items": [{"title": "商品 A", "price": 10}]})

    config = ProductApiConfig(
        endpoint="https://api.example.com/query",
        method="POST",
        auth_mode="header",
        auth_header_name="X-API-Key",
        api_key="header-secret",
        response_path="",
        field_map={"title": "title", "price": "price", "url": "url", "sku": "sku"},
    )
    result = probe_product_api(
        config,
        owner_id="workspace-a",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result["status"] == "success"
    assert observed == {
        "method": "POST",
        "header": "header-secret",
        "body": {"query": "可折叠露营桌", "category": "可折叠露营桌"},
    }


def test_product_api_route_uses_workspace_and_does_not_echo_key(monkeypatch) -> None:
    def fake_probe(config, *, owner_id):
        assert config.api_key.get_secret_value() == "route-secret"
        assert owner_id == "workspace-route"
        return {
            "status": "success",
            "message": "ok",
            "configured": True,
            "reachable": True,
            "products": [],
            "commercial_decision_ready": False,
        }

    monkeypatch.setattr(app_module, "probe_product_api", fake_probe)
    with TestClient(app_module.app) as client:
        response = client.post(
            "/api/ecommerce/authorized-data/product-api/preflight",
            headers={"X-Workspace-Id": "workspace-route"},
            json={
                "config": {
                    "endpoint": "https://api.example.com/products",
                    "api_key": "route-secret",
                }
            },
        )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "route-secret" not in response.text


def test_demo_product_api_route_returns_deterministic_demo_samples() -> None:
    with TestClient(app_module.app) as client:
        response = client.get(
            "/api/ecommerce/demo/product-api",
            params={"q": "折叠桌"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["demo_only"] is True
    assert payload["query"] == "折叠桌"
    assert len(payload["data"]) == 3
    assert all(item["source"].startswith("DEMO_ONLY") for item in payload["data"])
