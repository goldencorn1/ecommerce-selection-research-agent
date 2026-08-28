"""Create a self-contained offline demo bundle for the e-commerce MVP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .provenance import build_candidate_catalog
from .provenance.templates import build_unverified_verification_records
from .provenance.verification import (
    report_fingerprint,
    run_verification_preflight,
    write_verification_records,
)
from .report_export import render_html_comparison, render_html_report
from ..ecommerce_graph import run_ecommerce_graph, run_ecommerce_report_snapshot


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _report_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "report": state["ecommerce_report"],
        "report_fingerprint": state["ecommerce_report_fingerprint"],
        "run_metrics": state["ecommerce_metrics"],
        "search_status": state["ecommerce_search_status"],
        "search_details": state["ecommerce_search_details"],
        "citation_validation": state["ecommerce_citation_validation"],
        "verification_records": state["ecommerce_verification_records"],
        "verification_validation": state["ecommerce_verification_validation"],
    }


def run_offline_demo(
    output_dir: str | Path,
    *,
    category: str,
    market: str,
    customer: str | None = None,
    price_min: float = 99.0,
    price_max: float = 299.0,
    top_n: int = 3,
) -> dict[str, Any]:
    """Run Mock mode and write report, catalog, replay, and summary artifacts."""

    target = Path(output_dir)
    request: dict[str, Any] = {
        "category": category,
        "target_market": market,
        "price_min": price_min,
        "price_max": price_max,
        "top_n": top_n,
        "search_enabled": False,
        "model_config": {"enabled": False},
    }
    if customer:
        request["target_customer"] = customer

    state = run_ecommerce_graph(request)
    report_payload = _report_payload(state)
    report_path = target / "report.json"
    markdown_path = target / "report.md"
    html_path = target / "report.html"
    catalog_path = target / "candidate-catalog.json"
    replay_path = target / "snapshot-replay.json"
    verification_demo_path = target / "commercial-verification-demo-only.jsonl"
    verification_audit_path = target / "commercial-verification-preflight.json"
    summary_path = target / "summary.json"
    _write_json(report_path, report_payload)
    markdown_path.write_text(state["final_report"], encoding="utf-8")
    html_path.write_text(
        render_html_report(
            report_payload["report"],
            search_status=state["ecommerce_search_status"],
            model_status=state["ecommerce_metrics"].get("model_status", "unknown"),
        ),
        encoding="utf-8",
    )

    catalog = build_candidate_catalog(report_payload["report"])
    _write_json(catalog_path, catalog)

    # C4 demo-only path: show the complete handoff without fabricating
    # commercial facts.  These records are intentionally conditional/pending
    # and must remain blocked by the commercial decision gate.
    demo_records = build_unverified_verification_records(
        report_payload["report"], run_id="DEMO_ONLY"
    )
    write_verification_records(verification_demo_path, demo_records)
    verification_audit = run_verification_preflight(
        report_path, verification_demo_path
    )
    _write_json(verification_audit_path, verification_audit)

    replay_state = run_ecommerce_report_snapshot(report_path)
    replay_payload = _report_payload(replay_state)
    _write_json(replay_path, replay_payload)

    summary = {
        "schema_version": "1.0",
        "status": "success",
        "mode": "offline_demo",
        "category": category,
        "report_fingerprint": report_fingerprint(state["ecommerce_report"]),
        "recommendation_count": len(state["ecommerce_report"].get("recommendations", [])),
        "candidate_count": catalog["candidate_count"],
        "average_score": round(
            sum(
                item["score"]["total"]
                for item in state["ecommerce_report"].get("recommendations", [])
            )
            / max(len(state["ecommerce_report"].get("recommendations", [])), 1),
            2,
        ),
        "warning_count": len(state["ecommerce_report"].get("warnings", [])),
        "search_status": state["ecommerce_search_status"],
        "model_status": state["ecommerce_metrics"].get("model_status"),
        "replay_mode": replay_state["ecommerce_metrics"].get("mode"),
        "replay_external_request_count": replay_state["ecommerce_metrics"].get(
            "external_request_count", 0
        ),
        "verification_status": state["ecommerce_verification_validation"].get(
            "complete", False
        ),
        "commercial_verification_demo": {
            "label": "DEMO_ONLY",
            "status": verification_audit["status"],
            "record_count": verification_audit["record_count"],
            "commercial_decision_ready": False,
            "message": "演示数据仅用于展示核验流程，不代表真实商品、销量、成本、库存或合规事实。",
        },
        "files": {
            "report": str(report_path),
            "markdown_report": str(markdown_path),
            "html_report": str(html_path),
            "candidate_catalog": str(catalog_path),
            "snapshot_replay": str(replay_path),
            "commercial_verification_demo": str(verification_demo_path),
            "commercial_verification_audit": str(verification_audit_path),
        },
        "warnings": [
            "这是离线 Mock 演示包，不代表真实市场或商业事实。",
            "候选目录仅用于展示证据聚合和排序流程。",
        ],
    }
    _write_json(summary_path, summary)
    return summary


def run_offline_demo_suite(
    output_dir: str | Path,
    *,
    categories: list[str],
    market: str = "中国大陆电商",
) -> dict[str, Any]:
    """Run several independent offline demos and write a comparison index."""

    normalized = list(dict.fromkeys(item.strip() for item in categories if item.strip()))
    if not normalized:
        raise ValueError("at least one demo category is required")
    root = Path(output_dir)
    rows: list[dict[str, Any]] = []
    for index, category in enumerate(normalized, 1):
        category_dir = root / f"case-{index:02d}"
        summary = run_offline_demo(category_dir, category=category, market=market)
        rows.append(
            {
                "category": category,
                "recommendation_count": summary["recommendation_count"],
                "candidate_count": summary["candidate_count"],
                "average_score": summary["average_score"],
                "warning_count": summary["warning_count"],
                "report_html": f"case-{index:02d}/report.html",
                "summary": f"case-{index:02d}/summary.json",
            }
        )
    comparison = {
        "schema_version": "1.0",
        "status": "success",
        "mode": "offline_demo_suite",
        "category_count": len(rows),
        "categories": rows,
        "warnings": ["全部结果来自 Mock 数据，仅用于离线流程演示和横向比较。"],
    }
    _write_json(root / "comparison.json", comparison)
    (root / "index.html").parent.mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text(render_html_comparison(rows), encoding="utf-8")
    comparison["index_html"] = str(root / "index.html")
    return comparison
