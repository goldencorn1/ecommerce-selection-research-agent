# 电商选品研究 V1 Schema

状态：V1 基线草案（以当前代码实现为准）
适用范围：`src/ecommerce/models.py`、`src/ecommerce/orchestration.py`、`src/ecommerce_graph.py` 以及当前 Mock/搜索接口。
本文件定义 V1 核心输入/报告契约；A1/A2 的多智能体和私有知识能力作为可选运行扩展加入，不改变 `EcommerceResearchRequest` 与 `FinalReport` 的核心结构。

## 1. V1 契约边界

V1 分成三个层次：

1. **研究请求**：由 `EcommerceResearchRequest` 校验，是业务输入的稳定核心。
2. **结构化报告**：由 `FinalReport` 校验，是 Mock、搜索和 DeepSeek 润色路径共同使用的报告核心。
3. **运行信封**：由 `run_ecommerce_graph()` 生成，包含报告之外的搜索状态、模型状态、质量门禁、溯源、进度和 Markdown 等运行信息。

`EcommerceResearchRequest.model_config.extra = "forbid"`。因此，研究请求中的未知字段必须被拒绝，不能静默忽略。Graph 入口另外接受少量运行控制字段；这些字段会在进入 `EcommerceResearchRequest` 前被移出，不属于报告业务输入。

## 2. V1 输入 Schema

### 2.1 研究请求对象

规范类型：`src.ecommerce.models.EcommerceResearchRequest`。

| 字段 | 类型 | 默认值 | 约束 | 说明 |
|---|---|---:|---|---|
| `category` | `string` | `"便携榨汁杯"` | 长度 1–80 | 研究品类；空字符串不允许 |
| `target_market` | `string` | `"中国大陆电商"` | 长度 1–80 | 目标市场 |
| `target_customer` | `string` | `""` | 最大长度 120 | 目标客群；为空时在模型初始化阶段按品类画像补默认客群 |
| `price_min` | `number` | `99.0` | `>= 0` | 研究价格区间下限 |
| `price_max` | `number` | `299.0` | `>= 0` 且 `>= price_min` | 研究价格区间上限 |
| `top_n` | `integer` | `3` | 1–10 | 最多生成的推荐方向数 |
| `constraints` | `array[string]` | `[]` | 最多 10 项 | 研究约束；当前模型只限制数量，不限制每项字符串长度或具体枚举 |

最小 JSON 示例：

```json
{
  "category": "可折叠露营桌"
}
```

完整 JSON 示例：

```json
{
  "category": "可折叠露营桌",
  "target_market": "中国大陆电商",
  "target_customer": "周末短途露营的年轻家庭",
  "price_min": 199,
  "price_max": 599,
  "top_n": 3,
  "constraints": ["便携", "易收纳", "避免复杂安装"]
}
```

以下规则属于当前模型行为：

- `price_max < price_min` 会触发校验错误。
- `target_customer` 为空时，使用 `get_category_profile(category).audience` 补齐；这不是调用外部搜索得到的事实。
- `top_n` 控制推荐方向数量，但当前品类画像实际提供的方向数可能进一步限制最终数量。
- `constraints` 当前会被模型接受，但现有报告模型没有独立的约束回显字段；不能在 V1 输出中承诺每条约束都被单独证明或展示。

### 2.2 Graph 入口的运行控制字段

`run_ecommerce_graph()` 接受一个字典时，还会识别以下控制字段。它们不是 `EcommerceResearchRequest` 的业务字段，也不会写入 `ecommerce_request`：

| 字段 | 类型 | 默认值 | 作用 |
|---|---|---:|---|
| `search_enabled` | `boolean` | `false` | 为 `true` 时启用搜索适配器；为 `false` 时使用默认 Mock provider |
| `search_config` | `object` | `{}` | 搜索适配器及质量策略配置，见下表 |
| `model_config` | `object` | `{}` | DeepSeek 润色及商业核验文件配置，见下表 |
| `knowledge_config` | `object` | `{}` | 可选私有知识源、召回模式和 Rerank 配置，见下表 |
| `search_provider` | Python 对象 | 无 | 仅程序化调用时注入自定义 `SearchProvider`；不是 JSON/HTTP 公共字段 |

