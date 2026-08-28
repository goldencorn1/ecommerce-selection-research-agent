# GitHub 上传交接说明

## 当前状态

- 本地公开发布提交：`8b0523a`（`main`）
- 上游远程：`upstream` → `https://github.com/bytedance/deer-flow.git`
- 项目截图已放入 `assets/demo/`
- 公开展示说明见 `docs/GITHUB_SHOWCASE.md`
- `.env`、`conf.yaml`、SQLite、本地浏览器历史、临时目录和填好版个人提交文档未进入提交

## 唯一未完成项

当前机器没有 GitHub CLI 登录态，且设备登录接口被网络层阻断，因此无法代替用户完成账号认证、创建个人仓库和推送。项目代码与发布材料已经在本地提交并通过检查。

## 登录后自动上传

在项目根目录执行一次：

```powershell
gh auth login --hostname github.com --git-protocol https --web
```

完成登录后，继续执行以下命令：

```powershell
$repo = "ecommerce-selection-research-agent"
$owner = gh api user --jq .login
gh repo create "$owner/$repo" --public --description "可追溯、可验证的电商选品研究工作台" --source . --remote origin
git push -u origin main
gh repo edit "$owner/$repo" --add-topic langgraph --add-topic deep-research --add-topic ecommerce --add-topic product-research --add-topic nextjs --add-topic fastapi --add-topic docker
gh release create v1.0.0-demo --repo "$owner/$repo" --title "v1.0.0-demo · 选品研判台 Demo Final" --notes-file docs/FINAL_DEMO_RUNBOOK_2026-08-18.md
gh repo view "$owner/$repo" --web
```

## 上传后检查

```powershell
gh repo view "$owner/$repo" --json nameWithOwner,isPrivate,defaultBranchRef,url
gh run list --repo "$owner/$repo" --limit 5
git status --short --branch
```

公开仓库首页优先查看 README、`assets/demo/` 和 `docs/GITHUB_SHOWCASE.md`。不要把填好个人信息的 DOCX/PDF、真实 API Key 或本地数据库追加到仓库。
