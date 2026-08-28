"""Run P7 release, authorized-data, and demo-boundary acceptance checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
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
from src.ecommerce.provenance.excel_import import preview_import_file  # noqa: E402


REQUIRED_FILES = (
    "docs/P6_FINAL_VALIDATION_2026-08-18.md",
    "docs/HANDOFF_P6_2026-08-18.md",
    "docs/P7_RELEASE_REHEARSAL_2026-08-18.md",
    "docs/HANDOFF_P7_2026-08-18.md",
    "docker-compose.yml",
    "docker-compose.demo.yml",
    "Dockerfile",
    "web/Dockerfile",
    "migrations/001_ecommerce_tenant_rls.sql",
    "src/server/oidc_auth.py",
    "src/ecommerce/authorized_data.py",
    "src/ecommerce/provenance/excel_import.py",
)


def run_compose_config(root: Path, compose_file: str | None = None) -> list[str]:
    command = ["docker", "compose"]
    if compose_file:
        command.extend(["-f", compose_file])
    command.append("config")
    command.append("--quiet")
    try:
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"compose config could not run ({compose_file or 'default'}): {exc}"]
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()[-1:]
        return [f"compose config failed ({compose_file or 'default'}): {' '.join(detail)}"]
    return []


def validate_demo_compose(root: Path) -> list[str]:
    errors: list[str] = []
    content = (root / "docker-compose.demo.yml").read_text(encoding="utf-8")
    for marker in (
        'ECOMMERCE_AUTH_MODE: anonymous_local',
        'ECOMMERCE_REQUIRE_BEARER_AUTH: "false"',
        'TAVILY_API_KEY: ""',
        'DEEPSEEK_API_KEY: ""',
        'INFOQUEST_API_KEY: ""',
        "healthcheck:",
    ):
        if marker not in content:
            errors.append(f"demo compose missing safe marker: {marker}")
    return errors


def validate_authorized_fixture() -> list[str]:
    errors: list[str] = []
    source = AuthorizedDataSource(
        source_id="p7-owned-fixture",
        provider="user-owned-fixture",
        source_kind="owned_file",
        authorization_status="verified",
        authorization_reference="p7-acceptance-only",
        allowed_use="offline acceptance only",
        owner_id="tenant-p7",
    )
    record = AuthorizedProductRecord(
        record_id="p7-product-1",
        source_id=source.source_id,
        title="P7 acceptance product",
        price=99.0,
        retrieved_at=datetime.now(timezone.utc),
    )
    report = validate_authorized_dataset(source, [record])
    if report.get("status") != "ready_for_verification":
        errors.append("authorized fixture did not reach ready_for_verification")
    if report.get("commercial_decision_ready") is not False:
        errors.append("demo authorized fixture incorrectly opened the commercial gate")

    with tempfile.TemporaryDirectory(prefix="p7-csv-") as directory:
        csv_path = Path(directory) / "owned-products.csv"
        csv_path.write_text(
            "推荐方向,商品名称,平台,商品链接,核验人,核验时间,售价,销量,销量周期,单位成本,库存状态,合规状态,结论,证据ID\n"
            "方向-1,演示商品,自有表格,https://example.invalid/p7,验收人,2026-08-18T10:00:00+08:00,99,12,近30天,50,有货,待核验,待核验,evidence-p7\n",
            encoding="utf-8-sig",
        )
        preview = preview_import_file(csv_path)
        if preview.get("status") != "ready" or preview.get("row_count") != 1:
            errors.append("owned CSV preview did not pass the P7 fixture check")
        if preview.get("missing_required_columns"):
            errors.append("owned CSV preview reported unexpected missing columns")
    return errors


def validate(root: Path, skip_compose: bool) -> list[str]:
    errors = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    if errors:
        errors = [f"missing P7 file: {relative}" for relative in errors]
    errors.extend(validate_demo_compose(root))
    errors.extend(validate_authorized_fixture())
    sql = (root / "migrations/001_ecommerce_tenant_rls.sql").read_text(encoding="utf-8")
    for marker in ("FORCE ROW LEVEL SECURITY", "current_setting('app.tenant_id'", "WITH CHECK"):
        if marker not in sql:
            errors.append(f"RLS migration missing marker: {marker}")
    if not skip_compose:
        errors.extend(run_compose_config(root))
        errors.extend(run_compose_config(root, "docker-compose.demo.yml"))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--skip-compose", action="store_true")
    args = parser.parse_args()
    errors = validate(args.root.resolve(), args.skip_compose)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(json.dumps({"status": "success", "stage": "P7", "network_requested": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
