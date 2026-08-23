$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$envFile = Join-Path $root 'deployment\config.quality.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Missing $envFile. Copy config.quality.example.env to config.quality.env first."
}

foreach ($line in Get-Content -LiteralPath $envFile) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2])
    }
}

foreach ($path in @($env:TITAN_LLAMA_SERVER, $env:TITAN_MODEL, $env:TITAN_MMPROJ, $env:TITAN_MTP_MODEL)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Required file not found: $path" }
}

$args = [System.Collections.Generic.List[string]]::new()
foreach ($pair in @(
    @('-m', $env:TITAN_MODEL), @('--mmproj', $env:TITAN_MMPROJ),
    @('--host', $env:TITAN_UPSTREAM_HOST), @('--port', $env:TITAN_UPSTREAM_PORT),
    @('-ngl', $env:TITAN_GPU_LAYERS), @('-c', $env:TITAN_CONTEXT),
    @('-np', $env:TITAN_PARALLEL), @('-b', $env:TITAN_BATCH),
    @('-ub', $env:TITAN_UBATCH), @('--metrics')
)) {
    foreach ($value in $pair) { [void]$args.Add([string]$value) }
}

if ($env:TITAN_FLASH_ATTN) { [void]$args.Add('--flash-attn'); [void]$args.Add($env:TITAN_FLASH_ATTN) }
if ($env:TITAN_CACHE_TYPE_K) { [void]$args.Add('-ctk'); [void]$args.Add($env:TITAN_CACHE_TYPE_K) }
if ($env:TITAN_CACHE_TYPE_V) { [void]$args.Add('-ctv'); [void]$args.Add($env:TITAN_CACHE_TYPE_V) }
if ($env:TITAN_JINJA -eq 'on') { [void]$args.Add('--jinja') }
if ($env:TITAN_IMAGE_MIN_TOKENS) { [void]$args.Add('--image-min-tokens'); [void]$args.Add($env:TITAN_IMAGE_MIN_TOKENS) }

# These flags depend on the exact llama.cpp build and matching MTP file.
[void]$args.Add('--spec-type'); [void]$args.Add($env:TITAN_SPEC_TYPE)
[void]$args.Add('--model-draft'); [void]$args.Add($env:TITAN_MTP_MODEL)
[void]$args.Add('--spec-draft-n-max'); [void]$args.Add($env:TITAN_SPEC_DRAFT_N_MAX)

# These are the flags used by current llama.cpp builds for rope scaling.
[void]$args.Add('--rope-scaling'); [void]$args.Add($env:TITAN_ROPE_SCALING)
[void]$args.Add('--rope-scale'); [void]$args.Add($env:TITAN_ROPE_SCALE)

Write-Host 'Starting QUALITY EXPERIMENT profile.' -ForegroundColor Yellow
Write-Host "GPU layers=$($env:TITAN_GPU_LAYERS) context=$($env:TITAN_CONTEXT) KV=$($env:TITAN_CACHE_TYPE_K)/$($env:TITAN_CACHE_TYPE_V)"
Write-Host "Full command: $env:TITAN_LLAMA_SERVER $($args -join ' ')"
& $env:TITAN_LLAMA_SERVER @args
