# 电商选品研究工作台：用户操作手册

版本：Final V1.0 / Web Demo 验收版
适用目录：`E:\\gpt plus\\agent project1\\deer-flow`

## 1. 当前版本能做什么

本版本用于演示“输入一个品类，生成一份带证据、评分、验证动作和风险边界的选品研究报告”。当前推荐使用 Mock 模式，Mock 不需要任何 API Key，也不依赖外部搜索网络。

已支持：

- 品类、市场、目标客群和价格区间输入；
- Mock 离线研究和 Live 真实搜索模式；
- 市场、竞品、用户、机会/风险等研究模块；
- 推荐方向、评分、证据目录、风险边界和验证卡片；
- 研究进度事件和质量门禁；
- JSON、Markdown、HTML 报告下载；
- 历史报告保存、回放和对比；
- Excel/CSV/TSV 预览、列映射和商业核验导入；
- Docker Compose 前后端运行。
- 商品 API 配置模板、启用状态、本地 Demo 商品 API 和样品载入；
- 报告“摘要—证据—风险—行动”四段导航、推荐趋势图和价格分布图；
- 移动端紧凑布局和可横向滚动的报告导航。

重要边界：Mock 结果用于验证产品流程，不代表真实市场事实；报告默认回答“先验证什么”，不能直接替代采购、进货或放量决策。

最终材料入口：

- `docs/FINAL_PRODUCT_REQUIREMENTS_2026-08-18.md`：最终产品需求文档；
- `docs/FINAL_PRODUCT_SPEC_2026-08-18.md`：最终产品说明书；
- `docs/FINAL_DEMO_RUNBOOK_2026-08-18.md`：最终现场演示手册。

## 2. 推荐启动方式：Docker Compose

### 2.0 最快捷方式：双击智能一键启动文件

在项目根目录直接双击：

```text
一键启动选品研判台.bat
```

它会自动完成：

1. 优先检查 Docker CLI 和 Docker daemon；
2. 如果 Docker Desktop 未运行，尝试自动启动并等待；
3. Docker 可用时，启动 Docker Compose Mock 演示环境；
4. Docker 不可用或启动失败时，自动切换本地后端/前端模式；
5. 本地前端不可用时，自动打开备用页面；
6. 自动打开演示页面：Docker 模式通常为 `http://127.0.0.1:3000/ecommerce`；本地备用模式通常为 `http://127.0.0.1:8000/ecommerce`。

因此，现场演示只需要双击这一个文件，不需要先判断 Docker 是否启动，也不需要手动选择启动脚本。

启动窗口可以关闭，容器会继续运行。停止服务时，再执行：

```powershell
docker compose down
```

### 2.1 启动 Docker Desktop

确认 Docker Desktop 已启动。PowerShell 中执行：

```powershell
docker info
```

如果能看到 Server 版本信息，说明 Docker daemon 可用。

### 2.2 启动项目

在项目根目录执行：

```powershell
cd "E:\\gpt plus\\agent project1\\deer-flow"
docker compose up -d --build
docker compose ps
```

正常结果应类似：

```text
deer-flow-backend   Up (healthy)   0.0.0.0:8000->8000/tcp
deer-flow-frontend  Up             0.0.0.0:3000->3000/tcp
```

backend 如果刚启动仍处于 `starting`，等待 10—30 秒后再次执行 `docker compose ps`。只有 backend 显示 `healthy` 后，才开始页面测试。

### 2.3 打开页面

浏览器打开：

```text
http://127.0.0.1:3000/ecommerce
```

也可以使用：

```text
http://localhost:3000/ecommerce
```

## 3. 最小手动测试路径

这是建议你第一次手动测试时完整执行的一条主路径。

### 第一步：确认默认参数

页面打开后，在“研究配置”区域确认：

- 商品品类：`可折叠露营桌`；
- 目标市场：`中国大陆电商`；
- 目标客群：可以留空；
- 最低价：`99`；
- 最高价：`299`；
- 数据模式：选择 `Mock 演示`；
- 报告模型：选择 `结构化 Mock`；
- 并行搜索模块：第一次测试可以不勾选。

### 第二步：生成报告

点击：

```text
开始生成选品报告
```

等待页面完成。Mock 模式一般很快返回；如果页面出现加载状态，请不要连续重复点击。

### 第三步：检查报告结果

页面完成后，依次检查：

1. 顶部出现“当前最值得先验证”区域；
2. 出现推荐方向卡片，通常为 3 条；
3. 每条方向都有价格范围、需求/竞争/利润/差异/证据评分；
4. 每条方向都有“验证卡片”；
5. 页面出现“研究进度事件”，事件状态为 `success`；
6. “报告质量门禁”中的项目均显示“通过”；
7. 页面明确提示当前报告不能直接支持采购或放量；
8. “历史报告与对比”区域出现一条新的历史记录。

