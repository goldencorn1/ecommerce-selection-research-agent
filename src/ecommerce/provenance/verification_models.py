"""Typed records for human verification of commercial e-commerce claims."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VerificationPrice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(ge=0)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    type: Literal["sale_price", "coupon_price", "list_price", "unknown"] = "sale_price"


class VerificationSales(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int = Field(ge=0)
    unit: str = Field(min_length=1)
    period: str = Field(min_length=1)


class VerificationCost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_cost: Decimal = Field(ge=0)
    currency: str = Field(default="CNY", min_length=3, max_length=3)


class VerificationInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["in_stock", "out_of_stock", "unknown"]
    quantity: int | None = Field(default=None, ge=0)


class VerificationCompliance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["passed", "pending", "failed", "not_applicable"]
    notes: str = ""


class CommercialVerificationRecord(BaseModel):
    """One human-reviewed product-page record linked to report evidence."""

    model_config = ConfigDict(extra="forbid")

    verification_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    report_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    recommendation_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    detail_page_url: str = Field(min_length=1)
    verifier: str = Field(min_length=1)
    verified_at: datetime
    price: VerificationPrice
    sales: VerificationSales
    cost: VerificationCost
    inventory: VerificationInventory
    compliance: VerificationCompliance
    conclusion: Literal["pass", "conditional", "reject"]
    notes: str = ""
    evidence_ids: list[str] = Field(min_length=1)

    @field_validator("detail_page_url")
    @classmethod
    def valid_detail_page_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("detail_page_url must be an absolute http(s) URL")
        return value

    @field_validator("verified_at")
    @classmethod
    def timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("verified_at must be timezone-aware")
        return value

    @field_validator("evidence_ids")
    @classmethod
    def non_empty_evidence_ids(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("evidence_ids must contain non-empty values")
        return value


class VerificationValidation(BaseModel):
    """Auditable result of checking records against one generated report."""

    model_config = ConfigDict(extra="forbid")

    complete: bool = False
    records_count: int = Field(default=0, ge=0)
    covered_recommendations: int = Field(default=0, ge=0)
    missing_recommendations: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
