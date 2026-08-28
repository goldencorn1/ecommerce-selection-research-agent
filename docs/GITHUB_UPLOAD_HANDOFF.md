# GitHub 上传交接说明

## 当前状态

- 公开仓库：<https://github.com/goldencorn1/ecommerce-selection-research-agent>
- 账号：`goldencorn1`
- 默认分支：`main`
- 最终公开提交：`8a2831a`（完整 SHA：`8a2831aa967e5588a5ccbeb99c67740b65c7c679`）
- 仓库可见性：Public
- 项目截图已放入 `assets/demo/`
- 公开展示说明见 `docs/GITHUB_SHOWCASE.md`
- 脱敏后的评测摘要已放入 `artifacts/evaluation/ecommerce-eval-v1-summary.json`

## 验证结果

最终提交对应的 GitHub Actions 已全部通过：

- Test Cases Check：通过（1431 passed，4 skipped）
- Lint Check：通过
- Publish Containers：通过

本地验证也已完成：定向电商测试 9/9 通过，全量测试 1431 passed、4 skipped。

## 公开发布边界

没有上传 `.env`、`conf.yaml`、SQLite、本地浏览器历史、临时目录、真实 API Key，以及含个人信息的填好版 DOCX/PDF。未上传的大型评测明细和内部工作记录也不影响公开 Demo；保留了运行所需的代码、锁文件、截图、公开说明和脱敏评测摘要。

## 使用方式

在 GitHub 仓库首页查看 README、`assets/demo/` 和 `docs/GITHUB_SHOWCASE.md`。Windows 本地演示可双击仓库根目录的 `start_ecommerce_mock.bat`，然后打开 `http://127.0.0.1:3000/ecommerce`；Docker 方式见 `docker-compose.demo.yml` 和 `docs/ecommerce-deployment.md`。

项目默认使用 Mock/Demo 数据，不需要真实商业 API；有合法授权的用户可以在 Web 页面配置自己的模型、搜索和商品数据服务。

## 后续可选动作

Topics、`v1.0.0-demo` Release 和 GitHub Pages 展示页属于可选的仓库装修项，不影响当前代码上传、CI 验证和 Demo 使用。