当前 Graph 读取的 `search_config` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `provider` | Python `SearchProvider` 对象 | 已注入时使用；否则创建 `TavilySearchProvider` |
| `endpoint` | `string` | 默认 `https://api.tavily.com/search` |
| `api_key_env` | `string` | 默认 `TAVILY_API_KEY` |
| `timeout` | `number` | 传给搜索适配器的超时时间 |
| `max_retries` | `integer` | 额外重试次数 |
| `retry_backoff` | `number` | 重试退避参数 |
| `max_results` | `integer` | 每个搜索查询的最大结果数，provider 层约束为 1–100 |
| `min_score` | `number` | 搜索结果最低分数，provider 层约束为 0–1 |
| `max_age_days` | `integer` 或 `null` | 有发布时间的结果的新鲜度过滤阈值 |
| `cache_ttl_seconds` | `number` | 搜索缓存 TTL；0 表示不启用 |
| `cache_max_entries` | `integer` | 缓存最大条目数 |
| `parallel_modules` | `boolean` | 是否并行预取模块搜索 |
| `max_parallel_searches` | `integer` | 并行搜索上限，provider 层约束为 1–4 |
| `source_domain_allowlist` | `array[string]` | 全局来源域名允许列表 |
| `source_domain_allowlist_by_module` | `object` | 按模块配置来源域名允许列表 |
| `source_policy` | `"annotate"` 或 `"filter"` | 标记来源或过滤来源；provider 层只接受这两个值 |

当前 Graph 读取的 `model_config` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `enabled` | `boolean` | 为 `true` 时启用 `DeepSeekReportEnhancer` 对结构化报告做语言润色 |
| `verification_file` | 路径字符串 | 读取商业核验 JSONL/JSON 文件，并参与商业门禁校验 |
| `input_cost_per_million` | `number` | 输入 token 成本配置；未提供时读取环境变量或默认为 0 |
| `output_cost_per_million` | `number` | 输出 token 成本配置；未提供时读取环境变量或默认为 0 |

`search_provider`、`search_config.provider` 和 `model_config` 中的路径/密钥配置属于本地编程或运行配置；V1 不把 API key、provider 实例或 `.env` 内容作为报告 schema 的一部分。

当前 Graph 读取的 `knowledge_config` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `path` / `source_file` | 路径字符串 | 支持 JSONL、CSV、Markdown 和 TXT 私有资料 |
| `retriever` | Python 对象 | 程序化调用时注入自定义 Retriever；不进入持久化 JSON |
| `retrieval_mode` | `keyword`、`vector`、`embedding` 或 `bge` | 默认关键词召回；向量模式使用无网络 Hash embedding，真实 BGE 通过适配器注入 |
| `rerank` | `boolean` | 向量模式下启用离线 Lexical Rerank；真实 BGE Reranker 通过适配器注入 |
| `dimensions` | `integer` | Hash embedding 维度，默认 128 |
| `top_k` | `integer` | 私有证据最大召回数，默认 3 |

私有知识命中只会作为 `Evidence(source_type="local")` 加入候选证据链，不自动变成商业核验事实；未命中或加载失败时保留原有 Mock/Live 研究结果。

## 3. V1 结构化报告输出 Schema

规范类型：`src.ecommerce.models.FinalReport`。Mock、搜索降级和 DeepSeek 润色都必须最终得到这个模型；`extra = "forbid"`。

### 3.1 顶层字段

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `request` | `EcommerceResearchRequest` | 必填 | 本次报告实际使用的规范化请求 |
| `executive_summary` | `string` | 必填 | 面向用户的结论摘要 |
| `recommendations` | `array[ProductRecommendation]` | `[]` | 推荐方向及验证卡片 |
| `trends` | `array[TrendSignal]` | `[]` | 市场趋势/需求信号 |
| `competitors` | `array[CompetitorInsight]` | `[]` | 竞品观察及价格锚点 |
| `customer_profiles` | `array[CustomerProfile]` | `[]` | 目标客群、需求、痛点和购买触发因素 |
| `opportunities_risks` | `array[OpportunityRisk]` | `[]` | 机会、风险、分数和缓解动作 |
| `evidence` | `array[Evidence]` | `[]` | 可追溯的结构化证据 |
| `warnings` | `array[string]` | `[]` | 模块失败、数据不足、来源质量或降级提示 |
| `decision_status` | `"validate_first"`、`"insufficient_evidence"`、`"ready_for_scale"` | `"validate_first"` | 报告决策状态；当前生成器实际使用前两个状态 |
| `decision_basis` | `string` | `""` | 决策状态的依据和边界 |
| `next_actions` | `array[string]` | `[]` | 下一步验证或补数动作 |

