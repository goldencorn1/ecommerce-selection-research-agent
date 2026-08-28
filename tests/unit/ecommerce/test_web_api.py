from fastapi.testclient import TestClient

from src.server.app import app


def test_ecommerce_web_health_and_mock_research():
    with TestClient(app) as client:
        health = client.get("/api/ecommerce/health")
        assert health.status_code == 200
        assert health.json()["mock_available"] is True

        fallback_ui = client.get("/ecommerce")
        assert fallback_ui.status_code == 200
        assert "电商选品研究工作台" in fallback_ui.text
        assert "验证卡片" in fallback_ui.text
        assert "确认导入当前报告" in fallback_ui.text
        assert "五大报告板块" in fallback_ui.text
        assert "status-grid" in fallback_ui.text

        evaluation = client.get("/api/ecommerce/evaluation-summary")
        assert evaluation.status_code == 200
        assert evaluation.json()["summary"]["total_case_count"] == 50
        assert evaluation.json()["summary"]["success_rate"] == 1.0

        response = client.post(
            "/api/ecommerce/research",
            headers={"X-Workspace-Id": "web-api-test"},
            json={
                "category": "可折叠露营桌",
                "market": "中国大陆电商",
                "mode": "mock",
                "model": "mock",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert len(payload["report"]["recommendations"]) == 3
    assert payload["candidate_catalog"]["status"] == "candidate_only"
    assert {event["stage"] for event in payload["progress_events"]} >= {
        "search",
        "clean",
        "score",
        "report",
        "complete",
    }
    assert payload["report_quality_gates"]["report_product_ready"] is True
    assert payload["agent_plan"]
    assert payload["agent_results"]
    assert payload["knowledge_status"] == "not_used"
    assert payload["trace_id"]
    assert payload["quality_audit"]["status"] == "degraded"
    assert payload["quality_audit"]["gates"]["interface_success"] is False
    assert "<!doctype html>" in payload["report_html"].lower()
    history_id = payload["history_id"]

    with TestClient(app) as client:
        observations = client.get("/api/ecommerce/observability?limit=10")
        assert observations.status_code == 200
        observation_payload = observations.json()
        assert observation_payload["summary"]["traced_run_count"] >= 1
        assert observation_payload["summary"]["status_counts"]["success"] >= 1
        assert any(
            event.get("trace_id") == payload["trace_id"]
            for event in observation_payload["events"]
        )
        history = client.get(
            "/api/ecommerce/history",
            headers={"X-Workspace-Id": "web-api-test"},
        )
        assert history.status_code == 200
        assert any(item["history_id"] == history_id for item in history.json()["reports"])

        replay = client.post(
            f"/api/ecommerce/history/{history_id}/replay",
            headers={"X-Workspace-Id": "web-api-test"},
        )
        assert replay.status_code == 200
        assert replay.json()["replayed"] is True

        comparison = client.post(
            "/api/ecommerce/compare",
            headers={"X-Workspace-Id": "web-api-test"},
            json={"report_ids": [history_id]},
        )
        assert comparison.status_code == 200
        assert comparison.json()["matched_count"] == 1

        preview = client.post(
            "/api/ecommerce/excel/preview",
            files={
                "file": (
                    "sample.csv",
                    "product_name,platform\n折叠桌,示例平台\n".encode("utf-8"),
                    "text/csv",
                )
            },
        )
        assert preview.status_code == 200
        assert preview.json()["preview"]["row_count"] == 1
        assert preview.json()["preview"]["status"] == "needs_columns"

        recommendation = payload["report"]["recommendations"][0]["product_name"]
        csv = (
            "推荐方向,商品名称,平台,商品链接,核验人,核验时间,售价,销量,销量周期,供应商成本,库存状态,合规状态,结论,证据ID\n"
            f"{recommendation},真实商品,淘宝,https://example.test/product,tester,2026-08-13T10:00:00+08:00,129,3200,近30天,58,有货,通过,通过,manual-web-001\n"
        ).encode("utf-8")
        validation = client.post(
            "/api/ecommerce/excel/validate",
            headers={"X-Workspace-Id": "web-api-test"},
            data={"report_id": history_id, "mapping_json": "{}"},
            files={"file": ("verified.csv", csv, "text/csv")},
        )
        assert validation.status_code == 200
        assert validation.json()["status"] == "success"
        assert validation.json()["validation"]["imported_count"] == 1

        imported = client.post(
            "/api/ecommerce/excel/import",
            headers={"X-Workspace-Id": "web-api-test"},
            data={"report_id": history_id, "mapping_json": "{}", "confirm": "true"},
            files={"file": ("verified.csv", csv, "text/csv")},
        )
        assert imported.status_code == 200
        assert imported.json()["status"] == "success"
        assert imported.json()["imported_count"] == 1


def test_ecommerce_web_private_knowledge_upload_is_used_as_candidate_evidence():
    workspace_id = "web-knowledge-test"
    with TestClient(app) as client:
        uploaded = client.post(
            "/api/ecommerce/knowledge/upload",
            headers={"X-Workspace-Id": workspace_id},
            files={
                "file": (
                    "catalog.csv",
                    "product,title,content,price\n折叠桌,折叠桌 中国大陆电商,折叠桌可收纳和快速展开,199\n".encode("utf-8"),
                    "text/csv",
                )
            },
        )
        assert uploaded.status_code == 200
        upload_payload = uploaded.json()
        assert upload_payload["record_count"] == 1

        response = client.post(
            "/api/ecommerce/research",
            headers={"X-Workspace-Id": workspace_id},
            json={
                "category": "折叠桌",
                "mode": "mock",
                "model": "mock",
                "knowledge_file_id": upload_payload["knowledge_file_id"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["knowledge_status"] == "success"
    assert payload["knowledge_details"]["hit_count"] == 1
    assert any(item["source_type"] == "local" for item in payload["report"]["evidence"])
