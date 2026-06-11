#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib.sh"

SERVICE_NAME="buddycore"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

banner
step "Uninstalling BuddyCore systemd service"

if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
  run sudo systemctl stop "$SERVICE_NAME" || true
  run sudo systemctl disable "$SERVICE_NAME" || true
fi

if [[ -f "$SERVICE_FILE" ]]; then
  run sudo rm -f "$SERVICE_FILE"
fi

run sudo systemctl daemon-reload
ok "BuddyCore service removed"
