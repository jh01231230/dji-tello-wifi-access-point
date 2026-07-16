#!/usr/bin/env bash
# Launch the Flask UI (optionally with SoftAP).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PY="$ROOT_DIR/.venv/bin/python"
else
  PY="python3"
fi

START_AP_FLAG=""
DRY_RUN_FLAG=""
if [[ "${START_AP:-0}" == "1" ]]; then
  START_AP_FLAG="--start-ap"
fi
if [[ "${TELLO_DRY_RUN:-0}" == "1" ]]; then
  DRY_RUN_FLAG="--dry-run"
fi

exec "$PY" app.py $START_AP_FLAG $DRY_RUN_FLAG "$@"