### 3.2 嵌套对象字段

#### `TrendSignal`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `name` | `string` | 信号名称 |
| `direction` | `"rising"`、`"stable"`、`"falling"` | 趋势方向 |
| `demand_score` | `number` | 0–100 |
| `growth_rate` | `number` | -1–10 |
| `rationale` | `string` | 解释 |
| `evidence_ids` | `array[string]` | 关联 `Evidence.evidence_id` |

#### `CompetitorInsight`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `name` | `string` | 竞品或竞品集合名称 |
| `price` | `number` | `>= 0`；不代表已核验售价 |
| `positioning` | `string` | 定位描述 |
| `price_source` | `string` | 当前实现使用 `explicit`、`request_midpoint`、`mock_fixture` 等值；V1 不扩展为枚举 |
| `strengths` | `array[string]` | 优势 |
| `weaknesses` | `array[string]` | 弱势 |
| `evidence_ids` | `array[string]` | 关联证据 |

#### `CustomerProfile`

| 字段 | 类型 | 说明 |
|---|---|---|
| `segment` | `string` | 客群描述 |
| `needs` | `array[string]` | 需求 |
| `pain_points` | `array[string]` | 痛点 |
| `buying_triggers` | `array[string]` | 购买触发因素 |
| `evidence_ids` | `array[string]` | 关联证据 |

#### `OpportunityRisk`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `opportunity` | `string` | 机会描述 |
| `rationale` | `string` | 机会判断依据 |
| `opportunity_score` | `number` | 0–100 |
| `risks` | `array[string]` | 风险项 |
| `risk_score` | `number` | 0–100 |
| `mitigations` | `array[string]` | 缓解动作 |
| `evidence_ids` | `array[string]` | 关联证据 |

#### `ProductRecommendation`

| 字段 | 类型 | 说明 |
|---|---|---|
| `product_name` | `string` | 候选产品方向名称 |
| `positioning` | `string` | 产品定位 |
| `target_customer` | `string` | 该方向适合的客群 |
| `price_range` | `string` | 展示用价格带字符串，如当前生成器产生的 `¥…-¥…` |
| `rationale` | `string` | 推荐理由 |
| `score` | `ProductScore` | 可解释评分 |
| `evidence_ids` | `array[string]` | 支撑该方向的证据 ID |
| `validation_action` | `string` | 建议验证动作 |
| `validation_threshold` | `string` | 成功阈值 |
| `validation_data_needed` | `array[string]` | 需要补齐的数据 |
| `validation_failure_action` | `string` | 未达标处理动作 |
| `price_basis` | `string` | 价格带形成依据及其限制 |
| `score_note` | `string` | 评分说明；方向修正不等于新增证据 |

#### `ProductScore`

字段为 `demand`、`competition`、`margin`、`differentiation`、`evidence_quality`、`total`，类型均为 0–100 的 `number`。这些是当前解释性评分，不是平台真实销量、成本或利润率。

#### `Evidence`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `evidence_id` | `string` | 非空，稳定关联键 |
| `source` | `string` | 非空；Mock 通常为 `mock://…`，搜索结果通常为原始 URL |
| `title` | `string` | 非空 |
| `summary` | `string` | 非空；搜索适配器主要使用结果摘要 |
| `confidence` | `number` | 0–1；搜索分数是检索置信度，不是事实真值概率 |
| `supports` | `array[string]` | 证据支持的模块/结论标签 |
| `retrieved_at` | `datetime` 或 `null` | 检索时间；Mock 证据通常为空 |
| `source_type` | `string` | 默认 `unknown`；搜索适配器可写 provider 名称，如 `tavily` |

## 4. 五大报告板块及字段映射

V1 将报告的分析内容固定为以下五个板块。当前模型没有单独的 `price_analysis`、`risk_analysis` 或 `validation_card` 类型，因此这些内容必须映射到现有字段，不新增同名虚拟字段。

