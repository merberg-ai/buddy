#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib.sh"

ROOT="$(project_root)"
USER_NAME="${SUDO_USER:-$USER}"
SERVICE_NAME="buddycore"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PY="$ROOT/.venv/bin/python"

banner
step "Installing BuddyCore systemd service"

if [[ ! -x "$PY" ]]; then
  err "Venv Python not found at $PY. Run ./scripts/install.sh first."
  exit 1
fi

TMP_SERVICE="$(mktemp)"
sed \
  -e "s|__BUDDY_ROOT__|$ROOT|g" \
  -e "s|__BUDDY_USER__|$USER_NAME|g" \
  "$ROOT/systemd/buddycore.service.template" > "$TMP_SERVICE"

run sudo cp "$TMP_SERVICE" "$SERVICE_FILE"
rm -f "$TMP_SERVICE"
run sudo systemctl daemon-reload
run sudo systemctl enable "$SERVICE_NAME"
run sudo systemctl restart "$SERVICE_NAME"
ok "Service installed and started"
info "Check status with: sudo systemctl status buddycore --no-pager"
info "View logs with: journalctl -u buddycore -f"
