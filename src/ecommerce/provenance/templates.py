"""Generate editable commercial-verification JSONL templates."""

from __future__ import annotations

from datetime import datetime, timezone
import csv
from pathlib import Path
from typing import Any, Mapping

from .verification import report_fingerprint, write_verification_records
from .verification_models import (
    CommercialVerificationRecord,
    VerificationCompliance,
    VerificationCost,
    VerificationInventory,
    VerificationPrice,
    VerificationSales,
)
from ..models import FinalReport


TEMPLATE_VARIANTS = ("轻量便携版", "静音升级版", "礼赠套装版")
VERIFICATION_CSV_HEADERS = (
    "核验ID",
    "运行ID",
    "推荐方向",
    "商品名称",
    "平台",
    "商品链接",
    "核验人",
    "核验时间",
    "售价",
    "价格类型",
    "销量",
    "销量单位",
    "销量周期",
    "供应商成本",
    "库存状态",
    "库存数量",
    "合规状态",
    "合规备注",
    "结论",
    "备注",
    "证据ID",
)


def build_verification_template(
    category: str,
    *,
    run_id: str = "REPLACE_WITH_RUN_ID",
) -> list[CommercialVerificationRecord]:
    """Build safe, conditional placeholders that never satisfy the gate by default."""

    normalized_category = category.strip()
    if not normalized_category:
        raise ValueError("category must not be empty")
    verified_at = datetime.now(timezone.utc)
    records: list[CommercialVerificationRecord] = []
    for index, variant in enumerate(TEMPLATE_VARIANTS, 1):
        records.append(
            CommercialVerificationRecord(
                verification_id=f"REPLACE_WITH_VERIFICATION_ID_{index}",
                run_id=run_id,
                recommendation_id=f"REPLACE_WITH_RECOMMENDATION_ID_{index}",
                product_name=f"{normalized_category}{variant}",
                platform="REPLACE_WITH_PLATFORM",
                detail_page_url="https://example.invalid/replace-with-detail-page",
                verifier="REPLACE_WITH_VERIFIER",
                verified_at=verified_at,
                price=VerificationPrice(amount=0),
                sales=VerificationSales(value=0, unit="件", period="REPLACE_WITH_PERIOD"),
                cost=VerificationCost(unit_cost=0),
                inventory=VerificationInventory(status="unknown"),
                compliance=VerificationCompliance(status="pending", notes="请补充 SKU 级合规材料"),
                conclusion="conditional",
                notes="模板占位记录：请替换所有 REPLACE_WITH 字段，并确认真实商品详情、销量、成本、库存和合规信息。",
                evidence_ids=[f"manual-template-{index}"],
            )
        )
    return records


def write_verification_template(
    path: str | Path,
    category: str,
    *,
    run_id: str = "REPLACE_WITH_RUN_ID",
) -> int:
    """Write an editable UTF-8 JSONL template and return its record count."""

    return write_verification_records(path, build_verification_template(category, run_id=run_id))


def build_verification_template_from_report(
    report: FinalReport | Mapping[str, Any],
    *,
    run_id: str = "REPLACE_WITH_RUN_ID",
) -> list[CommercialVerificationRecord]:
    """Build placeholders using the report's exact recommendation identifiers."""

    report_model = report if isinstance(report, FinalReport) else FinalReport.model_validate(report)
    if not report_model.recommendations:
        raise ValueError("report must contain at least one recommendation")
    verified_at = datetime.now(timezone.utc)
    fingerprint = report_fingerprint(report_model)
    records: list[CommercialVerificationRecord] = []
    for index, recommendation in enumerate(report_model.recommendations, 1):
        records.append(
            CommercialVerificationRecord(
                verification_id=f"REPLACE_WITH_VERIFICATION_ID_{index}",
                run_id=run_id,
                report_fingerprint=fingerprint,
                recommendation_id=recommendation.product_name,
                product_name="REPLACE_WITH_REAL_PRODUCT_NAME",
                platform="REPLACE_WITH_PLATFORM",
                detail_page_url="https://example.invalid/replace-with-detail-page",
                verifier="REPLACE_WITH_VERIFIER",
                verified_at=verified_at,
                price=VerificationPrice(amount=0),
                sales=VerificationSales(value=0, unit="件", period="REPLACE_WITH_PERIOD"),
                cost=VerificationCost(unit_cost=0),
                inventory=VerificationInventory(status="unknown"),
                compliance=VerificationCompliance(status="pending", notes="请补充 SKU 级合规材料"),
                conclusion="conditional",
                notes=(
                    f"已绑定报告推荐项：{recommendation.product_name}。请替换所有 REPLACE_WITH_* 字段，"
                    "并确认真实商品详情、销量、成本、库存和合规信息。"
                ),
                evidence_ids=[f"manual-template-{index}"],
            )
        )
    return records