| V1 板块 | 当前字段映射 | 板块应回答的问题 | 允许的证据关系 |
|---|---|---|---|
| 1. 市场趋势 | `trends[]`：`name`、`direction`、`demand_score`、`growth_rate`、`rationale`、`evidence_ids` | 需求信号是什么，方向如何，为什么这样判断 | 每个信号通过 `evidence_ids` 关联证据；无结果时保留空数组并产生 warning |
| 2. 竞争与价格 | `competitors[]` 全字段；`recommendations[].price_range`、`price_basis` | 竞品如何定位，价格锚点是什么，价格带如何形成 | `price_source=explicit` 仍只表示从搜索结果抽取到显式价格；`mock_fixture` 和 `request_midpoint` 只能作假设/占位 |
| 3. 目标客群与需求 | `customer_profiles[]` 全字段；`recommendations[].target_customer` | 谁会买，需求、痛点和触发因素是什么 | 客群结论应通过 `evidence_ids` 追溯；Mock 客群是代理数据 |
| 4. 机会、风险与进入边界 | `opportunities_risks[]` 全字段；`FinalReport.decision_basis` | 机会在哪里，风险多大，如何缓解，为什么不能越过当前决策边界 | 机会风险项通过 `evidence_ids` 关联；`decision_basis` 是边界说明，不是新证据 |
| 5. 推荐方向与验证动作 | `recommendations[]`、`ProductScore` 全字段、验证相关字段、`next_actions` | 优先验证哪个方向，评分如何解释，下一步需要什么数据 | 推荐的 `evidence_ids` 必须指向报告内证据；验证卡片不能替代真实商业核验 |

以下字段是五大分析板块的公共报告外壳，不单独计为第六个分析板块：

- `executive_summary`：汇总结论。
- `evidence[]`：跨板块证据池。
- `warnings[]`：质量与降级提示。
- `decision_status`、`decision_basis`：决策状态和边界。
- `next_actions[]`：跨推荐方向的行动清单。

## 5. 证据、降级和商业门禁边界

### 5.1 证据边界

- `Evidence` 是可追溯观察，不自动等于商业事实。
- Mock 证据的 `source` 以 `mock://` 开头，表示离线固定样本；不得在材料中称为真实平台数据。
- 搜索证据的 `source` 保留原始 URL，`source_type` 保留 provider 标签；搜索摘要、抽取价格和检索分数都只能支持候选假设。
- `confidence` 是当前 provider 的置信/检索分数，不是销量、转化率、利润率或事实真值概率。
- `retrieved_at` 缺失时，不能宣称证据时效已验证；搜索模块会在状态详情和 warning 中记录未提供发布时间的情况。
- `evidence_ids` 只建立引用关系，不保证引用内容已经通过人工商业核验。

### 5.2 研究降级边界

当前四个研究模块是：`market`、`competitor`、`customer`、`opportunity`。搜索 provider 失败时，`SearchBackedResearchProvider` 可以按模块回退到 `MockResearchProvider`，并记录：

- `ecommerce_search_status`：`success`、`partial`、`fallback` 或 `not_used`；
- `ecommerce_search_details[module].status`：模块级状态，通常为 `success` 或 `fallback`；
- `FinalReport.warnings`：面向用户的降级说明；
- `ecommerce_metrics.overall_status`：模型或搜索发生降级时为 `degraded`。

因此：

- `search_status=success` 只表示四个搜索模块接口路径均完成，不表示证据已经适合采购决策。
- `search_status=partial` 或 `fallback` 时，报告可以继续生成，但必须保留降级标记；不能把混合 Mock/搜索结果写成纯真实研究。
- `model_status` 取 `not_used`、`success`、`fallback`。DeepSeek 只对已生成结构化报告做可选语言润色；失败时保留结构化报告，不应改写为模型成功。
- `decision_status=validate_first` 是当前有推荐方向时的默认边界；`insufficient_evidence` 用于没有推荐方向的情况。当前生成器没有把报告自动升级为 `ready_for_scale`。

### 5.3 质量门禁与商业决策门禁

`ecommerce_metrics.quality_gates` 当前包含三个独立布尔值：

| 门禁 | 当前含义 |
|---|---|
| `interface_success` | 搜索详情存在、整体搜索状态为 `success`、且各模块状态均为 `success` |
| `evidence_usable` | 在 `interface_success` 基础上，各模块无质量 warning、无未知来源、存在中国大陆相关来源、时效为 `verified`，且竞品价格覆盖率达到 1.0 |
| `commercial_decision_ready` | 在 `evidence_usable` 基础上，商业核验记录校验 `complete=true` |

