"""Secret-safe preflight for the configured basic model."""

from __future__ import annotations

import time
from typing import Any

from .capabilities import build_ecommerce_capabilities


def _content_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                chunks.append(item["text"])
        return " ".join(chunks)
    return str(content)


def _usage(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage_metadata", None) or {}
    metadata = getattr(response, "response_metadata", None) or {}
    provider_usage = metadata.get("token_usage") or metadata.get("usage") or {}
    input_tokens = usage.get("input_tokens") or provider_usage.get("prompt_tokens") or 0
    output_tokens = usage.get("output_tokens") or provider_usage.get("completion_tokens") or 0
    total_tokens = usage.get("total_tokens") or provider_usage.get("total_tokens") or input_tokens + output_tokens
    return {
        "model": str(metadata.get("model_name") or metadata.get("model") or ""),
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "total_tokens": int(total_tokens),
        "usage_available": bool(usage or provider_usage),
    }


def _error_result(
    *,
    model_id: str,
    error_code: str,
    message: str,
    configured: bool,
    provider: str = "deepseek",
    model: str = "",
    started: float,
) -> dict[str, Any]:
    return {
        "status": "error",
        "provider": provider,
        "model": model,
        "model_id": model_id,
        "configured": configured,
        "reachable": False,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "error_code": error_code,
        "message": message,
        "usage": {"usage_available": False},
    }


def run_model_preflight(
    model_id: str = "deepseek",
    *,
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Perform a minimal model call, never returning credentials or raw errors."""

    started = time.perf_counter()
    if model_id == "mock":
        return {
            "status": "success",
            "provider": "mock",
            "model": "mock",
            "model_id": "mock",
            "configured": True,
            "reachable": True,
            "latency_ms": 0.0,
            "error_code": None,
            "message": "Mock 模型无需外部连接。",
            "usage": {"usage_available": False},
        }
    if model_id not in {"deepseek", "openai_compatible", "ollama"}:
        return _error_result(
            model_id=model_id,
            error_code="unsupported_model",
            message="当前电商预检仅支持 mock、deepseek、openai_compatible 或 ollama。",
            configured=False,
            provider="unknown",
            started=started,
        )

    capability = next(
        (
            item
            for item in build_ecommerce_capabilities()["models"]
            if item["id"] == model_id
        ),
        {"id": model_id, "model": ""},
    )
    if runtime_config:
        configured = bool(runtime_config.get("api_key")) or model_id == "ollama"
    else:
        configured = bool(capability.get("configured"))
    if not configured:
        return _error_result(
            model_id=model_id,
            error_code="config_error",
            message=str(capability.get("reason") or "DeepSeek 配置不完整。"),
            configured=False,
            model=str(capability.get("model", "")),
            started=started,
        )

    try:
        if runtime_config:
            from .model_provider import build_request_model

            llm = build_request_model({"provider": model_id, **runtime_config})
        else:
            from src.llms.llm import get_llm_by_type

            llm = get_llm_by_type("basic")
        provider_name = type(llm).__name__.lower()
        if not runtime_config and model_id == "deepseek" and "deepseek" not in provider_name:
            return _error_result(
                model_id=model_id,
                error_code="config_error",
                message="服务端 basic 客户端不是 DeepSeek。",
                configured=True,
                provider=type(llm).__name__,
                model=str(getattr(llm, "model_name", "") or getattr(llm, "model", "")),
                started=started,
            )
        response = llm.invoke(
            [
                ("system", "你是连接预检器。只回复 OK，不要输出其它内容。"),
                ("user", "请确认模型连接正常。"),
            ]
        )
        text = _content_text(response).strip()
        if not text:
            return _error_result(
                model_id=model_id,
                error_code="empty_response",
                message="模型连接成功但没有返回可读内容。",
                configured=True,
                provider=type(llm).__name__,
                model=str(getattr(llm, "model_name", "") or getattr(llm, "model", "")),
                started=started,
            )
        usage = _usage(response)
        return {
            "status": "success",
            "provider": model_id,
            "model": usage.get("model") or str(capability.get("model", "")),
            "model_id": model_id,
            "configured": True,
            "reachable": True,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error_code": None,
            "message": f"{model_id} 预检调用成功。",
            "usage": usage,
        }
    except Exception as exc:  # noqa: BLE001 - convert external errors to stable diagnostics
        from .orchestration import classify_model_error

        return _error_result(
            model_id=model_id,
            error_code=classify_model_error(exc),
            message="DeepSeek 预检失败，请检查配置、网络或服务额度。",
            configured=True,
            model=str(capability.get("model", "")),
            started=started,
        )
