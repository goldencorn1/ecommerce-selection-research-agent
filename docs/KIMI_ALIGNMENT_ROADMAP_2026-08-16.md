# Kimi 方案对齐路线大纲

> 日期：2026-08-16
> 说明：本文用于记录当前项目与 `kimi方案.txt` 的对照结论及后续推进路线。文中的完成度、优先级和收益判断均属于阶段性估算，不能替代测试结果；凡未经过实际测量的指标，均不得写成事实或宣传数字。

## 1. 对照结论

当前项目已经形成一个可运行的电商选品研判 MVP，已有搜索适配、Mock/Live 模式、结构化报告、证据溯源、降级机制、历史回放、Excel 导入、Web 工作台和商业核验门禁。项目的“可演示功能完整度”较高，核心流程已经可以在离线条件下复现。

与 Kimi 方案中更偏研究型、工程型的目标相比，主要差距集中在四个深度层：

1. 多智能体目前已有研究模块和编排能力，但还需要进一步明确 Supervisor、专职 Agent、Reviewer 的 Graph 边界和独立评测方式。
2. 尚未形成完整的电商垂域私有知识库闭环，尤其缺少统一商品/供应商证据模型、向量检索和 Rerank 的可复现实验。
3. 评测、LLM-as-Judge、人工校准和消融实验尚未形成完整的研究管线。
4. Langfuse 全链路观测、限流、熔断、Docker 实际启动和公网 Demo 等工程化目标仍待推进。

当前完成度估算：

- 作为可运行电商选品 MVP：约 88%；
- 按 Kimi 方案所描述的深度工程目标：约 55%—65%。

以上百分比是基于现有代码、文档、测试和产物的人工估算，不是自动评分，也不是经过第三方验收的结论。

## 2. 已确认基线与限制

以下是目前已经得到的阶段性事实：

- A0 前的电商单元测试基线为 `92 passed`；A0 新增 9 项 schema 契约测试后，当前电商单元测试为 `101 passed`。
- A0 评测回归测试为 `9 passed`，未改变原有 28 条评测数据格式。
- A0 相关 Ruff 检查通过，未修改生产 Python 代码，Mock/Live 入口保持兼容。
- 在排除外部依赖缺失的 checkpoint 测试并使用兼容导入模式后，全量测试已实测 `1248 passed, 1 skipped`。
- 离线三品类 Demo 和报告回放已成功运行，回放过程外部请求数为 `0`。
- fallback Web 健康检查和页面访问已返回 HTTP `200`。
- 前端 `npm run typecheck` 仍被 `@types/yargs/index.d.ts` 的语法错误阻断。
- Docker Compose 配置存在，但 Docker 实际启动尚未验证。
- 默认全量测试仍存在同名 `test_search.py` 模块冲突，checkpoint 测试还存在外部测试依赖缺失问题。
- 真实搜索报告中的部分来源缺少发布时间或来源分级，因此只能作为候选研究证据，不能直接视为已核验的商业事实。

后续文档、实验报告和演示材料必须区分：Mock 数据、搜索候选证据、私有资料、人工商业核验数据和可用于采购决策的数据。

## 3. 项目本身推进路线：A0—A5

### A0：基线和协议冻结

目标：

- 固定 V1 输入输出 schema；
- 明确五大报告板块及字段定义；
- 固定 50 条评测的格式、关键点和降级规则；
- 保留当前 Mock/Live 兼容接口，不因协议整理破坏现有 CLI、Web API 和回放能力。

计划产出：

- `docs/ecommerce_schema.md`；
- `docs/evaluation_spec.md`；
- schema 回归测试；
- 一份当前字段到 V1 字段的映射说明。

验收标准：

- 同一输入在 Mock 模式下可以稳定生成符合 V1 schema 的报告；
- 五大板块、推荐方向、证据、风险和验证动作均有明确字段；
- 缺失数据、搜索失败和模型失败有明确的空值/降级约定；
- 现有 Mock/Live 入口和报告回放测试不被破坏；
- schema 回归测试通过，并记录实际测试命令和结果。