本版本已验证的正常结果是：3 条推荐、4 条证据、12 条进度事件、7 项质量门禁全部通过。

### 第四步：验证报告下载

在“研究证据与导出”区域依次点击：

- `下载 JSON`；
- `下载 Markdown`；
- `下载 HTML`。

确认浏览器能够下载文件，并且文件不是空文件。JSON 适合检查结构化字段，Markdown 适合阅读，HTML 适合直接打开查看。

### 第五步：验证历史回放

1. 在“历史报告与对比”区域点击刚生成的品类记录；
2. 确认页面能够恢复之前的报告内容；
3. 回放时不应重新显示长时间的研究过程；
4. 再修改品类，例如改为 `宠物饮水机`，重新生成一份 Mock 报告；
5. 勾选两条历史记录，点击 `对比所选`；
6. 确认出现平均分、推荐数量和候选证据数量的对比信息。

## 4. 可选功能测试

### 4.1 并行搜索开关

返回研究配置，勾选“并行搜索模块”，保持 Mock 模式再次生成报告。确认页面仍能完成报告，并且报告结构和质量门禁不消失。

### 4.2 Excel/CSV/TSV 预览

在“导入 Excel 数据”区域上传 `.xlsx`、`.xlsm`、`.xls`、`.csv` 或 `.tsv` 文件。

预期行为：

- 页面显示列名、行数和前几行预览；
- 系统提示缺失的商业核验字段；
- 预览内容不会自动被当成真实商业事实；
- 完成一次研究并绑定报告后，才可以继续进行校验或导入。

### 4.3 Live/DeepSeek 模式

第一次手动验收不建议使用 Live 或 DeepSeek。它们需要 `.env` 中配置真实服务 Key，并会受到网络、额度、服务可用性和数据质量影响。

如果要测试：

1. 先确认 `.env` 已配置相应 Key；
2. 只使用一个小品类进行测试；
3. 检查报告中的来源、时间、价格和商业核验边界；
4. 不要把搜索候选证据直接当作采购事实。

### 4.4 当前 API 配置与网页临时 BYOK

当前版本保持项目原有 API 配置不变，仅用于基本演示和联调：

- `SEARCH_API=tavily`：当前真实搜索入口；
- `TAVILY_API_KEY`：本地 `.env` 中的搜索 Key，不要粘贴到页面截图、报告或聊天中；
- `DEEPSEEK_API_KEY`：可选的报告润色模型 Key；
- `INFOQUEST_API_KEY`：可选的商品页面增强 Key，目前不作为销量、排名或商品主数据 API；
- 默认演示仍建议使用 `Mock 演示`，因为 Mock 不消耗外部额度，也不受网络波动影响。

当前版本已经开放网页端临时 BYOK 设置面板，但不会保存用户 API Key。进入“本次请求 API 配置（BYOK）”区域后，可以填写：

- 模型：从预设中选择 DeepSeek、OpenAI、通义千问 / DashScope、智谱 GLM、月之暗面 Kimi、SiliconFlow、Ollama 或自定义 OpenAI-Compatible。选择后会预填常用 Endpoint 和模型名，仍可手动修改；填写 Key 后勾选“启用当前模型配置”才会真正调用该模型，取消勾选则回退到 Mock；
- 搜索：在 Live 模式下填写当前搜索供应商的 Key；SearXNG 可不填 Key；
- 商品数据：选择 InfoQuest 后填写本次请求的 Reader Key。

点击“预检当前能力”可以测试当前选择的连接；即使商品数据选择“仅使用搜索摘要”，预检也会正常执行，不再因为 `data_source=none` 失败。点击“清除本次配置”会清空当前页面中的输入。Key 只随当前请求发送，不写入报告历史、SQLite、服务端 `.env` 或页面 `localStorage`。关闭页面后，前端不会恢复这些输入。

预设里的 Endpoint 只是便于演示的兼容接口模板，不代表本机已经配置或已验证可用；真实调用仍取决于用户自己的 API Key、模型权限、额度和供应商条款。DeepSeek 官方文档当前仍说明其可通过 OpenAI 兼容接口访问，常用基地址为 `https://api.deepseek.com`；OpenAI 文档的模型接口使用 `https://api.openai.com/v1`。其他预设也应以供应商最新文档为准。

如果不填写临时 Key，系统继续使用服务端 `.env` 中的配置；Mock 模式不需要任何 Key。

后续配置会分为三块：

- AI 模型：用户可以选择 DeepSeek 或其他兼容模型，并填写自己的模型地址、模型名称和 Key；
- 搜索服务：用户可以选择 Tavily、SearXNG、Brave、Serper 或兼容搜索服务；
- 商品数据：用户需要选择项目支持的固定适配器，并填写对应商品 API，或导入自己的 CSV/Excel 数据。

