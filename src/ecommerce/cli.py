"""Command-line entry point for the offline product research MVP."""

from __future__ import annotations

import argparse
import json
import os
import sys

from .llm_report import DeepSeekReportEnhancer
from .telemetry import run_instrumented_research


class _FailedReportEnhancer:
    """Turn model initialization failures into the normal fallback path."""

    def __init__(self, error: Exception):
        self.error = error

    def enhance(self, report):
        raise self.error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run e-commerce product research.")
    parser.add_argument("--category", default="便携榨汁杯", help="商品品类")
    parser.add_argument("--market", default="中国大陆电商", help="目标市场")
    parser.add_argument("--customer", default=None, help="目标客群；不填写时按品类自动选择")
    parser.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    parser.add_argument(
        "--model",
        choices=("mock", "deepseek"),
        default="mock",
        help="报告生成模式；deepseek 需要先配置 conf.yaml 和 DEEPSEEK_API_KEY",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Keep Chinese text and the yen sign usable on Windows consoles using GBK.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    request = {
        "category": args.category,
        "target_market": args.market,
    }
    if args.customer:
        request["target_customer"] = args.customer
    enhancer = None
    if args.model == "deepseek":
        try:
            enhancer = DeepSeekReportEnhancer()
        except Exception as exc:  # noqa: BLE001 - report a safe structured fallback
            enhancer = _FailedReportEnhancer(exc)
    result, metrics = run_instrumented_research(
        request,
        mode=args.model,
        report_enhancer=enhancer,
        input_cost_per_million=float(os.getenv("DEEPSEEK_INPUT_COST_USD_PER_MILLION", 0)),
        output_cost_per_million=float(os.getenv("DEEPSEEK_OUTPUT_COST_USD_PER_MILLION", 0)),
    )
    if args.as_json:
        output = result.to_json_dict()
        output["metrics"] = metrics.to_dict()
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(result.markdown, end="")
    return 0
