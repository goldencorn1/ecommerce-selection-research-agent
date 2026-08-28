import json

from src.ecommerce import MockResearchProvider, run_deepseek_research, run_mock_research
from src.ecommerce.llm_report import LLMRecommendationDraft, LLMReportDraft
from src.ecommerce.orchestration import classify_model_error


class FakeStructuredLLM:
    def __init__(self):
        self.structured_kwargs = {}

    class RawResponse:
        usage_metadata = {"input_tokens": 120, "output_tokens": 45, "total_tokens": 165}
        response_metadata = {"model_name": "deepseek-v4-flash"}

    def with_structured_output(self, _schema, **_kwargs):
        self.structured_kwargs = _kwargs
        return self

    def invoke(self, _messages):
        return {
            "raw": self.RawResponse(),
            "parsed": LLMReportDraft(
                executive_summary="模型润色后的摘要：先小批量验证，再根据证据扩大投入。",
                recommendations=[
                    LLMRecommendationDraft(
                        positioning="轻量快速展开版本",
                        rationale="优先验证收纳体积和展开效率。",
                    ),
                    LLMRecommendationDraft(
                        positioning="稳定承重版本",
                        rationale="优先验证不同地面和负载下的稳定性。",
                    ),
                    LLMRecommendationDraft(
                        positioning="场景配件套装版本",
                        rationale="优先验证配件组合和客单价提升。",
                    ),
                ],
            ),
        }


def test_default_mock_run_returns_report_and_markdown():
    result = run_mock_research()

    assert result.report.request.category == "便携榨汁杯"
    assert result.report.recommendations
    assert result.markdown.startswith("# 电商选品研究报告：便携榨汁杯")
    assert "结论摘要" in result.markdown
    assert result.warnings == result.report.warnings


def test_custom_category_is_stable_and_json_friendly():
    first = run_mock_research("可折叠露营桌")
    second = run_mock_research("可折叠露营桌")

    assert first.to_json_dict() == second.to_json_dict()
    encoded = json.dumps(first.to_json_dict(), ensure_ascii=False)
    assert "可折叠露营桌" in encoded
    assert isinstance(first.to_json_dict()["report"]["evidence"], list)


def test_category_profile_removes_juice_cup_template_and_varies_recommendations():
    result = run_mock_research({"category": "可折叠露营桌"})

    assert "健康" not in result.report.request.target_customer
    assert "健康化" not in result.report.trends[0].name
    assert "低噪声" not in result.report.opportunities_risks[0].opportunity
    assert len({item.positioning for item in result.report.recommendations}) == 3
    assert len({item.price_range for item in result.report.recommendations}) == 3
    assert all(item.validation_action for item in result.report.recommendations)


def test_tablet_report_uses_category_specific_directions_and_actionable_price_anchors():
    result = run_mock_research(
        {"category": "平板电脑", "price_min": 999, "price_max": 9999}
    )

    assert [item.product_name for item in result.report.recommendations] == [
        "平板电脑学习入门款",
        "平板电脑移动办公款",
        "平板电脑创作娱乐款",
    ]
    assert len({item.price_range for item in result.report.recommendations}) == 3
    assert len({item.score.total for item in result.report.recommendations}) == 3
    assert all("竞品价格锚点" in item.price_basis for item in result.report.recommendations)
    assert result.report.decision_status == "validate_first"
    assert len(result.report.next_actions) == 3


def test_recommendation_scores_stay_in_range():
    result = run_mock_research({"category": "桌面收纳盒", "top_n": 2})

    assert len(result.report.recommendations) == 2
    for recommendation in result.report.recommendations:
        score = recommendation.score
        assert 0 <= score.total <= 100
        assert all(0 <= value <= 100 for value in score.model_dump().values())


def test_failed_module_degrades_and_records_warning():
    result = run_mock_research(
        {"category": "便携榨汁杯"},
        provider=MockResearchProvider(fail_modules={"competitor"}),
    )

    assert result.report.trends
    assert result.report.competitors == []
    assert any("竞品分析模块失败" in warning for warning in result.warnings)
    assert any("竞品模块无结果" in warning for warning in result.warnings)
    assert result.report.recommendations


def test_deepseek_enhancement_changes_language_only():
    llm = FakeStructuredLLM()
    result = run_deepseek_research(
        {"category": "可折叠露营桌"},
        llm=llm,
    )

    assert result.report.executive_summary.startswith("模型润色后的摘要")
    assert result.report.recommendations[0].positioning == "轻量快速展开版本"
    assert len({item.positioning for item in result.report.recommendations}) == 3
    assert result.report.recommendations[0].score.total > 0
    assert result.report.evidence
    assert result.model_status == "success"
    assert llm.structured_kwargs["method"] == "json_mode"
    assert result.model_usage["model"] == "deepseek-v4-flash"
    assert result.model_usage["input_tokens"] == 120
    assert result.model_usage["output_tokens"] == 45
    assert result.model_usage["usage_available"] is True
    assert result.model_usage["usage_source"] == "usage_metadata"
    assert not any("真实模型报告润色失败" in warning for warning in result.warnings)


def test_deepseek_enhancement_failure_keeps_structured_report():
    class FailingLLM(FakeStructuredLLM):
        def invoke(self, _messages):
            raise RuntimeError("offline")

    result = run_deepseek_research(
        {"category": "可折叠露营桌"},
        llm=FailingLLM(),
    )

    assert result.report.recommendations
    assert result.report.evidence
    assert result.model_status == "fallback"
    assert result.model_error_kind == "unknown_error"
    assert any("真实模型报告润色失败" in warning for warning in result.warnings)


def test_model_error_classifier_identifies_encoding_failures_without_exposing_details():
    error = UnicodeEncodeError("ascii", "中文", 0, 1, "ordinal not in range")

    assert classify_model_error(error) == "encoding_error"


def test_model_error_classifier_identifies_provider_api_failures():
    error = RuntimeError("HTTP 502 from upstream provider")

    assert classify_model_error(error) == "provider_error"
