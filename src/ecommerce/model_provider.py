"""Safe construction of request-scoped e-commerce model clients."""

from __future__ import annotations

from ipaddress import ip_address
from typing import Any
from urllib.parse import urlsplit

from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI


class ModelConfigurationError(ValueError):
    """Raised when a request-scoped model configuration is incomplete."""


def _validate_base_url(value: str, *, allow_default: bool = False) -> str:
    url = value.strip()
    if len(url) > 500:
        raise ModelConfigurationError("模型 Endpoint 长度不能超过 500 个字符。")
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.netloc:
        return url.rstrip("/")
    if parts.scheme != "http" or not parts.hostname or not parts.netloc:
        raise ModelConfigurationError("模型 Endpoint 必须是 HTTPS，或使用本机 HTTP 服务。")
    hostname = parts.hostname.lower()
    local_hosts = {"localhost", "host.docker.internal"}
    is_local_ip = False
    try:
        is_local_ip = ip_address(hostname).is_loopback or ip_address(hostname).is_private
    except ValueError:
        pass
    if hostname not in local_hosts and not is_local_ip:
        raise ModelConfigurationError("非 HTTPS 的模型 Endpoint 仅允许本机或内网服务。")
    return url.rstrip("/")


def build_request_model(config: dict[str, Any]) -> Any:
    """Build a model client from credentials that exist only for one request."""

    provider = str(config.get("provider") or "deepseek").strip().lower()
    api_key = config.get("api_key")
    base_url = str(config.get("base_url") or "").strip()
    model = str(config.get("model") or "").strip()
    if api_key is not None and not isinstance(api_key, str):
        raise ModelConfigurationError("模型 API Key 格式无效。")
    if api_key == "":
        api_key = None

    if provider == "deepseek":
        if not api_key:
            raise ModelConfigurationError("DeepSeek 需要填写本次请求的 API Key，或使用服务端配置。")
        return ChatDeepSeek(
            model=model or "deepseek-chat",
            api_key=api_key,
            api_base=_validate_base_url(base_url or "https://api.deepseek.com"),
            max_retries=1,
        )

    if provider == "openai_compatible":
        if not base_url:
            raise ModelConfigurationError("OpenAI-compatible 模型需要填写 Endpoint。")
        if not api_key:
            raise ModelConfigurationError("OpenAI-compatible 模型需要填写本次请求的 API Key。")
        return ChatOpenAI(
            model=model or "gpt-4o-mini",
            api_key=api_key,
            base_url=_validate_base_url(base_url),
            max_retries=1,
        )

    if provider == "ollama":
        return ChatOpenAI(
            model=model or "qwen2.5:7b",
            api_key=api_key or "ollama",
            base_url=_validate_base_url(base_url or "http://localhost:11434/v1"),
            max_retries=0,
        )

    raise ModelConfigurationError(
        "不支持的模型供应商。可选值为 deepseek、openai_compatible 或 ollama。"
    )
