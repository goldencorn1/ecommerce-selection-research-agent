from datetime import datetime, timezone

import pytest

from src.ecommerce import run_mock_research
from src.ecommerce.provenance import (
    CommercialVerificationRecord,
    VerificationCompliance,
    VerificationCost,
    VerificationInventory,
    VerificationPrice,
    VerificationSales,
    read_verification_records,
    report_fingerprint,
    run_verification_preflight,
    validate_verification_records,
    write_verification_records,
)


def _record(recommendation_id: str) -> CommercialVerificationRecord:
    return CommercialVerificationRecord(
        verification_id=f"verify-{recommendation_id}",
        run_id="run-1",
        recommendation_id=recommendation_id,
        product_name="具体商品",
        platform="淘宝",
        detail_page_url="https://example.test/product",
        verifier="tester",
        verified_at=datetime(2026, 8, 13, tzinfo=timezone.utc),
        price=VerificationPrice(amount="129.00"),
        sales=VerificationSales(value=3200, unit="件", period="近30天"),
        cost=VerificationCost(unit_cost="58.00"),
        inventory=VerificationInventory(status="in_stock", quantity=800),
        compliance=VerificationCompliance(status="passed", notes="已核验"),
        conclusion="pass",
        evidence_ids=["manual-product-page-id"],
    )


def test_verification_jsonl_round_trip_is_utf8(tmp_path):
    report = run_mock_research("可折叠露营桌").report
    records = [_record(item.product_name) for item in report.recommendations]
    path = tmp_path / "verifications.jsonl"

    assert write_verification_records(path, records) == 3
    loaded = read_verification_records(path)

    assert len(loaded) == 3
    assert loaded[0].price.amount == records[0].price.amount
    assert "淘宝" in path.read_text(encoding="utf-8")


def test_verification_reader_accepts_pretty_json_object(tmp_path):
    record = _record("推荐方向")
    path = tmp_path / "pretty-record.json"
    path.write_text(
        __import__("json").dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    loaded = read_verification_records(path)

    assert loaded == [record]


def test_verification_gate_requires_all_fresh_passing_recommendations():
    report = run_mock_research("可折叠露营桌").report
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)

    incomplete = validate_verification_records(report, [_record(report.recommendations[0].product_name)], now=now)
    complete = validate_verification_records(
        report,
        [_record(item.product_name) for item in report.recommendations],
        now=now,
        valid_evidence_ids={item.evidence_id for item in report.evidence},
    )

    assert incomplete.complete is False
    assert incomplete.covered_recommendations == 1
    assert complete.complete is True
    assert complete.blocking_reasons == []


def test_verification_record_rejects_insecure_url():
    with pytest.raises(ValueError, match=r"absolute http\(s\) URL"):
        CommercialVerificationRecord.model_validate(
            _record("x").model_dump(mode="json")
            | {"detail_page_url": "javascript:alert(1)"}
        )


def test_verification_preflight_blocks_before_research(tmp_path):
    report = run_mock_research("可折叠露营桌").report
    report_path = tmp_path / "report.json"
    report_path.write_text(
        __import__("json").dumps({"report": report.model_dump(mode="json")}, ensure_ascii=False),
        encoding="utf-8",
    )
    records_path = tmp_path / "records.jsonl"
    write_verification_records(records_path, [])

    result = run_verification_preflight(report_path, records_path)

    assert result["status"] == "blocked"
    assert result["validation"]["complete"] is False
    assert len(result["validation"]["missing_recommendations"]) == 3
    assert result["placeholder_record_count"] == 0


def test_verification_preflight_passes_complete_manual_records(tmp_path):
    report = run_mock_research("可折叠露营桌").report
    report_path = tmp_path / "report.json"
    report_path.write_text(
        __import__("json").dumps(
            {
                "report": report.model_dump(mode="json"),
                "ecommerce_citation_validation": {"complete": True},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    records_path = tmp_path / "records.jsonl"
    write_verification_records(
        records_path,
        [
            _record(item.product_name).model_copy(
                update={"report_fingerprint": report_fingerprint(report)}
            )
            for item in report.recommendations
        ],
    )

    result = run_verification_preflight(report_path, records_path)

    assert result["status"] == "pass"
    assert result["validation"]["complete"] is True
    assert result["placeholder_record_count"] == 0
    assert result["report_fingerprint"] == report_fingerprint(report)


def test_verification_preflight_blocks_records_from_another_report(tmp_path):
    original_report = run_mock_research("可折叠露营桌").report
    changed_report = run_mock_research("便携榨汁杯").report
    report_path = tmp_path / "report.json"
    report_path.write_text(
        __import__("json").dumps(
            {
                "report": changed_report.model_dump(mode="json"),
                "ecommerce_citation_validation": {"complete": True},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    records_path = tmp_path / "records.jsonl"
    write_verification_records(
        records_path,
        [
            _record(item.product_name).model_copy(
                update={"report_fingerprint": report_fingerprint(original_report)}
            )
            for item in changed_report.recommendations
        ],
    )

    result = run_verification_preflight(report_path, records_path)

    assert result["status"] == "blocked"
    assert any("报告指纹不匹配" in reason for reason in result["validation"]["blocking_reasons"])
