#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib.sh"

ROOT="$(project_root)"
VENV="$ROOT/.venv"

banner
cd "$ROOT"

if [[ ! -x "$VENV/bin/python" ]]; then
  err "Virtual environment missing. Run ./scripts/install.sh first."
  exit 1
fi

HOST="${BUDDY_HOST:-0.0.0.0}"
PORT="${BUDDY_PORT:-8080}"

step "Starting BuddyCore"
info "WebUI: http://127.0.0.1:${PORT}"
info "LAN:   http://<pi-ip>:${PORT}"

env BUDDY_HOST="$HOST" BUDDY_PORT="$PORT" "$VENV/bin/python" -m buddycore
