# D4 正式身份与多租户存储升级方案

更新时间：2026-08-17

## 1. D4 目标

D4 在不破坏匿名 Mock Demo 的前提下，补齐正式部署所需的身份 provider 选择、OIDC/JWKS JWT 校验、显式 `tenant_id` 存储迁移和 PostgreSQL RLS 迁移脚本。当前没有真实 OIDC/JWKS 服务或授权商品 API，因此本阶段完成可复现的生产化骨架、离线验收和接入说明，不宣称真实联调已经完成。

## 2. 身份 provider

默认保持 D3 HS256：

```env
ECOMMERCE_REQUIRE_BEARER_AUTH=true
ECOMMERCE_BEARER_PROVIDER=hs256
ECOMMERCE_JWT_HS256_SECRET=请使用随机高熵密钥
```

正式 OIDC/JWKS 模式：

```env
ECOMMERCE_REQUIRE_BEARER_AUTH=true
ECOMMERCE_BEARER_PROVIDER=oidc
ECOMMERCE_OIDC_ISSUER=https://issuer.example.com/
ECOMMERCE_OIDC_AUDIENCE=deer-flow-ecommerce
ECOMMERCE_OIDC_JWKS_URL=https://issuer.example.com/.well-known/jwks.json
ECOMMERCE_OIDC_ALGORITHMS=RS256
```

OIDC 模式要求：

- `Authorization: Bearer <token>`，不接受 URL 查询参数传递 token；
- 固定算法白名单，仅允许 `RS256` 或 `ES256`；
- 必须验证签名、`exp`、`iss`、`aud`、`sub`、`tenant_id`；
- JWKS 只从配置的 HTTPS 地址读取，loopback HTTP 仅用于本地测试；
- 请求中的 `X-Workspace-Id` 必须与已验证的 `tenant_id` 一致；
- OIDC 配置不完整或 JWKS/签名校验失败时拒绝请求，不回退到 HS256。

## 3. 显式租户字段

SQLite 本地存储现在自动迁移 `ecommerce_reports.tenant_id`，旧数据库会用已有 `owner_id` 回填；应用查询优先按 `tenant_id` 过滤，同时保留 `owner_id` 输出和调用参数作为兼容别名。这样既不破坏当前 Demo，也为 PostgreSQL 迁移提供明确字段。

正式数据库迁移脚本位于 `migrations/001_ecommerce_tenant_rls.sql`，包括：

1. 增加并回填 `tenant_id`；
2. 建立租户+时间组合索引；
3. 开启并强制 PostgreSQL Row-Level Security；
4. 使用事务级 `app.tenant_id` 作为 `USING/WITH CHECK` 条件。

应用必须由服务端在每个事务中设置已验证的租户上下文，不能使用未经认证的客户端 Header 直接设置。

## 4. 验收与当前边界

运行 D4 离线验收：

```powershell
.venv\Scripts\python.exe scripts/run_d4_acceptance.py
```

验收覆盖 OIDC 严格校验、租户 mismatch 拒绝、旧 SQLite 结构迁移、跨租户报告读取隔离、RLS 脚本关键语句和 Demo 配置默认兼容。

真实 OIDC 联调需要用户提供 issuer、audience、JWKS 地址和测试租户 token；真实跨品类评测仍需用户自有且合法的商品数据服务，D4 不代替这些外部条件。

## 5. D5 建议

下一阶段可在获得正式身份服务和 PostgreSQL 环境后，完成 OIDC callback/gateway 联调、数据库迁移演练、RLS 集成测试、审计事件 tenant/subject 关联和授权商品 API 的真实跨品类评测。
