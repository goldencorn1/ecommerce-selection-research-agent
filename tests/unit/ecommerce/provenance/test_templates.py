from src.ecommerce.provenance import (
    build_verification_template,
    build_verification_template_from_report,
    build_unverified_verification_records,
    read_verification_records,
    report_fingerprint,
    write_verification_csv_template_from_report,
    write_verification_template,
)
from src.ecommerce_graph import run_ecommerce_graph


def test_verification_template_is_parseable_and_conditional(tmp_path):
    records = build_verification_template("可折叠露营桌")

    assert len(records) == 3
    assert all(record.conclusion == "conditional" for record in records)
    assert all(record.compliance.status == "pending" for record in records)

    path = tmp_path / "template.jsonl"
    assert write_verification_template(path, "可折叠露营桌") == 3
    assert len(read_verification_records(path)) == 3


def test_report_bound_template_uses_exact_recommendation_ids():
    state = run_ecommerce_graph("可折叠露营桌")
    records = build_verification_template_from_report(state["ecommerce_report"])

    assert [record.recommendation_id for record in records] == [
        item["product_name"] for item in state["ecommerce_report"]["recommendations"]
    ]
    assert all(record.conclusion == "conditional" for record in records)
    assert all(
        record.report_fingerprint == report_fingerprint(state["ecommerce_report"])
        for record in records
    )


def test_unverified_draft_covers_report_without_claiming_pass():
    state = run_ecommerce_graph("可折叠露营桌")
    records = build_unverified_verification_records(state["ecommerce_report"])

    assert len(records) == 3
    assert {record.recommendation_id for record in records} == {
        item["product_name"] for item in state["ecommerce_report"]["recommendations"]
    }
    assert all(record.conclusion == "conditional" for record in records)
    assert all(record.compliance.status == "pending" for record in records)
    assert all(record.report_fingerprint == report_fingerprint(state["ecommerce_report"]) for record in records)


def test_excel_compatible_csv_template_uses_report_recommendations(tmp_path):
    state = run_ecommerce_graph("可折叠露营桌")
    path = tmp_path / "verification-template.csv"

    assert write_verification_csv_template_from_report(path, state["ecommerce_report"]) == 3
    content = path.read_text(encoding="utf-8-sig")

    assert "推荐方向" in content
    assert "商品名称" in content
    assert state["ecommerce_report"]["recommendations"][0]["product_name"] in content
    assert content.count("REPLACE_WITH_REAL_PRODUCT_NAME_") == 3
