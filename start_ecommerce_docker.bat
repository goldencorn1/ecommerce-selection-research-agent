@echo off
set "ROOT=%~dp0"
if exist "C:\Program Files\PowerShell\7\pwsh.exe" (
    "C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\start_ecommerce_docker.ps1"
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\start_ecommerce_docker.ps1"
)
if errorlevel 1 (
    echo.
    echo Docker launcher failed. Please review the error above.
    pause
)
