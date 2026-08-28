# B2 授权数据源接入说明

## 当前可用配置

项目当前识别以下真实能力：

- `TAVILY_API_KEY`：真实搜索，已完成 B1 预检并可用于 Live 研究；
- `DEEPSEEK_API_KEY`：真实报告增强模型，已完成 B1 预检并可调用；
- `INFOQUEST_API_KEY`：InfoQuest 页面读取凭据，已接入 B2 商品页增强流程。

方案文件提到的“价格/榜单 API”没有给出独立端点或服务名称，因此没有擅自把任何搜索摘要当成销量、库存、榜单或利润数据。

## InfoQuest 的作用

InfoQuest 在 B2 中是可选的授权商品页内容增强器，不是交易平台数据 API。选择 `infoquest` 后，系统会：

1. 先用 Tavily 获取候选页面；
2. 只对有限数量的竞品页面调用 InfoQuest；
3. 从返回页面文本中抽取显式价格，保留来源 URL 和采集时间；
4. 记录请求数、成功数、失败数和错误分类；
5. 失败时保留 Tavily 结果，并在报告中显示降级提示。

## 预检

```powershell
$body = @{
  provider = "data"
  data_source = "infoquest"
  url = "https://www.example.com"
  timeout = 20
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/ecommerce/preflight" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

本次真实预检返回 HTTP 403，错误分类为 `authorization_error`：当前 key 未被授权调用 InfoQuest Reader 服务。该结果已经被纳入 Live 研究的降级测试，不影响 Mock 或 Tavily-only 模式。

## 研究请求

单品类和批量请求都可以选择：

```json
{
  "mode": "live",
  "model": "deepseek",
  "data_source": "infoquest"
}
```

如果 InfoQuest 未授权，报告仍会完成，但 `search_details.competitor` 会记录：

- `data_status: "error"`
- `data_error_code: "authorization_error"`
- `data_success_count` / `data_failed_count`

这表示搜索链路成功、页面增强失败，不能解释为商品销量或库存已验证。
