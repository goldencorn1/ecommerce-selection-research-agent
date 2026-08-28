# D1 正式提交与答辩材料总包

更新时间：2026-08-17

## 1. D1 目标

D1 将已经完成的 Mock MVP、真实能力配置、证据审计、离线商业核验和 P3 演示材料整理为一套评委可以快速理解、现场可以复现、边界可以解释的提交包。

项目正式名称建议使用：**选品研判台 - 面向证据与验证动作的电商研究工作台**。

一句话定位：**系统不让模型直接猜销量，而是把选品研究、证据来源、风险和下一步验证动作组织成一条可追溯链路。**

## 2. 提交材料清单

### 必交材料

- `docs/PRODUCT_REQUIREMENTS_D0_2026-08-17.pdf`：正式产品需求文档；
- `docs/PRODUCT_DESIGN_SPEC.md`：产品设计说明；
- `docs/P3_FINAL_DELIVERY_RUNBOOK_2026-08-17.md`：现场 5 分钟演示路径；
- `docs/ecommerce_schema.md`：V1 输入输出协议；
- `docs/evaluation_spec.md`：V1 50 条评测规格；
- `docs/USER_OPERATION_MANUAL.md`：用户操作手册；
- `artifacts/p3/demo/index.html`：三品类离线演示材料；
- `artifacts/c5/final_submission/manifest.json`：文件哈希和密钥排除证明。

### 证据材料

- `artifacts/evaluation/ecommerce-eval-v1-summary.json`：50 条 Mock 评测结果；
- `artifacts/c3/c3-quality-audit.json`：质量审计结果；
- `artifacts/c4/demo/`：无真实商业数据时的 `DEMO_ONLY` 核验闭环；
- `docs/D0_AUDIT_REMEDIATION_REPORT_2026-08-17.md`：审核问题整改记录。

## 3. 五分钟答辩讲稿

### 0:00-0:40：问题与定位

“传统选品工具容易把搜索摘要、模型生成内容和商业事实混在一起。选品研判台把研究结论、证据来源、风险和验证动作拆开管理，先帮助用户判断‘值得验证什么’，而不是在缺少合法商业数据时直接建议采购或放量。”

### 0:40-1:30：输入与配置

演示品类使用“可折叠露营桌”。展示市场、客群、价格区间、Mock/Live、模型和搜索 API 配置。强调 Mock 模式无需 Key；Live 模式由使用者在页面填写并预检自己的合法 API。

### 1:30-2:40：研究流程

点击一键研究，展示显式八节点流程：Supervisor、Market、Competitor、Price、Customer、Risk、Report、Reviewer。说明每个模块有独立状态，模块失败时会保留已完成结果并给出降级原因。

### 2:40-3:40：可信度与商业边界

展示五大报告板块、证据卡片、来源类型、置信度、Trace ID 和质量审计。重点说明：Mock、搜索摘要和模型文字不能直接证明销量、库存、成本、转化率或合规；商业决策门禁在缺少合法核验数据时保持阻断。

### 3:40-4:30：评测与导出

展示 V1 50 条评测、成功率、降级通过率、Judge 均分和 P95；下载 JSON、Markdown、HTML 三种报告格式，说明结果可回放、可比较、可追溯。

### 4:30-5:00：离线商业闭环与收束

打开 `artifacts/p3/demo/index.html`，展示三品类对比和 `DEMO_ONLY` 核验记录。收束：“本项目的价值不是伪装成拥有全网商业数据，而是把不确定性显式化，让用户知道下一步需要补什么数据、验证什么风险。”

## 4. 评分证据映射

| 评分维度 | 主张 | 现场证据 |
| --- | --- | --- |
| 原创程度 | 证据约束、质量门禁、BYOK、降级机制和 Agent 编排形成组合创新 | 产品说明、八节点过程、质量审计 |
| 用户体验 | 一键启动、配置预检、状态反馈、报告导出、历史回放和离线路径 | Web 页面、操作手册、5 分钟演示 |
| 应用价值 | 将选品研究从“生成结论”推进到“证据-风险-验证动作”闭环 | 五大报告板块、商业门禁、DEMO_ONLY 记录 |
| 性能表现 | Mock 稳定性、P50/P95/P99、重试、缓存和 Docker 健康检查 | 50 条评测摘要、Docker、observability |
| 计划加分 | A0-D1 路线、阶段交接、评测规格和可复现提交包 | PRD、D0 整改记录、manifest |

## 5. 现场风险处理

| 风险 | 处理方式 | 不应承诺 |
| --- | --- | --- |
| 真实搜索网络不可用 | 切换 Mock，展示预检失败分类和降级结果 | 不声称已完成全网真实搜索 |
| DeepSeek 无法访问 | 保留结构化报告，说明模型润色是可选增强 | 不声称模型调用成功 |
| 无真实商品商业数据 | 展示 `DEMO_ONLY` 核验和 blocked 门禁 | 不声称拥有销量/库存/成本数据 |
| 评委追问准确率 | 展示 50 条 Mock 结构评测，同时明确其不等于真实市场准确率 | 不把 Mock 分数当成商业预测精度 |

## 6. D1 现场前操作

```powershell
docker compose -f docker-compose.demo.yml ps
.venv\Scripts\python.exe scripts/run_d1_acceptance.py
Start-Process ".\start_ecommerce_mock.bat"
```

确认浏览器打开：`http://127.0.0.1:3000/ecommerce`。

正式外部提交前，补录 PRD 中的开发者姓名，再重新生成 PDF、提交包和 manifest。未补录前，D1 工程验收仍可通过，但提交材料保留人工动作提示。

## 7. D1 完成定义

- 提交材料可从一个 manifest 复现；
- 5 分钟演示不依赖真实 API；
- 50 条 V1 评测口径唯一；
- 真实能力、Mock 能力和商业数据边界均能解释；
- Docker、页面、自动测试和密钥排除检查通过；
- 姓名补录是唯一待人工动作。
