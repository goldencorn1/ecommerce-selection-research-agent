from __future__ import annotations

import json
from pathlib import Path

from src.evaluation.dataset import load_evaluation_cases


DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "evaluation"
    / "ecommerce_cases.jsonl"
)
REQUIRED_FIELDS = {
    "id",
    "category",
    "target_customer",
    "budget",
    "expected_sections",
    "minimum_evidence_count",
    "tags",
    "expected_degradation",
}
ALLOWED_DEGRADATION_MODULES = {"market", "competitor", "customer", "opportunity"}
A3_SCENARIO_TAGS = {
    "a3-normal",
    "a3-search-degradation",
    "a3-module-degradation",
    "a3-low-evidence",
    "a3-private-knowledge-hit",
    "a3-private-knowledge-miss",
    "a3-price-missing",
    "a3-commercial-verification-incomplete",
    "a3-boundary-budget",
}


def test_a3_jsonl_has_exactly_fifty_valid_unique_cases() -> None:
    lines = [
        line
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    records = [json.loads(line) for line in lines]
    cases = load_evaluation_cases(DATASET_PATH)

    assert len(lines) == 50
    assert len(records) == len(cases) == 50
    assert all(isinstance(record, dict) for record in records)
    assert all(REQUIRED_FIELDS <= set(record) for record in records)
    assert len({case.id for case in cases}) == 50


def test_a3_cases_cover_required_scenarios_and_valid_constraints() -> None:
    cases = load_evaluation_cases(DATASET_PATH)
    scenario_tags = {tag for case in cases for tag in case.tags} & A3_SCENARIO_TAGS

    assert scenario_tags == A3_SCENARIO_TAGS
    assert len({case.category for case in cases}) >= 40
    assert all(case.budget.minimum >= 0 for case in cases)
    assert all(case.budget.maximum >= case.budget.minimum for case in cases)
    assert all(case.minimum_evidence_count >= 0 for case in cases)
    assert all(
        set(case.expected_degradation) <= ALLOWED_DEGRADATION_MODULES for case in cases
    )
    assert any(case.budget.minimum == case.budget.maximum for case in cases)
    assert any(case.budget.minimum == 0 for case in cases)


def test_a3_annotations_match_case_constraints() -> None:
    cases = load_evaluation_cases(DATASET_PATH)

    assert all(
        not case.expected_degradation for case in cases if "a3-normal" in case.tags
    )
    assert all(
        case.expected_degradation
        for case in cases
        if "a3-search-degradation" in case.tags
    )
    assert all(
        case.minimum_evidence_count <= 1
        for case in cases
        if "a3-low-evidence" in case.tags
    )
    assert any("a3-private-knowledge-hit" in case.tags for case in cases)
    assert any("a3-private-knowledge-miss" in case.tags for case in cases)
    assert any("a3-price-missing" in case.tags for case in cases)
    assert any("a3-commercial-verification-incomplete" in case.tags for case in cases)
