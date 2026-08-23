#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT/deployment/config.env"
export TITAN_UPSTREAM_URL="http://${TITAN_UPSTREAM_HOST}:${TITAN_UPSTREAM_PORT}"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/gateway/requirements.txt"
export PYTHONPATH="$ROOT/gateway"
exec "$ROOT/.venv/bin/python" -m titan_gateway
