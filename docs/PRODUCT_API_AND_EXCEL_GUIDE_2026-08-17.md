# 用户商品 API 与 Excel 输入指南

## 目标

项目不内置真实商品数据，也不要求开发者持有平台授权。使用者可以在 Web 页面临时填写自己有权使用的商品 JSON API；如果没有 API，则直接上传 Excel/CSV 文件。两种输入都先进入“候选证据”层，不会自动打开商业决策门禁。

## 用户商品 API

入口：`/ecommerce` 页面“用户商品 API（可选）”。

页面提供“配置模板”和“启用本次商品 API”开关：

- `通用 JSON API`：GET + Bearer，适用于返回 `data[]` 的接口。
- `本地 Demo 商品 API`：无需 Key，连接项目内置的固定演示服务，适合现场演示完整链路。
- `POST items 接口`：POST JSON + `X-API-Key`，适用于返回 `items[]` 的接口。

选择模板只会填充表单，不会自动发起请求；勾选启用后再点击预检。未启用的配置不会参与本次研究。

填写内容：

- Endpoint：必须是 HTTPS；本地演示允许 `http://localhost` 或 `http://127.0.0.1`。
- 方法：GET 或 POST JSON。
- 认证：Bearer Token、自定义 Header 或无需认证。
- API Key：只在本次预检请求中使用，不写入 localStorage、历史报告或服务端配置，也不会出现在响应和日志中。
- 查询参数：GET 默认使用 `q`；POST 会发送 `{"query": "品类", "category": "品类"}`。
- 响应路径：默认 `data`，支持点号路径，例如 `data.items`；留空表示根节点。
- 字段映射：商品标题、价格、链接、SKU 支持点号路径。

最小返回示例：

```json
{
  "data": [
    {
      "id": "sku-001",
      "name": "折叠露营桌",
      "price": 199,
      "url": "https://shop.example.com/products/sku-001"
    }
  ]
}
```

操作顺序：

1. 填写 Endpoint、认证信息和字段映射。
2. 点击“预检并读取样品”。系统最多读取 50 条配置上限内的少量样品，默认展示 10 条。
3. 确认标题、价格、链接映射正确后点击“载入本次研究”。样品会转换为本次工作区的临时私有知识文件。
4. 生成报告。样品以候选私有证据参与检索，不代表销量、成本、库存、转化率或合规事实。

服务端接口：`POST /api/ecommerce/authorized-data/product-api/preflight`。

内置演示服务：`GET /api/ecommerce/demo/product-api?q=折叠桌`。该接口只返回固定的 `DEMO_ONLY` 样品，不代表真实商业商品数据，也不会访问外部平台。

安全边界：

- 禁止 URL 内嵌用户名、密码或 API Key。
- 不跟随重定向，不接受连接级敏感 Header。
- 阻止公网请求访问本机、内网、链路本地和保留地址；只为本地 Demo 放行明确的 localhost/127.0.0.1 HTTP。
- 返回体限制为 2 MB，响应只返回归一化字段和脱敏验证状态。
- `commercial_decision_ready` 永远为 `false`；若要开展商业决策，仍需用户合法授权、逐 SKU 核验和独立证据绑定。

## Excel/CSV 输入

页面“导入 Excel 数据”支持：`.xlsx`、`.xlsm`、`.xls`、`.csv`、`.tsv`，单文件上限 20 MB。

推荐列：

- `推荐方向` / `product_name`
- `商品名称`
- `销售平台`
- `商品链接`
- `售价`
- `销量`、`销量周期`
- `单位成本`
- `库存状态`
- `合规状态`
- `核验人`、`核验时间`
- `结论`

操作顺序：

1. 选择文件，先看列预览和必需列提示。
2. 系统自动匹配常见中文/英文列名；无法匹配时手动选择字段映射。
3. 先生成一份报告，再点击“校验当前映射”。
4. 校验通过后点击“确认导入当前报告”，系统写入本地审计快照。

Excel 导入同样不会把用户文件直接包装成商业事实。缺少详情页、价格、核验时间或授权说明时，报告会保留警告或阻断状态。

## 没有真实 API 时的演示路径

1. 双击项目快捷启动脚本，进入 `/ecommerce`。
2. 直接点击“一键体验 Mock”，生成离线报告。
3. 在“导入 Excel 数据”上传本地样例文件，完成预览和字段映射。
4. 选择“本地 Demo 商品 API”模板，勾选“启用”，点击预检并读取样品，再点击“载入本次研究”。
5. 生成报告，查看“摘要—证据—风险—行动”导航、推荐得分趋势图和价格分布图。
6. 最后展示报告中的候选证据、数据边界和“商业决策未就绪”提示。

## 开发者接口验证

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/ecommerce/test_product_api.py -q
.venv\Scripts\python.exe -m pytest tests/unit/ecommerce -q
```

真实 API 联调只能在使用者明确拥有合法授权和网络条件时执行；本项目测试使用 MockTransport，不需要真实商品 API Key。
