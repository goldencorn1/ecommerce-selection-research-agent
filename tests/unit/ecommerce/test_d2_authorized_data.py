from datetime import datetime, timedelta, timezone

from src.ecommerce.authorized_data import (
    AuthorizedDataSource,
    AuthorizedProductRecord,
    validate_authorized_dataset,
)


def _source(status: str = "verified") -> AuthorizedDataSource:
    return AuthorizedDataSource(
        source_id="owned-catalog",
        provider="示例授权平台",
        source_kind="marketplace_api",
        authorization_status=status,
        authorization_reference="contract-2026-demo",
        terms_url="https://example.test/terms",
        allowed_use="内部选品研究和人工复核",
        owner_id="workspace-a",
    )


def _record(*, source_id: str = "owned-catalog", age_hours: int = 1) -> AuthorizedProductRecord:
    return AuthorizedProductRecord(
        record_id="sku-001",
        source_id=source_id,
        sku_id="sku-001",
        title="授权商品",
        product_url="https://example.test/product/1",
        price=199,
        retrieved_at=datetime.now(timezone.utc) - timedelta(hours=age_hours),
    )


def test_verified_records_are_ready_for_verification_but_not_commercial_ready():
    result = validate_authorized_dataset(_source(), [_record()])
    assert result["status"] == "ready_for_verification"
    assert result["commercial_decision_ready"] is False
    assert result["priced_record_count"] == 1


def test_unverified_source_is_blocked_and_stale_records_are_reported():
    result = validate_authorized_dataset(
        _source("user_declared"), [_record(age_hours=100)], max_age_hours=72
    )
    assert result["status"] == "blocked"
    assert result["stale_record_count"] == 1
    assert any("verified" in message for message in result["errors"])


def test_mismatched_source_is_blocked():
    result = validate_authorized_dataset(_source(), [_record(source_id="other")])
    assert result["status"] == "blocked"
    assert any("source_id" in message for message in result["errors"])
