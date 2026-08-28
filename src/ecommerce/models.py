"""Typed domain models for the e-commerce product research MVP."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .category_profiles import get_category_profile


class EcommerceResearchRequest(BaseModel):
    """Structured input for one product selection research run."""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(default="便携榨汁杯", min_length=1, max_length=80)
    target_market: str = Field(default="中国大陆电商", min_length=1, max_length=80)
    target_customer: str = Field(default="", max_length=120)
    price_min: float = Field(default=99.0, ge=0)
    price_max: float = Field(default=299.0, ge=0)
    top_n: int = Field(default=3, ge=1, le=10)
    constraints: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("price_max")
    @classmethod
    def price_max_not_below_min(cls, value: float, info):
        price_min = info.data.get("price_min")
        if price_min is not None and value < price_min:
            raise ValueError("price_max must be greater than or equal to price_min")
        return value

    def model_post_init(self, __context: object) -> None:
        if not self.target_customer:
            self.target_customer = get_category_profile(self.category).audience


class Evidence(BaseModel):
    """A traceable observation used by one or more research conclusions."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    supports: list[str] = Field(default_factory=list)
    retrieved_at: datetime | None = None
    source_type: str = "unknown"


class TrendSignal(BaseModel):
    """Market demand and momentum signal."""

    name: str
    direction: Literal["rising", "stable", "falling"]
    demand_score: float = Field(ge=0, le=100)
    growth_rate: float = Field(ge=-1, le=10)
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)


class CompetitorInsight(BaseModel):
    """A compact, provider-independent competitor observation."""

    name: str
    price: float = Field(ge=0)
    positioning: str
    price_source: str = "explicit"
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class CustomerProfile(BaseModel):
    """A target customer segment and the job it wants the product to do."""

    segment: str
    needs: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    buying_triggers: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class OpportunityRisk(BaseModel):
    """Opportunity and risk assessment for the category."""

    opportunity: str
    rationale: str
    opportunity_score: float = Field(ge=0, le=100)
    risks: list[str] = Field(default_factory=list)
    risk_score: float = Field(ge=0, le=100)
    mitigations: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ProductScore(BaseModel):
    """Explainable 0-100 product selection score."""

    demand: float = Field(ge=0, le=100)
    competition: float = Field(ge=0, le=100)
    margin: float = Field(ge=0, le=100)
    differentiation: float = Field(ge=0, le=100)
    evidence_quality: float = Field(ge=0, le=100)
    total: float = Field(ge=0, le=100)


class ProductRecommendation(BaseModel):
    """A concrete product direction derived from the research."""

    product_name: str
    positioning: str
    target_customer: str
    price_range: str
    rationale: str
    score: ProductScore
    evidence_ids: list[str] = Field(default_factory=list)
    validation_action: str = ""
    validation_threshold: str = ""
    validation_data_needed: list[str] = Field(default_factory=list)
    validation_failure_action: str = ""
    price_basis: str = ""
    score_note: str = ""


class ResearchProgressEvent(BaseModel):
    """A stable, UI-friendly event emitted by one research run."""

    event_id: str
    stage: Literal["request", "search", "clean", "score", "report", "complete", "error"]
    status: Literal["pending", "running", "success", "partial", "error"]
    message: str
    module: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class FinalReport(BaseModel):
    """Structured final report consumed by CLI, tests, or a future graph node."""

    model_config = ConfigDict(extra="forbid")

    request: EcommerceResearchRequest
    executive_summary: str
    recommendations: list[ProductRecommendation] = Field(default_factory=list)
    trends: list[TrendSignal] = Field(default_factory=list)
    competitors: list[CompetitorInsight] = Field(default_factory=list)
    customer_profiles: list[CustomerProfile] = Field(default_factory=list)
    opportunities_risks: list[OpportunityRisk] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    decision_status: Literal["validate_first", "insufficient_evidence", "ready_for_scale"] = "validate_first"
    decision_basis: str = ""
    next_actions: list[str] = Field(default_factory=list)
