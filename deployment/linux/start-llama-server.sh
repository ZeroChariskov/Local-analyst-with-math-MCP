#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT/deployment/config.env"
ARGS=(-m "$TITAN_MODEL" --mmproj "$TITAN_MMPROJ" --host "$TITAN_UPSTREAM_HOST" --port "$TITAN_UPSTREAM_PORT" -ngl "$TITAN_GPU_LAYERS" -c "$TITAN_CONTEXT" -np "$TITAN_PARALLEL" -b "$TITAN_BATCH" -ub "$TITAN_UBATCH" --metrics)
if [[ -n "${TITAN_FLASH_ATTN:-}" ]]; then ARGS+=(--flash-attn "$TITAN_FLASH_ATTN"); fi
if [[ -n "${TITAN_CACHE_TYPE_K:-}" ]]; then ARGS+=(-ctk "$TITAN_CACHE_TYPE_K"); fi
if [[ -n "${TITAN_CACHE_TYPE_V:-}" ]]; then ARGS+=(-ctv "$TITAN_CACHE_TYPE_V"); fi
if [[ "${TITAN_JINJA:-}" == "on" ]]; then ARGS+=(--jinja); fi
if [[ -n "${TITAN_IMAGE_MIN_TOKENS:-}" ]]; then ARGS+=(--image-min-tokens "$TITAN_IMAGE_MIN_TOKENS"); fi
if [[ -n "${TITAN_MTP_MODEL:-}" ]]; then
  [[ -n "${TITAN_SPEC_TYPE:-}" ]] && ARGS+=(--spec-type "$TITAN_SPEC_TYPE")
  ARGS+=(--model-draft "$TITAN_MTP_MODEL")
  [[ -n "${TITAN_SPEC_DRAFT_N_MAX:-}" ]] && ARGS+=(--spec-draft-n-max "$TITAN_SPEC_DRAFT_N_MAX")
fi
echo "Starting llama-server with GPU layers=$TITAN_GPU_LAYERS context=$TITAN_CONTEXT batch=$TITAN_BATCH ubatch=$TITAN_UBATCH"
exec "$TITAN_LLAMA_SERVER" "${ARGS[@]}"
