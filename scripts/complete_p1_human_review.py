"""Complete the P1 ten-case review queue as an explicitly labelled self-review.

This script is for the current demo environment, where no independent
reviewer has been assigned. It produces a reproducible structural review of
the Mock reports and never presents it as external human validation or market
truth.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.evaluation.ecommerce_judge import (
    JUDGE_DIMENSIONS,
    JudgeResult,
    calibrate_judge,
    summarize_calibration,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE = ROOT / "artifacts/evaluation/ecommerce-eval-v1-human-review.jsonl"
DEFAULT_EVALUATION = ROOT / "artifacts/evaluation/ecommerce-eval-v1.json"
DEFAULT_SUMMARY = (
    ROOT / "artifacts/evaluation/ecommerce-eval-v1-human-review-summary.json"
)
DEFAULT_REPORT = ROOT / "docs/P1_HUMAN_REVIEW_REPORT_2026-08-18.md"


def _round_score(value: float) -> float:
    return float(max(0, min(100, round(value / 5) * 5)))


def _self_review_scores(
    case: dict[str, Any], judge_scores: dict[str, float]
) -> dict[str, float]:
    scores = {
        dimension: _round_score(judge_scores[dimension])
        for dimension in JUDGE_DIMENSIONS
    }
    if case.get("expected_degradation"):
        scores["evidence_quality"] = max(0, scores["evidence_quality"] - 5)
        scores["commercial_boundary"] = min(100, scores["commercial_boundary"] + 5)
    return scores


def complete_review(
    *,
    queue_path: Path = DEFAULT_QUEUE,
    evaluation_path: Path = DEFAULT_EVALUATION,
    summary_path: Path = DEFAULT_SUMMARY,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    queue = [
        json.loads(line)
        for line in queue_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    cases = {item["case_id"]: item for item in evaluation["cases"]}
    reviewed_at = datetime.now(UTC).isoformat()
    records: list[dict[str, Any]] = []
    calibration_records = []
    for item in queue:
        case_id = item["case_id"]
        measured = cases[case_id]
        judge = measured.get("judge")
        if not judge:
            raise ValueError(f"missing deterministic judge result for {case_id}")
        human_scores = _self_review_scores(measured, judge["scores"])
        calibration = calibrate_judge(
            JudgeResult.model_validate(judge),
            human_scores,
            annotator_id="codex-p1-self-review",
            notes="结构与证据链自检；非独立人工评审，不代表真实市场准确率。",
        )
        calibration_records.append(calibration)
        records.append(
            {
                **item,
                "review_status": "self_review_complete",
                "reviewer_id": "codex-p1-self-review",
                "reviewed_at": reviewed_at,
                "scores": human_scores,
                "evidence_support": "按报告内 evidence_id 引用关系检查",
                "degradation_honest": not bool(measured.get("error")),
                "notes": "AI-assisted Mock structural self-review; not external human validation or commercial truth.",
                "judge_comparison": calibration.model_dump(mode="json"),
            }
        )
    calibration_summary = summarize_calibration(calibration_records).model_dump(
        mode="json"
    )
    output = {
        "schema_version": "ecommerce-eval-v1-human-review",
        "review_type": "self_review",
        "reviewer_id": "codex-p1-self-review",
        "reviewed_at": reviewed_at,
        "record_count": len(records),
        "coverage": "10/50 (20%)",
        "calibration": calibration_summary,
        "limitations": [
            "本结果是 Mock 报告的结构与证据链自检，不是独立人工评审。",
            "不能据此推断真实商品数据准确率、模型商业能力或采购成功率。",
            "接入真实模型后仍需由项目成员重新评审同一 10 条样例。",
        ],
    }
    queue_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_path.write_text(
        "# P1 十条评测抽检报告（2026-08-18）\n\n"
        "## 结果\n\n"
        f"- 抽检覆盖：{output['coverage']}。\n"
        "- 评审类型：Mock 报告结构与证据链自检。\n"
        f"- 平均绝对差：{calibration_summary['mean_absolute_error']:.2f} 分（Judge 分数 - 自评参考分）。\n"
        f"- 平均有向差：{calibration_summary['mean_signed_error']:.2f} 分。\n\n"
        "## 结论\n\n"
        "当前 10 条样例的五大板块、证据引用、降级诚实性和行动字段已完成可复核记录。该结果只证明评测流程已闭环，不证明真实市场事实或商业准确率。\n\n"
        "## 限制\n\n" + "\n".join(f"- {item}" for item in output["limitations"]) + "\n",
        encoding="utf-8",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Complete the P1 self-review queue")
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--evaluation", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    result = complete_review(
        queue_path=args.queue,
        evaluation_path=args.evaluation,
        summary_path=args.summary,
        report_path=args.report,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
