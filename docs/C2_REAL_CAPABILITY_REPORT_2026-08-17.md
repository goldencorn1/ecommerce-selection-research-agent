# C2 真实能力验证报告（2026-08-17）

## 结论

C2 真实能力验证已通过。首次在受限执行环境中出现 `ConnectError`，随后切换到已授权的提升网络执行路径后，Tavily 与 DeepSeek 均真实连通，单品类真实搜索和 DeepSeek 报告润色端到端成功。

根因是当前普通执行环境的外网路由受限，而不是 API Key 缺失或认证失败。提升网络路径下 Tavily 返回 HTTP 200，DeepSeek 返回 HTTP 200；项目原有的失败降级逻辑也已被验证。

## 本次验证范围

- 品类：可折叠露营桌
- 市场：中国大陆电商
- 搜索：Tavily，单请求预检 + 单品类四模块受控回归
- 模型：DeepSeek，最小连接预检；未重复调用报告润色
- 数据处理：只记录配置是否存在、错误类别、延迟、请求数、模块状态和 usage 是否可用；不保存 API Key、请求头或完整请求内容

## 结果

| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| 搜索配置 | 已配置 | Tavily Key 存在，但不代表网络可达 |
| 搜索预检 | 通过 | Tavily HTTP 200，5 条结果，约 8.6 秒 |
| 单品类真实搜索 | 通过 | 4/4 模块成功，4 次外部请求，每个模块 5 条结果 |
| 模型配置 | 已配置 | DeepSeek 模型为 `deepseek-v4-flash` |
| DeepSeek 预检 | 通过 | HTTP 200，146 tokens，约 3.7 秒 |
| 端到端运行 | 通过 | `search+deepseek`，整体约 31.7 秒 |
| 报告结构 | 保持有效 | 19 条证据、3 条推荐、9 条质量告警 |
| 单元测试 | 224/224 通过 | 电商与评测相关测试无失败 |
| 新增 C2 错误 | 0 | Ruff 仅发现仓库原有基线问题，未发现本阶段新增问题 |

## 质量判断

本次真实运行的接口状态为成功，质量等级为 `interface_success`。但 `evidence_usable=false`、`commercial_decision_ready=false`：来源发布时间和来源质量仍需人工核验，报告不能直接替代销量、利润、库存、排名或采购事实。

DeepSeek usage 已真实获取：输入 15,213、输出 2,868、合计 18,081 tokens。由于当前未配置供应商单价，成本状态为 `unpriced`；不能把 `actual_cost_usd=0` 解读为账单成本为零。

## 产物

- [C2 脱敏汇总 JSON](../artifacts/c2/c2-real-capability-summary.json)
- [单品类搜索回归 JSON](../artifacts/c2/c2-search-smoke.json)
- [真实端到端运行 JSON](../artifacts/c2/c2-real-e2e.json)
- [真实端到端脱敏摘要](../artifacts/c2/c2-real-e2e-summary.json)
- [当前交接文档](HANDOFF_CURRENT_2026-08-17.md)

## 下一步

1. 为 DeepSeek 配置输入/输出单价，再复跑一次成本字段核验。
2. 继续优化来源分级、发布时间和价格证据质量；当前真实报告仍不是商业决策结论。
3. 可以进入 C3，优先做质量治理、来源策略和演示数据边界强化。
