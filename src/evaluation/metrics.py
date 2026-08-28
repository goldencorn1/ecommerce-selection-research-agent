"""Explainable, local-only metrics for structured e-commerce research reports."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.ecommerce.models import FinalReport

from .dataset import EvaluationCase


class MetricResult(BaseModel):
    """A measured metric; it never claims model quality beyond the checked rule."""

    model_config = ConfigDict(extra="forbid")

    name: str
    measured: Literal["measured"] = "measured"
    score: float = Field(ge=0, le=1)
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)


def _metric(name: str, score: float, passed: bool, **details: Any) -> MetricResult:
    return MetricResult(
        name=name,
        score=round(max(0.0, min(1.0, score)), 4),
        passed=passed,
        details=details,
    )


def report_completeness(
    report: FinalReport,
    expected_sections: Iterable[str],
    expected_degradation: Iterable[str] = (),
) -> MetricResult:
    """Measure whether expected non-empty report sections are present."""

    section_values: Mapping[str, Any] = {
        "executive_summary": report.executive_summary,
        "recommendations": report.recommendations,
        "trends": report.trends,
        "competitors": report.competitors,
        "customer_profiles": report.customer_profiles,
        "opportunities_risks": report.opportunities_risks,
        "evidence": report.evidence,
        "warnings": report.warnings,
    }
    requested = list(dict.fromkeys(expected_sections))
    degraded_section_map = {
        "market": "trends",
        "competitor": "competitors",
        "customer": "customer_profiles",
        "opportunity": "opportunities_risks",
    }
    allowed_missing = [
        degraded_section_map[module]
        for module in expected_degradation
        if module in degraded_section_map
        and degraded_section_map[module] in requested
    ]
    required = [name for name in requested if name not in allowed_missing]
    present = [
        name for name in requested
        if name in section_values and bool(section_values[name])
    ]
    required_present = [name for name in required if name in present]
    score = len(required_present) / len(required) if required else 1.0
    return _metric(
        "report_completeness",
        score,
        len(required_present) == len(required),
        expected_sections=requested,
        present_sections=present,
        required_sections=required,
        allowed_missing_sections=allowed_missing,
        missing_sections=[name for name in required if name not in present],
    )


def category_relevance(report: FinalReport, category: str) -> MetricResult:
    """Measure whether key report sections keep the requested category visible."""

    if not category.strip():
        raise ValueError("category must not be empty")
    section_texts = {
        "executive_summary": report.executive_summary,
        "recommendations": " ".join(item.product_name for item in report.recommendations),
        "trends": " ".join(item.name for item in report.trends),
        "opportunities_risks": " ".join(item.opportunity for item in report.opportunities_risks),
    }
    matched_sections = [
        name for name, text in section_texts.items() if category in text
    ]
    score = len(matched_sections) / len(section_texts)
    return _metric(
        "category_relevance",
        score,
        len(matched_sections) >= 3,
        category=category,
        checked_sections=list(section_texts),
        matched_sections=matched_sections,
    )


def evidence_coverage(report: FinalReport, minimum_evidence_count: int) -> MetricResult:
    """Measure evidence volume and whether report recommendations cite known evidence."""

    if minimum_evidence_count < 0:
        raise ValueError("minimum_evidence_count must be non-negative")
    evidence_ids = {item.evidence_id for item in report.evidence}
    cited_ids = {
        evidence_id
        for recommendation in report.recommendations
        for evidence_id in recommendation.evidence_ids
    }
    valid_citations = cited_ids & evidence_ids
    volume_score = (
        1.0
        if minimum_evidence_count == 0
        else min(1.0, len(report.evidence) / minimum_evidence_count)
    )
    citation_score = (
        1.0
        if not report.recommendations
        else len(valid_citations) / max(1, len(cited_ids))
    )
    score = volume_score * 0.7 + citation_score * 0.3
    passed = len(report.evidence) >= minimum_evidence_count and citation_score == 1.0
    return _metric(
        "evidence_coverage",
        score,
        passed,
        minimum_evidence_count=minimum_evidence_count,
        measured_evidence_count=len(report.evidence),
        cited_evidence_count=len(cited_ids),
        valid_citation_count=len(valid_citations),
    )


def score_validity(report: FinalReport) -> MetricResult:
    """Measure that every recommendation score is numeric and inside the 0-100 contract."""

    field_names = (
        "demand",
        "competition",
        "margin",
        "differentiation",
        "evidence_quality",
        "total",
    )
    values = [
        getattr(recommendation.score, field_name)
        for recommendation in report.recommendations
        for field_name in field_names
    ]
    valid_values = [
        value for value in values
        if isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 100
    ]
    score = len(valid_values) / len(values) if values else 0.0
    return _metric(
        "score_validity",
        score,
        bool(values) and len(valid_values) == len(values),
        checked_value_count=len(values),
        valid_value_count=len(valid_values),
        allowed_range=[0, 100],
    )


def degradation_warning_quality(report: FinalReport) -> MetricResult:
    """Measure warning presence and specificity for observable degraded report states."""

    expected_fragments: list[str] = []
    if len(report.evidence) < 3:
        expected_fragments.append("证据不足")
    if not report.trends:
        expected_fragments.append("市场趋势")
    if not report.competitors:
        expected_fragments.append("竞品")
    if not report.customer_profiles:
        expected_fragments.append("用户画像")
    if not report.opportunities_risks:
        expected_fragments.append("机会风险")

    warning_texts = [warning for warning in report.warnings if isinstance(warning, str) and warning.strip()]
    matched_fragments = [
        fragment for fragment in expected_fragments
        if any(fragment in warning for warning in warning_texts)
    ]
    unexpected_state = not expected_fragments
    score = (
        1.0
        if unexpected_state and not report.warnings
        else len(matched_fragments) / len(expected_fragments)
        if expected_fragments
        else 0.0
    )
    warning_format_ok = len(warning_texts) == len(report.warnings)
    return _metric(
        "degradation_warning_quality",
        score if warning_format_ok else score * 0.5,
        warning_format_ok and len(matched_fragments) == len(expected_fragments),
        expected_warning_fragments=expected_fragments,
        matched_warning_fragments=matched_fragments,
        warning_count=len(report.warnings),
        warning_format_valid=warning_format_ok,
    )


def structured_output_validity(report: FinalReport) -> MetricResult:
    """Measure serializability and required top-level structure of the report."""

    required_keys = {
        "request",
        "executive_summary",
        "recommendations",
        "trends",
        "competitors",
        "customer_profiles",
        "opportunities_risks",
        "evidence",
        "warnings",
    }
    try:
        payload = report.model_dump(mode="json")
        json.dumps(payload, ensure_ascii=False)
        actual_keys = set(payload)
        valid = required_keys <= actual_keys
    except (TypeError, ValueError):
        payload = {}
        actual_keys = set()
        valid = False
    return _metric(
        "structured_output_validity",
        1.0 if valid else 0.0,
        valid,
        required_keys=sorted(required_keys),
        missing_keys=sorted(required_keys - actual_keys),
    )


def evaluate_report(report: FinalReport, case: EvaluationCase) -> list[MetricResult]:
    """Run all local metrics for one report and mark every result as measured."""

    return [
        report_completeness(
            report,
            case.expected_sections,
            expected_degradation=case.expected_degradation,
        ),
        category_relevance(report, case.category),
        evidence_coverage(report, case.minimum_evidence_count),
        score_validity(report),
        degradation_warning_quality(report),
        structured_output_validity(report),
    ]
