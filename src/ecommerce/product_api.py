"""Safe, request-scoped connector for user-authorized product APIs.

The connector is deliberately a preview/normalization boundary. It accepts a
user's endpoint and credential for one request, never persists either value,
does not follow redirects, and returns only normalized product fields. It does
not claim that an API response proves sales, margin, inventory, or compliance.
"""

from __future__ import annotations

import ipaddress
import json
import re
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from src.ecommerce.authorized_data import (
    AuthorizedDataSource,
    AuthorizedProductRecord,
    validate_authorized_dataset,
)


_ALLOWED_AUTH_HEADERS = {"authorization", "x-api-key", "x-auth-token"}
_PATH_PART = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class ProductApiFieldMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="title", min_length=1, max_length=120)
    price: str = Field(default="price", min_length=1, max_length=120)
    url: str = Field(default="url", min_length=1, max_length=120)
    sku: str = Field(default="sku", min_length=1, max_length=120)

    @field_validator("title", "price", "url", "sku")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not _valid_path(value):
            raise ValueError("字段映射必须是点分隔的 JSON 字段路径")
        return value


class ProductApiConfig(BaseModel):
    """Strict product API configuration; API key remains request-scoped."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(default="user-product-api", min_length=1, max_length=120)
    provider: str = Field(default="用户商品 API", min_length=1, max_length=120)
    endpoint: str = Field(min_length=8, max_length=500)
    method: Literal["GET", "POST"] = "GET"
    auth_mode: Literal["bearer", "header", "none"] = "bearer"
    api_key: SecretStr | None = Field(default=None, max_length=500)
    auth_header_name: str = Field(default="Authorization", min_length=1, max_length=80)
    query_param: str = Field(default="q", min_length=1, max_length=50)
    category: str = Field(default="可折叠露营桌", min_length=1, max_length=120)
    response_path: str = Field(default="data", max_length=120)
    field_map: ProductApiFieldMap = Field(default_factory=ProductApiFieldMap)
    max_results: int = Field(default=10, ge=1, le=50)
    timeout: float = Field(default=15.0, gt=0, le=30)
    authorization_status: Literal["verified", "user_declared", "blocked"] = "user_declared"
    authorization_reference: str = Field(default="user-declared", min_length=1, max_length=500)
    terms_url: str | None = Field(default=None, max_length=500)
    allowed_use: str = Field(default="用户声明已获授权的商品数据读取", min_length=1, max_length=500)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        parsed = _parse_safe_endpoint(value)
        if parsed is None:
            raise ValueError("商品 API Endpoint 必须使用 HTTPS；本地演示仅允许 localhost/127.0.0.1")
        return value.strip()

    @field_validator("auth_header_name")
    @classmethod
    def validate_auth_header_name(cls, value: str) -> str:
        normalized = value.strip()
        if normalized.lower() not in _ALLOWED_AUTH_HEADERS and not (
            normalized.lower().startswith("x-") and normalized.replace("-", "").isalnum()
        ):
            raise ValueError("仅允许 Authorization、X-API-Key、X-Auth-Token 或 X-* Header")
        if normalized.lower() in {"cookie", "host", "proxy-authorization"}:
            raise ValueError("禁止使用敏感或连接级 Header")
        return normalized

    @field_validator("query_param")
    @classmethod
    def validate_query_param(cls, value: str) -> str:
        if not _PATH_PART.fullmatch(value.strip()):
            raise ValueError("查询参数名格式不合法")
        return value.strip()

    @field_validator("response_path")
    @classmethod
    def validate_response_path(cls, value: str) -> str:
        value = value.strip()
        if value and not _valid_path(value):
            raise ValueError("响应路径必须是点分隔的 JSON 字段路径")
        return value


def _valid_path(value: str) -> bool:
    return bool(value) and all(_PATH_PART.fullmatch(part) for part in value.split("."))


def _parse_safe_endpoint(value: str):
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        return None
    if parsed.username or parsed.password or parsed.fragment:
        return None
    host = parsed.hostname.lower()
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if host in local_hosts:
        if parsed.scheme != "http":
            return None
    elif parsed.scheme != "https":
        return None
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        address = None
    if address is not None and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
    ):
        # Plain HTTP is permitted only for an explicitly local demo server;
        # HTTPS to a loopback/private address is still rejected to avoid
        # turning this connector into an internal network bridge.
        if not (
            parsed.scheme == "http"
            and host in {"127.0.0.1", "::1"}
        ):
            return None
    return parsed


def _safe_endpoint(value: str) -> str:
    parsed = _parse_safe_endpoint(value)
    if parsed is None:
        raise ValueError("商品 API Endpoint 不安全或格式不受支持")
    # Query parameters are allowed for non-secret routing, but credentials are
    # always sent in a header and never copied into the URL.
    return parsed._replace(fragment="").geturl()


def _extract_path(payload: Any, path: str) -> Any:
    if not path:
        return payload
    current = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return None
    text = str(value).strip()
    return text[:500] if text else None


def _as_price(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value >= 0 else None
    text = str(value).replace(",", "").replace("¥", "").replace("￥", "").strip()
    try:
        number = float(text)
    except ValueError:
        return None
    return number if number >= 0 else None


def _normalize_products(payload: Any, config: ProductApiConfig, owner_id: str) -> list[AuthorizedProductRecord]:
    selected = _extract_path(payload, config.response_path)
    if selected is None and isinstance(payload, list):
        selected = payload
    if isinstance(selected, dict):
        selected = selected.get("items") or selected.get("products") or selected.get("results")
    if not isinstance(selected, list):
        return []

    records: list[AuthorizedProductRecord] = []
    now = datetime.now(timezone.utc)
    for index, item in enumerate(selected[: config.max_results]):
        if not isinstance(item, dict):
            continue
        title = _as_text(_extract_path(item, config.field_map.title))
        if not title:
            continue
        sku = _as_text(_extract_path(item, config.field_map.sku))
        product_url = _as_text(_extract_path(item, config.field_map.url))
        if product_url and not product_url.startswith(("https://", "http://")):
            product_url = None
        record_id = sku or f"api-row-{index + 1}"
        records.append(
            AuthorizedProductRecord(
                record_id=record_id[:120],
                source_id=config.source_id,
                sku_id=sku,
                title=title,
                product_url=product_url,
                price=_as_price(_extract_path(item, config.field_map.price)),
                retrieved_at=now,
                fields={"owner_id": owner_id, "source": config.provider},
            )
        )
    return records


def _read_response_json(response: httpx.Response) -> Any:
    content = response.content
    if len(content) > _MAX_RESPONSE_BYTES:
        raise ValueError("商品 API 返回体超过 2 MB 限制")
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("商品 API 未返回合法 JSON") from exc


def probe_product_api(
    config: ProductApiConfig,
    *,
    owner_id: str,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Call a user endpoint and return a secret-free normalized preview."""

    endpoint = _safe_endpoint(config.endpoint)
    if config.auth_mode != "none" and not config.api_key:
        return {
            "status": "blocked",
            "error_code": "missing_api_key",
            "message": "当前认证方式需要 API Key；Key 只在本次请求中使用。",
            "provider": config.provider,
            "endpoint": endpoint,
            "configured": False,
            "reachable": False,
            "commercial_decision_ready": False,
        }

    headers = {"Accept": "application/json"}
    if config.api_key:
        key = config.api_key.get_secret_value()
        if config.auth_mode == "bearer":
            headers["Authorization"] = f"Bearer {key}"
        elif config.auth_mode == "header":
            headers[config.auth_header_name] = key
    request_kwargs: dict[str, Any] = {"headers": headers}
    if config.method == "GET":
        request_kwargs["params"] = {config.query_param: config.category}
    else:
        request_kwargs["json"] = {"query": config.category, "category": config.category}

    owns_client = client is None
    http_client = client or httpx.Client(follow_redirects=False, timeout=config.timeout)
    try:
        response = http_client.request(config.method, endpoint, **request_kwargs)
        if response.status_code >= 400:
            return {
                "status": "error",
                "error_code": f"http_{response.status_code}",
                "message": "商品 API 返回错误状态，请检查 Endpoint、Key 和权限。",
                "provider": config.provider,
                "endpoint": endpoint,
                "configured": True,
                "reachable": True,
                "commercial_decision_ready": False,
            }
        payload = _read_response_json(response)
        records = _normalize_products(payload, config, owner_id)
        source = AuthorizedDataSource(
            source_id=config.source_id,
            provider=config.provider,
            source_kind="marketplace_api",
            authorization_status=config.authorization_status,
            authorization_reference=config.authorization_reference,
            terms_url=config.terms_url,
            allowed_use=config.allowed_use,
            owner_id=owner_id,
        )
        validation = validate_authorized_dataset(source, records)
        return {
            "status": "success" if records else "error",
            "error_code": None if records else "empty_products",
            "message": "商品 API 连接成功，已读取可映射的商品样品。" if records else "商品 API 连接成功，但未找到可映射的商品数组。",
            "provider": config.provider,
            "endpoint": endpoint,
            "configured": True,
            "reachable": True,
            "result_count": len(records),
            "products": [record.model_dump(mode="json") for record in records],
            "data_validation": validation,
            "commercial_decision_ready": False,
            "claims_boundary": "API 样品仅作为候选数据；销量、成本、库存和合规仍需独立核验。",
        }
    except (httpx.HTTPError, ValueError, TypeError):
        return {
            "status": "error",
            "error_code": "connection_or_payload_error",
            "message": "商品 API 连接或返回结构失败，请检查网络、Endpoint、认证和字段映射。",
            "provider": config.provider,
            "endpoint": endpoint,
            "configured": True,
            "reachable": False,
            "commercial_decision_ready": False,
        }
    finally:
        if owns_client:
            http_client.close()
