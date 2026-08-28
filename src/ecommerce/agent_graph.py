"""Independent multi-agent graph for the e-commerce research workflow.

The graph deliberately keeps provider calls in the four research agents.  The
remaining agents only prepare state, derive price anchors, build the existing
report, or review it.  This makes the execution order observable without
running the provider-backed research more than once.
"""

from __future__ import annotations

from collections.abc import Mapping
from statistics import median
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .models import (
    CompetitorInsight,
    CustomerProfile,
    EcommerceResearchRequest,
    Evidence,
    FinalReport,
    OpportunityRisk,
    TrendSignal,
)
from .orchestration import (
    CompetitorResearch,
    CustomerResearch,
    MarketResearch,
    OpportunityRiskAnalysis,
    ReportGenerator,
    Reviewer,
    _append_unique,
    _render_markdown,
    _request_from_input,
    classify_model_error,
)
from .providers import MockResearchProvider, ResearchProvider


AGENT_NAMES = (
    "supervisor",
    "market",
    "competitor",
    "price",
    "customer",
    "risk",
    "report",
    "reviewer",
)

_REQUIRED_AGENT_RESULT_KEYS = (
    "agent",
    "status",
    "output",
    "evidence_ids",
    "warnings",
    "error_kind",
    "attempts",
)


class EcommerceAgentState(TypedDict, total=False):
    """JSON-friendly state shared by the independent e-commerce agents."""

    request: dict[str, Any]
    research_mode: str
    agent_plan: list[str]
    agent_results: dict[str, dict[str, Any]]
    warnings: list[str]
    evidence: list[dict[str, Any]]
    trends: list[dict[str, Any]]
    competitors: list[dict[str, Any]]
    price_anchors: dict[str, Any]
    customers: list[dict[str, Any]]
    opportunities: list[dict[str, Any]]
    report: dict[str, Any]
    markdown: str


def _empty_agent_result(agent: str, status: str = "pending") -> dict[str, Any]:
    """Create the stable envelope used for every agent result."""

    return {
        "agent": agent,
        "status": status,
        "output": {},
        "evidence_ids": [],
        "warnings": [],
        "error_kind": None,
        "attempts": 0,
    }


def _json_value(value: Any) -> Any:
    """Convert domain models and nested values to standard JSON values."""

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _copy_results(state: EcommerceAgentState) -> dict[str, dict[str, Any]]:
    results = dict(state.get("agent_results") or {})
    for agent in AGENT_NAMES:
        results.setdefault(agent, _empty_agent_result(agent))
    return results


def _copy_warnings(state: EcommerceAgentState) -> list[str]:
    return list(state.get("warnings") or [])


def _merge_evidence(
    existing: list[dict[str, Any]], new_items: list[Evidence]
) -> list[dict[str, Any]]:
    """Merge evidence by id while retaining the existing orchestration rule."""

    merged = [dict(item) for item in existing]
    by_id = {str(item.get("evidence_id")): item for item in merged}
    for evidence in new_items:
        item = _json_value(evidence)
        evidence_id = str(item.get("evidence_id", ""))
        prior = by_id.get(evidence_id)
        if prior is None:
            merged.append(item)
            by_id[evidence_id] = item
            continue
        prior["confidence"] = max(
            float(prior.get("confidence", 0)), float(item.get("confidence", 0))
        )
        supports = list(prior.get("supports") or [])
        _append_unique(supports, list(item.get("supports") or []))
        prior["supports"] = supports
    return merged


def _result(
    agent: str,
    *,
    status: str,
    output: Any,
    evidence_ids: list[str] | None = None,
    warnings: list[str] | None = None,
    error_kind: str | None = None,
    attempts: int = 1,
    error: str | None = None,
) -> dict[str, Any]:
    value = _empty_agent_result(agent, status)
    value.update(
        {
            "output": _json_value(output),
            "evidence_ids": list(evidence_ids or []),
            "warnings": list(warnings or []),
            "error_kind": error_kind,
            "attempts": attempts,
        }
    )
    if error is not None:
        value["error"] = str(error)
    # Keep this assertion local so future edits cannot accidentally make one
    # agent's envelope differ from the contract of the others.
    assert all(key in value for key in _REQUIRED_AGENT_RESULT_KEYS)
    return value


