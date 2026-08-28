# WPS CLI 配置记录

更新时间：2026-08-18

## 已完成

- 已安装 GitHub `jjchen17/wps-cli` 当前源码版本 `0.2.0`。
- 已安装 `pywin32`，当前 Python 为 64 位 Python 3.12。
- 已创建项目快捷封装：`tools/wps-cli.ps1`。
- 通过 `wps doctor --verbose` 完成环境诊断。

## 当前限制

本机 WPS 12.1.0.28043 可以正常运行并打开 DOCX，但当前安装目录没有注册以下 COM ProgID：

- `KWPS.Application`
- `KET.Application`
- `KWPP.Application`

同时未发现 `ksomgr.exe` 或 `ksomisc.exe`，因此 `wps-cli` 暂时无法自动驱动 WPS、导出 PDF 或通过 WPS 引擎读取分页信息。

这不会影响 DOCX 文件本身的打开和编辑。当前产品设计说明书已使用模板兼容的 DOCX 方式生成，可直接用 WPS 打开；最终分页建议在 WPS 中人工确认。

## 使用方式

在项目目录执行：

```powershell
.\tools\wps-cli.ps1 doctor --verbose
.\tools\wps-cli.ps1 writer info ".\docs\选品研判台_产品设计说明书_最终版.docx" --json
.\tools\wps-cli.ps1 writer export-pdf ".\docs\选品研判台_产品设计说明书_最终版.docx" --output ".\tmp\产品设计说明书.pdf" --json
```

当 WPS 安装了可用的 COM 组件后，上述命令即可用于真实 WPS 排版检查和 PDF 导出。