### A1：多智能体 Graph 化

目标：

- 将现有研究模块整理为 Supervisor、Market、Competitor、Price、Customer、Risk、Report、Reviewer 等清晰节点；
- 每个 Agent 输出结构化结果、证据和状态；
- 支持局部失败、重试、降级和质量门禁；
- 保持当前 CLI、Web API、Mock/Live 适配和报告回放兼容。

验收标准：

- 各节点有独立单元测试和最小输入输出契约；
- 能从最终报告追溯到 Agent、工具和证据；
- 任一非关键 Agent 失败时仍能生成带限制说明的报告；
- Reviewer 能阻止无证据或越过商业核验门禁的结论。

### A2：私有知识库和自定义工具

目标：

- 支持商品库、供应商资料和平台规则的 JSONL/CSV/文档导入；
- 建立商品、价格、成本、销量周期、库存、平台、来源文件和更新时间等元数据；
- 增加 BGE embedding adapter、向量召回和 Rerank 接口；
- 增加价格/榜单工具的 Mock 与 HTTP 适配器。

验收标准：

- 私有证据能够参与推荐并在报告中显示来源；
- 私有知识未命中时能够回退到现有 Mock/Live 流程；
- 每条证据都有来源、更新时间和可信度标签；
- 不把候选证据自动升级为采购事实。

### A3：50 条评测和电商专用 LLM Judge

目标：

- 将现有评测样例扩展并固定为 50 条；
- 覆盖正常、搜索失败、模型失败、私有知识命中/未命中、低证据质量、价格缺失和商业核验不完整等场景；
- 增加市场判断、竞品拆解、价格带、人群匹配、风险识别、证据质量和商业边界等评分维度；
- 支持批量运行、JSONL 保存、人工抽检和 Judge 失败降级。

验收标准：

- 50 条样例均有输入、预期关键点、允许降级行为和评分规则；
- 可重复生成成功率、关键点覆盖率、延迟、Token 和成本等结果；
- 至少完成约定比例的人工抽检，并保存人工与 Judge 的差异；
- 所有未测指标保持“待测”状态，不提前填写提升百分比。

### A4：Rerank、重试和消融实验

目标：

- 比较有/无专职子智能体的流程；
- 比较向量召回与向量召回加 Rerank；
- 增加 Planner 重试、预算控制和失败分类；
- 在同一数据、模型和评测集上保存原始实验结果。

验收标准：

- 至少形成两组可复现实验及配置快照；
- 比较任务成功率、关键点覆盖率、平均延迟、P99、Token、成本、证据命中率和无关证据率；
- 结论同时报告收益、代价和统计口径；
- 没有实际测量的数据不写成“提升 XX%”。

### A5：工程化收口

目标：

- 接入 Langfuse 或等效的统一 trace/span/generation 观测；
- 增加限流、熔断、超时和外部服务预算控制；
- 完成 Docker 实际启动和端到端流程验证；
- 固化生产配置、错误边界、敏感信息保护和部署说明。

验收标准：

- 能查看一次完整任务从请求到报告的链路；
- 外部服务异常时有可观测、可解释的降级结果；
- 超限请求会被安全拒绝；
- Docker 环境能完成一次端到端流程；
- 运行说明与实际验证结果一致。

## 4. 演示与提交材料路线：B1—B3

### B1：演示路径

在项目核心能力稳定后，固定一条可重复的主路径：

```text
输入品类、预算和目标人群
  → Supervisor 拆解任务
  → 市场/竞品/价格/用户/风险分析
  → 私有知识与搜索证据召回
  → 可选 Rerank
  → 结构化报告
  → Reviewer/质量门禁
  → 风险提示与下一步验证动作
```

