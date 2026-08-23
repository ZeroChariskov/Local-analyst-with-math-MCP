$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$envFile = Join-Path $root 'deployment\config.env'
if (-not (Test-Path -LiteralPath $envFile)) { throw "Missing $envFile" }
foreach ($line in Get-Content -LiteralPath $envFile) {
  if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
    [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2])
  }
}
$gatewayPort = [int]$env:TITAN_GATEWAY_PORT
New-NetFirewallRule `
  -DisplayName "Titan Local AI Gateway ($gatewayPort)" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort $gatewayPort `
  -RemoteAddress 100.64.0.0/10 `
  -Action Allow `
  -Profile Any `
  -ErrorAction SilentlyContinue
Write-Host 'Allowed TCP 8080 from the Tailscale IPv4 range.'
Write-Host 'llama-server should remain bound to 127.0.0.1:8081.'
