"""Import commercial verification rows from Excel/CSV into typed records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any, Mapping
from xml.etree import ElementTree
from zipfile import ZipFile

from ..models import FinalReport
from .evidence_merge import audit_verification_evidence
from .verification import report_fingerprint
from .verification_models import (
    CommercialVerificationRecord,
    VerificationCompliance,
    VerificationCost,
    VerificationInventory,
    VerificationPrice,
    VerificationSales,
)


@dataclass(frozen=True)
class ExcelImportResult:
    """Auditable result of converting a tabular file to verification records."""

    records: list[CommercialVerificationRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    column_mapping: dict[str, str] = field(default_factory=dict)
    row_count: int = 0
    quality_checks: dict[str, int] = field(default_factory=dict)
    evidence_audit: dict[str, Any] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return not self.errors and bool(self.records) and len(self.records) == self.row_count

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe summary suitable for an import audit report."""

        return {
            "row_count": self.row_count,
            "imported_count": len(self.records),
            "status": "success" if self.complete else "blocked",
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "column_mapping": dict(self.column_mapping),
            "quality_checks": dict(self.quality_checks),
            "evidence_audit": dict(self.evidence_audit),
        }


def preview_import_file(
    path: str | Path,
    *,
    sheet_name: str | int = 0,
    preview_rows: int = 10,
) -> dict[str, Any]:
    """Read headers and a bounded preview without requiring a report."""

    rows, columns = _load_rows(path, sheet_name=sheet_name)
    mapping, missing = resolve_column_mapping(list(columns))
    column_names = [str(column) for column in columns]
    return {
        "status": "ready" if not missing else "needs_columns",
        "sheet": sheet_name,
        "columns": column_names,
        "column_mapping": mapping,
        "mapping_options": {
            canonical: ["", *column_names]
            for canonical in _REQUIRED_FIELDS
        },
        "required_fields": list(_REQUIRED_FIELDS),
        "missing_required_columns": missing,
        "row_count": len(rows),
        "preview_rows": [
            {str(key): value for key, value in row.items()}
            for row in rows[: max(1, min(preview_rows, 50))]
        ],
    }


_ALIASES: dict[str, tuple[str, ...]] = {
    "verification_id": ("verification_id", "核验ID", "核验编号"),
    "run_id": ("run_id", "运行ID", "运行编号"),
    "recommendation_id": ("recommendation_id", "推荐方向", "推荐项", "推荐方向ID"),
    "product_name": ("product_name", "商品名称", "实际商品名称", "SKU名称"),
    "platform": ("platform", "平台", "销售平台"),
    "detail_page_url": ("detail_page_url", "商品链接", "详情页URL", "详情页链接", "链接"),
    "verifier": ("verifier", "核验人", "核验者"),
    "verified_at": ("verified_at", "核验时间", "核验日期"),
    "price_amount": ("price_amount", "售价", "销售价", "商品售价", "price"),
    "price_type": ("price_type", "价格类型"),
    "sales_value": ("sales_value", "销量", "销量值", "近30天销量"),
    "sales_unit": ("sales_unit", "销量单位"),
    "sales_period": ("sales_period", "销量周期", "统计周期"),
    "cost_unit": ("cost_unit", "单位成本", "供应商成本", "采购成本", "成本"),
    "inventory_status": ("inventory_status", "库存状态", "库存"),
    "inventory_quantity": ("inventory_quantity", "库存数量", "可用库存"),
    "compliance_status": ("compliance_status", "合规状态", "合规"),
    "compliance_notes": ("compliance_notes", "合规备注", "合规说明"),
    "conclusion": ("conclusion", "结论", "核验结论"),
    "notes": ("notes", "备注", "核验备注"),
    "evidence_ids": ("evidence_ids", "证据ID", "证据编号", "证据"),
}

_REQUIRED_FIELDS = (
    "recommendation_id",
    "product_name",
    "platform",
    "detail_page_url",
    "verifier",
    "verified_at",
    "price_amount",
    "sales_value",
    "sales_period",
    "cost_unit",
    "inventory_status",
    "compliance_status",
    "conclusion",
    "evidence_ids",
)


