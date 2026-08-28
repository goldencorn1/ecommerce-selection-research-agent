"""Validate the D1 submission and defense materials without using external services."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


REQUIRED_FILES = (
    "docs/D0_AUDIT_REMEDIATION_REPORT_2026-08-17.md",
    "docs/D1_FINAL_SUBMISSION_AND_DEFENSE_PACK_2026-08-17.md",
    "docs/D1_DEFENSE_QA_2026-08-17.md",
    "docs/PRODUCT_REQUIREMENTS_D0_2026-08-17.md",
    "docs/PRODUCT_REQUIREMENTS_D0_2026-08-17.pdf",
    "docs/P3_FINAL_DELIVERY_RUNBOOK_2026-08-17.md",
    "docs/P3_SCORECARD_AND_SUBMISSION_CHECKLIST_2026-08-17.md",
    "docs/ecommerce_schema.md",
    "docs/evaluation_spec.md",
    "docs/USER_OPERATION_MANUAL.md",
    "artifacts/evaluation/ecommerce-eval-v1-summary.json",
    "artifacts/p3/demo/index.html",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(root: Path, bundle: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    manual_actions: list[str] = []
    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing or empty required file: {relative}")

    dataset = root / "data/evaluation/ecommerce_cases.jsonl"
    if not dataset.is_file():
        errors.append(f"missing V1 dataset: {dataset}")
    else:
        case_count = sum(1 for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip())
        if case_count != 50:
            errors.append(f"V1 dataset must contain 50 cases, found {case_count}")

    summary = root / "artifacts/evaluation/ecommerce-eval-v1-summary.json"
    if summary.is_file():
        try:
            payload = json.loads(summary.read_text(encoding="utf-8"))
            if payload.get("summary", {}).get("total_case_count") != 50:
                errors.append("evaluation summary total_case_count is not 50")
        except json.JSONDecodeError as exc:
            errors.append(f"invalid evaluation summary: {exc}")

    d0_prd = root / "docs/PRODUCT_REQUIREMENTS_D0_2026-08-17.md"
    if d0_prd.is_file() and "待补录" in d0_prd.read_text(encoding="utf-8"):
        manual_actions.append("补录正式提交人姓名，并重新生成 D0 PDF、提交包和 manifest")

    manifest_path = bundle / "manifest.json"
    if not manifest_path.is_file():
        errors.append(f"missing submission manifest: {manifest_path}")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            paths = {str(item["path"]) for item in manifest.get("files", [])}
            for relative in (
                "docs/D1_FINAL_SUBMISSION_AND_DEFENSE_PACK_2026-08-17.md",
                "docs/D1_DEFENSE_QA_2026-08-17.md",
                "scripts/run_d1_acceptance.py",
            ):
                if relative not in paths:
                    errors.append(f"D1 file missing from manifest: {relative}")
            for item in manifest.get("files", []):
                path = bundle / str(item["path"])
                if not path.is_file():
                    errors.append(f"manifest file missing: {item['path']}")
                elif path.stat().st_size != int(item["bytes"]) or sha256(path) != item["sha256"]:
                    errors.append(f"manifest integrity mismatch: {item['path']}")
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            errors.append(f"invalid manifest: {exc}")

    forbidden_names = {".env", ".env.local", ".env.production"}
    secret_pattern = re.compile(r"sk-[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}")
    for path in bundle.rglob("*"):
        if not path.is_file():
            continue
        if path.name in forbidden_names:
            errors.append(f"secret file included: {path.relative_to(bundle)}")
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if secret_pattern.search(text):
            errors.append(f"likely secret value included: {path.relative_to(bundle)}")
    return errors, manual_actions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--bundle-dir", type=Path, default=Path("artifacts/c5/final_submission"))
    args = parser.parse_args()
    errors, manual_actions = validate(args.root.resolve(), (args.root / args.bundle_dir).resolve())
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(json.dumps({"status": "success", "manual_actions": manual_actions}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
