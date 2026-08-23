#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT/deployment/config.env"

if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow from 100.64.0.0/10 to any port "$TITAN_GATEWAY_PORT" proto tcp
  echo "Allowed TCP $TITAN_GATEWAY_PORT from the Tailscale IPv4 range using ufw."
elif command -v firewall-cmd >/dev/null 2>&1; then
  sudo firewall-cmd --permanent --add-rich-rule="rule family=\"ipv4\" source address=\"100.64.0.0/10\" port port=\"$TITAN_GATEWAY_PORT\" protocol=\"tcp\" accept"
  sudo firewall-cmd --reload
  echo 'Allowed TCP 8080 from the Tailscale IPv4 range using firewalld.'
else
  echo 'No ufw or firewalld found. Configure TCP 8080 for Tailscale manually.' >&2
  exit 1
fi
