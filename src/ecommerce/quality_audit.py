"""Offline quality audit for saved e-commerce reports.

The audit is deliberately read-only: it never calls a search provider or a
model.  It turns runtime telemetry into a compact review artifact and keeps
the distinction between interface success, usable evidence and commercial
decision readiness explicit.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _payload_section(payload: Mapping[str, Any], *names: str) -> Mapping[str, Any]:
    for name in names:
        value = payload.get(name)
        if isinstance(value, Mapping):
            return value
    return {}


def audit_report_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic, secret-free quality audit from a saved report."""

    report = _payload_section(payload, "report")
    metrics = _payload_section(payload, "run_metrics", "ecommerce_metrics")
    search_details = _payload_section(payload, "search_details", "ecommerce_search_details")
    gates = _payload_section(metrics, "quality_gates")

    modules: dict[str, dict[str, Any]] = {}
    total_results = 0
    total_mainland = 0
    total_unknown = 0
    total_published = 0
    weighted_source_score = 0.0
    warning_count = _int(metrics.get("warning_count"))
    for module_name, raw_details in search_details.items():
        if not isinstance(raw_details, Mapping):
            continue
        result_count = _int(raw_details.get("result_count"))
        mainland_count = _int(raw_details.get("mainland_relevant_count"))
        unknown_count = _int(raw_details.get("unknown_source_count"))
        published_count = _int(raw_details.get("published_result_count"))
        source_score = _float(raw_details.get("source_quality_score"))
        quality_warnings = raw_details.get("quality_warnings")
        if not isinstance(quality_warnings, list):
            quality_warnings = []
        warning_count = max(warning_count, len(quality_warnings))
        total_results += result_count
        total_mainland += mainland_count
        total_unknown += unknown_count
        total_published += min(published_count, result_count)
        if source_score is not None:
            weighted_source_score += source_score * result_count
        modules[str(module_name)] = {
            "status": str(raw_details.get("status", "unknown")),
            "result_count": result_count,
            "mainland_relevant_count": mainland_count,
            "mainland_relevance_rate": round(mainland_count / result_count, 4)
            if result_count
            else 0.0,
            "unknown_source_count": unknown_count,
            "unknown_source_rate": round(unknown_count / result_count, 4)
            if result_count
            else 0.0,
            "published_result_count": published_count,
            "published_result_rate": round(published_count / result_count, 4)
            if result_count
            else 0.0,
            "priced_result_count": _int(raw_details.get("priced_result_count")),
            "price_coverage": _float(raw_details.get("price_coverage")),
            "freshness_status": str(raw_details.get("freshness_status", "unverified")),
            "source_quality_score": source_score,
            "quality_warning_count": len(quality_warnings),
        }

    competitor = modules.get("competitor", {})
    price_coverage = competitor.get("price_coverage")
    if price_coverage is None:
        price_coverage = 0.0
    evidence_count = len(report.get("evidence", [])) if isinstance(report.get("evidence"), list) else 0
    recommendation_count = (
        len(report.get("recommendations", []))
        if isinstance(report.get("recommendations"), list)
        else 0
    )
    quality_level = str(metrics.get("quality_level", "not_assessed"))
    interface_success = bool(gates.get("interface_success", False))
    evidence_usable = bool(gates.get("evidence_usable", False))
    commercial_ready = bool(gates.get("commercial_decision_ready", False))

    blocking_reasons: list[str] = []
    if not interface_success:
        blocking_reasons.append("接口或搜索模块未全部成功")
    if not evidence_usable:
        blocking_reasons.append("证据门禁未通过：来源、地域相关性、时效或价格证据仍不足")
    if not commercial_ready:
        blocking_reasons.append("商业决策门禁未开放：仍需可追溯的商品页、销量、成本、库存和合规核验")
    for module_name, details in modules.items():
        if details["quality_warning_count"]:
            blocking_reasons.append(
                f"{module_name} 模块存在 {details['quality_warning_count']} 条来源/时效告警"
            )

    status = "commercial_ready" if commercial_ready else "review_required"
    if not interface_success:
        status = "degraded"
    return {
        "schema_version": "c3-quality-audit-v1",
        "status": status,
        "quality_level": quality_level,
        "gates": {
            "interface_success": interface_success,
            "evidence_usable": evidence_usable,
            "commercial_decision_ready": commercial_ready,
        },
        "report": {
            "recommendation_count": recommendation_count,
            "evidence_count": evidence_count,
            "warning_count": warning_count,
        },
        "search": {
            "module_count": len(modules),
            "total_result_count": total_results,
            "mainland_relevance_rate": round(total_mainland / total_results, 4)
            if total_results
            else 0.0,
            "unknown_source_rate": round(total_unknown / total_results, 4)
            if total_results
            else 0.0,
            "published_result_rate": round(total_published / total_results, 4)
            if total_results
            else 0.0,
            "weighted_source_quality_score": round(weighted_source_score / total_results, 4)
            if total_results
            else 0.0,
            "competitor_price_coverage": round(float(price_coverage), 4),
        },
        "modules": modules,
        "model": {
            "name": str(metrics.get("model_name", "")),
            "usage_available": bool(metrics.get("usage_available", False)),
            "input_tokens": _int(metrics.get("actual_input_tokens")),
            "output_tokens": _int(metrics.get("actual_output_tokens")),
            "total_tokens": _int(metrics.get("actual_total_tokens")),
            "cost_status": str(metrics.get("cost_status", "unavailable")),
            "actual_cost_usd": _float(metrics.get("actual_cost_usd")),
        },
        "blocking_reasons": list(dict.fromkeys(blocking_reasons)),
    }
