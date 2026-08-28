"""LangGraph entry point for the offline e-commerce product research MVP."""

from __future__ import annotations

import os
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.ecommerce import EcommerceResearchRequest
from src.ecommerce.providers import SearchBackedResearchProvider
from src.ecommerce.provenance import (
    citation_completeness,
    evidence_to_provenance,
    read_verification_records,
    report_fingerprint,
    validate_verification_records,
)
from src.ecommerce.search import SearchProvider, build_search_provider
from src.ecommerce.byok import scrub_runtime_credentials
from src.ecommerce.telemetry import run_instrumented_research
from datetime import datetime, timezone
from src.graph.types import State


class _UnavailableReportEnhancer:
    """Turn model-client initialization failures into normal model fallback."""

    def __init__(self, error: Exception):
        self.error = error
        self.usage = None

    def enhance(self, report):
        # ``run_research`` already has the public fallback contract for errors
        # raised by an enhancer. Reuse it for constructor failures as well.
        raise self.error


def _request_from_state(state: State) -> EcommerceResearchRequest:
    request = state.get("ecommerce_request") or {}
    if isinstance(request, str):
        return EcommerceResearchRequest(category=request)
    if isinstance(request, dict):
        return EcommerceResearchRequest.model_validate(request)
    return EcommerceResearchRequest(category=state.get("research_topic") or "便携榨汁杯")


def ecommerce_research_node(state: State) -> dict[str, Any]:
    """Run the deterministic MVP and adapt its output to DeerFlow State."""

    request = _request_from_state(state)
    search_config = state.get("ecommerce_search_config") or {}
    model_config = state.get("ecommerce_model_config") or {}
    data_config = state.get("ecommerce_data_config") or {}
    runtime_credentials = state.get("ecommerce_runtime_credentials") or {}
    knowledge_config = state.get("ecommerce_knowledge_config") or {}
    search_provider: SearchProvider | None = None
    mode = "mock"
    if search_config.get("enabled"):
        search_options = dict(search_config)
        search_runtime = runtime_credentials.get("search") or {}
        if search_runtime.get("api_key"):
            search_options["api_key"] = search_runtime["api_key"]
            search_options["api_key_env"] = ""
        search_provider = search_options.get("provider")
        if search_provider is None or isinstance(search_provider, str):
            search_provider = build_search_provider(search_options)
        content_enricher = None
        if data_config.get("provider") == "infoquest":
            from src.ecommerce.product_data import InfoQuestProductEnricher

            content_enricher = InfoQuestProductEnricher(
                max_pages=int(data_config.get("max_pages", 3)),
                api_key=(runtime_credentials.get("data") or {}).get("api_key"),
            )
        provider = SearchBackedResearchProvider(
            search_provider,
            max_results=int(search_config.get("max_results", 5)),
            min_score=float(search_config.get("min_score", 0.0)),
            max_age_days=(
                int(search_config["max_age_days"])
                if search_config.get("max_age_days") is not None
                else None
            ),
            cache_ttl_seconds=float(search_config.get("cache_ttl_seconds", 0.0)),
            cache_max_entries=int(search_config.get("cache_max_entries", 128)),
            parallel_modules=bool(search_config.get("parallel_modules", False)),
            max_parallel_searches=int(search_config.get("max_parallel_searches", 4)),
            source_domain_allowlist=tuple(search_config.get("source_domain_allowlist", ())),
            source_domain_allowlist_by_module=search_config.get(
                "source_domain_allowlist_by_module", {}
            ),
            source_policy=str(search_config.get("source_policy", "annotate")),
            content_enricher=content_enricher,
        )
        mode = "search"
    else:
        provider = None
    report_enhancer = None
    verification_records = None
    verification_file = model_config.get("verification_file")
    if verification_file:
        verification_records = read_verification_records(verification_file)
    if model_config.get("enabled"):
        from src.ecommerce.llm_report import DeepSeekReportEnhancer

        model_runtime = runtime_credentials.get("model") or {}
        try:
            if model_runtime:
                from src.ecommerce.model_provider import build_request_model

                report_enhancer = DeepSeekReportEnhancer(
                    llm=build_request_model(
                        {
                            "provider": model_config.get("provider", "deepseek"),
                            **model_runtime,
                        }
                    )
                )
            else:
                # Keep server-side configuration as a compatibility fallback,
                # but do not let a missing global key abort the whole report.
                report_enhancer = DeepSeekReportEnhancer()
        except Exception as exc:  # noqa: BLE001 - model fallback is intentional
            # The enhancer will raise inside run_research, where the existing
            # model fallback path records a safe error kind and keeps the
            # deterministic report. Never include the exception text because
            # provider errors can contain request-specific details.
            report_enhancer = _UnavailableReportEnhancer(exc)
        mode = f"{mode}+deepseek"
    knowledge_retriever = None
    knowledge_error: str | None = None
    if knowledge_config:
        try:
            from src.ecommerce.knowledge.integration import build_knowledge_retriever

            knowledge_retriever = build_knowledge_retriever(knowledge_config)
        except Exception as exc:  # noqa: BLE001 - private knowledge is optional
            knowledge_error = str(exc)
    result, metrics = run_instrumented_research(
        request,
        provider=provider,
        mode=mode,
        report_enhancer=report_enhancer,
        input_cost_per_million=float(
            model_config.get("input_cost_per_million", os.getenv("DEEPSEEK_INPUT_COST_USD_PER_MILLION", 0))
        ),
        output_cost_per_million=float(
            model_config.get("output_cost_per_million", os.getenv("DEEPSEEK_OUTPUT_COST_USD_PER_MILLION", 0))
        ),
        verification_records=verification_records,
        knowledge_retriever=knowledge_retriever,
        knowledge_top_k=int(knowledge_config.get("top_k", 3)),
    )
    if knowledge_error:
        warning = f"私有知识加载失败，已保留现有研究结果：{knowledge_error}"
        if warning not in result.report.warnings:
            result.report.warnings.append(warning)
    report_json = result.report.model_dump(mode="json")
    provenance = [
        evidence_to_provenance(
            evidence,
            retrieved_at=datetime.now(timezone.utc),
            source_type="mock" if evidence.source.startswith("mock://") else "search",
        )
        for evidence in result.report.evidence
    ]
    citation_validation = citation_completeness(result.report, provenance)
    observations = [result.report.executive_summary, result.markdown]
    citations = [evidence for evidence in report_json["evidence"]]
    return {
        "research_topic": request.category,
        "ecommerce_request": request.model_dump(mode="json"),
        "ecommerce_runtime_credentials": {},
        "ecommerce_report": report_json,
        "ecommerce_report_fingerprint": report_fingerprint(result.report),
        "ecommerce_model_status": result.model_status,
        "ecommerce_model_error_kind": result.model_error_kind,
        "ecommerce_model_usage": result.model_usage,
        "ecommerce_search_status": result.search_status,
        "ecommerce_search_details": result.search_details,
        "ecommerce_knowledge_status": result.knowledge_status,
        "ecommerce_knowledge_details": result.knowledge_details,
        "ecommerce_agent_plan": result.agent_plan,
        "ecommerce_agent_results": result.agent_results,
        "ecommerce_progress_events": [
            item.model_dump(mode="json") for item in result.progress_events
        ],
        "ecommerce_metrics": metrics.to_dict(),
        "ecommerce_verification_records": [
            record.model_dump(mode="json") for record in (verification_records or [])
        ],
        "ecommerce_verification_validation": metrics.verification_validation,
        "ecommerce_provenance": [item.model_dump(mode="json") for item in provenance],
        "ecommerce_citation_validation": citation_validation.model_dump(mode="json"),
        "final_report": result.markdown,
        "observations": observations,
        "citations": citations,
        "messages": [
            {
                "role": "assistant",
                "content": result.report.executive_summary,
                "name": "ecommerce_reviewer",
            }
        ],
    }


