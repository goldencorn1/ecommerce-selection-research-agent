from __future__ import annotations

import json

from src.ecommerce_graph import run_ecommerce_graph


def test_private_knowledge_hits_join_the_existing_evidence_chain(tmp_path):
    path = tmp_path / "private.jsonl"
    path.write_text(
        json.dumps(
            {
                "record_id": "sku-camping-1",
                "product": "可折叠露营桌",
                "supplier": "供应商 A",
                "price": 139,
                "cost": 82,
                "platform": "内部商品库",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    state = run_ecommerce_graph(
        {
            "category": "可折叠露营桌",
            "knowledge_config": {
                "path": str(path),
                "retrieval_mode": "vector",
                "rerank": True,
                "top_k": 2,
            },
        }
    )

    assert state["ecommerce_knowledge_status"] == "success"
    assert state["ecommerce_knowledge_details"]["hit_count"] == 1
    local_hits = [
        item
        for item in state["ecommerce_report"]["evidence"]
        if item["source_type"] == "local"
    ]
    assert local_hits
    assert "private-knowledge" in local_hits[0]["supports"]
    assert local_hits[0]["source"].startswith("local://")


def test_private_knowledge_miss_keeps_mock_report_running(tmp_path):
    path = tmp_path / "unrelated.jsonl"
    path.write_text(
        json.dumps({"record_id": "other", "product": "瑜伽垫"}, ensure_ascii=False),
        encoding="utf-8",
    )

    state = run_ecommerce_graph(
        {
            "category": "可折叠露营桌",
            "knowledge_config": {"path": str(path)},
        }
    )

    assert state["ecommerce_knowledge_status"] == "no_hit"
    assert state["ecommerce_report"]["recommendations"]
    assert not any(
        item["source_type"] == "local" for item in state["ecommerce_report"]["evidence"]
    )


def test_private_knowledge_load_failure_degrades_without_blocking_report(tmp_path):
    state = run_ecommerce_graph(
        {
            "category": "桌面收纳盒",
            "knowledge_config": {"path": str(tmp_path / "missing.csv")},
        }
    )

    assert state["ecommerce_report"]["recommendations"]
    assert any("私有知识加载失败" in warning for warning in state["ecommerce_report"]["warnings"])
