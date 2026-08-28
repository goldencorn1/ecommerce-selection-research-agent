from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, get_type_hints

from src.ecommerce.agent_graph import (
    AGENT_NAMES,
    EcommerceAgentState,
    build_ecommerce_agent_graph,
    run_ecommerce_agent_graph,
)
from src.ecommerce.providers import MockResearchProvider


REQUEST = {
    "category": "可折叠露营桌",
    "target_market": "中国大陆电商",
    "price_min": 99,
    "price_max": 299,
    "top_n": 3,
}


def _result_status(result: Any) -> str | None:
    if isinstance(result, Mapping):
        return result.get("status")
    return getattr(result, "status", None)


def _evidence_ids(value: Any) -> set[str]:
    """Collect evidence IDs from nested, JSON-shaped agent results."""

    if isinstance(value, Mapping):
        evidence_ids: set[str] = set()
        for key, item in value.items():
            if key == "evidence_id" and isinstance(item, str):
                evidence_ids.add(item)
            elif key == "evidence_ids" and isinstance(item, list):
                evidence_ids.update(
                    identifier for identifier in item if isinstance(identifier, str)
                )
            evidence_ids.update(_evidence_ids(item))
        return evidence_ids
    if isinstance(value, list):
        evidence_ids = set()
        for item in value:
            evidence_ids.update(_evidence_ids(item))
        return evidence_ids
    return set()


def _agent_named(fragment: str, results: Mapping[str, Any]) -> str:
    matches = [name for name in results if fragment in name.lower()]
    assert len(matches) == 1, f"expected one {fragment!r} agent, got {matches!r}"
    return matches[0]


def _warnings(state: Mapping[str, Any], report_result: Any) -> list[str]:
    warnings = state.get("warnings", [])
    if warnings:
        return list(warnings)
    if isinstance(report_result, Mapping):
        for key in ("warnings", "output", "data", "result"):
            value = report_result.get(key)
            if key == "warnings" and isinstance(value, list):
                return list(value)
            if isinstance(value, Mapping) and value.get("warnings"):
                return list(value["warnings"])
    return []


def _agent_plan(state: Mapping[str, Any]) -> list[str]:
    supervisor = state["agent_results"]["supervisor"]
    return list(supervisor["output"]["execution_order"])


def test_a1_state_contract_has_eight_routed_agents():
    annotations = get_type_hints(EcommerceAgentState)
    names = tuple(AGENT_NAMES)

    assert len(names) == 8
    assert len(set(names)) == 8
    assert {"agent_results", "evidence", "warnings"} <= set(annotations)

    graph = build_ecommerce_agent_graph()
    graph_view = graph.get_graph()
    graph_nodes = set(graph_view.nodes)
    assert set(names) <= graph_nodes

    edges = tuple(graph_view.edges)
    for name in names:
        assert any(edge.source == name for edge in edges), (
            f"{name} has no outgoing route"
        )
        assert any(edge.target == name for edge in edges), (
            f"{name} has no incoming route"
        )


def test_mock_provider_completes_all_nodes_with_stable_plan_and_evidence():
    first = run_ecommerce_agent_graph(REQUEST, provider=MockResearchProvider())
    second = run_ecommerce_agent_graph(REQUEST, provider=MockResearchProvider())

    names = set(AGENT_NAMES)
    results = first["agent_results"]
    assert isinstance(results, Mapping)
    assert set(results) == names
    agent_plan = _agent_plan(first)
    assert agent_plan == _agent_plan(second)
    assert agent_plan == list(AGENT_NAMES)
    assert all(_result_status(results[name]) == "success" for name in names)
    json.dumps(results, ensure_ascii=False)

    report_name = _agent_named("report", results)
    reviewer_name = _agent_named("review", results)
    report_result = results[report_name]
    reviewer_result = results[reviewer_name]
    assert _result_status(report_result) == "success"
    assert _result_status(reviewer_result) == "success"
    assert report_result
    assert reviewer_result

    research_names = names - {report_name, reviewer_name}
    research_evidence_ids = _evidence_ids(
        {name: results[name] for name in research_names}
    )
    report_evidence_ids = _evidence_ids(report_result)
    reviewer_evidence_ids = _evidence_ids(reviewer_result)
    assert research_evidence_ids
    assert research_evidence_ids <= report_evidence_ids
    assert reviewer_evidence_ids <= report_evidence_ids


def test_single_provider_module_failure_keeps_report_and_marks_partial_node():
    state = run_ecommerce_agent_graph(
        REQUEST,
        provider=MockResearchProvider(fail_modules={"competitor"}),
    )

    results = state["agent_results"]
    assert set(results) == set(AGENT_NAMES)
    failed_name = _agent_named("compet", results)
    assert _result_status(results[failed_name]) in {"error", "partial"}

    report_name = _agent_named("report", results)
    reviewer_name = _agent_named("review", results)
    assert _result_status(results[report_name]) == "success"
    assert _result_status(results[reviewer_name]) in {"success", "partial"}
    assert results[report_name]
    assert results[reviewer_name]
    assert _warnings(state, results[report_name])
