# D5 真实环境联调与上线前验收方案

更新时间：2026-08-17

## 1. D5 目标

D5 把 D4 的生产化骨架接入真实环境前的流程固定下来：先做无网络预检，再由调用者明确授权探测 OIDC/JWKS、PostgreSQL 和用户授权数据，最后才运行跨品类 Live 评测。没有真实外部配置时，D5 仍可通过本地集成模拟和阻断式验收完成工程验证。

## 2. 默认预检

默认不联网、不读取外部服务，也不输出 DSN、Token 或 API Key：

```powershell
.venv\Scripts\python.exe scripts/run_d5_integration_preflight.py
```

预检检查三项：

1. `ECOMMERCE_REQUIRE_BEARER_AUTH=true`、`ECOMMERCE_BEARER_PROVIDER=oidc`、OIDC issuer/audience/JWKS/算法；
2. `ECOMMERCE_POSTGRES_DSN` 或 `DATABASE_URL`；
3. `ECOMMERCE_AUTHORIZED_DATA_FILE`，格式为 `{ "source": {...}, "records": [...] }`。

无配置时返回 `status=blocked` 是预期结果，不是系统错误；`commercial_decision_ready` 始终为 `false`。

## 3. 显式外部探测

只有在用户已确认配置均属于其有权访问的环境时，才执行：

```powershell
.venv\Scripts\python.exe scripts/run_d5_integration_preflight.py --execute --output artifacts/d5/integration-preflight.json
```

该模式只探测已配置的 JWKS URL、PostgreSQL 连接和授权数据文件。失败时只返回脱敏分类，不返回 URL 中的凭据、连接串、响应正文或第三方错误详情。预检通过后，才允许显式运行：

```powershell
.venv\Scripts\python.exe scripts/run_d3_cross_category_evaluation.py --execute --output artifacts/d5/cross-category-evaluation.json
```

该命令仍然只适用于调用者自有且合法授权的搜索服务。

## 4. 真实部署检查表

- OIDC issuer、audience、JWKS URL 和算法已由身份服务管理员确认；
- Token 的 `sub` 与 `tenant_id` 来源于已验证身份，不由浏览器自报；
- PostgreSQL 已执行 `migrations/001_ecommerce_tenant_rls.sql`，应用角色不是绕过 RLS 的表 owner；
- 每个请求/事务设置可信的 `app.tenant_id`；
- 授权数据源的使用范围、条款、更新时间和逐 SKU 详情页均可追溯；
- 真实评测结果经过人工抽检，不能解释为销量预测或自动采购建议；
- 日志不记录 Authorization、JWT、DSN、API Key 或完整商品敏感字段。

## 5. 当前完成边界

D5 已完成预检脚本、脱敏执行路径、本地 OIDC/SQLite 集成测试、RLS 关键语句验收和文档收口。由于当前没有真实 OIDC/JWKS、PostgreSQL 或授权商品 API，真实外部联调和 Live 评测保持待执行，不伪造成功结果。

## 6. 下一阶段

获得真实配置后进入 D6：正式 OIDC/JWKS 联调、PostgreSQL 迁移与 RLS 集成测试、授权商品 API 跨品类 Live 评测、审计日志和上线回滚演练。
