# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
Entry point script for the DeerFlow project.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from InquirerPy import inquirer

from src.config.questions import BUILT_IN_QUESTIONS, BUILT_IN_QUESTIONS_ZH_CN
from src.ecommerce_graph import run_ecommerce_graph, run_ecommerce_report_snapshot
from src.workflow import run_agent_workflow_async


def _configure_utf8_stdio() -> None:
    """Keep Chinese reports readable in Windows PowerShell and redirected logs."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


_configure_utf8_stdio()


def _emit_json_payload(payload: dict, output_file: str | None = None) -> None:
    """Print or write JSON without relying on PowerShell's native encoding."""

    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if output_file:
        target = Path(output_file)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(serialized, encoding="utf-8")
        print(f"JSON 已以 UTF-8 写入：{target}")
    else:
        print(serialized, end="")


def ask(
    question,
    debug=False,
    max_plan_iterations=1,
    max_step_num=3,
    enable_background_investigation=True,
    enable_clarification=False,
    max_clarification_rounds=None,
    locale=None,
):
    """Run the agent workflow with the given question.

    Args:
        question: The user's query or request
        debug: If True, enables debug level logging
        max_plan_iterations: Maximum number of plan iterations
        max_step_num: Maximum number of steps in a plan
        enable_background_investigation: If True, performs web search before planning to enhance context
        enable_clarification: If False (default), skip clarification; if True, enable multi-turn clarification
        max_clarification_rounds: Maximum number of clarification rounds (default: None, uses State default=3)
        locale: The locale setting (e.g., 'en-US', 'zh-CN')
    """
    asyncio.run(
        run_agent_workflow_async(
            user_input=question,
            debug=debug,
            max_plan_iterations=max_plan_iterations,
            max_step_num=max_step_num,
            enable_background_investigation=enable_background_investigation,
            enable_clarification=enable_clarification,
            max_clarification_rounds=max_clarification_rounds,
            locale=locale,
        )
    )


def main(
    debug=False,
    max_plan_iterations=1,
    max_step_num=3,
    enable_background_investigation=True,
    enable_clarification=False,
    max_clarification_rounds=None,
):
    """Interactive mode with built-in questions.

    Args:
        enable_background_investigation: If True, performs web search before planning to enhance context
        debug: If True, enables debug level logging
        max_plan_iterations: Maximum number of plan iterations
        max_step_num: Maximum number of steps in a plan
        enable_clarification: If False (default), skip clarification; if True, enable multi-turn clarification
        max_clarification_rounds: Maximum number of clarification rounds (default: None, uses State default=3)
    """
    # First select language
    language = inquirer.select(
        message="Select language / 选择语言:",
        choices=["English", "中文"],
    ).execute()

    # Set locale based on language
    locale = "en-US" if language == "English" else "zh-CN"

    # Choose questions based on language
    questions = (
        BUILT_IN_QUESTIONS if language == "English" else BUILT_IN_QUESTIONS_ZH_CN
    )
    ask_own_option = (
        "[Ask my own question]" if language == "English" else "[自定义问题]"
    )

    # Select a question
    initial_question = inquirer.select(
        message=(
            "What do you want to know?" if language == "English" else "您想了解什么?"
        ),
        choices=[ask_own_option] + questions,
    ).execute()

    if initial_question == ask_own_option:
        initial_question = inquirer.text(
            message=(
                "What do you want to know?"
                if language == "English"
                else "您想了解什么?"
            ),
        ).execute()

    # Pass all parameters to ask function
    ask(
        question=initial_question,
        debug=debug,
        max_plan_iterations=max_plan_iterations,
        max_step_num=max_step_num,
        enable_background_investigation=enable_background_investigation,
        enable_clarification=enable_clarification,
        max_clarification_rounds=max_clarification_rounds,
        locale=locale,
    )


