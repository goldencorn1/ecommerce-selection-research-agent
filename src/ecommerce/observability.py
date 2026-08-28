"""Structured, in-memory observation events for local workflow instrumentation."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import threading
from time import perf_counter
from typing import Any, Protocol


def _json_safe(value: Any) -> Any:
    """Convert arbitrary attributes to a value accepted by ``json.dumps``."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return _json_safe(value.value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(mode="json"))
    if hasattr(value, "to_dict"):
        return _json_safe(value.to_dict())
    return repr(value)


def _timestamp(value: str | datetime | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


@dataclass(frozen=True)
class ObservationEvent:
    """A JSON-safe event representing one observable workflow operation."""

    name: str
    kind: str = "observation"
    status: str = "success"
    timestamp: str = field(default_factory=lambda: _timestamp(None))
    duration_ms: float | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    error_kind: str | None = None
    trace_id: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must be non-empty")
        object.__setattr__(self, "timestamp", _timestamp(self.timestamp))
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("duration_ms must be non-negative")
        object.__setattr__(self, "attributes", _json_safe(dict(self.attributes)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "timestamp": self.timestamp,
            "duration_ms": None if self.duration_ms is None else round(self.duration_ms, 6),
            "attributes": _json_safe(self.attributes),
            "error_kind": self.error_kind,
            "trace_id": self.trace_id,
        }

    model_dump = to_dict

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ObservationEvent":
        return cls(
            name=str(data["name"]),
            kind=str(data.get("kind", "observation")),
            status=str(data.get("status", "success")),
            timestamp=data.get("timestamp"),
            duration_ms=(
                None if data.get("duration_ms") is None else float(data["duration_ms"])
            ),
            attributes=dict(data.get("attributes", {})),
            error_kind=(None if data.get("error_kind") is None else str(data["error_kind"])),
            trace_id=(None if data.get("trace_id") is None else str(data["trace_id"])),
        )


class ObservationSink(Protocol):
    def record(self, event: ObservationEvent) -> ObservationEvent:
        ...


class MemoryObservationRecorder:
    """Thread-safe bounded recorder and sink for structured events."""

    def __init__(self, max_events: int | None = None) -> None:
        if max_events is not None and max_events < 1:
            raise ValueError("max_events must be positive")
        self.max_events = max_events
        self._events: list[ObservationEvent] = []
        self._lock = threading.RLock()

    def record(self, event: ObservationEvent | None = None, **fields: Any) -> ObservationEvent:
        if event is None:
            event = ObservationEvent(**fields)
        elif fields:
            raise TypeError("fields cannot be supplied when event is provided")
        if not isinstance(event, ObservationEvent):
            raise TypeError("event must be an ObservationEvent")
        with self._lock:
            self._events.append(event)
            if self.max_events is not None:
                del self._events[:-self.max_events]
        return event

    emit = record

    def events(self) -> list[ObservationEvent]:
        with self._lock:
            return list(self._events)

    def recent(self, limit: int = 10) -> list[ObservationEvent]:
        if limit < 0:
            raise ValueError("limit must be non-negative")
        with self._lock:
            return list(self._events[-limit:]) if limit else []

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def to_list(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events()]

    def to_json(self) -> str:
        return json.dumps(self.to_list(), ensure_ascii=False, sort_keys=True)

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)

    def __iter__(self) -> Iterator[ObservationEvent]:
        return iter(self.events())

    @contextmanager
    def span(
        self,
        name: str,
        *,
        kind: str = "span",
        attributes: Mapping[str, Any] | None = None,
        trace_id: str | None = None,
    ):
        started = perf_counter()
        try:
            yield
        except BaseException as error:
            from .resilience import classify_failure

            self.record(
                ObservationEvent(
                    name=name,
                    kind=kind,
                    status="error",
                    duration_ms=(perf_counter() - started) * 1000,
                    attributes=attributes or {},
                    error_kind=classify_failure(error),
                    trace_id=trace_id,
                )
            )
            raise
        else:
            self.record(
                ObservationEvent(
                    name=name,
                    kind=kind,
                    status="success",
                    duration_ms=(perf_counter() - started) * 1000,
                    attributes=attributes or {},
                    trace_id=trace_id,
                )
            )


ObservationRecorder = MemoryObservationRecorder
MemoryObservationSink = MemoryObservationRecorder


__all__ = [
    "MemoryObservationRecorder",
    "MemoryObservationSink",
    "ObservationEvent",
    "ObservationRecorder",
    "ObservationSink",
]
