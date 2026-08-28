# B5 正式运行与演示交付手册

日期：2026-08-17

## 1. B5 交付目标

B5 将当前电商研究工作台收口为可重复启动、可重复演示、可复核交接的版本。B5 不把 Mock、搜索摘要或用户未授权的数据描述成真实商业事实。

## 2. 两条启动路径

### A. 最稳妥的离线 Mock 演示

在项目根目录双击：

```text
start_ecommerce_mock.bat
```

它使用独立的 `docker-compose.demo.yml`，不读取项目 `.env`，不需要任何 API Key；脚本会启动 Docker Desktop（若尚未运行）、构建镜像、等待 backend 健康、检查 frontend HTTP 200，并打开：

```text
http://127.0.0.1:3000/ecommerce
```

页面中选择“Mock 演示”，即可完成完整研究流程。

### B. 生成可脱离服务的离线材料包

在项目根目录双击：

```text
start_ecommerce_offline_bundle.bat
```

它会用三个不同品类生成 `artifacts/ecommerce/demo/`，并打开 `index.html`。材料包包括：

- 三品类比较页；
- 每个品类的 JSON、Markdown、HTML 报告；
- 候选证据目录；
- 快照回放结果；
- summary 和报告指纹。

该命令不调用搜索、模型或商品 API。

## 3. 固定 3—5 分钟演示路径

1. 打开工作台，说明 Mock/Live、模型、搜索供应商和商品数据源的能力状态。
2. 输入“可折叠露营桌”，保留“中国大陆电商”和默认价格区间，选择 Mock 演示。
3. 点击“开始生成选品报告”，展示参数校验、搜索模块、价格整理、报告生成四段进度。
4. 在报告顶部先讲决策状态、平均评分、推荐数量和“建议的下一步”。
5. 展示三条不同推荐方向、价格依据、评分组成和验证卡片。
6. 展开候选证据与搜索质量，强调候选证据不是销量、库存或利润事实。
7. 在 Excel 区域上传已有测试表或模板，展示预览、字段映射、校验和导入边界；没有真实核验数据时不要确认导入为商业事实。
8. 从历史报告中回放一条记录，说明回放不会再次调用搜索或模型 API。
9. 需要时选中至少两条历史报告进行比较，最后导出 JSON、Markdown 或 HTML。

## 4. 异常路径演示

- 未配置 Key：能力区显示未配置，Mock 仍可运行。
- 真实搜索失败：显示失败原因分类，并在报告中保留降级边界，不伪装为完整 Live 成功。
- 模型失败：结构化报告仍可返回，但模型状态和降级告警必须可见。
- 批量局部失败：已完成项目保留，失败项目显示原因，并提供重试入口。
- Excel 缺列：页面显示 `needs_columns` 与缺失字段，不能绕过核验门禁。

## 5. Live/DeepSeek 可选路径

常规 Compose 使用项目根目录 `.env`。请复制 `.env.example` 为 `.env`，只填写自己有权使用的搜索、模型或商品页增强 Key，再执行：

```powershell
docker compose up -d --build
```

也可以直接在网页 BYOK 区域选择模型预设、填写 Key、启用配置并执行能力预检。Live/DeepSeek 是可选能力，不是离线演示前置条件。商品真实页面增强仍必须使用用户有权调用的服务；DeepSeek 本身不提供真实商品销量、库存或排名。

## 6. 健康检查与停止

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/ecommerce/health
Invoke-WebRequest http://127.0.0.1:3000/ecommerce -UseBasicParsing
docker compose ps
docker compose down
```

不要使用 `docker compose down -v`，以免删除本地报告历史卷数据。

## 7. B5 验收清单

- [x] 独立 Mock Compose 不依赖 `.env` 或 API Key。
- [x] Docker backend 健康检查、frontend 依赖和端口固定。
- [x] Mock 单品类、批量品类、报告、证据、导出和回放路径可用。
- [x] Live/DeepSeek 入口保留，状态和失败边界可见。
- [x] 异常演示和降级说明固定。
- [x] 用户操作手册、产品方案和交接文档已更新。
