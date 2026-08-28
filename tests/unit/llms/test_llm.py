# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import pytest

from src.llms import llm


class DummyChatOpenAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def invoke(self, msg):
        return f"Echo: {msg}"


class DummyChatDeepSeek(DummyChatOpenAI):
    pass


@pytest.fixture(autouse=True)
def patch_chat_openai(monkeypatch):
    monkeypatch.setattr(llm, "ChatOpenAI", DummyChatOpenAI)
    monkeypatch.setattr(llm, "ChatDeepSeek", DummyChatDeepSeek)


@pytest.fixture
def dummy_conf():
    return {
        "BASIC_MODEL": {"api_key": "test_key", "base_url": "http://test"},
        "REASONING_MODEL": {"api_key": "reason_key"},
        "VISION_MODEL": {"api_key": "vision_key"},
    }


def test_get_env_llm_conf(monkeypatch):
    # Clear any existing environment variables that might interfere
    monkeypatch.delenv("BASIC_MODEL__API_KEY", raising=False)
    monkeypatch.delenv("BASIC_MODEL__BASE_URL", raising=False)
    monkeypatch.delenv("BASIC_MODEL__MODEL", raising=False)

    monkeypatch.setenv("BASIC_MODEL__API_KEY", "env_key")
    monkeypatch.setenv("BASIC_MODEL__BASE_URL", "http://env")
    conf = llm._get_env_llm_conf("basic")
    assert conf["api_key"] == "env_key"
    assert conf["base_url"] == "http://env"


def test_create_llm_use_conf_merges_env(monkeypatch, dummy_conf):
    # Clear any existing environment variables that might interfere
    monkeypatch.delenv("BASIC_MODEL__BASE_URL", raising=False)
    monkeypatch.delenv("BASIC_MODEL__MODEL", raising=False)
    monkeypatch.setenv("BASIC_MODEL__API_KEY", "env_key")
    result = llm._create_llm_use_conf("basic", dummy_conf)
    assert isinstance(result, DummyChatOpenAI)
    assert result.kwargs["api_key"] == "env_key"
    assert result.kwargs["base_url"] == "http://test"


def test_create_llm_use_conf_invalid_type(monkeypatch, dummy_conf):
    # Clear any existing environment variables that might interfere
    monkeypatch.delenv("BASIC_MODEL__API_KEY", raising=False)
    monkeypatch.delenv("BASIC_MODEL__BASE_URL", raising=False)
    monkeypatch.delenv("BASIC_MODEL__MODEL", raising=False)

    with pytest.raises(ValueError):
        llm._create_llm_use_conf("unknown", dummy_conf)


def test_create_llm_use_conf_empty_conf(monkeypatch):
    # Clear any existing environment variables that might interfere
    monkeypatch.delenv("BASIC_MODEL__API_KEY", raising=False)
    monkeypatch.delenv("BASIC_MODEL__BASE_URL", raising=False)
    monkeypatch.delenv("BASIC_MODEL__MODEL", raising=False)

    with pytest.raises(ValueError):
        llm._create_llm_use_conf("basic", {})


def test_get_llm_by_type_caches(monkeypatch, dummy_conf):
    called = {}

    def fake_load_yaml_config(path):
        called["called"] = True
        return dummy_conf

    monkeypatch.setattr(llm, "load_yaml_config", fake_load_yaml_config)
    llm._llm_cache.clear()
    inst1 = llm.get_llm_by_type("basic")
    inst2 = llm.get_llm_by_type("basic")
    assert inst1 is inst2
    assert called["called"]


def test_create_llm_filters_unexpected_keys(monkeypatch, caplog):
    """Test that unexpected configuration keys like SEARCH_ENGINE are filtered out (Issue #411)."""
    import logging
    
    # Clear any existing environment variables that might interfere
    monkeypatch.delenv("BASIC_MODEL__API_KEY", raising=False)
    monkeypatch.delenv("BASIC_MODEL__BASE_URL", raising=False)
    monkeypatch.delenv("BASIC_MODEL__MODEL", raising=False)
    
    # Config with unexpected keys that should be filtered
    conf_with_unexpected_keys = {
        "BASIC_MODEL": {
            "api_key": "test_key",
            "base_url": "http://test",
            "model": "gpt-4",
            "SEARCH_ENGINE": {"include_domains": ["example.com"]},  # Should be filtered
            "engine": "tavily",  # Should be filtered
        }
    }
    
    with caplog.at_level(logging.WARNING):
        result = llm._create_llm_use_conf("basic", conf_with_unexpected_keys)
    
    # Verify the LLM was created
    assert isinstance(result, DummyChatOpenAI)
    
    # Verify unexpected keys were not passed to the LLM
    assert "SEARCH_ENGINE" not in result.kwargs
    assert "engine" not in result.kwargs
    
    # Verify valid keys were passed
    assert result.kwargs["api_key"] == "test_key"
    assert result.kwargs["base_url"] == "http://test"
    assert result.kwargs["model"] == "gpt-4"
    
    # Verify warnings were logged
    assert any("SEARCH_ENGINE" in record.message for record in caplog.records)
    assert any("engine" in record.message for record in caplog.records)


def test_create_deepseek_platform_uses_native_client(monkeypatch):
    monkeypatch.delenv("BASIC_MODEL__API_KEY", raising=False)
    monkeypatch.delenv("BASIC_MODEL__BASE_URL", raising=False)
    monkeypatch.delenv("BASIC_MODEL__MODEL", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "provider_key")

    result = llm._create_llm_use_conf(
        "basic",
        {
            "BASIC_MODEL": {
                "platform": "deepseek",
                "model": "deepseek-v4-flash",
            }
        },
    )

    assert isinstance(result, DummyChatDeepSeek)
    assert result.kwargs["api_key"] == "provider_key"
    assert result.kwargs["api_base"] == "https://api.deepseek.com"
    assert result.kwargs["model"] == "deepseek-v4-flash"
    assert "platform" not in result.kwargs


def test_deepseek_rejects_non_ascii_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("BASIC_MODEL__API_KEY", raising=False)
    with pytest.raises(ValueError, match="ASCII"):
        llm._create_llm_use_conf(
            "basic",
            {
                "BASIC_MODEL": {
                    "platform": "deepseek",
                    "model": "deepseek-v4-flash",
                    "api_key": "你的真实DeepSeek_API_Key",
                }
            },
        )


def test_role_specific_deepseek_env_overrides_provider_alias(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "provider_key")
    monkeypatch.setenv("BASIC_MODEL__API_KEY", "role_key")
    result = llm._create_llm_use_conf(
        "basic",
        {
            "BASIC_MODEL": {
                "platform": "deepseek",
                "model": "deepseek-v4-flash",
            }
        },
    )
    assert result.kwargs["api_key"] == "role_key"
