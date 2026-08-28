from __future__ import annotations

import time
import importlib
from threading import Event

from fastapi.testclient import TestClient

from src.ecommerce.batch import EcommerceBatchTaskManager
from src.server.app import app


def _wait_for_batch(client: TestClient, task_id: str, workspace_id: str) -> dict:
    for _ in range(100):
        response = client.get(
            f"/api/ecommerce/batch/{task_id}",
            headers={"X-Workspace-Id": workspace_id},
        )
        assert response.status_code == 200
        task = response.json()["task"]
        if task["status"] in {"success", "partial", "error", "cancelled"}:
            return task
        time.sleep(0.02)
    raise AssertionError("batch task did not finish in time")


def test_batch_research_runs_multiple_categories_and_persists_each_report():
    workspace_id = "b2-batch-success"
    with TestClient(app) as client:
        response = client.post(
            "/api/ecommerce/batch",
            headers={"X-Workspace-Id": workspace_id},
            json={
                "items": [
                    {"category": "可折叠露营桌"},
                    {"category": "便携榨汁杯"},
                    {"category": "桌面收纳盒"},
                ],
                "mode": "mock",
                "model": "mock",
                "max_concurrency": 2,
            },
        )
        assert response.status_code == 200
        task = _wait_for_batch(client, response.json()["task"]["task_id"], workspace_id)

    assert task["status"] == "success"
    assert task["counts"] == {
        "total": 3,
        "completed": 3,
        "failed": 0,
        "cancelled": 0,
        "running": 0,
    }
    assert {item["category"] for item in task["items"]} == {
        "可折叠露营桌",
        "便携榨汁杯",
        "桌面收纳盒",
    }
    assert all(item["history_id"] for item in task["items"])


def test_batch_exposes_partial_failure_and_can_retry_failed_items(monkeypatch):
    app_module = importlib.import_module("src.server.app")

    original = app_module._run_batch_item

    def flaky(spec, item_id, *, owner_id):
        if spec["category"] == "失败品类":
            raise RuntimeError("synthetic batch failure")
        return original(spec, item_id, owner_id=owner_id)

    monkeypatch.setattr(app_module, "_run_batch_item", flaky)
    workspace_id = "b2-batch-partial"
    with TestClient(app) as client:
        response = client.post(
            "/api/ecommerce/batch",
            headers={"X-Workspace-Id": workspace_id},
            json={
                "items": [{"category": "可折叠露营桌"}, {"category": "失败品类"}],
                "mode": "mock",
            },
        )
        assert response.status_code == 200
        task = _wait_for_batch(client, response.json()["task"]["task_id"], workspace_id)
        assert task["status"] == "partial"
        assert task["counts"]["completed"] == 1
        assert task["counts"]["failed"] == 1
        assert task["items"][1]["error"]["code"] == "item_failed"

        retry = client.post(
            f"/api/ecommerce/batch/{task['task_id']}/retry",
            headers={"X-Workspace-Id": workspace_id},
        )
        assert retry.status_code == 200
        retry_task = _wait_for_batch(
            client, retry.json()["task"]["task_id"], workspace_id
        )

    assert retry_task["status"] == "error"
    assert retry_task["counts"]["failed"] == 1


def test_batch_manager_cancel_marks_queued_items_without_losing_completed_results():
    manager = EcommerceBatchTaskManager(max_workers=2)
    started = Event()
    release = Event()

    def runner(spec, item_id):
        started.set()
        release.wait(timeout=2)
        return {"history_id": f"history-{item_id}"}

    task = manager.create(
        owner_id="manager-test",
        item_specs=[{"category": "一"}, {"category": "二"}],
        mode="mock",
        model="mock",
        max_concurrency=1,
    )
    manager.submit(task["task_id"], runner)
    assert started.wait(timeout=1)
    cancelled = manager.cancel(task["task_id"])
    assert cancelled is not None
    assert cancelled["cancel_requested"] is True
    release.set()

    for _ in range(100):
        final = manager.get(task["task_id"])
        assert final is not None
        if final["status"] == "cancelled":
            break
        time.sleep(0.02)
    else:
        raise AssertionError("cancelled batch task did not settle")

    assert final["counts"]["completed"] == 1
    assert final["counts"]["cancelled"] == 1
