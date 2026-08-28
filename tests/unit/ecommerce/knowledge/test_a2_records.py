import json

import pytest
from pydantic import ValidationError

from src.ecommerce.knowledge import (
    PrivateKnowledgeRecord,
    load_knowledge_records,
    record_to_evidence,
    records_to_documents,
)


def test_private_record_is_strict_and_json_safe():
    record = PrivateKnowledgeRecord(
        record_id="sku-1",
        product="折叠露营桌",
        supplier="供应商 A",
        sku="SKU-1",
        platform="淘宝",
        price=129,
        cost=80,
        sales_period="近30天",
        inventory=42,
        source_file="catalog.csv",
        metadata={"tags": ["露营", "折叠"]},
    )

    assert json.loads(record.model_dump_json())["sku"] == "SKU-1"
    with pytest.raises(ValidationError):
        PrivateKnowledgeRecord(product="桌子", unexpected="拒绝")
    with pytest.raises(ValidationError):
        PrivateKnowledgeRecord(price=-1)
    with pytest.raises(ValidationError):
        PrivateKnowledgeRecord(inventory=-1)


def test_jsonl_import_skips_blank_and_bad_rows(tmp_path):
    path = tmp_path / "private.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {"sku": "ok", "product": "桌子", "price": 99}, ensure_ascii=False
                ),
                "not-json",
                "",
                json.dumps({"sku": "bad", "price": -3}),
            ]
        ),
        encoding="utf-8",
    )

    records = load_knowledge_records(path)
    assert [record.sku for record in records] == ["ok"]
    assert records[0].source_file == str(path)


def test_csv_import_supports_chinese_and_english_columns(tmp_path):
    path = tmp_path / "catalog.csv"
    path.write_text(
        "商品名称,供应商,SKU,platform,价格,成本,销量周期,库存,更新时间\n"
        "折叠桌,供应商A,S-1,淘宝,129,80,近30天,42,2026-08-15T10:00:00+08:00\n",
        encoding="utf-8",
    )

    records = load_knowledge_records(path)
    assert len(records) == 1
    assert records[0].product == "折叠桌"
    assert records[0].price == 129
    assert records[0].inventory == 42
    assert records[0].updated_at.isoformat().startswith("2026-08-15T10:00:00")


def test_document_import_preserves_source_and_adapts_to_local_document(tmp_path):
    path = tmp_path / "supplier-notes.md"
    path.write_text("供应商交期：7天\n", encoding="utf-8")

    records = load_knowledge_records(path)
    documents = records_to_documents(records)
    assert records[0].source_file == str(path)
    assert documents[0].source.startswith("local://")
    assert "供应商交期" in documents[0].content


def test_private_record_evidence_remains_local_candidate_evidence():
    record = PrivateKnowledgeRecord(
        record_id="sku-2",
        product="收纳盒",
        source_file="inventory.csv",
        updated_at="2026-08-16T00:00:00Z",
    )

    evidence = record_to_evidence(record, confidence=0.8)
    assert evidence.source == "local://inventory.csv"
    assert evidence.source_type == "local"
    assert evidence.confidence == 0.8
    assert evidence.supports == ["local-rag"]
