# Tello WiFi Communication Module (Raspberry Pi SoftAP) #

Deploy this module on a Raspberry Pi to create a WiFi access point and talk to Tello EDU drones on one subnet with simple UI.<br>
--ssid TELLO-SWARM --password tello12345

### How it works

1. Pi runs SoftAP (`hostapd` + `dnsmasq`) — default SSID `TELLO-SWARM`.
2. Each Tello is provisioned once into station mode with SDK command `ap <ssid> <password>` (Tello EDU).
3. Drones join the Pi network and get DHCP leases (default `192.168.0.10`–`192.168.0.50`).
4. This module discovers clients (DHCP leases + ARP), probes with `command`, and shows them in the UI.


[Tello A] ─┐<br>
[Tello B] ─┼──>> [Raspberry Pi SoftAP] <<── Laptop (http://192.168.0.1:8080)<br>
[Tello C] ─┘


### Setup (on the Pi)

```bash
cd wifi_com_module
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# SoftAP (needs root)
sudo ./scripts/setup_ap.sh

# UI (dry-run skips hostapd if AP already started by the script)
./scripts/run_ui.sh
# or: TELLO_DRY_RUN=1 ./scripts/run_ui.sh --dry-run
```

Open `http://192.168.0.1:8080/`.

### Put each Tello into station mode

Do this once per drone (Temporarily joins the Tello’s own AP `TELLO-XXXX`):

```bash
source .venv/bin/activate
python station_provision.py --ssid TELLO-SWARM --password tello12345
```

### API

- `GET /api/status` — AP + drone summary  
- `GET /api/drones` — discovered / connected drones  
- `POST /api/drones/add` — `{"ip":"192.168.0.12"}`  
- `POST /api/drones/<ip>/command` — `{"command":"battery?"}`  
- `POST /api/broadcast` — send to all connected drones  

