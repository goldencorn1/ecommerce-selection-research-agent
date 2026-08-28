"""Run D5 offline integration acceptance without contacting external services."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ecommerce.authorized_data import (  # noqa: E402
    AuthorizedDataSource,
    AuthorizedProductRecord,
    validate_authorized_dataset,
)
from src.server.integration_preflight import build_d5_preflight_plan  # noqa: E402


REQUIRED_FILES = (
    "docs/D5_REAL_ENVIRONMENT_INTEGRATION_PLAN_2026-08-17.md",
    "docs/HANDOFF_D5_2026-08-17.md",
    "scripts/run_d5_integration_preflight.py",
    "src/server/integration_preflight.py",
    "migrations/001_ecommerce_tenant_rls.sql",
)


def validate(root: Path, bundle: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing D5 file: {relative}")

    plan = build_d5_preflight_plan()
    if plan["network_requested"] is not False:
        errors.append("D5 default preflight must not request network")
    if plan["commercial_decision_ready"] is not False:
        errors.append("D5 preflight must not open commercial decision gate")
    serialized = json.dumps(plan, ensure_ascii=False)
    if any(marker in serialized for marker in ("api_key", "password", "secret", "postgresql://")):
        errors.append("D5 preflight exposes a secret-like field")

    source = AuthorizedDataSource(
        source_id="d5-fixture",
        provider="user-owned-fixture",
        source_kind="owned_file",
        authorization_status="verified",
        authorization_reference="fixture-authorized",
        allowed_use="offline acceptance only",
        owner_id="tenant-d5",
    )
    record = AuthorizedProductRecord(
        record_id="d5-record-1",
        source_id="d5-fixture",
        title="D5 fixture product",
        price=99.0,
        retrieved_at=datetime.now(timezone.utc),
    )
    report = validate_authorized_dataset(source, [record])
    if report["status"] != "ready_for_verification" or report["commercial_decision_ready"]:
        errors.append("authorized data fixture boundary is invalid")

    sql = (root / "migrations/001_ecommerce_tenant_rls.sql").read_text(encoding="utf-8")
    for marker in ("ENABLE ROW LEVEL SECURITY", "FORCE ROW LEVEL SECURITY", "current_setting('app.tenant_id'"):
        if marker not in sql:
            errors.append(f"D5 RLS migration missing marker: {marker}")

    manifest = bundle / "manifest.json"
    if not manifest.is_file():
        errors.append(f"missing D5 bundle manifest: {manifest}")
    else:
        try:
            paths = {
                str(item["path"])
                for item in json.loads(manifest.read_text(encoding="utf-8")).get("files", [])
            }
            for relative in (
                "docs/D5_REAL_ENVIRONMENT_INTEGRATION_PLAN_2026-08-17.md",
                "docs/HANDOFF_D5_2026-08-17.md",
                "scripts/run_d5_acceptance.py",
                "scripts/run_d5_integration_preflight.py",
            ):
                if relative not in paths:
                    errors.append(f"D5 file missing from manifest: {relative}")
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            errors.append("invalid D5 bundle manifest")
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
