param(
    [switch]$NoLaunch,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
$ComposeFile = Join-Path $Root "docker-compose.demo.yml"

$dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
$Docker = if ($null -ne $dockerCommand) {
    $dockerCommand.Source
} elseif (Test-Path -LiteralPath "C:\Program Files\Docker\Docker\resources\bin\docker.exe") {
    "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
} else {
    throw "Docker CLI not found. Please install Docker Desktop first."
}

function Test-DockerReady {
    & $Docker info *> $null
    return $LASTEXITCODE -eq 0
}

Write-Host "=== DeerFlow Ecommerce Offline Mock Demo ===" -ForegroundColor Cyan
if (-not (Test-DockerReady)) {
    $desktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path -LiteralPath $desktop) {
        Start-Process -FilePath $desktop | Out-Null
    }
    $ready = $false
    for ($i = 1; $i -le 60; $i++) {
        Start-Sleep -Seconds 2
        if (Test-DockerReady) {
            $ready = $true
            break
        }
        Write-Host ("Waiting for Docker daemon ({0}/60)..." -f $i) -ForegroundColor DarkGray
    }
    if (-not $ready) {
        throw "Docker daemon did not become ready within 120 seconds."
    }
}

$composeArgs = @("compose", "-f", $ComposeFile)
if (-not $SkipBuild) {
    & $Docker @composeArgs build
    if ($LASTEXITCODE -ne 0) { throw "Offline demo image build failed with exit code $LASTEXITCODE." }
}
& $Docker @composeArgs up -d
if ($LASTEXITCODE -ne 0) { throw "Offline demo compose startup failed with exit code $LASTEXITCODE." }

$healthy = $false
for ($i = 1; $i -le 60; $i++) {
    $status = (& $Docker inspect deer-flow-backend --format '{{.State.Health.Status}}' 2>$null | Select-Object -First 1).Trim()
    if ($status -eq "healthy") {
        $healthy = $true
        break
    }
    if ($status -eq "unhealthy") {
        & $Docker @composeArgs logs --tail=60 backend
        throw "Backend container is unhealthy."
    }
    Start-Sleep -Seconds 2
}
if (-not $healthy) {
    & $Docker @composeArgs ps
    throw "Backend did not become healthy within 120 seconds."
}

$page = Invoke-WebRequest -Uri "http://127.0.0.1:3000/ecommerce" -UseBasicParsing -TimeoutSec 10
if ($page.StatusCode -ne 200) { throw "Frontend returned HTTP $($page.StatusCode)." }
Write-Host "Mock demo ready: http://127.0.0.1:3000/ecommerce" -ForegroundColor Green
Write-Host "No API Key is required. Select Mock 演示 to run the offline path." -ForegroundColor DarkGreen
if (-not $NoLaunch) {
    Start-Process -FilePath "http://127.0.0.1:3000/ecommerce"
    Read-Host "Press Enter to close this window; containers will keep running"
}