def write_verification_template_from_report(
    path: str | Path,
    report: FinalReport | Mapping[str, Any],
    *,
    run_id: str = "REPLACE_WITH_RUN_ID",
) -> int:
    """Write a report-bound UTF-8 JSONL template."""

    return write_verification_records(
        path,
        build_verification_template_from_report(report, run_id=run_id),
    )


def write_verification_csv_template_from_report(
    path: str | Path,
    report: FinalReport | Mapping[str, Any],
    *,
    run_id: str = "REPLACE_WITH_RUN_ID",
) -> int:
    """Write a UTF-8 CSV template that can be opened directly in Excel."""

    report_model = report if isinstance(report, FinalReport) else FinalReport.model_validate(report)
    if not report_model.recommendations:
        raise ValueError("report must contain at least one recommendation")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=VERIFICATION_CSV_HEADERS)
        writer.writeheader()
        for index, recommendation in enumerate(report_model.recommendations, 1):
            writer.writerow(
                {
                    "核验ID": f"REPLACE_WITH_VERIFICATION_ID_{index}",
                    "运行ID": run_id,
                    "推荐方向": recommendation.product_name,
                    "商品名称": f"REPLACE_WITH_REAL_PRODUCT_NAME_{index}",
                    "平台": f"REPLACE_WITH_PLATFORM_{index}",
                    "商品链接": f"https://example.invalid/replace-with-detail-page-{index}",
                    "核验人": f"REPLACE_WITH_VERIFIER_{index}",
                    "核验时间": datetime.now(timezone.utc).isoformat(),
                    "售价": "0",
                    "价格类型": "unknown",
                    "销量": "0",
                    "销量单位": "件",
                    "销量周期": "REPLACE_WITH_PERIOD",
                    "供应商成本": "0",
                    "库存状态": "unknown",
                    "库存数量": "",
                    "合规状态": "pending",
                    "合规备注": "请补充 SKU 级合规材料",
                    "结论": "conditional",
                    "备注": "请替换所有 REPLACE_WITH_* 字段，并确认真实商品、销量、成本、库存和合规信息。",
                    "证据ID": f"manual-template-{index}",
                }
            )
    return len(report_model.recommendations)


def build_unverified_verification_records(
    report: FinalReport | Mapping[str, Any],
    *,
    run_id: str = "auto-unverified",
) -> list[CommercialVerificationRecord]:
    """Build explicit unknown records without inventing commercial facts."""

    report_model = report if isinstance(report, FinalReport) else FinalReport.model_validate(report)
    fingerprint = report_fingerprint(report_model)
    verified_at = datetime.now(timezone.utc)
    records: list[CommercialVerificationRecord] = []
    for index, recommendation in enumerate(report_model.recommendations, 1):
        records.append(
            CommercialVerificationRecord(
                verification_id=f"{run_id}-{index:03d}",
                run_id=run_id,
                report_fingerprint=fingerprint,
                recommendation_id=recommendation.product_name,
                product_name="待人工确认",
                platform="未核验",
                detail_page_url=f"https://example.invalid/not-verified-{index:03d}",
                verifier="system-unverified",
                verified_at=verified_at,
                price=VerificationPrice(amount=0, type="unknown"),
                sales=VerificationSales(value=0, unit="件", period="未核验"),
                cost=VerificationCost(unit_cost=0),
                inventory=VerificationInventory(status="unknown"),
                compliance=VerificationCompliance(
                    status="pending",
                    notes="尚未取得真实商品、供应链和 SKU 合规资料",
                ),
                conclusion="conditional",
                notes="系统自动生成的未核验记录，不代表真实商品事实，不得用于进货决策。",
                evidence_ids=[f"manual-unverified-{index:03d}"],
            )
        )
    return records


def write_unverified_verification_records(
    path: str | Path,
    report: FinalReport | Mapping[str, Any],
    *,
    run_id: str = "auto-unverified",
) -> int:
    """Write a safe, explicitly blocked draft for every report recommendation."""

    return write_verification_records(
        path,
        build_unverified_verification_records(report, run_id=run_id),
    )
