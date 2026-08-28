"""Allowlisted adapters for user-owned authorized data sources."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class AuthorizedAdapterSpec:
    adapter_id: str
    label: str
    source_kind: Literal["marketplace_api", "reader", "owned_file", "internal_db"]
    requires_user_credentials: bool
    supports_preflight: bool
    claims_boundary: str


AUTHORIZED_ADAPTERS: tuple[AuthorizedAdapterSpec, ...] = (
    AuthorizedAdapterSpec(
        adapter_id="user_jsonl",
        label="用户授权 JSONL/CSV",
        source_kind="owned_file",
        requires_user_credentials=False,
        supports_preflight=False,
        claims_boundary="用户自有文件，仍需逐条核验",
    ),
    AuthorizedAdapterSpec(
        adapter_id="infoquest_reader",
        label="InfoQuest Reader",
        source_kind="reader",
        requires_user_credentials=True,
        supports_preflight=True,
        claims_boundary="页面内容增强，不代表销量、库存或成本",
    ),
    AuthorizedAdapterSpec(
        adapter_id="marketplace_api",
        label="用户授权商品 API（JSON）",
        source_kind="marketplace_api",
        requires_user_credentials=True,
        supports_preflight=True,
        claims_boundary="API 返回字段仍需来源、时效和合规核验",
    ),
    AuthorizedAdapterSpec(
        adapter_id="internal_catalog",
        label="用户内部商品库",
        source_kind="internal_db",
        requires_user_credentials=True,
        supports_preflight=True,
        claims_boundary="内部数据只在所属租户内使用",
    ),
)


def list_authorized_adapters() -> list[dict[str, object]]:
    return [asdict(item) for item in AUTHORIZED_ADAPTERS]


def get_authorized_adapter(adapter_id: str) -> AuthorizedAdapterSpec | None:
    return next((item for item in AUTHORIZED_ADAPTERS if item.adapter_id == adapter_id), None)
