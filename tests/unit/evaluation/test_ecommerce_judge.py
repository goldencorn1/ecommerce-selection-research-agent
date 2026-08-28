"""Tests for the independent A3 e-commerce judge contract."""

from __future__ import annotations

import json

import pytest

from src.ecommerce.models import EcommerceResearchRequest, FinalReport
from src.evaluation.dataset import EvaluationCase
from src.evaluation.ecommerce_judge import (
    JUDGE_DIMENSIONS,
    EcommerceLLMJudge,
    calibrate_judge,
    deterministic_ecommerce_judge,
    summarize_calibration,
)


def _case() -> EvaluationCase:
    return EvaluationCase(
        id="a3-test",
        category="便携榨汁杯",
        target_customer="年轻上班族",
        budget={"minimum": 99, "maximum": 299},
        expected_sections=[
            "executive_summary",
            "recommendations",
            "trends",
            "competitors",
            "customer_profiles",
            "opportunities_risks",
            "evidence",
        ],
        minimum_evidence_count=2,
    )


def _report(*, low_evidence: bool = False) -> FinalReport:
    evidence = (
        []
        if low_evidence
        else [
            {
                "evidence_id": "e1",
                "source": "https://example.test/market",
                "title": "市场观察",
                "summary": "需求观察",
                "confidence": 0.9,
            },
            {
                "evidence_id": "e2",
                "source": "https://example.test/customer",
                "title": "用户观察",
                "summary": "用户需求",
                "confidence": 0.8,
            },
        ]
    )
    return FinalReport(
        request=EcommerceResearchRequest(
            category="便携榨汁杯",
            target_customer="年轻上班族",
            price_min=99,
            price_max=299,
        ),
        executive_summary="便携榨汁杯市场面向年轻上班族，建议先验证。",
        recommendations=[
            {
                "product_name": "通勤便携款",
                "positioning": "轻量便携",
                "target_customer": "年轻上班族",
                "price_range": "129-199",
                "rationale": "便于通勤使用",
                "score": {
                    "demand": 70,
                    "competition": 60,
                    "margin": 65,
                    "differentiation": 70,
                    "evidence_quality": 80,
                    "total": 69,
                },
                "evidence_ids": ["e1"] if not low_evidence else [],
                "price_basis": "竞品价格锚点",
                "validation_action": "访谈并测试转化",
            }
        ],
        trends=[
            {
                "name": "便携榨汁杯需求趋势",
                "direction": "rising",
                "demand_score": 70,
                "growth_rate": 0.2,
                "rationale": "便携场景增长",
                "evidence_ids": ["e1"] if not low_evidence else [],
            }
        ],
        competitors=[
            {
                "name": "竞品 A",
                "price": 159,
                "positioning": "通勤",
                "evidence_ids": ["e1"] if not low_evidence else [],
            }
        ],
        customer_profiles=[
            {
                "segment": "年轻上班族",
                "needs": ["便携"],
                "pain_points": ["通勤时间有限"],
                "buying_triggers": ["易清洗"],
                "evidence_ids": ["e2"] if not low_evidence else [],
            }
        ],
        opportunities_risks=[
            {
                "opportunity": "通勤饮品场景",
                "rationale": "高频使用",
                "opportunity_score": 70,
                "risks": ["同质化"],
                "risk_score": 50,
                "mitigations": ["先做小规模验证"],
                "evidence_ids": ["e2"] if not low_evidence else [],
            }
        ],
        evidence=evidence,
        warnings=["证据不足：当前结论仅适合生成选品假设。"] if low_evidence else [],
        decision_basis="需要先验证需求和转化。",
        next_actions=["补充访谈"],
    )


def _llm_json(score: float = 80) -> str:
    return json.dumps(
        {
            "scores": {dimension: score for dimension in JUDGE_DIMENSIONS},
            "overall_score": score,
            "rationale": {dimension: "结构清楚" for dimension in JUDGE_DIMENSIONS},
            "strengths": ["引用关系清楚"],
            "weaknesses": ["仍需人工核验"],
        },
        ensure_ascii=False,
    )


def test_deterministic_judge_scores_normal_report_and_keeps_metrics():
    result = deterministic_ecommerce_judge(_report(), _case())

    assert result.source == "deterministic"
    assert set(result.scores) == set(JUDGE_DIMENSIONS)
    assert result.auto_metrics
    assert result.fallback_used is False


def test_low_evidence_is_scored_conservatively():
    result = deterministic_ecommerce_judge(_report(low_evidence=True), _case())

    assert result.scores["evidence_quality"] < 50
    assert result.scores["commercial_boundary"] < 80
    assert result.auto_metrics


@pytest.mark.asyncio
async def test_bad_json_returns_fallback_and_preserves_automatic_metrics():
    async def adapter(prompt: str) -> str:
        return "not-json"

    result = await EcommerceLLMJudge(adapter).evaluate(_report(), _case())

    assert result.source == "fallback"
    assert result.fallback_used is True
    assert result.auto_metrics
    assert result.fallback_reason


def test_sync_llm_failure_returns_fallback():
    def adapter(prompt: str) -> str:
        raise RuntimeError("adapter unavailable")

    result = EcommerceLLMJudge(adapter).evaluate_sync(_report(), _case())

    assert result.source == "fallback"
    assert "adapter unavailable" in (result.fallback_reason or "")
    assert result.automatic_metric_scores


def test_human_calibration_exposes_differences_and_summary():
    result = deterministic_ecommerce_judge(_report(), _case())
    human_scores = {dimension: 50 for dimension in JUDGE_DIMENSIONS}

    record = calibrate_judge(result, human_scores, annotator_id="human-1")
    summary = summarize_calibration([record])

    assert record.differences["market"] == result.scores["market"] - 50
    assert record.mean_absolute_error >= 0
    assert summary.record_count == 1
    assert set(summary.dimension_mean_absolute_error) == set(JUDGE_DIMENSIONS)


@pytest.mark.asyncio
async def test_async_llm_result_and_models_are_json_serializable():
    async def adapter(prompt: str) -> str:
        return _llm_json(73)

    result = await EcommerceLLMJudge(adapter).evaluate(_report(), _case())
    record = calibrate_judge(result, {dimension: 70 for dimension in JUDGE_DIMENSIONS})

    json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
    assert result.source == "llm"
    assert result.overall_score == 73
