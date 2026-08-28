"""Tests for the standalone A4 policy layer."""

import json

import pytest
from pydantic import ValidationError

from src.evaluation.a4_policy import (
    A4BudgetExceeded,
    BudgetController,
    RetryPolicy,
    classify_error,
    run_with_retry,
)


def test_budget_controller_is_serializable_and_tracks_limits() -> None:
    budget = BudgetController(
        max_cases=2,
        max_attempts=3,
        max_latency_ms=100,
        max_cost_usd=0.5,
    )

    budget.start_case()
    budget.consume_attempt()
    budget.record_attempt(latency_ms=12.5, cost_usd=0.1)

    payload = budget.model_dump(mode="json")
    assert json.loads(json.dumps(payload)) == payload
    assert payload["cases"] == 1
    assert payload["attempts"] == 1
    assert payload["latency_ms"] == 12.5
    assert payload["cost_usd"] == 0.1


def test_budget_controller_rejects_case_attempt_latency_and_cost_overruns() -> None:
    budget = BudgetController(
        max_cases=1,
        max_attempts=1,
        max_latency_ms=10,
        max_cost_usd=0.1,
    )
    budget.start_case()
    with pytest.raises(A4BudgetExceeded, match="cases"):
        budget.start_case()

    budget.consume_attempt()
    with pytest.raises(A4BudgetExceeded, match="attempts"):
        budget.consume_attempt()

    with pytest.raises(A4BudgetExceeded, match="latency_ms"):
        budget.record_attempt(latency_ms=10.1)

    with pytest.raises(A4BudgetExceeded, match="cost_usd"):
        budget.record_attempt(cost_usd=0.2)


@pytest.mark.parametrize(
    ("error", "kind", "retryable"),
    [
        (TimeoutError("slow"), "timeout", True),
        (A4BudgetExceeded("attempts", 1, 2), "budget_exceeded", False),
        (ConnectionError("upstream"), "provider_error", True),
        (ValueError("bad input"), "validation_error", False),
        (RuntimeError("unexpected"), "unknown_error", False),
    ],
)
def test_classify_error_is_stable(error: Exception, kind: str, retryable: bool) -> None:
    result = classify_error(error)
    assert result.kind == kind
    assert result.retryable is retryable
    assert result.exception_type == type(error).__name__
    assert result.model_dump(mode="json")["kind"] == kind


def test_pydantic_validation_error_is_classified_as_validation_error() -> None:
    with pytest.raises(ValidationError) as caught:
        BudgetController(max_cases=-1)

    result = classify_error(caught.value)
    assert result.kind == "validation_error"


def test_retry_policy_retries_only_configured_retryable_failures() -> None:
    policy = RetryPolicy(max_attempts=3, backoff_seconds=0)
    assert policy.should_retry(classify_error(TimeoutError()), 1)
    assert policy.should_retry(classify_error(ConnectionError()), 2)
    assert not policy.should_retry(classify_error(TimeoutError()), 3)
    assert not policy.should_retry(classify_error(ValueError()), 1)
    assert policy.model_dump(mode="json")["retryable_kinds"] == [
        "timeout",
        "provider_error",
    ]


def test_run_with_retry_succeeds_after_retry_without_sleep() -> None:
    calls = 0
    sleeps: list[float] = []

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    result = run_with_retry(
        operation,
        policy=RetryPolicy(max_attempts=3, backoff_seconds=0.25),
        sleep_fn=sleeps.append,
    )
    assert result == "ok"
    assert calls == 2
    assert sleeps == [0.25]


def test_run_with_retry_reraises_non_retryable_error() -> None:
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("invalid")

    with pytest.raises(ValueError, match="invalid"):
        run_with_retry(operation, policy=RetryPolicy(max_attempts=4))
    assert calls == 1


def test_run_with_retry_honors_budget_attempt_limit() -> None:
    budget = BudgetController(max_attempts=1)
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise TimeoutError("temporary")

    with pytest.raises(A4BudgetExceeded, match="attempts"):
        run_with_retry(
            operation,
            policy=RetryPolicy(max_attempts=3),
            budget=budget,
        )
    assert calls == 1
    assert budget.attempts == 1


def test_invalid_policy_and_budget_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValidationError):
        RetryPolicy(retryable_kinds=("not_a_kind",))
    with pytest.raises(ValidationError):
        BudgetController(max_cost_usd=float("inf"))
