# 搜索供应商替换与页面 BYOK 配置方案

版本：2026-08-17 方案分析版
范围：电商选品研究页的搜索链路，不改变当前 `.env` API 配置和基础演示路径

## 1. 结论先行

当前项目暂时保留现有 `SEARCH_API=tavily`、`TAVILY_API_KEY`、`DEEPSEEK_API_KEY` 和 `INFOQUEST_API_KEY` 配置。基础演示继续使用 Mock；Live 模式仍由本地 `.env` 决定，不在本阶段替换 Key 或改变默认行为。

后续页面可以支持用户自填 API，但应采用“前端临时输入、后端请求级使用”的 BYOK（Bring Your Own Key）模式：

- API Key 只提交给后端，不写入浏览器 `localStorage`、报告历史或 SQLite；
- 后端只在当前请求或短生命周期会话内使用，日志和预检结果只返回脱敏状态；
- 搜索结果统一转换为项目已有的 `SearchResult` / `SearchResponse`；
- 供应商失败时返回明确的 `provider_status` 和 `error_code`，不把失败伪装成真实搜索成功；
- SearXNG、自定义 Tavily-compatible endpoint 和官方搜索 API 可以共存，用户可切换。

## 2. 当前项目基线

### 已有能力

- `src/ecommerce/search/models.py` 已有统一的 `SearchProvider`、`SearchResult` 和 `SearchResponse` 协议；
- `src/ecommerce/search/adapters.py` 已有基于 HTTP JSON 的 Tavily-shaped 适配器，支持 endpoint、Bearer Key、超时、有限重试和脱敏元数据；
- `src/ecommerce_graph.py` 当前在搜索开启时直接创建 `TavilySearchProvider`；
- 项目已有全局 DeerFlow 搜索配置，支持 DuckDuckGo、Brave、Serper、SearX 等入口，但电商研究链路尚未把这些入口统一接入；
- 页面已有 Mock/Live 选择和搜索预检能力；
- 当前 InfoQuest Key 的真实预检返回 403，因此 InfoQuest 只应作为可选网页增强，不应作为搜索主链路。

### 当前演示约束

- 当前 `.env` 不改动；
- 当前默认演示仍建议选择 `Mock 演示`；
- Tavily 的真实调用只用于已有配置下的基本联调，不作为替换方案的验收依据；
- 页面内填写 API 的功能本文件只定义方案，尚未在当前版本开放。

## 3. GitHub 相似项目调研

以下项目用于提炼架构和交互模式，不直接复制代码。

