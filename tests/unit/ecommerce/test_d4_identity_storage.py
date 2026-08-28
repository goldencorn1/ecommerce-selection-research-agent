from datetime import datetime, timedelta, timezone
import json
import sqlite3
import importlib

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from src.server.ecommerce_store import EcommerceReportStore
from src.server.oidc_auth import decode_oidc_bearer_token
from src.server.tenant_auth import TenantPrincipal


def _oidc_token(private_key, *, issuer="https://issuer.test/", audience="deer-flow"):
    return jwt.encode(
        {
            "sub": "user-d4",
            "tenant_id": "tenant-a",
            "iss": issuer,
            "aud": audience,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
    )


def test_oidc_jwks_requires_strict_claims_and_algorithm_allowlist():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class FakeKey:
        def get_signing_key_from_jwt(self, _token):
            return type("SigningKey", (), {"key": private_key.public_key()})()

    token = _oidc_token(private_key)
    principal = decode_oidc_bearer_token(
        "Bearer " + token,
        jwks_url="https://issuer.test/.well-known/jwks.json",
        issuer="https://issuer.test/",
        audience="deer-flow",
        algorithms=("RS256",),
        jwks_client_factory=lambda _url: FakeKey(),
    )
    assert principal is not None
    assert principal.tenant_id == "tenant-a"
    assert decode_oidc_bearer_token(
        "Bearer " + token,
        jwks_url="https://issuer.test/jwks.json",
        issuer="https://wrong.test/",
        audience="deer-flow",
        algorithms=("RS256",),
        jwks_client_factory=lambda _url: FakeKey(),
    ) is None
    assert decode_oidc_bearer_token(
        "Bearer " + token,
        jwks_url="https://issuer.test/jwks.json",
        issuer="https://issuer.test/",
        audience="deer-flow",
        algorithms=("HS256",),
        jwks_client_factory=lambda _url: FakeKey(),
    ) is None


def test_sqlite_store_migrates_legacy_owner_to_explicit_tenant(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE ecommerce_reports (
                report_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                category TEXT NOT NULL, market TEXT NOT NULL,
                created_at TEXT NOT NULL, average_score REAL NOT NULL,
                recommendation_count INTEGER NOT NULL, candidate_count INTEGER NOT NULL,
                search_status TEXT NOT NULL, model_status TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO ecommerce_reports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("legacy-1", "tenant-legacy", "桌", "CN", "now", 0, 0, 0, "mock", "mock", json.dumps({})),
        )
    store = EcommerceReportStore(database)
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(ecommerce_reports)")}
    assert "tenant_id" in columns
    item = store.get("legacy-1", tenant_id="tenant-legacy")
    assert item is not None
    assert item["history"]["tenant_id"] == "tenant-legacy"


def test_sqlite_store_enforces_explicit_tenant_boundary(tmp_path):
    store = EcommerceReportStore(tmp_path / "reports.sqlite3")
    report_id = store.save(
        {"report": {"request": {"category": "桌面收纳盒"}}},
        tenant_id="tenant-a",
    )
    assert store.get(report_id, tenant_id="tenant-a") is not None
    assert store.get(report_id, tenant_id="tenant-b") is None
    assert store.list(tenant_id="tenant-b") == []


def test_app_selects_oidc_provider_without_hs256_fallback(monkeypatch):
    app_module = importlib.import_module("src.server.app")

    monkeypatch.setenv("ECOMMERCE_REQUIRE_BEARER_AUTH", "true")
    monkeypatch.setenv("ECOMMERCE_BEARER_PROVIDER", "oidc")
    monkeypatch.setattr(
        app_module,
        "decode_oidc_bearer_token",
        lambda _authorization: TenantPrincipal("user-d4", "tenant-a", ()),
    )
    monkeypatch.setattr(
        app_module,
        "decode_bearer_token",
        lambda _authorization: (_ for _ in ()).throw(AssertionError("HS256 fallback")),
    )
    with TestClient(app_module.app) as client:
        response = client.get(
            "/api/ecommerce/history/does-not-exist",
            headers={
                "Authorization": "Bearer oidc-token",
                "X-Workspace-Id": "tenant-a",
            },
        )
    assert response.status_code == 404