if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Run the Deer")
    parser.add_argument("query", nargs="*", help="The query to process")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode with built-in questions",
    )
    parser.add_argument(
        "--max_plan_iterations",
        type=int,
        default=1,
        help="Maximum number of plan iterations (default: 1)",
    )
    parser.add_argument(
        "--max_step_num",
        type=int,
        default=3,
        help="Maximum number of steps in a plan (default: 3)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--no-background-investigation",
        action="store_false",
        dest="enable_background_investigation",
        help="Disable background investigation before planning",
    )
    parser.add_argument(
        "--enable-clarification",
        action="store_true",
        dest="enable_clarification",
        help="Enable multi-turn clarification for vague questions (default: disabled)",
    )
    parser.add_argument(
        "--max-clarification-rounds",
        type=int,
        dest="max_clarification_rounds",
        help="Maximum number of clarification rounds (default: 3)",
    )
    parser.add_argument(
        "--ecommerce-mock",
        action="store_true",
        help="Run the offline e-commerce product research MVP",
    )
    parser.add_argument("--category", default="便携榨汁杯", help="E-commerce product category")
    parser.add_argument("--market", default="中国大陆电商", help="Target market")
    parser.add_argument(
        "--customer",
        default=None,
        help="Target customer segment",
    )
    parser.add_argument("--price-min", type=float, default=99.0, help="Minimum price")
    parser.add_argument("--price-max", type=float, default=299.0, help="Maximum price")
    parser.add_argument("--top-n", type=int, default=3, help="Number of recommendations")
    parser.add_argument("--json", action="store_true", help="Output e-commerce MVP result as JSON")
    parser.add_argument(
        "--output-file",
        default=None,
        help="Write e-commerce JSON directly as UTF-8; use with --json",
    )
    parser.add_argument(
        "--ecommerce-search",
        action="store_true",
        help="Explicitly enable the configured Tavily-compatible search adapter",
    )
    parser.add_argument(
        "--ecommerce-model",
        choices=("mock", "deepseek"),
        default="mock",
        help="E-commerce report language model; deepseek requires BASIC_MODEL and DEEPSEEK_API_KEY",
    )
    parser.add_argument(
        "--ecommerce-require-live",
        action="store_true",
        help="Fail without writing a report unless enabled live search and DeepSeek both succeed",
    )
    parser.add_argument(
        "--deepseek-input-cost",
        type=float,
        default=None,
        help="DeepSeek input price in USD per 1M tokens; omit to use DEEPSEEK_INPUT_COST_USD_PER_MILLION",
    )
    parser.add_argument(
        "--deepseek-output-cost",
        type=float,
        default=None,
        help="DeepSeek output price in USD per 1M tokens; omit to use DEEPSEEK_OUTPUT_COST_USD_PER_MILLION",
    )
    parser.add_argument(
        "--ecommerce-verification-file",
        default=None,
        help="Optional UTF-8 JSONL file with human commercial verification records",
    )
    parser.add_argument(
        "--ecommerce-verification-template",
        default=None,
        help="Write an editable UTF-8 commercial-verification JSONL template and exit",
    )
    parser.add_argument(
        "--ecommerce-verification-template-report",
        default=None,
        help="Bind the verification template to recommendations in a prior --json report",
    )
    parser.add_argument(
        "--ecommerce-verification-excel-template",
        default=None,
        help="Write a UTF-8 CSV template that can be opened and edited in Excel",
    )
    parser.add_argument(
        "--ecommerce-candidate-catalog",
        default=None,
        help="Write a candidate-only catalog from a saved report's search evidence",
    )
    parser.add_argument(
        "--ecommerce-demo",
        action="store_true",
        help="Run a complete offline demo and write a self-contained artifact bundle",
    )
    parser.add_argument(
        "--ecommerce-demo-dir",
        default="artifacts/ecommerce/demo",
        help="Output directory for --ecommerce-demo",
    )
    parser.add_argument(
        "--ecommerce-demo-categories",
        default="",
        help="Comma-separated categories for a multi-category offline demo",
    )
    parser.add_argument(
        "--ecommerce-report-html",
        default=None,
        help="Export a saved e-commerce report as a standalone HTML file",
    )
    parser.add_argument(
        "--ecommerce-verification-draft",
        default=None,
        help="Write explicit unknown commercial records from a saved report; never passes the gate",
    )
    parser.add_argument(
        "--ecommerce-verification-excel",
        default=None,
        help="Import commercial verification rows from an Excel/CSV file",
    )
    parser.add_argument(
        "--ecommerce-verification-excel-output",
        default=None,
        help="Output JSONL path for imported Excel verification rows",
    )
    parser.add_argument(
        "--ecommerce-verification-excel-error-report",
        default=None,
        help="Optional JSON audit report for Excel import errors, warnings and quality checks",
    )
    parser.add_argument(
        "--ecommerce-verification-excel-sheet",
        default="0",
        help="Excel sheet name or zero-based index (default: 0)",
    )
    parser.add_argument(
        "--ecommerce-verification-preflight",
        action="store_true",
        help="Validate a saved report and verification JSONL before research",
    )
    parser.add_argument(
        "--ecommerce-report-replay",
        action="store_true",
        help="Replay a saved e-commerce report without calling search or a model",
    )
    parser.add_argument(
        "--ecommerce-report-file",
        default=None,
        help="Saved --json e-commerce report used by verification preflight",
    )
    parser.add_argument(
        "--verification-max-age-days",
        type=int,
        default=30,
        help="Maximum verification record age for preflight",
    )
    parser.add_argument(
        "--search-preflight",
        action="store_true",
        help="Run one secret-safe authorized search request and exit",
    )
    parser.add_argument("--search-endpoint", default=None, help="Search endpoint (default: Tavily endpoint)")
    parser.add_argument("--search-api-key-env", default="TAVILY_API_KEY", help="Environment variable name for search key")
    parser.add_argument("--search-timeout", type=float, default=10.0, help="Search request timeout in seconds")
    parser.add_argument(
        "--search-retries",
        "--search-max-retries",
        dest="search_retries",
        type=int,
        default=0,
        help="Additional search retries (the --search-max-retries alias matches the benchmark CLI)",
    )
    parser.add_argument("--search-backoff", type=float, default=0.0, help="Exponential retry backoff in seconds")
    parser.add_argument("--search-max-results", type=int, default=5, help="Maximum results per search query")
    parser.add_argument("--search-min-score", type=float, default=0.0, help="Minimum normalized search score")
    parser.add_argument("--search-max-age-days", type=int, default=None, help="Maximum evidence age in days")
    parser.add_argument("--search-cache-ttl", type=float, default=0.0, help="Optional in-memory search cache TTL in seconds (default: disabled)")
    parser.add_argument("--search-cache-max-entries", type=int, default=128, help="Maximum entries in the optional search cache")
    parser.add_argument("--search-parallel", action="store_true", help="Opt in to parallel search fetching with a thread-safe provider")
    parser.add_argument("--search-parallel-workers", type=int, default=4, help="Maximum parallel search workers (1-4)")
    parser.add_argument("--search-allowed-domains", default="", help="Optional comma-separated source domains")
    parser.add_argument(
        "--search-module-allowed-domains",
        default="",
        help='Optional JSON object mapping modules to domains, e.g. {"market":["jd.com","taobao.com"]}',
    )
    parser.add_argument(
        "--search-source-profile",
        choices=("", "conservative-mainland"),
        default="",
        help="Optional reusable source-policy template; default is disabled",
    )
    parser.add_argument("--search-source-policy", choices=("annotate", "filter"), default="annotate", help="Source policy; annotate is the safe default")

    args = parser.parse_args()
    if args.ecommerce_report_html:
        if not args.ecommerce_report_file:
            parser.error("--ecommerce-report-html requires --ecommerce-report-file")
        from src.ecommerce.report_export import render_html_report

        saved_payload = json.loads(
            Path(args.ecommerce_report_file).read_text(encoding="utf-8-sig")
        )
        report_payload = saved_payload.get("report", saved_payload)
        run_metrics = saved_payload.get("run_metrics", {})
        target = Path(args.ecommerce_report_html)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            render_html_report(
                report_payload,
                search_status=str(saved_payload.get("search_status", "unknown")),
                model_status=str(run_metrics.get("model_status", "unknown")),
            ),
            encoding="utf-8",
        )
        print(f"HTML 报告已写入：{args.ecommerce_report_html}")
        raise SystemExit(0)
    if args.ecommerce_demo:
        from src.ecommerce.demo import run_offline_demo, run_offline_demo_suite

        categories = [
            item.strip()
            for item in args.ecommerce_demo_categories.split(",")
            if item.strip()
        ]
        if categories:
            summary = run_offline_demo_suite(
                args.ecommerce_demo_dir,
                categories=categories,
                market=args.market,
            )
        else:
            summary = run_offline_demo(
                args.ecommerce_demo_dir,
                category=args.category,
                market=args.market,
                customer=args.customer,
                price_min=args.price_min,
                price_max=args.price_max,
                top_n=args.top_n,
            )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    if args.ecommerce_verification_template:
        from src.ecommerce.provenance import (
            write_verification_template,
            write_verification_template_from_report,
        )

        if args.ecommerce_verification_template_report:
            report_payload = json.loads(
                Path(args.ecommerce_verification_template_report).read_text(encoding="utf-8")
            )
            report_payload = report_payload.get("report", report_payload)
            count = write_verification_template_from_report(
                args.ecommerce_verification_template,
                report_payload,
            )
        else:
            count = write_verification_template(args.ecommerce_verification_template, args.category)
        print(
            f"已生成 {count} 条商业核验模板记录：{args.ecommerce_verification_template}\n"
            "请替换 REPLACE_WITH_* 字段后，再使用 --ecommerce-verification-file 运行。"
        )
        raise SystemExit(0)
    if args.ecommerce_verification_excel_template:
        if not args.ecommerce_verification_template_report:
            parser.error(
                "--ecommerce-verification-excel-template requires "
                "--ecommerce-verification-template-report"
            )
        from src.ecommerce.provenance import write_verification_csv_template_from_report

        report_payload = json.loads(
            Path(args.ecommerce_verification_template_report).read_text(encoding="utf-8-sig")
        )
        report_payload = report_payload.get("report", report_payload)
        count = write_verification_csv_template_from_report(
            args.ecommerce_verification_excel_template,
            report_payload,
        )
        print(
            f"已生成 {count} 条 Excel 可打开的 CSV 商业核验模板："
            f"{args.ecommerce_verification_excel_template}\n"
            "请替换占位字段后，再使用 --ecommerce-verification-excel 导入。"
        )
        raise SystemExit(0)
    if args.ecommerce_candidate_catalog:
        if not args.ecommerce_report_file:
            parser.error("--ecommerce-candidate-catalog requires --ecommerce-report-file")
        from src.ecommerce.provenance import build_candidate_catalog

        saved_payload = json.loads(
            Path(args.ecommerce_report_file).read_text(encoding="utf-8-sig")
        )
        report_payload = saved_payload.get("report", saved_payload)
        catalog = build_candidate_catalog(report_payload)
        target = Path(args.ecommerce_candidate_catalog)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            f"已生成 {catalog['candidate_count']} 条候选证据目录：{args.ecommerce_candidate_catalog}\n"
            "该目录仅用于候选筛选，不代表真实商业事实。"
        )
        raise SystemExit(0)
    if args.ecommerce_verification_draft:
        if not args.ecommerce_report_file:
            parser.error("--ecommerce-verification-draft requires --ecommerce-report-file")
        from src.ecommerce.provenance import write_unverified_verification_records

        saved_payload = json.loads(
            Path(args.ecommerce_report_file).read_text(encoding="utf-8-sig")
        )
        report_payload = saved_payload.get("report", saved_payload)
        count = write_unverified_verification_records(
            args.ecommerce_verification_draft,
            report_payload,
        )
        print(
            f"已生成 {count} 条未核验草稿记录：{args.ecommerce_verification_draft}\n"
            "这些记录明确不会通过商业门禁，也不代表真实商品事实。"
        )
        raise SystemExit(0)
    if args.ecommerce_verification_excel:
        if not args.ecommerce_report_file or not args.ecommerce_verification_excel_output:
            parser.error(
                "--ecommerce-verification-excel requires "
                "--ecommerce-report-file and --ecommerce-verification-excel-output"
            )
        from src.ecommerce.provenance import (
            import_verification_rows,
            write_excel_import_report,
            write_verification_records,
        )

        saved_payload = json.loads(
            Path(args.ecommerce_report_file).read_text(encoding="utf-8-sig")
        )
        report_payload = saved_payload.get("report", saved_payload)
        sheet_name: str | int = (
            int(args.ecommerce_verification_excel_sheet)
            if str(args.ecommerce_verification_excel_sheet).isdigit()
            else args.ecommerce_verification_excel_sheet
        )
        try:
            imported = import_verification_rows(
                args.ecommerce_verification_excel,
                report_payload,
                sheet_name=sheet_name,
            )
        except (OSError, ValueError) as exc:
            if args.ecommerce_verification_excel_error_report:
                error_report = {
                    "status": "error",
                    "input_file": args.ecommerce_verification_excel,
                    "output_file": args.ecommerce_verification_excel_output,
                    "errors": [str(exc)],
                    "warnings": [],
                    "quality_checks": {},
                }
                Path(args.ecommerce_verification_excel_error_report).parent.mkdir(
                    parents=True, exist_ok=True
                )
                Path(args.ecommerce_verification_excel_error_report).write_text(
                    json.dumps(error_report, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
            raise SystemExit(2)
        summary = {"input_file": args.ecommerce_verification_excel, "output_file": args.ecommerce_verification_excel_output, **imported.as_dict()}
        if args.ecommerce_verification_excel_error_report:
            write_excel_import_report(
                args.ecommerce_verification_excel_error_report,
                imported,
                input_file=args.ecommerce_verification_excel,
                output_file=args.ecommerce_verification_excel_output,
            )
        if imported.complete:
            write_verification_records(args.ecommerce_verification_excel_output, imported.records)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise SystemExit(0 if imported.complete else 2)
    if args.ecommerce_verification_preflight:
        if not args.ecommerce_report_file or not args.ecommerce_verification_file:
            parser.error(
                "--ecommerce-verification-preflight requires "
                "--ecommerce-report-file and --ecommerce-verification-file"
            )
        from src.ecommerce.provenance import run_verification_preflight

        preflight = run_verification_preflight(
            args.ecommerce_report_file,
            args.ecommerce_verification_file,
            max_age_days=args.verification_max_age_days,
        )
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        raise SystemExit(0 if preflight["status"] == "pass" else 2)
    if args.ecommerce_report_replay:
        if not args.ecommerce_report_file:
            parser.error("--ecommerce-report-replay requires --ecommerce-report-file")
        try:
            ecommerce_state = run_ecommerce_report_snapshot(
                args.ecommerce_report_file,
                verification_file=args.ecommerce_verification_file,
                max_age_days=args.verification_max_age_days,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.error(f"无法复用电商报告快照：{exc}")
        if args.json:
            _emit_json_payload(
                {
                    "report": ecommerce_state["ecommerce_report"],
                    "report_fingerprint": ecommerce_state["ecommerce_report_fingerprint"],
                    "run_metrics": ecommerce_state["ecommerce_metrics"],
                    "search_status": ecommerce_state["ecommerce_search_status"],
                    "search_details": ecommerce_state["ecommerce_search_details"],
                    "citation_validation": ecommerce_state["ecommerce_citation_validation"],
                    "verification_records": ecommerce_state["ecommerce_verification_records"],
                    "verification_validation": ecommerce_state["ecommerce_verification_validation"],
                },
                args.output_file,
            )
        else:
            print(ecommerce_state["final_report"], end="")
        raise SystemExit(0)
    module_allowlist = {}
    if args.search_module_allowed_domains:
        try:
            parsed_module_allowlist = json.loads(args.search_module_allowed_domains)
        except json.JSONDecodeError as exc:
            parser.error(f"--search-module-allowed-domains must be valid JSON: {exc.msg}")
        if not isinstance(parsed_module_allowlist, dict) or any(
            not isinstance(module, str) or not isinstance(domains, list)
            or any(not isinstance(domain, str) for domain in domains)
            for module, domains in parsed_module_allowlist.items()
        ):
            parser.error("--search-module-allowed-domains must map module names to string arrays")
        module_allowlist = parsed_module_allowlist
    source_policy = args.search_source_policy
    if args.search_source_profile:
        from src.ecommerce.search.source_policies import get_source_policy_template

        template = get_source_policy_template(args.search_source_profile)
        if not module_allowlist:
            module_allowlist = template["source_domain_allowlist_by_module"]
        if source_policy == "annotate":
            source_policy = str(template["source_policy"])

    if args.search_preflight:
        from src.ecommerce.search import run_search_preflight

        preflight = run_search_preflight(
            f"{args.category} {args.market} 竞品 价格",
            endpoint=args.search_endpoint,
            api_key_env=args.search_api_key_env,
            timeout=args.search_timeout,
            max_retries=args.search_retries,
            retry_backoff=args.search_backoff,
            max_results=min(args.search_max_results, 5),
        )
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        raise SystemExit(0 if preflight["status"] == "success" else 2)

    if args.ecommerce_mock:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        ecommerce_request = {
            "category": args.category,
            "target_market": args.market,
            "price_min": args.price_min,
            "price_max": args.price_max,
            "top_n": args.top_n,
            "search_enabled": args.ecommerce_search,
            "model_config": {
                "enabled": args.ecommerce_model == "deepseek",
                "verification_file": args.ecommerce_verification_file,
            },
            "search_config": {
                "endpoint": args.search_endpoint,
                "api_key_env": args.search_api_key_env,
                "timeout": args.search_timeout,
                "max_retries": args.search_retries,
                "retry_backoff": args.search_backoff,
                "max_results": args.search_max_results,
                "min_score": args.search_min_score,
                "max_age_days": args.search_max_age_days,
                "cache_ttl_seconds": args.search_cache_ttl,
                "cache_max_entries": args.search_cache_max_entries,
                "parallel_modules": args.search_parallel,
                "max_parallel_searches": args.search_parallel_workers,
                "source_domain_allowlist": [item.strip() for item in args.search_allowed_domains.split(",") if item.strip()],
                "source_domain_allowlist_by_module": module_allowlist,
                "source_policy": source_policy,
            },
        }
        if args.deepseek_input_cost is not None:
            ecommerce_request["model_config"]["input_cost_per_million"] = args.deepseek_input_cost
        if args.deepseek_output_cost is not None:
            ecommerce_request["model_config"]["output_cost_per_million"] = args.deepseek_output_cost
        if args.customer:
            ecommerce_request["target_customer"] = args.customer
        ecommerce_state = run_ecommerce_graph(ecommerce_request)
        if args.ecommerce_require_live:
            live_search_ok = ecommerce_state["ecommerce_search_status"] == "success"
            live_model_ok = (
                args.ecommerce_model != "deepseek"
                or ecommerce_state["ecommerce_metrics"].get("model_status") == "success"
            )
            if not live_search_ok or not live_model_ok:
                failed_search_modules = {
                    module: details
                    for module, details in ecommerce_state["ecommerce_search_details"].items()
                    if details.get("status") != "success"
                }
                failure = {
                    "status": "error",
                    "error_code": "live_run_not_ready",
                    "message": "真实搜索或 DeepSeek 未成功，严格模式不会写入报告文件",
                    "search_status": ecommerce_state["ecommerce_search_status"],
                    "model_status": ecommerce_state["ecommerce_metrics"].get("model_status"),
                    "failed_search_modules": failed_search_modules,
                }
                print(json.dumps(failure, ensure_ascii=False, indent=2))
                raise SystemExit(2)
        if args.json:
            _emit_json_payload(
                {
                    "report": ecommerce_state["ecommerce_report"],
                    "report_fingerprint": ecommerce_state["ecommerce_report_fingerprint"],
                    "run_metrics": ecommerce_state["ecommerce_metrics"],
                    "search_status": ecommerce_state["ecommerce_search_status"],
                    "search_details": ecommerce_state["ecommerce_search_details"],
                    "citation_validation": ecommerce_state["ecommerce_citation_validation"],
                    "verification_records": ecommerce_state["ecommerce_verification_records"],
                    "verification_validation": ecommerce_state["ecommerce_verification_validation"],
                },
                args.output_file,
            )
        else:
            print(ecommerce_state["final_report"], end="")
        raise SystemExit(0)

    if args.interactive:
        # Pass command line arguments to main function
        main(
            debug=args.debug,
            max_plan_iterations=args.max_plan_iterations,
            max_step_num=args.max_step_num,
            enable_background_investigation=args.enable_background_investigation,
            enable_clarification=args.enable_clarification,
            max_clarification_rounds=args.max_clarification_rounds,
        )
    else:
        # Parse user input from command line arguments or user input
        if args.query:
            user_query = " ".join(args.query)
        else:
            # Loop until user provides non-empty input
            while True:
                user_query = input("Enter your query: ")
                if user_query is not None and user_query != "":
                    break

        # Run the agent workflow with the provided parameters
        ask(
            question=user_query,
            debug=args.debug,
            max_plan_iterations=args.max_plan_iterations,
            max_step_num=args.max_step_num,
            enable_background_investigation=args.enable_background_investigation,
            enable_clarification=args.enable_clarification,
            max_clarification_rounds=args.max_clarification_rounds,
        )
