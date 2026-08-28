"""Policy primitives for reproducible A4 evaluation experiments.

This module deliberately has no dependency on the evaluation runner.  It owns
only the cross-cutting policy concerns that an A4 runner needs: stable error
classification, mutable-but-serializable budget accounting, and bounded
retries.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable, Iterable
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


ErrorKind = Literal[
    "timeout",
    "budget_exceeded",
    "provider_error",
    "validation_error",
    "unknown_error",
]

ERROR_KINDS: tuple[ErrorKind, ...] = (
    "timeout",
    "budget_exceeded",
    "provider_error",
    "validation_error",
    "unknown_error",
)

DEFAULT_RETRYABLE_KINDS: tuple[ErrorKind, ...] = (
    "timeout",
    "provider_error",
)


class A4PolicyError(Exception):
    """Base class for errors raised by the A4 policy layer."""


class A4BudgetExceeded(A4PolicyError):
    """Raised when a configured A4 budget can no longer be consumed."""

    def __init__(
        self,
        dimension: str,
        limit: int | float,
        observed: int | float,
    ) -> None:
        self.dimension = dimension
        self.limit = limit
        self.observed = observed
        super().__init__(
            f"A4 budget exceeded: {dimension}={observed} exceeds limit={limit}"
        )


class A4RetryExhausted(A4PolicyError):
    """Optional wrapper for callers that want to wrap the final failure."""

    def __init__(self, attempts: int, last_error: BaseException) -> None:
        self.attempts = attempts
        self.last_error = last_error
        self.kind = classify_error(last_error).kind
        super().__init__(
            f"A4 retry policy exhausted after {attempts} attempts: {last_error}"
        )


class ErrorClassification(BaseModel):
    """Stable, JSON-serializable description of an exception."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ErrorKind
    retryable: bool
    exception_type: str
    message: str


def _looks_like_provider_error(error: BaseException) -> bool:
    """Recognize provider-shaped errors without importing provider modules."""

    type_name = type(error).__name__.lower()
    return any(
        marker in type_name
        for marker in ("provider", "transport", "upstream", "http", "api")
    ) or isinstance(error, (ConnectionError, OSError))


def classify_error(error: BaseException) -> ErrorClassification:
    """Classify an exception into the stable A4 failure taxonomy.

    The classifier intentionally uses standard exception classes first and
    only uses conservative class-name matching for provider-specific errors.
    This keeps the policy layer independent from any particular provider SDK.
    """

    if isinstance(error, A4BudgetExceeded):
        kind: ErrorKind = "budget_exceeded"
    elif isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        kind = "timeout"
    elif _looks_like_provider_error(error):
        kind = "provider_error"
    elif isinstance(error, (ValidationError, ValueError, TypeError)):
        kind = "validation_error"
    else:
        kind = "unknown_error"

    return ErrorClassification(
        kind=kind,
        retryable=kind in DEFAULT_RETRYABLE_KINDS,
        exception_type=type(error).__name__,
        message=str(error),
    )


# A descriptive alias makes the public API discoverable for callers that use
# "exception" rather than "error" terminology.
classify_exception = classify_error


