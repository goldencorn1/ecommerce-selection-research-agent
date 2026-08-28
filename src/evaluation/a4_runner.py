"""Reproducible A4 ablation experiments for the e-commerce workflow."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.ecommerce.knowledge.models import KnowledgeDocument
from src.ecommerce.knowledge.vector import (
    HashEmbeddingAdapter,
    LexicalReranker,
    VectorRetriever,
)
from src.ecommerce.orchestration import ResearchResult, run_research
from src.ecommerce.providers import ResearchProvider

from .a3_runner import _provider_for_case
from .a4_policy import (
    BudgetController,
    RetryPolicy,
    classify_error,
    run_with_retry,
)
from .dataset import DEFAULT_DATASET_PATH, EvaluationCase, load_evaluation_cases
from .ecommerce_judge import JudgeResult, deterministic_ecommerce_judge


class A4ExperimentConfig(BaseModel):
    """Immutable knobs for one comparable experiment arm."""

    model_config = ConfigDict(extra="forbid")

    experiment_id: str = Field(min_length=1)
    dataset_path: str = str(DEFAULT_DATASET_PATH)
    use_agents: bool = True
    use_rerank: bool = False
    retrieval_mode: str = "vector"
    knowledge_top_k: int = Field(default=2, ge=1, le=20)
    max_retries: int = Field(default=1, ge=0, le=5)
    budget: BudgetController = Field(default_factory=BudgetController)
    seed: int = 0

    @model_validator(mode="after")
    def validate_retrieval_mode(self) -> "A4ExperimentConfig":
        if self.retrieval_mode not in {"vector"}:
            raise ValueError("A4 currently supports retrieval_mode='vector' only")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @property
    def config_hash(self) -> str:
        payload = json.dumps(self.canonical_dict(), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class A4CaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    category: str
    success: bool
    attempts: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    warning_count: int = Field(ge=0)
    error_kind: str | None = None
    budget_exceeded: bool = False
    judge: JudgeResult | None = None
    raw_result: dict[str, Any] = Field(default_factory=dict)


class A4ExperimentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measured: str = "measured"
    experiment_id: str
    config_hash: str
    total_case_count: int = Field(ge=0)
    measured_case_count: int = Field(ge=0)
    success_rate: float = Field(ge=0, le=1)
    average_latency_ms: float = Field(ge=0)
    average_warning_count: float = Field(ge=0)
    judge_average_score: float = Field(ge=0, le=100)
    budget_exceeded_case_count: int = Field(ge=0)
    failure_kinds: dict[str, int] = Field(default_factory=dict)


class A4ExperimentRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measured: bool = True
    config: A4ExperimentConfig
    cases: list[A4CaseResult]
    summary: A4ExperimentSummary

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def write_json(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_json_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class A4Comparison(BaseModel):
    """Measured deltas between two completed experiment arms."""

    model_config = ConfigDict(extra="forbid")

    measured: str = "measured"
    baseline_experiment_id: str
    candidate_experiment_id: str
    baseline_config_hash: str
    candidate_config_hash: str
    metric_deltas: dict[str, float]
    common_case_count: int = Field(ge=0)


def _retriever_for_case(case: EvaluationCase, *, use_rerank: bool) -> VectorRetriever:
    relevant = KnowledgeDocument(
        document_id=f"a4-{case.id}-relevant",
        title=f"{case.category} 私有验证记录",
        content=(
            f"类别：{case.category}；客群：{case.target_customer}；"
            f"预算：{case.budget.minimum}-{case.budget.maximum}；"
            "用于小批量验证、成本和合规核验。"
        ),
        source=f"local://a4/{case.id}/relevant",
    )
    distractor = KnowledgeDocument(
        document_id=f"a4-{case.id}-distractor",
        title="无关库存备忘",
        content="仅记录仓库盘点与物流箱规，不包含目标品类或客群判断。",
        source=f"local://a4/{case.id}/distractor",
    )
    return VectorRetriever(
        [relevant, distractor],
        HashEmbeddingAdapter(dimensions=128),
        reranker=LexicalReranker() if use_rerank else None,
    )


def _run_case(
    case: EvaluationCase,
    config: A4ExperimentConfig,
    *,
    provider: ResearchProvider | None,
) -> tuple[ResearchResult, JudgeResult]:
    active_provider = _provider_for_case(case, provider)
    retriever = _retriever_for_case(case, use_rerank=config.use_rerank)
    result = run_research(
        case.to_request(),
        provider=active_provider,
        research_mode="Mock",
        knowledge_retriever=retriever,
        knowledge_top_k=config.knowledge_top_k,
        use_agent_graph=config.use_agents,
    )
    return result, deterministic_ecommerce_judge(result.report, case)


def run_a4_experiment(
    config: A4ExperimentConfig,
    *,
    provider: ResearchProvider | None = None,
    output_path: str | Path | None = None,
) -> A4ExperimentRun:
    """Run one fixed arm and retain raw structured reports for replay."""

    cases = load_evaluation_cases(config.dataset_path)
    budget = BudgetController.model_validate(config.budget.model_dump())
    retry_policy = RetryPolicy(max_attempts=config.max_retries + 1)
    measurements: list[A4CaseResult] = []
    for case in cases:
        try:
            budget.check_case()
            budget.start_case()
        except Exception as exc:  # noqa: BLE001 - preserve budget stop reason
            measurements.append(
                A4CaseResult(
                    case_id=case.id,
                    category=case.category,
                    success=False,
                    attempts=0,
                    latency_ms=0,
                    warning_count=0,
                    error_kind=classify_error(exc).kind,
                    budget_exceeded=True,
                )
            )
            continue
        started = time.perf_counter()
        attempts = 0

        def operation() -> tuple[ResearchResult, JudgeResult]:
            nonlocal attempts
            attempts += 1
            return _run_case(case, config, provider=provider)

        try:
            result, judge = run_with_retry(
                operation,
                policy=retry_policy,
                budget=budget,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            measurements.append(
                A4CaseResult(
                    case_id=case.id,
                    category=case.category,
                    success=True,
                    attempts=attempts,
                    latency_ms=round(elapsed_ms, 4),
                    warning_count=len(result.report.warnings),
                    judge=judge,
                    raw_result=result.to_json_dict(),
                )
            )
        except Exception as exc:  # noqa: BLE001 - preserve case-level failure
            elapsed_ms = (time.perf_counter() - started) * 1000
            kind = classify_error(exc).kind
            measurements.append(
                A4CaseResult(
                    case_id=case.id,
                    category=case.category,
                    success=False,
                    attempts=attempts,
                    latency_ms=round(elapsed_ms, 4),
                    warning_count=0,
                    error_kind=kind,
                    budget_exceeded=kind == "budget_exceeded",
                )
            )

    successful = [item for item in measurements if item.success and item.judge]
    failure_kinds: dict[str, int] = {}
    for item in measurements:
        if item.error_kind:
            failure_kinds[item.error_kind] = failure_kinds.get(item.error_kind, 0) + 1
    summary = A4ExperimentSummary(
        experiment_id=config.experiment_id,
        config_hash=config.config_hash,
        total_case_count=len(measurements),
        measured_case_count=sum(item.success for item in measurements),
        success_rate=round(sum(item.success for item in measurements) / max(1, len(measurements)), 4),
        average_latency_ms=round(sum(item.latency_ms for item in measurements) / max(1, len(measurements)), 4),
        average_warning_count=round(sum(item.warning_count for item in measurements) / max(1, len(measurements)), 4),
        judge_average_score=round(sum(item.judge.overall_score for item in successful) / max(1, len(successful)), 4),
        budget_exceeded_case_count=sum(item.budget_exceeded for item in measurements),
        failure_kinds=dict(sorted(failure_kinds.items())),
    )
    run = A4ExperimentRun(config=config, cases=measurements, summary=summary)
    if output_path is not None:
        run.write_json(output_path)
    return run


def compare_a4_experiments(
    baseline: A4ExperimentRun,
    candidate: A4ExperimentRun,
) -> A4Comparison:
    baseline_cases = {item.case_id: item for item in baseline.cases}
    candidate_cases = {item.case_id: item for item in candidate.cases}
    common = sorted(set(baseline_cases) & set(candidate_cases))
    baseline_scores = [baseline_cases[item].judge.overall_score for item in common if baseline_cases[item].judge]
    candidate_scores = [candidate_cases[item].judge.overall_score for item in common if candidate_cases[item].judge]
    baseline_latency = [baseline_cases[item].latency_ms for item in common]
    candidate_latency = [candidate_cases[item].latency_ms for item in common]
    return A4Comparison(
        baseline_experiment_id=baseline.config.experiment_id,
        candidate_experiment_id=candidate.config.experiment_id,
        baseline_config_hash=baseline.config.config_hash,
        candidate_config_hash=candidate.config.config_hash,
        common_case_count=len(common),
        metric_deltas={
            "judge_average_score": round(sum(candidate_scores) / max(1, len(candidate_scores)) - sum(baseline_scores) / max(1, len(baseline_scores)), 4),
            "average_latency_ms": round(sum(candidate_latency) / max(1, len(candidate_latency)) - sum(baseline_latency) / max(1, len(baseline_latency)), 4),
            "success_rate": round(candidate.summary.success_rate - baseline.summary.success_rate, 4),
        },
    )


__all__ = [
    "A4CaseResult",
    "A4Comparison",
    "A4ExperimentConfig",
    "A4ExperimentRun",
    "A4ExperimentSummary",
    "compare_a4_experiments",
    "run_a4_experiment",
]
