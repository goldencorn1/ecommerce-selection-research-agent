from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.ecommerce.byok import runtime_credentials, scrub_runtime_credentials
from src.ecommerce.model_provider import ModelConfigurationError, build_request_model
from src.ecommerce_graph import run_ecommerce_graph
from src.server.app import _ecommerce_request_payload, app
from src.server.ecommerce_request import EcommerceWebResearchRequest


def test_byok_request_uses_secret_types_and_internal_runtime_shape():
    request = EcommerceWebResearchRequest.model_validate(
        {
            "model": "deepseek",
            "byok": {
                "model_api_key": "model-secret",
                "model_base_url": "https://api.example.com/v1",
                "model_name": "deepseek-chat",
                "search_api_key": "search-secret",
                "data_api_key": "data-secret",
            },
        }
    )

    runtime = runtime_credentials(request.byok)
    assert runtime == {
        "model": {
            "api_key": "model-secret",
            "base_url": "https://api.example.com/v1",
            "model": "deepseek-chat",
        },
        "search": {"api_key": "search-secret"},
        "data": {"api_key": "data-secret"},
    }
    assert "model-secret" not in request.model_dump(mode="json")["byok"]["model_api_key"]


def test_graph_scrubs_runtime_credentials_from_final_state():
    state = run_ecommerce_graph(
        {
            "category": "可折叠露营桌",
            "model_config": {"enabled": False, "provider": "mock"},
            "_ecommerce_runtime_credentials": {
                "model": {"api_key": "model-secret"},
                "search": {"api_key": "search-secret"},
                "data": {"api_key": "data-secret"},
            },
        }
    )
    rendered = repr(state)
    assert "model-secret" not in rendered
    assert "search-secret" not in rendered
    assert "data-secret" not in rendered
    assert not state.get("ecommerce_runtime_credentials")


def test_request_payload_keeps_byok_internal_for_research_graph():
    request = EcommerceWebResearchRequest.model_validate(
        {
            "mode": "live",
            "model": "deepseek",
            "search_provider": "tavily",
            "byok": {"model_api_key": "request-only-secret"},
        }
    )

    payload = _ecommerce_request_payload(request)

    assert payload["model_config"] == {"enabled": True, "provider": "deepseek"}
    assert payload["_ecommerce_runtime_credentials"] == {
        "model": {"api_key": "request-only-secret"},
        "search": {},
        "data": {},
    }


def test_model_initialization_failure_degrades_to_structured_report(monkeypatch):
    class BrokenEnhancer:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("model client is unavailable")

    monkeypatch.setattr("src.ecommerce.llm_report.DeepSeekReportEnhancer", BrokenEnhancer)
    state = run_ecommerce_graph(
        {
            "category": "可折叠露营桌",
            "model_config": {"enabled": True, "provider": "deepseek"},
        }
    )

    assert state["ecommerce_model_status"] == "fallback"
    assert state["ecommerce_report"]["recommendations"]
    assert state["ecommerce_model_error_kind"]


def test_scrub_runtime_credentials_clears_mutable_values():
    credentials = {"model": {"api_key": "secret"}, "search": {"api_key": "secret-2"}}
    scrub_runtime_credentials(credentials)
    assert credentials == {}


def test_model_provider_rejects_insecure_public_endpoint():
    with pytest.raises(ModelConfigurationError, match="HTTPS"):
        build_request_model(
            {
                "provider": "openai_compatible",
                "api_key": "secret",
                "base_url": "http://public.example.com/v1",
                "model": "demo",
            }
        )


def test_model_preflight_api_accepts_request_scoped_mock_without_exposing_key(monkeypatch):
    app_module = __import__("src.server.app", fromlist=["run_model_preflight"])
    captured: dict[str, object] = {}

    def fake_preflight(model, *, runtime_config=None):
        captured["model"] = model
        captured["runtime_config"] = runtime_config
        return {
            "status": "success",
            "provider": model,
            "configured": True,
            "reachable": True,
        }

    monkeypatch.setattr(app_module, "run_model_preflight", fake_preflight)
    with TestClient(app) as client:
        response = client.post(
            "/api/ecommerce/preflight",
            json={
                "provider": "model",
                "model": "deepseek",
                "byok": {"model_api_key": "preflight-secret"},
            },
        )

    assert response.status_code == 200
    assert captured["model"] == "deepseek"
    assert captured["runtime_config"] == {"api_key": "preflight-secret"}
    assert "preflight-secret" not in response.text


def test_model_preflight_accepts_default_none_data_source():
    with TestClient(app) as client:
        response = client.post(
            "/api/ecommerce/preflight",
            json={"provider": "model", "model": "mock", "data_source": "none"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_research_response_and_history_do_not_include_byok_values():
    workspace_id = "b4-byok-isolation"
    secrets = {"model_api_key": "model-secret", "search_api_key": "search-secret", "data_api_key": "data-secret"}
    with TestClient(app) as client:
        response = client.post(
            "/api/ecommerce/research",
            headers={"X-Workspace-Id": workspace_id},
            json={"mode": "mock", "model": "mock", "byok": secrets},
        )
        assert response.status_code == 200
        history = client.get(
            "/api/ecommerce/history",
            headers={"X-Workspace-Id": workspace_id},
        )

    combined = response.text + history.text
    for secret in secrets.values():
        assert secret not in combined


def test_request_model_factory_builds_deepseek_without_network(monkeypatch):
    calls: dict[str, object] = {}

    class FakeChatDeepSeek:
        def __init__(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr("src.ecommerce.model_provider.ChatDeepSeek", FakeChatDeepSeek)
    client = build_request_model(
        {
            "provider": "deepseek",
            "api_key": "secret",
            "base_url": "https://api.example.com",
            "model": "deepseek-chat",
        }
    )
    assert isinstance(client, FakeChatDeepSeek)
    assert calls["api_key"] == "secret"
    assert calls["api_base"] == "https://api.example.com"
