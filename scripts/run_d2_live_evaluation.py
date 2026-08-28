"""Plan or execute a real-search quality evaluation.

The default is a no-network dry run. ``--execute`` is intentionally explicit
because live mode requires a user-owned, legally authorized search provider.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ecommerce.search.benchmark import (  # noqa: E402
    DEFAULT_CATEGORIES,
    run_search_benchmark,
)


def build_evaluation_plan(categories: list[str]) -> dict[str, object]:
    return {
        "schema_version": "d2-live-evaluation-plan-v1",
        "mode": "real-search",
        "network_requested": False,
        "requires_authorized_credentials": True,
        "categories": categories,
        "metrics": [
            "search_success_rate",
            "interface_success_rate",
            "evidence_usable_rate",
            "commercial_decision_ready_rate",
            "average_latency_ms",
            "average_warning_count",
            "module_averages",
        ],
        "guardrails": [
            "记录 provider、endpoint、时间和脱敏错误分类，不写入 API Key",
            "商业决策门禁默认不会因搜索成功而自动开放",
            "结果需按品类和人工抽检记录审阅，不能直接解释为销量预测",
        ],
        "next_step": "配置用户自有且有授权的搜索服务后，以 --execute 运行。",
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--categories", default=",".join(DEFAULT_CATEGORIES))
    parser.add_argument("--execute", action="store_true", help="明确允许发起真实搜索请求")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    categories = [item.strip() for item in args.categories.split(",") if item.strip()]
    if not categories:
        parser.error("至少需要一个品类")
    if not args.execute:
        payload = build_evaluation_plan(categories)
    else:
        payload = run_search_benchmark(categories).to_json_dict()
        payload["network_requested"] = True
        payload["legal_data_boundary"] = "仅适用于调用者自有且有授权的搜索服务"
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
