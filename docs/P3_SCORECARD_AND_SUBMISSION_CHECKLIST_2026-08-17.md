# P3 评分依据与最终提交清单

## 一、答辩评分口径

以下是基于当前实现的估算，不代表评委最终分数：

| 维度 | 估算 | 满分 | 主要证据 |
| --- | ---: | ---: | --- |
| 原创程度 | 23 | 30 | 证据约束、质量门禁、BYOK、降级和 Agent 编排组合 |
| 用户体验 | 20 | 25 | 一键启动、Mock 快捷路径、配置预检、报告/历史/导出 |
| 应用价值 | 20 | 25 | 面向选品验证，连接证据、风险和行动，不伪造商业事实 |
| 性能表现 | 15 | 20 | Docker 健康检查、Mock 稳定性、缓存/重试/观测/P95 |
| 基础分 | **78** | **100** | 当前演示版估算 |
| 产品计划加分 | **17** | **20** | 阶段路线、评测规格、交接材料和可复现验收 |
| 合计 | **95** | **120** | 约 79.2%（若按 120 分折算） |

## 二、应主动展示的证据

- `docs/PRODUCT_DESIGN_SPEC.md`：产品定位、五大报告板块和真实性边界；
- `docs/P3_FINAL_DELIVERY_RUNBOOK_2026-08-17.md`：固定五分钟演示路径；
- `docs/ecommerce_schema.md`：V1 输入输出 schema；
- `docs/evaluation_spec.md`：50 条评测格式和指标；
- `docs/P0_P1_PRODUCT_QUALITY_REPORT_2026-08-17.md`：可信度与产品化能力；
- `docs/P2_RESEARCH_OBSERVABILITY_REPORT_2026-08-17.md`：质量审计和运行观测；
- `artifacts/p3/demo/index.html`：离线比较材料；
- `artifacts/evaluation/`：评测摘要和人工抽检队列；
- `manifest.json`：提交包文件哈希与密钥排除策略。

## 三、最终提交前检查

- [x] D0 正式 PRD Markdown 与 PDF 已生成，PDF 已渲染复核；
- [x] V1 评测口径已统一为 50 条 JSONL 案例；
- [x] D1 提交与答辩总包、评委问答和自动验收已生成；
- [ ] 将正式提交人姓名补录到 `docs/PRODUCT_REQUIREMENTS_D0_2026-08-17.md`，重新生成 PDF 并重建提交包；
- [x] Docker Desktop 已启动，`docker compose ps` 显示 backend healthy；
- [x] 双击 `start_ecommerce_mock.bat` 可打开页面；
- [x] Mock 一键流程已走通；
- [x] 质量审计显示商业决策门禁未在无核验数据时开放；
- [x] 50 条评测摘要可读取；
- [x] 离线材料可打开且不访问外部网络；
- [x] JSON、Markdown、HTML 下载可用；
- [x] `scripts/run_p3_acceptance.py` 和 `scripts/run_d1_acceptance.py` 通过；
- [x] 提交包 manifest 校验通过；
- [x] 提交包内没有 `.env`、API Key、Token 或本机路径配置。

## 四、答辩重点表述

推荐表述：

> 选品研判台的核心不是让模型直接猜市场，而是把研究结论、证据来源、价格时效、风险和下一步验证动作放在同一条可追溯链路中。没有合法真实商业数据时，系统会保持候选和验证状态，不会把 Mock 或搜索摘要包装成商业事实。

避免表述：

- “系统已经拥有真实全网商品数据”；
- “推荐分数就是销量预测”；
- “DeepSeek 可以替代商品数据 API”；
- “Mock 评测等于真实市场准确率”。
