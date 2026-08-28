"""Conversions and local citation checks; no network access is performed."""

from __future__ import annotations

from collections.abc import Iterable

from src.ecommerce.models import Evidence, FinalReport
from src.ecommerce.search import SearchResult

from .models import EvidenceProvenance, ProvenanceValidation


def search_result_to_provenance(
    result: SearchResult,
    *,
    evidence_id: str,
    authorization_note: str = "需确认搜索 API 授权、版权、robots 与服务条款",
) -> EvidenceProvenance:
    return EvidenceProvenance(
        evidence_id=evidence_id,
        source=result.url,
        title=result.title,
        retrieved_at=result.retrieved_at,
        retrieval_score=result.score,
        source_type=result.source,
        authorization_note=authorization_note,
    )


def evidence_to_provenance(
    evidence: Evidence,
    *,
    retrieved_at,
    source_type: str = "evidence",
    authorization_note: str = "来源授权状态待核验",
) -> EvidenceProvenance:
    return EvidenceProvenance(
        evidence_id=evidence.evidence_id,
        source=evidence.source,
        title=evidence.title,
        retrieved_at=evidence.retrieved_at or retrieved_at,
        retrieval_score=evidence.confidence,
        source_type=(
            evidence.source_type if evidence.source_type != "unknown" else source_type
        ),
        authorization_note=authorization_note,
    )


def citation_completeness(
    report: FinalReport,
    provenance: Iterable[EvidenceProvenance],
) -> ProvenanceValidation:
    provenance_by_id = {item.evidence_id: item for item in provenance}
    cited_ids = {
        evidence_id
        for recommendation in report.recommendations
        for evidence_id in recommendation.evidence_ids
    }
    missing = sorted(cited_ids - provenance_by_id.keys())
    invalid = sorted(
        evidence_id
        for evidence_id, item in provenance_by_id.items()
        if not item.source.startswith(("http://", "https://", "mock://", "local://"))
    )
    return ProvenanceValidation(
        complete=not missing and not invalid,
        cited_evidence_count=len(cited_ids),
        mapped_source_count=len(cited_ids & provenance_by_id.keys()),
        missing_evidence_ids=missing,
        invalid_provenance_ids=invalid,
    )
