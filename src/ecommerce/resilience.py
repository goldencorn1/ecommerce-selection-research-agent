"""Small, dependency-free resilience primitives for the e-commerce workflow.

The classes in this module deliberately keep their state local and explicit.  They
are suitable for a single process and can be snapshotted with ``to_dict`` and
restored with ``from_dict``.  A monotonic clock is injected so callers and tests do
not need to sleep in order to exercise time based transitions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from time import monotonic
from typing import Any, TypeVar
import threading


Clock = Callable[[], float]
T = TypeVar("T")


class ResilienceError(RuntimeError):
    """Base class for stable errors raised by this module."""

    error_kind = "resilience_error"

    def to_dict(self) -> dict[str, Any]:
        return {"error_kind": self.error_kind, "message": str(self)}


class RateLimitExceeded(ResilienceError):
    """Raised when a fixed-window limit has no remaining capacity."""

    error_kind = "rate_limited"

    def __init__(self, key: str, retry_after: float) -> None:
        self.key = key
        self.retry_after = max(0.0, float(retry_after))
        super().__init__(
            f"rate limit exceeded for key {key!r}; retry after {self.retry_after:.3f}s"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_kind": self.error_kind,
            "key": self.key,
            "retry_after": self.retry_after,
            "message": str(self),
        }


class CircuitOpenError(ResilienceError):
    """Raised when a circuit is open or another half-open probe is running."""

    error_kind = "circuit_open"

    def __init__(self, name: str, retry_after: float, state: str = "open") -> None:
        self.name = name
        self.retry_after = max(0.0, float(retry_after))
        self.state = state
        super().__init__(
            f"circuit {name!r} is {state}; retry after {self.retry_after:.3f}s"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_kind": self.error_kind,
            "name": self.name,
            "state": self.state,
            "retry_after": self.retry_after,
            "message": str(self),
        }


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


def classify_failure(error: BaseException) -> str:
    """Return a stable, JSON-safe category for an exception."""

    if isinstance(error, RateLimitExceeded):
        return "rate_limited"
    if isinstance(error, CircuitOpenError):
        return "circuit_open"
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, (ValueError, TypeError, KeyError)):
        return "validation_error"
    if isinstance(error, (ConnectionError, OSError)):
        return "provider_error"
    return "unknown_error"


@dataclass
class _Window:
    started_at: float
    count: int = 0


class RateLimiter:
    """Thread-safe fixed-window rate limiter.

    ``allow`` is the non-raising API.  ``acquire`` raises ``RateLimitExceeded``
    and includes the key and exact remaining window in the exception.  The state
    snapshot is intentionally plain JSON data.
    """

    def __init__(
        self,
        limit: int | None = None,
        window_seconds: float = 60.0,
        *,
        max_requests: int | None = None,
        clock: Clock | None = None,
    ) -> None:
        resolved_limit = max_requests if limit is None else limit
        if resolved_limit is None:
            raise TypeError("limit or max_requests is required")
        if resolved_limit < 1:
            raise ValueError("limit must be at least 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.limit = int(resolved_limit)
        self.window_seconds = float(window_seconds)
        self._clock = clock or monotonic
        self._windows: dict[str, _Window] = {}
        self._lock = threading.RLock()

    def _now(self, now: float | None) -> float:
        return float(self._clock() if now is None else now)

    def _window_for(self, key: str, now: float) -> _Window:
        current = self._windows.get(key)
        if current is None or now - current.started_at >= self.window_seconds:
            current = _Window(started_at=now)
            self._windows[key] = current
        return current

    def allow(self, key: str = "default", *, now: float | None = None) -> bool:
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty string")
        current_time = self._now(now)
        with self._lock:
            window = self._window_for(key, current_time)
            if window.count >= self.limit:
                return False
            window.count += 1
            return True

    acquire = allow

    def check(self, key: str = "default", *, now: float | None = None) -> bool:
        return self.allow(key, now=now)

    def try_acquire(self, key: str = "default", *, now: float | None = None) -> bool:
        return self.allow(key, now=now)

    def acquire_or_raise(self, key: str = "default", *, now: float | None = None) -> None:
        current_time = self._now(now)
        if not self.allow(key, now=current_time):
            raise RateLimitExceeded(key, self.retry_after(key, now=current_time))

    def retry_after(self, key: str = "default", *, now: float | None = None) -> float:
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty string")
        current_time = self._now(now)
        with self._lock:
            window = self._windows.get(key)
            if window is None:
                return 0.0
            remaining = self.window_seconds - (current_time - window.started_at)
            return round(max(0.0, remaining), 6) if window.count >= self.limit else 0.0

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "limit": self.limit,
                "window_seconds": self.window_seconds,
                "windows": {
                    key: {"started_at": value.started_at, "count": value.count}
                    for key, value in self._windows.items()
                },
            }

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, clock: Clock | None = None) -> "RateLimiter":
        instance = cls(
            limit=int(data["limit"]),
            window_seconds=float(data["window_seconds"]),
            clock=clock,
        )
        instance._windows = {
            str(key): _Window(
                started_at=float(value["started_at"]), count=int(value["count"])
            )
            for key, value in dict(data.get("windows", {})).items()
        }
        return instance


class CircuitBreaker:
    """Thread-safe closed/open/half-open circuit breaker."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        *,
        name: str = "default",
        clock: Clock | None = None,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be positive")
        if not name:
            raise ValueError("name must be non-empty")
        self.name = name
        self.failure_threshold = int(failure_threshold)
        self.recovery_timeout = float(recovery_timeout)
        self._clock = clock or monotonic
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None
        self._half_open_probe = False
        self._last_failure_kind: str | None = None
        self._lock = threading.RLock()

    @property
    def state(self) -> str:
        with self._lock:
            self._refresh_state(self._clock())
            return self._state.value

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    @property
    def last_failure_kind(self) -> str | None:
        with self._lock:
            return self._last_failure_kind

    def _refresh_state(self, now: float) -> None:
        if (
            self._state is CircuitState.OPEN
            and self._opened_at is not None
            and now - self._opened_at >= self.recovery_timeout
        ):
            self._state = CircuitState.HALF_OPEN

    def _retry_after(self, now: float) -> float:
        if self._opened_at is None:
            return 0.0
        return max(0.0, self.recovery_timeout - (now - self._opened_at))

    def before_call(self) -> None:
        now = float(self._clock())
        with self._lock:
            self._refresh_state(now)
            if self._state is CircuitState.OPEN:
                raise CircuitOpenError(self.name, self._retry_after(now), self.state)
            if self._state is CircuitState.HALF_OPEN:
                if self._half_open_probe:
                    raise CircuitOpenError(self.name, 0.0, self.state)
                self._half_open_probe = True

    def record_success(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._opened_at = None
            self._half_open_probe = False
            self._last_failure_kind = None

    def record_failure(self, error: BaseException) -> str:
        kind = classify_failure(error)
        now = float(self._clock())
        with self._lock:
            self._last_failure_kind = kind
            self._half_open_probe = False
            self._failure_count += 1
            if self._state is CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = now
            return kind

    def call(self, operation: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        self.before_call()
        try:
            result = operation(*args, **kwargs)
        except BaseException as error:
            self.record_failure(error)
            raise
        self.record_success()
        return result

    def reset(self) -> None:
        self.record_success()

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "opened_at": self._opened_at,
                "half_open_probe": self._half_open_probe,
                "last_failure_kind": self._last_failure_kind,
            }

    snapshot = to_dict

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, clock: Clock | None = None) -> "CircuitBreaker":
        instance = cls(
            failure_threshold=int(data["failure_threshold"]),
            recovery_timeout=float(data["recovery_timeout"]),
            name=str(data.get("name", "default")),
            clock=clock,
        )
        with instance._lock:
            instance._state = CircuitState(str(data.get("state", "closed")))
            instance._failure_count = int(data.get("failure_count", 0))
            opened_at = data.get("opened_at")
            instance._opened_at = None if opened_at is None else float(opened_at)
            instance._half_open_probe = bool(data.get("half_open_probe", False))
            last_kind = data.get("last_failure_kind")
            instance._last_failure_kind = None if last_kind is None else str(last_kind)
        return instance


__all__ = [
    "CircuitBreaker",
    "CircuitOpenError",
    "CircuitState",
    "RateLimitExceeded",
    "RateLimiter",
    "ResilienceError",
    "classify_failure",
]
