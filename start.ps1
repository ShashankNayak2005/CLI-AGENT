# =============================================================================
# CLI Agent AI — One-Click Development Launcher (Windows PowerShell)
# =============================================================================

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "           CLI AGENT AI - STARTING FULL PLATFORM          " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# Ensure virtual environment exists
$venvActivate = Join-Path $root ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    Write-Host "[ERROR] Python virtual environment not found at .venv" -ForegroundColor Red
    Write-Host "Please create it using: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

# 1. Launch FastAPI Backend in a new terminal window
Write-Host "[1/3] Launching FastAPI Backend (Port 8000)..." -ForegroundColor Yellow
$backendCommand = "cd '$root'; . '$venvActivate'; `$env:PYTHONPATH='backend'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
$backendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCommand -PassThru

# 2. Wait briefly and open browser
Start-Sleep -Seconds 3
Write-Host "[2/3] Opening browser at http://localhost:5173..." -ForegroundColor Yellow
Start-Process "http://localhost:5173"

# 3. Launch React Frontend in current terminal
Write-Host "[3/3] Launching React + Vite Frontend (Port 5173)..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the frontend." -ForegroundColor DarkGray
Write-Host ""

Set-Location (Join-Path $root "frontend")
try {
    npm run dev
} finally {
    # Cleanup backend process on frontend termination
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Write-Host "Stopping backend service..." -ForegroundColor DarkGray
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
