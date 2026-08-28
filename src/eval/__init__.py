# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
Legacy generic report evaluation compatibility layer for DeerFlow.

For the e-commerce evaluation dataset, Judge, A3/A4 runners, and ablation
experiments, use ``src.evaluation``. This package remains available only to
avoid breaking upstream/general-report imports.

This module provides objective methods to evaluate generated report quality,
including automated metrics and LLM-based evaluation.
"""

from .evaluator import ReportEvaluator
from .metrics import ReportMetrics, compute_metrics
from .llm_judge import LLMJudge, evaluate_with_llm

__all__ = [
    "ReportEvaluator",
    "ReportMetrics",
    "compute_metrics",
    "LLMJudge",
    "evaluate_with_llm",
]
