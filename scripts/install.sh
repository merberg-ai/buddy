#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib.sh"

ROOT="$(project_root)"
VENV="$ROOT/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_SERVICE=0

for arg in "$@"; do
  case "$arg" in
    --service) INSTALL_SERVICE=1 ;;
    --help|-h)
      echo "Usage: ./scripts/install.sh [--service]"
      exit 0
      ;;
  esac
done

banner
ensure_not_root
step "Preparing Buddy install in $ROOT"

cd "$ROOT"

step "Checking operating system"
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  info "Detected: ${PRETTY_NAME:-unknown Linux}"
else
  warn "Could not read /etc/os-release"
fi

step "Installing system packages"
if command -v apt-get >/dev/null 2>&1; then
  run sudo apt-get update
  run sudo apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    git \
    curl \
    unzip \
    build-essential \
    pkg-config \
    libgl1 \
    libgl1-mesa-dri \
    libsdl2-2.0-0 \
    libsdl2-dev \
    libsdl2-image-2.0-0 \
    libsdl2-mixer-2.0-0 \
    libsdl2-ttf-2.0-0
  ok "System packages installed"
else
  warn "apt-get not found. Skipping system package install. Install Python 3, venv, pip, git, SDL2 libs manually."
fi

step "Checking Python"
run "$PYTHON_BIN" --version

if [[ ! -d "$VENV" ]]; then
  step "Creating virtual environment"
  run "$PYTHON_BIN" -m venv "$VENV"
  ok "Created venv at $VENV"
else
  ok "Virtual environment already exists at $VENV"
fi

step "Upgrading pip/setuptools/wheel"
run "$VENV/bin/python" -m pip install --upgrade pip setuptools wheel

step "Installing Python dependencies"
run "$VENV/bin/pip" install -r requirements.txt
ok "Python dependencies installed"

step "Preparing runtime directories"
run mkdir -p data data/plugin_data logs config/plugins
if [[ ! -f config/buddy.yaml && -f config/buddy.yaml.example ]]; then
  run cp config/buddy.yaml.example config/buddy.yaml
  ok "Created config/buddy.yaml from example"
else
  ok "Config already present"
fi

step "Running import sanity check"
run "$VENV/bin/python" -m compileall -q buddycore plugins
ok "Python files compile cleanly"

if [[ "$INSTALL_SERVICE" -eq 1 ]]; then
  step "Installing systemd service because --service was provided"
  run "$ROOT/scripts/service-install.sh"
fi

step "Install complete"
ok "Buddy is ready. Run it with: ./scripts/run.sh"
info "Then open: http://<pi-ip>:8080"
