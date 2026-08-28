"""Audit a saved e-commerce report without calling search or model APIs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ecommerce.quality_audit import audit_report_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("artifacts/c2/c2-real-e2e.json"),
        help="Saved UTF-8 e-commerce report JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/c3/c3-quality-audit.json"),
        help="Output UTF-8 audit JSON",
    )
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
    audit = audit_report_payload(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
