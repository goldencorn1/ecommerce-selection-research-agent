"""A3 e-commerce judging and human-calibration contract.

This module is deliberately independent from the existing report evaluator.  It
provides a small, JSON-safe contract for offline judging, while allowing a
caller to inject an LLM adapter when a second opinion is useful.  Scores are on
the 0-100 scale and are measurements of the supplied report only; they are not
claims about market truth or commercial performance.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import math
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.ecommerce.models import FinalReport

from .dataset import EvaluationCase
from .metrics import MetricResult, evaluate_report

logger = logging.getLogger(__name__)

JudgeDimension = Literal[
    "market",
    "competitor",
    "price",
    "customer",
    "risk",
    "evidence_quality",
    "commercial_boundary",
]

JUDGE_DIMENSIONS: tuple[JudgeDimension, ...] = (
    "market",
    "competitor",
    "price",
    "customer",
    "risk",
    "evidence_quality",
    "commercial_boundary",
)


class JudgeCriterion(BaseModel):
    """One dimension in the A3 e-commerce rubric."""

    model_config = ConfigDict(extra="forbid")

    dimension: JudgeDimension
    description: str = Field(min_length=1)
    weight: float = Field(gt=0, le=1)
    minimum: float = Field(default=0, ge=0, le=100)
    maximum: float = Field(default=100, ge=0, le=100)

    @model_validator(mode="after")
    def validate_scale(self) -> "JudgeCriterion":
        if self.maximum <= self.minimum:
            raise ValueError("maximum must be greater than minimum")
        return self


class JudgeRubric(BaseModel):
    """Versionable rubric with all required e-commerce dimensions."""

    model_config = ConfigDict(extra="forbid")

    name: str = "a3_ecommerce"
    version: str = "1"
    criteria: list[JudgeCriterion] = Field(min_length=len(JUDGE_DIMENSIONS))

    @model_validator(mode="after")
    def validate_criteria(self) -> "JudgeRubric":
        dimensions = [criterion.dimension for criterion in self.criteria]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("rubric criteria must have unique dimensions")
        missing = set(JUDGE_DIMENSIONS) - set(dimensions)
        if missing:
            raise ValueError(f"rubric is missing dimensions: {sorted(missing)}")
        if abs(sum(criterion.weight for criterion in self.criteria) - 1.0) > 0.001:
            raise ValueError("rubric criterion weights must sum to 1")
        return self


DEFAULT_RUBRIC = JudgeRubric(
    criteria=[
        JudgeCriterion(
            dimension="market",
            description="市场需求信号是否具体、相关且被报告内容支撑。",
            weight=0.16,
        ),
        JudgeCriterion(
            dimension="competitor",
            description="竞品覆盖、定位和竞争差异是否可比较。",
            weight=0.14,
        ),
        JudgeCriterion(
            dimension="price",
            description="价格带、价格依据与输入预算是否清楚且可追溯。",
            weight=0.14,
        ),
        JudgeCriterion(
            dimension="customer",
            description="目标客群、需求和购买触发是否具体。",
            weight=0.14,
        ),
        JudgeCriterion(
            dimension="risk",
            description="机会、风险和缓解动作是否同时呈现。",
            weight=0.14,
        ),
        JudgeCriterion(
            dimension="evidence_quality",
            description="证据数量、引用关系和来源置信度是否足够。",
            weight=0.16,
        ),
        JudgeCriterion(
            dimension="commercial_boundary",
            description="报告是否清楚区分验证假设与可直接放量的商业结论。",
            weight=0.12,
        ),
    ]
)


class JudgeResult(BaseModel):
    """A JSON-safe judge result, including the automatic audit trail."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    judge_version: str = "ecommerce-judge-v1"
    rubric_name: str = "a3_ecommerce"
    rubric_version: str = "1"
    source: Literal["deterministic", "llm", "fallback"]
    scores: dict[JudgeDimension, float]
    overall_score: float = Field(ge=0, le=100)
    auto_metrics: list[MetricResult] = Field(default_factory=list)
    rationale: dict[JudgeDimension, str] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: str | None = None
    raw_response: str | None = None
    needs_human_review: bool = False

    @model_validator(mode="after")
    def validate_scores(self) -> "JudgeResult":
        missing = set(JUDGE_DIMENSIONS) - set(self.scores)
        extra = set(self.scores) - set(JUDGE_DIMENSIONS)
        if missing or extra:
            raise ValueError(
                f"scores must contain exactly the rubric dimensions; missing={sorted(missing)}, "
                f"extra={sorted(extra)}"
            )
        if any(not 0 <= score <= 100 for score in self.scores.values()):
            raise ValueError("all judge scores must be between 0 and 100")
        if self.rationale and set(self.rationale) - set(JUDGE_DIMENSIONS):
            raise ValueError("rationale contains an unsupported dimension")
        return self

    @property
    def automatic_metric_scores(self) -> dict[str, float]:
        """Return the scalar automatic metrics for simple JSON consumers."""

        return {metric.name: metric.score for metric in self.auto_metrics}

    @property
    def judge_failed(self) -> bool:
        """Compatibility flag for consumers that call failures ``judge_failed``."""

        return self.fallback_used


