from src.ecommerce.telemetry import (
    assess_quality_gates,
    estimate_tokens,
    run_instrumented_mock_research,
    run_instrumented_research,
)
from src.ecommerce.llm_report import ModelUsage


class UsageEnhancer:
    usage = ModelUsage(
        model="deepseek-v4-flash",
        input_tokens=100,
        output_tokens=25,
        total_tokens=125,
        available=True,
        source="usage_metadata",
    )

    def enhance(self, report):
        return report


def test_estimate_tokens_is_zero_for_empty_text_and_positive_for_text():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("你好") == 1


def test_instrumented_mock_run_reports_latency_and_zero_mock_cost():
    result, metrics = run_instrumented_mock_research("可折叠露营桌")

    assert result.report.recommendations
    assert metrics.mode == "mock"
    assert metrics.status == "success"
    assert metrics.latency_ms >= 0
    assert metrics.output_chars > 0
    assert metrics.estimated_input_tokens > 0
    assert metrics.estimated_output_tokens > 0
    assert metrics.estimated_cost_usd == 0
    assert metrics.to_dict()["cost_note"]
    assert metrics.quality_level == "not_assessed"
    assert metrics.quality_gates["commercial_decision_ready"] is False


def test_instrumented_run_records_provider_usage_and_configured_cost():
    result, metrics = run_instrumented_research(
        "可折叠露营桌",
        mode="deepseek",
        report_enhancer=UsageEnhancer(),
        input_cost_per_million=0.14,
        output_cost_per_million=0.28,
    )

    assert result.model_status == "success"
    assert metrics.actual_input_tokens == 100
    assert metrics.actual_output_tokens == 25
    assert metrics.actual_total_tokens == 125
    assert metrics.actual_cost_usd == (100 * 0.14 + 25 * 0.28) / 1_000_000
    assert metrics.overall_status == "success"
    assert metrics.usage_available is True
    assert metrics.cost_status == "actual"
    assert metrics.to_dict()["model_name"] == "deepseek-v4-flash"
    assert metrics.verification_validation == {}


def test_quality_gates_require_clean_real_evidence_before_evidence_usable():
    result, _metrics = run_instrumented_research("可折叠露营桌")

    level, gates = assess_quality_gates(result)

    assert level == "not_assessed"
    assert gates == {
        "interface_success": False,
        "evidence_usable": False,
        "commercial_decision_ready": False,
    }


def test_instrumented_run_marks_model_fallback_as_degraded():
    class FailingEnhancer:
        def enhance(self, report):
            raise TimeoutError("model timeout")

    result, metrics = run_instrumented_research(
        "可折叠露营桌",
        mode="deepseek",
        report_enhancer=FailingEnhancer(),
    )

    assert result.model_status == "fallback"
    assert result.model_error_kind == "timeout"
    assert metrics.overall_status == "degraded"
    assert metrics.model_error_kind == "timeout"
    assert metrics.cost_status == "unavailable"
