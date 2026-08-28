"""JSONL persistence and validation for human commercial verification records."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .verification_models import CommercialVerificationRecord, VerificationValidation
from ..models import FinalReport


def report_fingerprint(report: FinalReport | Mapping[str, Any]) -> str:
    """Return a stable SHA-256 fingerprint for the canonical report payload."""

    report_model = report if isinstance(report, FinalReport) else FinalReport.model_validate(report)
    canonical = json.dumps(
        report_model.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_verification_records(
    path: str | Path,
    records: Iterable[CommercialVerificationRecord],
) -> int:
    """Write UTF-8 JSONL records and return the number of records written."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = list(records)
    payload = "".join(f"{record.model_dump_json()}\n" for record in normalized)
    target.write_text(payload, encoding="utf-8")
    return len(normalized)


def read_verification_records(path: str | Path) -> list[CommercialVerificationRecord]:
    """Read UTF-8 JSONL, with a convenience fallback for one JSON document."""

    from pydantic import TypeAdapter

    raw_text = Path(path).read_text(encoding="utf-8-sig")
    adapter = TypeAdapter(CommercialVerificationRecord)
    records: list[CommercialVerificationRecord] = []
    lines = raw_text.splitlines()
    try:
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            records.append(adapter.validate_json(line))
        return records
    except Exception as line_error:  # noqa: BLE001 - retry as one JSON document
        import json

        try:
            document = json.loads(raw_text)
        except json.JSONDecodeError:
            raise ValueError(f"invalid verification JSONL at line {line_number}") from line_error
        if isinstance(document, dict):
            document = [document]
        if not isinstance(document, list):
            raise ValueError("verification file must contain JSONL records or a JSON object/array") from line_error
        try:
            return [adapter.validate_python(item) for item in document]
        except Exception as document_error:  # noqa: BLE001 - preserve validation context
            raise ValueError("invalid verification JSON object/array") from document_error


def validate_verification_records(
    report: FinalReport,
    records: Sequence[CommercialVerificationRecord],
    *,
    now: datetime | None = None,
    max_age_days: int = 30,
    valid_evidence_ids: set[str] | None = None,
    citation_complete: bool = True,
    expected_report_fingerprint: str | None = None,
) -> VerificationValidation:
    """Check whether every recommendation has a fresh, passing audit record."""

    if max_age_days < 0:
        raise ValueError("max_age_days must be non-negative")
    current = now or datetime.now(timezone.utc)
    recommendation_ids = {item.product_name for item in report.recommendations}
    covered = {record.recommendation_id for record in records if record.recommendation_id in recommendation_ids}
    missing = sorted(recommendation_ids - covered)
    reasons: list[str] = []
    if not report.recommendations:
        reasons.append("报告没有推荐方向")
    if not citation_complete:
        reasons.append("报告引用完整性检查未通过")
    if missing:
        reasons.append(f"缺少推荐方向核验记录：{'、'.join(missing)}")
    cutoff = current - timedelta(days=max_age_days)
    for record in records:
        if record.recommendation_id not in recommendation_ids:
            reasons.append(f"核验记录关联未知推荐方向：{record.recommendation_id}")
        if record.verified_at > current:
            reasons.append(f"核验时间在未来：{record.verification_id}")
        elif record.verified_at < cutoff:
            reasons.append(f"核验记录已过期：{record.verification_id}")
        if record.conclusion != "pass":
            reasons.append(f"核验结论不是 pass：{record.verification_id}")
        if expected_report_fingerprint is not None:
            if record.report_fingerprint is None:
                reasons.append(f"核验记录缺少报告指纹：{record.verification_id}")
            elif record.report_fingerprint != expected_report_fingerprint:
                reasons.append(f"核验记录报告指纹不匹配：{record.verification_id}")
        if record.compliance.status in {"failed", "pending"}:
            reasons.append(f"合规状态未通过：{record.verification_id}")
        if valid_evidence_ids is not None:
            invalid_ids = [
                evidence_id
                for evidence_id in record.evidence_ids
                if evidence_id not in valid_evidence_ids and not evidence_id.startswith("manual-")
            ]
            if invalid_ids:
                reasons.append(f"核验记录引用不存在的证据：{record.verification_id}")
    complete = bool(recommendation_ids) and not missing and not reasons
    return VerificationValidation(
        complete=complete,
        records_count=len(records),
        covered_recommendations=len(covered),
        missing_recommendations=missing,
        blocking_reasons=list(dict.fromkeys(reasons)),
    )


def run_verification_preflight(
    report_path: str | Path,
    verification_path: str | Path,
    *,
    max_age_days: int = 30,
) -> dict[str, Any]:
    """Validate saved report and JSONL before an expensive research run."""

    import json

    try:
        saved_payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
        report_payload = saved_payload.get("report", saved_payload)
        report = FinalReport.model_validate(report_payload)
        records = read_verification_records(verification_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "status": "error",
            "error_code": "verification_input_error",
            "message": str(exc),
            "report_path": str(report_path),
            "verification_path": str(verification_path),
        }

    valid_evidence_ids = {evidence.evidence_id for evidence in report.evidence}
    expected_fingerprint = report_fingerprint(report)
    placeholder_record_ids = [
        record.verification_id
        for record in records
        if "REPLACE_WITH_" in record.model_dump_json()
    ]
    citation_complete = bool(
        saved_payload.get("ecommerce_citation_validation", {}).get("complete", True)
    )
    validation = validate_verification_records(
        report,
        records,
        max_age_days=max_age_days,
        valid_evidence_ids=valid_evidence_ids,
        citation_complete=citation_complete,
        expected_report_fingerprint=expected_fingerprint,
    )
    return {
        "status": "pass" if validation.complete else "blocked",
        "report_path": str(report_path),
        "verification_path": str(verification_path),
        "recommendation_count": len(report.recommendations),
        "record_count": len(records),
        "report_fingerprint": expected_fingerprint,
        "citation_complete": citation_complete,
        "placeholder_record_ids": placeholder_record_ids,
        "placeholder_record_count": len(placeholder_record_ids),
        "validation": validation.model_dump(mode="json"),
        "next_step": (
            "可以将该 JSONL 作为 --ecommerce-verification-file 输入，但仍需满足证据质量门禁。"
            if validation.complete
            else "请按 blocking_reasons 修正核验记录后再运行正式研究。"
        ),
    }
