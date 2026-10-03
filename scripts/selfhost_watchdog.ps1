<#
.SYNOPSIS
  Keeps a self-hosted PolyGuard up: stops the PC sleeping and restarts the backend or the
  ngrok tunnel within about 30 seconds if either one dies.

.DESCRIPTION
  Run it once after start_polyguard.ps1 and leave its window open:
      .\scripts\selfhost_watchdog.ps1
  Close the window (or press Ctrl+C) to stop watching and let the PC sleep again.
  It cannot help if the PC is shut down or loses its internet connection; for always-on
  hosting use the Render setup described in DEPLOYMENT.md.

.PARAMETER IntervalSeconds
  How often to check (default 30).

.PARAMETER Domain
  Same as start_polyguard.ps1: an optional reserved ngrok domain.
#>
param(
    [int]$IntervalSeconds = 30,
    [string]$Domain = ""
)

$root = Split-Path -Parent $PSScriptRoot
$webapp = Join-Path $root "webapp"

# Ask Windows not to sleep while this window is open (released automatically when it closes).
Add-Type -Namespace Win32 -Name Power -MemberDefinition @'
[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);
'@
$ES_CONTINUOUS = 2147483648; $ES_SYSTEM_REQUIRED = 1
[void][Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)

function Test-Backend {
    try { return (Invoke-WebRequest -Uri "http://127.0.0.1:8765/api/health" -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200 }
    catch { return $false }
}

function Test-Tunnel {
    try { return (Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 5).tunnels.Count -gt 0 }
    catch { return $false }
}

function Write-Log($message, $color = "Gray") {
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $message) -ForegroundColor $color
}

Write-Log "Watching PolyGuard every $IntervalSeconds seconds. PC will stay awake while this window is open." "Cyan"
while ($true) {
    if (-not (Test-Backend)) {
        Write-Log "Backend is not answering - restarting it." "Yellow"
        Start-Process powershell -ArgumentList @("-NoExit", "-Command",
            "cd '$webapp'; python -m uvicorn main:app --host 127.0.0.1 --port 8765")
        for ($i = 0; $i -lt 30 -and -not (Test-Backend); $i++) { Start-Sleep -Seconds 2 }
        if (Test-Backend) { Write-Log "Backend is back." "Green" } else { Write-Log "Backend still down; will try again." "Red" }
    }
    if (-not (Test-Tunnel)) {
        Write-Log "Tunnel is down - restarting ngrok." "Yellow"
        $ngrokArgs = if ($Domain) { "http 8765 --url=$Domain" } else { "http 8765" }
        Start-Process powershell -ArgumentList @("-NoExit", "-Command", "ngrok $ngrokArgs")
        for ($i = 0; $i -lt 15 -and -not (Test-Tunnel); $i++) { Start-Sleep -Seconds 2 }
        if (Test-Tunnel) { Write-Log "Tunnel is back." "Green" } else { Write-Log "Tunnel still down; will try again." "Red" }
    }
    Start-Sleep -Seconds $IntervalSeconds
}
