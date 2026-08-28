$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$WebRoot = Join-Path $Root "web"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$NextUrl = "http://localhost:3000/ecommerce"
$BackendPort = 8000
$FallbackUrl = "http://127.0.0.1:$BackendPort/ecommerce"

function Open-Url {
    param([string]$Url)

    try {
        Start-Process -FilePath "explorer.exe" -ArgumentList $Url | Out-Null
    }
    catch {
        Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "start", "", $Url) | Out-Null
    }
}

function Test-LocalPort {
    param([int]$Port)

    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        $connected = $task.Wait(500) -and $client.Connected
        $client.Dispose()
        return $connected
    }
    catch {
        return $false
    }
}

function Wait-LocalPort {
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-LocalPort -Port $Port) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Find-FreePort {
    param([int]$StartPort = 8001, [int]$EndPort = 8010)

    for ($port = $StartPort; $port -le $EndPort; $port++) {
        if (-not (Test-LocalPort -Port $port)) {
            return $port
        }
    }
    throw "No free backend port found in $StartPort-$EndPort."
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python virtual environment not found: $Python"
}

$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($null -eq $npm) {
    throw "npm not found. Install Node.js LTS from https://nodejs.org/"
}

Write-Host "=== DeerFlow Ecommerce Workspace Launcher ===" -ForegroundColor Cyan

if (Test-LocalPort -Port $BackendPort) {
    $currentApiIsReady = $false
    try {
        $sessionProbe = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/api/ecommerce/session" -UseBasicParsing -TimeoutSec 3
        $currentApiIsReady = $sessionProbe.StatusCode -eq 200
    }
    catch {
        $currentApiIsReady = $false
    }
    if ($currentApiIsReady) {
        Write-Host "Backend already running on http://127.0.0.1:$BackendPort. Reusing it." -ForegroundColor DarkGreen
    }
    else {
        $BackendPort = Find-FreePort
        $FallbackUrl = "http://127.0.0.1:$BackendPort/ecommerce"
        Write-Host "Port 8000 has an older backend. Starting current backend on $BackendPort." -ForegroundColor Yellow
        Start-Process `
            -FilePath $Python `
            -ArgumentList @("server.py", "--host", "127.0.0.1", "--port", "$BackendPort") `
            -WorkingDirectory $Root
    }
}
else {
    Write-Host "Starting backend API..." -ForegroundColor Yellow
    Start-Process `
        -FilePath $Python `
        -ArgumentList @("server.py", "--host", "127.0.0.1", "--port", "$BackendPort") `
        -WorkingDirectory $Root
}

if (-not (Wait-LocalPort -Port $BackendPort -TimeoutSeconds 45)) {
    throw "Backend did not listen on port $BackendPort within 45 seconds."
}

$nextCommand = Join-Path $WebRoot "node_modules\.bin\next.cmd"
if (-not (Test-Path -LiteralPath $nextCommand)) {
    Write-Host "Installing frontend dependencies with npm install..." -ForegroundColor Yellow
    Push-Location $WebRoot
    try {
        & $npm.Source install --no-audit --no-fund --prefer-offline
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed with exit code: $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

$nextUsable = $true
$node = Get-Command node.exe -ErrorAction SilentlyContinue
$parcelWatcher = Join-Path $WebRoot "node_modules\@parcel\watcher-win32-x64\watcher.node"
if ($null -ne $node -and (Test-Path -LiteralPath $parcelWatcher)) {
    & $node.Source -e "require('@parcel/watcher')" *> $null
    if ($LASTEXITCODE -ne 0) {
        $nextUsable = $false
    }
}

if (-not $nextUsable) {
    Write-Host "Next.js native watcher is not usable. Opening the dependency-free fallback UI." -ForegroundColor Yellow
    Write-Host "Fallback UI: $FallbackUrl" -ForegroundColor Green
    Open-Url -Url $FallbackUrl
    exit 0
}

if ($BackendPort -ne 8000) {
    Write-Host "Current backend is on $BackendPort, so the dependency-free fallback UI will be used." -ForegroundColor Yellow
    Write-Host "Fallback UI: $FallbackUrl" -ForegroundColor Green
    Open-Url -Url $FallbackUrl
    exit 0
}

if (Test-LocalPort -Port 3000) {
    Write-Host "Frontend already running on http://localhost:3000. Reusing it." -ForegroundColor DarkGreen
}
else {
    Write-Host "Starting frontend Web..." -ForegroundColor Yellow
    Start-Process `
        -FilePath "cmd.exe" `
        -ArgumentList @("/k", "npm run dev") `
        -WorkingDirectory $WebRoot
}

Write-Host "Waiting for frontend port 3000..." -ForegroundColor Yellow
if (-not (Wait-LocalPort -Port 3000 -TimeoutSeconds 45)) {
    Write-Host "Next.js frontend is unavailable. Opening the dependency-free fallback UI." -ForegroundColor Yellow
    Write-Host "Fallback UI: $FallbackUrl" -ForegroundColor Green
    Open-Url -Url $FallbackUrl
    exit 0
}

Write-Host "Startup complete. Opening: $NextUrl" -ForegroundColor Green
Open-Url -Url $NextUrl