def _header_key(value: Any) -> str:
    return re.sub(r"[\s_\-（）()]+", "", str(value).strip().lower())


def resolve_column_mapping(
    columns: list[Any],
    overrides: Mapping[str, str] | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Resolve canonical fields from Chinese or English spreadsheet headers."""

    normalized = {_header_key(column): str(column) for column in columns}
    mapping: dict[str, str] = {}
    missing: list[str] = []
    required = set(_REQUIRED_FIELDS)
    available = {str(column) for column in columns}
    for canonical, selected in (overrides or {}).items():
        if canonical not in _ALIASES:
            continue
        if selected and str(selected) in available:
            mapping[canonical] = str(selected)
    for canonical, aliases in _ALIASES.items():
        alias_keys = {_header_key(alias) for alias in aliases}
        found = next((normalized[key] for key in alias_keys if key in normalized), None)
        if canonical in mapping:
            continue
        if found:
            mapping[canonical] = found
        elif canonical in required:
            missing.append(canonical)
    return mapping, missing


def _cell(row: Mapping[str, Any], mapping: Mapping[str, str], name: str, default: Any = "") -> Any:
    value = row.get(mapping.get(name, ""), default)
    if value is None:
        return default
    try:
        if value != value:  # NaN without importing numpy
            return default
    except Exception:  # noqa: BLE001
        pass
    return value


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _decimal_text(value: Any) -> str:
    return _text(value).replace(",", "").replace("，", "").replace("¥", "").replace("￥", "")


def _int_value(value: Any) -> int:
    text = _decimal_text(value)
    if not text:
        return 0
    return int(float(text))


def _parse_datetime(value: Any) -> tuple[datetime, bool]:
    if isinstance(value, datetime):
        parsed = value
    else:
        import pandas as pd

        parsed = pd.to_datetime(value, errors="raise").to_pydatetime()
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone(timedelta(hours=8))), True
    return parsed, False


def _normalize_choice(value: Any, choices: Mapping[str, str], field_name: str) -> str:
    raw = _text(value).lower()
    if raw in choices:
        return choices[raw]
    raise ValueError(f"{field_name} 不支持的值：{value}")


def _split_evidence_ids(value: Any) -> list[str]:
    return [item.strip() for item in re.split(r"[,，;；\n]", _text(value)) if item.strip()]


def _load_rows(path: str | Path, sheet_name: str | int = 0) -> tuple[list[dict[str, Any]], list[Any]]:
    import pandas as pd

    source = Path(path)
    if source.suffix.lower() in {".csv", ".tsv"}:
        frame = pd.read_csv(source, sep="\t" if source.suffix.lower() == ".tsv" else ",")
    elif source.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        try:
            frame = pd.read_excel(source, sheet_name=sheet_name)
        except ImportError as exc:
            if source.suffix.lower() == ".xls":
                raise ValueError("读取 .xls 需要额外引擎；请先另存为 .xlsx 或 .csv") from exc
            return _read_xlsx_without_openpyxl(source, sheet_name=sheet_name)
    else:
        raise ValueError("仅支持 .xlsx、.xlsm、.xls、.csv 和 .tsv 文件")
    return frame.to_dict(orient="records"), list(frame.columns)


def _read_xlsx_without_openpyxl(
    path: Path,
    *,
    sheet_name: str | int = 0,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Read a simple tabular XLSX with the Python standard library."""

    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_namespace = {"rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    package_rel_namespace = {
        "pr": "http://schemas.openxmlformats.org/package/2006/relationships"
    }
    with ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall("main:si", namespace):
                shared_strings.append(
                    "".join(text.text or "" for text in item.iter("{%s}t" % namespace["main"]))
                )
        workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rels_root = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in rels_root.findall("pr:Relationship", package_rel_namespace)
        }
        sheets = workbook_root.find("main:sheets", namespace)
        if sheets is None:
            raise ValueError("Excel 文件没有工作表")
        sheet_items = list(sheets)
        if isinstance(sheet_name, int):
            if sheet_name < 0 or sheet_name >= len(sheet_items):
                raise ValueError(f"Excel 工作表索引超出范围：{sheet_name}")
            selected = sheet_items[sheet_name]
        else:
            selected = next(
                (item for item in sheet_items if item.attrib.get("name") == sheet_name),
                None,
            )
            if selected is None:
                raise ValueError(f"找不到 Excel 工作表：{sheet_name}")
        relationship_id = selected.attrib.get("{%s}id" % rel_namespace["rel"])
        target = rel_targets.get(relationship_id)
        if not target:
            raise ValueError("Excel 工作表关系缺失")
        worksheet_path = "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
        root = ElementTree.fromstring(archive.read(worksheet_path))
        row_values: list[dict[int, Any]] = []
        for row in root.findall(".//main:sheetData/main:row", namespace):
            values: dict[int, Any] = {}
            for cell in row.findall("main:c", namespace):
                reference = cell.attrib.get("r", "")
                match = re.match(r"([A-Z]+)", reference)
                if not match:
                    continue
                column_index = 0
                for char in match.group(1):
                    column_index = column_index * 26 + ord(char) - ord("A") + 1
                value_node = cell.find("main:v", namespace)
                inline_node = cell.find("main:is/main:t", namespace)
                value = inline_node.text if inline_node is not None else (
                    value_node.text if value_node is not None else ""
                )
                if cell.attrib.get("t") == "s" and value:
                    value = shared_strings[int(value)]
                values[column_index] = value
            row_values.append(values)
    if not row_values:
        return [], []
    headers = [str(row_values[0].get(index, "")).strip() for index in range(1, max(row_values[0]) + 1)]
    records = [
        {
            headers[index - 1]: row.get(index, "")
            for index in range(1, len(headers) + 1)
            if headers[index - 1]
        }
        for row in row_values[1:]
    ]
    return records, headers


