"""Run offline acceptance checks for D3 productionization boundaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ecommerce.authorized_adapters import list_authorized_adapters  # noqa: E402
from src.server.tenant_auth import decode_bearer_token  # noqa: E402
from scripts.run_d3_cross_category_evaluation import (  # noqa: E402
    DEFAULT_CATEGORIES,
    build_plan,
)


REQUIRED_FILES = (
    "docs/D3_PRODUCTIONIZATION_PLAN_2026-08-17.md",
    "docs/HANDOFF_D3_2026-08-17.md",
    "scripts/run_d3_cross_category_evaluation.py",
    "src/ecommerce/authorized_adapters.py",
    "src/ecommerce/cross_category_eval.py",
    "src/server/tenant_auth.py",
)


def validate(root: Path, bundle: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing D3 file: {relative}")

    plan = build_plan(DEFAULT_CATEGORIES)
    if plan["network_requested"] is not False or plan["category_count"] < 3:
        errors.append("D3 cross-category dry-run plan is invalid")
    if any("api_key" in item for item in list_authorized_adapters()):
        errors.append("adapter registry exposes a credential field")

    try:
        import jwt

        token = jwt.encode(
            {"sub": "d3-acceptance", "tenant_id": "tenant-d3", "exp": 4102444800},
            "d3-acceptance-secret",
            algorithm="HS256",
        )
        principal = decode_bearer_token(
            "Bearer " + token,
            secret="d3-acceptance-secret",
        )
        if principal is None or principal.tenant_id != "tenant-d3":
            errors.append("D3 JWT acceptance round-trip failed")
    except Exception as exc:  # noqa: BLE001 - acceptance should report one failure
        errors.append(f"D3 JWT acceptance failed: {type(exc).__name__}")

    manifest = bundle / "manifest.json"
    if not manifest.is_file():
        errors.append(f"missing D3 bundle manifest: {manifest}")
    else:
        try:
            paths = {str(item["path"]) for item in json.loads(manifest.read_text(encoding="utf-8")).get("files", [])}
            for relative in (
                "docs/D3_PRODUCTIONIZATION_PLAN_2026-08-17.md",
                "docs/HANDOFF_D3_2026-08-17.md",
                "scripts/run_d3_cross_category_evaluation.py",
                "scripts/run_d3_acceptance.py",
            ):
                if relative not in paths:
                    errors.append(f"D3 file missing from manifest: {relative}")
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            errors.append("invalid D3 bundle manifest")
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
