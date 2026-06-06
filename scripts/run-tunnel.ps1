<#
.SYNOPSIS
  Host the persistent Microsoft Dev Tunnel that exposes the webhook receiver.

.DESCRIPTION
  GitHub cannot reach 127.0.0.1, so the workflow-service is exposed through a
  persistent, anonymous Dev Tunnel. This hosts the pre-created `living-adr`
  tunnel (port 8000). The public URL is stable across restarts:
      https://<tunnel-id>-8000.<cluster>.devtunnels.ms/webhooks/github

  Prerequisites (one-time):
      winget install Microsoft.devtunnel
      devtunnel user login
      devtunnel create living-adr --allow-anonymous
      devtunnel port create living-adr -p 8000 --protocol http

  Run scripts\run-workflow.ps1 (the receiver) in one terminal and this in
  another; both must stay running.

.EXAMPLE
  pwsh -File scripts\run-tunnel.ps1
#>
[CmdletBinding()]
param(
    [string]$TunnelId = 'living-adr'
)

$ErrorActionPreference = 'Stop'

$cmd = Get-Command devtunnel -ErrorAction SilentlyContinue
$devtunnel = if ($cmd) { $cmd.Source } else {
    Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\devtunnel.exe'
}
if (-not (Test-Path $devtunnel)) {
    throw "devtunnel not found. Install it: winget install Microsoft.devtunnel"
}

Write-Host "Hosting Dev Tunnel '$TunnelId' (keep this running)..."
& $devtunnel host $TunnelId
