# Runtime configuration

import os

# Access Point settings (Pi as AP)
AP_INTERFACE = os.environ.get('TELLO_AP_IFACE', 'wlan0')
AP_SSID = os.environ.get('TELLO_AP_SSID', 'TELLO-SWARM')
AP_PASSWORD = os.environ.get('TELLO_AP_PASSWORD', 'tello12345')
AP_CHANNEL = int(os.environ.get('TELLO_AP_CHANNEL', '6'))
AP_COUNTRY = os.environ.get('TELLO_AP_COUNTRY', 'US')

# Network addressing for the AP subnet
AP_GATEWAY = os.environ.get('TELLO_AP_GATEWAY', '192.168.0.1')
AP_NETMASK = os.environ.get('TELLO_AP_NETMASK', '255.255.255.0')
AP_DHCP_START = os.environ.get('TELLO_AP_DHCP_START', '192.168.0.10')
AP_DHCP_END = os.environ.get('TELLO_AP_DHCP_END', '192.168.0.50')
AP_CIDR = os.environ.get('TELLO_AP_CIDR', '192.168.0.0/24')

# Paths used by hostapd / dnsmasq on Raspberry Pi OS
HOSTAPD_CONF = os.environ.get(
    'TELLO_HOSTAPD_CONF',
    '/tmp/tello_wifi_com/hostapd.conf',
)
DNSMASQ_CONF = os.environ.get(
    'TELLO_DNSMASQ_CONF',
    '/tmp/tello_wifi_com/dnsmasq.conf',
)
DNSMASQ_LEASES = os.environ.get(
    'TELLO_DNSMASQ_LEASES',
    '/var/lib/misc/dnsmasq.leases',
)
RUNTIME_DIR = os.environ.get('TELLO_RUNTIME_DIR', '/tmp/tello_wifi_com')

# Tello UDP SDK (same ports as Tools/Tello-Python-master)
TELLO_CMD_PORT = 8889
TELLO_STATE_PORT = 8890
LOCAL_BIND_IP = os.environ.get('TELLO_LOCAL_BIND_IP', '0.0.0.0')

# Discovery / keep-alive
DISCOVERY_INTERVAL_SEC = float(os.environ.get('TELLO_DISCOVERY_INTERVAL', '3.0'))
COMMAND_TIMEOUT_SEC = float(os.environ.get('TELLO_CMD_TIMEOUT', '2.0'))
STALE_AFTER_SEC = float(os.environ.get('TELLO_STALE_AFTER', '15.0'))
KEEPALIVE_INTERVAL_SEC = float(os.environ.get('TELLO_KEEPALIVE_INTERVAL', '5.0'))

# Flask UI
FLASK_HOST = os.environ.get('TELLO_UI_HOST', '0.0.0.0')
FLASK_PORT = int(os.environ.get('TELLO_UI_PORT', '8080'))
FLASK_DEBUG = os.environ.get('TELLO_UI_DEBUG', '0') == '1'

# Dry-run mode skips hostapd/dnsmasq system calls (useful on non-Pi hosts)
DRY_RUN = os.environ.get('TELLO_DRY_RUN', '0') == '1'