商业核验记录使用当前 `CommercialVerificationRecord` 模型，要求包含真实商品页、平台、售价、销量周期、单位成本、库存、合规状态、结论和 `evidence_ids` 等字段。核验还会检查推荐覆盖、报告指纹、时效、`pass` 结论、合规状态和证据关联。

V1 明确禁止以下推断：

- 不能从 Mock 价格推断真实成本或利润。
- 不能从搜索摘要推断真实销量、库存、转化率或退款率。
- 不能从 `ProductScore.total` 推断可直接采购。
- 不能因为接口成功或 `interface_success=true` 就打开商业决策门禁。
- 没有完整且通过校验的商业核验记录时，不得宣称 `commercial_decision_ready=true`。

## 6. Mock/Live 兼容规则

### 6.1 共同不变量

Mock、搜索 Live、搜索失败回退和可选 DeepSeek 路径必须共同遵守：

1. 输入最终都转换为 `EcommerceResearchRequest`。
2. 报告最终都通过 `FinalReport` 校验。
3. 五大板块使用同一组字段，不因 provider 改变字段名。
4. 推荐评分、证据 ID、价格来源和 warning 必须保留，不得被语言润色层静默覆盖。
5. 外部 provider 失败时可以降级，但必须在状态和 warning 中如实标记。

### 6.2 Mock 模式

- `run_mock_research()` 默认使用 `MockResearchProvider`，不访问网络或凭据。
- `run_ecommerce_graph()` 在 `search_enabled=false` 时走默认 Mock provider。
- Mock provider 对四个模块分别提供结构化结果和 `mock://ecommerce/fixtures` 证据。
- Mock 结果适合测试 schema、报告结构、前端和降级流程，不适合宣称真实市场或直接支持采购。
- `model_config.enabled=true` 时可以在 Mock 研究结果上追加 DeepSeek 润色；这不改变 Mock 证据的来源性质。

### 6.3 搜索 Live 模式

- `search_enabled=true` 时，Graph 使用注入的 `SearchProvider`，或创建 `TavilySearchProvider`。
- `SearchProvider` 的最小接口是：`search(query: str, *, max_results: int = 5) -> list[SearchResult]`。
- 可选的 `SearchProviderWithMetadata` 接口返回 `SearchResponse`，以便保留请求元数据。
- `SearchResult` 必须包含 `title`、`url`、`snippet`、`source`、0–1 的 `score`、带时区的 `retrieved_at`，可选带时区的 `published_at` 和非负 `price`。
- Live 搜索按四个模块分别查询；结果会先规范化 URL、去重、清洗、按分数/时效过滤，并生成 `Evidence`。
- Live 结果中没有明确价格时，竞品价格可能使用请求区间中点，`price_source` 为 `request_midpoint`；这不是显式价格证据。
- Live 搜索异常可以按模块回退 Mock；此时必须按降级规则处理整体状态。

### 6.4 报告回放

`run_ecommerce_report_snapshot()` 读取已保存的 `FinalReport`，校验报告指纹，并且不调用搜索或模型 API。回放输出保持 `ecommerce_report` 和指纹不变，运行指标的 `mode` 为 `snapshot`、外部请求数为 0。回放使用保存的搜索状态和可选商业核验文件重新计算门禁。

## 7. Graph 运行信封输出

`ecommerce_research_node()` 的正常输出除了 `ecommerce_report` 外，还包含以下当前实际字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `research_topic` | `string` | 报告品类 |
| `ecommerce_request` | JSON object | 规范化后的研究请求 |
| `ecommerce_report` | JSON object | `FinalReport` |
| `ecommerce_report_fingerprint` | `string` | 报告内容的 SHA-256 指纹 |
| `ecommerce_model_status` | `string` | `not_used`、`success`、`fallback` |
| `ecommerce_model_error_kind` | `string` 或 `null` | 模型失败的稳定错误分类 |
| `ecommerce_model_usage` | object | 模型 usage；Mock 通常为空 |
| `ecommerce_search_status` | `string` | 搜索总体状态 |
| `ecommerce_search_details` | object | 四个模块的查询、状态、清洗和来源质量详情 |
| `ecommerce_knowledge_status` | `string` | `success`、`no_hit`、`fallback` 或 `not_used` |
| `ecommerce_knowledge_details` | object | 私有知识查询、命中数和 top-k 等详情 |
| `ecommerce_agent_plan` | `array[string]` | A1 固定节点执行计划 |
| `ecommerce_agent_results` | object | A1 节点状态、输出、证据和 warning；可选观测字段 |
| `ecommerce_progress_events` | `array[ResearchProgressEvent]` | 请求、搜索、清洗、评分、报告和完成事件 |
| `ecommerce_metrics` | object | 延迟、token 估算/usage、成本状态、质量门禁等 |
| `ecommerce_verification_records` | array | 读取到的 `CommercialVerificationRecord` JSON |
| `ecommerce_verification_validation` | object | 商业核验验证结果 |
| `ecommerce_provenance` | array | 由报告证据转换得到的溯源记录 |
| `ecommerce_citation_validation` | object | 引用完整性检查结果 |
| `final_report` | `string` | Markdown 报告 |
| `observations` | `array[string]` | 执行摘要和 Markdown 报告 |
| `citations` | `array[object]` | 报告中的证据 JSON |
| `messages` | `array[object]` | DeerFlow 消息，当前包含 `role`、`content`、`name` |

