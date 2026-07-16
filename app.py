# Flask UI and REST API
from __future__ import print_function

import argparse
import atexit
import logging
import os
import sys

from flask import Flask, jsonify, render_template, request

import config
from ap_manager import AccessPointManager
from drone_manager import DroneManager

log = logging.getLogger(__name__)

app = Flask(__name__)
ap_manager = None
drone_manager = None


def create_services(start_ap=False, dry_run=None):
    global ap_manager, drone_manager
    ap_manager = AccessPointManager(dry_run=dry_run)
    if start_ap:
        ap_manager.start()
    drone_manager = DroneManager(auto_start=True)
    return ap_manager, drone_manager


@app.route('/')
def index():
    return render_template(
        'index.html',
        ap=ap_manager.info() if ap_manager else {},
        title='Tello WiFi Swarm',
    )


@app.route('/api/status')
def api_status():
    return jsonify({
        'ap': ap_manager.info() if ap_manager else {},
        'drones': drone_manager.summary() if drone_manager else {},
    })


@app.route('/api/drones')
def api_drones():
    if not drone_manager:
        return jsonify({'drones': []})
    return jsonify(drone_manager.summary())


@app.route('/api/drones/<ip>')
def api_drone(ip):
    if not drone_manager:
        return jsonify({'error': 'manager not ready'}), 503
    drone = drone_manager.get_drone(ip)
    if not drone:
        return jsonify({'error': 'not found'}), 404
    return jsonify(drone)


@app.route('/api/drones/<ip>/command', methods=['POST'])
def api_command(ip):
    if not drone_manager:
        return jsonify({'error': 'manager not ready'}), 503
    payload = request.get_json(silent=True) or {}
    command = payload.get('command') or request.form.get('command')
    if not command:
        return jsonify({'error': 'missing command'}), 400
    resp = drone_manager.send_command(ip, command)
    return jsonify({'ip': ip, 'command': command, 'response': resp})


@app.route('/api/broadcast', methods=['POST'])
def api_broadcast():
    if not drone_manager:
        return jsonify({'error': 'manager not ready'}), 503
    payload = request.get_json(silent=True) or {}
    command = payload.get('command')
    if not command:
        return jsonify({'error': 'missing command'}), 400
    results = drone_manager.broadcast_command(command)
    return jsonify({'command': command, 'results': results})


@app.route('/api/drones/add', methods=['POST'])
def api_add_drone():
    if not drone_manager:
        return jsonify({'error': 'manager not ready'}), 503
    payload = request.get_json(silent=True) or {}
    ip = payload.get('ip')
    if not ip:
        return jsonify({'error': 'missing ip'}), 400
    drone_manager.add_ip(ip)
    return jsonify({'ok': True, 'ip': ip})


@app.route('/api/ap/start', methods=['POST'])
def api_ap_start():
    if not ap_manager:
        return jsonify({'error': 'ap manager not ready'}), 503
    info = ap_manager.start()
    return jsonify(info)


@app.route('/api/ap/stop', methods=['POST'])
def api_ap_stop():
    if not ap_manager:
        return jsonify({'error': 'ap manager not ready'}), 503
    ap_manager.stop()
    return jsonify({'ok': True})


def _shutdown():
    if drone_manager:
        drone_manager.stop()
    if ap_manager and ap_manager.is_running:
        ap_manager.stop()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Tello WiFi communication UI')
    parser.add_argument('--host', default=config.FLASK_HOST)
    parser.add_argument('--port', type=int, default=config.FLASK_PORT)
    parser.add_argument('--start-ap', action='store_true',
                        help='Start SoftAP (hostapd/dnsmasq) on launch')
    parser.add_argument('--dry-run', action='store_true',
                        help='Skip hostapd/dnsmasq system calls')
    parser.add_argument('--debug', action='store_true', default=config.FLASK_DEBUG)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    dry_run = True if args.dry_run else None
    if args.dry_run:
        os.environ['TELLO_DRY_RUN'] = '1'

    create_services(start_ap=args.start_ap, dry_run=dry_run)
    atexit.register(_shutdown)

    print('UI: http://{}:{}/'.format(args.host, args.port))
    print('AP SSID: {}  password: {}'.format(config.AP_SSID, config.AP_PASSWORD))
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == '__main__':
    sys.exit(main() or 0)
