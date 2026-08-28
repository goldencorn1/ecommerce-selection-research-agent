# D0 审核整改与交付记录

更新时间：2026-08-17

## 1. 整改范围

本记录对应 `docs/PROJECT_AUDIT_AND_TEST_REPORT_2026-08-17.md` 中指出的 P0 提交问题，目标是把当前可运行的 Mock MVP 整理为可复现、可审查、可提交的个人项目材料。

## 2. 已完成整改

| 审核问题 | D0 处理 | 验收证据 |
| --- | --- | --- |
| 缺少正式 PRD PDF | 新增正式 PRD Markdown，并使用中文字体生成 A4 PDF；已渲染检查 5 页 | `docs/PRODUCT_REQUIREMENTS_D0_2026-08-17.pdf` |
| 缺少人员/职责材料 | 在 PRD 中加入个人独立开发分工表，保留姓名待补录字段 | PRD 第 8 节 |
| 评测数量存在 28/50 口径冲突 | V1 统一按数据集文件中的 50 条 JSONL 案例执行；历史 28 条仅保留为早期基线说明 | `docs/evaluation_spec.md`、P3 acceptance |
| 提交包可复现性不足 | 将 D0 PRD、PDF、审计原报告和 PDF 构建脚本纳入 manifest allowlist | `artifacts/c5/final_submission/manifest.json` |
| 缺少一条可执行的最终检查 | P3 acceptance 增加 D0 文件、PDF 存在性和 V1 50 条计数检查 | `scripts/run_p3_acceptance.py` |

## 3. 仍需人工补录

当前项目按个人独立开发口径整理，系统不会虚构开发者姓名。正式提交前仅需在 PRD Markdown 的个人分工表中补录真实姓名，然后重新运行：

```powershell
.venv\Scripts\python.exe scripts/build_d0_prd_pdf.py
.venv\Scripts\python.exe scripts/build_c5_submission.py --output-dir artifacts/c5/final_submission
.venv\Scripts\python.exe scripts/run_p3_acceptance.py
```

若提交规则要求展示团队成员，则应将真实成员和实际职责替换表格中的“待补录”，不应沿用模板占位符。

## 4. D0 结论

D0 的工程整改目标已完成：PRD、评测口径、个人分工、离线材料、manifest 和自动验收均已纳入同一提交链路。D1 可以开始；但在正式外部提交前，应完成姓名补录并重建 PDF 与提交包。