最终录制优先使用离线 Mock 数据和已经验证的 fallback Web，确保网络和外部服务波动不会影响演示。演示中应明确展示：证据来源、失败降级、商业核验门禁、历史回放和不能直接采购的边界。

### B2：演示材料

需要准备：

- 产品设计说明书；
- 产品需求文档及 PDF；
- 3—5 分钟演示视频；
- 系统架构图、Agent 分工图和数据流图；
- 评测指标与实验配置；
- 运行截图、精选报告和回放结果；
- README、运行说明、环境变量示例和最终提交说明。

### B3：材料表达重点

材料不应只展示“生成了一份报告”，还应说明：

- 为什么采用多智能体拆分；
- 私有知识和 Rerank 解决什么问题；
- 如何处理搜索、模型和数据缺失；
- 如何观察成本、延迟和证据质量；
- 哪些结论可以辅助研究，哪些结论仍需人工核验；
- 当前已测结果、待测指标和项目限制分别是什么。

## 5. 优先级

### P0：必须先完成

1. A0 协议冻结和 schema 回归测试；
2. 统一当前文档中的测试、Python 版本、演示品类和验证状态口径；
3. 保持现有 Mock/Live、CLI、Web 和回放兼容；
4. 在协议稳定后推进 A1 的 Graph 边界设计。

### P1：核心深度能力

1. A1 多智能体 Graph 化；
2. A2 私有知识库、向量召回和自定义工具；
3. A3 50 条评测与电商专用 Judge；
4. A4 Rerank、重试、预算控制和消融实验。

### P2：工程化和展示增强

1. A5 Langfuse、限流、熔断和 Docker 实测；
2. B1 演示路径固化；
3. B2/B3 设计说明书、PRD、视频、截图和提交包；
4. 公网 Demo、博客和正式运营能力。

## 6. 明确暂不做项

在 A0—A4 的核心协议、评测和实验未稳定前，暂不把以下事项作为主线阻塞项：

- 大规模真实商品数据接入；
- 直接给出进货、采购或盈利保证；
- 未经实测的效果提升数字和宣传结论；
- 大范围升级前端依赖或重构现有 Web UI；
- 云部署、正式公网运营和复杂用户权限系统；
- 完整支付、订单、库存交易闭环；
- 为了展示而绕过证据质量门禁或商业核验门禁；
- 在没有同一评测集和固定配置的情况下进行性能比较；
- 把 Docker 配置文件存在写成 Docker 已完成部署；
- 把通用搜索候选结果写成已经验证的市场事实。

## 8. A0 实际完成记录（2026-08-16）

已完成：

- 新增 `docs/ecommerce_schema.md`，冻结 V1 输入、报告、运行信封、五大板块映射、证据边界和 Mock/Live 兼容规则；
- 新增 `docs/evaluation_spec.md`，冻结 50 条评测目标格式、关键点标注、自动指标、Judge 和人工抽检规范；
- 新增 `tests/unit/ecommerce/test_schema_contract.py`，覆盖输入校验、JSON 序列化、五大板块映射、证据引用、Mock/Live 控制和现有 28 条评测兼容；
- 新增 9 项 schema 回归测试；
- 电商单元测试实测 `101 passed`；评测单元测试实测 `9 passed`；Ruff 检查通过。

A0 尚未扩展评测数据到 50 条，也尚未改变生产 schema 或实现 A1 的 Supervisor/专职 Agent；这两项分别属于 A3 和 A1，不能因文档冻结而宣称已经完成。

## 7. 推荐执行顺序

```text
A0 协议与基线冻结
  → A1 多智能体 Graph 化
  → A2 私有知识库与工具
  → A3 50 条评测与专用 Judge
  → A4 Rerank、重试与消融实验
  → A5 观测、限流、熔断与 Docker
  → B1 演示路径
  → B2/B3 设计说明书、PRD、视频与提交材料
```

