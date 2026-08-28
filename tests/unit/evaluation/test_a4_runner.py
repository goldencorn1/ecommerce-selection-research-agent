"""Contract tests for the reproducible A4 experiment runner."""

import json

from src.evaluation.a4_policy import BudgetController
from src.evaluation.a4_runner import (
    A4ExperimentConfig,
    compare_a4_experiments,
    run_a4_experiment,
)


def _config(experiment_id: str, *, use_agents: bool, use_rerank: bool) -> A4ExperimentConfig:
    return A4ExperimentConfig(
        experiment_id=experiment_id,
        use_agents=use_agents,
        use_rerank=use_rerank,
        max_retries=0,
        budget=BudgetController(max_cases=2, max_attempts=2),
    )


def test_a4_config_hash_is_stable_and_captures_ablation_flags() -> None:
    left = _config("left", use_agents=True, use_rerank=False)
    right = _config("right", use_agents=False, use_rerank=True)
    assert left.config_hash == left.model_copy().config_hash
    assert left.config_hash != right.config_hash


def test_a4_runner_keeps_raw_reports_and_classifies_budget_stop(tmp_path) -> None:
    config = _config("smoke", use_agents=True, use_rerank=True)
    output_path = tmp_path / "a4-smoke.json"
    run = run_a4_experiment(config, output_path=output_path)

    assert run.summary.total_case_count == 50
    assert run.summary.measured_case_count == 2
    assert run.summary.budget_exceeded_case_count == 48
    assert run.cases[0].success is True
    assert run.cases[0].raw_result["report"]["recommendations"]
    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8"))["config"]["experiment_id"] == "smoke"


def test_a4_comparison_reports_measured_deltas() -> None:
    baseline = run_a4_experiment(_config("baseline", use_agents=False, use_rerank=False))
    candidate = run_a4_experiment(_config("candidate", use_agents=True, use_rerank=True))

    comparison = compare_a4_experiments(baseline, candidate)
    assert comparison.common_case_count == 50
    assert set(comparison.metric_deltas) == {
        "average_latency_ms",
        "judge_average_score",
        "success_rate",
    }
    assert comparison.measured == "measured"