class HumanCalibrationRecord(BaseModel):
    """Difference between one judge result and a human reference score.

    ``differences`` use ``judge - human``.  A positive value therefore means
    that the judge scored the dimension higher than the human reference.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    judge_scores: dict[JudgeDimension, float]
    human_scores: dict[JudgeDimension, float]
    differences: dict[JudgeDimension, float] = Field(default_factory=dict)
    absolute_differences: dict[JudgeDimension, float] = Field(default_factory=dict)
    mean_absolute_error: float = Field(default=0, ge=0)
    mean_signed_error: float = 0
    calibrated_scores: dict[JudgeDimension, float] = Field(default_factory=dict)
    annotator_id: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def calculate_differences(self) -> "HumanCalibrationRecord":
        if set(self.judge_scores) != set(JUDGE_DIMENSIONS):
            raise ValueError("judge_scores must contain every rubric dimension")
        if set(self.human_scores) != set(JUDGE_DIMENSIONS):
            raise ValueError("human_scores must contain every rubric dimension")
        if any(not 0 <= value <= 100 for value in self.judge_scores.values()):
            raise ValueError("judge scores must be between 0 and 100")
        if any(not 0 <= value <= 100 for value in self.human_scores.values()):
            raise ValueError("human scores must be between 0 and 100")

        differences = {
            dimension: round(
                self.judge_scores[dimension] - self.human_scores[dimension], 4
            )
            for dimension in JUDGE_DIMENSIONS
        }
        absolute = {
            dimension: round(abs(value), 4) for dimension, value in differences.items()
        }
        object.__setattr__(self, "differences", differences)
        object.__setattr__(self, "absolute_differences", absolute)
        object.__setattr__(
            self,
            "mean_absolute_error",
            round(sum(absolute.values()) / len(absolute), 4),
        )
        object.__setattr__(
            self,
            "mean_signed_error",
            round(sum(differences.values()) / len(differences), 4),
        )
        if not self.calibrated_scores:
            object.__setattr__(self, "calibrated_scores", dict(self.human_scores))
        return self


class CalibrationSummary(BaseModel):
    """Aggregate, descriptive calibration statistics for recorded cases."""

    model_config = ConfigDict(extra="forbid")

    record_count: int = Field(ge=0)
    mean_absolute_error: float = Field(ge=0)
    mean_signed_error: float
    dimension_mean_absolute_error: dict[JudgeDimension, float]
    dimension_mean_signed_error: dict[JudgeDimension, float]


def _as_report(report: FinalReport | Mapping[str, Any]) -> FinalReport:
    return (
        report
        if isinstance(report, FinalReport)
        else FinalReport.model_validate(report)
    )


def _as_case(case: EvaluationCase | Mapping[str, Any]) -> EvaluationCase:
    return (
        case
        if isinstance(case, EvaluationCase)
        else EvaluationCase.model_validate(case)
    )


def _clamp(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("judge scores must be finite numbers")
    return round(max(0.0, min(100.0, float(value))), 2)


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _evidence_reference_score(report: FinalReport) -> float:
    evidence_ids = {item.evidence_id for item in report.evidence}
    references = [
        evidence_id
        for recommendation in report.recommendations
        for evidence_id in recommendation.evidence_ids
    ]
    if not references:
        return 0.0
    return _ratio(
        sum(reference in evidence_ids for reference in references), len(references)
    )


def _price_quality(report: FinalReport, case: EvaluationCase) -> float:
    if not report.recommendations:
        return 0.0
    valid = 0
    for recommendation in report.recommendations:
        has_range = (
            bool(recommendation.price_range.strip())
            and recommendation.price_range != "待计算"
        )
        has_basis = bool(recommendation.price_basis.strip())
        if has_range and has_basis:
            valid += 1
    completeness = _ratio(valid, len(report.recommendations))
    competitor_prices = [item.price for item in report.competitors]
    in_budget = sum(
        case.budget.minimum <= price <= case.budget.maximum
        for price in competitor_prices
    )
    budget_signal = (
        _ratio(in_budget, len(competitor_prices)) if competitor_prices else 0.0
    )
    return _clamp((completeness * 0.75 + budget_signal * 0.25) * 100)


def _deterministic_scores(
    report: FinalReport, case: EvaluationCase
) -> dict[JudgeDimension, float]:
    """Score observable structure only; this function makes no network calls."""

    category = case.category
    market_relevance = _ratio(
        sum(
            category in text
            for text in (
                report.executive_summary,
                *(trend.name for trend in report.trends),
            )
        ),
        1 + len(report.trends),
    )
    market = _clamp(
        (0.6 * min(1.0, len(report.trends) / 3) + 0.4 * market_relevance) * 100
    )

    competitor_coverage = min(1.0, len(report.competitors) / 3)
    competitor_citations = _ratio(
        sum(bool(item.evidence_ids) for item in report.competitors),
        len(report.competitors),
    )
    competitor = _clamp(
        (competitor_coverage * 0.65 + competitor_citations * 0.35) * 100
    )

    price = _price_quality(report, case)

    customer_match = _ratio(
        sum(
            case.target_customer in profile.segment
            or profile.segment in case.target_customer
            for profile in report.customer_profiles
        ),
        len(report.customer_profiles),
    )
    customer_detail = _ratio(
        sum(
            bool(profile.needs and profile.pain_points)
            for profile in report.customer_profiles
        ),
        len(report.customer_profiles),
    )
    customer = _clamp((customer_match * 0.6 + customer_detail * 0.4) * 100)

    risk_detail = _ratio(
        sum(
            bool(item.risks and item.mitigations) for item in report.opportunities_risks
        ),
        len(report.opportunities_risks),
    )
    risk = _clamp(
        (min(1.0, len(report.opportunities_risks) / 2) * 0.5 + risk_detail * 0.5) * 100
    )

    evidence_count = min(
        1.0, _ratio(len(report.evidence), max(1, case.minimum_evidence_count))
    )
    confidence = _ratio(
        sum(item.confidence for item in report.evidence), len(report.evidence)
    )
    references = _evidence_reference_score(report)
    evidence_quality = _clamp(
        (evidence_count * 0.45 + confidence * 0.25 + references * 0.3) * 100
    )

    boundary_base = {
        "insufficient_evidence": 25.0,
        "validate_first": 65.0,
        "ready_for_scale": 90.0,
    }[report.decision_status]
    boundary_detail = 10.0 if report.decision_basis and report.next_actions else 0.0
    if report.warnings:
        boundary_detail -= min(20.0, len(report.warnings) * 2.0)
    commercial_boundary = _clamp(boundary_base + boundary_detail)

    return {
        "market": market,
        "competitor": competitor,
        "price": price,
        "customer": customer,
        "risk": risk,
        "evidence_quality": evidence_quality,
        "commercial_boundary": commercial_boundary,
    }


def _overall_score(
    scores: Mapping[JudgeDimension, float], rubric: JudgeRubric
) -> float:
    weights = {criterion.dimension: criterion.weight for criterion in rubric.criteria}
    return _clamp(
        sum(scores[dimension] * weights[dimension] for dimension in JUDGE_DIMENSIONS)
    )


def _automatic_result(
    report: FinalReport, case: EvaluationCase, rubric: JudgeRubric
) -> JudgeResult:
    metrics = evaluate_report(report, case)
    scores = _deterministic_scores(report, case)
    return JudgeResult(
        case_id=case.id,
        judge_version="ecommerce-judge-v1",
        rubric_name=rubric.name,
        rubric_version=rubric.version,
        source="deterministic",
        scores=scores,
        overall_score=_overall_score(scores, rubric),
        auto_metrics=metrics,
        rationale={
            dimension: "按报告中可观察的结构和引用关系测量。"
            for dimension in JUDGE_DIMENSIONS
        },
        weaknesses=["该基线不验证外部事实，只评价报告内可观察证据。"],
        needs_human_review=(
            len(report.evidence) < case.minimum_evidence_count or bool(report.warnings)
        ),
    )


def deterministic_ecommerce_judge(
    report: FinalReport | Mapping[str, Any],
    case: EvaluationCase | Mapping[str, Any],
    *,
    rubric: JudgeRubric = DEFAULT_RUBRIC,
) -> JudgeResult:
    """Evaluate a report locally and deterministically, without network access."""

    return _automatic_result(_as_report(report), _as_case(case), rubric)


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, Mapping):
        return json.dumps(response, ensure_ascii=False)
    if hasattr(response, "content"):
        content = response.content
        return (
            content
            if isinstance(content, str)
            else json.dumps(content, ensure_ascii=False)
        )
    return str(response)


def _parse_json_object(response: str) -> dict[str, Any]:
    candidate = response.strip()
    fenced = re.search(
        r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.DOTALL | re.IGNORECASE
    )
    if fenced:
        candidate = fenced.group(1).strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("LLM response does not contain a JSON object") from None
        try:
            parsed = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("LLM response contains invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object")
    return parsed


def _llm_result(
    payload: Mapping[str, Any],
    automatic: JudgeResult,
    raw_response: str,
    rubric: JudgeRubric,
) -> JudgeResult:
    raw_scores = payload.get("scores", payload.get("dimensions"))
    if not isinstance(raw_scores, Mapping):
        raise ValueError("LLM response must include a scores object")
    if set(raw_scores) != set(JUDGE_DIMENSIONS):
        raise ValueError("LLM scores must contain every rubric dimension exactly once")
    scores = {
        dimension: _clamp(float(raw_scores[dimension]))
        for dimension in JUDGE_DIMENSIONS
    }
    rationale = payload.get("rationale", {})
    if not isinstance(rationale, Mapping):
        raise ValueError("rationale must be an object")
    overall = payload.get("overall_score", _overall_score(scores, rubric))
    return JudgeResult(
        case_id=automatic.case_id,
        judge_version="ecommerce-judge-v1",
        rubric_name=rubric.name,
        rubric_version=rubric.version,
        source="llm",
        scores=scores,
        overall_score=_clamp(float(overall)),
        auto_metrics=automatic.auto_metrics,
        rationale={
            dimension: str(rationale.get(dimension, ""))
            for dimension in JUDGE_DIMENSIONS
        },
        strengths=_string_list(payload.get("strengths", []), "strengths"),
        weaknesses=_string_list(payload.get("weaknesses", []), "weaknesses"),
        raw_response=raw_response,
        needs_human_review=automatic.needs_human_review,
    )


def _string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return value


def _fallback(
    automatic: JudgeResult, reason: str, raw_response: str | None = None
) -> JudgeResult:
    return automatic.model_copy(
        update={
            "source": "fallback",
            "fallback_used": True,
            "fallback_reason": reason,
            "raw_response": raw_response,
            "needs_human_review": True,
        }
    )


def _callable_arguments(
    adapter: Callable[..., Any], prompt: str, report: FinalReport, case: EvaluationCase
) -> tuple[Any, ...]:
    """Use a one-argument prompt adapter or a two-argument report/case adapter."""

    try:
        parameters = inspect.signature(adapter).parameters.values()
    except (TypeError, ValueError):
        return (prompt,)
    positional = [
        parameter
        for parameter in parameters
        if parameter.kind
        in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
    ]
    return (report, case) if len(positional) >= 2 else (prompt,)


async def _invoke_async(
    adapter: Any, prompt: str, report: FinalReport, case: EvaluationCase
) -> Any:
    method = getattr(adapter, "ainvoke", None)
    if method is not None:
        return await method(prompt)
    method = getattr(adapter, "invoke", None)
    if method is not None:
        result = method(prompt)
        return await result if inspect.isawaitable(result) else result
    if not callable(adapter):
        raise TypeError("adapter must be callable or expose invoke/ainvoke")
    result = adapter(*_callable_arguments(adapter, prompt, report, case))
    return await result if inspect.isawaitable(result) else result


def _invoke_sync(
    adapter: Any, prompt: str, report: FinalReport, case: EvaluationCase
) -> Any:
    method = getattr(adapter, "invoke", None)
    if method is not None:
        return method(prompt)
    method = getattr(adapter, "ainvoke", None)
    if method is not None:
        return asyncio.run(method(prompt))
    if not callable(adapter):
        raise TypeError("adapter must be callable or expose invoke/ainvoke")
    result = adapter(*_callable_arguments(adapter, prompt, report, case))
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


class EcommerceLLMJudge:
    """LLM judge with an injectable sync or async adapter and safe fallback."""

    def __init__(self, adapter: Any, *, rubric: JudgeRubric = DEFAULT_RUBRIC):
        self.adapter = adapter
        self.rubric = rubric

    def build_prompt(self, report: FinalReport, case: EvaluationCase) -> str:
        """Build a deterministic prompt so adapters can be tested or audited."""

        schema = {
            "scores": {dimension: "0-100 number" for dimension in JUDGE_DIMENSIONS},
            "overall_score": "0-100 number",
            "rationale": {
                dimension: "short explanation" for dimension in JUDGE_DIMENSIONS
            },
            "strengths": ["string"],
            "weaknesses": ["string"],
        }
        return (
            "你是 A3 电商报告 Judge。只根据输入报告评分，不要补造外部事实。"
            "请仅返回合法 JSON。\n"
            f"Rubric: {json.dumps(self.rubric.model_dump(mode='json'), ensure_ascii=False)}\n"
            f"Case: {json.dumps(case.model_dump(mode='json'), ensure_ascii=False)}\n"
            f"Report: {json.dumps(report.model_dump(mode='json'), ensure_ascii=False)}\n"
            f"Required shape: {json.dumps(schema, ensure_ascii=False)}"
        )

    async def evaluate(
        self,
        report: FinalReport | Mapping[str, Any],
        case: EvaluationCase | Mapping[str, Any],
    ) -> JudgeResult:
        report_model, case_model = _as_report(report), _as_case(case)
        automatic = _automatic_result(report_model, case_model, self.rubric)
        prompt = self.build_prompt(report_model, case_model)
        try:
            response = await _invoke_async(
                self.adapter, prompt, report_model, case_model
            )
            raw_response = _response_text(response)
            return _llm_result(
                _parse_json_object(raw_response), automatic, raw_response, self.rubric
            )
        except Exception as exc:
            logger.warning(
                "E-commerce LLM judge failed; using deterministic fallback: %s", exc
            )
            return _fallback(automatic, str(exc), locals().get("raw_response"))

    def evaluate_sync(
        self,
        report: FinalReport | Mapping[str, Any],
        case: EvaluationCase | Mapping[str, Any],
    ) -> JudgeResult:
        """Synchronous entry point; it also accepts an async-only adapter."""

        report_model, case_model = _as_report(report), _as_case(case)
        automatic = _automatic_result(report_model, case_model, self.rubric)
        prompt = self.build_prompt(report_model, case_model)
        raw_response: str | None = None
        try:
            raw_response = _response_text(
                _invoke_sync(self.adapter, prompt, report_model, case_model)
            )
            return _llm_result(
                _parse_json_object(raw_response), automatic, raw_response, self.rubric
            )
        except Exception as exc:
            logger.warning(
                "E-commerce LLM judge failed; using deterministic fallback: %s", exc
            )
            return _fallback(automatic, str(exc), raw_response)


def calibrate_judge(
    result: JudgeResult,
    human_scores: Mapping[JudgeDimension, float],
    *,
    annotator_id: str | None = None,
    notes: str | None = None,
) -> HumanCalibrationRecord:
    """Create a human-reference record and calculate per-dimension differences."""

    return HumanCalibrationRecord(
        case_id=result.case_id,
        judge_scores=dict(result.scores),
        human_scores=dict(human_scores),
        annotator_id=annotator_id,
        notes=notes,
    )


def summarize_calibration(
    records: Sequence[HumanCalibrationRecord],
) -> CalibrationSummary:
    """Summarize calibration records without inferring an unmeasured uplift."""

    if not records:
        return CalibrationSummary(
            record_count=0,
            mean_absolute_error=0,
            mean_signed_error=0,
            dimension_mean_absolute_error={
                dimension: 0 for dimension in JUDGE_DIMENSIONS
            },
            dimension_mean_signed_error={
                dimension: 0 for dimension in JUDGE_DIMENSIONS
            },
        )
    count = len(records)
    return CalibrationSummary(
        record_count=count,
        mean_absolute_error=round(
            sum(record.mean_absolute_error for record in records) / count, 4
        ),
        mean_signed_error=round(
            sum(record.mean_signed_error for record in records) / count, 4
        ),
        dimension_mean_absolute_error={
            dimension: round(
                sum(record.absolute_differences[dimension] for record in records)
                / count,
                4,
            )
            for dimension in JUDGE_DIMENSIONS
        },
        dimension_mean_signed_error={
            dimension: round(
                sum(record.differences[dimension] for record in records) / count, 4
            )
            for dimension in JUDGE_DIMENSIONS
        },
    )


compare_judge_to_human = calibrate_judge
calibration_summary = summarize_calibration

__all__ = [
    "CalibrationSummary",
    "DEFAULT_RUBRIC",
    "EcommerceLLMJudge",
    "HumanCalibrationRecord",
    "JUDGE_DIMENSIONS",
    "JudgeCriterion",
    "JudgeDimension",
    "JudgeResult",
    "JudgeRubric",
    "calibrate_judge",
    "calibration_summary",
    "compare_judge_to_human",
    "deterministic_ecommerce_judge",
    "summarize_calibration",
]
