param(
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

function Get-DockerExecutable {
    $dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
    if ($null -ne $dockerCommand) {
        return $dockerCommand.Source
    }

    $bundledDocker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path -LiteralPath $bundledDocker) {
        return $bundledDocker
    }

    return $null
}

function Test-DockerReady {
    param([string]$Docker)

    if ([string]::IsNullOrWhiteSpace($Docker)) {
        return $false
    }

    & $Docker info *> $null
    return $LASTEXITCODE -eq 0
}

function Wait-DockerReady {
    param(
        [string]$Docker,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerReady -Docker $Docker) {
            return $true
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Invoke-LocalFallback {
    param([switch]$NoLaunch)

    Write-Host "Docker daemon unavailable. Starting local demo fallback..." -ForegroundColor Yellow
    $localScript = Join-Path $Root "scripts\start_ecommerce_web.ps1"
    if (-not (Test-Path -LiteralPath $localScript)) {
        throw "Local launcher not found: $localScript"
    }

    if ($NoLaunch) {
        & $localScript
    }
    else {
        & $localScript
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Local demo launcher failed with exit code $LASTEXITCODE."
    }

    Write-Host "Local demo launcher completed. The browser URL is shown above." -ForegroundColor Green
}

Write-Host "=== DeerFlow Ecommerce One-Click Launcher ===" -ForegroundColor Cyan
Write-Host "The launcher will prefer Docker and automatically fall back to local mode." -ForegroundColor DarkGray

$Docker = Get-DockerExecutable
if ($null -ne $Docker -and -not (Test-DockerReady -Docker $Docker)) {
    $desktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path -LiteralPath $desktop) {
        Write-Host "Starting Docker Desktop..." -ForegroundColor Yellow
        Start-Process -FilePath $desktop | Out-Null
        if (Wait-DockerReady -Docker $Docker -TimeoutSeconds 45) {
            Write-Host "Docker daemon is ready." -ForegroundColor DarkGreen
        }
    }
}

if ($null -ne $Docker -and (Test-DockerReady -Docker $Docker)) {
    Write-Host "Starting Docker Compose Mock demo..." -ForegroundColor Yellow
    $dockerScript = Join-Path $Root "scripts\start_ecommerce_mock.ps1"
    try {
        if ($NoLaunch) {
            & $dockerScript -NoLaunch
        }
        else {
            & $dockerScript
        }
        if ($LASTEXITCODE -eq 0) {
            exit 0
        }
        Write-Host "Docker launcher returned exit code $LASTEXITCODE. Switching to local mode." -ForegroundColor Yellow
    }
    catch {
        Write-Host "Docker startup failed: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "Switching to local mode." -ForegroundColor Yellow
    }
}
else {
    Write-Host "Docker CLI/daemon is unavailable. Using local mode." -ForegroundColor Yellow
}

Invoke-LocalFallback -NoLaunch:$NoLaunch
