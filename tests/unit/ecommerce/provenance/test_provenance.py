from datetime import datetime, timezone

import pytest

from src.ecommerce.models import EcommerceResearchRequest, Evidence, FinalReport, ProductRecommendation, ProductScore
from src.ecommerce.provenance import (
    CommercialVerificationRecord,
    EvidenceProvenance,
    VerificationCompliance,
    VerificationCost,
    VerificationInventory,
    VerificationPrice,
    VerificationSales,
    audit_verification_evidence,
    build_candidate_catalog,
    citation_completeness,
    evidence_to_provenance,
)


def _report(ids):
    score = ProductScore(demand=1, competition=1, margin=1, differentiation=1, evidence_quality=1, total=1)
    return FinalReport(
        request=EcommerceResearchRequest(),
        executive_summary="summary",
        recommendations=[ProductRecommendation(product_name="p", positioning="x", target_customer="u", price_range="1", rationale="r", score=score, evidence_ids=ids)],
    )


def test_citation_completeness_maps_all_citations():
    evidence = Evidence(evidence_id="e1", source="https://example.test/e1", title="t", summary="s", confidence=.8)
    provenance = [evidence_to_provenance(evidence, retrieved_at=datetime.now(timezone.utc))]
    result = citation_completeness(_report(["e1"]), provenance)
    assert result.complete is True
    assert result.mapped_source_count == 1


def test_citation_completeness_reports_missing_id():
    result = citation_completeness(_report(["missing"]), [])
    assert result.complete is False
    assert result.missing_evidence_ids == ["missing"]


def test_provenance_validates_url_and_score():
    with pytest.raises(ValueError):
        EvidenceProvenance(evidence_id="e", source="not-url", title="t", retrieved_at=datetime.now(timezone.utc), retrieval_score=.5)
    with pytest.raises(ValueError):
        EvidenceProvenance(evidence_id="e", source="https://example.test", title="t", retrieved_at=datetime.now(timezone.utc), retrieval_score=2)


def test_audit_verification_evidence_matches_saved_source_url():
    evidence = Evidence(
        evidence_id="e1",
        source="https://example.test/product?utm_source=search",
        title="product",
        summary="summary",
        confidence=0.8,
    )
    report = _report(["e1"]).model_copy(update={"evidence": [evidence]})
    record = CommercialVerificationRecord(
        verification_id="v1",
        run_id="run-1",
        recommendation_id="p",
        product_name="real product",
        platform="淘宝",
        detail_page_url="https://example.test/product",
        verifier="tester",
        verified_at=datetime.now(timezone.utc),
        price=VerificationPrice(amount="129"),
        sales=VerificationSales(value=1, unit="件", period="近30天"),
        cost=VerificationCost(unit_cost="58"),
        inventory=VerificationInventory(status="in_stock"),
        compliance=VerificationCompliance(status="passed"),
        conclusion="pass",
        evidence_ids=["e1"],
    )

    result = audit_verification_evidence(report, [record])

    assert result.status == "pass"
    assert result.linked_record_count == 1
    assert result.url_conflict_count == 0
    assert result.links[0]["url_match"] is True


def test_audit_verification_evidence_separates_manual_and_conflicting_links():
    evidence = Evidence(
        evidence_id="e1",
        source="https://example.test/search-result",
        title="product",
        summary="summary",
        confidence=0.8,
    )
    report = _report(["e1"]).model_copy(update={"evidence": [evidence]})
    record = CommercialVerificationRecord(
        verification_id="v2",
        run_id="run-1",
        recommendation_id="p",
        product_name="real product",
        platform="淘宝",
        detail_page_url="https://example.test/detail",
        verifier="tester",
        verified_at=datetime.now(timezone.utc),
        price=VerificationPrice(amount="129"),
        sales=VerificationSales(value=1, unit="件", period="近30天"),
        cost=VerificationCost(unit_cost="58"),
        inventory=VerificationInventory(status="in_stock"),
        compliance=VerificationCompliance(status="passed"),
        conclusion="pass",
        evidence_ids=["manual-product-page", "e1"],
    )

    result = audit_verification_evidence(report, [record])

    assert result.status == "blocked"
    assert result.manual_only_record_count == 0
    assert result.url_conflict_count == 1
    assert any("URL" in issue for issue in result.issues)


def test_audit_verification_evidence_blocks_missing_records():
    result = audit_verification_evidence(_report([]), [])

    assert result.status == "blocked"
    assert result.missing_recommendations == ["p"]


def test_candidate_catalog_is_explicitly_non_commercial():
    evidence = Evidence(
        evidence_id="e1",
        source="https://example.test/product?utm_source=search",
        title="candidate",
        summary="summary",
        confidence=0.8,
        supports=["search:competitor"],
    )
    report = _report(["e1"]).model_copy(update={"evidence": [evidence]})

    catalog = build_candidate_catalog(report)

    assert catalog["status"] == "candidate_only"
    assert catalog["candidate_count"] == 1
    assert catalog["candidates"][0]["modules"] == ["competitor"]
    assert catalog["candidates"][0]["canonical_url"] == "https://example.test/product"
    assert catalog["candidates"][0]["source_quality_category"] == "other_domain"
    assert catalog["candidates"][0]["candidate_rank_score"] > 0
    assert "销量" in "".join(catalog["warnings"])