def _with_agent_result(
    state: EcommerceAgentState,
    agent: str,
    result: dict[str, Any],
    **updates: Any,
) -> EcommerceAgentState:
    next_state: EcommerceAgentState = dict(state)
    results = _copy_results(state)
    results[agent] = result
    next_state["agent_results"] = results
    next_state.update(updates)
    return next_state


def _request(state: EcommerceAgentState) -> EcommerceResearchRequest:
    return _request_from_input(state.get("request"))


def _module_status(provider: ResearchProvider, module: str) -> str:
    details = getattr(provider, "module_status", {}) or {}
    value = details.get(module, {}) if isinstance(details, Mapping) else {}
    return str(value.get("status", "success")) if isinstance(value, Mapping) else "success"


def _provider_warnings(provider: ResearchProvider, state: EcommerceAgentState) -> list[str]:
    warnings = _copy_warnings(state)
    _append_unique(warnings, list(getattr(provider, "warnings", []) or []))
    return warnings


def _supervisor_node(
    state: EcommerceAgentState, *, research_mode: str
) -> EcommerceAgentState:
    try:
        request = _request(state)
        results = {agent: _empty_agent_result(agent) for agent in AGENT_NAMES}
        results["supervisor"] = _result(
            "supervisor",
            status="success",
            output={
                "request": request.model_dump(mode="json"),
                "research_mode": research_mode,
                "execution_order": list(AGENT_NAMES),
            },
        )
        return _with_agent_result(
            state,
            "supervisor",
            results["supervisor"],
            request=request.model_dump(mode="json"),
            research_mode=research_mode,
            agent_plan=list(AGENT_NAMES),
            agent_results=results,
            warnings=_copy_warnings(state),
            evidence=list(state.get("evidence") or []),
            trends=list(state.get("trends") or []),
            competitors=list(state.get("competitors") or []),
            customers=list(state.get("customers") or []),
            opportunities=list(state.get("opportunities") or []),
        )
    except Exception as exc:  # noqa: BLE001 - malformed input must be observable
        result = _result(
            "supervisor",
            status="error",
            output={},
            error_kind=classify_model_error(exc),
            error=str(exc),
        )
        return _with_agent_result(state, "supervisor", result)


def _research_node(
    state: EcommerceAgentState,
    *,
    agent: str,
    label: str,
    module: str,
    worker: Any,
    output_key: str,
    model_type: Any,
    provider: ResearchProvider,
) -> EcommerceAgentState:
    """Run exactly one existing research role and degrade only that role."""

    try:
        request = _request(state)
        values, new_evidence = worker(provider).run(request)
        json_values = [_json_value(value) for value in values]
        evidence_ids = [str(item.evidence_id) for item in new_evidence]
        status = "partial" if _module_status(provider, module) == "fallback" else "success"
        warnings = list(getattr(provider, "warnings", []) or [])
        result = _result(
            agent,
            status=status,
            output=json_values,
            evidence_ids=evidence_ids,
            warnings=warnings,
        )
        return _with_agent_result(
            state,
            agent,
            result,
            **{
                output_key: json_values,
                "evidence": _merge_evidence(list(state.get("evidence") or []), new_evidence),
                "warnings": _provider_warnings(provider, state),
            },
        )
    except Exception as exc:  # noqa: BLE001 - one provider module must not stop the graph
        warning = f"{label}模块失败，已降级继续：{exc}"
        warnings = _copy_warnings(state)
        _append_unique(warnings, [warning])
        result = _result(
            agent,
            status="error",
            output=[],
            warnings=[warning],
            error_kind=classify_model_error(exc),
            error=str(exc),
        )
        return _with_agent_result(
            state,
            agent,
            result,
            **{output_key: [], "warnings": warnings},
        )