def build_ecommerce_graph():
    """Build the isolated MVP graph while reusing DeerFlow's State schema."""

    builder = StateGraph(State)
    builder.add_node("ecommerce_research", ecommerce_research_node)
    builder.add_edge(START, "ecommerce_research")
    builder.add_edge("ecommerce_research", END)
    return builder.compile()


graph = build_ecommerce_graph()


def run_ecommerce_graph(request: EcommerceResearchRequest | dict[str, Any] | str | None = None) -> dict[str, Any]:
    """Run the MVP graph synchronously and return its final DeerFlow state."""

    if request is None:
        payload: dict[str, Any] = {}
    elif isinstance(request, str):
        payload = {"category": request}
    elif isinstance(request, EcommerceResearchRequest):
        payload = request.model_dump(mode="json")
    else:
        payload = dict(request)
    search_enabled = bool(payload.pop("search_enabled", False))
    runtime_credentials = payload.pop("_ecommerce_runtime_credentials", {}) or {}
    search_config = payload.pop("search_config", {}) or {}
    model_config = payload.pop("model_config", {}) or {}
    search_provider = payload.pop("search_provider", None)
    knowledge_config = payload.pop("knowledge_config", {}) or {}
    data_config = payload.pop("data_config", {}) or {}
    if search_provider is not None:
        search_config["provider"] = search_provider
    search_config["enabled"] = search_enabled
    initial_state: dict[str, Any] = {
        "messages": [],
        "research_topic": payload.get("category", "便携榨汁杯"),
        "ecommerce_request": payload,
        "ecommerce_search_config": search_config,
        "ecommerce_model_config": model_config,
        "ecommerce_knowledge_config": knowledge_config,
        "ecommerce_data_config": data_config,
        "ecommerce_runtime_credentials": runtime_credentials,
    }
    try:
        return graph.invoke(initial_state)
    finally:
        scrub_runtime_credentials(runtime_credentials)


