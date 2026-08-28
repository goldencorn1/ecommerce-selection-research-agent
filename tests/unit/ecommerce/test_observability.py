"""Tests for the standalone A5 observation layer."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import json

import pytest

from src.ecommerce.observability import (
    MemoryObservationRecorder,
    ObservationEvent,
    ObservationRecorder,
)


class ExampleStatus(Enum):
    READY = "ready"


def test_event_normalizes_attributes_and_round_trips_as_json() -> None:
    event = ObservationEvent(
        name="research",
        kind="workflow",
        status="success",
        timestamp="2026-01-01T00:00:00+00:00",
        duration_ms=1.23456789,
        attributes={"status": ExampleStatus.READY, "set": {"a", "b"}, "object": object()},
    )
    payload = event.to_dict()
    assert payload["attributes"]["status"] == "ready"
    assert isinstance(payload["attributes"]["set"], list)
    assert json.loads(event.to_json()) == payload
    assert ObservationEvent.from_dict(payload).to_dict() == payload


def test_event_validates_name_and_duration() -> None:
    with pytest.raises(ValueError):
        ObservationEvent(name="")
    with pytest.raises(ValueError):
        ObservationEvent(name="bad", duration_ms=-1)


def test_memory_recorder_records_recent_clears_and_bounds() -> None:
    recorder = MemoryObservationRecorder(max_events=2)
    first = recorder.record(name="one")
    recorder.record(name="two")
    recorder.record(name="three")
    assert len(recorder) == 2
    assert [event.name for event in recorder.recent(1)] == ["three"]
    assert [event.name for event in recorder.events()] == ["two", "three"]
    assert recorder.record(first) is first
    assert [event.name for event in recorder.recent(2)] == ["three", "one"]
    assert json.loads(recorder.to_json())[0]["name"] == "three"
    recorder.clear()
    assert len(recorder) == 0
    assert recorder.recent() == []


def test_recorder_is_a_sink_and_thread_safe() -> None:
    recorder: ObservationRecorder = MemoryObservationRecorder()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: recorder.record(name=f"event-{i}"), range(100)))
    assert len(recorder) == 100
    assert len(recorder.to_list()) == 100


def test_span_records_success_and_failure_with_duration() -> None:
    recorder = MemoryObservationRecorder()
    with recorder.span("ok", attributes={"attempt": 1}):
        pass
    with pytest.raises(TimeoutError):
        with recorder.span("failed"):
            raise TimeoutError("slow")
    events = recorder.events()
    assert events[0].status == "success"
    assert events[0].duration_ms is not None
    assert events[1].status == "error"
    assert events[1].error_kind == "timeout"


def test_recent_and_record_reject_invalid_calls() -> None:
    recorder = MemoryObservationRecorder()
    with pytest.raises(ValueError):
        recorder.recent(-1)
    with pytest.raises(TypeError):
        recorder.record("not an event")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        recorder.record(ObservationEvent(name="x"), name="y")
