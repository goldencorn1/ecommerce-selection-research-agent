param(
    [string]$OutputDir = "artifacts/ecommerce/demo",
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python virtual environment not found: $Python"
}

$categories = "可折叠露营桌,平板电脑,桌面收纳盒"
& $Python main.py --ecommerce-demo --ecommerce-demo-dir $OutputDir --ecommerce-demo-categories $categories
if ($LASTEXITCODE -ne 0) {
    throw "Offline bundle generation failed with exit code $LASTEXITCODE."
}

$index = Join-Path $Root "$OutputDir\index.html"
if (-not (Test-Path -LiteralPath $index)) {
    throw "Offline comparison index was not generated: $index"
}
Write-Host "Offline demo bundle ready: $index" -ForegroundColor Green
if (-not $NoLaunch) {
    try {
        Start-Process -FilePath "explorer.exe" -ArgumentList (Resolve-Path -LiteralPath $index) | Out-Null
    }
    catch {
        Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "start", "", $index) | Out-Null
    }
}
