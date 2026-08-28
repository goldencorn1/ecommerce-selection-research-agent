from datetime import datetime, timezone
import json

from src.ecommerce.authorized_data import (
    AuthorizedDataSource,
    AuthorizedProductRecord,
    validate_authorized_dataset,
)
from src.server.integration_preflight import build_d5_preflight_plan


def test_d5_default_preflight_is_blocked_without_external_configuration(monkeypatch):
    for name in (
        "ECOMMERCE_REQUIRE_BEARER_AUTH",
        "ECOMMERCE_BEARER_PROVIDER",
        "ECOMMERCE_OIDC_ISSUER",
        "ECOMMERCE_OIDC_AUDIENCE",
        "ECOMMERCE_OIDC_JWKS_URL",
        "ECOMMERCE_POSTGRES_DSN",
        "DATABASE_URL",
        "ECOMMERCE_AUTHORIZED_DATA_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    plan = build_d5_preflight_plan()
    assert plan["network_requested"] is False
    assert plan["status"] == "blocked"
    assert plan["commercial_decision_ready"] is False
    assert "postgresql://" not in json.dumps(plan)


def test_d5_verified_authorized_data_stays_before_commercial_gate():
    source = AuthorizedDataSource(
        source_id="source-d5",
        provider="user-owned",
        source_kind="owned_file",
        authorization_status="verified",
        authorization_reference="ticket-d5",
        allowed_use="verification",
        owner_id="tenant-d5",
    )
    record = AuthorizedProductRecord(
        record_id="record-d5",
        source_id="source-d5",
        title="Authorized product",
        price=12.5,
        retrieved_at=datetime.now(timezone.utc),
    )
    result = validate_authorized_dataset(source, [record])
    assert result["status"] == "ready_for_verification"
    assert result["commercial_decision_ready"] is False
