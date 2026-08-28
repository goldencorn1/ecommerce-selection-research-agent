# 电商选品 V1 评测规范

状态：P1 评测闭环已落地；Mock 基线可测，LLM/Live 在无显式配置时安全阻断

本文件定义电商选品 V1 的 50 条评测集格式、标注规则、自动指标、未来 LLM-as-Judge 维度和人工抽检规则。它约束评测方法，不把尚未测量的结果写成效果结论。

## 1. 评测目标

评测集用于回答以下问题：

1. 报告是否覆盖预期的五大板块；
2. 推荐方向是否与输入品类、客群和预算相关；
3. 推荐是否引用了报告内可追溯证据；
4. 搜索、模型或数据缺失时，系统是否如实降级；
5. 评分、价格带、风险和验证动作是否保持结构化；
6. Mock、Live、失败回退和商业核验状态是否被正确区分。

评测结果只代表在固定数据集、配置和运行环境下的结构性表现，不代表真实市场准确率、采购成功率或模型普遍能力。

## 2. 50 条评测集组成

V1 目标为 50 条 JSONL 样例，建议按以下结构分层：

| 类型 | 数量 | 目的 |
|---|---:|---|
| 正常 Mock 基线 | 20 | 检查报告结构、品类相关性和稳定输出 |
| 品类/预算/客群变化 | 10 | 检查输入变化是否传递到报告 |
| 搜索失败或模块降级 | 6 | 检查 fallback、warning 和状态字段 |
| 价格/证据质量不足 | 4 | 检查价格占位、来源质量和证据门禁 |
| 私有知识命中/未命中 | 4 | 为 A2 RAG 接入预留评测 |
| 模型失败或模型未启用 | 3 | 检查结构化报告保留和模型状态 |
| 商业核验不完整 | 3 | 检查 `commercial_decision_ready` 不被错误打开 |
| **合计** | **50** | |

当前数据文件已固定为 50 条；后续新增样例必须升级数据集版本或同步更新 A3 回归测试，不得静默改变样例数量。

## 3. JSONL 单条格式

每行一个 JSON 对象，必须使用 UTF-8 编码。A0 兼容当前 `src.evaluation.dataset.EvaluationCase` 的字段，同时为 A3 增加可选标注字段。

### 3.1 当前兼容字段

```json
{
  "id": "ec-001",
  "category": "可折叠露营桌",
  "target_customer": "周末露营的年轻家庭",
  "budget": {
    "minimum": 129,
    "maximum": 399
  },
  "expected_sections": [
    "executive_summary",
    "recommendations",
    "trends",
    "competitors",
    "customer_profiles",
    "opportunities_risks",
    "evidence"
  ],
  "minimum_evidence_count": 3,
  "tags": ["户外", "家庭", "便携"],
  "expected_degradation": []
}
```

这些字段继续由 `EvaluationCase` 校验：预算上限不得低于下限，`expected_degradation` 只能使用 `market`、`competitor`、`customer`、`opportunity`，样例 ID 必须唯一。

### 3.2 A3 扩展字段

以下扩展字段是 A3 标注规范，当前严格的 `EvaluationCase` 仍保持兼容核心字段；数据集目前使用场景 tags 和降级字段承载最小可执行标注：

```json
{
  "schema_version": "ecommerce-eval-v1",
  "case_type": "normal_mock",
  "expected_key_points": {
    "market_overview": ["需求信号", "季节性或增长依据"],
    "competitive_landscape": ["竞品定位", "竞争风险"],
    "price_band_analysis": ["价格锚点", "价格带边界"],
    "target_customer_match": ["目标人群", "购买痛点"],
    "risk_and_entry_barriers": ["进入风险", "验证动作"]
  },
  "required_evidence": {
    "minimum_count": 3,
    "required_supports": ["market", "competitor"]
  },
  "allowed_degradation": ["search_fallback"],
  "expected_decision_status": "validate_first",
  "private_knowledge": {
    "required": false,
    "document_ids": []
  },
  "judge_notes": "报告可以提出候选方向，但不能直接给出采购结论。"
}
```

扩展字段约束：

- `schema_version` 固定为 `ecommerce-eval-v1`；
- `case_type` 必须来自已登记的样例类型；
- 五大板块都必须有至少一个关键点；
- 关键点是可人工判断的内容，不写成未经测量的分数；
- `required_evidence.minimum_count` 不得小于 0；
- `expected_decision_status` 当前优先使用 `validate_first` 或 `insufficient_evidence`；
- 私有知识命中样例必须列出稳定的文档 ID，未命中样例必须明确允许回退；
- `judge_notes` 只作为标注说明，不作为模型输入事实。

## 4. 五大板块标注规范

评测集使用 `docs/ecommerce_schema.md` 中冻结的五大板块名称：

| 板块 | 当前报告映射 | 最小检查内容 |
|---|---|---|
| `market_overview` | `trends[]` | 需求/趋势信号、方向、理由和证据 |
| `competitive_landscape` | `competitors[]` | 竞品、定位、优势/弱势和证据 |
| `price_band_analysis` | 竞品价格、`price_range`、`price_basis` | 价格锚点、区间来源和占位说明 |
| `target_customer_match` | `customer_profiles[]`、推荐客群 | 人群、需求、痛点和购买触发因素 |
| `risk_and_entry_barriers` | `opportunities_risks[]`、`decision_basis` | 风险、缓解动作、进入边界和验证动作 |

