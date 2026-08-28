"""Audit links between saved search evidence and commercial verification rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from ..models import FinalReport
from ..search.models import normalize_search_url
from .verification_models import CommercialVerificationRecord


@dataclass(frozen=True)
class EvidenceMergeAudit:
    """Non-blocking audit result for evidence-to-record associations."""

    status: str
    records_count: int
    linked_record_count: int
    manual_only_record_count: int
    unlinked_evidence_count: int
    url_conflict_count: int
    missing_recommendations: list[str] = field(default_factory=list)
    links: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "records_count": self.records_count,
            "linked_record_count": self.linked_record_count,
            "manual_only_record_count": self.manual_only_record_count,
            "unlinked_evidence_count": self.unlinked_evidence_count,
            "url_conflict_count": self.url_conflict_count,
            "missing_recommendations": list(self.missing_recommendations),
            "links": list(self.links),
            "issues": list(self.issues),
        }


def audit_verification_evidence(
    report: FinalReport,
    records: Sequence[CommercialVerificationRecord],
) -> EvidenceMergeAudit:
    """Compare record evidence IDs and URLs with the saved report evidence.

    ``manual-*`` IDs remain explicitly classified as manual-only. They are not
    treated as search evidence and therefore cannot silently inflate source
    coverage.
    """

    evidence_by_id = {item.evidence_id: item for item in report.evidence}
    report_recommendations = {item.product_name for item in report.recommendations}
    covered_recommendations = {
        record.recommendation_id
        for record in records
        if record.recommendation_id in report_recommendations
    }
    links: list[dict[str, Any]] = []
    issues: list[str] = []
    linked_record_count = 0
    manual_only_record_count = 0
    unlinked_evidence_count = 0
    url_conflict_count = 0

    for record in records:
        record_links: list[dict[str, Any]] = []
        record_has_saved_evidence = False
        record_has_manual_evidence = False
        for evidence_id in record.evidence_ids:
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                if evidence_id.startswith("manual-"):
                    record_has_manual_evidence = True
                    record_links.append(
                        {
                            "verification_id": record.verification_id,
                            "evidence_id": evidence_id,
                            "link_type": "manual_only",
                            "url_match": None,
                        }
                    )
                    continue
                unlinked_evidence_count += 1
                issue = f"核验记录 {record.verification_id} 引用了不存在的证据 {evidence_id}"
                issues.append(issue)
                record_links.append(
                    {
                        "verification_id": record.verification_id,
                        "evidence_id": evidence_id,
                        "link_type": "unlinked",
                        "url_match": False,
                    }
                )
                continue

            record_has_saved_evidence = True
            url_match = normalize_search_url(record.detail_page_url) == normalize_search_url(
                evidence.source
            )
            if not url_match:
                url_conflict_count += 1
                issues.append(
                    f"核验记录 {record.verification_id} 的详情页 URL 与证据 {evidence_id} 来源不一致"
                )
            record_links.append(
                {
                    "verification_id": record.verification_id,
                    "evidence_id": evidence_id,
                    "link_type": "report_evidence",
                    "evidence_source": evidence.source,
                    "url_match": url_match,
                }
            )
        links.extend(record_links)
        if record_has_saved_evidence:
            linked_record_count += 1
        elif record_has_manual_evidence:
            manual_only_record_count += 1

    missing_recommendations = sorted(report_recommendations - covered_recommendations)
    if missing_recommendations:
        issues.append(f"缺少推荐方向商业记录：{'、'.join(missing_recommendations)}")
    if missing_recommendations or unlinked_evidence_count or url_conflict_count:
        status = "blocked"
    elif manual_only_record_count:
        status = "review"
    else:
        status = "pass"
    return EvidenceMergeAudit(
        status=status,
        records_count=len(records),
        linked_record_count=linked_record_count,
        manual_only_record_count=manual_only_record_count,
        unlinked_evidence_count=unlinked_evidence_count,
        url_conflict_count=url_conflict_count,
        missing_recommendations=missing_recommendations,
        links=links,
        issues=list(dict.fromkeys(issues)),
    )
