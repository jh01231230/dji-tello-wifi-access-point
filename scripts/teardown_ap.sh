#!/usr/bin/env bash
# Stop SoftAP services started by setup_ap.sh / AccessPointManager.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

export TELLO_AP_IFACE="${TELLO_AP_IFACE:-wlan0}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Please run as root: sudo $0" >&2
  exit 1
fi

python3 - <<'PY'
import os, sys
sys.path.insert(0, os.getcwd())
from ap_manager import AccessPointManager
mgr = AccessPointManager(dry_run=False)
mgr._running = True
mgr.stop()
print('AP stopped')
PY

echo "Done."
