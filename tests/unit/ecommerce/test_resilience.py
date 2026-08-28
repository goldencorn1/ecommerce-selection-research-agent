"""Tests for the standalone A5 resilience policy layer."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from src.ecommerce.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    RateLimitExceeded,
    RateLimiter,
    classify_failure,
)


class ManualClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_fixed_window_is_keyed_and_exposes_retry_after() -> None:
    clock = ManualClock()
    limiter = RateLimiter(limit=2, window_seconds=10, clock=clock)

    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is False
    assert limiter.retry_after("alice") == 10
    assert limiter.allow("bob") is True

    clock.advance(10)
    assert limiter.allow("alice") is True
    assert limiter.retry_after("alice") == 0


def test_rate_limit_exception_has_stable_json_fields() -> None:
    clock = ManualClock()
    limiter = RateLimiter(max_requests=1, window_seconds=5, clock=clock)
    limiter.acquire("tenant")
    with pytest.raises(RateLimitExceeded) as raised:
        limiter.acquire_or_raise("tenant")
    assert raised.value.to_dict() == {
        "error_kind": "rate_limited",
        "key": "tenant",
        "retry_after": 5.0,
        "message": str(raised.value),
    }
    json.dumps(raised.value.to_dict())


def test_rate_limiter_snapshot_round_trip() -> None:
    clock = ManualClock()
    limiter = RateLimiter(limit=2, window_seconds=20, clock=clock)
    limiter.allow("x")
    restored = RateLimiter.from_dict(json.loads(json.dumps(limiter.to_dict())), clock=clock)
    assert restored.to_dict() == limiter.to_dict()
    assert restored.allow("x") is True
    assert restored.allow("x") is False


def test_rate_limiter_is_thread_safe() -> None:
    limiter = RateLimiter(limit=7, window_seconds=60)
    with ThreadPoolExecutor(max_workers=16) as pool:
        decisions = list(pool.map(lambda _: limiter.allow("shared"), range(100)))
    assert sum(decisions) == 7


def test_rate_limiter_validates_configuration_and_keys() -> None:
    with pytest.raises(ValueError):
        RateLimiter(limit=0)
    with pytest.raises(ValueError):
        RateLimiter(limit=1, window_seconds=0)
    limiter = RateLimiter(limit=1)
    with pytest.raises(ValueError):
        limiter.allow("")


def test_circuit_transitions_closed_open_half_open_closed() -> None:
    clock = ManualClock()
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=5, clock=clock)

    assert breaker.state == CircuitState.CLOSED.value
    with pytest.raises(ValueError):
        breaker.call(lambda: (_ for _ in ()).throw(ValueError("bad")))
    assert breaker.state == "closed"
    with pytest.raises(ConnectionError):
        breaker.call(lambda: (_ for _ in ()).throw(ConnectionError("down")))
    assert breaker.state == "open"
    assert breaker.failure_count == 2

    with pytest.raises(CircuitOpenError) as raised:
        breaker.call(lambda: "blocked")
    assert raised.value.retry_after == 5
    assert raised.value.state == "open"

    clock.advance(5)
    assert breaker.state == "half_open"
    assert breaker.call(lambda: "recovered") == "recovered"
    assert breaker.state == "closed"
    assert breaker.failure_count == 0


def test_half_open_allows_one_probe_and_reopens_on_failure() -> None:
    clock = ManualClock()
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=3, clock=clock)
    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("down")))
    clock.advance(3)
    breaker.before_call()
    assert breaker.state == "half_open"
    with pytest.raises(CircuitOpenError) as raised:
        breaker.before_call()
    assert raised.value.retry_after == 0
    breaker.record_failure(TimeoutError("still down"))
    assert breaker.state == "open"


def test_circuit_snapshot_round_trip_and_reset() -> None:
    clock = ManualClock()
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=9, name="search", clock=clock)
    with pytest.raises(OSError):
        breaker.call(lambda: (_ for _ in ()).throw(OSError("down")))
    restored = CircuitBreaker.from_dict(json.loads(json.dumps(breaker.to_dict())), clock=clock)
    assert restored.to_dict() == breaker.to_dict()
    restored.reset()
    assert restored.state == "closed"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError("slow"), "timeout"),
        (RateLimitExceeded("x", 1), "rate_limited"),
        (CircuitOpenError("x", 1), "circuit_open"),
        (ValueError("bad"), "validation_error"),
        (ConnectionError("down"), "provider_error"),
        (RuntimeError("unknown"), "unknown_error"),
    ],
)
def test_failure_classification_is_stable(error: BaseException, expected: str) -> None:
    assert classify_failure(error) == expected
