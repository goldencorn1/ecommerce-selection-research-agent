# GitHub 展示说明

## 项目一句话

选品研判台是一个面向个人卖家和中小商家的电商研究工作台：通过可替换数据源、模型适配和 LangGraph 研究工作流，把一个品类问题整理成可追溯的摘要、证据、风险与行动报告。

## 推荐展示顺序

1. 先看报告总览，说明用户输入、研究状态和最终结论如何汇总。
2. 再看能力配置，说明默认 Mock/Demo 如何保证现场可运行，以及用户如何配置自有 API。
3. 进入 Agent 状态、证据与趋势区域，展示研究模块、来源追踪、趋势图和价格分布图。
4. 最后展示风险与行动，说明系统不会只给“推荐”，而是给出风险边界与可执行的下一步验证动作。

## 截图说明

| 文件 | 展示重点 |
| --- | --- |
| `assets/demo/01-report-overview.png` | 研究台主界面、推荐方向和研究进度 |
| `assets/demo/02-capability-config.png` | Excel 导入、历史回放和 50 条质量基线 |
| `assets/demo/03-evidence-trend.png` | 推荐方向得分趋势和价格分布 |
| `assets/demo/04-risk-action.png` | 风险提示、决策边界和验证行动 |
| `assets/demo/05-templates.png` | 四种 Web 页面模板与当前选择 |
| `assets/demo/06-api-config.png` | 用户自有 API、知识库和 BYOK 配置 |
| `assets/demo/07-agent-workflow.png` | Supervisor 到 Reviewer 的八节点工作流状态 |

截图来自本地 Demo 页面，仅用于展示交互界面，不代表真实商业数据。仓库中的 `DEMO_ONLY` 标记、运行手册和边界说明应与截图一起阅读。

## GitHub 首页建议

- README 首屏保留“30 秒了解项目”、一张主截图、快速启动和公开演示边界。
- 使用 Topics：`langgraph`、`deep-research`、`ecommerce`、`product-research`、`nextjs`、`fastapi`、`docker`。
- Release 使用 `v1.0.0-demo`，标题写明 Demo Final；发布说明引用最终产品需求、产品设计、演示手册和评测规范。
- 不上传 `.env`、本地数据库、浏览器历史、临时运行目录和含个人信息的填好版提交文档。

## 运行入口

Windows 用户可以双击仓库根目录的 `start_ecommerce_mock.bat`，然后打开 `http://127.0.0.1:3000/ecommerce`。Docker 方式见 `docker-compose.demo.yml` 和 `docs/ecommerce-deployment.md`。
