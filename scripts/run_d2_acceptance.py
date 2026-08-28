"""Run offline acceptance checks for the D2 data and multi-user boundary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ecommerce.authorized_data import (  # noqa: E402
    AuthorizedDataSource,
    AuthorizedProductRecord,
    validate_authorized_dataset,
)
from src.server.workspace_security import issue_workspace_token, verify_workspace_token  # noqa: E402
from scripts.run_d2_live_evaluation import build_evaluation_plan  # noqa: E402


REQUIRED_FILES = (
    "docs/D2_AUTHORIZED_DATA_AND_MULTIUSER_PLAN_2026-08-17.md",
    "scripts/run_d2_live_evaluation.py",
    "src/ecommerce/authorized_data.py",
    "src/server/workspace_security.py",
)


def validate(root: Path, bundle: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing D2 file: {relative}")

    plan = build_evaluation_plan(["品类 A", "品类 B"])
    if plan["network_requested"] is not False or plan["requires_authorized_credentials"] is not True:
        errors.append("D2 live evaluation dry-run must not request network")

    source = AuthorizedDataSource(
        source_id="d2-source",
        provider="test-provider",
        source_kind="owned_file",
        authorization_status="verified",
        authorization_reference="d2-test",
        allowed_use="evaluation",
        owner_id="d2-owner",
    )
    record = AuthorizedProductRecord(
        record_id="d2-record",
        source_id="d2-source",
        title="D2 test product",
        retrieved_at="2026-08-17T00:00:00Z",
    )
    report = validate_authorized_dataset(source, [record])
    if report["status"] != "ready_for_verification" or report["commercial_decision_ready"]:
        errors.append("verified D2 fixture must be ready for verification but not commercial-ready")

    token = issue_workspace_token("d2-owner", secret="d2-acceptance", now=1000)
    if not token or not verify_workspace_token("d2-owner", token, secret="d2-acceptance", now=1000):
        errors.append("workspace token round-trip failed")
    if verify_workspace_token("other-owner", token, secret="d2-acceptance", now=1000):
        errors.append("workspace token was not bound to owner")

    manifest_path = bundle / "manifest.json"
    if not manifest_path.is_file():
        errors.append(f"missing D2 bundle manifest: {manifest_path}")
    else:
        try:
            paths = {str(item["path"]) for item in json.loads(manifest_path.read_text(encoding="utf-8")).get("files", [])}
            for relative in ("docs/D2_AUTHORIZED_DATA_AND_MULTIUSER_PLAN_2026-08-17.md", "scripts/run_d2_live_evaluation.py", "scripts/run_d2_acceptance.py"):
                if relative not in paths:
                    errors.append(f"D2 file missing from manifest: {relative}")
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            errors.append("invalid D2 bundle manifest")
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
