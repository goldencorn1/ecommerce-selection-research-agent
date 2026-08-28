# D3 生产化扩展方案

更新时间：2026-08-17

## 1. D3 目标

D3 把 D2 的“可选边界能力”整理成生产化接入契约：授权数据适配器可发现、JWT 租户身份可严格校验、跨品类 Live 评测可重复运行，同时继续保留无 Key Mock 演示。

## 2. 授权数据适配器

接口：`GET /api/ecommerce/authorized-data/adapters`

当前 allowlist：

- `user_jsonl`：用户自有 JSONL/CSV；
- `infoquest_reader`：用户有权限的页面 Reader；
- `marketplace_api`：用户授权商品 API；
- `internal_catalog`：用户所属组织的内部商品库。

适配器注册表只公开 provider、来源类型、是否需要用户凭据、是否支持预检和声明边界，不公开 API Key。所有记录仍需经过 D2 的授权状态、时效、价格覆盖、详情页和逐 SKU 核验。

## 3. OIDC/JWT 认证边界

D3 增加严格 Bearer JWT 适配器，默认关闭。受控单服务部署可以配置：

```env
ECOMMERCE_REQUIRE_BEARER_AUTH=true
ECOMMERCE_JWT_HS256_SECRET=请使用高熵密钥
ECOMMERCE_JWT_ISSUER=https://issuer.example.com/
ECOMMERCE_JWT_AUDIENCE=deer-flow-ecommerce
```

JWT 必须：

- 通过 `Authorization: Bearer <token>` 传递，不放在 URL；
- 固定使用 HS256 校验，必须包含并验证 `exp`、`sub`、`tenant_id`；
- 可选校验 `iss` 和 `aud`，生产环境建议必须配置；
- 请求中的 `X-Workspace-Id` 必须与 JWT 的 `tenant_id` 一致；
- 认证失败返回 401，租户不匹配返回 403。

正式多用户部署建议由 OIDC 网关验证 RS256/ES256/JWKS，再把已验证的租户身份传给应用；本地代码中的 HS256 适配器只用于受控单服务场景，不是完整身份供应商。

## 4. 多租户数据隔离

当前 SQLite 报告表使用 `owner_id` 作为租户边界，报告、知识文件、批量任务和 Excel 导入均按工作区查询。D3 在 Bearer 模式下由服务端把 JWT `tenant_id` 与工作区绑定，避免只依赖浏览器自报的工作区 ID。

生产数据库迁移建议：

1. 将 `owner_id` 显式迁移为 `tenant_id`，建立组合索引；
2. PostgreSQL 使用 Row-Level Security 或每租户 schema；
3. 由网关用户身份生成 tenant context，禁止客户端覆盖；
4. 所有详情、下载、回放、比较和导入接口继续做对象级授权；
5. 审计事件记录 tenant、subject、trace_id 和结果，不记录 token 或 API Key。

## 5. 跨品类 Live 评测

默认 dry-run：

```powershell
.venv\Scripts\python.exe scripts/run_d3_cross_category_evaluation.py
```

具备合法授权的搜索服务后，显式执行：

```powershell
.venv\Scripts\python.exe scripts/run_d3_cross_category_evaluation.py --execute --output artifacts/d3/cross-category-evaluation.json
```

默认使用 5 个品类，并检查：搜索成功率至少 80%、证据可用率至少 80%、至少 3 个品类。评测通过只代表跨品类接口和证据质量达到阈值，不代表销量预测准确，也不会自动开放商业决策门禁。

## 6. D3 完成定义

- Mock Web、Docker 和现有 API 不受影响；
- 适配器注册表可读且不含凭据；
- JWT 缺失、过期、错误签名和租户不匹配均被拒绝；
- 跨品类评测默认不联网，显式执行才访问用户授权服务；
- 200+ 电商测试、D3 专项验收、Docker 重建、HTTP smoke test 和密钥扫描通过。