class BudgetController(BaseModel):
    """Mutable budget accounting that remains directly serializable.

    Limits are inclusive: a value equal to a limit is accepted, while the
    next consumption that would exceed it raises :class:`A4BudgetExceeded`.
    ``start_case`` and ``consume_attempt`` are explicit so a runner can choose
    where a case boundary lies; latency and cost are recorded after execution.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    max_cases: int | None = Field(default=None, ge=0)
    max_attempts: int | None = Field(default=None, ge=0)
    max_latency_ms: float | None = Field(default=None, ge=0)
    max_cost_usd: float | None = Field(default=None, ge=0)

    cases: int = Field(default=0, ge=0)
    attempts: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0.0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0)

    @field_validator("max_latency_ms", "max_cost_usd", "latency_ms", "cost_usd")
    @classmethod
    def _require_finite(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("budget values must be finite")
        return value

    def start_case(self) -> None:
        """Reserve one case, raising before mutation when the limit is full."""

        self._ensure_within("cases", self.cases + 1, self.max_cases)
        self.cases += 1

    def consume_attempt(self) -> None:
        """Reserve one attempt, raising before mutation when the limit is full."""

        self._ensure_within("attempts", self.attempts + 1, self.max_attempts)
        self.attempts += 1

    def record_attempt(
        self,
        *,
        latency_ms: float = 0.0,
        cost_usd: float = 0.0,
    ) -> None:
        """Record measured latency and cost for an already-consumed attempt."""

        if not math.isfinite(latency_ms) or latency_ms < 0:
            raise ValueError("latency_ms must be a finite non-negative number")
        if not math.isfinite(cost_usd) or cost_usd < 0:
            raise ValueError("cost_usd must be a finite non-negative number")

        new_latency = self.latency_ms + latency_ms
        new_cost = self.cost_usd + cost_usd
        self._ensure_within("latency_ms", new_latency, self.max_latency_ms)
        self._ensure_within("cost_usd", new_cost, self.max_cost_usd)
        self.latency_ms = new_latency
        self.cost_usd = new_cost

    def check_case(self) -> None:
        """Check whether another case may start without consuming it."""

        self._ensure_within("cases", self.cases + 1, self.max_cases)

    def check_attempt(self) -> None:
        """Check whether another attempt may start without consuming it."""

        self._ensure_within("attempts", self.attempts + 1, self.max_attempts)

    def _ensure_within(
        self,
        dimension: str,
        observed: int | float,
        limit: int | float | None,
    ) -> None:
        if limit is not None and observed > limit:
            raise A4BudgetExceeded(dimension, limit, observed)


class RetryPolicy(BaseModel):
    """Bounded retry policy with explicit, serializable retryable kinds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_attempts: int = Field(default=3, ge=1)
    backoff_seconds: float = Field(default=0.0, ge=0)
    retryable_kinds: tuple[ErrorKind, ...] = DEFAULT_RETRYABLE_KINDS

    @field_validator("backoff_seconds")
    @classmethod
    def _require_finite_backoff(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("backoff_seconds must be finite")
        return value

    @field_validator("retryable_kinds")
    @classmethod
    def _validate_kinds(cls, value: Iterable[ErrorKind]) -> tuple[ErrorKind, ...]:
        kinds = tuple(value)
        invalid = set(kinds).difference(ERROR_KINDS)
        if invalid:
            raise ValueError(f"unsupported retryable error kinds: {sorted(invalid)}")
        return tuple(dict.fromkeys(kinds))

    def should_retry(self, classification: ErrorClassification, attempt: int) -> bool:
        """Return whether a failed 1-based attempt may be followed by another."""

        if attempt < 1:
            raise ValueError("attempt must be 1 or greater")
        return attempt < self.max_attempts and classification.kind in self.retryable_kinds

    def delay_for(self, attempt: int) -> float:
        """Return exponential backoff for the next retry after ``attempt``."""

        if attempt < 1:
            raise ValueError("attempt must be 1 or greater")
        return self.backoff_seconds * (2 ** (attempt - 1))


T = TypeVar("T")


def run_with_retry(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy | None = None,
    budget: BudgetController | None = None,
    attempt_cost_usd: float = 0.0,
    sleep_fn: Callable[[float], Any] = time.sleep,
) -> T:
    """Run ``operation`` under bounded retries and optional budget accounting.

    The final operation exception is re-raised unchanged.  A budget violation
    takes precedence over further retries and is raised as
    :class:`A4BudgetExceeded` so callers can classify it deterministically.
    ``sleep_fn`` is injectable to keep tests and deterministic runs free of
    real delays.
    """

    active_policy = policy or RetryPolicy()
    if not math.isfinite(attempt_cost_usd) or attempt_cost_usd < 0:
        raise ValueError("attempt_cost_usd must be a finite non-negative number")

    attempt = 0
    while True:
        attempt += 1
        if budget is not None:
            budget.consume_attempt()

        started = time.monotonic()
        try:
            result = operation()
        except Exception as error:
            elapsed_ms = (time.monotonic() - started) * 1000
            if budget is not None:
                budget.record_attempt(
                    latency_ms=elapsed_ms,
                    cost_usd=attempt_cost_usd,
                )
            classification = classify_error(error)
            if not active_policy.should_retry(classification, attempt):
                raise
            delay = active_policy.delay_for(attempt)
            if delay:
                sleep_fn(delay)
            continue

        if budget is not None:
            elapsed_ms = (time.monotonic() - started) * 1000
            budget.record_attempt(
                latency_ms=elapsed_ms,
                cost_usd=attempt_cost_usd,
            )
        return result


__all__ = [
    "A4BudgetExceeded",
    "A4PolicyError",
    "A4RetryExhausted",
    "BudgetController",
    "DEFAULT_RETRYABLE_KINDS",
    "ERROR_KINDS",
    "ErrorClassification",
    "ErrorKind",
    "RetryPolicy",
    "classify_error",
    "classify_exception",
    "run_with_retry",
]
