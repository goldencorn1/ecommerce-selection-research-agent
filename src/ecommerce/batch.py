"""Thread-safe batch task coordination for e-commerce research jobs."""

from __future__ import annotations

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock, Semaphore
from typing import Any, Callable
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class _BatchTask:
    task_id: str
    owner_id: str
    mode: str
    model: str
    max_concurrency: int
    item_specs: list[dict[str, Any]]
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    status: str = "queued"
    cancel_requested: bool = False
    items: list[dict[str, Any]] = field(default_factory=list)


class EcommerceBatchTaskManager:
    """Run independent category jobs with bounded concurrency.

    The manager intentionally keeps task state in memory. Reports themselves
    are persisted by the existing SQLite report store, so a completed item can
    be replayed even after this process-local task summary is gone.
    """

    def __init__(self, max_workers: int = 8):
        self._lock = Lock()
        self._tasks: dict[str, _BatchTask] = {}
        self._semaphores: dict[str, Semaphore] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="ecommerce-batch",
        )

    def create(
        self,
        *,
        owner_id: str,
        item_specs: list[dict[str, Any]],
        mode: str,
        model: str,
        max_concurrency: int,
    ) -> dict[str, Any]:
        task_id = f"batch-{uuid4()}"
        items = [
            {
                "item_id": f"item-{index}",
                "category": str(spec.get("category", "")),
                "status": "queued",
                "attempts": 0,
                "history_id": None,
                "error": None,
            }
            for index, spec in enumerate(item_specs, start=1)
        ]
        task = _BatchTask(
            task_id=task_id,
            owner_id=owner_id,
            mode=mode,
            model=model,
            max_concurrency=max_concurrency,
            item_specs=deepcopy(item_specs),
            items=items,
        )
        with self._lock:
            self._tasks[task_id] = task
            self._semaphores[task_id] = Semaphore(max_concurrency)
        return self._snapshot(task)

    def submit(
        self,
        task_id: str,
        runner: Callable[[dict[str, Any], str], dict[str, Any]],
    ) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(task_id)
            item_ids = [item["item_id"] for item in task.items]
            task.status = "running"
            task.updated_at = _now()
        for item_id in item_ids:
            self._executor.submit(self._run_item, task_id, item_id, runner)

    def _run_item(
        self,
        task_id: str,
        item_id: str,
        runner: Callable[[dict[str, Any], str], dict[str, Any]],
    ) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            item_index = next(
                (index for index, item in enumerate(task.items) if item["item_id"] == item_id),
                None,
            )
            if item_index is None:
                return
            if task.cancel_requested:
                task.items[item_index]["status"] = "cancelled"
                self._refresh_status_locked(task)
                return
            task.items[item_index]["status"] = "waiting"
            task.items[item_index]["attempts"] += 1
            task.updated_at = _now()
            spec = deepcopy(task.item_specs[item_index])
            semaphore = self._semaphores[task_id]

        with semaphore:
            with self._lock:
                task = self._tasks.get(task_id)
                if task is None:
                    return
                item = task.items[item_index]
                if task.cancel_requested:
                    item["status"] = "cancelled"
                    self._refresh_status_locked(task)
                    return
                item["status"] = "running"
                item["started_at"] = _now()
                task.updated_at = _now()
            try:
                summary = runner(spec, item_id)
            except Exception as exc:  # noqa: BLE001 - task boundary records safe failure
                with self._lock:
                    task = self._tasks.get(task_id)
                    if task is None:
                        return
                    item = task.items[item_index]
                    item.update(
                        {
                            "status": "error",
                            "error": {
                                "code": "item_failed",
                                "type": type(exc).__name__,
                                "message": str(exc)[:240],
                            },
                            "completed_at": _now(),
                        }
                    )
                    self._refresh_status_locked(task)
                return

            with self._lock:
                task = self._tasks.get(task_id)
                if task is None:
                    return
                item = task.items[item_index]
                item.update(
                    {
                        "status": "success",
                        "error": None,
                        "completed_at": _now(),
                        **summary,
                    }
                )
                self._refresh_status_locked(task)

    def cancel(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task.cancel_requested = True
            for item in task.items:
                if item["status"] in {"queued", "waiting"}:
                    item["status"] = "cancelled"
            self._refresh_status_locked(task)
            return self._snapshot(task)

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return self._snapshot(task) if task else None

    def specs_for_failed_items(self, task_id: str) -> tuple[str, list[dict[str, Any]]] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            failed_indexes = [
                index
                for index, item in enumerate(task.items)
                if item["status"] == "error"
            ]
            return task.owner_id, [deepcopy(task.item_specs[index]) for index in failed_indexes]

    @staticmethod
    def _refresh_status_locked(task: _BatchTask) -> None:
        statuses = [item["status"] for item in task.items]
        task.updated_at = _now()
        if any(status in {"queued", "waiting", "running"} for status in statuses):
            task.status = "running"
        elif task.cancel_requested and any(status == "cancelled" for status in statuses):
            task.status = "cancelled"
        elif all(status == "success" for status in statuses):
            task.status = "success"
        elif any(status == "success" for status in statuses):
            task.status = "partial"
        else:
            task.status = "error"

    @staticmethod
    def _snapshot(task: _BatchTask | None) -> dict[str, Any]:
        if task is None:
            return {}
        items = deepcopy(task.items)
        counts = {
            "total": len(items),
            "completed": sum(item["status"] == "success" for item in items),
            "failed": sum(item["status"] == "error" for item in items),
            "cancelled": sum(item["status"] == "cancelled" for item in items),
            "running": sum(item["status"] in {"waiting", "running"} for item in items),
        }
        return {
            "task_id": task.task_id,
            "owner_id": task.owner_id,
            "status": task.status,
            "mode": task.mode,
            "model": task.model,
            "max_concurrency": task.max_concurrency,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "cancel_requested": task.cancel_requested,
            "counts": counts,
            "items": items,
        }
