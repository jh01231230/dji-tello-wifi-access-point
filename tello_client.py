# UDP SDK client for a single Tello drone.

from __future__ import print_function

import logging
import socket
import threading
import time

import config

log = logging.getLogger(__name__)


def parse_state_packet(payload):

    if isinstance(payload, bytes):
        payload = payload.decode('utf-8', errors='ignore')
    state = {}
    for item in payload.strip().split(';'):
        item = item.strip()
        if not item or ':' not in item:
            continue
        key, value = item.split(':', 1)
        key = key.strip()
        value = value.strip()
        try:
            if '.' in value:
                state[key] = float(value)
            else:
                state[key] = int(value)
        except ValueError:
            state[key] = value
    return state


class TelloClient(object):

    def __init__(
        self,
        tello_ip,
        tello_port=None,
        local_ip=None,
        command_timeout=None,
        local_cmd_port=0,
    ):
        self.tello_ip = tello_ip
        self.tello_port = tello_port or config.TELLO_CMD_PORT
        self.tello_address = (self.tello_ip, self.tello_port)
        self.local_ip = local_ip if local_ip is not None else config.LOCAL_BIND_IP
        self.command_timeout = (
            command_timeout
            if command_timeout is not None
            else config.COMMAND_TIMEOUT_SEC
        )

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.local_ip, local_cmd_port))
        self._sock.settimeout(0.5)

        self._response = None
        self._response_event = threading.Event()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.last_response = None
        self.last_contact = 0.0
        self.state = {}
        self.connected = False
        self.error = None

        self._rx_thread = threading.Thread(
            target=self._receive_loop, name='tello-rx-{}'.format(tello_ip)
        )
        self._rx_thread.daemon = True
        self._rx_thread.start()

    def _receive_loop(self):
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(4096)
            except socket.timeout:
                continue
            except socket.error as exc:
                if not self._stop.is_set():
                    log.debug('recv error from %s: %s', self.tello_ip, exc)
                continue

            src_ip = addr[0]
            if src_ip != self.tello_ip:
                # Shared socket edge case; ignore unrelated packets
                continue

            text = data.decode('utf-8', errors='ignore').strip()
            self.last_contact = time.time()
            # State telemetry is usually longer key:value lists
            if ';' in text and ':' in text and not text.lower().startswith('ok'):
                self.state = parse_state_packet(text)
                continue

            with self._lock:
                self._response = text
                self.last_response = text
                self._response_event.set()

    def send_command(self, command, wait=True):
        if isinstance(command, bytes):
            command = command.decode('utf-8')

        with self._lock:
            self._response = None
            self._response_event.clear()

        try:
            self._sock.sendto(command.encode('utf-8'), self.tello_address)
        except socket.error as exc:
            self.error = str(exc)
            log.warning('send to %s failed: %s', self.tello_ip, exc)
            return None

        if not wait:
            return None

        deadline = time.time() + self.command_timeout
        while time.time() < deadline:
            if self._response_event.wait(0.05):
                with self._lock:
                    return self._response
        self.error = 'timeout'
        return None

    def enter_sdk_mode(self):
        resp = self.send_command('command')
        ok = resp is not None and resp.lower().startswith('ok')
        self.connected = ok
        if not ok:
            self.error = resp or 'timeout'
        else:
            self.error = None
        return ok

    def query_battery(self):
        resp = self.send_command('battery?')
        if resp is None:
            return None
        try:
            return int(resp)
        except ValueError:
            return None

    def query_sn(self):
        return self.send_command('sn?')

    def query_sdk(self):
        return self.send_command('sdk?')

    def enable_state(self):
        return self.send_command('command')

    def close(self):
        self._stop.set()
        try:
            self._sock.close()
        except socket.error:
            pass


class StateListener(object):

    def __init__(self, bind_ip=None, port=None):
        self.bind_ip = bind_ip if bind_ip is not None else config.LOCAL_BIND_IP
        self.port = port or config.TELLO_STATE_PORT
        self._states = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.bind_ip, self.port))
        self._sock.settimeout(0.5)
        self._thread = threading.Thread(target=self._loop, name='tello-state')
        self._thread.daemon = True
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(4096)
            except socket.timeout:
                continue
            except socket.error:
                continue
            state = parse_state_packet(data)
            with self._lock:
                self._states[addr[0]] = {
                    'state': state,
                    'updated': time.time(),
                }

    def get(self, ip):
        with self._lock:
            return self._states.get(ip)

    def snapshot(self):
        with self._lock:
            return dict(self._states)

    def close(self):
        self._stop.set()
        try:
            self._sock.close()
        except socket.error:
            pass
