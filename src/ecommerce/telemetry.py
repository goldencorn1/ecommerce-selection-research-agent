"""Local latency and cost estimation for e-commerce research runs.

The current MVP uses deterministic Mock data, so its measured API cost is zero.
Token counts are estimates based on UTF-8 text length and must not be presented
as provider billing records. A future model-backed provider can replace the
estimator with usage metadata from the provider response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Sequence

from .orchestration import ResearchResult
from .providers import ResearchProvider


def estimate_tokens(text: str) -> int:
    """Estimate tokens conservatively from text length; not provider billing."""

    return max(1, (len(text) + 3) // 4) if text else 0


def assess_quality_gates(
    result: ResearchResult,
    verification_validation: dict[str, Any] | None = None,
) -> tuple[str, dict[str, bool]]:
    """Separate transport success from evidence and business-readiness claims."""

    details = result.search_details
    interface_success = bool(details) and result.search_status == "success" and all(
        str(module.get("status")) == "success" for module in details.values()
    )
    evidence_usable = interface_success and all(
        not module.get("quality_warnings")
        and int(module.get("unknown_source_count", 0) or 0) == 0
        and int(module.get("mainland_relevant_count", 0) or 0) > 0
        and str(module.get("freshness_status")) == "verified"
        for module in details.values()
    )
    competitor = details.get("competitor", {})
    evidence_usable = evidence_usable and float(competitor.get("price_coverage", 0.0) or 0.0) >= 1.0
    # Commercial readiness requires verified first-party sales, cost, compliance,
    # and product-page data; this MVP intentionally never infers that gate.
    commercial_decision_ready = bool(
        evidence_usable
        and verification_validation
        and verification_validation.get("complete") is True
    )
    gates = {
        "interface_success": interface_success,
        "evidence_usable": evidence_usable,
        "commercial_decision_ready": commercial_decision_ready,
    }
    if commercial_decision_ready:
        level = "commercial_decision_ready"
    elif evidence_usable:
        level = "evidence_usable"
    elif interface_success:
        level = "interface_success"
    else:
        level = "not_assessed"
    return level, gates


def assess_report_quality(result: ResearchResult) -> dict[str, bool]:
    """Check whether the generated report is useful as a product artifact."""

    report = result.report
    recommendations = report.recommendations
    validation_cards_complete = bool(recommendations) and all(
        item.validation_action.strip()
        and item.validation_threshold.strip()
        and bool(item.validation_data_needed)
        and item.validation_failure_action.strip()
        for item in recommendations
    )
    price_basis_present = bool(recommendations) and all(
        item.price_range.strip() and item.price_basis.strip() for item in recommendations
    )
    direction_distinctness = len(
        {(item.positioning.strip(), item.price_range.strip()) for item in recommendations}
    ) >= min(2, len(recommendations))
    score_explanations = bool(recommendations) and all(item.score_note.strip() for item in recommendations)
    decision_boundary_present = bool(report.decision_basis.strip() and report.next_actions)
    return {
        "report_structure_complete": bool(
            report.executive_summary.strip()
            and report.decision_status
            and recommendations
            and report.evidence
        ),
        "validation_cards_complete": validation_cards_complete,
        "price_basis_present": price_basis_present,
        "direction_distinctness": direction_distinctness,
        "score_explanations_present": score_explanations,
        "decision_boundary_present": decision_boundary_present,
        "report_product_ready": all(
            (
                bool(report.executive_summary.strip()),
                validation_cards_complete,
                price_basis_present,
                direction_distinctness,
                score_explanations,
                decision_boundary_present,
            )
        ),
    }


@dataclass(frozen=True)
class RunMetrics:
    mode: str
    status: str
    latency_ms: float
    input_chars: int
    output_chars: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    warning_count: int
    external_request_count: int = 0
    cost_note: str = "Mock 数据运行未产生真实模型或搜索 API 费用；token 数为估算值。"
    overall_status: str = "success"
    model_status: str = "not_used"
    model_error_kind: str | None = None
    model_name: str = ""
    usage_available: bool = False
    usage_source: str = ""
    actual_input_tokens: int = 0
    actual_output_tokens: int = 0
    actual_total_tokens: int = 0
    actual_cost_usd: float = 0.0
    cost_status: str = "unavailable"
    search_status: str = "not_used"
    search_cache_hit_count: int = 0
    search_cache_miss_count: int = 0
    quality_level: str = "not_assessed"
    quality_gates: dict[str, bool] = field(default_factory=dict)
    report_quality_gates: dict[str, bool] = field(default_factory=dict)
    verification_validation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "status": self.status,
            "latency_ms": round(self.latency_ms, 2),
            "input_chars": self.input_chars,
            "output_chars": self.output_chars,
            "estimated_input_tokens": self.estimated_input_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 8),
            "warning_count": self.warning_count,
            "external_request_count": self.external_request_count,
            "cost_note": self.cost_note,
            "overall_status": self.overall_status,
            "model_status": self.model_status,
            "model_error_kind": self.model_error_kind,
            "model_name": self.model_name,
            "usage_available": self.usage_available,
            "usage_source": self.usage_source,
            "actual_input_tokens": self.actual_input_tokens,
            "actual_output_tokens": self.actual_output_tokens,
            "actual_total_tokens": self.actual_total_tokens,
            "actual_cost_usd": round(self.actual_cost_usd, 8),
            "cost_status": self.cost_status,
            "search_status": self.search_status,
            "search_cache_hit_count": self.search_cache_hit_count,
            "search_cache_miss_count": self.search_cache_miss_count,
            "quality_level": self.quality_level,
            "quality_gates": self.quality_gates,
            "report_quality_gates": self.report_quality_gates,
            "verification_validation": self.verification_validation,
        }


def run_instrumented_mock_research(
    request: Any = None,
    provider: ResearchProvider | None = None,
) -> tuple[ResearchResult, RunMetrics]:
    """Run the Mock workflow and return its result plus measured local metrics."""

    return run_instrumented_research(request, provider=provider, mode="mock")


def run_instrumented_research(
    request: Any = None,
    provider: ResearchProvider | None = None,
    *,
    mode: str = "mock",
    estimated_cost_usd: float = 0.0,
    cost_note: str | None = None,
    report_enhancer: Any = None,
    input_cost_per_million: float = 0.0,
    output_cost_per_million: float = 0.0,
    verification_records: Sequence[Any] | None = None,
    knowledge_retriever: Any = None,
    knowledge_top_k: int = 3,
    use_agent_graph: bool = True,
) -> tuple[ResearchResult, RunMetrics]:
    """Run a provider-backed workflow and measure local latency/usage metadata."""

    from .orchestration import run_research

    request_text = request if isinstance(request, str) else repr(request or {})
    request_count_before = int(getattr(provider, "request_count", 0))
    started = perf_counter()
    try:
        result = run_research(
            request,
            provider=provider,
            research_mode=mode.title(),
            report_enhancer=report_enhancer,
            knowledge_retriever=knowledge_retriever,
            knowledge_top_k=knowledge_top_k,
            use_agent_graph=use_agent_graph,
        )
        status = "success"
    except Exception:
        elapsed = (perf_counter() - started) * 1000
        metrics = RunMetrics(
            mode=mode,
            status="error",
            latency_ms=elapsed,
            input_chars=len(request_text),
            output_chars=0,
            estimated_input_tokens=estimate_tokens(request_text),
            estimated_output_tokens=0,
            estimated_cost_usd=0.0,
            warning_count=0,
            cost_note=cost_note or "运行失败，未产生可计量的模型或搜索 API 成本。",
        )
        raise RuntimeError(f"{mode} research failed; metrics={metrics.to_dict()}") from None

    output_text = result.markdown
    usage = result.model_usage
    actual_input_tokens = int(usage.get("input_tokens", 0) or 0)
    actual_output_tokens = int(usage.get("output_tokens", 0) or 0)
    actual_total_tokens = int(usage.get("total_tokens", 0) or actual_input_tokens + actual_output_tokens)
    actual_cost_usd = (
        actual_input_tokens * input_cost_per_million
        + actual_output_tokens * output_cost_per_million
    ) / 1_000_000
    usage_available = bool(usage.get("usage_available", False))
    usage_source = str(usage.get("usage_source", ""))
    if not usage_available:
        cost_status = "unavailable"
        usage_cost_note = cost_note or "provider 未返回 usage，无法计算账单级模型成本。"
    elif input_cost_per_million > 0 and output_cost_per_million > 0:
        cost_status = "actual"
        usage_cost_note = cost_note or "成本按 provider usage 和完整输入/输出单价计算。"
    elif input_cost_per_million > 0 or output_cost_per_million > 0:
        cost_status = "partial"
        usage_cost_note = cost_note or "仅配置了部分单价，成本不是完整账单口径。"
    else:
        cost_status = "unpriced"
        usage_cost_note = cost_note or "已读取 provider usage；未配置完整单价，因此实际成本暂记为 0。"
    overall_status = (
        "degraded"
        if result.model_status == "fallback" or result.search_status in {"partial", "fallback"}
        else "success"
    )
    verification_validation: dict[str, Any] = {}
    if verification_records is not None:
        from .provenance.verification import report_fingerprint, validate_verification_records

        validation = validate_verification_records(
            result.report,
            verification_records,
            valid_evidence_ids={item.evidence_id for item in result.report.evidence},
            expected_report_fingerprint=report_fingerprint(result.report),
        )
        verification_validation = validation.model_dump(mode="json")
    quality_level, quality_gates = assess_quality_gates(result, verification_validation)
    report_quality_gates = assess_report_quality(result)
    metrics = RunMetrics(
        mode=mode,
        status=status,
        latency_ms=(perf_counter() - started) * 1000,
        input_chars=len(request_text),
        output_chars=len(output_text),
        estimated_input_tokens=estimate_tokens(request_text),
        estimated_output_tokens=estimate_tokens(output_text),
        estimated_cost_usd=estimated_cost_usd,
        warning_count=len(result.warnings),
        external_request_count=max(
            0, int(getattr(provider, "request_count", 0)) - request_count_before
        ),
        cost_note=usage_cost_note,
        overall_status=overall_status,
        model_status=result.model_status,
        model_error_kind=result.model_error_kind,
        model_name=str(usage.get("model", "")),
        usage_available=usage_available,
        usage_source=usage_source,
        actual_input_tokens=actual_input_tokens,
        actual_output_tokens=actual_output_tokens,
        actual_total_tokens=actual_total_tokens,
        actual_cost_usd=actual_cost_usd,
        cost_status=cost_status,
        search_status=result.search_status,
        search_cache_hit_count=int(getattr(provider, "cache_hit_count", 0)),
        search_cache_miss_count=int(getattr(provider, "cache_miss_count", 0)),
        quality_level=quality_level,
        quality_gates=quality_gates,
        report_quality_gates=report_quality_gates,
        verification_validation=verification_validation,
    )
    return result, metrics
