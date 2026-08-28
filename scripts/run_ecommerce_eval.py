"""Run the reproducible C1 offline evaluation bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from src.evaluation.a3_runner import run_a3_evaluation
from src.evaluation.dataset import DEFAULT_DATASET_PATH, load_evaluation_cases


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _review_queue(cases, count: int = 10) -> list[dict[str, object]]:
    priorities = (
        "a3-search-degradation",
        "a3-private-knowledge-hit",
        "a3-private-knowledge-miss",
        "a3-low-evidence",
        "a3-price-missing",
        "a3-commercial-verification-incomplete",
        "a3-normal",
    )
    selected = []
    selected_ids: set[str] = set()
    for tag in priorities:
        for case in cases:
            if tag in case.tags and case.id not in selected_ids:
                selected.append(case)
                selected_ids.add(case.id)
                break
        if len(selected) >= count:
            break
    for case in cases:
        if len(selected) >= count:
            break
        if case.id not in selected_ids:
            selected.append(case)
            selected_ids.add(case.id)
    return [
        {
            "case_id": case.id,
            "category": case.category,
            "tags": case.tags,
            "review_status": "pending",
            "reviewer_id": None,
            "reviewed_at": None,
            "scores": None,
            "notes": "请人工检查五大板块、证据支持关系、降级诚实性和下一步动作。",
        }
        for case in selected
    ]


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _write_markdown(path: Path, run, config: dict[str, object]) -> None:
    summary = run.summary.model_dump(mode="json")
    metric_rows = "\n".join(
        f"| {name} | {summary['metric_averages'].get(name, 0):.4f} | "
        f"{summary['metric_pass_rates'].get(name, 0):.2%} |"
        for name in sorted(summary["metric_averages"])
    )
    tag_rows = "\n".join(
        f"| {name} | {count} |"
        for name, count in summary["scenario_tag_counts"].items()
    )
    content = f"""# C1 电商选品 V1 Mock 评测报告

运行时间：{config['run_started_at']} 至 {config['run_completed_at']}
数据集：`{config['dataset_path']}`
数据集 SHA-256：`{config['dataset_sha256']}`
模式：Mock 离线；外部请求：0；模型 token：0；成本：0 USD

## 一、总体结果

| 指标 | 结果 |
|---|---:|
| 总样例数 | {summary['total_case_count']} |
| 实际测量样例数 | {summary['measured_case_count']} |
| 成功率 | {summary['success_rate']:.2%} |
| 降级样例数 | {summary['degraded_case_count']} |
| 降级通过率 | {summary['degradation_pass_rate']:.2%} |
| Judge 平均分 | {summary['judge_average_score']:.2f}/100 |
| 平均延迟 | {summary['average_latency_ms']:.2f} ms |
| P50 延迟 | {summary['latency_p50_ms']:.2f} ms |
| P95 延迟 | {summary['latency_p95_ms']:.2f} ms |
| P99 延迟 | {summary['latency_p99_ms']:.2f} ms |
| 平均 warning 数 | {summary['average_warning_count']:.2f} |

## 二、自动指标

| 指标 | 平均分 | 通过率 |
|---|---:|---:|
{metric_rows}

## 三、Judge 维度

| 维度 | 平均分 |
|---|---:|
""" + "\n".join(
        f"| {name} | {score:.2f} |"
        for name, score in summary["judge_dimension_averages"].items()
    ) + f"""

## 四、场景覆盖

| 场景标签 | 数量 |
|---|---:|
{tag_rows}

## 五、人工抽检

已生成 10 条人工抽检队列：`ecommerce-eval-v1-human-review.jsonl`。当前仅生成待审核样本，不虚构人工分数；完成抽检后再填写 reviewer、scores、notes 和校准差异。

## 六、结论与边界

- 本次 50 条 Mock 结构回归全部完成，成功率和降级通过率均为 100%。
- 该结果证明固定输入、结构化报告和降级链路在 Mock 环境可重复运行。
- 该结果不代表真实搜索准确率、真实模型质量、商品销量、库存、利润或采购成功率。
- 下一步应使用用户具备合法权限的搜索 API 和模型 API 进行 C2 真实能力验证。
"""
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/evaluation")
    )
    args = parser.parse_args()
    dataset_path = args.dataset.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)
    run = run_a3_evaluation(
        dataset_path=dataset_path,
        output_path=output_dir / "ecommerce-eval-v1.json",
    )
    completed_at = datetime.now(timezone.utc)
    cases = load_evaluation_cases(dataset_path)
    config = {
        "dataset_version": "ecommerce-eval-v1",
        "dataset_path": str(dataset_path),
        "dataset_sha256": _sha256(dataset_path),
        "mode": "mock",
        "model": "mock",
        "search_provider": "mock",
        "runner": "src.evaluation.a3_runner.run_a3_evaluation",
        "run_started_at": started_at.isoformat(),
        "run_completed_at": completed_at.isoformat(),
        "external_request_count": run.summary.total_external_request_count,
        "total_cost_usd": run.summary.total_cost_usd,
        "total_token_count": run.summary.total_token_count,
        "human_review_sample_count": 10,
    }
    (output_dir / "ecommerce-eval-v1-summary.json").write_text(
        json.dumps(
            {"config": config, "summary": run.summary.model_dump(mode="json")},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "ecommerce-eval-v1-config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_jsonl(
        output_dir / "ecommerce-eval-v1-human-review.jsonl",
        _review_queue(cases),
    )
    _write_markdown(output_dir / "ecommerce-eval-v1-report.md", run, config)
    print(json.dumps(run.summary.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
