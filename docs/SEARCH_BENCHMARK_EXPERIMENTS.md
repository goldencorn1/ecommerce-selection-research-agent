# 搜索基准实验记录

该文件只记录运行条件和指标，不把单次实时搜索结果当成市场事实。

## 2026-08-13：串行 annotate 三品类基准

- 品类：可折叠露营桌、便携榨汁杯、桌面收纳盒
- 模式：真实 Tavily、annotate、预检开启、串行模块请求
- 参数：timeout 20 秒、max_results 3、额外重试 1 次、backoff 0.25 秒
- 结果：`search_success_rate=0.3333`、`interface_success_rate=0.3333`
- 平均延迟：约 64.8 秒
- 失败原因：1 次 `search_timeout`、1 次 `search_http_error`
- 共同证据问题：发布时间覆盖率为 0，来源未分级较多，证据门禁和商业门禁均未通过
- 解释边界：串行比并行更稳定，但仍不能视为生产级稳定性；该结果用于工程基线，不用于判断品类商业机会。

## 对照方法

将输出 JSON 保存后，使用：

```powershell
.venv\Scripts\python.exe -m src.ecommerce.search.benchmark `
  --compare-baseline artifacts/ecommerce/search-annotate.json `
  --compare-candidate artifacts/ecommerce/search-filter.json `
  --pretty
```

delta 定义为 candidate 减 baseline。延迟、告警和未分级来源率的正 delta 通常不是改进；大陆来源率和价格覆盖率的正 delta 才可能代表质量改善，但仍需人工查看原始页面。
