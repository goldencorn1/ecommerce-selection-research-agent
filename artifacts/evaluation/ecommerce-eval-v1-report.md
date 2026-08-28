# C1 电商选品 V1 Mock 评测报告

运行时间：2026-08-17T09:00:31.639140+00:00 至 2026-08-17T09:00:32.380323+00:00
数据集：`E:\gpt plus\agent project1\deer-flow\data\evaluation\ecommerce_cases.jsonl`
数据集 SHA-256：`d10092152689082e210a551dd3ddbb1487d45849516df22d6e8e3b97c7172087`
模式：Mock 离线；外部请求：0；模型 token：0；成本：0 USD

## 一、总体结果

| 指标 | 结果 |
|---|---:|
| 总样例数 | 50 |
| 实际测量样例数 | 50 |
| 成功率 | 100.00% |
| 降级样例数 | 8 |
| 降级通过率 | 100.00% |
| Judge 平均分 | 79.60/100 |
| 平均延迟 | 14.70 ms |
| P50 延迟 | 7.73 ms |
| P95 延迟 | 9.47 ms |
| P99 延迟 | 354.96 ms |
| 平均 warning 数 | 0.52 |

## 二、自动指标

| 指标 | 平均分 | 通过率 |
|---|---:|---:|
| category_relevance | 0.9700 | 98.00% |
| degradation_warning_quality | 1.0000 | 100.00% |
| evidence_coverage | 0.9753 | 96.00% |
| report_completeness | 0.9933 | 98.00% |
| score_validity | 1.0000 | 100.00% |
| structured_output_validity | 1.0000 | 100.00% |

## 三、Judge 维度

| 维度 | 平均分 |
|---|---:|
| commercial_boundary | 73.96 |
| competitor | 73.63 |
| customer | 94.00 |
| evidence_quality | 90.84 |
| market | 58.80 |
| price | 96.00 |
| risk | 70.50 |

## 四、场景覆盖

| 场景标签 | 数量 |
|---|---:|
| a3-boundary-budget | 3 |
| a3-commercial-verification-incomplete | 1 |
| a3-low-evidence | 3 |
| a3-module-degradation | 8 |
| a3-normal | 35 |
| a3-price-missing | 1 |
| a3-private-knowledge-hit | 1 |
| a3-private-knowledge-miss | 1 |
| a3-search-degradation | 8 |

## 五、人工抽检

已生成 10 条人工抽检队列：`ecommerce-eval-v1-human-review.jsonl`。当前仅生成待审核样本，不虚构人工分数；完成抽检后再填写 reviewer、scores、notes 和校准差异。

## 六、结论与边界

- 本次 50 条 Mock 结构回归全部完成，成功率和降级通过率均为 100%。
- 该结果证明固定输入、结构化报告和降级链路在 Mock 环境可重复运行。
- 该结果不代表真实搜索准确率、真实模型质量、商品销量、库存、利润或采购成功率。
- 下一步应使用用户具备合法权限的搜索 API 和模型 API 进行 C2 真实能力验证。
