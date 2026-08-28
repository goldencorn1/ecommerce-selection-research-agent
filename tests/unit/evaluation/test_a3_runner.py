from __future__ import annotations

import json

from src.evaluation.a3_runner import run_a3_evaluation


def test_a3_runner_measures_all_fifty_cases_and_judge_dimensions(tmp_path):
    output = tmp_path / "a3-run.json"
    result = run_a3_evaluation(output_path=output)

    assert result.summary.total_case_count == 50
    assert result.summary.measured_case_count == 50
    assert result.summary.success_rate == 1
    assert result.summary.degraded_case_count > 0
    assert set(result.summary.judge_dimension_averages) == {
        "market",
        "competitor",
        "price",
        "customer",
        "risk",
        "evidence_quality",
        "commercial_boundary",
    }
    assert result.summary.latency_p50_ms > 0
    assert result.summary.latency_p50_ms <= result.summary.latency_p95_ms
    assert result.summary.latency_p95_ms <= result.summary.latency_p99_ms
    assert result.summary.metric_pass_rates["structured_output_validity"] == 1
    assert result.summary.scenario_tag_counts["a3-normal"] > 0
    assert result.summary.mode == "mock"
    assert result.summary.total_external_request_count == 0
    assert result.summary.total_cost_usd == 0
    assert all(case.judge for case in result.cases)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["total_case_count"] == 50
    assert saved["judge_version"] == "ecommerce-judge-v1"
