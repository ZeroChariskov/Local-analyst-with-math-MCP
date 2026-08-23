$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$llamaScript = Join-Path $PSScriptRoot 'start-llama-server.ps1'
$gatewayScript = Join-Path $PSScriptRoot 'start-gateway.ps1'

if (-not (Test-Path -LiteralPath $llamaScript)) { throw "Missing $llamaScript" }
if (-not (Test-Path -LiteralPath $gatewayScript)) { throw "Missing $gatewayScript" }

Write-Host 'Starting llama-server in a new window...'
Start-Process powershell.exe -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-File', $llamaScript) -WorkingDirectory $root
Start-Sleep -Seconds 3
Write-Host 'Starting Gateway in a new window...'
Start-Process powershell.exe -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-File', $gatewayScript) -WorkingDirectory $root
Write-Host 'Both startup windows were opened. Wait for model loaded and math-mcp-ready.'
