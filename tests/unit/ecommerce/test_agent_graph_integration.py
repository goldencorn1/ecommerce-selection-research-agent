from __future__ import annotations

import json

from src.ecommerce_graph import run_ecommerce_graph, run_ecommerce_report_snapshot


def test_outer_graph_exposes_a1_agent_contract_without_changing_report_fields():
    state = run_ecommerce_graph({"category": "可折叠露营桌"})

    assert state["ecommerce_agent_plan"] == [
        "supervisor",
        "market",
        "competitor",
        "price",
        "customer",
        "risk",
        "report",
        "reviewer",
    ]
    assert set(state["ecommerce_agent_results"]) == set(state["ecommerce_agent_plan"])
    assert state["ecommerce_report"]["recommendations"]
    assert state["ecommerce_report_fingerprint"]
    assert getattr(state["messages"][0], "name", None) == "ecommerce_reviewer"


def test_snapshot_replay_does_not_enter_agent_graph(tmp_path):
    live = run_ecommerce_graph({"category": "桌面收纳盒"})
    report_file = tmp_path / "report.json"
    report_file.write_text(
        json.dumps(
            {
                "report": live["ecommerce_report"],
                "report_fingerprint": live["ecommerce_report_fingerprint"],
                "search_status": live["ecommerce_search_status"],
                "search_details": live["ecommerce_search_details"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    replay = run_ecommerce_report_snapshot(report_file)

    assert replay["ecommerce_metrics"]["mode"] == "snapshot"
    assert replay["ecommerce_metrics"]["external_request_count"] == 0
    assert replay["ecommerce_agent_plan"] == []
    assert replay["ecommerce_agent_results"] == {}
