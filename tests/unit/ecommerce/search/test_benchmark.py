from __future__ import annotations

from datetime import datetime, timezone

from src.ecommerce.search.benchmark import compare_benchmark_runs, run_search_benchmark
from src.ecommerce.search.models import SearchResult


class BenchmarkProvider:
    request_count = 0
    parallel_safe = True

    def search(self, query: str, *, max_results: int = 5):
        self.request_count += 1
        now = datetime.now(timezone.utc)
        return [
            SearchResult(
                title="京东商品结果",
                url="https://item.jd.com/1001.html",
                snippet="商品摘要，售价 ¥129。",
                source="unit",
                score=0.9,
                retrieved_at=now,
                published_at=now,
                price=129,
            ),
            SearchResult(
                title="外部讨论结果",
                url="https://unknown.example/discussion",
                snippet="用户讨论摘要。",
                source="unit",
                score=0.8,
                retrieved_at=now,
            ),
        ][:max_results]


def test_search_benchmark_aggregates_gate_and_module_metrics():
    result = run_search_benchmark(
        ["可折叠露营桌", "便携榨汁杯"],
        provider_factory=BenchmarkProvider,
        max_results=2,
    )

    assert result.summary.category_count == 2
    assert result.summary.search_success_rate == 1.0
    assert result.summary.interface_success_rate == 1.0
    assert result.summary.evidence_usable_rate == 0.0
    assert result.summary.commercial_decision_ready_rate == 0.0
    assert result.summary.failure_reason_counts == {}
    assert result.parallel_modules is False
    assert result.summary.module_averages["market"]["mainland_source_rate"] == 0.5
    assert result.summary.module_averages["competitor"]["price_coverage"] == 0.5
    assert result.summary.source_filter_exhausted_case_count == 0


def test_search_benchmark_applies_source_profile():
    result = run_search_benchmark(
        ["桌面收纳盒"],
        source_profile="conservative-mainland",
        provider_factory=BenchmarkProvider,
        max_results=2,
    )

    assert result.source_policy == "filter"
    assert result.source_profile == "conservative-mainland"
    assert result.cases[0].module_details["market"]["result_count"] == 1
    assert result.cases[0].module_details["market"]["filtered_source_count"] == 1


def test_search_benchmark_comparison_returns_candidate_deltas():
    baseline = run_search_benchmark(["可折叠露营桌"], provider_factory=BenchmarkProvider, max_results=2)
    candidate = run_search_benchmark(
        ["可折叠露营桌"],
        source_profile="conservative-mainland",
        provider_factory=BenchmarkProvider,
        max_results=2,
    )

    comparison = compare_benchmark_runs(baseline, candidate)

    assert comparison.category_overlap == ["可折叠露营桌"]
    assert comparison.module_deltas["market"]["filtered_source_count"] == 1.0
    assert comparison.module_deltas["market"]["mainland_source_rate"] == 0.5
