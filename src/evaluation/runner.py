"""Run the local evaluation set against the existing mock research workflow."""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.ecommerce.orchestration import ResearchResult, run_mock_research
from src.ecommerce.providers import MockResearchProvider, ResearchProvider

from .dataset import load_evaluation_cases
from .metrics import MetricResult, evaluate_report


class CaseEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: str
    measured: bool = True
    success: bool
    degraded: bool = False
    expected_degradation: list[str] = Field(default_factory=list)
    latency_ms: float = Field(ge=0)
    warning_count: int = Field(ge=0)
    metrics: list[MetricResult] = Field(default_factory=list)
    error: str | None = None


class EvaluationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measured: Literal["measured"] = "measured"
    measured_case_count: int
    total_case_count: int
    success_rate: float = Field(ge=0, le=1)
    average_warning_count: float = Field(ge=0)
    average_latency_ms: float = Field(ge=0)
    mock_cost: float = Field(ge=0)
    degradation_case_count: int = Field(ge=0)
    degradation_pass_rate: float = Field(ge=0, le=1)
    metric_averages: dict[str, float]
    metric_pass_rates: dict[str, float]
    category_case_counts: dict[str, int]
    category_metric_averages: dict[str, dict[str, float]]
    category_metric_pass_rates: dict[str, dict[str, float]]


class EvaluationRun(BaseModel):
    """逐例测量结果和汇总；不代表模型质量或真实市场准确率。"""

    model_config = ConfigDict(extra="forbid")

    measured: bool = True
    dataset_path: str
    cases: list[CaseEvaluation]
    summary: EvaluationSummary

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _failed_metrics() -> list[MetricResult]:
    return [
        MetricResult(
            name="structured_output_validity",
            score=0.0,
            passed=False,
            details={"execution_completed": False},
        )
    ]


def run_evaluation(
    dataset_path: str | Path | None = None,
    *,
    provider: ResearchProvider | None = None,
) -> EvaluationRun:
    """Load cases and call ``run_mock_research`` once per case, entirely offline."""

    cases = load_evaluation_cases(dataset_path)
    measurements: list[CaseEvaluation] = []
    for case in cases:
        active_provider = provider
        if active_provider is None:
            active_provider = MockResearchProvider(fail_modules=set(case.expected_degradation))
        elif isinstance(active_provider, MockResearchProvider):
            active_provider = MockResearchProvider(
                fail_modules=active_provider.fail_modules | set(case.expected_degradation)
            )
        started = time.perf_counter()
        try:
            result: ResearchResult = run_mock_research(case.to_request(), provider=active_provider)
            latency_ms = (time.perf_counter() - started) * 1000
            measurements.append(
                CaseEvaluation(
                    id=case.id,
                    category=case.category,
                    success=True,
                    degraded=bool(case.expected_degradation),
                    expected_degradation=case.expected_degradation,
                    latency_ms=round(latency_ms, 4),
                    warning_count=len(result.report.warnings),
                    metrics=evaluate_report(result.report, case),
                )
            )
        except Exception as exc:  # noqa: BLE001 - one bad case must not hide batch results
            latency_ms = (time.perf_counter() - started) * 1000
            measurements.append(
                CaseEvaluation(
                    id=case.id,
                    category=case.category,
                    success=False,
                    degraded=bool(case.expected_degradation),
                    expected_degradation=case.expected_degradation,
                    latency_ms=round(latency_ms, 4),
                    warning_count=0,
                    metrics=_failed_metrics(),
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

    averages: dict[str, list[float]] = defaultdict(list)
    passes: dict[str, list[bool]] = defaultdict(list)
    category_averages: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    category_passes: dict[str, dict[str, list[bool]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for measurement in measurements:
        for metric in measurement.metrics:
            averages[metric.name].append(metric.score)
            passes[metric.name].append(metric.passed)
            category_averages[measurement.category][metric.name].append(metric.score)
            category_passes[measurement.category][metric.name].append(metric.passed)
    degradation_cases = [item for item in measurements if item.degraded]
    degradation_passes = [
        item.success
        and all(metric.passed for metric in item.metrics if metric.name == "degradation_warning_quality")
        for item in degradation_cases
    ]
    summary = EvaluationSummary(
        measured_case_count=sum(item.measured for item in measurements),
        total_case_count=len(measurements),
        success_rate=round(sum(item.success for item in measurements) / len(measurements), 4)
        if measurements else 0.0,
        average_warning_count=round(
            sum(item.warning_count for item in measurements) / len(measurements), 4
        )
        if measurements else 0.0,
        average_latency_ms=round(
            sum(item.latency_ms for item in measurements) / len(measurements), 4
        )
        if measurements else 0.0,
        mock_cost=0.0,
        degradation_case_count=len(degradation_cases),
        degradation_pass_rate=round(sum(degradation_passes) / len(degradation_passes), 4)
        if degradation_passes else 1.0,
        metric_averages={name: round(sum(values) / len(values), 4) for name, values in averages.items()},
        metric_pass_rates={name: round(sum(values) / len(values), 4) for name, values in passes.items()},
        category_case_counts={
            category: sum(1 for item in measurements if item.category == category)
            for category in sorted(category_averages)
        },
        category_metric_averages={
            category: {
                name: round(sum(values) / len(values), 4)
                for name, values in metrics.items()
            }
            for category, metrics in sorted(category_averages.items())
        },
        category_metric_pass_rates={
            category: {
                name: round(sum(values) / len(values), 4)
                for name, values in metrics.items()
            }
            for category, metrics in sorted(category_passes.items())
        },
    )
    resolved_path = Path(dataset_path) if dataset_path is not None else Path(__file__).resolve().parents[2] / "data" / "evaluation" / "ecommerce_cases.jsonl"
    return EvaluationRun(
        dataset_path=str(resolved_path),
        cases=measurements,
        summary=summary,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="运行离线电商选品评测集")
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = run_evaluation(args.dataset)
    print(json.dumps(result.to_json_dict(), ensure_ascii=False, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
