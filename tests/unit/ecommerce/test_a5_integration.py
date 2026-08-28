"""Interface-level regression tests for A5 runtime protections."""

import importlib

from fastapi.testclient import TestClient

from src.ecommerce.observability import MemoryObservationRecorder
from src.ecommerce.resilience import CircuitBreaker, RateLimiter


app_module = importlib.import_module("src.server.app")


def _request_payload() -> dict[str, str]:
    return {
        "category": "可折叠露营桌",
        "market": "中国大陆电商",
        "mode": "mock",
        "model": "mock",
    }


def test_a5_health_and_observability_report_runtime_state(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "_ecommerce_rate_limiter", RateLimiter(limit=10))
    monkeypatch.setattr(
        app_module,
        "_ecommerce_circuit_breaker",
        CircuitBreaker(failure_threshold=3, recovery_timeout=30, name="test"),
    )
    recorder = MemoryObservationRecorder()
    monkeypatch.setattr(app_module, "_ecommerce_observations", recorder)

    with TestClient(app_module.app) as client:
        response = client.post(
            "/api/ecommerce/research",
            headers={"X-Workspace-Id": "a5-observability"},
            json=_request_payload(),
        )
        assert response.status_code == 200

        health = client.get("/api/ecommerce/health")
        assert health.status_code == 200
        assert health.json()["circuit_breaker"]["state"] == "closed"
        assert health.json()["observation_event_count"] >= 2

        events = client.get("/api/ecommerce/observability?limit=10")
        assert events.status_code == 200
        assert {item["status"] for item in events.json()["events"]} >= {"started", "success"}


def test_a5_rate_limit_returns_retryable_429(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "_ecommerce_rate_limiter", RateLimiter(limit=1))
    monkeypatch.setattr(
        app_module,
        "_ecommerce_circuit_breaker",
        CircuitBreaker(failure_threshold=3, recovery_timeout=30, name="test"),
    )
    monkeypatch.setattr(app_module, "_ecommerce_observations", MemoryObservationRecorder())

    with TestClient(app_module.app) as client:
        first = client.post(
            "/api/ecommerce/research",
            headers={"X-Workspace-Id": "a5-rate"},
            json=_request_payload(),
        )
        second = client.post(
            "/api/ecommerce/research",
            headers={"X-Workspace-Id": "a5-rate"},
            json=_request_payload(),
        )

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) >= 1


def test_a5_circuit_breaker_returns_503_after_failure_threshold(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "_ecommerce_rate_limiter", RateLimiter(limit=10))
    monkeypatch.setattr(
        app_module,
        "_ecommerce_circuit_breaker",
        CircuitBreaker(failure_threshold=1, recovery_timeout=30, name="test"),
    )
    monkeypatch.setattr(app_module, "_ecommerce_observations", MemoryObservationRecorder())

    def fail(_payload):
        raise RuntimeError("synthetic A5 failure")

    monkeypatch.setattr(app_module, "run_ecommerce_graph", fail)
    with TestClient(app_module.app) as client:
        first = client.post(
            "/api/ecommerce/research",
            headers={"X-Workspace-Id": "a5-circuit"},
            json=_request_payload(),
        )
        second = client.post(
            "/api/ecommerce/research",
            headers={"X-Workspace-Id": "a5-circuit"},
            json=_request_payload(),
        )

    assert first.status_code == 500
    assert second.status_code == 503
    assert second.headers["retry-after"]
