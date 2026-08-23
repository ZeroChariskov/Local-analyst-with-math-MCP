#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT/deployment/config.quality.env"

for path in "$TITAN_LLAMA_SERVER" "$TITAN_MODEL" "$TITAN_MMPROJ" "$TITAN_MTP_MODEL"; do
  [[ -f "$path" ]] || { echo "Required file not found: $path" >&2; exit 1; }
done

ARGS=(-m "$TITAN_MODEL" --mmproj "$TITAN_MMPROJ" --host "$TITAN_UPSTREAM_HOST" --port "$TITAN_UPSTREAM_PORT" -ngl "$TITAN_GPU_LAYERS" -c "$TITAN_CONTEXT" -np "$TITAN_PARALLEL" -b "$TITAN_BATCH" -ub "$TITAN_UBATCH" --metrics)
[[ -n "${TITAN_FLASH_ATTN:-}" ]] && ARGS+=(--flash-attn "$TITAN_FLASH_ATTN")
[[ -n "${TITAN_CACHE_TYPE_K:-}" ]] && ARGS+=(-ctk "$TITAN_CACHE_TYPE_K")
[[ -n "${TITAN_CACHE_TYPE_V:-}" ]] && ARGS+=(-ctv "$TITAN_CACHE_TYPE_V")
[[ "${TITAN_JINJA:-}" == on ]] && ARGS+=(--jinja)
[[ -n "${TITAN_IMAGE_MIN_TOKENS:-}" ]] && ARGS+=(--image-min-tokens "$TITAN_IMAGE_MIN_TOKENS")
ARGS+=(--spec-type "$TITAN_SPEC_TYPE" --model-draft "$TITAN_MTP_MODEL" --spec-draft-n-max "$TITAN_SPEC_DRAFT_N_MAX")
ARGS+=(--rope-scaling "$TITAN_ROPE_SCALING" --rope-scale "$TITAN_ROPE_SCALE")

echo 'Starting QUALITY EXPERIMENT profile.'
exec "$TITAN_LLAMA_SERVER" "${ARGS[@]}"
