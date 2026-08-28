# DeepSeek 接入指南

## 1. 创建 API Key

在 DeepSeek 开放平台创建 API Key，并准备账户余额。API Key 只放在本机环境变量或未提交的 `.env` 文件中，不要写入 `conf.yaml`、代码或 Git。

DeepSeek 使用 OpenAI-compatible Chat Completions API，官方地址为 `https://api.deepseek.com`。

## 2. 配置模型

在项目根目录创建 `conf.yaml`：

```powershell
Copy-Item conf.yaml.example conf.yaml
```

将 `BASIC_MODEL` 配置为：

```yaml
BASIC_MODEL:
  platform: deepseek
  base_url: https://api.deepseek.com
  model: deepseek-v4-flash
  max_retries: 3
```

建议把所有密钥放进 `.env`：

```dotenv
DEEPSEEK_API_KEY=你的真实密钥
```

本项目会自动加载 `.env`。也可以只在当前 PowerShell 会话中设置：

```powershell
$env:DEEPSEEK_API_KEY = "你的真实密钥"
```

如果不同角色要使用不同模型，可以使用角色级配置：

```powershell
$env:BASIC_MODEL__MODEL = "deepseek-v4-flash"
$env:REASONING_MODEL__MODEL = "deepseek-v4-pro"
$env:REASONING_MODEL__API_KEY = $env:DEEPSEEK_API_KEY
$env:REASONING_MODEL__BASE_URL = "https://api.deepseek.com"
```

角色级变量优先于 `DEEPSEEK_*` 全局变量。

## 3. 先验证模型配置

不需要真实调用即可检查模型实例是否能创建：

```powershell
.venv\Scripts\python.exe -c "from src.llms.llm import get_llm_by_type; print(type(get_llm_by_type('basic')).__name__)"
```

配置正确时，输出应为 `ChatDeepSeek`。这个命令只创建客户端，不代表已经完成一次 API 调用。

## 4. 运行电商 MVP

默认 Mock 模式不会产生模型费用：

```powershell
.venv\Scripts\python.exe -m src.ecommerce --category "可折叠露营桌"
```

使用 DeepSeek 润色已经由 Mock/搜索流程产生的结构化报告：

```powershell
.venv\Scripts\python.exe -m src.ecommerce --model deepseek --category "可折叠露营桌"
```

这条路径只允许 DeepSeek 改写摘要、定位和理由；评分、价格、证据、风险和引用仍由结构化流程保留。模型调用失败时会保留原报告并记录 warning。

## 5. 在 LangGraph 电商节点中启用

```python
from ecommerce_graph import run_ecommerce_graph

state = run_ecommerce_graph({
    "category": "可折叠露营桌",
    "model_config": {"enabled": True},
})
```

如果同时开启真实搜索：

```python
state = run_ecommerce_graph({
    "category": "可折叠露营桌",
    "search_enabled": True,
    "search_config": {"api_key_env": "TAVILY_API_KEY"},
    "model_config": {"enabled": True},
})
```

这样搜索证据来自授权搜索 provider，报告语言由 DeepSeek 处理；搜索 API 和模型 API 的密钥分别管理。

## 6. 费用与安全

- `deepseek-v4-flash` 适合作为 basic 模型，`deepseek-v4-pro` 只在确实需要更强推理时使用。

## B1 能力预检

电商 Web 页面提供两个不自动触发外部请求的诊断接口：

```text
GET  /api/ecommerce/capabilities
POST /api/ecommerce/preflight
```

`capabilities` 只返回 Mock、Tavily 和 DeepSeek 的配置状态，不返回任何密钥；“已配置”不等于“已连通”。需要实际验证时调用：

```json
{
  "provider": "all",
  "model": "deepseek",
  "query": "可折叠露营桌 中国大陆电商 竞品 价格 用户需求"
}
```

预检会返回搜索和模型的成功/失败状态、稳定错误分类、耗时及可用的 token usage。模型失败时不会暴露上游原始异常，也不会改变 Mock/结构化报告回退路径。
- 真实成本以 DeepSeek 控制台和响应中的 usage 为准，不要把本地字符估算当作账单。
- 首次接入建议设置 `max_retries: 3`、限制研究步数，并先跑单个品类。
- 不要把 `.env`、真实 `conf.yaml` 或 API Key 提交到 Git。
- 不要把未经核验的模型改写文本当成新证据；本项目的 evidence、score、risk 仍由结构化流程保留。
