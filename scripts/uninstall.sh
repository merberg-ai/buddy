#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib.sh"

ROOT="$(project_root)"

banner
warn "This removes the systemd service. It does not delete your repo, config, database, or logs."
run "$ROOT/scripts/service-uninstall.sh" || true
ok "Uninstall helper finished"
info "To remove the venv manually: rm -rf .venv"
info "To remove runtime data manually: rm -rf data logs"
