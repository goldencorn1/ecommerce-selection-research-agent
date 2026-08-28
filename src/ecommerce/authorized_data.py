"""Contracts and deterministic checks for user-supplied authorized data.

The validator never fetches a marketplace and never promotes page text to
commercial truth. It checks that records have a declared source, retrieval
time, authorization reference and basic product fields before they enter a
later verification workflow.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuthorizedDataSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, max_length=120)
    provider: str = Field(min_length=1, max_length=120)
    source_kind: Literal["marketplace_api", "reader", "owned_file", "internal_db"]
    authorization_status: Literal["verified", "user_declared", "blocked"]
    authorization_reference: str = Field(min_length=1, max_length=500)
    terms_url: str | None = Field(default=None, max_length=500)
    allowed_use: str = Field(min_length=1, max_length=500)
    owner_id: str = Field(min_length=1, max_length=80)

    @field_validator("terms_url")
    @classmethod
    def validate_terms_url(cls, value: str | None) -> str | None:
        if value is not None and urlparse(value).scheme not in {"http", "https"}:
            raise ValueError("terms_url must use http or https")
        return value


class AuthorizedProductRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(min_length=1, max_length=120)
    source_id: str = Field(min_length=1, max_length=120)
    sku_id: str | None = Field(default=None, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    product_url: str | None = Field(default=None, max_length=500)
    price: float | None = Field(default=None, ge=0)
    currency: str = Field(default="CNY", min_length=3, max_length=8)
    retrieved_at: datetime
    fields: dict[str, Any] = Field(default_factory=dict)

    @field_validator("product_url")
    @classmethod
    def validate_product_url(cls, value: str | None) -> str | None:
        if value is not None and urlparse(value).scheme not in {"http", "https"}:
            raise ValueError("product_url must use http or https")
        return value


def validate_authorized_dataset(
    source: AuthorizedDataSource,
    records: list[AuthorizedProductRecord],
    *,
    now: datetime | None = None,
    max_age_hours: int = 72,
) -> dict[str, Any]:
    """Return a secret-free data readiness report for the current workspace."""

    current = now or datetime.now(timezone.utc)
    errors: list[str] = []
    warnings: list[str] = []
    if source.authorization_status != "verified":
        errors.append("授权状态必须为 verified，user_declared 不能直接开放商业决策")
    source_ids = {record.source_id for record in records}
    if source.source_id not in source_ids and records:
        errors.append("记录 source_id 与数据源 source_id 不匹配")
    seen_ids: set[str] = set()
    stale_count = 0
    missing_url_count = 0
    priced_count = 0
    for record in records:
        if record.record_id in seen_ids:
            errors.append(f"record_id 重复：{record.record_id}")
        seen_ids.add(record.record_id)
        if record.retrieved_at.tzinfo is None:
            errors.append(f"retrieved_at 必须包含时区：{record.record_id}")
        elif (current - record.retrieved_at).total_seconds() > max_age_hours * 3600:
            stale_count += 1
        if not record.product_url:
            missing_url_count += 1
        if record.price is not None:
            priced_count += 1
    if stale_count:
        warnings.append(f"有 {stale_count} 条记录超过 {max_age_hours} 小时未刷新")
    if missing_url_count:
        warnings.append(f"有 {missing_url_count} 条记录缺少商品详情页 URL")
    if records and priced_count == 0:
        warnings.append("当前记录没有价格字段，不能形成价格核验覆盖")
    if source.source_kind == "reader":
        warnings.append("Reader 只证明页面内容可读取，不证明销量、库存、成本或合规")
    if not records:
        errors.append("数据集不能为空")
    status = "ready_for_verification" if not errors else "blocked"
    return {
        "schema_version": "d2-authorized-data-v1",
        "status": status,
        "commercial_decision_ready": False,
        "owner_id": source.owner_id,
        "source": {
            "source_id": source.source_id,
            "provider": source.provider,
            "source_kind": source.source_kind,
            "authorization_status": source.authorization_status,
            "authorization_reference_present": bool(source.authorization_reference),
            "terms_url_present": bool(source.terms_url),
        },
        "record_count": len(records),
        "priced_record_count": priced_count,
        "stale_record_count": stale_count,
        "missing_url_count": missing_url_count,
        "errors": errors,
        "warnings": warnings,
        "next_step": "完成逐 SKU 商业核验、证据绑定和合规复核后，才可评估商业决策门禁。",
    }
