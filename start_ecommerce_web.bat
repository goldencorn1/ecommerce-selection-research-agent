@echo off
set "ROOT=%~dp0"
cd /d "%ROOT%"
if exist "C:\Program Files\PowerShell\7\pwsh.exe" goto run_pwsh7
pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\start_ecommerce_web.ps1"
goto done
:run_pwsh7
"C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\start_ecommerce_web.ps1"
:done
if errorlevel 1 (
    echo.
    echo Launcher failed. Please review the error above.
    pause
)