“全部使用 DeepSeek”可以表示分析、总结和报告生成都使用 DeepSeek，但 DeepSeek 不会自动提供真实商品价格、销量或排名。商品事实仍必须来自用户有权使用的商品 API、网页数据或用户导入数据。

Tavily 替换方案和供应商选择请参阅：[搜索供应商替换与页面 BYOK 配置方案](SEARCH_PROVIDER_REPLACEMENT_PLAN.md)。

## 5. API 健康检查（可选）

浏览器访问：

```text
http://127.0.0.1:8000/api/ecommerce/health
```

正常应返回 JSON，且包含：

- `status: "ok"`；
- `mock_available: true`；
- `rate_limiter` 配置；
- `circuit_breaker.state: "closed"`。

PowerShell 检查命令：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/ecommerce/health
```

## 6. 停止和重新启动

### B5 最稳妥的无 Key 演示

如果只需要完成演示，不需要配置任何外部 API，双击项目根目录的 `start_ecommerce_mock.bat`。它使用独立的 `docker-compose.demo.yml`，会自动构建并启动容器，健康检查通过后打开 `http://127.0.0.1:3000/ecommerce`。页面选择“Mock 演示”即可运行。

如果只需要生成可脱离服务的三品类报告材料，双击 `start_ecommerce_offline_bundle.bat`，生成结果位于 `artifacts/ecommerce/demo/index.html`。

停止服务：

```powershell
cd "E:\\gpt plus\\agent project1\\deer-flow"
docker compose down
```

重新启动：

```powershell
docker compose up -d
```

不要使用 `docker compose down -v`，因为它可能删除不必要的卷数据。报告历史和导入审计数据保存在项目的 `artifacts` 目录中，请不要手动删除。

## 7. 常见问题

### backend 显示 unhealthy

执行：

```powershell
docker compose ps
docker compose logs --tail=100 backend
```

确认 Docker Desktop 正在运行，并等待 backend 完成启动。不要在 backend 未 healthy 时判断前端失败。

### 页面打不开

确认：

```powershell
docker compose ps
Invoke-WebRequest http://127.0.0.1:3000/ecommerce
```

如果端口被其他程序占用，先执行 `docker compose down`，再重新启动；不要直接删除项目文件。

### 页面能打开但历史接口报 CORS

使用本手册中的 `127.0.0.1:3000` 或 `localhost:3000` 访问，当前版本已同时允许这两个本地地址。若修改了 `.env`，需要重新创建 backend：

```powershell
docker compose up -d --force-recreate backend
```

### 真实搜索失败

这不代表 Mock 主流程失败。先切回 `Mock 演示`，确认离线主流程正常，再检查 API Key、网络、服务额度和来源质量。

## 8. 手动验收清单

- [ ] Docker Desktop 正常运行；
- [ ] `docker compose ps` 显示 backend `healthy`；
- [ ] `/ecommerce` 页面返回并正常显示；
- [ ] Mock 报告可以生成；
- [ ] 推荐方向、评分、证据和验证卡片显示；
- [ ] 进度事件全部成功；
- [ ] 质量门禁全部通过；
- [ ] 历史记录出现并可以回放；
- [ ] 两条历史记录可以对比；
- [ ] JSON/Markdown/HTML 可以下载；
- [ ] 可选的 Excel/CSV/TSV 预览行为符合预期；
- [ ] 页面没有明显 console 错误；
- [ ] 测试结束后按需执行 `docker compose down`。

## 9. 当前项目与 Kimi 方案的边界

A0—A5 已完成：协议、八节点 Graph、私有知识/向量/Rerank 接口、50 条评测、Judge、消融实验、重试/预算、限流/熔断、Docker 和前后端联调均已落地。

仍与 Kimi 方案存在差距的部分：

- 尚未接入 Langfuse 级别的完整外部 trace；当前是等效的本地观测、限流和熔断能力；
- 50 条评测已可重复运行，但 20% 人工抽检和 Judge 校准尚未完成；
- A4 结果主要来自本地 Mock、Hash embedding 和固定 Judge，真实模型、真实商品数据下的 P99、Token 和成本指标仍需补测；
- 私有知识库和 BGE/Rerank 已有可注入接口和离线实现，但真实供应商/商品数据闭环尚未形成；
- 尚未完成公网 Demo、演示视频、产品设计说明书、PRD、架构图和最终提交材料；
- 当前仍是匿名本地 workspace + SQLite，未完成正式认证、多用户权限、生产数据库和对象存储。

B 阶段按当前任务约定继续暂停，待你手动验收项目本身后再决定是否推进。
