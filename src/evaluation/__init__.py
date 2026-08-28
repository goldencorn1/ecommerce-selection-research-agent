"""Offline evaluation utilities for the e-commerce research MVP."""

from .dataset import EvaluationCase, load_evaluation_cases
from .metrics import evaluate_report
from .a3_runner import A3EvaluationRun, run_a3_evaluation
from .a4_runner import (
    A4Comparison,
    A4ExperimentConfig,
    A4ExperimentRun,
    compare_a4_experiments,
    run_a4_experiment,
)
from .p1_runner import P1EvaluationRun, run_p1_evaluation

__all__ = [
    "EvaluationCase",
    "EvaluationRun",
    "evaluate_report",
    "load_evaluation_cases",
    "run_evaluation",
    "A3EvaluationRun",
    "run_a3_evaluation",
    "A4Comparison",
    "A4ExperimentConfig",
    "A4ExperimentRun",
    "compare_a4_experiments",
    "run_a4_experiment",
    "P1EvaluationRun",
    "run_p1_evaluation",
]


def __getattr__(name: str):
    if name in {"EvaluationRun", "run_evaluation"}:
        from .runner import EvaluationRun, run_evaluation

        return {"EvaluationRun": EvaluationRun, "run_evaluation": run_evaluation}[name]
    raise AttributeError(name)
