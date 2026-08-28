@echo off
setlocal
set "ROOT=%~dp0"
title 电商选品研判台 - 一键启动

if exist "C:\Program Files\PowerShell\7\pwsh.exe" (
    "C:\Program Files\PowerShell\7\pwsh.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\start_ecommerce_one_click.ps1"
) else (
    powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\start_ecommerce_one_click.ps1"
)

if errorlevel 1 (
    echo.
    echo 启动失败，请查看上方错误信息。
    pause
)

endlocal