`ecommerce_metrics` 当前至少可能包含 `mode`、`status`、`latency_ms`、`input_chars`、`output_chars`、估算 token、成本状态、`overall_status`、模型/搜索状态、缓存计数、`quality_level`、`quality_gates`、`report_quality_gates` 和 `verification_validation`。这些是运行观测字段，不应复制进 `FinalReport`。

回放接口保持相同的核心报告/指纹/门禁语义，但当前实现不重新产生普通研究阶段的 `ecommerce_progress_events`；消费者应按字段存在性兼容回放结果。

## 8. V1 回归不变量

后续 schema 回归测试应至少锁定以下行为：

1. 研究请求只接受本文件列出的 7 个业务字段；未知字段被拒绝。
2. 默认请求为 `便携榨汁杯`、`中国大陆电商`、价格 `99.0–299.0`、`top_n=3`、空约束。
3. `price_max < price_min` 被拒绝。
4. Mock、搜索成功和搜索失败回退都能产出可校验的 `FinalReport`。
5. `FinalReport` 顶层字段和嵌套字段与本文件一致，未知报告字段被拒绝。
6. 五大板块的证据引用只能使用报告 `evidence[].evidence_id` 作为关联键。
7. 搜索失败必须留下 `partial`/`fallback` 状态或对应 warning，不能伪装成纯 Live 成功。
8. Mock 证据必须保留 `mock://` 来源标记。
9. 报告指纹由规范化报告内容计算；同一报告回放指纹保持一致。
10. 没有完整商业核验记录时，`commercial_decision_ready` 不得为 `true`。

## 9. 版本演进规则

### V1 兼容原则

- V1 字段名、字段语义和枚举值视为稳定契约；下游 CLI、Web、报告导出和回放均以此为准。
- 新增字段必须先是可选字段并提供明确默认值；不得改变现有字段含义。
- 删除字段、重命名字段、改变类型、收紧现有约束或改变枚举语义，必须升级主版本（V2）。
- 增加新的 provider 不得复制一套新报告 schema；必须适配现有 `ResearchProvider` 和 `Evidence` 契约。
- 真实数据、Mock 数据、搜索候选证据和人工商业核验数据必须继续通过来源、状态和门禁区分，不得以字段复用掩盖来源差异。

### 允许的 V1.x 变化

- 增加可选运行指标或新的 `ecommerce_search_details` 诊断字段。
- 增加新的 `source_type` 字符串值，但不能改变已有值含义。
- 增加新的可选约束项或 provider 元数据。
- 为现有报告字段补充更严格的文档、回归测试和导出展示；不改变 JSON 结构语义。

### 需要 V2 的变化

- 将 `price_range: string` 改成结构化价格对象。
- 将 `price_source: string` 改成限制性枚举并拒绝当前已有值。
- 把五大板块拆成新的顶层对象并删除当前数组字段。
- 将商业核验、私有商品库或 RAG 证据直接并入 `FinalReport`，同时改变现有证据边界。
- 把 `ready_for_scale` 从保留枚举变成自动化决策结果，或改变商业门禁判定条件。
- 改变 Mock/Live 失败时的降级语义，或让模型润色层可以覆盖结构化分数、证据和风险。

每次版本变更都必须同步更新：本文件、schema 回归测试、CLI/API 适配、报告回放和现有 Mock/Live 兼容测试。