每个阶段完成后，必须保存实际测试命令、原始结果、配置和已知限制；只有在验收标准满足且结果可复现时，才将阶段标记为完成。

## 9. A1 实际完成记录（2026-08-16）

已完成 A1 的第一版兼容接入：

- 新增 `src/ecommerce/agent_graph.py`，固定 `supervisor → market → competitor → price → customer → risk → report → reviewer` 八节点顺序；
- 四个研究节点复用现有 `ResearchProvider` 和研究类，Price 节点只从竞品结果派生价格锚点，不重复调用外部工具；
- 每个节点输出统一的 JSON 结果包，包含 `agent`、`status`、`output`、`evidence_ids`、`warnings`、`error_kind`、`attempts`；
- 单模块异常会记录 `error`/降级 warning，并继续执行 Report/Reviewer；
- `ResearchResult`、DeerFlow `State` 和 `ecommerce_graph` 适配层新增 `agent_plan`/`agent_results` 可观测字段；
- 保留 `run_mock_research`、搜索适配、DeepSeek 报告增强、CLI/Web 字段和 snapshot replay；回放仍不进入研究图，也不调用外部请求；
- 新增 `tests/unit/ecommerce/test_agent_graph.py` 与 `test_agent_graph_integration.py`，覆盖节点路由、结构化状态、证据传递、局部失败、公共 Graph 传递和回放隔离。

实测结果：

- 电商测试目录：`106 passed`；
- Graph 状态保持、locale 恢复和 Server API 回归：`107 passed, 1 skipped`；
- A1 定向组合测试：`36 passed`；
- `ruff check`：通过；`git diff --check`：通过；
- 项目默认全量收集仍被既有同名测试模块冲突阻断：`tests/unit/ecommerce/search/test_search.py` 与 `tests/unit/tools/test_search.py` 都导入为 `test_search`。该问题发生在收集阶段，不是 A1 运行失败。

A1 的边界说明：对外的 `src/ecommerce_graph.py` 仍保留单节点兼容适配器，内部实际执行已切换到显式八节点子图；质量门禁继续由现有 telemetry、验证记录和商业核验字段负责。尚未在 A1 宣称重试策略、Rerank、私有知识库或 50 条评测完成，这些属于 A2—A4。

## 10. A2 实际完成记录（2026-08-16）

已完成 A2 的离线可复现版本：

- `PrivateKnowledgeRecord` 支持商品、供应商、SKU、平台、价格、成本、销量周期、库存、来源文件、更新时间和扩展元数据；
- 私有资料支持 JSONL、CSV、Markdown 和 TXT 导入，CSV 支持中英文列名，坏行不会阻塞其他有效记录；
- 记录可转换为现有 `KnowledgeDocument` 和 `Evidence`，本地来源统一为 `local://`，并保留候选证据语义；
- 新增 Hash/Deterministic embedding、BGE-compatible embedding adapter、VectorRetriever、Lexical/BGE Reranker adapter；
- 新增 Mock/HTTP PriceTool 与 RankTool，HTTP 适配器支持注入 transport/client、稳定错误分类和 Evidence 转换；
- `run_ecommerce_graph()` 新增可选 `knowledge_config`，私有命中进入报告证据链；未命中、加载失败和检索失败均回退到现有研究路径；
- Web payload 暴露 `knowledge_status`、`knowledge_details` 和 `agent_plan`，没有改变既有报告字段；
- 新增 A2 导入、向量、工具和 Graph 集成测试。

实测结果：

- A2 知识库、向量、工具和 Graph 集成定向测试：`72 passed`；
- 电商测试目录：`135 passed`；
- Graph 状态保持、locale 恢复和 Server API 回归：`107 passed, 1 skipped`；
- A2 相关新模块 Ruff 检查、Python 编译检查和 `git diff --check` 通过；
- A2 交付时项目全量测试曾受 `test_search` 同名模块收集冲突影响；该问题已在 A3 阶段修复并由全量测试复核。

