#!/usr/bin/env bash
# Configure and start SoftAP for Tello swarm (Raspberry Pi).
# Requires: hostapd, dnsmasq, iproute2. Run as root.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

export TELLO_AP_IFACE="${TELLO_AP_IFACE:-wlan0}"
export TELLO_AP_SSID="${TELLO_AP_SSID:-TELLO-SWARM}"
export TELLO_AP_PASSWORD="${TELLO_AP_PASSWORD:-tello12345}"
export TELLO_AP_GATEWAY="${TELLO_AP_GATEWAY:-192.168.0.1}"
export TELLO_AP_DHCP_START="${TELLO_AP_DHCP_START:-192.168.0.10}"
export TELLO_AP_DHCP_END="${TELLO_AP_DHCP_END:-192.168.0.50}"
export TELLO_RUNTIME_DIR="${TELLO_RUNTIME_DIR:-/tmp/tello_wifi_com}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Please run as root: sudo $0" >&2
  exit 1
fi

apt-get update
apt-get install -y hostapd dnsmasq iptables

systemctl unmask hostapd || true
systemctl stop hostapd || true
systemctl stop dnsmasq || true

python3 - <<'PY'
import os, sys
sys.path.insert(0, os.getcwd())
from ap_manager import AccessPointManager
mgr = AccessPointManager(dry_run=False)
info = mgr.start()
print(info)
PY

# Optional: NAT if eth0 has upstream internet
if ip link show eth0 >/dev/null 2>&1; then
  sysctl -w net.ipv4.ip_forward=1
  iptables -t nat -C POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null || \
    iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
fi

echo "SoftAP up: SSID=${TELLO_AP_SSID} gateway=${TELLO_AP_GATEWAY}"
