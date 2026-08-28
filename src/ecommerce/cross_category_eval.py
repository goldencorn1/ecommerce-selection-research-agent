"""Threshold checks for cross-category live-search evaluation."""

from __future__ import annotations

from typing import Any

from .search.benchmark import SearchBenchmarkRun


def evaluate_cross_category_run(
    run: SearchBenchmarkRun,
    *,
    min_categories: int = 3,
    min_search_success_rate: float = 0.8,
    min_evidence_usable_rate: float = 0.8,
) -> dict[str, Any]:
    """Evaluate repeatability without turning search success into truth."""

    summary = run.summary
    blocking_reasons: list[str] = []
    if summary.category_count < min_categories:
        blocking_reasons.append(f"品类数不足：{summary.category_count}/{min_categories}")
    if summary.search_success_rate < min_search_success_rate:
        blocking_reasons.append("搜索成功率未达到跨品类评测阈值")
    if summary.evidence_usable_rate < min_evidence_usable_rate:
        blocking_reasons.append("证据可用率未达到跨品类评测阈值")
    return {
        "schema_version": "d3-cross-category-eval-v1",
        "status": "pass" if not blocking_reasons else "blocked",
        "category_count": summary.category_count,
        "search_success_rate": summary.search_success_rate,
        "evidence_usable_rate": summary.evidence_usable_rate,
        "commercial_decision_ready_rate": summary.commercial_decision_ready_rate,
        "blocking_reasons": blocking_reasons,
        "commercial_boundary": "通过搜索评测不等于商业决策就绪，仍需授权商品数据和人工核验",
    }
