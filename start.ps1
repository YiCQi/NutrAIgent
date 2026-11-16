# Start NutrAIgent with one command.
#   .\start.ps1          build the frontend if needed, serve everything on http://127.0.0.1:8000, open the browser
#   .\start.ps1 -Dev     backend (8000) + Vite dev server with hot reload (5173) in this one window
#   .\start.ps1 -Port 9000 -NoBrowser
# Ctrl+C stops everything.
param([switch]$Dev, [int]$Port = 8000, [switch]$NoBrowser)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$be = Join-Path $root "backend"
$fe = Join-Path $root "frontend"
$py = Join-Path $be ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "First run: creating Python environment..."
    python -m venv (Join-Path $be ".venv")
    & $py -m pip install -q -e "$be[dev]"
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "Port $Port is already in use (NutrAIgent may already be running): http://127.0.0.1:$Port" -ForegroundColor Yellow
    if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$Port" }
    exit 0
}
if (-not (Test-Path (Join-Path $fe "node_modules"))) {
    Write-Host "First run: installing frontend packages..."
    Push-Location $fe; npm.cmd install; Pop-Location
}

$env:NUTRAIGENT_API = "http://127.0.0.1:$Port"
if ($Dev) {
    $url = "http://127.0.0.1:5173"
    $api = Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "app.main:app", "--port", $Port -WorkingDirectory $be -NoNewWindow -PassThru
    try {
        if (-not $NoBrowser) { Start-Job { Start-Sleep 3; Start-Process $using:url } | Out-Null }
        Push-Location $fe; npm.cmd run dev; Pop-Location
    } finally {
        if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force }
    }
    exit 0
}

# production-style: rebuild the frontend only when sources are newer than the last build
$index = Join-Path $fe "dist\index.html"
$srcNewest = Get-ChildItem (Join-Path $fe "src"), (Join-Path $fe "index.html"), (Join-Path $fe "package.json") -Recurse -File |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not (Test-Path $index) -or $srcNewest.LastWriteTime -gt (Get-Item $index).LastWriteTime) {
    Write-Host "Building frontend..."
    Push-Location $fe; npm.cmd run build; $code = $LASTEXITCODE; Pop-Location
    if ($code -ne 0) { throw "frontend build failed" }
}
$url = "http://127.0.0.1:$Port"
Write-Host "NutrAIgent: $url   (Ctrl+C to stop)" -ForegroundColor Green
if (-not $NoBrowser) { Start-Job { Start-Sleep 2; Start-Process $using:url } | Out-Null }
Push-Location $be
try { & $py -m uvicorn app.main:app --port $Port } finally { Pop-Location }