A2 的边界说明：当前向量默认使用无网络 Hash embedding，真实 BGE 仅完成可注入适配接口；价格/榜单 HTTP 适配器已完成但尚未接入真实平台凭据；尚未完成 50 条评测、LLM-as-Judge、Rerank 效果对比和消融实验，这些属于 A3/A4。

## 11. A3 实际完成记录（2026-08-16）

已完成 A3 的可复现评测基线：

- `data/evaluation/ecommerce_cases.jsonl` 从 28 条扩展并固定为 50 条，ID 唯一，覆盖正常、搜索/模块降级、低证据、私有知识命中/未命中、价格缺失、商业核验不完整和边界预算等场景；
- 新增 `src/evaluation/ecommerce_judge.py`，固定市场、竞品、价格、客群、风险、证据质量、商业边界七个评分维度及权重；
- 提供无网络 deterministic Judge、可注入 async/sync LLM Judge、坏 JSON/调用失败 fallback、人工校准记录和误差汇总；
- 新增 `src/evaluation/a3_runner.py`，逐例运行 50 条 Mock 评测、保存 JSON 结果并汇总成功率、延迟、warning、Judge 分数和人工复核数量；
- 修复 `tests/unit/tools/test_search.py` 与电商搜索测试同名导致的 `import file mismatch`；
- 修复 checkpoint 单元测试中伪连接测试仍在构造函数访问 localhost 的阻塞问题，改为显式注入 fake connection；
- 更新 A0 schema 回归断言，从 28 条切换到 50 条。

实测结果：

- A3 评测数据、Judge、Runner 和旧评测回归：`28 passed`；
- A3 Runner 实际完成 50/50 条，成功率 `1.0`；
- checkpoint 回归：`23 passed, 3 skipped`；
- 全项目测试：`1325 passed, 4 skipped`；
- 全量收集：`1329 items`，无 `import file mismatch`；
- A3 相关 Ruff、Python 编译检查和 `git diff --check`：通过。

A3 的边界说明：当前默认 Judge 是结构化、无网络的可复现基线；LLM Judge 已具备注入接口和失败降级，但尚未做人工抽检统计、模型间一致性分析或效果提升宣称。下一阶段 A4 应在固定 50 条数据和 A3 输出格式之上开展 Rerank/无 Rerank、专职 Agent/单流程、重试和预算控制的消融实验。

## 12. A4 实际完成记录（2026-08-16）

已完成 A4 的离线可复现实验框架：

- 新增 `src/evaluation/a4_policy.py`，固定 `timeout`、`budget_exceeded`、`provider_error`、`validation_error`、`unknown_error` 五类失败分类；
- 新增可序列化 `BudgetController`，支持 case、attempt、latency、cost 四类预算边界；
- 新增 `RetryPolicy` 和 `run_with_retry`，默认仅对 timeout/provider_error 重试，不对校验错误和预算错误重试；
- `src/ecommerce/orchestration.py` 增加私有的顺序执行基线开关，默认 Agent Graph 行为与 V1 保持不变；
- 新增 `src/evaluation/a4_runner.py`，固定实验配置哈希、Agent/Rerank 消融开关、逐案例 Judge、原始 `ResearchResult` 保存、失败分类和 measured 对比结果；
- `src/evaluation/__init__.py` 暴露 A4 Runner 和比较接口；
- 新增 A4 策略与 Runner 契约测试，共 `16 passed`。

固定 50 条数据的四臂实测结果已保存到 `artifacts/evaluation/a4/`：

| 实验臂 | Agent | Rerank | 样本数 | 成功率 | Judge 均分 |
|---|---:|---:|---:|---:|---:|
| single-vector | 否 | 否 | 50 | 1.0 | 79.1252 |
| agents-vector | 是 | 否 | 50 | 1.0 | 79.1252 |
| single-rerank | 否 | 是 | 50 | 1.0 | 79.2114 |
| agents-rerank | 是 | 是 | 50 | 1.0 | 79.2114 |

