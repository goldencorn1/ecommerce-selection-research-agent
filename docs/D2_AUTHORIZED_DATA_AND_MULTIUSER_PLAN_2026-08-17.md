# D2 合法数据接入、真实评测与多用户隔离方案

更新时间：2026-08-17

## 1. D2 目标

D2 不承诺项目自动获得真实商业数据，而是完成“用户提供合法来源后，系统可以安全接入、评测、隔离和审计”的工程闭环。

本阶段覆盖：

1. 授权数据记录契约和只读校验 API；
2. 真实搜索质量评测计划与显式执行开关；
3. 工作区令牌、报告/知识/导入数据隔离和审计边界；
4. 不改变现有 Mock 快捷演示路径。

## 2. 合法数据接入契约

接口：`POST /api/ecommerce/authorized-data/validate`

数据源必须声明：

- `provider` 和 `source_kind`；
- `authorization_status`：只有 `verified` 才能进入下一步核验；
- 授权合同、服务条款或内部数据授权引用；
- 允许用途和所属工作区；
- 商品记录的 `record_id`、`source_id`、标题、抓取时间和可选价格/详情页 URL。

校验结果只会返回：

- 数据是否可进入“逐 SKU 商业核验”；
- 记录数量、价格覆盖、过期记录和缺少 URL 的数量；
- 错误、告警和下一步动作。

它不会调用外部平台，也不会把 `ready_for_verification` 改写成 `commercial_decision_ready`。

## 3. 真实搜索质量评测

默认执行：

```powershell
.venv\Scripts\python.exe scripts/run_d2_live_evaluation.py
```

默认只生成无网络评测计划。只有在配置了调用者自有、合法授权的搜索服务后，才显式执行：

```powershell
.venv\Scripts\python.exe scripts/run_d2_live_evaluation.py --execute --output artifacts/d2/live-search-evaluation.json
```

评测维度包括搜索成功率、接口成功率、证据可用率、商业决策就绪率、延迟、告警数量、模块级来源质量、时效和价格覆盖。真实运行产物必须脱敏保存，不得写入 API Key、Authorization Header 或完整私有 URL 参数。

## 4. 多用户与配置隔离

现有默认模式仍是 `anonymous_local`，通过 `X-Workspace-Id` 将本地历史、私有知识和导入快照分区。D2 新增可选签名令牌：

```env
ECOMMERCE_WORKSPACE_TOKEN_SECRET=请使用随机高熵密钥
ECOMMERCE_REQUIRE_WORKSPACE_TOKEN=true
ECOMMERCE_WORKSPACE_TOKEN_TTL=86400
```

开启后：

- 先调用 `/api/ecommerce/session` 获取当前工作区令牌；
- 对研究、历史、批量、知识上传和 Excel 导入等有状态接口同时发送 `X-Workspace-Id` 与 `X-Workspace-Token`；
- 缺失或篡改令牌时返回 401；
- 令牌过期后需要重新获取；
- BYOK 仍然只在当前请求内存在，不写入报告、历史或 manifest。

注意：该令牌是工作区完整性边界，不是完整身份认证。生产部署仍应在反向代理或 API 网关接入 OIDC/JWT，并由已验证的用户身份生成工作区 ID。

## 5. D2 验收标准

- Mock 研究和既有 Web 页面不受影响；
- 授权数据验证能区分 `verified`、`user_declared` 和 `blocked`；
- Reader 数据明确提示“页面内容增强，不等于商业事实”；
- 真实评测默认无网络，必须 `--execute` 才发起外部请求；
- 工作区令牌能阻断无令牌请求并允许合法令牌请求；
- 193+ 电商测试、ruff、Docker、HTTP、manifest 和密钥扫描通过。

## 6. D2 后续边界

D2 完成后仍不能声称系统已经具备全网真实商品数据、销量预测或生产级身份系统。下一阶段应根据实际授权数据决定是否推进：平台数据适配器、真实跨品类评测、OIDC/JWT 集成、多租户数据库和后台审计查询。
