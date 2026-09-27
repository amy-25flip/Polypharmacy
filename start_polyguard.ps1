<#
.SYNOPSIS
  Starts PolyGuard (backend + built frontend, single origin) and an ngrok
  tunnel, so the app is reachable at a public URL for as long as this PC
  and this script's two windows stay running.

.PARAMETER Domain
  Optional reserved ngrok static domain (e.g. yourname.ngrok-free.app).
  Without it, ngrok assigns a random URL that changes every restart.

.PARAMETER Rebuild
  Rebuild the frontend before starting. Use this after changing any
  frontend code - otherwise the script reuses the existing build.

.EXAMPLE
  .\start_polyguard.ps1
.EXAMPLE
  .\start_polyguard.ps1 -Domain yourname.ngrok-free.app
.EXAMPLE
  .\start_polyguard.ps1 -Rebuild
#>
param(
    [string]$Domain = "",
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$webapp = Join-Path $root "webapp"
$frontend = Join-Path $webapp "frontend"
$dist = Join-Path $frontend "dist"
$envFile = Join-Path $webapp ".env"

Write-Host "== PolyGuard self-host startup ==" -ForegroundColor Cyan

# --- Load secrets (e.g. GEMINI_API_KEY) from webapp\.env, if present. ---
# This file is gitignored - see webapp\.env.example for the format.
if (Test-Path $envFile) {
    Write-Host "Loading secrets from webapp\.env ..."
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$' -and $_ -notmatch '^\s*#') {
            $name = $matches[1]
            $value = $matches[2].Trim('"').Trim("'")
            if ($value) {
                [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
    }
    if ($env:GEMINI_API_KEY) {
        Write-Host "  GEMINI_API_KEY loaded - prescription scanning enabled." -ForegroundColor Green
    } else {
        Write-Host "  webapp\.env found but GEMINI_API_KEY is empty - scanning disabled." -ForegroundColor Yellow
    }
} else {
    Write-Host "  No webapp\.env found - prescription scanning will be disabled." -ForegroundColor Yellow
    Write-Host "  To enable it: copy webapp\.env.example to webapp\.env and add your key."
}

# --- Build the frontend if missing, or if -Rebuild was passed. ---
if ($Rebuild -or -not (Test-Path (Join-Path $dist "index.html"))) {
    Write-Host "Building frontend (this can take a minute)..." -ForegroundColor Cyan
    Push-Location $frontend
    npm run build
    Pop-Location
} else {
    Write-Host "Using existing frontend build at webapp\frontend\dist (pass -Rebuild to rebuild it)."
}

# --- Start the backend in its own window (serves the API and the built frontend together). ---
# main.py loads webapp\.env itself at startup, so the secret never needs to
# be embedded in this command line (where it would be visible to anything
# inspecting running process command lines on this machine).
Write-Host "Starting PolyGuard backend on http://127.0.0.1:8765 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$webapp'; python -m uvicorn main:app --host 127.0.0.1 --port 8765"
)

# --- Wait for the backend to come up. ---
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8765/api/health" -UseBasicParsing -TimeoutSec 3
        if ($resp.StatusCode -eq 200) { $healthy = $true; break }
    } catch {}
}
if (-not $healthy) {
    Write-Host "Backend did not come up in time - check the new backend window for errors." -ForegroundColor Red
    exit 1
}
Write-Host "Backend is up." -ForegroundColor Green

# --- Start ngrok in its own window. ---
$ngrokArgs = if ($Domain) { "http 8765 --url=$Domain" } else { "http 8765" }
Write-Host "Starting ngrok tunnel (ngrok $ngrokArgs) ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "ngrok $ngrokArgs"
)

# --- Wait for ngrok's local API and print the public URL. ---
$publicUrl = $null
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 2
    try {
        $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 3
        if ($tunnels.tunnels.Count -gt 0) {
            $publicUrl = $tunnels.tunnels[0].public_url
            break
        }
    } catch {}
}

Write-Host ""
if ($publicUrl) {
    Write-Host "PolyGuard is live at: $publicUrl" -ForegroundColor Green
    Write-Host "First-time visitors in a browser will see ngrok's one-time 'Visit Site' notice - normal on the free tier."
} else {
    Write-Host "Could not confirm the ngrok public URL - check the new ngrok window for errors." -ForegroundColor Red
}
Write-Host ""
Write-Host "Two new windows are now running the backend and the tunnel. Close either one to stop it; re-run this script to bring it back."
