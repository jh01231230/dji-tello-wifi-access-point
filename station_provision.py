"""
Workflow (one drone at a time):
1. Connect your controller WiFi to the Tello's own AP (TELLO-XXXX).
2. Run this script; it sends SDK ``command`` then ``ap <ssid> <password>``.
3. The Tello reboots onto the swarm SoftAP and gets a DHCP lease.
4. Repeat for each drone.
"""

from __future__ import print_function

import argparse
import logging
import sys
import time

import config
from tello_client import TelloClient

log = logging.getLogger(__name__)


def provision_tello(
    ssid=None,
    password=None,
    tello_ip='192.168.10.1',
    timeout=5.0,
):
    ssid = ssid or config.AP_SSID
    password = password or config.AP_PASSWORD

    client = TelloClient(tello_ip, command_timeout=timeout)
    try:
        print('Entering SDK mode on {} ...'.format(tello_ip))
        if not client.enter_sdk_mode():
            return False, 'Failed to enter SDK mode: {}'.format(client.error)

        cmd = 'ap {} {}'.format(ssid, password)
        print('Sending: {}'.format(cmd))
        # Tello may reboot before responding; do not require a reply
        client.send_command(cmd, wait=False)
        time.sleep(1.0)
        return True, 'Station join requested for SSID={}'.format(ssid)
    finally:
        client.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Put a Tello into station mode (join Pi SoftAP).'
    )
    parser.add_argument('--ssid', default=config.AP_SSID)
    parser.add_argument('--password', default=config.AP_PASSWORD)
    parser.add_argument('--tello-ip', default='192.168.10.1')
    parser.add_argument('--timeout', type=float, default=5.0)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    ok, message = provision_tello(
        ssid=args.ssid,
        password=args.password,
        tello_ip=args.tello_ip,
        timeout=args.timeout,
    )
    print(message)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
