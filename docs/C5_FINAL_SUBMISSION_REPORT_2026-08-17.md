# C5 最终演示验收与提交报告（2026-08-17）

## 结论

C5 已完成最终演示路径、评分依据、阶段文档和提交包收口。最终包采用文件白名单复制，不包含 `.env`、真实 API Key、OAuth token 或个人授权配置。

## 最终演示路径

### 现场 Web 演示

1. 双击 `start_ecommerce_mock.bat`。
2. 打开 `http://127.0.0.1:3000/ecommerce`。
3. 选择 Mock 演示，输入“可折叠露营桌”。
4. 展示研究进度、三条推荐方向、评分组成、证据、来源质量、风险和验证动作。
5. 展示报告质量门禁，说明 Mock 不代表真实商业事实。
6. 下载 JSON、Markdown 或 HTML 报告。
7. 打开历史记录，展示回放和对比不会重复调用外部 API。

### 离线材料演示

运行 `start_ecommerce_offline_bundle.bat`，或执行：

```powershell
.\.venv\Scripts\python.exe main.py `
  --ecommerce-demo `
  --ecommerce-demo-dir artifacts/c4/demo `
  --ecommerce-demo-categories "可折叠露营桌,便携榨汁杯"
```

打开 `artifacts/c4/demo/index.html`，然后展示 C4 的 `DEMO_ONLY` 商业核验记录和 `blocked` 预检结果。

## 评分材料冻结

依据最新评分分析，建议答辩采用以下估算口径，并明确这是预测而非评委最终分数：

| 维度 | 估算 | 满分 |
| --- | ---: | ---: |
| 原创程度 | 23 | 30 |
| 用户体验 | 19 | 25 |
| 应用价值 | 20 | 25 |
| 性能表现 | 14 | 20 |
| 基础分 | **76** | **100** |
| 产品计划加分 | **15** | **20** |
| 合计 | **91** | **120** |

如果评审方将加分项折算到百分制，91/120 约等于 75.8%；答辩时应同时说明基础分与加分项，避免混淆分母。

主要得分依据：

- 证据、来源质量、价格、时效和风险被纳入同一研究链路。
- 支持 Mock、Live、DeepSeek、BYOK、批量、历史、导出和离线回放。
- 50 条 Mock 评测已实际运行，并保存自动指标和人工抽检队列。
- C2 已完成真实 Tavily + DeepSeek 端到端验证。
- C3/C4 已补齐质量审计和无真实商业数据演示闭环。

主要扣分边界：

- 当前没有真实销量、供应商成本、库存、转化率和 SKU 合规数据。
- 真实搜索证据仍可能存在来源分级不足和发布时间缺失。
- 真实成本需要使用者配置供应商当前单价。

## 验收结果

- 电商与评测回归：226 passed。
- C4 两品类 Demo：生成成功。
- `DEMO_ONLY` 核验预检：blocked，商业决策门禁保持关闭。
- C3 质量审计 JSON：校验通过。
- C5 提交包：由 `scripts/build_c5_submission.py` 生成，包含 SHA-256 清单。
- 密钥安全：提交包使用白名单，不复制 `.env` 或授权配置。

## 交付命令

```powershell
.\.venv\Scripts\python.exe scripts/build_c5_submission.py `
  --output-dir artifacts/c5/final_submission
```

提交目录：`artifacts/c5/final_submission/`

交接入口：`artifacts/c5/final_submission/README.md`
文件校验：`artifacts/c5/final_submission/manifest.json`

## 下一步

C5 已完成。后续可以进入维护/扩展阶段：真实商业数据接入、正式认证与多用户隔离、成本账单校准、云部署和更高质量的人工评测。它们不再是当前演示交付的前置条件。
