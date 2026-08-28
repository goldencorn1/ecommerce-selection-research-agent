"""Multi-category benchmark runner for real-search ecommerce runs."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.ecommerce_graph import run_ecommerce_graph

from .adapters import TavilySearchProvider
from .models import SearchProvider
from .source_policies import get_source_policy_template


DEFAULT_CATEGORIES = ("可折叠露营桌", "便携榨汁杯", "桌面收纳盒")
MODULES = ("market", "competitor", "customer", "opportunity")


class SearchBenchmarkCase(BaseModel):
    """One category's search-only benchmark result."""

    model_config = ConfigDict(extra="forbid")

    category: str
    search_status: str
    quality_level: str
    quality_gates: dict[str, bool]
    latency_ms: float = Field(ge=0)
    warning_count: int = Field(ge=0)
    module_details: dict[str, dict[str, Any]]


class SearchBenchmarkSummary(BaseModel):
    """Aggregate metrics; these do not establish market truth."""

    model_config = ConfigDict(extra="forbid")

    category_count: int = Field(ge=0)
    search_success_rate: float = Field(ge=0, le=1)
    interface_success_rate: float = Field(ge=0, le=1)
    evidence_usable_rate: float = Field(ge=0, le=1)
    commercial_decision_ready_rate: float = Field(ge=0, le=1)
    average_latency_ms: float = Field(ge=0)
    average_warning_count: float = Field(ge=0)
    source_filter_exhausted_case_count: int = Field(ge=0)
    failure_reason_counts: dict[str, int] = Field(default_factory=dict)
    module_averages: dict[str, dict[str, float]]


