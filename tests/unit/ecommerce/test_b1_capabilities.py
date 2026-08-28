from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.ecommerce.capabilities import build_ecommerce_capabilities
from src.ecommerce.model_preflight import run_model_preflight
from src.server.app import app


def test_capabilities_are_secret_safe_and_keep_mock_available(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("BASIC_MODEL__API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.delenv("SEARXNG_HOST", raising=False)
    monkeypatch.delenv("SEARX_HOST", raising=False)
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("SEARCH_API_URL", raising=False)
    monkeypatch.delenv("SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("INFOQUEST_API_KEY", raising=False)

    payload = build_ecommerce_capabilities()
    assert payload["status"] == "offline_only"
    assert payload["models"][0]["id"] == "mock"
    assert payload["models"][0]["request_supported"] is True
    assert payload["models"][1]["configured"] is False
    assert {item["id"] for item in payload["model_presets"]} >= {
        "mock",
        "deepseek",
        "openai",
        "qwen",
        "zhipu",
        "moonshot",
        "siliconflow",
        "ollama",
        "custom",
    }
    assert all("model_api_key" not in str(item) for item in payload["model_presets"])
    assert "test-key" not in str(payload)
    assert "tvly-" not in str(payload)


def test_mock_model_preflight_is_offline():
    result = run_model_preflight("mock")
    assert result["status"] == "success"
    assert result["reachable"] is True
    assert result["usage"]["usage_available"] is False


def test_deepseek_model_preflight_uses_real_client_contract(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    class ChatDeepSeekFakeLLM:
        model_name = "deepseek-test"

        def invoke(self, _messages):
            return SimpleNamespace(
                content="OK",
                usage_metadata={"input_tokens": 2, "output_tokens": 1, "total_tokens": 3},
                response_metadata={"model_name": "deepseek-test"},
            )

    monkeypatch.setattr("src.llms.llm.get_llm_by_type", lambda _role: ChatDeepSeekFakeLLM())
    result = run_model_preflight("deepseek")
    assert result["status"] == "success"
    assert result["provider"] == "deepseek"
    assert result["usage"]["total_tokens"] == 3


def test_capabilities_and_mock_preflight_api():
    with TestClient(app) as client:
        capabilities = client.get("/api/ecommerce/capabilities")
        assert capabilities.status_code == 200
        body = capabilities.json()
        assert body["status"] == "success"
        assert {item["id"] for item in body["capabilities"]["models"]} >= {
            "mock",
            "deepseek",
        }

        preflight = client.post(
            "/api/ecommerce/preflight",
            json={"provider": "model", "model": "mock", "data_source": "none"},
        )
        assert preflight.status_code == 200
        assert preflight.json()["status"] == "success"
        assert preflight.json()["checks"]["model"]["provider"] == "mock"
