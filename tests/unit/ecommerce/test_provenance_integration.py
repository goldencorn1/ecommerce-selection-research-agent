from datetime import datetime, timezone

from src.ecommerce_graph import run_ecommerce_graph, run_ecommerce_report_snapshot
from src.ecommerce.provenance import (
    CommercialVerificationRecord,
    VerificationCompliance,
    VerificationCost,
    VerificationInventory,
    VerificationPrice,
    VerificationSales,
    report_fingerprint,
    write_verification_records,
)
import json


def test_graph_exposes_provenance_and_citation_validation():
    state = run_ecommerce_graph("可折叠露营桌")

    assert state["ecommerce_provenance"]
    assert len(state["ecommerce_report_fingerprint"]) == 64
    assert state["ecommerce_citation_validation"]["measured"] == "measured"
    assert state["ecommerce_citation_validation"]["complete"] is True


def test_graph_loads_verification_jsonl_and_keeps_quality_gate_truthful(tmp_path):
    base = run_ecommerce_graph("可折叠露营桌")
    records = [
        CommercialVerificationRecord(
            verification_id=f"verify-{item['product_name']}",
            run_id="run-test",
            report_fingerprint=report_fingerprint(base["ecommerce_report"]),
            recommendation_id=item["product_name"],
            product_name="实际商品",
            platform="淘宝",
            detail_page_url="https://example.test/product",
            verifier="tester",
            verified_at=datetime.now(timezone.utc),
            price=VerificationPrice(amount="129"),
            sales=VerificationSales(value=1, unit="件", period="近30天"),
            cost=VerificationCost(unit_cost="58"),
            inventory=VerificationInventory(status="in_stock", quantity=1),
            compliance=VerificationCompliance(status="passed"),
            conclusion="pass",
            evidence_ids=["manual-product-page-id"],
        )
        for item in base["ecommerce_report"]["recommendations"]
    ]
    path = tmp_path / "records.jsonl"
    write_verification_records(path, records)

    state = run_ecommerce_graph(
        {
            "category": "可折叠露营桌",
            "model_config": {"verification_file": str(path)},
        }
    )

    assert len(state["ecommerce_verification_records"]) == 3
    assert state["ecommerce_verification_validation"]["complete"] is True
    assert state["ecommerce_metrics"]["quality_gates"]["commercial_decision_ready"] is False


def test_report_snapshot_replay_does_not_rerun_research(tmp_path):
    base = run_ecommerce_graph("可折叠露营桌")
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "report": base["ecommerce_report"],
                "report_fingerprint": base["ecommerce_report_fingerprint"],
                "search_status": base["ecommerce_search_status"],
                "search_details": base["ecommerce_search_details"],
                "citation_validation": base["ecommerce_citation_validation"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    replayed = run_ecommerce_report_snapshot(report_path)

    assert replayed["ecommerce_report"] == base["ecommerce_report"]
    assert replayed["ecommerce_report_fingerprint"] == base["ecommerce_report_fingerprint"]
    assert replayed["ecommerce_metrics"]["mode"] == "snapshot"
    assert replayed["ecommerce_metrics"]["external_request_count"] == 0
    assert replayed["ecommerce_verification_validation"]["complete"] is False


def test_report_snapshot_replay_revalidates_bound_records(tmp_path):
    base = run_ecommerce_graph("可折叠露营桌")
    records = [
        CommercialVerificationRecord(
            verification_id=f"verify-{item['product_name']}",
            run_id="run-snapshot",
            report_fingerprint=base["ecommerce_report_fingerprint"],
            recommendation_id=item["product_name"],
            product_name="实际商品",
            platform="淘宝",
            detail_page_url="https://example.test/product",
            verifier="tester",
            verified_at=datetime.now(timezone.utc),
            price=VerificationPrice(amount="129"),
            sales=VerificationSales(value=1, unit="件", period="近30天"),
            cost=VerificationCost(unit_cost="58"),
            inventory=VerificationInventory(status="in_stock", quantity=1),
            compliance=VerificationCompliance(status="passed"),
            conclusion="pass",
            evidence_ids=["manual-product-page-id"],
        )
        for item in base["ecommerce_report"]["recommendations"]
    ]
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "report": base["ecommerce_report"],
                "report_fingerprint": base["ecommerce_report_fingerprint"],
                "citation_validation": {"complete": True},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    records_path = tmp_path / "records.jsonl"
    write_verification_records(records_path, records)

    replayed = run_ecommerce_report_snapshot(
        report_path,
        verification_file=records_path,
    )

    assert replayed["ecommerce_verification_validation"]["complete"] is True
    assert replayed["ecommerce_metrics"]["quality_gates"]["commercial_decision_ready"] is False
