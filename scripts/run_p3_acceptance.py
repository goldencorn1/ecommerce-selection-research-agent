"""Validate the P3 offline demo materials and secret-free submission bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REQUIRED_FILES = (
    "docs/P3_FINAL_DELIVERY_RUNBOOK_2026-08-17.md",
    "docs/P3_SCORECARD_AND_SUBMISSION_CHECKLIST_2026-08-17.md",
    "docs/P3_FINAL_VALIDATION_2026-08-18.md",
    "docs/P2_RESEARCH_OBSERVABILITY_REPORT_2026-08-17.md",
    "docs/PRODUCT_REQUIREMENTS_D0_2026-08-17.md",
    "docs/PRODUCT_REQUIREMENTS_D0_2026-08-17.pdf",
    "docs/PRODUCT_DESIGN_SPEC.md",
    "docs/USER_OPERATION_MANUAL.md",
    "artifacts/evaluation/ecommerce-eval-v1-summary.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_demo(root: Path, demo_dir: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"missing required file: {relative}")
    summary_path = demo_dir / "summary.json"
    if not summary_path.is_file():
        summary_path = demo_dir / "comparison.json"
    index_path = demo_dir / "index.html"
    if not summary_path.is_file():
        errors.append(f"missing offline demo summary: {summary_path}")
    if not index_path.is_file() or index_path.stat().st_size == 0:
        errors.append(f"missing or empty offline demo index: {index_path}")
    elif any(token in index_path.read_text(encoding="utf-8") for token in ("http://", "https://")):
        errors.append("offline demo index must not contain external HTTP links")
    if summary_path.is_file():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            case_count = summary.get("case_count", summary.get("category_count", 0))
            if int(case_count) < 3:
                errors.append("offline demo must contain at least three categories")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid offline demo summary: {exc}")
    case_dirs = sorted(path for path in demo_dir.glob("case-*") if path.is_dir())
    if len(case_dirs) < 3:
        errors.append(f"offline demo must contain at least three case directories, found {len(case_dirs)}")
    for case_dir in case_dirs:
        for filename in (
            "summary.json",
            "report.json",
            "report.md",
            "report.html",
            "commercial-verification-preflight.json",
            "commercial-verification-demo-only.jsonl",
        ):
            if not (case_dir / filename).is_file():
                errors.append(f"offline demo case missing {case_dir.name}/{filename}")
        summary_file = case_dir / "summary.json"
        if summary_file.is_file():
            try:
                case_summary = json.loads(summary_file.read_text(encoding="utf-8"))
                if case_summary.get("mode") != "offline_demo":
                    errors.append(f"offline demo case is not marked offline_demo: {case_dir.name}")
                if int(case_summary.get("recommendation_count", 0)) < 3:
                    errors.append(f"offline demo case must contain three recommendations: {case_dir.name}")
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                errors.append(f"invalid offline demo case summary {case_dir.name}: {exc}")
        preflight_file = case_dir / "commercial-verification-preflight.json"
        if preflight_file.is_file():
            try:
                preflight = json.loads(preflight_file.read_text(encoding="utf-8"))
                if preflight.get("status") != "blocked":
                    errors.append(f"commercial verification must remain blocked in demo: {case_dir.name}")
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"invalid commercial preflight {case_dir.name}: {exc}")
        verification_file = case_dir / "commercial-verification-demo-only.jsonl"
        if verification_file.is_file() and "DEMO_ONLY" not in verification_file.read_text(encoding="utf-8"):
            errors.append(f"commercial verification demo data must be marked DEMO_ONLY: {case_dir.name}")
    eval_path = root / "data/evaluation/ecommerce_cases.jsonl"
    if eval_path.is_file():
        try:
            case_count = sum(
                1 for line in eval_path.read_text(encoding="utf-8").splitlines() if line.strip()
            )
            if case_count != 50:
                errors.append(f"V1 evaluation set must contain exactly 50 cases, found {case_count}")
        except OSError as exc:
            errors.append(f"unable to read V1 evaluation set: {exc}")
    else:
        errors.append(f"missing V1 evaluation set: {eval_path}")
    return errors


def validate_manifest(bundle: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = bundle / "manifest.json"
    if not manifest_path.is_file():
        return [f"missing manifest: {manifest_path}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid manifest: {exc}"]
    for item in manifest.get("files", []):
        path = bundle / str(item["path"])
        if not path.is_file():
            errors.append(f"manifest file missing: {item['path']}")
            continue
        if path.stat().st_size != int(item["bytes"]):
            errors.append(f"manifest size mismatch: {item['path']}")
        if sha256(path) != item["sha256"]:
            errors.append(f"manifest hash mismatch: {item['path']}")
    forbidden_names = {".env", ".env.local", ".env.production"}
    for path in bundle.rglob("*"):
        if path.is_file() and path.name in forbidden_names:
            errors.append(f"secret file included: {path.relative_to(bundle)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--demo-dir", type=Path, default=Path("artifacts/p3/demo"))
    parser.add_argument(
        "--bundle-dir", type=Path, default=Path("artifacts/c5/final_submission")
    )
    args = parser.parse_args()
    root = args.root.resolve()
    demo_dir = (root / args.demo_dir).resolve()
    bundle_dir = (root / args.bundle_dir).resolve()
    errors = validate_demo(root, demo_dir)
    errors.extend(validate_manifest(bundle_dir))
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(
        json.dumps(
            {"status": "success", "demo_dir": str(demo_dir), "bundle_dir": str(bundle_dir)},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
