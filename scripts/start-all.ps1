<#
.SYNOPSIS
  Start the LivingADR webhook receiver and the public tunnel together.

.DESCRIPTION
  Convenience launcher that starts both long-running pieces:
    - scripts\run-workflow.ps1  (webhook receiver + HITL review UI; loads .env)
    - scripts\run-tunnel.ps1     (public Dev Tunnel to port 8000)

  By default each runs in its **own PowerShell window** so you see live logs and
  can Ctrl-C them independently. Use -Detached to run them hidden with output
  redirected to var\*.log (handy for unattended runs).

  The launcher is idempotent: it skips the receiver if port 8000 is already
  listening, and skips the tunnel if a devtunnel host is already running.

.PARAMETER Detached
  Run both hidden, logging to var\workflow.*.log and var\tunnel.*.log instead of
  opening windows.

.EXAMPLE
  pwsh -File scripts\start-all.ps1

.EXAMPLE
  pwsh -File scripts\start-all.ps1 -Detached
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [int]$Port = 8000,
    [switch]$Detached
)

$ErrorActionPreference = 'Stop'

# Prefer PowerShell 7 (pwsh); fall back to Windows PowerShell.
$cmd = Get-Command pwsh -ErrorAction SilentlyContinue
$pwsh = if ($cmd) { $cmd.Source } else { (Get-Command powershell).Source }

$workflowScript = Join-Path $RepoRoot 'scripts\run-workflow.ps1'
$tunnelScript = Join-Path $RepoRoot 'scripts\run-tunnel.ps1'
foreach ($s in @($workflowScript, $tunnelScript)) {
    if (-not (Test-Path $s)) { throw "Missing script: $s" }
}

function Start-Piece {
    param(
        [string]$Name,
        [string]$Script,
        [string]$LogBase
    )
    if ($Detached) {
        $logDir = Join-Path $RepoRoot 'var'
        New-Item -ItemType Directory -Force $logDir | Out-Null
        $out = Join-Path $logDir "$LogBase.out.log"
        $err = Join-Path $logDir "$LogBase.err.log"
        Start-Process -FilePath $pwsh `
            -ArgumentList '-NoProfile', '-File', $Script `
            -WorkingDirectory $RepoRoot `
            -RedirectStandardOutput $out -RedirectStandardError $err `
            -WindowStyle Hidden | Out-Null
        Write-Host "  started $Name (detached -> var\$LogBase.*.log)"
    }
    else {
        Start-Process -FilePath $pwsh `
            -ArgumentList '-NoExit', '-NoProfile', '-File', $Script `
            -WorkingDirectory $RepoRoot | Out-Null
        Write-Host "  started $Name (new window)"
    }
}

Write-Host "Starting LivingADR (receiver + tunnel)..."

$receiverUp = [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
if ($receiverUp) {
    Write-Host "  receiver already listening on port $Port - skipping"
}
else {
    Start-Piece -Name 'webhook receiver' -Script $workflowScript -LogBase 'workflow'
}

$tunnelUp = [bool](Get-Process devtunnel -ErrorAction SilentlyContinue)
if ($tunnelUp) {
    Write-Host "  devtunnel host already running - skipping"
}
else {
    Start-Piece -Name 'public tunnel' -Script $tunnelScript -LogBase 'tunnel'
}

# Best-effort readiness check.
Start-Sleep -Seconds 6
try {
    $health = (Invoke-WebRequest "http://127.0.0.1:$Port/healthz" -UseBasicParsing -TimeoutSec 5).Content
    Write-Host "Receiver healthz: $health"
}
catch {
    Write-Host "Receiver not responding yet on http://127.0.0.1:$Port/healthz (it may still be starting)."
}

Write-Host ""
Write-Host "Both pieces are starting. Reminders:"
Write-Host "  * Confirm the public tunnel origin (its window prints 'Connect via browser')."
Write-Host "  * If that origin changed, set the GitHub App Webhook URL to <origin>/webhooks/github."
Write-Host "  * Stop with Ctrl-C in each window, or: Stop-Process -Id <PID> -Force."