| 项目 | 可借鉴做法 | 对本项目的价值 |
|---|---|---|
| [Open WebUI](https://github.com/open-webui/open-webui/blob/main/src/lib/components/admin/Settings/WebSearch.svelte) | 管理台按供应商动态展示 API Key、Base URL、Engine 等字段，并使用敏感输入控件 | 适合借鉴页面配置组件和供应商专属字段展示 |
| [AIRP](https://github.com/JCDC0/AIRP) | Settings Drawer 中配置 BYOK；支持 Brave、Tavily、Serper、SearXNG、DuckDuckGo；SearXNG 提供 URL 实时校验和结果数量控制 | 最接近“用户自己填 API 并即时验证”的交互模式 |
| [Argus](https://github.com/Khamel83/argus) | 多供应商 Broker、免费优先路由、健康门禁、预算门禁、缓存、RRF 去重和来源归因 | 适合借鉴生产级路由、成本控制和降级设计 |
| [TrailSearch / tavily-open](https://github.com/jianjungki/tavily-open) | 自托管 SearXNG，提供 Tavily-compatible `/tavily/search` 和 `/tavily/extract`，加本地索引、缓存和 Reader/HTTP/浏览器分层抽取 | 最适合作为“不改业务调用协议、替换底层搜索”的自托管路线参考 |
| [SearChat](https://github.com/yokingma/SearChat) | Docker 内置 SearXNG，同时支持 Tavily、Bing、Google、Exa、Bocha 等搜索源 | 适合参考 Docker 演示环境和多搜索源配置 |
| [one-search-mcp](https://github.com/yokingma/one-search-mcp) | 用 `SEARCH_PROVIDER`、`SEARCH_API_URL`、`SEARCH_API_KEY` 统一配置多种搜索服务 | 适合参考最小化环境变量和统一配置命名 |

### 调研后的取舍

- 页面交互优先参考 Open WebUI + AIRP：供应商选择后只显示相关字段，Key 使用敏感输入，SearXNG 需要 URL 和连通性检查；
- 后端路由优先参考 Argus：配置、健康、预算和执行分开判断；
- 自托管替代优先参考 TrailSearch/SearChat：用 SearXNG 或 Tavily-compatible 服务作为底层替换，不迫使上层业务理解每家 API 的返回格式；
- 不建议直接照搬复杂 Broker。当前项目是单机演示，先实现可测试的单供应商切换，再增加多供应商路由。

## 4. 推荐的替换路线

### 路线 A：自托管 SearXNG，作为低成本默认替代

结构：

```text
页面 -> 后端 SearchProvider -> SearXNG /search?format=json -> 统一 SearchResult
```

优点：无需把第三方 API Key 发给页面后端；可用 Docker 管理；成本可控；可以聚合多个搜索引擎。缺点是搜索质量、可用性和来源稳定性依赖 SearXNG 实例及其启用的引擎，且需要处理限流和 JSON 格式配置。

适合：本地演示、内网部署、希望降低 Tavily 依赖的场景。

### 路线 B：自定义 Tavily-compatible endpoint，作为最小改动替代

结构：

```text
页面/环境变量 -> endpoint + API Key -> HttpJsonSearchProvider -> 统一 SearchResult
```

只要替代服务接受类似以下请求，就可以复用当前 HTTP JSON 适配器：

```json
{
  "query": "可折叠露营桌 中国大陆电商 价格 竞品",
  "max_results": 5
}
```

优点是改动最小、容易做回归测试。缺点是供应商必须严格兼容请求认证和响应字段，不能解决商品价格、销量、排名等结构化数据问题。

适合：TrailSearch、自建网关、团队内部搜索代理或其他明确提供 Tavily-compatible API 的服务。

### 路线 C：原生多供应商适配器，作为正式产品方案

建议实现顺序：

1. SearXNG：实例 URL，无 Key 或可选访问 Key；
2. Brave Search：API Key，原生 JSON 响应；
3. Serper：API Key，原生 Google 搜索 JSON 响应；
4. 自定义 HTTP JSON：endpoint、Header 名称、认证前缀、响应映射；
5. 后续再考虑 Exa、Bocha 或目标电商平台的商品数据 API。

这条路线最适合长期维护，因为每个供应商的认证、限流、错误码和结果字段都可以单独测试，不需要强迫所有服务伪装成 Tavily。

## 5. 页面 BYOK 配置草案

第一版页面只需要以下字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `provider` | 枚举 | `tavily`、`searxng`、`brave`、`serper`、`custom_http_json` |
| `endpoint` | URL | 自定义服务或 SearXNG 地址；官方供应商可使用默认地址 |
| `api_key` | 密码输入 | 只提交给后端，不回显、不持久化 |
| `auth_header` | 枚举 | `Authorization`、`X-API-Key` 或自定义 Header |
| `auth_prefix` | 字符串 | 例如 `Bearer`；SearXNG 可为空 |
| `max_results` | 整数 | 建议 1—10 |
| `timeout_seconds` | 数值 | 建议 5—30 秒 |
| `test_query` | 字符串 | 预检时使用，默认使用当前品类 |

页面交互建议：

1. 选择供应商；
2. 动态显示必填字段；
3. 点击“测试连接”；
4. 只显示 `ready / unauthorized / timeout / invalid_response` 等脱敏结果；
5. 测试成功后才允许选择 Live 搜索；
6. 每次报告显示实际 `provider`、请求数、结果数和降级状态；
7. 页面刷新后不自动恢复 API Key。

## 6. 后端配置协议草案

建议将搜索配置统一为以下结构，兼容当前 `search_config`：

```json
{
  "enabled": true,
  "provider": "searxng",
  "endpoint": "http://searxng:8080/search",
  "api_key": null,
  "auth_header": "Authorization",
  "auth_prefix": "Bearer",
  "timeout": 15,
  "max_retries": 1,
  "max_results": 5,
  "cache_ttl_seconds": 900
}
```

安全要求：

- `api_key` 不写入 `ecommerce_request` 历史、报告 JSON、SQLite 或日志；
- 运行日志只记录供应商、状态码、耗时、结果数和错误类别；
- 页面输入的 Key 只允许服务端使用，禁止浏览器直接请求第三方搜索服务；
- 远程部署必须增加用户身份、请求级隔离、速率限制和 HTTPS；
- 自定义 endpoint 默认只允许 HTTPS；内网 SearXNG 需要显式放行内部地址，避免 SSRF；
- 自定义响应必须经过严格 schema 校验，不能把任意字段直接写入报告。

## 7. 推荐落地顺序

### B3：统一搜索供应商配置

- 将 `TavilySearchProvider` 改为由 provider factory 创建；
- 把 `TavilySearchProvider`、SearXNG、Brave、Serper 和 custom HTTP JSON 统一到同一协议；
- 增加 provider-specific preflight；
- 保留当前 Tavily 默认值和 Mock 回退；
- 增加配置 schema、错误码和 schema 回归测试。

### B4：页面 BYOK

- 增加搜索供应商设置面板；
- API Key 使用敏感输入；
- 增加测试连接、清除配置、当前供应商状态和结果数量显示；
- 页面请求只传当前请求使用的临时配置；
- 增加“不会保存 Key”的明确提示。

### B5：SearXNG / 自定义服务演示

- 增加可选 SearXNG Compose profile；
- 完成 SearXNG JSON 格式、超时、限流和健康检查；
- 用相同品类分别运行 Mock、Tavily、SearXNG 和 custom endpoint 回归；
- 对比结果数、来源重复率、延迟和失败原因。

### B6：商品数据 API 与网页设计

- 将商品价格、销量、排名等结构化数据与普通网页搜索分层；
- 页面设计最后统一美化，展示数据源、证据状态和降级原因；
- 不把普通搜索摘要误标为商品真实销量或排名。

## 8. 当前决策

当前不改动 `.env`，不更换 Tavily Key，也不把 InfoQuest 403 当作代码错误。短期继续用 Mock 完成基础演示；下一次正式开发建议优先实现：

> `SearXNG + custom Tavily-compatible endpoint + 页面临时 BYOK + provider preflight`

这套组合能覆盖免费本地演示、用户自带 API 和未来正式供应商接入，同时不会破坏当前报告 schema 和 Mock/Live 兼容接口。

## 9. 追加设计：自由模型配置与固定商品数据配置

用户可以自由选择模型供应商，但模型服务和商品数据服务必须分开配置。

### 9.1 模型服务：允许用户自由选择

页面可以提供以下模型配置：

| 字段 | 示例 | 说明 |
|---|---|---|
| `model_provider` | `deepseek`、`openai_compatible`、`ollama`、`mock` | 模型供应商或协议类型 |
| `model_base_url` | `https://api.deepseek.com` | OpenAI-compatible 服务地址 |
| `model_api_key` | 用户自己的 Key | 只在当前请求中使用 |
| `model_name` | `deepseek-chat` | 具体模型名称 |
| `temperature` | `0.2` | 报告生成参数 |
| `max_tokens` | `4096` | 输出上限 |

因此可以支持：

```text
搜索：SearXNG
报告模型：DeepSeek
商品数据：用户自己的商品数据 API
```

也可以支持：

```text
搜索：用户自定义搜索 API
报告模型：DeepSeek
商品数据：CSV/Excel 导入
```

但“全部使用 DeepSeek”只能表示分析、总结、报告润色等模型任务都使用 DeepSeek。DeepSeek 模型本身不会自动变成商品价格、销量、排名数据源；商品数据仍必须由搜索结果、用户 API 或用户导入数据提供。

### 9.2 商品数据服务：使用相对固定的适配器

商品数据不建议完全开放任意 API 响应。应当定义稳定的数据协议：

```json
{
  "product_id": "demo-001",
  "title": "示例商品",
  "url": "https://example.com/product/001",
  "price": 199.0,
  "currency": "CNY",
  "sales": null,
  "rank": null,
  "rating": null,
  "stock": null,
  "retrieved_at": "2026-08-17T00:00:00Z",
  "source": "user_configured_provider"
}
```

页面提供固定的商品数据来源类型：

- `none`：不读取真实商品数据；
- `csv_upload`：用户导入自己的商品数据；
- `infoquest_reader`：读取用户有权限访问的网页正文；
- `custom_product_api`：用户提供符合项目协议的商品 API；
- 后续按平台增加经过适配的商品 API，例如某个明确平台的价格/排名接口。

这样用户可以自行提供合法 API，但项目仍能验证字段、时间、来源和数据类型，避免把任意 JSON 或模型猜测直接当成真实商品事实。

### 9.3 页面布局建议

把配置分成三个独立卡片：

1. **AI 模型配置**：自由选择 DeepSeek 或其他 OpenAI-compatible 服务；
2. **搜索配置**：Tavily、SearXNG、Brave、Serper 或自定义搜索服务；
3. **商品数据配置**：选择固定适配器，并填写该适配器要求的 API 信息。

每张卡片都提供“测试连接”，报告顶部显示三个实际状态：

```text
模型：DeepSeek / success
搜索：SearXNG / success
商品数据：用户商品 API / unavailable
```

### 9.4 配置优先级

同一配置项按照以下优先级生效：

```text
本次页面请求配置 > 当前用户会话配置 > 本地 .env 默认配置 > Mock 默认值
```

当前项目继续使用 `.env` 作为默认配置，因此现有演示不会被破坏。页面 BYOK 实现后，用户只覆盖自己本次请求需要的配置。

### 9.5 必须保留的边界

- 模型 API Key、搜索 API Key 和商品 API Key 不能混用；
- 模型成功不代表商品数据成功；
- 商品 API 失败时，报告必须显示“无商品数据”或“使用用户导入数据”，不能自动补写销量和排名；
- 页面中输入的 Key 不写入报告历史、评测数据或日志；
- 对外部署时必须增加 HTTPS、用户身份隔离、限流和请求级密钥保护。
