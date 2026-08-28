# 电商选品 Web 部署说明

当前版本提供两种推荐运行方式：Windows 本地一键启动，以及 Docker Compose 部署。真实商业验证数据仍然是可选输入，系统可以先用 Mock 数据运行完整 Demo。

## Windows 本地运行

1. 复制 `.env.example` 为 `.env`，至少配置 `TAVILY_API_KEY`；如果使用 DeepSeek，再配置 `DEEPSEEK_API_KEY`。
2. 双击仓库根目录的 `start_ecommerce_web.bat`。
3. 启动器会优先尝试 Next.js 页面；如果 Windows 原生依赖不可用，会自动打开无 Node 依赖的 fallback 页面。
4. 默认访问地址为 `http://127.0.0.1:8000/ecommerce`，Next.js 页面地址为 `http://localhost:3000/ecommerce`。

## Docker Compose

在仓库根目录执行：

```powershell
Copy-Item .env.example .env
# 编辑 .env，填写 TAVILY_API_KEY / DEEPSEEK_API_KEY 等配置
docker compose up --build -d
```

访问：

- Web：`http://localhost:3000/ecommerce`
- API 健康检查：`http://localhost:8000/api/ecommerce/health`

停止服务：

```powershell
docker compose down
```

报告历史和 Excel 导入审计快照会持久化到宿主机的 `artifacts` 目录。不要把 `.env` 提交到 Git；生产环境建议把 `ALLOWED_ORIGINS` 改为实际 Web 域名，并关闭匿名工作区模式后接入正式身份系统。

## D2 工作区令牌模式

当前本地 Demo 默认使用 `anonymous_local`，工作区 ID 主要用于本地报告和私有知识分区。需要在同一服务上提供多个受控工作区时，可以先设置高熵密钥并打开签名令牌：

```env
ECOMMERCE_WORKSPACE_TOKEN_SECRET=请替换为随机高熵密钥
ECOMMERCE_REQUIRE_WORKSPACE_TOKEN=true
ECOMMERCE_WORKSPACE_TOKEN_TTL=86400
```

客户端先请求 `/api/ecommerce/session`，随后对研究、历史、批量、知识和 Excel 接口同时发送 `X-Workspace-Id` 与 `X-Workspace-Token`。该令牌只提供工作区完整性边界，不等于用户身份认证；正式多用户部署仍需由 OIDC/JWT 网关验证用户，再由服务端生成工作区 ID。

## D3 可选 Bearer JWT 与跨租户边界

D3 增加了严格的可选 Bearer JWT 适配层。Demo 默认关闭，保持匿名 Mock 兼容；受控环境可先使用 HS256 适配器：

```env
ECOMMERCE_REQUIRE_BEARER_AUTH=true
ECOMMERCE_JWT_HS256_SECRET=请替换为随机高熵密钥
ECOMMERCE_JWT_ISSUER=可选的签发方
ECOMMERCE_JWT_AUDIENCE=可选的受众
```

启用后，受保护接口必须携带 `Authorization: Bearer <token>`，令牌必须包含 `exp`、`sub`、`tenant_id`，且 `X-Workspace-Id` 必须与 `tenant_id` 完全一致。生产部署建议由 OIDC 网关负责 RS256/ES256 + JWKS 验证，应用只接收已验证的身份声明；当前 SQLite 的 `owner_id` 是 D3 的应用层边界，迁移 PostgreSQL 后还应增加显式 `tenant_id` 和 RLS。

跨品类评测默认只生成计划，不发起网络请求：

```powershell
.venv\Scripts\python.exe scripts/run_d3_cross_category_evaluation.py
```

只有在用户已配置自有且有授权的数据源后，才允许显式使用 `--execute`。

## D4 OIDC/JWKS 与 PostgreSQL

正式身份服务可在 D3 HS256 兼容模式之外选择 OIDC/JWKS：

```env
ECOMMERCE_REQUIRE_BEARER_AUTH=true
ECOMMERCE_BEARER_PROVIDER=oidc
ECOMMERCE_OIDC_ISSUER=https://issuer.example.com/
ECOMMERCE_OIDC_AUDIENCE=deer-flow-ecommerce
ECOMMERCE_OIDC_JWKS_URL=https://issuer.example.com/.well-known/jwks.json
ECOMMERCE_OIDC_ALGORITHMS=RS256
```

OIDC 配置不完整、签名错误、issuer/audience 不匹配或租户不一致时请求会被拒绝；不会自动回退到 HS256。SQLite 会自动迁移显式 `tenant_id`，PostgreSQL RLS 迁移脚本见 `migrations/001_ecommerce_tenant_rls.sql`。在没有真实身份服务时保持 `ECOMMERCE_BEARER_PROVIDER=hs256` 和匿名 Demo 默认值。

## D5 真实环境联调预检

D5 提供默认无网络预检：

```powershell
.venv\Scripts\python.exe scripts/run_d5_integration_preflight.py
```

无 OIDC/JWKS、PostgreSQL 或授权数据配置时显示 `blocked` 是预期的安全结果。只有在确认配置属于自己有权访问的环境后，才使用：

```powershell
.venv\Scripts\python.exe scripts/run_d5_integration_preflight.py --execute
```

预检通过后，再显式运行跨品类评测；所有结果仍需人工复核，不能视为销量预测或自动采购结论。

## 上云前检查

- 使用 HTTPS，并把 `NEXT_PUBLIC_API_URL` 设置为浏览器可访问的 API 公网地址。
- 只允许正式前端域名访问 CORS，不要继续使用 `*`。
- 为 `artifacts` 或替换为对象存储/数据库配置持久化卷。
- 为 Tavily、DeepSeek 和服务器增加预算、超时、重试及速率限制。
- 真实搜索结果仍是候选证据；正式采购前必须通过 Excel 或平台数据补齐售价、销量、成本、库存、转化率、退款率和合规状态。
