"""Run the P1 Mock/LLM/Live evaluation contract from a shell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.evaluation.p1_runner import run_p1_evaluation


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts/evaluation/ecommerce-eval-v1-p1-run.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P1 e-commerce evaluation")
    parser.add_argument("--mode", choices=("mock", "live"), default="mock")
    parser.add_argument(
        "--judge", choices=("deterministic", "llm", "hybrid"), default="deterministic"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run_p1_evaluation(
        mode=args.mode, judge=args.judge, output_path=args.output
    )
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if result.status == "measured" else 2


if __name__ == "__main__":
    raise SystemExit(main())
