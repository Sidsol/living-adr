<#
.SYNOPSIS
  Load .env and run the LivingADR workflow-service (webhook receiver + HITL UI).

.DESCRIPTION
  The deployables read configuration from process environment variables, not
  from .env directly. This helper loads C:\repos\living-adr\.env into the
  current process and starts `living-adr-workflow`, so you don't have to paste
  the env loader each time. Config + env are read once at startup — restart this
  script after editing .env or living-adr.config.yaml (there is no hot reload).

.EXAMPLE
  pwsh -File scripts\run-workflow.ps1
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$EnvFile
)

$ErrorActionPreference = 'Stop'
if (-not $EnvFile) { $EnvFile = Join-Path $RepoRoot '.env' }

if (-not (Test-Path $EnvFile)) {
    throw "Env file not found: $EnvFile (copy .env.example to .env and fill it in)"
}

Get-Content $EnvFile | Where-Object { $_ -match '^\s*[^#].*=' } | ForEach-Object {
    $key, $value = $_ -split '=', 2
    Set-Item "Env:$($key.Trim())" $value.Trim()
}

$bindHost = if ($env:LIVING_ADR_HOST) { $env:LIVING_ADR_HOST } else { '127.0.0.1' }
$bindPort = if ($env:LIVING_ADR_PORT) { $env:LIVING_ADR_PORT } else { '8000' }
Write-Host "Starting living-adr-workflow on ${bindHost}:${bindPort} ..."
$exe = Join-Path $RepoRoot '.venv\Scripts\living-adr-workflow.exe'
& $exe
