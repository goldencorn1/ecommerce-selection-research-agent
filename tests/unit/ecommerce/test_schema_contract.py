"""Regression tests for the V1 e-commerce schema and offline entry points."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.ecommerce import EcommerceResearchRequest, FinalReport, run_mock_research
from src.ecommerce_graph import run_ecommerce_graph
from src.evaluation.dataset import EvaluationCase, load_evaluation_cases
from src.server.ecommerce_request import EcommerceWebResearchRequest


def test_request_rejects_unknown_fields_at_model_and_mock_entry_point():
    with pytest.raises(ValidationError):
        EcommerceResearchRequest(category="可折叠露营桌", unexpected_field="拒绝")

    with pytest.raises(ValidationError):
        run_mock_research(
            {
                "category": "可折叠露营桌",
                "unexpected_field": "拒绝",
            }
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"price_min": -1},
        {"price_max": -1},
        {"price_min": 300, "price_max": 299},
    ],
)
def test_request_enforces_non_negative_and_ordered_price_bounds(payload):
    with pytest.raises(ValidationError):
        EcommerceResearchRequest(category="测试品类", **payload)


def test_mock_result_and_final_report_are_json_serializable():
    result = run_mock_research(
        {
            "category": "可折叠露营桌",
            "target_customer": "周末露营的年轻家庭",
            "price_min": 129,
            "price_max": 399,
        }
    )

    encoded_result = json.dumps(result.to_json_dict(), ensure_ascii=False)
    assert "可折叠露营桌" in encoded_result

    report_payload = result.report.model_dump(mode="json")
    restored_report = FinalReport.model_validate(report_payload)
    assert restored_report == result.report
    assert json.loads(result.report.model_dump_json()) == report_payload


def test_five_report_sections_have_mappable_content():
    report = run_mock_research("可折叠露营桌").report

    section_mapping = {
        "market_overview": report.trends,
        "competitive_landscape": report.competitors,
        "price_band_analysis": [item.price for item in report.competitors],
        "target_customer_match": report.customer_profiles,
        "risk_and_entry_barriers": report.opportunities_risks,
    }

    assert set(section_mapping) == {
        "market_overview",
        "competitive_landscape",
        "price_band_analysis",
        "target_customer_match",
        "risk_and_entry_barriers",
    }
    assert all(section_mapping.values())
    assert report.executive_summary
    assert report.recommendations
    assert report.evidence


def test_recommendations_reference_only_report_evidence():
    report = run_mock_research("可折叠露营桌").report
    evidence_ids = {item.evidence_id for item in report.evidence}

    assert evidence_ids
    assert all(item.evidence_ids for item in report.recommendations)
    assert all(
        set(item.evidence_ids) <= evidence_ids for item in report.recommendations
    )


def test_mock_and_live_controls_preserve_existing_entry_boundaries():
    mock_request = EcommerceWebResearchRequest(mode="mock", model="mock")
    live_request = EcommerceWebResearchRequest(mode="live", model="deepseek")
    assert (mock_request.mode, mock_request.model) == ("mock", "mock")
    assert (live_request.mode, live_request.model) == ("live", "deepseek")

    state = run_ecommerce_graph(
        {
            "category": "可折叠露营桌",
            "search_enabled": False,
            "search_config": {"parallel_modules": False},
            "model_config": {"enabled": False},
        }
    )

    assert state["ecommerce_report"]["request"]["category"] == "可折叠露营桌"
    assert state["ecommerce_metrics"]["mode"] == "mock"
    assert state["ecommerce_search_status"] == "not_used"
    assert state["ecommerce_model_status"] == "not_used"


def test_existing_50_evaluation_cases_load_as_current_evaluation_case():
    cases = load_evaluation_cases()

    assert len(cases) == 50
    assert all(isinstance(case, EvaluationCase) for case in cases)
    assert len({case.id for case in cases}) == len(cases)
    assert all(case.expected_sections for case in cases)

    for case in cases:
        request = EcommerceResearchRequest.model_validate(case.to_request())
        assert request.category == case.category
        assert request.target_customer == case.target_customer
        assert request.price_min == case.budget.minimum
        assert request.price_max == case.budget.maximum
