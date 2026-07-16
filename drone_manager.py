from __future__ import print_function

import logging
import threading
import time

import config
from ap_manager import collect_wifi_clients
from tello_client import StateListener, TelloClient

log = logging.getLogger(__name__)


class DroneRecord(object):
    def __init__(self, ip, mac='', hostname=''):
        self.ip = ip
        self.mac = mac
        self.hostname = hostname
        self.connected = False
        self.battery = None
        self.sn = None
        self.sdk = None
        self.last_response = None
        self.last_seen = 0.0
        self.last_ok = 0.0
        self.error = None
        self.state = {}
        self.source = ''

    def to_dict(self):
        age = None
        if self.last_seen:
            age = round(time.time() - self.last_seen, 1)
        return {
            'ip': self.ip,
            'mac': self.mac,
            'hostname': self.hostname,
            'connected': self.connected,
            'battery': self.battery,
            'sn': self.sn,
            'sdk': self.sdk,
            'last_response': self.last_response,
            'last_seen': self.last_seen,
            'last_ok': self.last_ok,
            'age_sec': age,
            'error': self.error,
            'state': self.state,
            'source': self.source,
        }


class DroneManager(object):

    def __init__(
        self,
        lease_path=None,
        discovery_interval=None,
        stale_after=None,
        auto_start=True,
    ):
        self.lease_path = lease_path
        self.discovery_interval = (
            discovery_interval
            if discovery_interval is not None
            else config.DISCOVERY_INTERVAL_SEC
        )
        self.stale_after = (
            stale_after if stale_after is not None else config.STALE_AFTER_SEC
        )
        self._drones = {}  # ip -> DroneRecord
        self._clients = {}  # ip -> TelloClient
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._manual_ips = set()
        self._state_listener = None
        self._thread = None
        self.started_at = None

        if auto_start:
            self.start()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.started_at = time.time()
        try:
            self._state_listener = StateListener()
        except OSError as exc:
            log.warning('State listener unavailable: %s', exc)
            self._state_listener = None
        self._thread = threading.Thread(target=self._loop, name='drone-manager')
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        with self._lock:
            for client in self._clients.values():
                client.close()
            self._clients.clear()
        if self._state_listener:
            self._state_listener.close()
            self._state_listener = None

    def add_ip(self, ip):
        with self._lock:
            self._manual_ips.add(ip)
            if ip not in self._drones:
                self._drones[ip] = DroneRecord(ip)
                self._drones[ip].source = 'manual'

    def remove_ip(self, ip):
        with self._lock:
            self._manual_ips.discard(ip)
            self._drones.pop(ip, None)
            client = self._clients.pop(ip, None)
        if client:
            client.close()

    def list_drones(self):
        with self._lock:
            drones = [d.to_dict() for d in self._drones.values()]
        drones.sort(key=lambda d: d['ip'])
        return drones

    def get_drone(self, ip):
        with self._lock:
            rec = self._drones.get(ip)
            return rec.to_dict() if rec else None

    def send_command(self, ip, command):
        client = self._ensure_client(ip)
        resp = client.send_command(command)
        with self._lock:
            rec = self._drones.setdefault(ip, DroneRecord(ip))
            rec.last_response = resp
            rec.last_seen = time.time()
            if resp is not None and str(resp).lower().startswith('ok'):
                rec.connected = True
                rec.last_ok = rec.last_seen
                rec.error = None
            elif resp is None:
                rec.error = client.error or 'timeout'
        return resp

    def broadcast_command(self, command, connected_only=True):
        results = {}
        for drone in self.list_drones():
            if connected_only and not drone['connected']:
                continue
            results[drone['ip']] = self.send_command(drone['ip'], command)
        return results

    def summary(self):
        drones = self.list_drones()
        connected = [d for d in drones if d['connected']]
        return {
            'total': len(drones),
            'connected': len(connected),
            'drones': drones,
            'uptime_sec': (
                round(time.time() - self.started_at, 1) if self.started_at else 0
            ),
        }

    def _ensure_client(self, ip):
        with self._lock:
            client = self._clients.get(ip)
            if client is None:
                client = TelloClient(ip)
                self._clients[ip] = client
            return client

    def _candidate_ips(self):
        clients = collect_wifi_clients(self.lease_path)
        with self._lock:
            for client in clients:
                ip = client['ip']
                rec = self._drones.setdefault(ip, DroneRecord(ip))
                rec.mac = client.get('mac', rec.mac)
                rec.hostname = client.get('hostname', rec.hostname)
                rec.source = client.get('source', rec.source)
            for ip in self._manual_ips:
                self._drones.setdefault(ip, DroneRecord(ip)).source = (
                    self._drones[ip].source or 'manual'
                )
            return list(self._drones.keys())

    def _probe(self, ip):
        client = self._ensure_client(ip)
        ok = client.enter_sdk_mode()
        now = time.time()
        with self._lock:
            rec = self._drones.setdefault(ip, DroneRecord(ip))
            rec.last_seen = now
            rec.last_response = client.last_response
            if ok:
                rec.connected = True
                rec.last_ok = now
                rec.error = None
            else:
                # Keep previous connected flag until stale timeout
                rec.error = client.error

        if ok:
            battery = client.query_battery()
            sn = client.query_sn()
            sdk = client.query_sdk()
            with self._lock:
                if battery is not None:
                    rec.battery = battery
                if sn:
                    rec.sn = sn
                if sdk:
                    rec.sdk = sdk

    def _refresh_state(self):
        if not self._state_listener:
            return
        snapshot = self._state_listener.snapshot()
        with self._lock:
            for ip, payload in snapshot.items():
                rec = self._drones.setdefault(ip, DroneRecord(ip))
                rec.state = payload.get('state') or {}
                rec.last_seen = payload.get('updated', rec.last_seen)
                if 'bat' in rec.state:
                    rec.battery = rec.state['bat']
                # Telemetry implies the drone is alive
                if rec.last_seen and (time.time() - rec.last_seen) < self.stale_after:
                    rec.connected = True

    def _mark_stale(self):
        now = time.time()
        with self._lock:
            for rec in self._drones.values():
                if rec.last_ok and (now - rec.last_ok) > self.stale_after:
                    # Prefer last_seen from state packets if fresher
                    ref = max(rec.last_ok, rec.last_seen or 0)
                    if (now - ref) > self.stale_after:
                        rec.connected = False
                        if not rec.error:
                            rec.error = 'stale'

    def _loop(self):
        keepalive_at = 0.0
        while not self._stop.is_set():
            try:
                ips = self._candidate_ips()
                for ip in ips:
                    if self._stop.is_set():
                        break
                    self._probe(ip)
                self._refresh_state()
                self._mark_stale()

                now = time.time()
                if now - keepalive_at >= config.KEEPALIVE_INTERVAL_SEC:
                    keepalive_at = now
                    for drone in self.list_drones():
                        if drone['connected']:
                            self.send_command(drone['ip'], 'command')
            except Exception:
                log.exception('discovery loop error')
            self._stop.wait(self.discovery_interval)
