"""Build a secret-free C5 final submission bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


FILES = (
    ".env.demo.example",
    "docker-compose.demo.yml",
    "start_ecommerce_mock.bat",
    "start_ecommerce_offline_bundle.bat",
    "scripts/generate_ecommerce_offline_bundle.ps1",
    "scripts/build_d0_prd_pdf.py",
    "scripts/run_p3_acceptance.py",
    "scripts/run_d1_acceptance.py",
    "scripts/run_d2_live_evaluation.py",
    "scripts/run_d2_acceptance.py",
    "scripts/run_d3_cross_category_evaluation.py",
    "scripts/run_d3_acceptance.py",
    "scripts/run_d4_acceptance.py",
    "scripts/run_d5_acceptance.py",
    "scripts/run_d5_integration_preflight.py",
    "docs/ecommerce_schema.md",
    "docs/evaluation_spec.md",
    "docs/PRODUCT_DESIGN_SPEC.md",
    "docs/USER_OPERATION_MANUAL.md",
    "docs/B5_DEMO_RUNBOOK_2026-08-17.md",
    "docs/C0_DEMO_FREEZE_2026-08-17.md",
    "docs/C1_EVALUATION_REPORT_2026-08-17.md",
    "docs/C2_REAL_CAPABILITY_REPORT_2026-08-17.md",
    "docs/C3_QUALITY_GOVERNANCE_REPORT_2026-08-17.md",
    "docs/C4_COMMERCIAL_DATA_DEMO_REPORT_2026-08-17.md",
    "docs/C5_FINAL_SUBMISSION_REPORT_2026-08-17.md",
    "docs/P2_RESEARCH_OBSERVABILITY_REPORT_2026-08-17.md",
    "docs/P3_FINAL_DELIVERY_RUNBOOK_2026-08-17.md",
    "docs/P3_SCORECARD_AND_SUBMISSION_CHECKLIST_2026-08-17.md",
    "docs/P3_FINAL_VALIDATION_2026-08-18.md",
    "docs/PRODUCT_REQUIREMENTS_D0_2026-08-17.md",
    "docs/PRODUCT_REQUIREMENTS_D0_2026-08-17.pdf",
    "docs/PROJECT_AUDIT_AND_TEST_REPORT_2026-08-17.md",
    "docs/D0_AUDIT_REMEDIATION_REPORT_2026-08-17.md",
    "docs/D1_FINAL_SUBMISSION_AND_DEFENSE_PACK_2026-08-17.md",
    "docs/D1_DEFENSE_QA_2026-08-17.md",
    "docs/D2_AUTHORIZED_DATA_AND_MULTIUSER_PLAN_2026-08-17.md",
    "docs/HANDOFF_D2_2026-08-17.md",
    "docs/D3_PRODUCTIONIZATION_PLAN_2026-08-17.md",
    "docs/HANDOFF_D3_2026-08-17.md",
    "docs/D4_IDENTITY_STORAGE_PLAN_2026-08-17.md",
    "docs/HANDOFF_D4_2026-08-17.md",
    "docs/D5_REAL_ENVIRONMENT_INTEGRATION_PLAN_2026-08-17.md",
    "docs/HANDOFF_D5_2026-08-17.md",
    "docs/PRODUCT_API_AND_EXCEL_GUIDE_2026-08-17.md",
    "migrations/001_ecommerce_tenant_rls.sql",
    "docs/PROJECT_SCORING_ANALYSIS_2026-08-17.md",
    "docs/PROJECT_SCORING_REPORT.md",
    "docs/HANDOFF_CURRENT_2026-08-17.md",
    "docs/HANDOFF_P3_2026-08-17.md",
    "artifacts/evaluation/ecommerce-eval-v1-summary.json",
    "artifacts/evaluation/ecommerce-eval-v1-report.md",
    "artifacts/evaluation/ecommerce-eval-v1-human-review.jsonl",
    "artifacts/c2/c2-real-capability-summary.json",
    "artifacts/c2/c2-real-e2e-summary.json",
    "artifacts/c2/c2-real-e2e.json",
    "artifacts/c3/c3-quality-audit.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_file(root: Path, output: Path, relative: str) -> None:
    source = root / relative
    if not source.is_file():
        raise FileNotFoundError(f"required submission file is missing: {relative}")
    target = output / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copy_tree(root: Path, output: Path, relative: str) -> None:
    source = root / relative
    if not source.is_dir():
        raise FileNotFoundError(f"required submission directory is missing: {relative}")
    shutil.copytree(source, output / relative, dirs_exist_ok=True)


def build_submission(root: Path, output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    for relative in FILES:
        _copy_file(root, output, relative)
    _copy_tree(root, output, "artifacts/c4/demo")
    optional_demo = root / "artifacts/p3/demo"
    if optional_demo.is_dir():
        _copy_tree(root, output, "artifacts/p3/demo")

    readme = output / "README.md"
    readme.write_text(
        """# DeerFlow 电商选品研究工作台：P3 最终交付包

## 快速演示

1. 在项目原仓库根目录双击 `start_ecommerce_mock.bat`，打开 Web 工作台。
2. 选择 Mock 演示，输入“可折叠露营桌”，生成报告。
3. 展示 Agent 过程、质量审计、证据边界、验证动作和导出。
4. 打开 `artifacts/p3/demo/index.html`（若未生成则使用 `artifacts/c4/demo/index.html`），展示离线比较。
5. 展示 `commercial-verification-demo-only.jsonl` 和对应的 `blocked` 预检，说明没有真实商业数据时系统不会放开商业决策。

## 交付边界

- 本包不包含 `.env`、真实 API Key、OAuth token、授权回调或个人配置。
- Mock 数据只用于流程演示和回归测试。
- 真实销量、成本、库存、转化率和 SKU 合规数据必须由使用者提供合法来源后再导入。
- `manifest.json` 提供每个交付文件的大小和 SHA-256。

## 主要材料

- 正式 PRD：`docs/PRODUCT_REQUIREMENTS_D0_2026-08-17.pdf`
- D1 提交与答辩总包：`docs/D1_FINAL_SUBMISSION_AND_DEFENSE_PACK_2026-08-17.md`
- D1 高频问答：`docs/D1_DEFENSE_QA_2026-08-17.md`
- 产品说明：`docs/PRODUCT_DESIGN_SPEC.md`
- 用户操作：`docs/USER_OPERATION_MANUAL.md`
- 评分依据：`docs/P3_SCORECARD_AND_SUBMISSION_CHECKLIST_2026-08-17.md`
- P3 验收记录：`docs/P3_FINAL_VALIDATION_2026-08-18.md`
- 评测结果：`artifacts/evaluation/`
- 真实能力脱敏记录：`artifacts/c2/`
- 质量审计：`artifacts/c3/c3-quality-audit.json`
- 商业数据演示：`artifacts/c4/demo/`
- P3 离线演示：`artifacts/p3/demo/`
- D0 整改记录：`docs/D0_AUDIT_REMEDIATION_REPORT_2026-08-17.md`
""",
        encoding="utf-8",
    )

    entries = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        if path.name == "manifest.json":
            continue
        relative = path.relative_to(output).as_posix()
        entries.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    manifest = {
        "schema_version": "p3-submission-manifest-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "secret_policy": "allowlist copy; .env and credentials excluded",
        "file_count": len(entries),
        "files": entries,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/c5/final_submission")
    )
    args = parser.parse_args()
    manifest = build_submission(Path.cwd(), args.output_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
