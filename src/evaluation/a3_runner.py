"""Batch runner for the fixed A3 e-commerce evaluation contract."""

from __future__ import annotations

import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.ecommerce.orchestration import ResearchResult, run_mock_research
from src.ecommerce.providers import MockResearchProvider, ResearchProvider

from .dataset import DEFAULT_DATASET_PATH, EvaluationCase, load_evaluation_cases
from .ecommerce_judge import JudgeResult, deterministic_ecommerce_judge


class A3CaseEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    category: str
    success: bool
    degraded: bool = False
    expected_degradation: list[str] = Field(default_factory=list)
    latency_ms: float = Field(ge=0)
    warning_count: int = Field(ge=0)
    judge: JudgeResult | None = None
    error: str | None = None


class A3EvaluationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measured: str = "measured"
    total_case_count: int = Field(ge=0)
    measured_case_count: int = Field(ge=0)
    success_rate: float = Field(ge=0, le=1)
    degraded_case_count: int = Field(ge=0)
    degradation_pass_rate: float = Field(ge=0, le=1)
    average_latency_ms: float = Field(ge=0)
    average_warning_count: float = Field(ge=0)
    judge_average_score: float = Field(ge=0, le=100)
    judge_dimension_averages: dict[str, float] = Field(default_factory=dict)
    judge_human_review_count: int = Field(ge=0)
    latency_p50_ms: float = Field(default=0, ge=0)
    latency_p95_ms: float = Field(default=0, ge=0)
    latency_p99_ms: float = Field(default=0, ge=0)
    total_warning_count: int = Field(default=0, ge=0)
    metric_averages: dict[str, float] = Field(default_factory=dict)
    metric_pass_rates: dict[str, float] = Field(default_factory=dict)
    scenario_tag_counts: dict[str, int] = Field(default_factory=dict)
    mode: str = "mock"
    model_status: str = "not_used"
    search_status: str = "mock"
    total_external_request_count: int = Field(default=0, ge=0)
    total_cost_usd: float = Field(default=0, ge=0)
    total_token_count: int = Field(default=0, ge=0)


class A3EvaluationRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measured: bool = True
    dataset_path: str
    judge_version: str = "ecommerce-judge-v1"
    cases: list[A3CaseEvaluation]
    summary: A3EvaluationSummary

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_json_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _provider_for_case(
    case: EvaluationCase, provider: ResearchProvider | None
) -> ResearchProvider:
    if provider is None:
        return MockResearchProvider(fail_modules=set(case.expected_degradation))
    if isinstance(provider, MockResearchProvider):
        return MockResearchProvider(
            fail_modules=provider.fail_modules | set(case.expected_degradation)
        )
    return provider


def _percentile(values: list[float], percentile: float) -> float:
    """Return a stable nearest-rank percentile for a non-empty list."""

    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile / 100 * len(ordered)))
    return round(ordered[rank - 1], 4)


def run_a3_evaluation(
    dataset_path: str | Path | None = None,
    *,
    provider: ResearchProvider | None = None,
    output_path: str | Path | None = None,
) -> A3EvaluationRun:
    """Run all fixed cases with the offline report pipeline and deterministic Judge."""

    resolved_path = Path(dataset_path) if dataset_path is not None else DEFAULT_DATASET_PATH
    cases = load_evaluation_cases(resolved_path)
    measurements: list[A3CaseEvaluation] = []
    for case in cases:
        started = time.perf_counter()
        try:
            active_provider = _provider_for_case(case, provider)
            result: ResearchResult = run_mock_research(
                case.to_request(), provider=active_provider
            )
            judge = deterministic_ecommerce_judge(result.report, case)
            measurements.append(
                A3CaseEvaluation(
                    case_id=case.id,
                    category=case.category,
                    success=True,
                    degraded=bool(case.expected_degradation),
                    expected_degradation=case.expected_degradation,
                    latency_ms=round((time.perf_counter() - started) * 1000, 4),
                    warning_count=len(result.report.warnings),
                    judge=judge,
                )
            )
        except Exception as exc:  # noqa: BLE001 - preserve one-case failure detail
            measurements.append(
                A3CaseEvaluation(
                    case_id=case.id,
                    category=case.category,
                    success=False,
                    degraded=bool(case.expected_degradation),
                    expected_degradation=case.expected_degradation,
                    latency_ms=round((time.perf_counter() - started) * 1000, 4),
                    warning_count=0,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

    successful = [item for item in measurements if item.success and item.judge]
    degraded = [item for item in measurements if item.degraded]
    degradation_passes = [
        item.success and item.warning_count > 0 for item in degraded
    ]
    dimension_values: dict[str, list[float]] = defaultdict(list)
    metric_values: dict[str, list[float]] = defaultdict(list)
    metric_passes: dict[str, list[bool]] = defaultdict(list)
    for item in successful:
        assert item.judge is not None
        for dimension, score in item.judge.scores.items():
            dimension_values[dimension].append(score)
        for metric in item.judge.auto_metrics:
            metric_values[metric.name].append(metric.score)
            metric_passes[metric.name].append(metric.passed)
    latencies = [item.latency_ms for item in measurements]
    scenario_tag_counts = Counter(
        tag
        for case in cases
        for tag in case.tags
        if tag.startswith("a3-")
    )
    summary = A3EvaluationSummary(
        total_case_count=len(measurements),
        measured_case_count=len(measurements),
        success_rate=round(
            sum(item.success for item in measurements) / max(1, len(measurements)), 4
        ),
        degraded_case_count=len(degraded),
        degradation_pass_rate=round(
            sum(degradation_passes) / len(degradation_passes), 4
        )
        if degradation_passes
        else 1.0,
        average_latency_ms=round(
            sum(item.latency_ms for item in measurements) / max(1, len(measurements)),
            4,
        ),
        average_warning_count=round(
            sum(item.warning_count for item in measurements) / max(1, len(measurements)),
            4,
        ),
        judge_average_score=round(
            sum(item.judge.overall_score for item in successful) / max(1, len(successful)),
            4,
        ),
        judge_dimension_averages={
            dimension: round(sum(scores) / len(scores), 4)
            for dimension, scores in sorted(dimension_values.items())
        },
        judge_human_review_count=sum(
            item.judge.needs_human_review for item in successful if item.judge
        ),
        latency_p50_ms=_percentile(latencies, 50),
        latency_p95_ms=_percentile(latencies, 95),
        latency_p99_ms=_percentile(latencies, 99),
        total_warning_count=sum(item.warning_count for item in measurements),
        metric_averages={
            metric: round(sum(scores) / len(scores), 4)
            for metric, scores in sorted(metric_values.items())
        },
        metric_pass_rates={
            metric: round(sum(passes) / len(passes), 4)
            for metric, passes in sorted(metric_passes.items())
        },
        scenario_tag_counts=dict(sorted(scenario_tag_counts.items())),
    )
    evaluation = A3EvaluationRun(
        dataset_path=str(resolved_path),
        cases=measurements,
        summary=summary,
    )
    if output_path is not None:
        evaluation.write_json(output_path)
    return evaluation


__all__ = [
    "A3CaseEvaluation",
    "A3EvaluationRun",
    "A3EvaluationSummary",
    "run_a3_evaluation",
]
