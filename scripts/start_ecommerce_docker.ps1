param(
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

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

Write-Host "=== DeerFlow Ecommerce Docker Launcher ===" -ForegroundColor Cyan

if (-not (Test-DockerReady)) {
    $desktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path -LiteralPath $desktop) {
        Write-Host "Starting Docker Desktop..." -ForegroundColor Yellow
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

Write-Host "Starting Docker Compose services..." -ForegroundColor Yellow
& $Docker compose up -d
if ($LASTEXITCODE -ne 0) {
    throw "docker compose up failed with exit code $LASTEXITCODE."
}

$healthy = $false
for ($i = 1; $i -le 60; $i++) {
    $status = (& $Docker inspect deer-flow-backend --format '{{.State.Health.Status}}' 2>$null | Select-Object -First 1).Trim()
    if ($status -eq "healthy") {
        $healthy = $true
        break
    }
    if ($status -eq "unhealthy") {
        & $Docker compose logs --tail=60 backend
        throw "Backend container is unhealthy."
    }
    Start-Sleep -Seconds 2
}

if (-not $healthy) {
    & $Docker compose ps
    throw "Backend did not become healthy within 120 seconds."
}

try {
    $page = Invoke-WebRequest -Uri "http://127.0.0.1:3000/ecommerce" -UseBasicParsing -TimeoutSec 10
    if ($page.StatusCode -ne 200) {
        throw "Frontend returned HTTP $($page.StatusCode)."
    }
}
catch {
    & $Docker compose ps
    throw "Frontend is not ready: $($_.Exception.Message)"
}

Write-Host "Frontend is ready: http://127.0.0.1:3000/ecommerce" -ForegroundColor Green
if (-not $NoLaunch) {
    Start-Process -FilePath "http://127.0.0.1:3000/ecommerce"
}

if (-not $NoLaunch) {
    Read-Host "Press Enter to close this window; containers will keep running"
}
