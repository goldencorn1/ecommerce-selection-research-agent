"""Run offline acceptance checks for D4 identity and tenant storage boundaries."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.server.ecommerce_store import EcommerceReportStore  # noqa: E402
from src.server.oidc_auth import decode_oidc_bearer_token  # noqa: E402


REQUIRED_FILES = (
    "docs/D4_IDENTITY_STORAGE_PLAN_2026-08-17.md",
    "docs/HANDOFF_D4_2026-08-17.md",
    "migrations/001_ecommerce_tenant_rls.sql",
    "src/server/oidc_auth.py",
    "src/server/ecommerce_store.py",
)


def _oidc_round_trip() -> bool:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        {
            "sub": "d4-acceptance",
            "tenant_id": "tenant-d4",
            "iss": "https://issuer.d4.test/",
            "aud": "deer-flow-d4",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
    )

    class FakeKey:
        def __init__(self, key):
            self.key = key

        def get_signing_key_from_jwt(self, _token):
            return self

    principal = decode_oidc_bearer_token(
        "Bearer " + token,
        jwks_url="https://issuer.d4.test/jwks.json",
        issuer="https://issuer.d4.test/",
        audience="deer-flow-d4",
        algorithms=("RS256",),
        jwks_client_factory=lambda _url: FakeKey(private_key.public_key()),
    )
    return principal is not None and principal.tenant_id == "tenant-d4"


def validate(root: Path, bundle: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing D4 file: {relative}")

    if not _oidc_round_trip():
        errors.append("OIDC RS256/JWKS acceptance round-trip failed")

    with tempfile.TemporaryDirectory(prefix="d4-tenant-") as directory:
        store = EcommerceReportStore(Path(directory) / "reports.sqlite3")
        report_id = store.save(
            {"report": {"request": {"category": "D4 test"}}},
            tenant_id="tenant-a",
        )
        if store.get(report_id, tenant_id="tenant-b") is not None:
            errors.append("cross-tenant report read was not blocked")
        if store.get(report_id, tenant_id="tenant-a") is None:
            errors.append("same-tenant report read failed")

    sql = (root / "migrations/001_ecommerce_tenant_rls.sql").read_text(encoding="utf-8")
    for marker in ("FORCE ROW LEVEL SECURITY", "current_setting('app.tenant_id'", "WITH CHECK"):
        if marker not in sql:
            errors.append(f"RLS migration missing marker: {marker}")

    manifest = bundle / "manifest.json"
    if not manifest.is_file():
        errors.append(f"missing D4 bundle manifest: {manifest}")
    else:
        try:
            paths = {
                str(item["path"])
                for item in json.loads(manifest.read_text(encoding="utf-8")).get("files", [])
            }
            for relative in (
                "docs/D4_IDENTITY_STORAGE_PLAN_2026-08-17.md",
                "docs/HANDOFF_D4_2026-08-17.md",
                "migrations/001_ecommerce_tenant_rls.sql",
                "scripts/run_d4_acceptance.py",
            ):
                if relative not in paths:
                    errors.append(f"D4 file missing from manifest: {relative}")
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            errors.append("invalid D4 bundle manifest")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--bundle-dir", type=Path, default=Path("artifacts/c5/final_submission"))
    args = parser.parse_args()
    errors = validate(args.root.resolve(), (args.root / args.bundle_dir).resolve())
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(json.dumps({"status": "success", "network_requested": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