def run_ecommerce_report_snapshot(
    report_file: str | os.PathLike[str],
    *,
    verification_file: str | os.PathLike[str] | None = None,
    max_age_days: int = 30,
) -> dict[str, Any]:
    """Replay a saved report without calling search or a language model."""

    started = perf_counter()
    saved_payload = json.loads(Path(report_file).read_text(encoding="utf-8"))
    report_payload = saved_payload.get("report", saved_payload)
    from src.ecommerce.models import FinalReport
    from src.ecommerce.orchestration import ResearchResult, _render_markdown
    from src.ecommerce.telemetry import (
        RunMetrics,
        assess_quality_gates,
        assess_report_quality,
        estimate_tokens,
    )

    report = FinalReport.model_validate(report_payload)
    fingerprint = report_fingerprint(report)
    expected_saved_fingerprint = saved_payload.get("report_fingerprint")
    fingerprint_warning = []
    if expected_saved_fingerprint and expected_saved_fingerprint != fingerprint:
        fingerprint_warning.append("保存文件中的 report_fingerprint 与报告内容不一致。")
    records = read_verification_records(verification_file) if verification_file else []
    validation = validate_verification_records(
        report,
        records,
        max_age_days=max_age_days,
        valid_evidence_ids={item.evidence_id for item in report.evidence},
        citation_complete=bool(
            saved_payload.get("citation_validation", {}).get(
                "complete",
                saved_payload.get("ecommerce_citation_validation", {}).get("complete", True),
            )
        ),
        expected_report_fingerprint=fingerprint,
    )
    if fingerprint_warning:
        validation.blocking_reasons.extend(fingerprint_warning)
        validation.complete = False
    search_status = str(saved_payload.get("search_status", "not_used"))
    search_details = dict(saved_payload.get("search_details", {}))
    result = ResearchResult(
        report=report,
        markdown=_render_markdown(report, search_status=search_status),
        warnings=report.warnings,
        research_mode="Snapshot",
        search_status=search_status,
        search_details=search_details,
    )
    quality_level, quality_gates = assess_quality_gates(
        result, validation.model_dump(mode="json")
    )
    metrics = RunMetrics(
        mode="snapshot",
        status="success",
        latency_ms=(perf_counter() - started) * 1000,
        input_chars=0,
        output_chars=len(result.markdown),
        estimated_input_tokens=0,
        estimated_output_tokens=estimate_tokens(result.markdown),
        estimated_cost_usd=0.0,
        warning_count=len(report.warnings) + len(fingerprint_warning),
        cost_note="报告快照复用未调用搜索或模型 API；成本为 0。",
        overall_status="degraded" if fingerprint_warning else "success",
        model_status="not_used",
        search_status=search_status,
        quality_level=quality_level,
        quality_gates=quality_gates,
        report_quality_gates=assess_report_quality(result),
        verification_validation=validation.model_dump(mode="json"),
    )
    provenance = [
        evidence_to_provenance(
            evidence,
            retrieved_at=evidence.retrieved_at or datetime.now(timezone.utc),
            source_type="mock" if evidence.source.startswith("mock://") else "search",
        )
        for evidence in report.evidence
    ]
    return {
        "research_topic": report.request.category,
        "ecommerce_request": report.request.model_dump(mode="json"),
        "ecommerce_report": report.model_dump(mode="json"),
        "ecommerce_report_fingerprint": fingerprint,
        "ecommerce_model_status": "not_used",
        "ecommerce_model_error_kind": None,
        "ecommerce_model_usage": {},
        "ecommerce_search_status": search_status,
        "ecommerce_search_details": search_details,
        "ecommerce_knowledge_status": str(saved_payload.get("knowledge_status", "not_used")),
        "ecommerce_knowledge_details": dict(saved_payload.get("knowledge_details", {})),
        "ecommerce_agent_plan": list(saved_payload.get("agent_plan", [])),
        "ecommerce_agent_results": dict(saved_payload.get("agent_results", {})),
        "ecommerce_metrics": metrics.to_dict(),
        "ecommerce_verification_records": [
            record.model_dump(mode="json") for record in records
        ],
        "ecommerce_verification_validation": validation.model_dump(mode="json"),
        "ecommerce_provenance": [item.model_dump(mode="json") for item in provenance],
        "ecommerce_citation_validation": saved_payload.get(
            "citation_validation",
            saved_payload.get("ecommerce_citation_validation", {}),
        ),
        "final_report": result.markdown,
        "observations": [report.executive_summary, result.markdown],
        "citations": [item.model_dump(mode="json") for item in report.evidence],
        "messages": [
            {
                "role": "assistant",
                "content": report.executive_summary,
                "name": "ecommerce_reviewer",
            }
        ],
    }
