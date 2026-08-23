$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$envFile = Join-Path $root 'deployment\config.env'
if (-not (Test-Path -LiteralPath $envFile)) { throw "Missing $envFile. Copy config.example.env to config.env first." }
$requirements = Join-Path $root 'gateway\requirements.txt'
$gatewayPackage = Join-Path $root 'gateway\titan_gateway\__main__.py'
if (-not (Test-Path -LiteralPath $requirements)) {
    throw "Gateway files are missing: $requirements. Copy the complete titan-local-ai project, including the gateway folder."
}
if (-not (Test-Path -LiteralPath $gatewayPackage)) {
    throw "Gateway Python package is missing: $gatewayPackage. Copy the complete titan-local-ai project, including gateway\titan_gateway."
}

foreach ($line in Get-Content -LiteralPath $envFile) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2])
    }
}
$env:TITAN_UPSTREAM_URL = "http://$($env:TITAN_UPSTREAM_HOST):$($env:TITAN_UPSTREAM_PORT)"
$env:TITAN_GATEWAY_HOST = $env:TITAN_GATEWAY_HOST
$env:TITAN_GATEWAY_PORT = $env:TITAN_GATEWAY_PORT
$env:PYTHONPATH = Join-Path $root 'gateway'
python -m venv (Join-Path $root '.venv')
if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python virtual environment.' }
& (Join-Path $root '.venv\Scripts\python.exe') -m pip install -r $requirements
if ($LASTEXITCODE -ne 0) { throw 'Could not install Gateway dependencies.' }
& (Join-Path $root '.venv\Scripts\python.exe') -m titan_gateway