class SearchBenchmarkRun(BaseModel):
    """Serializable multi-category search benchmark."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "real-search"
    source_policy: str
    source_profile: str | None = None
    parallel_modules: bool = False
    cases: list[SearchBenchmarkCase]
    summary: SearchBenchmarkSummary

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SearchBenchmarkComparison(BaseModel):
    """Numeric deltas between two saved benchmark runs."""

    model_config = ConfigDict(extra="forbid")

    baseline_path: str
    candidate_path: str
    category_overlap: list[str]
    summary_deltas: dict[str, float]
    module_deltas: dict[str, dict[str, float]]

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _module_averages(cases: Iterable[SearchBenchmarkCase]) -> dict[str, dict[str, float]]:
    values: dict[str, dict[str, list[float]]] = {
        module: {
            "result_count": [],
            "raw_result_count": [],
            "mainland_source_rate": [],
            "unknown_source_rate": [],
            "price_coverage": [],
            "published_result_rate": [],
            "filtered_source_count": [],
        }
        for module in MODULES
    }
    for case in cases:
        for module in MODULES:
            details = case.module_details.get(module, {})
            result_count = int(details.get("result_count", 0) or 0)
            raw_result_count = int(details.get("raw_result_count", 0) or 0)
            values[module]["result_count"].append(float(result_count))
            values[module]["raw_result_count"].append(float(raw_result_count))
            values[module]["mainland_source_rate"].append(
                _ratio(int(details.get("mainland_relevant_count", 0) or 0), result_count)
            )
            values[module]["unknown_source_rate"].append(
                _ratio(int(details.get("unknown_source_count", 0) or 0), result_count)
            )
            values[module]["price_coverage"].append(
                float(details.get("price_coverage", 0.0) or 0.0)
            )
            values[module]["published_result_rate"].append(
                _ratio(int(details.get("published_result_count", 0) or 0), result_count)
            )
            values[module]["filtered_source_count"].append(
                float(details.get("filtered_source_count", 0) or 0)
            )
    return {
        module: {
            metric: round(sum(samples) / len(samples), 4) if samples else 0.0
            for metric, samples in metrics.items()
        }
        for module, metrics in values.items()
    }


def compare_benchmark_runs(
    baseline: SearchBenchmarkRun,
    candidate: SearchBenchmarkRun,
    *,
    baseline_path: str = "baseline",
    candidate_path: str = "candidate",
) -> SearchBenchmarkComparison:
    """Compare saved runs and return candidate-minus-baseline deltas."""

    baseline_categories = {case.category for case in baseline.cases}
    candidate_categories = {case.category for case in candidate.cases}
    summary_fields = (
        "search_success_rate",
        "interface_success_rate",
        "evidence_usable_rate",
        "commercial_decision_ready_rate",
        "average_latency_ms",
        "average_warning_count",
        "source_filter_exhausted_case_count",
    )
    summary_deltas = {
        field: round(
            float(getattr(candidate.summary, field)) - float(getattr(baseline.summary, field)),
            4,
        )
        for field in summary_fields
    }
    module_deltas: dict[str, dict[str, float]] = {}
    for module in MODULES:
        baseline_metrics = baseline.summary.module_averages.get(module, {})
        candidate_metrics = candidate.summary.module_averages.get(module, {})
        metric_names = set(baseline_metrics) | set(candidate_metrics)
        module_deltas[module] = {
            metric: round(
                float(candidate_metrics.get(metric, 0.0))
                - float(baseline_metrics.get(metric, 0.0)),
                4,
            )
            for metric in sorted(metric_names)
        }
    return SearchBenchmarkComparison(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
        category_overlap=sorted(baseline_categories & candidate_categories),
        summary_deltas=summary_deltas,
        module_deltas=module_deltas,
    )


def run_search_benchmark(
    categories: Iterable[str],
    *,
    source_policy: str = "annotate",
    source_profile: str | None = None,
    timeout: float = 25.0,
    max_results: int = 3,
    max_parallel_searches: int = 2,
    parallel_modules: bool = False,
    max_retries: int = 1,
    retry_backoff: float = 0.25,
    provider_factory: Callable[[], SearchProvider] | None = None,
) -> SearchBenchmarkRun:
    """Run the search path for each category without invoking a report LLM."""

    normalized_categories = tuple(dict.fromkeys(item.strip() for item in categories if item.strip()))
    if not normalized_categories:
        raise ValueError("at least one category is required")
    module_allowlist: dict[str, list[str]] = {}
    effective_policy = source_policy
    if source_profile:
        template = get_source_policy_template(source_profile)
        module_allowlist = dict(template["source_domain_allowlist_by_module"])
        if source_policy == "annotate":
            effective_policy = str(template["source_policy"])

    cases: list[SearchBenchmarkCase] = []
    for category in normalized_categories:
        provider = (
            provider_factory()
            if provider_factory is not None
            else TavilySearchProvider(
                timeout=timeout,
                max_retries=max_retries,
                retry_backoff=retry_backoff,
            )
        )
        started = time.perf_counter()
        state = run_ecommerce_graph(
            {
                "category": category,
                "search_enabled": True,
                "search_provider": provider,
                "search_config": {
                    "max_results": max_results,
                    "parallel_modules": parallel_modules,
                    "max_parallel_searches": max_parallel_searches,
                    "source_policy": effective_policy,
                    "source_domain_allowlist_by_module": module_allowlist,
                },
            }
        )
        metrics = state.get("ecommerce_metrics", {})
        cases.append(
            SearchBenchmarkCase(
                category=category,
                search_status=str(state.get("ecommerce_search_status", "not_used")),
                quality_level=str(metrics.get("quality_level", "not_assessed")),
                quality_gates=dict(metrics.get("quality_gates", {})),
                latency_ms=round(
                    float(metrics.get("latency_ms", (time.perf_counter() - started) * 1000)), 4
                ),
                warning_count=len(state.get("ecommerce_report", {}).get("warnings", [])),
                module_details={
                    module: dict(details)
                    for module, details in state.get("ecommerce_search_details", {}).items()
                },
            )
        )

    denominator = len(cases)
    failure_reason_counts: dict[str, int] = {}
    for case in cases:
        for details in case.module_details.values():
            reason = details.get("fallback_reason")
            if reason:
                failure_reason_counts[str(reason)] = failure_reason_counts.get(str(reason), 0) + 1
    summary = SearchBenchmarkSummary(
        category_count=denominator,
        search_success_rate=_ratio(sum(case.search_status == "success" for case in cases), denominator),
        interface_success_rate=_ratio(
            sum(case.quality_gates.get("interface_success", False) for case in cases), denominator
        ),
        evidence_usable_rate=_ratio(
            sum(case.quality_gates.get("evidence_usable", False) for case in cases), denominator
        ),
        commercial_decision_ready_rate=_ratio(
            sum(case.quality_gates.get("commercial_decision_ready", False) for case in cases), denominator
        ),
        average_latency_ms=round(sum(case.latency_ms for case in cases) / denominator, 4),
        average_warning_count=round(sum(case.warning_count for case in cases) / denominator, 4),
        source_filter_exhausted_case_count=sum(
            any(bool(details.get("source_filter_exhausted")) for details in case.module_details.values())
            for case in cases
        ),
        failure_reason_counts=failure_reason_counts,
        module_averages=_module_averages(cases),
    )
    return SearchBenchmarkRun(
        source_policy=effective_policy,
        source_profile=source_profile,
        parallel_modules=parallel_modules,
        cases=cases,
        summary=summary,
    )


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="运行多品类电商真实搜索基准，不调用 DeepSeek")
    parser.add_argument("--category", action="append", dest="categories", help="可重复传入多个品类")
    parser.add_argument("--categories", dest="categories_csv", help="逗号分隔的品类列表")
    parser.add_argument("--search-source-policy", choices=("annotate", "filter"), default="annotate")
    parser.add_argument("--search-source-profile", choices=("", "conservative-mainland"), default="")
    parser.add_argument("--search-timeout", type=float, default=25.0)
    parser.add_argument("--search-max-results", type=int, default=3)
    parser.add_argument("--search-parallel-workers", type=int, default=2)
    parser.add_argument("--search-parallel", action="store_true", help="显式启用并行模块搜索；默认串行以优先保证稳定性")
    parser.add_argument("--search-max-retries", type=int, default=1)
    parser.add_argument("--search-retry-backoff", type=float, default=0.25)
    parser.add_argument("--search-preflight", action="store_true", help="先用一个查询验证搜索 API，再运行基准")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--compare-baseline", type=Path, default=None)
    parser.add_argument("--compare-candidate", type=Path, default=None)
    args = parser.parse_args()

    if bool(args.compare_baseline) != bool(args.compare_candidate):
        parser.error("--compare-baseline and --compare-candidate must be used together")
    if args.compare_baseline and args.compare_candidate:
        baseline = SearchBenchmarkRun.model_validate_json(args.compare_baseline.read_text(encoding="utf-8"))
        candidate = SearchBenchmarkRun.model_validate_json(args.compare_candidate.read_text(encoding="utf-8"))
        print(json.dumps(
            compare_benchmark_runs(
                baseline,
                candidate,
                baseline_path=str(args.compare_baseline),
                candidate_path=str(args.compare_candidate),
            ).to_json_dict(),
            ensure_ascii=False,
            indent=2 if args.pretty else None,
        ))
        return

    try:
        from dotenv import load_dotenv

        load_dotenv(Path.cwd() / ".env")
    except ImportError:
        pass
    categories = args.categories or (
        [item.strip() for item in args.categories_csv.split(",") if item.strip()]
        if args.categories_csv
        else list(DEFAULT_CATEGORIES)
    )
    if args.search_preflight:
        from .preflight import run_search_preflight

        preflight = run_search_preflight(
            f"{categories[0]} 中国大陆电商 商品销量 价格带 用户需求 2025 2026",
            timeout=args.search_timeout,
            max_retries=args.search_max_retries,
            retry_backoff=args.search_retry_backoff,
            max_results=1,
        )
        if preflight["status"] != "success":
            print(json.dumps({"mode": "preflight", **preflight}, ensure_ascii=False, indent=2))
            raise SystemExit(2)
    result = run_search_benchmark(
        categories,
        source_policy=args.search_source_policy,
        source_profile=args.search_source_profile or None,
        timeout=args.search_timeout,
        max_results=args.search_max_results,
        max_parallel_searches=args.search_parallel_workers,
        parallel_modules=args.search_parallel,
        max_retries=args.search_max_retries,
        retry_backoff=args.search_retry_backoff,
    )
    serialized = json.dumps(result.to_json_dict(), ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