`executive_summary`、`evidence`、`warnings`、`decision_status` 和 `next_actions` 是公共报告外壳，不重复计为五大板块。

## 5. 自动评测指标

当前已经实现并可离线测量的指标：

1. `report_completeness`：预期顶层字段是否存在且非空；
2. `category_relevance`：关键报告字段是否保留输入品类；
3. `evidence_coverage`：证据数量是否达到下限，推荐引用是否指向报告证据；
4. `score_validity`：推荐评分是否为 0—100 的有限数值；
5. `degradation_warning_quality`：预期降级是否对应明确 warning；
6. `structured_output_validity`：报告是否可序列化并满足当前顶层结构。

当前运行结果应同时记录：

- 总样例数和实际测量样例数；
- 成功率；
- 降级样例数和降级通过率；
- 平均延迟；
- 平均 warning 数；
- Mock 成本；
- 各指标平均分和通过率。

未来 A3/A4 增加：

- 关键点覆盖率；
- 证据命中率；
- 无关证据率；
- 平均和 P99 延迟；
- 输入/输出 Token；
- 单任务成本；
- 私有知识命中率；
- Rerank 前后排序变化。

## 6. LLM-as-Judge 规范

A3 的 Judge 只评价报告质量，不替代结构化门禁。建议使用 1—5 分或 1—10 分的固定量表，并保存原始输出、解析状态和版本信息。

电商专用维度：

- 市场概况完整性；
- 竞争格局拆解质量；
- 价格带合理性；
- 目标人群匹配度；
- 风险与进入壁垒识别；
- 证据引用质量；
- 商业边界诚实性；
- 下一步验证动作可执行性。

Judge 输出至少包含：

```json
{
  "case_id": "ec-001",
  "judge_version": "ecommerce-judge-v1",
  "scores": {
    "market_overview": 0,
    "competitive_landscape": 0,
    "price_band_analysis": 0,
    "target_customer_match": 0,
    "risk_and_entry_barriers": 0,
    "evidence_quality": 0,
    "commercial_boundary": 0,
    "next_actions": 0
  },
  "overall_score": 0,
  "strengths": [],
  "weaknesses": [],
  "needs_human_review": false
}
```

Judge 调用失败、输出无法解析或超出上下文时，必须保留自动指标结果，并将该样例标记为 `judge_failed`，不能把缺失的 Judge 分数当成 0 分或成功结果。

P1 已提供 `src.evaluation.p1_runner.run_p1_evaluation` 作为统一入口：

- `mode=mock, judge=deterministic`：运行固定 50 条离线基线；
- `judge=llm/hybrid`：必须显式注入已配置的 adapter；没有 adapter 时返回 `blocked`，不产生伪造分数；
- `mode=live`：当前评测入口不自行创建网络 provider，返回 `blocked`，要求调用方显式提供并审计真实 provider；
- 结果记录数据集 SHA-256、模式、Judge 版本、外部请求数和阻断原因。

## 7. 人工抽检规则

50 条样例至少抽检 20%，即 10 条。抽检样例应覆盖不同 `case_type`，并尽量包括至少 2 条降级样例和 2 条私有知识样例。

人工记录：

- case ID；
- 标注人和时间；
- 五大板块逐项评分；
- 证据是否真正支持结论；
- 降级是否诚实；
- Judge 与人工评分差异；
- 是否需要修改标注或 Judge 提示词。

抽检结果只能用于校准评测规则，不能从 10 条样例推断系统整体商业准确率。当前无独立评审人时，`scripts/complete_p1_human_review.py` 只允许生成明确标记为 `self_review` 的结构自检记录，不能写成外部人工结论。

## 8. Mock/Live 评测兼容

- Mock 评测默认不访问网络和模型 API，作为结构回归基线；
- Live 评测必须记录搜索 provider、查询配置、来源质量、发布时间覆盖和失败重试；
- 搜索失败回退样例必须保留 `partial` 或 `fallback` 状态和 warning；
- DeepSeek 润色失败不得改变结构化评分、价格、证据 ID、风险和门禁；
- 同一份报告回放不得重新调用搜索或模型 API；
- Mock、Live 和回放必须使用同一套 V1 报告字段，不允许按模式复制不同 schema。

## 9. 结果文件和版本

建议结果文件：

```text
artifacts/evaluation/
├─ ecommerce-eval-v1.json
├─ ecommerce-eval-v1-summary.json
├─ ecommerce-eval-v1-judge.jsonl
├─ ecommerce-eval-v1-human-review.jsonl
└─ ecommerce-eval-v1-config.json
```

结果必须保存：

- 数据集版本或文件哈希；
- 代码版本；
- 模型和 provider 配置；
- 是否使用 Mock、Live、RAG 或 Rerank；
- 运行时间；
- 原始指标和 warning；
- 失败样例及错误分类。

任何优化前后比较都必须使用相同数据集、相同输入、相同评分规则和可复现配置。未保存原始结果时，不得发布提升比例。
