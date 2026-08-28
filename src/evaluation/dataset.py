"""Load and validate the local JSONL evaluation set."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationBudget(BaseModel):
    """Price budget passed to the existing research request model."""

    model_config = ConfigDict(extra="forbid")

    minimum: float = Field(ge=0)
    maximum: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> "EvaluationBudget":
        if self.maximum < self.minimum:
            raise ValueError("budget.maximum must be greater than or equal to budget.minimum")
        return self


class EvaluationCase(BaseModel):
    """One deterministic, human-readable product-selection evaluation case."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    target_customer: str = Field(min_length=1)
    budget: EvaluationBudget
    expected_sections: list[str] = Field(min_length=1)
    minimum_evidence_count: int = Field(ge=0)
    tags: list[str] = Field(default_factory=list)
    expected_degradation: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_degradation_modules(self) -> "EvaluationCase":
        allowed = {"market", "competitor", "customer", "opportunity"}
        unknown = set(self.expected_degradation) - allowed
        if unknown:
            raise ValueError(f"unsupported expected_degradation module(s): {sorted(unknown)}")
        if len(self.expected_degradation) != len(set(self.expected_degradation)):
            raise ValueError("expected_degradation must not contain duplicates")
        return self

    def to_request(self) -> dict[str, Any]:
        """Adapt the evaluation schema to the existing mock workflow interface."""

        return {
            "category": self.category,
            "target_customer": self.target_customer,
            "price_min": self.budget.minimum,
            "price_max": self.budget.maximum,
        }


DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "evaluation" / "ecommerce_cases.jsonl"
)


def load_evaluation_cases(path: str | Path | None = None) -> list[EvaluationCase]:
    """Read JSONL cases without consulting environment variables or external services."""

    dataset_path = Path(path) if path is not None else DEFAULT_DATASET_PATH
    cases: list[EvaluationCase] = []
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            content = line.strip()
            if not content:
                continue
            try:
                cases.append(EvaluationCase.model_validate(json.loads(content)))
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"Invalid evaluation case at {dataset_path}:{line_number}") from exc
    if not cases:
        raise ValueError(f"Evaluation dataset is empty: {dataset_path}")
    return cases
