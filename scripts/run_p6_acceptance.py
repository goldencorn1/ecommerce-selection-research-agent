"""Validate the P6 productionization prerequisites and local build artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


REQUIRED_FILES = (
    "Dockerfile",
    "docker-compose.yml",
    "web/Dockerfile",
    "web/package.json",
    "web/pnpm-lock.yaml",
    "web/next.config.js",
    "web/scripts/next-build-windows.cjs",
    "web/src/app/page.tsx",
    "web/src/app/ecommerce/page.tsx",
    "web/public/icon.svg",
)


def check_files(root: Path) -> list[str]:
    return [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]


def check_package(root: Path) -> list[str]:
    errors: list[str] = []
    path = root / "web/package.json"
    try:
        package = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid web/package.json: {exc}"]
    build_command = package.get("scripts", {}).get("build")
    if build_command != "node scripts/next-build-windows.cjs build":
        errors.append(f"unexpected frontend build command: {build_command!r}")
    dependencies = {
        **package.get("dependencies", {}),
        **package.get("devDependencies", {}),
    }
    for name in ("@tiptap/pm", "eslint-plugin-react-hooks"):
        if name not in dependencies:
            errors.append(f"missing explicit frontend dependency: {name}")
    return errors


def check_compose_config(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["docker", "compose", "config", "--quiet"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"docker compose config could not run: {exc}"]
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()[-1:]
        return [f"docker compose config failed: {' '.join(detail)}"]
    return []


def check_frontend_artifact(root: Path) -> list[str]:
    errors: list[str] = []
    next_dir = root / "web/.next"
    for relative in ("BUILD_ID", "standalone/server.js", "static"):
        if not (next_dir / relative).exists():
            errors.append(f"missing frontend production artifact: web/.next/{relative}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--skip-compose",
        action="store_true",
        help="skip Docker Compose static configuration validation",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    errors = check_files(root)
    errors.extend(check_package(root))
    errors.extend(check_frontend_artifact(root))
    if not args.skip_compose:
        errors.extend(check_compose_config(root))
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(json.dumps({"status": "success", "stage": "P6"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
