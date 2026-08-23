$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$envFile = Join-Path $root 'deployment\config.env'
if (-not (Test-Path -LiteralPath $envFile)) { throw "Missing $envFile. Copy config.example.env to config.env first." }

foreach ($line in Get-Content -LiteralPath $envFile) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2])
    }
}

if (-not $env:TITAN_GPU_LAYERS) { $env:TITAN_GPU_LAYERS = '99999' }
if (-not $env:TITAN_CONTEXT) { $env:TITAN_CONTEXT = '16384' }
if (-not $env:TITAN_PARALLEL) { $env:TITAN_PARALLEL = '1' }
if (-not $env:TITAN_BATCH) { $env:TITAN_BATCH = '2048' }
if (-not $env:TITAN_UBATCH) { $env:TITAN_UBATCH = '512' }
if (-not $env:TITAN_FLASH_ATTN) { $env:TITAN_FLASH_ATTN = 'on' }
if (-not $env:TITAN_CACHE_TYPE_K) { $env:TITAN_CACHE_TYPE_K = 'q4_0' }
if (-not $env:TITAN_CACHE_TYPE_V) { $env:TITAN_CACHE_TYPE_V = 'q4_0' }
if (-not $env:TITAN_JINJA) { $env:TITAN_JINJA = 'on' }
if (-not $env:TITAN_IMAGE_MIN_TOKENS) { $env:TITAN_IMAGE_MIN_TOKENS = '1024' }

$llamaArgs = [System.Collections.Generic.List[string]]::new()
foreach ($pair in @(
    @('-m', $env:TITAN_MODEL), @('--mmproj', $env:TITAN_MMPROJ),
    @('--host', $env:TITAN_UPSTREAM_HOST), @('--port', $env:TITAN_UPSTREAM_PORT),
    @('-ngl', $env:TITAN_GPU_LAYERS), @('-c', $env:TITAN_CONTEXT),
    @('-np', $env:TITAN_PARALLEL), @('-b', $env:TITAN_BATCH),
    @('-ub', $env:TITAN_UBATCH), @('--metrics')
)) {
    foreach ($value in $pair) { if ($null -ne $value -and $value -ne '') { [void]$llamaArgs.Add([string]$value) } }
}
if ($env:TITAN_FLASH_ATTN) { [void]$llamaArgs.Add('--flash-attn'); [void]$llamaArgs.Add($env:TITAN_FLASH_ATTN) }
if ($env:TITAN_CACHE_TYPE_K) { [void]$llamaArgs.Add('-ctk'); [void]$llamaArgs.Add($env:TITAN_CACHE_TYPE_K) }
if ($env:TITAN_CACHE_TYPE_V) { [void]$llamaArgs.Add('-ctv'); [void]$llamaArgs.Add($env:TITAN_CACHE_TYPE_V) }
if ($env:TITAN_JINJA -eq 'on') { [void]$llamaArgs.Add('--jinja') }
if ($env:TITAN_IMAGE_MIN_TOKENS) { [void]$llamaArgs.Add('--image-min-tokens'); [void]$llamaArgs.Add($env:TITAN_IMAGE_MIN_TOKENS) }
if ($env:TITAN_MTP_MODEL) {
    if ($env:TITAN_SPEC_TYPE) { [void]$llamaArgs.Add('--spec-type'); [void]$llamaArgs.Add($env:TITAN_SPEC_TYPE) }
    [void]$llamaArgs.Add('--model-draft'); [void]$llamaArgs.Add($env:TITAN_MTP_MODEL)
    if ($env:TITAN_SPEC_DRAFT_N_MAX) { [void]$llamaArgs.Add('--spec-draft-n-max'); [void]$llamaArgs.Add($env:TITAN_SPEC_DRAFT_N_MAX) }
}

Write-Host "Starting llama-server on $($env:TITAN_UPSTREAM_HOST):$($env:TITAN_UPSTREAM_PORT)"
Write-Host "GPU layers=$($env:TITAN_GPU_LAYERS) context=$($env:TITAN_CONTEXT) batch=$($env:TITAN_BATCH) ubatch=$($env:TITAN_UBATCH)"
Write-Host "Full command: $env:TITAN_LLAMA_SERVER $($llamaArgs -join ' ')"
& $env:TITAN_LLAMA_SERVER @llamaArgs