def import_verification_rows(
    path: str | Path,
    report: FinalReport | Mapping[str, Any],
    *,
    sheet_name: str | int = 0,
    default_run_id: str = "excel-import",
    column_mapping: Mapping[str, str] | None = None,
) -> ExcelImportResult:
    """Convert spreadsheet rows to records bound to one report fingerprint."""

    report_model = report if isinstance(report, FinalReport) else FinalReport.model_validate(report)
    rows, columns = _load_rows(path, sheet_name=sheet_name)
    mapping, missing = resolve_column_mapping(columns, overrides=column_mapping)
    if missing:
        return ExcelImportResult(
            errors=[f"缺少必需列：{'、'.join(missing)}"],
            column_mapping=mapping,
            row_count=len(rows),
            quality_checks={},
            evidence_audit={},
        )
    recommendation_ids = {item.product_name for item in report_model.recommendations}
    fingerprint = report_fingerprint(report_model)
    records: list[CommercialVerificationRecord] = []
    errors: list[str] = []
    warnings: list[str] = []
    record_rows: list[tuple[int, CommercialVerificationRecord]] = []
    for row_number, row in enumerate(rows, 2):
        try:
            recommendation_id = _text(_cell(row, mapping, "recommendation_id"))
            if recommendation_id not in recommendation_ids:
                raise ValueError(f"推荐方向不属于当前报告：{recommendation_id}")
            verified_at, assumed_timezone = _parse_datetime(_cell(row, mapping, "verified_at"))
            if assumed_timezone:
                warnings.append(f"第 {row_number} 行核验时间无时区，按 Asia/Shanghai 解释")
            record = CommercialVerificationRecord(
                verification_id=_text(_cell(row, mapping, "verification_id")) or f"excel-{row_number:03d}",
                run_id=_text(_cell(row, mapping, "run_id")) or default_run_id,
                report_fingerprint=fingerprint,
                recommendation_id=recommendation_id,
                product_name=_text(_cell(row, mapping, "product_name")),
                platform=_text(_cell(row, mapping, "platform")),
                detail_page_url=_text(_cell(row, mapping, "detail_page_url")),
                verifier=_text(_cell(row, mapping, "verifier")),
                verified_at=verified_at,
                price=VerificationPrice(
                    amount=_decimal_text(_cell(row, mapping, "price_amount")),
                    type=_normalize_choice(
                        _cell(row, mapping, "price_type", "sale_price"),
                        {
                            "sale_price": "sale_price",
                            "售价": "sale_price",
                            "coupon_price": "coupon_price",
                            "list_price": "list_price",
                            "unknown": "unknown",
                        },
                        "price_type",
                    ),
                ),
                sales=VerificationSales(
                    value=_int_value(_cell(row, mapping, "sales_value")),
                    unit=_text(_cell(row, mapping, "sales_unit", "件")) or "件",
                    period=_text(_cell(row, mapping, "sales_period")),
                ),
                cost=VerificationCost(unit_cost=_decimal_text(_cell(row, mapping, "cost_unit"))),
                inventory=VerificationInventory(
                    status=_normalize_choice(
                        _cell(row, mapping, "inventory_status"),
                        {
                            "in_stock": "in_stock",
                            "有货": "in_stock",
                            "在售": "in_stock",
                            "out_of_stock": "out_of_stock",
                            "缺货": "out_of_stock",
                            "unknown": "unknown",
                            "未知": "unknown",
                        },
                        "inventory_status",
                    ),
                    quantity=_int_value(_cell(row, mapping, "inventory_quantity"))
                    if _text(_cell(row, mapping, "inventory_quantity"))
                    else None,
                ),
                compliance=VerificationCompliance(
                    status=_normalize_choice(
                        _cell(row, mapping, "compliance_status"),
                        {
                            "passed": "passed",
                            "通过": "passed",
                            "pending": "pending",
                            "待核验": "pending",
                            "failed": "failed",
                            "不通过": "failed",
                            "not_applicable": "not_applicable",
                            "不适用": "not_applicable",
                        },
                        "compliance_status",
                    ),
                    notes=_text(_cell(row, mapping, "compliance_notes")),
                ),
                conclusion=_normalize_choice(
                    _cell(row, mapping, "conclusion"),
                    {
                        "pass": "pass",
                        "通过": "pass",
                        "conditional": "conditional",
                        "条件通过": "conditional",
                        "reject": "reject",
                        "拒绝": "reject",
                    },
                    "conclusion",
                ),
                notes=_text(_cell(row, mapping, "notes")),
                evidence_ids=_split_evidence_ids(_cell(row, mapping, "evidence_ids")),
            )
            records.append(record)
            record_rows.append((row_number, record))
        except Exception as exc:  # noqa: BLE001 - report row context to the user
            errors.append(f"第 {row_number} 行导入失败：{exc}")
    quality_checks = {
        "duplicate_product_rows": 0,
        "zero_price_rows": 0,
        "cost_not_below_price_rows": 0,
        "placeholder_url_rows": 0,
    }
    seen_products: dict[tuple[str, str, str], int] = {}
    for row_number, record in record_rows:
        product_key = (record.platform, record.product_name, record.detail_page_url)
        if product_key in seen_products:
            quality_checks["duplicate_product_rows"] += 1
            warnings.append(
                f"第 {row_number} 行与第 {seen_products[product_key]} 行商品、平台和链接完全重复"
            )
        else:
            seen_products[product_key] = row_number
        if record.price.amount == 0:
            quality_checks["zero_price_rows"] += 1
            warnings.append(f"第 {row_number} 行售价为 0，请确认是否为真实价格")
        if record.cost.unit_cost >= record.price.amount and record.price.amount > 0:
            quality_checks["cost_not_below_price_rows"] += 1
            warnings.append(f"第 {row_number} 行单位成本不低于售价，请核对币种、规格或成本口径")
        if ".invalid/" in record.detail_page_url:
            quality_checks["placeholder_url_rows"] += 1
            warnings.append(f"第 {row_number} 行仍使用占位商品链接")
    evidence_audit = audit_verification_evidence(report_model, records).as_dict()
    return ExcelImportResult(
        records=records,
        errors=errors,
        warnings=warnings,
        column_mapping=mapping,
        row_count=len(rows),
        quality_checks=quality_checks,
        evidence_audit=evidence_audit,
    )


def write_excel_import_report(
    path: str | Path,
    result: ExcelImportResult,
    *,
    input_file: str | Path,
    output_file: str | Path,
) -> None:
    """Write a compact JSON audit report for successful or blocked imports."""

    import json

    payload = {
        "input_file": str(input_file),
        "output_file": str(output_file),
        **result.as_dict(),
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
