from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from src.ecommerce import run_mock_research
from src.ecommerce.provenance import (
    import_verification_rows,
    preview_import_file,
    report_fingerprint,
    write_excel_import_report,
)


def test_import_verification_rows_supports_chinese_csv_headers(tmp_path):
    report = run_mock_research("可折叠露营桌").report
    recommendation = report.recommendations[0].product_name
    path = tmp_path / "verification.csv"
    path.write_text(
        "推荐方向,商品名称,平台,商品链接,核验人,核验时间,售价,销量,销量周期,供应商成本,库存状态,库存数量,合规状态,合规备注,结论,备注,证据ID\n"
        f"{recommendation},真实商品,淘宝,https://example.test/product,tester,2026-08-13 10:00:00,129.00,3200,近30天,58.00,有货,800,通过,已核验,通过,人工核验,manual-product-001\n",
        encoding="utf-8-sig",
    )

    result = import_verification_rows(path, report)

    assert result.complete is True
    assert len(result.records) == 1
    assert result.records[0].conclusion == "pass"
    assert result.records[0].compliance.status == "passed"
    assert result.records[0].report_fingerprint == report_fingerprint(report)
    assert result.warnings == ["第 2 行核验时间无时区，按 Asia/Shanghai 解释"]


def test_import_verification_rows_reports_missing_columns(tmp_path):
    report = run_mock_research("可折叠露营桌").report
    path = tmp_path / "incomplete.csv"
    path.write_text("商品名称,平台\n商品,淘宝\n", encoding="utf-8")

    result = import_verification_rows(path, report)

    assert result.complete is False
    assert result.records == []
    assert "缺少必需列" in result.errors[0]


def test_preview_exposes_mapping_options_for_manual_correction(tmp_path):
    path = tmp_path / "mapping.csv"
    path.write_text(
        "方向,商品,平台名,链接,核验员,时间,价格,数量,周期,成本,库存,合规,判断,证据\n"
        "方向A,商品A,淘宝,https://example.test/a,甲,2026-08-13T10:00:00+08:00,99,10,近30天,40,有货,通过,通过,e-1\n",
        encoding="utf-8",
    )

    preview = preview_import_file(path)

    assert preview["status"] == "needs_columns"
    assert "product_name" in preview["required_fields"]
    assert "商品" in preview["mapping_options"]["product_name"]


def test_import_verification_rows_accepts_manual_column_mapping(tmp_path):
    report = run_mock_research("可折叠露营桌").report
    recommendation = report.recommendations[0].product_name
    path = tmp_path / "custom-mapping.csv"
    path.write_text(
        "方向,商品,平台名,链接,核验员,时间,价格,数量,周期,成本,库存,合规,判断,证据\n"
        f"{recommendation},商品A,淘宝,https://example.test/a,甲,2026-08-13T10:00:00+08:00,99,10,近30天,40,有货,通过,通过,e-1\n",
        encoding="utf-8",
    )

    result = import_verification_rows(
        path,
        report,
        column_mapping={
            "recommendation_id": "方向",
            "product_name": "商品",
            "platform": "平台名",
            "detail_page_url": "链接",
            "verifier": "核验员",
            "verified_at": "时间",
            "price_amount": "价格",
            "sales_value": "数量",
            "sales_period": "周期",
            "cost_unit": "成本",
            "inventory_status": "库存",
            "compliance_status": "合规",
            "conclusion": "判断",
            "evidence_ids": "证据",
        },
    )

    assert result.complete is True
    assert result.records[0].product_name == "商品A"


def test_import_verification_rows_rejects_recommendation_from_another_report(tmp_path):
    report = run_mock_research("可折叠露营桌").report
    path = tmp_path / "unknown.csv"
    path.write_text(
        "推荐方向,商品名称,平台,商品链接,核验人,核验时间,售价,销量,销量周期,供应商成本,库存状态,合规状态,结论,证据ID\n"
        "不存在的推荐,真实商品,淘宝,https://example.test/product,tester,2026-08-13T10:00:00+08:00,129,1,近30天,58,有货,通过,通过,manual-unknown\n",
        encoding="utf-8",
    )

    result = import_verification_rows(path, report)

    assert result.complete is False
    assert "推荐方向不属于当前报告" in result.errors[0]


def test_import_verification_rows_reads_xlsx_without_openpyxl(tmp_path, monkeypatch):
    report = run_mock_research("可折叠露营桌").report
    recommendation = report.recommendations[0].product_name
    path = tmp_path / "verification.xlsx"
    headers = [
        "推荐方向",
        "商品名称",
        "平台",
        "商品链接",
        "核验人",
        "核验时间",
        "售价",
        "销量",
        "销量周期",
        "供应商成本",
        "库存状态",
        "合规状态",
        "结论",
        "证据ID",
    ]
    values = [
        recommendation,
        "真实商品",
        "淘宝",
        "https://example.test/product",
        "tester",
        "2026-08-13 10:00:00",
        "129.00",
        "3200",
        "近30天",
        "58.00",
        "有货",
        "通过",
        "通过",
        "manual-xlsx-001",
    ]

    def cell(row_number, column_number, value):
        column = ""
        number = column_number
        while number:
            number, remainder = divmod(number - 1, 26)
            column = chr(65 + remainder) + column
        escaped = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f'<c r="{column}{row_number}" t="inlineStr"><is><t>{escaped}</t></is></c>'

    rows = "".join(
        f'<row r="{row_number}">{"".join(cell(row_number, index, value) for index, value in enumerate(row, 1))}</row>'
        for row_number, row in enumerate([headers, values], 1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="核验数据" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{rows}</sheetData></worksheet>"
    )
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)

    def missing_openpyxl(*args, **kwargs):
        raise ImportError("openpyxl is intentionally unavailable in this test")

    monkeypatch.setattr(pd, "read_excel", missing_openpyxl)
    result = import_verification_rows(path, report, sheet_name="核验数据")

    assert result.complete is True
    assert result.records[0].product_name == "真实商品"
    assert result.records[0].evidence_ids == ["manual-xlsx-001"]


def test_import_verification_rows_reports_quality_warnings(tmp_path):
    report = run_mock_research("可折叠露营桌").report
    recommendation = report.recommendations[0].product_name
    path = tmp_path / "quality.csv"
    header = "推荐方向,商品名称,平台,商品链接,核验人,核验时间,售价,销量,销量周期,供应商成本,库存状态,合规状态,结论,证据ID\n"
    row = f"{recommendation},重复商品,淘宝,https://example.invalid/item,tester,2026-08-13T10:00:00+08:00,0,1,近30天,0,未知,待核验,条件通过,manual-quality\n"
    path.write_text(header + row + row, encoding="utf-8")

    result = import_verification_rows(path, report)

    assert result.complete is True
    assert result.quality_checks == {
        "duplicate_product_rows": 1,
        "zero_price_rows": 2,
        "cost_not_below_price_rows": 0,
        "placeholder_url_rows": 2,
    }
    assert any("完全重复" in warning for warning in result.warnings)
    audit_path = tmp_path / "import-audit.json"
    write_excel_import_report(
        audit_path,
        result,
        input_file=path,
        output_file=tmp_path / "records.jsonl",
    )
    assert '"status": "success"' in audit_path.read_text(encoding="utf-8")
