"""Secret-safe capability registry for the e-commerce workspace."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.config import load_yaml_config
from src.llms.llm import get_configured_llm_models


_DEEPSEEK_PLATFORMS = {"deepseek", "deepseek_api", "deepseek-api"}
_SEARCH_PROVIDER_ALIASES = {
    "searx": "searxng",
    "brave_search": "brave",
    "custom": "custom_http_json",
    "http_json": "custom_http_json",
}


def _config_path() -> str:
    return str((Path(__file__).parent.parent.parent / "conf.yaml").resolve())


def _role_env(role: str) -> dict[str, str]:
    prefix = f"{role.upper()}_MODEL__"
    return {
        name[len(prefix) :].lower(): value
        for name, value in os.environ.items()
        if name.startswith(prefix) and value
    }


def _basic_model_config() -> dict[str, Any]:
    try:
        config = load_yaml_config(_config_path())
    except Exception:  # noqa: BLE001 - capability reporting must never break health
        config = {}
    yaml_config = config.get("BASIC_MODEL", {})
    if not isinstance(yaml_config, dict):
        yaml_config = {}
    merged = {**yaml_config, **_role_env("BASIC")}
    platform = str(merged.get("platform", "")).lower()
    # A clean checkout does not contain the developer's private ``conf.yaml``.
    # The provider-level DeepSeek variables are already the documented
    # request-time configuration, so use them as a complete DeepSeek preset
    # when no role-level platform was supplied.
    if not platform and os.getenv("DEEPSEEK_API_KEY"):
        merged["platform"] = "deepseek"
        platform = "deepseek"
    if platform in _DEEPSEEK_PLATFORMS:
        provider_env = {
            "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", ""),
            "model": os.getenv("DEEPSEEK_MODEL", ""),
        }
        merged = {**merged, **{key: value for key, value in provider_env.items() if value}}
    return merged


def _key_configured(config: dict[str, Any], *env_names: str) -> bool:
    return bool(config.get("api_key") or any(os.getenv(name) for name in env_names))


def _model_provider(config: dict[str, Any]) -> str:
    platform = str(config.get("platform", "")).lower()
    if platform in _DEEPSEEK_PLATFORMS:
        return "deepseek"
    if platform:
        return platform
    base_url = str(config.get("base_url", "")).lower()
    if "ollama" in base_url:
        return "ollama"
    if base_url:
        return "openai_compatible"
    return "unconfigured"


def build_ecommerce_capabilities() -> dict[str, Any]:
    """Return selectable capabilities without exposing secrets or raw config."""

    basic_config = _basic_model_config()
    configured_models = get_configured_llm_models()
    basic_model = str(basic_config.get("model", ""))
    basic_provider = _model_provider(basic_config)
    deepseek_configured = basic_provider == "deepseek" and _key_configured(
        basic_config, "DEEPSEEK_API_KEY", "BASIC_MODEL__API_KEY"
    )
    openai_compatible_configured = basic_provider == "openai_compatible" and _key_configured(
        basic_config, "BASIC_MODEL__API_KEY"
    )
    ollama_configured = basic_provider == "ollama" or "ollama" in str(
        basic_config.get("base_url", "")
    ).lower()
    selected_search_provider = str(os.getenv("SEARCH_API", "tavily")).lower()
    selected_search_provider = _SEARCH_PROVIDER_ALIASES.get(
        selected_search_provider, selected_search_provider
    )
    search_configured = {
        "tavily": bool(os.getenv("TAVILY_API_KEY")),
        "searxng": bool(
            os.getenv("SEARXNG_URL")
            or os.getenv("SEARXNG_HOST")
            or os.getenv("SEARX_HOST")
        ),
        "brave": bool(os.getenv("BRAVE_SEARCH_API_KEY")),
        "serper": bool(os.getenv("SERPER_API_KEY")),
        "custom_http_json": bool(os.getenv("SEARCH_API_URL") and os.getenv("SEARCH_API_KEY")),
    }
    # Keep the old public variable name for callers that still display Tavily
    # specifically, while the new registry reports all provider states.
    tavily_configured = search_configured["tavily"]
    infoquest_configured = bool(os.getenv("INFOQUEST_API_KEY"))

    models: list[dict[str, Any]] = [
        {
            "id": "mock",
            "label": "结构化 Mock",
            "provider": "mock",
            "model": "mock",
            "configured": True,
            "reachable": True,
            "request_supported": True,
            "preflight_required": False,
            "mode": "offline",
        },
        {
            "id": "deepseek",
            "label": "DeepSeek",
            "provider": "deepseek",
            "model": basic_model if basic_provider == "deepseek" else "deepseek-v4-flash",
            "configured": deepseek_configured,
            "reachable": None,
            "request_supported": True,
            "preflight_required": True,
            "mode": "live",
            "reason": None
            if deepseek_configured
            else "需要 BASIC_MODEL 使用 DeepSeek 平台并配置 DEEPSEEK_API_KEY",
        },
        {
            "id": "openai_compatible",
            "label": "OpenAI-Compatible",
            "provider": "openai_compatible",
            "model": basic_model if basic_provider == "openai_compatible" else "gpt-4o-mini",
            "configured": openai_compatible_configured,
            "reachable": None,
            "request_supported": True,
            "preflight_required": True,
            "mode": "live",
            "reason": None
            if openai_compatible_configured
            else "需要配置 BASIC_MODEL 的 Endpoint、模型和 API Key",
        },
        {
            "id": "ollama",
            "label": "Ollama 本地模型",
            "provider": "ollama",
            "model": basic_model if basic_provider == "ollama" else "qwen2.5:7b",
            "configured": ollama_configured,
            "reachable": None,
            "request_supported": True,
            "preflight_required": True,
            "mode": "local",
            "reason": None if ollama_configured else "可在页面中填写本地 Ollama Endpoint",
        },
    ]

    # These are editable, secret-free templates for the web BYOK form.  They
    # do not claim that a provider is configured or reachable on this server;
    # users still need to provide their own key and can override endpoint and
    # model before enabling the request-scoped configuration.
    model_presets = [
        {
            "id": "mock",
            "label": "结构化 Mock",
            "provider": "mock",
            "base_url": "",
            "model": "mock",
            "requires_api_key": False,
            "description": "离线演示，不调用外部模型服务",
        },
        {
            "id": "deepseek",
            "label": "DeepSeek",
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "requires_api_key": True,
            "description": "DeepSeek OpenAI-compatible 接口",
        },
        {
            "id": "openai",
            "label": "OpenAI",
            "provider": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "requires_api_key": True,
            "description": "OpenAI 官方兼容接口模板",
        },
        {
            "id": "qwen",
            "label": "通义千问 / DashScope",
            "provider": "openai_compatible",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-plus",
            "requires_api_key": True,
            "description": "DashScope OpenAI-compatible 接口模板",
        },
        {
            "id": "zhipu",
            "label": "智谱 GLM",
            "provider": "openai_compatible",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "model": "glm-4-flash",
            "requires_api_key": True,
            "description": "智谱开放平台兼容接口模板",
        },
        {
            "id": "moonshot",
            "label": "月之暗面 Kimi",
            "provider": "openai_compatible",
            "base_url": "https://api.moonshot.cn/v1",
            "model": "moonshot-v1-8k",
            "requires_api_key": True,
            "description": "Kimi OpenAI-compatible 接口模板",
        },
        {
            "id": "siliconflow",
            "label": "SiliconFlow",
            "provider": "openai_compatible",
            "base_url": "https://api.siliconflow.cn/v1",
            "model": "deepseek-ai/DeepSeek-V3",
            "requires_api_key": True,
            "description": "多模型聚合兼容接口模板",
        },
        {
            "id": "ollama",
            "label": "Ollama 本地模型",
            "provider": "ollama",
            "base_url": "http://localhost:11434/v1",
            "model": "qwen2.5:7b",
            "requires_api_key": False,
            "description": "本机 Ollama OpenAI-compatible 接口",
        },
        {
            "id": "custom",
            "label": "自定义 OpenAI-Compatible",
            "provider": "openai_compatible",
            "base_url": "",
            "model": "",
            "requires_api_key": True,
            "description": "填写任意兼容 Chat Completions 的服务",
        },
    ]

    # Surface configured models from the DeerFlow platform without pretending
    # that the ecommerce enhancer can already use every provider.
    for role, model_names in configured_models.items():
        for model_name in model_names:
            if role == "basic" and basic_provider == "deepseek" and model_name == basic_model:
                continue
            models.append(
                {
                    "id": f"configured:{role}:{model_name}",
                    "label": str(model_name),
                    "provider": basic_provider if role == "basic" else "configured",
                    "model": str(model_name),
                    "configured": True,
                    "reachable": None,
                    "request_supported": False,
                    "preflight_required": True,
                    "mode": "platform_configured",
                    "reason": "已在 DeerFlow 配置中发现；电商报告增强器将在后续阶段开放此模型",
                }
            )

    return {
        "version": "b4",
        "status": "ready"
        if deepseek_configured
        or openai_compatible_configured
        or ollama_configured
        or any(search_configured.values())
        or infoquest_configured
        else "offline_only",
        "active_search_provider": selected_search_provider,
        "selection_contract": {
            "data_modes": ["mock", "live"],
            "model_modes": ["mock", "deepseek", "openai_compatible", "ollama"],
            "data_sources": ["none", "infoquest"],
            "search_providers": [
                "tavily",
                "searxng",
                "brave",
                "serper",
                "custom_http_json",
            ],
            "fallback_is_explicit": True,
        },
        "search_providers": [
            {
                "id": "tavily",
                "label": "Tavily",
                "configured": tavily_configured,
                "reachable": None,
                "request_supported": True,
                "preflight_required": True,
                "mode": "live",
                "reason": None if tavily_configured else "需要配置 TAVILY_API_KEY",
            },
            {
                "id": "searxng",
                "label": "SearXNG",
                "configured": search_configured["searxng"],
                "reachable": None,
                "request_supported": True,
                "preflight_required": True,
                "mode": "live",
                "reason": None
                if search_configured["searxng"]
                else "需要配置 SEARXNG_URL/SEARXNG_HOST，或在本机启动 SearXNG",
            },
            {
                "id": "brave",
                "label": "Brave Search",
                "configured": search_configured["brave"],
                "reachable": None,
                "request_supported": True,
                "preflight_required": True,
                "mode": "live",
                "reason": None
                if search_configured["brave"]
                else "需要配置 BRAVE_SEARCH_API_KEY",
            },
            {
                "id": "serper",
                "label": "Serper",
                "configured": search_configured["serper"],
                "reachable": None,
                "request_supported": True,
                "preflight_required": True,
                "mode": "live",
                "reason": None
                if search_configured["serper"]
                else "需要配置 SERPER_API_KEY",
            },
            {
                "id": "custom_http_json",
                "label": "自定义 HTTP JSON",
                "configured": search_configured["custom_http_json"],
                "reachable": None,
                "request_supported": True,
                "preflight_required": True,
                "mode": "live",
                "reason": None
                if search_configured["custom_http_json"]
                else "需要同时配置 SEARCH_API_URL 和 SEARCH_API_KEY",
            },
        ],
        "data_sources": [
            {
                "id": "none",
                "label": "仅搜索摘要",
                "provider": "none",
                "configured": True,
                "reachable": True,
                "request_supported": True,
                "preflight_required": False,
                "mode": "search_summary",
            },
            {
                "id": "infoquest",
                "label": "InfoQuest 商品页增强",
                "provider": "infoquest",
                "configured": infoquest_configured,
                "reachable": None,
                "request_supported": True,
                "preflight_required": True,
                "mode": "authorized_page_enrichment",
                "reason": None
                if infoquest_configured
                else "需要配置 INFOQUEST_API_KEY；该接口不等于销量/库存/榜单 API",
            },
        ],
        "models": models,
        "model_presets": model_presets,
        "limits": {
            "search_timeout_seconds": 120,
            "search_retries": 3,
            "preflight_timeout_seconds": 30,
        },
    }

