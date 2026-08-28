"""Plan or execute a cross-category live-search evaluation for D3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ecommerce.cross_category_eval import evaluate_cross_category_run  # noqa: E402
from src.ecommerce.search.benchmark import (  # noqa: E402
    run_search_benchmark,
)


DEFAULT_CATEGORIES = [
    "可折叠露营桌",
    "便携榨汁杯",
    "桌面收纳盒",
    "通勤双肩包",
    "桌面小风扇",
]


def build_plan(categories: list[str]) -> dict[str, object]:
    return {
        "schema_version": "d3-cross-category-eval-plan-v1",
        "mode": "real-search",
        "network_requested": False,
        "requires_authorized_credentials": True,
        "category_count": len(categories),
        "categories": categories,
        "thresholds": {
            "min_categories": 3,
            "min_search_success_rate": 0.8,
            "min_evidence_usable_rate": 0.8,
        },
        "not_claimed": [
            "不代表销量预测准确率",
            "不代表商业决策门禁已开放",
            "不替代平台授权数据和人工复核",
        ],
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--categories", default=",".join(DEFAULT_CATEGORIES))
    parser.add_argument("--execute", action="store_true", help="明确允许调用真实搜索服务")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    categories = [item.strip() for item in args.categories.split(",") if item.strip()]
    if len(categories) < 3:
        parser.error("跨品类评测至少需要三个品类")
    if args.execute:
        run = run_search_benchmark(categories)
        payload = {
            "run": run.to_json_dict(),
            "evaluation": evaluate_cross_category_run(run),
            "network_requested": True,
            "legal_data_boundary": "仅适用于调用者自有且有授权的搜索服务",
        }
    else:
        payload = build_plan(categories)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
