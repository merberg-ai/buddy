#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib.sh"

ROOT="$(project_root)"
PORT="${BUDDY_PORT:-8080}"
HOST="${BUDDY_HOST:-127.0.0.1}"
BASE_URL="${BUDDY_BASE_URL:-http://${HOST}:${PORT}}"
OUT_DIR="$ROOT/data/debug_bundles"

banner
step "Requesting Buddy debug bundle"
info "BuddyCore API: ${BASE_URL}"

mkdir -p "$OUT_DIR"

if ! command -v curl >/dev/null 2>&1; then
  err "curl is required to export a debug bundle"
  exit 1
fi

response="$(curl -fsS -X POST "${BASE_URL}/api/debug-bundle")"
download_url="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("download_url",""))' <<< "$response")"

if [[ -z "$download_url" ]]; then
  err "BuddyCore did not return a download URL"
  echo "$response"
  exit 1
fi

filename="$(basename "$download_url")"
target="$OUT_DIR/$filename"
curl -fsS "${BASE_URL}${download_url}" -o "$target"

ok "Debug bundle saved to $target"
