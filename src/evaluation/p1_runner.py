"""P1 evaluation entry point with explicit Mock/Live and Judge boundaries.

The default path is fully offline and reuses the fixed A3 deterministic
baseline. The optional LLM Judge path accepts an injected adapter so callers
can connect an approved model without coupling the evaluator to a provider
SDK. Live/LLM runs without an adapter are reported as ``blocked`` rather than
silently converted into a fake score.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.ecommerce.orchestration import run_mock_research

from .a3_runner import run_a3_evaluation
from .dataset import DEFAULT_DATASET_PATH, load_evaluation_cases
from .ecommerce_judge import EcommerceLLMJudge, deterministic_ecommerce_judge

P1Mode = Literal["mock", "live"]
P1JudgeMode = Literal["deterministic", "llm", "hybrid"]


class P1EvaluationRun(BaseModel):
    """Stable machine-readable envelope for the P1 evaluation entry point."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["measured", "blocked"]
    mode: P1Mode
    judge_mode: P1JudgeMode
    dataset_path: str
    dataset_sha256: str
    generated_at: str
    total_case_count: int = Field(ge=0)
    measured_case_count: int = Field(ge=0)
    cases: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    block_reason: str | None = None
    provider: str | None = None
    model: str | None = None
    external_request_count: int = Field(default=0, ge=0)

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _dataset_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _blocked(
    *,
    mode: P1Mode,
    judge_mode: P1JudgeMode,
    dataset_path: Path,
    reason: str,
) -> P1EvaluationRun:
    return P1EvaluationRun(
        status="blocked",
        mode=mode,
        judge_mode=judge_mode,
        dataset_path=str(dataset_path),
        dataset_sha256=_dataset_hash(dataset_path),
        generated_at=datetime.now(UTC).isoformat(),
        total_case_count=len(load_evaluation_cases(dataset_path)),
        measured_case_count=0,
        block_reason=reason,
    )


def run_p1_evaluation(
    dataset_path: str | Path | None = None,
    *,
    mode: P1Mode = "mock",
    judge: P1JudgeMode = "deterministic",
    adapter: Any = None,
    output_path: str | Path | None = None,
) -> P1EvaluationRun:
    """Run P1 evaluation or return a truthful, actionable blocked envelope.

    ``adapter`` is dependency-injected. A production caller may provide a
    configured LangChain-compatible ``invoke`` adapter, while a local/demo
    caller can use the deterministic Mock path without credentials. This
    function never makes a network call by itself.
    """

    resolved_path = Path(dataset_path) if dataset_path else DEFAULT_DATASET_PATH
    if mode == "live":
        result = _blocked(
            mode=mode,
            judge_mode=judge,
            dataset_path=resolved_path,
            reason="live_evaluation_requires_an_explicit_provider_adapter",
        )
    elif judge in {"llm", "hybrid"} and adapter is None:
        result = _blocked(
            mode=mode,
            judge_mode=judge,
            dataset_path=resolved_path,
            reason="llm_judge_requires_an_explicit_configured_adapter",
        )
    elif judge == "deterministic":
        baseline = run_a3_evaluation(resolved_path)
        result = P1EvaluationRun(
            status="measured",
            mode="mock",
            judge_mode="deterministic",
            dataset_path=str(resolved_path),
            dataset_sha256=_dataset_hash(resolved_path),
            generated_at=datetime.now(UTC).isoformat(),
            total_case_count=len(baseline.cases),
            measured_case_count=len(baseline.cases),
            cases=[item.model_dump(mode="json") for item in baseline.cases],
            summary=baseline.summary.model_dump(mode="json"),
            provider="MockResearchProvider",
            model=None,
        )
    else:
        cases = load_evaluation_cases(resolved_path)
        llm_judge = EcommerceLLMJudge(adapter=adapter)
        measured: list[dict[str, Any]] = []
        for case in cases:
            report = run_mock_research(case.to_request()).report
            automatic = deterministic_ecommerce_judge(report, case)
            judged = llm_judge.evaluate_sync(report, case)
            if judge == "hybrid" and judged.fallback_used:
                judged = automatic
            measured.append(
                {
                    "case_id": case.id,
                    "category": case.category,
                    "success": True,
                    "judge": judged.model_dump(mode="json"),
                }
            )
        scores = [item["judge"]["overall_score"] for item in measured]
        result = P1EvaluationRun(
            status="measured",
            mode="mock",
            judge_mode=judge,
            dataset_path=str(resolved_path),
            dataset_sha256=_dataset_hash(resolved_path),
            generated_at=datetime.now(UTC).isoformat(),
            total_case_count=len(cases),
            measured_case_count=len(measured),
            cases=measured,
            summary={
                "judge_average_score": round(sum(scores) / max(1, len(scores)), 4),
                "judge_fallback_count": sum(
                    item["judge"].get("fallback_used", False) for item in measured
                ),
            },
            provider=str(getattr(adapter, "provider", "injected")),
            model=str(getattr(adapter, "model_name", "")) or None,
            external_request_count=len(measured),
        )
    if output_path is not None:
        result.write_json(output_path)
    return result


__all__ = ["P1EvaluationRun", "run_p1_evaluation"]
