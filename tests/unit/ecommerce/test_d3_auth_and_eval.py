from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from src.ecommerce.authorized_adapters import get_authorized_adapter, list_authorized_adapters
from src.ecommerce.cross_category_eval import evaluate_cross_category_run
from src.ecommerce.search.benchmark import (
    SearchBenchmarkRun,
    SearchBenchmarkSummary,
)
from src.server.app import app
from src.server.tenant_auth import decode_bearer_token


def _token(tenant_id: str, *, secret: str = "d3-secret") -> str:
    return jwt.encode(
        {
            "sub": "user-d3",
            "tenant_id": tenant_id,
            "scope": "ecommerce:research",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        secret,
        algorithm="HS256",
    )


def test_jwt_requires_exp_sub_tenant_and_fixed_algorithm():
    token = _token("tenant-a")
    principal = decode_bearer_token("Bearer " + token, secret="d3-secret")
    assert principal is not None
    assert principal.tenant_id == "tenant-a"
    assert principal.scopes == ("ecommerce:research",)

    wrong_secret = decode_bearer_token("Bearer " + token, secret="wrong")
    assert wrong_secret is None
    missing_exp = jwt.encode({"sub": "user", "tenant_id": "tenant-a"}, "d3-secret", algorithm="HS256")
    assert decode_bearer_token("Bearer " + missing_exp, secret="d3-secret") is None


def test_cross_category_threshold_is_explicit():
    summary = SearchBenchmarkSummary(
        category_count=3,
        search_success_rate=1.0,
        interface_success_rate=1.0,
        evidence_usable_rate=1.0,
        commercial_decision_ready_rate=0.0,
        average_latency_ms=10,
        average_warning_count=0,
        source_filter_exhausted_case_count=0,
        module_averages={},
    )
    run = SearchBenchmarkRun(
        source_policy="annotate",
        cases=[],
        summary=summary,
    )
    result = evaluate_cross_category_run(run)
    assert result["status"] == "pass"
    assert result["commercial_decision_ready_rate"] == 0.0


def test_adapter_registry_is_allowlisted_and_secret_free():
    adapters = list_authorized_adapters()
    assert {item["adapter_id"] for item in adapters} >= {
        "user_jsonl",
        "infoquest_reader",
        "marketplace_api",
    }
    assert get_authorized_adapter("unknown") is None
    assert all("api_key" not in item for item in adapters)


def test_bearer_auth_enforces_tenant_on_stateful_api(monkeypatch):
    monkeypatch.setenv("ECOMMERCE_REQUIRE_BEARER_AUTH", "true")
    monkeypatch.setenv("ECOMMERCE_JWT_HS256_SECRET", "d3-secret")
    with TestClient(app) as client:
        public_health = client.get("/api/ecommerce/health")
        denied = client.post(
            "/api/ecommerce/research",
            headers={"X-Workspace-Id": "tenant-a"},
            json={"category": "折叠桌", "mode": "mock", "model": "mock"},
        )
        wrong_tenant = client.post(
            "/api/ecommerce/research",
            headers={
                "Authorization": "Bearer " + _token("tenant-a"),
                "X-Workspace-Id": "tenant-b",
            },
            json={"category": "折叠桌", "mode": "mock", "model": "mock"},
        )
        allowed = client.post(
            "/api/ecommerce/research",
            headers={
                "Authorization": "Bearer " + _token("tenant-a"),
                "X-Workspace-Id": "tenant-a",
            },
            json={"category": "折叠桌", "mode": "mock", "model": "mock"},
        )
    assert public_health.status_code == 200
    assert denied.status_code == 401
    assert wrong_tenant.status_code == 403
    assert allowed.status_code == 200
