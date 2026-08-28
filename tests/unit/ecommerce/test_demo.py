import json

from src.ecommerce.demo import run_offline_demo, run_offline_demo_suite


def test_offline_demo_writes_reusable_bundle(tmp_path):
    summary = run_offline_demo(
        tmp_path,
        category="可折叠露营桌",
        market="中国大陆电商",
    )

    assert summary["status"] == "success"
    assert summary["mode"] == "offline_demo"
    assert summary["search_status"] == "not_used"
    assert summary["model_status"] == "not_used"
    assert summary["replay_mode"] == "snapshot"
    assert summary["replay_external_request_count"] == 0
    assert summary["candidate_count"] > 0
    assert summary["commercial_verification_demo"]["label"] == "DEMO_ONLY"
    assert summary["commercial_verification_demo"]["status"] == "blocked"
    assert summary["commercial_verification_demo"]["commercial_decision_ready"] is False
    for filename in (
        "report.json",
        "report.md",
        "report.html",
        "candidate-catalog.json",
        "snapshot-replay.json",
        "commercial-verification-demo-only.jsonl",
        "commercial-verification-preflight.json",
        "summary.json",
    ):
        assert (tmp_path / filename).exists()

    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    replay = json.loads((tmp_path / "snapshot-replay.json").read_text(encoding="utf-8"))
    verification_audit = json.loads(
        (tmp_path / "commercial-verification-preflight.json").read_text(encoding="utf-8")
    )
    assert report["report_fingerprint"] == replay["report_fingerprint"]
    assert verification_audit["status"] == "blocked"
    assert verification_audit["record_count"] == 3
    assert "<!doctype html>" in (tmp_path / "report.html").read_text(encoding="utf-8")


def test_offline_demo_suite_writes_comparison_index(tmp_path):
    comparison = run_offline_demo_suite(
        tmp_path,
        categories=["可折叠露营桌", "便携榨汁杯", "可折叠露营桌"],
    )

    assert comparison["status"] == "success"
    assert comparison["category_count"] == 2
    assert (tmp_path / "comparison.json").exists()
    assert (tmp_path / "index.html").exists()
    assert "离线对比" in (tmp_path / "index.html").read_text(encoding="utf-8")
