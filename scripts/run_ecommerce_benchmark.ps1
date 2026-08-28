param(
    [string[]]$Category = @("可折叠露营桌", "便携榨汁杯", "桌面收纳盒"),
    [string]$OutputPath = "artifacts/ecommerce/search-benchmark.json",
    [switch]$Parallel
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "未找到项目虚拟环境：$pythonPath"
}

$outputAbsolute = if ([IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath
} else {
    Join-Path (Get-Location) $OutputPath
}
$outputDirectory = Split-Path -Parent $outputAbsolute
if ($outputDirectory) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
}

$arguments = @(
    "-m", "src.ecommerce.search.benchmark",
    "--search-preflight",
    "--categories", ($Category -join ","),
    "--output", $outputAbsolute,
    "--pretty"
)
if ($Parallel) {
    $arguments += "--search-parallel"
}

Push-Location $repoRoot
try {
    & $pythonPath @arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
