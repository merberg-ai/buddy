#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib.sh"

ROOT="$(project_root)"
SERVICE_NAME="${BUDDY_SERVICE_NAME:-buddycore}"
PY="$ROOT/.venv/bin/python"
STOPPED_SERVICE=0

restart_on_error() {
  local exit_code=$?
  if [[ "$STOPPED_SERVICE" -eq 1 ]]; then
    warn "Update failed after stopping ${SERVICE_NAME}; attempting to restart it"
    sudo systemctl start "$SERVICE_NAME" || true
  fi
  exit "$exit_code"
}
trap restart_on_error ERR

banner
step "Updating BuddyCore from git"
cd "$ROOT"

if ! command -v git >/dev/null 2>&1; then
  err "git is required for updates"
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  err "systemctl is required because this updater manages the BuddyCore service"
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  err "$ROOT is not a git repository"
  exit 1
fi

step "Checking local repository state"
if ! git diff --quiet || ! git diff --cached --quiet; then
  err "Tracked local changes are present. Commit, stash, or discard them before updating."
  git status --short
  exit 1
fi

if ! git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  err "Current branch has no upstream configured. Set one with: git branch --set-upstream-to origin/<branch>"
  exit 1
fi

UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}')"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
info "Current branch: ${CURRENT_BRANCH}"
info "Upstream: ${UPSTREAM}"

SERVICE_INSTALLED=0
if systemctl list-unit-files "${SERVICE_NAME}.service" --no-legend 2>/dev/null | awk '{print $1}' | grep -qx "${SERVICE_NAME}.service"; then
  SERVICE_INSTALLED=1
fi

if [[ "$SERVICE_INSTALLED" -eq 1 ]]; then
  step "Stopping ${SERVICE_NAME}"
  if systemctl is-active --quiet "$SERVICE_NAME"; then
    run sudo systemctl stop "$SERVICE_NAME"
    STOPPED_SERVICE=1
  else
    info "${SERVICE_NAME} is already stopped"
  fi
else
  warn "${SERVICE_NAME}.service is not installed; continuing with git update only"
fi

step "Fetching latest changes"
run git fetch --prune

step "Applying fast-forward update"
run git pull --ff-only

if [[ -x "$PY" ]]; then
  step "Refreshing Python dependencies"
  run "$PY" -m pip install -r requirements.txt

  step "Running compile sanity check"
  run "$PY" -m compileall -q buddycore plugins
else
  warn "Venv Python not found at $PY. Skipping dependency refresh and compile check."
fi

if [[ "$SERVICE_INSTALLED" -eq 1 ]]; then
  step "Starting ${SERVICE_NAME}"
  run sudo systemctl start "$SERVICE_NAME"
  STOPPED_SERVICE=0
  run sudo systemctl status "$SERVICE_NAME" --no-pager
fi

trap - ERR
ok "BuddyCore update complete"