def _market_node(state: EcommerceAgentState, *, provider: ResearchProvider) -> EcommerceAgentState:
    return _research_node(
        state,
        agent="market",
        label="市场趋势",
        module="market",
        worker=MarketResearch,
        output_key="trends",
        model_type=TrendSignal,
        provider=provider,
    )


def _competitor_node(
    state: EcommerceAgentState, *, provider: ResearchProvider
) -> EcommerceAgentState:
    return _research_node(
        state,
        agent="competitor",
        label="竞品分析",
        module="competitor",
        worker=CompetitorResearch,
        output_key="competitors",
        model_type=CompetitorInsight,
        provider=provider,
    )


def _customer_node(state: EcommerceAgentState, *, provider: ResearchProvider) -> EcommerceAgentState:
    return _research_node(
        state,
        agent="customer",
        label="用户画像",
        module="customer",
        worker=CustomerResearch,
        output_key="customers",
        model_type=CustomerProfile,
        provider=provider,
    )


def _risk_node(state: EcommerceAgentState, *, provider: ResearchProvider) -> EcommerceAgentState:
    return _research_node(
        state,
        agent="risk",
        label="机会风险",
        module="opportunity",
        worker=OpportunityRiskAnalysis,
        output_key="opportunities",
        model_type=OpportunityRisk,
        provider=provider,
    )


def _price_node(state: EcommerceAgentState) -> EcommerceAgentState:
    """Derive price anchors from competitor output without any provider call."""

    try:
        competitors = [
            CompetitorInsight.model_validate(item)
            for item in (state.get("competitors") or [])
        ]
        prices = [
            float(item.price)
            for item in competitors
            if item.price > 0 and item.price_source != "request_midpoint"
        ]
        request = _request(state)
        if prices:
            anchor = float(median(prices))
            source = "competitor_price_anchor"
            basis = f"基于 {len(prices)} 个竞品价格锚点的中位数 ¥{anchor:.0f}。"
            status = "success"
        else:
            anchor = (request.price_min + request.price_max) / 2
            source = "request_midpoint_assumption"
            basis = f"未提取到明确竞品价格，暂以输入区间中点 ¥{anchor:.0f} 估算。"
            status = "partial"
        anchors = {
            "prices": prices,
            "median": round(anchor, 2),
            "min": round(min(prices), 2) if prices else None,
            "max": round(max(prices), 2) if prices else None,
            "source": source,
            "basis": basis,
        }
        evidence_ids = sorted(
            {
                evidence_id
                for competitor in competitors
                for evidence_id in competitor.evidence_ids
            }
        )
        result = _result(
            "price",
            status=status,
            output=anchors,
            evidence_ids=evidence_ids,
        )
        return _with_agent_result(state, "price", result, price_anchors=anchors)
    except Exception as exc:  # noqa: BLE001 - price derivation must not block reporting
        result = _result(
            "price",
            status="error",
            output={},
            error_kind=classify_model_error(exc),
            error=str(exc),
        )
        return _with_agent_result(state, "price", result, price_anchors={})


def _report_node(state: EcommerceAgentState) -> EcommerceAgentState:
    try:
        request = _request(state)
        trends = [TrendSignal.model_validate(item) for item in (state.get("trends") or [])]
        competitors = [
            CompetitorInsight.model_validate(item)
            for item in (state.get("competitors") or [])
        ]
        customers = [
            CustomerProfile.model_validate(item)
            for item in (state.get("customers") or [])
        ]
        opportunities = [
            OpportunityRisk.model_validate(item)
            for item in (state.get("opportunities") or [])
        ]
        evidence = [Evidence.model_validate(item) for item in (state.get("evidence") or [])]
        warnings = list(state.get("warnings") or [])
        report = ReportGenerator().generate(
            request,
            trends,
            competitors,
            customers,
            opportunities,
            evidence,
            warnings,
            research_mode=str(state.get("research_mode", "Mock")),
        )
        report_json = report.model_dump(mode="json")
        result = _result(
            "report",
            status="success",
            output=report_json,
            evidence_ids=[item.evidence_id for item in evidence],
        )
        return _with_agent_result(
            state,
            "report",
            result,
            report=report_json,
            markdown=_render_markdown(
                report,
                search_status=str(state.get("search_status", "not_used")),
            ),
        )
    except Exception as exc:  # noqa: BLE001 - reviewer still receives a visible failure
        result = _result(
            "report",
            status="error",
            output={},
            error_kind=classify_model_error(exc),
            error=str(exc),
        )
        return _with_agent_result(state, "report", result, report={}, markdown="")


