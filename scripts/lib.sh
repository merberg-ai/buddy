#!/usr/bin/env bash
set -Eeuo pipefail

BOLD="\033[1m"
DIM="\033[2m"
RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
BLUE="\033[34m"
MAGENTA="\033[35m"
CYAN="\033[36m"
RESET="\033[0m"

banner() {
  echo -e "${CYAN}${BOLD}"
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║                         🤖 Buddy                            ║"
  echo "║              Raspberry Pi Desktop AI Buddy                  ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
  echo -e "${RESET}"
}

step() { echo -e "\n${CYAN}${BOLD}▶ $*${RESET}"; }
ok() { echo -e "${GREEN}✅ $*${RESET}"; }
warn() { echo -e "${YELLOW}⚠️  $*${RESET}"; }
err() { echo -e "${RED}❌ $*${RESET}"; }
info() { echo -e "${BLUE}ℹ️  $*${RESET}"; }
run() {
  echo -e "${DIM}$ $*${RESET}"
  "$@"
}

project_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

ensure_not_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    warn "Running as root is not recommended. Use your normal Pi user; the script will sudo only when needed."
  fi
}
