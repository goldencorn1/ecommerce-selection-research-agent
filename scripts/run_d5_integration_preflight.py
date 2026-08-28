"""Plan or explicitly probe D5 real-environment integration prerequisites."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.server.integration_preflight import (  # noqa: E402
    build_d5_preflight_plan,
    execute_d5_preflight,
)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="明确允许探测已配置的外部依赖")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    payload = execute_d5_preflight() if args.execute else build_d5_preflight_plan()
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if payload["status"] in {"ready", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
