from __future__ import annotations

from pathlib import Path

from src.ecommerce.models import EcommerceResearchRequest, FinalReport
from src.evaluation.dataset import load_evaluation_cases
from src.evaluation.metrics import (
    category_relevance,
    degradation_warning_quality,
    evidence_coverage,
    report_completeness,
    score_validity,
    structured_output_validity,
)
from src.evaluation.runner import run_evaluation


REPO_ROOT = Path(__file__).resolve().parents[3]


def _empty_report(**overrides) -> FinalReport:
    values = {
        "request": EcommerceResearchRequest(category="测试品类"),
        "executive_summary": "待验证假设",
    }
    values.update(overrides)
    return FinalReport(**values)


def test_loads_at_least_twenty_chinese_cases_with_required_fields():
    cases = load_evaluation_cases()

    assert len(cases) >= 20
    assert len({case.id for case in cases}) == len(cases)
    assert all(case.category and case.target_customer for case in cases)
    assert all(case.expected_sections and case.minimum_evidence_count >= 0 for case in cases)
    assert all(case.budget.maximum >= case.budget.minimum for case in cases)
    assert sum(bool(case.expected_degradation) for case in cases) >= 4
    assert all(set(case.expected_degradation) <= {"market", "competitor", "customer", "opportunity"} for case in cases)


def test_completeness_and_evidence_metrics_cover_empty_boundaries():
    report = _empty_report()

    completeness = report_completeness(report, [])
    evidence = evidence_coverage(report, 0)

    assert completeness.measured == "measured"
    assert completeness.score == 1
    assert completeness.passed is True
    assert evidence.score == 1
    assert evidence.passed is True


def test_completeness_allows_expected_degraded_module_sections():
    report = _empty_report()

    result = report_completeness(
        report,
        ["executive_summary", "trends"],
        expected_degradation=["market"],
    )

    assert result.passed is True
    assert result.score == 1
    assert result.details["allowed_missing_sections"] == ["trends"]


def test_category_relevance_checks_multiple_report_sections():
    report = _empty_report(
        executive_summary="测试品类的验证摘要",
        recommendations=[
            {
                "product_name": "测试品类便携款",
                "positioning": "定位",
                "target_customer": "用户",
                "price_range": "1-2",
                "rationale": "理由",
                "score": {
                    "demand": 1,
                    "competition": 1,
                    "margin": 1,
                    "differentiation": 1,
                    "evidence_quality": 1,
                    "total": 1,
                },
            }
        ],
        trends=[{"name": "测试品类趋势", "direction": "stable", "demand_score": 1, "growth_rate": 0, "rationale": "r"}],
        opportunities_risks=[{"opportunity": "测试品类机会", "rationale": "r", "opportunity_score": 1, "risk_score": 1}],
    )

    result = category_relevance(report, "测试品类")

    assert result.passed is True
    assert result.score == 1


def test_score_and_structured_output_metrics_reject_report_without_recommendations():
    report = _empty_report()

    score = score_validity(report)
    structured = structured_output_validity(report)

    assert score.measured == "measured"
    assert score.score == 0
    assert score.passed is False
    assert structured.score == 1
    assert structured.passed is True


def test_degradation_warning_metric_requires_expected_fragments():
    report = _empty_report(
        warnings=[
            "证据不足：当前结论仅适合生成选品假设，不应直接放量。",
            "市场趋势模块无结果，需求评分使用了保守默认值。",
            "竞品模块无结果，竞争评分使用了保守默认值。",
            "用户画像模块无结果，目标客群沿用了输入描述。",
            "机会风险模块无结果，建议先补充风险验证。",
        ]
    )

    result = degradation_warning_quality(report)

    assert result.score == 1
    assert result.passed is True
    assert result.details["warning_format_valid"] is True


def test_end_to_end_evaluation_measures_every_case_without_real_api():
    evaluation = run_evaluation()

    assert evaluation.measured is True
    assert evaluation.summary.total_case_count >= 20
    assert evaluation.summary.measured_case_count == evaluation.summary.total_case_count
    assert all(item.success for item in evaluation.cases)
    assert set(evaluation.summary.metric_averages) == {
        "report_completeness",
        "category_relevance",
        "evidence_coverage",
        "score_validity",
        "degradation_warning_quality",
        "structured_output_validity",
    }
    assert all(metric.measured == "measured" for item in evaluation.cases for metric in item.metrics)
    assert evaluation.summary.measured == "measured"
    assert evaluation.summary.success_rate == 1
    assert evaluation.summary.mock_cost == 0
    assert evaluation.summary.degradation_case_count >= 4
    assert evaluation.summary.degradation_pass_rate == 1
    assert len(evaluation.summary.category_case_counts) >= 20
    assert all(
        "category_relevance" in metrics
        for metrics in evaluation.summary.category_metric_averages.values()
    )
    assert all(item.latency_ms >= 0 for item in evaluation.cases)
    assert all(item.warning_count >= 0 for item in evaluation.cases)


def test_degradation_case_uses_mock_failures_and_records_observable_warnings():
    evaluation = run_evaluation()
    degraded = [item for item in evaluation.cases if item.degraded]

    assert degraded
    assert all(item.expected_degradation for item in degraded)
    assert all(item.success for item in degraded)
    assert all(item.warning_count >= len(item.expected_degradation) for item in degraded)
    assert all(
        next(metric for metric in item.metrics if metric.name == "degradation_warning_quality").passed
        for item in degraded
    )


def test_empty_dataset_summary_boundaries(tmp_path):
    dataset = tmp_path / "empty.jsonl"
    dataset.write_text('{"id":"x","category":"测试","target_customer":"用户","budget":{"minimum":1,"maximum":2},"expected_sections":["executive_summary"],"minimum_evidence_count":0}\n', encoding="utf-8")
    evaluation = run_evaluation(dataset)

    assert evaluation.summary.total_case_count == 1
    assert evaluation.summary.success_rate == 1
    assert evaluation.summary.degradation_case_count == 0
    assert evaluation.summary.degradation_pass_rate == 1


def test_unknown_degradation_module_is_rejected(tmp_path):
    dataset = tmp_path / "invalid.jsonl"
    dataset.write_text('{"id":"x","category":"测试","target_customer":"用户","budget":{"minimum":1,"maximum":2},"expected_sections":["executive_summary"],"minimum_evidence_count":0,"expected_degradation":["unknown"]}\n', encoding="utf-8")

    import pytest

    with pytest.raises(ValueError, match="Invalid evaluation case"):
        load_evaluation_cases(dataset)
