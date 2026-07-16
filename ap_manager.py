from __future__ import print_function

import logging
import os
import re
import subprocess
import time

import config

log = logging.getLogger(__name__)


class AccessPointManager(object):

    def __init__(self, dry_run=None):
        self.dry_run = config.DRY_RUN if dry_run is None else dry_run
        self._running = False

    @property
    def is_running(self):
        return self._running

    def ensure_runtime_dir(self):
        if not os.path.isdir(config.RUNTIME_DIR):
            os.makedirs(config.RUNTIME_DIR)

    def write_hostapd_conf(self, path=None):
        path = path or config.HOSTAPD_CONF
        self.ensure_runtime_dir()
        body = (
            'interface={iface}\n'
            'driver=nl80211\n'
            'ssid={ssid}\n'
            'hw_mode=g\n'
            'channel={channel}\n'
            'wmm_enabled=0\n'
            'macaddr_acl=0\n'
            'auth_algs=1\n'
            'ignore_broadcast_ssid=0\n'
            'wpa=2\n'
            'wpa_passphrase={password}\n'
            'wpa_key_mgmt=WPA-PSK\n'
            'rsn_pairwise=CCMP\n'
            'country_code={country}\n'
        ).format(
            iface=config.AP_INTERFACE,
            ssid=config.AP_SSID,
            channel=config.AP_CHANNEL,
            password=config.AP_PASSWORD,
            country=config.AP_COUNTRY,
        )
        with open(path, 'w') as fh:
            fh.write(body)
        return path

    def write_dnsmasq_conf(self, path=None):
        path = path or config.DNSMASQ_CONF
        self.ensure_runtime_dir()
        body = (
            'interface={iface}\n'
            'dhcp-range={start},{end},{netmask},24h\n'
            'dhcp-option=3,{gateway}\n'
            'dhcp-option=6,{gateway}\n'
            'server=8.8.8.8\n'
            'log-queries\n'
            'log-dhcp\n'
            'listen-address={gateway}\n'
            'bind-interfaces\n'
        ).format(
            iface=config.AP_INTERFACE,
            start=config.AP_DHCP_START,
            end=config.AP_DHCP_END,
            netmask=config.AP_NETMASK,
            gateway=config.AP_GATEWAY,
        )
        with open(path, 'w') as fh:
            fh.write(body)
        return path

    def _run(self, args, check=True):
        log.info('exec: %s', ' '.join(args))
        if self.dry_run:
            return 0, ''
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        out, _ = proc.communicate()
        if check and proc.returncode != 0:
            raise RuntimeError(
                'Command failed ({rc}): {cmd}\n{out}'.format(
                    rc=proc.returncode, cmd=' '.join(args), out=out
                )
            )
        return proc.returncode, out

    def configure_interface(self):
        iface = config.AP_INTERFACE
        self._run(['ip', 'link', 'set', iface, 'down'], check=False)
        self._run(['ip', 'addr', 'flush', 'dev', iface], check=False)
        self._run(
            ['ip', 'addr', 'add', '{}/24'.format(config.AP_GATEWAY), 'dev', iface]
        )
        self._run(['ip', 'link', 'set', iface, 'up'])

    def start(self):
        hostapd = self.write_hostapd_conf()
        dnsmasq = self.write_dnsmasq_conf()

        if not self.dry_run:
            # Stop NetworkManager control of the AP iface when present
            self._run(
                ['nmcli', 'dev', 'set', config.AP_INTERFACE, 'managed', 'no'],
                check=False,
            )
            self.configure_interface()
            self._run(['systemctl', 'stop', 'hostapd'], check=False)
            self._run(['systemctl', 'stop', 'dnsmasq'], check=False)
            self._run(['killall', 'hostapd'], check=False)
            self._run(['killall', 'dnsmasq'], check=False)
            time.sleep(0.5)
            self._run(['hostapd', '-B', hostapd])
            self._run(['dnsmasq', '-C', dnsmasq])

        self._running = True
        log.info(
            'AP ready: SSID=%s gateway=%s dry_run=%s',
            config.AP_SSID,
            config.AP_GATEWAY,
            self.dry_run,
        )
        return {
            'ssid': config.AP_SSID,
            'password': config.AP_PASSWORD,
            'gateway': config.AP_GATEWAY,
            'interface': config.AP_INTERFACE,
            'dry_run': self.dry_run,
            'hostapd_conf': hostapd,
            'dnsmasq_conf': dnsmasq,
        }

    def stop(self):
        if not self.dry_run:
            self._run(['killall', 'hostapd'], check=False)
            self._run(['killall', 'dnsmasq'], check=False)
            self._run(
                ['nmcli', 'dev', 'set', config.AP_INTERFACE, 'managed', 'yes'],
                check=False,
            )
        self._running = False
        log.info('AP stopped')

    def info(self):
        return {
            'running': self._running,
            'ssid': config.AP_SSID,
            'password': config.AP_PASSWORD,
            'gateway': config.AP_GATEWAY,
            'interface': config.AP_INTERFACE,
            'dhcp_range': [config.AP_DHCP_START, config.AP_DHCP_END],
            'cidr': config.AP_CIDR,
            'dry_run': self.dry_run,
        }


def parse_dnsmasq_leases(lease_path=None):
    #Parse dnsmasq lease file into a list of client dicts.
    #Format: <expiry> <mac> <ip> <hostname> <client-id>
    lease_path = lease_path or config.DNSMASQ_LEASES
    clients = []
    if not os.path.isfile(lease_path):
        return clients
    with open(lease_path, 'r') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            clients.append({
                'expiry': int(parts[0]) if parts[0].isdigit() else 0,
                'mac': parts[1].lower(),
                'ip': parts[2],
                'hostname': parts[3] if parts[3] != '*' else '',
            })
    return clients


def parse_arp_table(text=None):
    if text is None:
        try:
            proc = subprocess.Popen(
                ['ip', 'neigh', 'show'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            text, _ = proc.communicate()
        except OSError:
            return []

    entries = []

    pattern = re.compile(
        r'^(\d+\.\d+\.\d+\.\d+)\s+dev\s+\S+\s+lladdr\s+'
        r'([0-9a-fA-F:]{17})\s+(\S+)',
        re.MULTILINE,
    )
    for match in pattern.finditer(text or ''):
        state = match.group(3).upper()
        if state in ('FAILED', 'INCOMPLETE'):
            continue
        entries.append({
            'ip': match.group(1),
            'mac': match.group(2).lower(),
            'state': state,
        })
    return entries


def collect_wifi_clients(lease_path=None, arp_text=None):
    by_ip = {}
    for lease in parse_dnsmasq_leases(lease_path):
        by_ip[lease['ip']] = {
            'ip': lease['ip'],
            'mac': lease['mac'],
            'hostname': lease.get('hostname', ''),
            'source': 'dhcp',
        }
    for neigh in parse_arp_table(arp_text):
        existing = by_ip.get(neigh['ip'])
        if existing:
            existing.setdefault('mac', neigh['mac'])
            if 'dhcp' in existing.get('source', ''):
                existing['source'] = 'dhcp+arp'
            else:
                existing['source'] = 'arp'
        else:
            by_ip[neigh['ip']] = {
                'ip': neigh['ip'],
                'mac': neigh['mac'],
                'hostname': '',
                'source': 'arp',
            }
    # Never treat the AP gateway itself as a client
    by_ip.pop(config.AP_GATEWAY, None)
    return sorted(by_ip.values(), key=lambda c: c['ip'])
