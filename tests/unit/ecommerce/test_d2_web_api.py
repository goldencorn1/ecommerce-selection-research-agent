from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.server.app import app


def test_authorized_data_validation_endpoint_is_workspace_bound():
    body = {
        "source": {
            "source_id": "owned-catalog",
            "provider": "示例授权平台",
            "source_kind": "marketplace_api",
            "authorization_status": "verified",
            "authorization_reference": "contract-2026-demo",
            "terms_url": "https://example.test/terms",
            "allowed_use": "内部研究",
            "owner_id": "d2-api-a",
        },
        "records": [
            {
                "record_id": "sku-001",
                "source_id": "owned-catalog",
                "title": "授权商品",
                "product_url": "https://example.test/product/1",
                "price": 199,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    }
    with TestClient(app) as client:
        accepted = client.post(
            "/api/ecommerce/authorized-data/validate",
            headers={"X-Workspace-Id": "d2-api-a"},
            json=body,
        )
        rejected = client.post(
            "/api/ecommerce/authorized-data/validate",
            headers={"X-Workspace-Id": "d2-api-b"},
            json=body,
        )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ready_for_verification"
    assert accepted.json()["commercial_decision_ready"] is False
    assert rejected.status_code == 403


def test_signed_workspace_mode_can_be_enabled_without_affecting_public_health(monkeypatch):
    monkeypatch.setenv("ECOMMERCE_WORKSPACE_TOKEN_SECRET", "d2-test-secret")
    monkeypatch.setenv("ECOMMERCE_REQUIRE_WORKSPACE_TOKEN", "true")
    with TestClient(app) as client:
        session = client.get(
            "/api/ecommerce/session", headers={"X-Workspace-Id": "d2-secure"}
        )
        health = client.get("/api/ecommerce/health")
        denied = client.post(
            "/api/ecommerce/research",
            headers={"X-Workspace-Id": "d2-secure"},
            json={"category": "折叠桌", "mode": "mock", "model": "mock"},
        )
        allowed = client.post(
            "/api/ecommerce/research",
            headers={
                "X-Workspace-Id": "d2-secure",
                "X-Workspace-Token": session.json()["workspace_token"],
            },
            json={"category": "折叠桌", "mode": "mock", "model": "mock"},
        )
    assert session.status_code == 200
    assert session.json()["auth_mode"] == "signed_workspace_token"
    assert health.status_code == 200
    assert denied.status_code == 401
    assert allowed.status_code == 200