这组结果只代表本地 Mock、Hash embedding 和固定 Judge 下的实测差异，不构成真实线上效果提升结论。当前观测到 Agent Graph 相对顺序基线的平均延迟差为 `+13.7613 ms`，Rerank 相对 agents-vector 的 Judge 均分差为 `+0.0862`；两项差异均应在真实数据和真实模型下重新验证。

最终验收：

- 全项目测试：`1341 passed, 4 skipped`；
- 全量收集：`1345 items`，无 collection/import error；
- A4 定向测试：`16 passed`；
- A4 50 条四臂实验：4/4 完成、每臂 50/50 成功；
- A4 相关 Ruff、Python 编译检查和 `git diff --check`：通过。

A4 的边界说明：当前重试与预算策略已接入离线评测 Runner，真实模型成本仍以 provider usage 为准；尚未宣称 Langfuse 观测、限流/熔断、Docker 实测或人工 Judge 校准提升，这些进入 A5 或 B 阶段。

## 13. A5 实际完成记录（2026-08-16）

已完成 A5 的代码和本地服务级接入：

- 新增 `src/ecommerce/resilience.py`，提供线程安全固定窗口限流、`retry_after`、快照恢复、Circuit Breaker 的 `closed/open/half_open` 状态迁移和稳定失败分类；
- 新增 `src/ecommerce/observability.py`，提供 JSON-safe `ObservationEvent`、有界内存 Recorder、最近事件查询、清空和 span 成功/失败记录；
- `src/server/app.py` 已将限流和熔断接入 `/api/ecommerce/research`：限流返回 `429 + Retry-After`，熔断返回 `503 + Retry-After`；
- `/api/ecommerce/health` 暴露限流配置、熔断快照和观测事件数量；
- 新增 `/api/ecommerce/observability`，仅返回有界的本地诊断事件；
- `.env.example` 增加限流、熔断恢复和事件缓冲区配置；
- Dockerfile/Compose 保留后端健康检查、前端等待后端 healthy、8000 端口暴露和 0.0.0.0 绑定契约。

实测结果：

- A5 策略层和接口级测试：`25 passed`；
- 全项目测试：`1366 passed, 4 skipped`；
- 全量收集：`1370 items`，无导入/收集错误；
- A5 相关 Ruff、Python 编译检查和 `git diff --check`：通过；
- 本地 TestClient 已验证正常请求、429 限流、503 熔断、健康状态和观测事件查询。

环境边界（代码阶段记录）：此前 Docker CLI/daemon 尚未就绪，因此当时只完成了 Dockerfile/Compose 静态契约和本地服务级健康检查；本记录不覆盖后续实际容器验收。

## 14. A5 容器验收实际完成记录（2026-08-16）

Docker Desktop、WSL2 和 Hypervisor 已恢复，实际完成了以下验收：

- Docker Desktop `4.86.0`，Docker CLI `29.7.2`，Compose `v5.3.1`；
- `docker compose config --quiet` 通过；
- backend/frontend 镜像真实构建通过；
- Compose 启动通过，backend `healthy`，frontend 在 backend healthy 后启动；
- backend `/api/ecommerce/health` 和 frontend `/ecommerce` 均返回 HTTP 200；
- Mock 研究请求返回 3 条推荐、4 条证据、12 条进度事件、历史记录和全部通过的质量门禁；
- 浏览器实际点击生成按钮后成功渲染报告，CORS 和 favicon 资源问题已修复，console 无错误。

容器验收补丁包括：frontend 优先使用锁定的 pnpm 依赖、backend 使用 `uv run --no-sync`、双回环地址 CORS、未知值安全显示和显式 favicon route。B 阶段继续按用户要求暂停。