def _reviewer_node(state: EcommerceAgentState) -> EcommerceAgentState:
    try:
        report = FinalReport.model_validate(state.get("report") or {})
        added_warnings = Reviewer().review(report)
        _append_unique(report.warnings, added_warnings)
        warnings = list(state.get("warnings") or [])
        _append_unique(warnings, added_warnings)
        report_json = report.model_dump(mode="json")
        result = _result(
            "reviewer",
            status="success",
            output={"warnings_added": added_warnings, "report": report_json},
            evidence_ids=[item.evidence_id for item in report.evidence],
            warnings=added_warnings,
        )
        return _with_agent_result(
            state,
            "reviewer",
            result,
            report=report_json,
            warnings=warnings,
            markdown=_render_markdown(
                report,
                search_status=str(state.get("search_status", "not_used")),
            ),
        )
    except Exception as exc:  # noqa: BLE001 - preserve an inspectable final state
        result = _result(
            "reviewer",
            status="error",
            output={},
            error_kind=classify_model_error(exc),
            error=str(exc),
        )
        return _with_agent_result(state, "reviewer", result)


def build_ecommerce_agent_graph(
    provider: ResearchProvider | None = None,
    *,
    research_mode: str = "Mock",
):
    """Build the isolated, serial e-commerce agent graph."""

    active_provider = provider if provider is not None else MockResearchProvider()
    builder = StateGraph(EcommerceAgentState)
    builder.add_node(
        "supervisor", lambda state: _supervisor_node(state, research_mode=research_mode)
    )
    builder.add_node("market", lambda state: _market_node(state, provider=active_provider))
    builder.add_node(
        "competitor", lambda state: _competitor_node(state, provider=active_provider)
    )
    builder.add_node("price", _price_node)
    builder.add_node("customer", lambda state: _customer_node(state, provider=active_provider))
    builder.add_node("risk", lambda state: _risk_node(state, provider=active_provider))
    builder.add_node("report", _report_node)
    builder.add_node("reviewer", _reviewer_node)

    previous = START
    for agent in AGENT_NAMES:
        builder.add_edge(previous, agent)
        previous = agent
    builder.add_edge(previous, END)
    return builder.compile()


def run_ecommerce_agent_graph(
    request: EcommerceResearchRequest | Mapping[str, Any] | str | None = None,
    provider: ResearchProvider | None = None,
    research_mode: str = "Mock",
) -> EcommerceAgentState:
    """Run the serial e-commerce agent graph and return its JSON-friendly state."""

    request_model = _request_from_input(request)
    graph = build_ecommerce_agent_graph(provider, research_mode=research_mode)
    initial_state: EcommerceAgentState = {
        "request": request_model.model_dump(mode="json"),
        "research_mode": research_mode,
        "agent_plan": list(AGENT_NAMES),
        "agent_results": {},
        "warnings": [],
        "evidence": [],
        "trends": [],
        "competitors": [],
        "customers": [],
        "opportunities": [],
    }
    return graph.invoke(initial_state)


__all__ = [
    "AGENT_NAMES",
    "EcommerceAgentState",
    "build_ecommerce_agent_graph",
    "run_ecommerce_agent_graph",
]
