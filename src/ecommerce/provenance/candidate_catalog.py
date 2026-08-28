"""Build a candidate-only catalog from report search evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from ..models import FinalReport
from ..search.models import normalize_search_url
from ..search.quality import classify_source_domain
from .verification import report_fingerprint


@dataclass
class _CandidateAccumulator:
    source_url: str
    title: str
    evidence_ids: list[str] = field(default_factory=list)
    modules: set[str] = field(default_factory=set)
    confidence: float = 0.0
    retrieved_at: str | None = None
    reported_price_hints: list[dict[str, Any]] = field(default_factory=list)
    recommendation_ids: set[str] = field(default_factory=set)


def build_candidate_catalog(report: FinalReport | dict[str, Any]) -> dict[str, Any]:
    """Group report evidence by canonical URL without making commercial claims."""

    report_model = report if isinstance(report, FinalReport) else FinalReport.model_validate(report)
    candidates: dict[str, _CandidateAccumulator] = {}
    evidence_to_candidate: dict[str, str] = {}
    for evidence in report_model.evidence:
        key = normalize_search_url(evidence.source)
        candidate = candidates.get(key)
        retrieved_at = evidence.retrieved_at.isoformat() if evidence.retrieved_at else None
        if candidate is None:
            candidate = _CandidateAccumulator(
                source_url=evidence.source,
                title=evidence.title,
                confidence=evidence.confidence,
                retrieved_at=retrieved_at,
            )
            candidates[key] = candidate
        candidate.evidence_ids.append(evidence.evidence_id)
        candidate.confidence = max(candidate.confidence, evidence.confidence)
        if retrieved_at and (candidate.retrieved_at is None or retrieved_at > candidate.retrieved_at):
            candidate.retrieved_at = retrieved_at
        for support in evidence.supports:
            if support.startswith("search:"):
                candidate.modules.add(support.split(":", 1)[1])
        evidence_to_candidate[evidence.evidence_id] = key

    for recommendation in report_model.recommendations:
        for evidence_id in recommendation.evidence_ids:
            key = evidence_to_candidate.get(evidence_id)
            if key:
                candidates[key].recommendation_ids.add(recommendation.product_name)
    for competitor in report_model.competitors:
        for evidence_id in competitor.evidence_ids:
            key = evidence_to_candidate.get(evidence_id)
            if key:
                candidates[key].reported_price_hints.append(
                    {
                        "name": competitor.name,
                        "amount": competitor.price,
                        "currency": "CNY",
                        "evidence_ids": [evidence_id],
                    }
                )

    recommendation_count = len(report_model.recommendations)
    ranked_candidates: list[tuple[float, str, _CandidateAccumulator]] = []
    for key, candidate in candidates.items():
        source_domain = (urlsplit(key).hostname or "").lower()
        source_quality = classify_source_domain(source_domain)
        module_coverage = len(candidate.modules) / 4
        recommendation_coverage = (
            len(candidate.recommendation_ids) / recommendation_count
            if recommendation_count
            else 0.0
        )
        rank_score = (
            candidate.confidence * 0.45
            + source_quality.score * 0.25
            + module_coverage * 0.15
            + recommendation_coverage * 0.15
        )
        ranked_candidates.append((rank_score, key, candidate))

    items = []
    for index, (rank_score, key, candidate) in enumerate(
        sorted(ranked_candidates, key=lambda item: (-item[0], item[1])), 1
    ):
        source_domain = (urlsplit(key).hostname or "").lower()
        source_quality = classify_source_domain(source_domain)
        module_coverage = len(candidate.modules) / 4
        recommendation_coverage = (
            len(candidate.recommendation_ids) / recommendation_count
            if recommendation_count
            else 0.0
        )
        items.append(
            {
                "candidate_id": f"candidate-{index:03d}",
                "canonical_url": key,
                "source_url": candidate.source_url,
                "source_domain": source_domain,
                "source_quality_category": source_quality.category,
                "source_quality_score": source_quality.score,
                "title": candidate.title,
                "evidence_ids": sorted(candidate.evidence_ids),
                "evidence_count": len(candidate.evidence_ids),
                "modules": sorted(candidate.modules),
                "module_coverage": round(module_coverage, 4),
                "recommendation_ids": sorted(candidate.recommendation_ids),
                "recommendation_coverage": round(recommendation_coverage, 4),
                "retrieval_confidence": round(candidate.confidence, 4),
                "candidate_rank_score": round(rank_score, 4),
                "ranking_reasons": [
                    f"来源质量：{source_quality.relevance}",
                    f"证据覆盖：{len(candidate.modules)}/4 个搜索模块",
                    f"推荐关联：{len(candidate.recommendation_ids)}/{recommendation_count or 0} 个方向",
                ],
                "retrieved_at": candidate.retrieved_at,
                "reported_price_hints": candidate.reported_price_hints,
            }
        )
    return {
        "schema_version": "1.0",
        "status": "candidate_only",
        "report_fingerprint": report_fingerprint(report_model),
        "category": report_model.request.category,
        "candidate_count": len(items),
        "candidates": items,
        "warnings": [
            "候选目录只汇总搜索证据，不代表商品详情、销量、成本、库存或合规事实。",
            "reported_price_hints 仅是报告中的竞品价格提示，不能替代 SKU 级核验。",
            "candidate_rank_score 仅用于候选优先级排序，不是商业可行性评分。",
        ],
    }
