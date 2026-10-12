#!/usr/bin/env python3
"""Read-only inventory, Python 3.7+. Prints a sanitized report to stdout.

Does not install dependencies, write configuration, restart services, or send
G-code. No passwords or SSH connections are managed by this program.
"""
import argparse
import glob
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


FEATURE_COMMANDS = (
    'ADXL_Z_OFFSET', 'ADXL_Z_OFFSET_CHECK', 'ADXL_Z_OFFSET_PREPARE_WIPE',
    'ADAPTIVE_MESH_RESOLVE', 'ADAPTIVE_BED_MESH', 'DUAL_Z_LEVEL',
    'Z_TILT_ADJUST', 'COLD_PULL', 'COLD_PULL_BEEP', 'SHAPER_CALIBRATE',
    'EXCLUDE_OBJECT', 'SET_PRINT_STATS_INFO', 'SET_SKEW',
)
SOURCES = (
    'klippy/extras/adxl345.py', 'klippy/extras/adxl345_tap.py',
    'klippy/extras/adxl345_z_offset.py', 'klippy/extras/adaptive_mesh_bounds.py',
    'klippy/extras/autotune_tmc.py', 'klippy/extras/motor_constants.py',
    'klippy/extras/motor_database.cfg', 'klippy/extras/bed_mesh.py',
    'klippy/extras/gcode_move.py', 'src/sensor_adxl345.c',
)


def fingerprint(path):
    try:
        return {'present': True, 'sha256': hashlib.sha256(
            Path(path).read_bytes()).hexdigest()}
    except (OSError, ValueError):
        return {'present': False}


def read_command(args):
    # All callers use fixed read-only commands, never shell=True.
    try:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
        result = subprocess.run(args, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=10, env=env)
        if result.returncode != 0:
            return None
        return (result.stdout + result.stderr).decode('utf-8', 'replace').strip()
    except (OSError, subprocess.TimeoutExpired):
        return None


def get_json(api_url, endpoint):
    parts = urlsplit(api_url)
    if parts.scheme not in ('http', 'https') or parts.username or parts.password:
        raise ValueError('Use an HTTP API URL without embedded credentials')
    request = Request(api_url.rstrip('/') + endpoint, method='GET')
    with urlopen(request, timeout=8) as response:
        # Bound read size; never echo response bodies on errors.
        raw = response.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError('API response too large')
        return json.loads(raw.decode('utf-8'))['result']


def discover_config(explicit):
    if explicit:
        return Path(explicit)
    candidates = (
        Path('/home/mks/klipper_config/printer.cfg'),
        Path('/home/mks/printer_data/config/printer.cfg'),
        Path('/home/pi/printer_data/config/printer.cfg'),
        Path.home() / 'printer_data/config/printer.cfg',
    )
    return next((p for p in candidates if p.is_file()), candidates[0])


def config_inventory(main):
    root = main.parent.resolve()
    queue, seen, files, sections, unresolved = [main], set(), {}, set(), 0
    while queue:
        path = queue.pop(0).resolve()
        if path in seen:
            continue
        seen.add(path)
        try:
            relative = str(path.relative_to(root)).replace('\\', '/')
            raw = path.read_bytes()
        except (OSError, ValueError):
            unresolved += 1
            continue
        files[relative] = {'present': True, 'sha256': hashlib.sha256(raw).hexdigest()}
        for line in raw.decode('utf-8', 'replace').splitlines():
            match = re.match(r'^\s*\[([^\]]+)\]', line)
            if not match:
                continue
            name = match.group(1).strip()
            if name.lower().startswith('include '):
                pattern = name[len('include '):].strip()
                matches = glob.glob(str(path.parent / pattern))
                queue.extend(Path(p) for p in matches)
                if not matches:
                    unresolved += 1
            else:
                # Section names could contain personal names; only report booleans.
                sections.add(name.lower())
    checks = {
        'pa11_probe_section': 'probe' in sections,
        'toolhead_adxl_section': 'adxl345 x' in sections,
        'bed_adxl_section': 'adxl345 y' in sections,
        'host_mcu_section': 'mcu rpi' in sections,
        'independent_z_section': 'stepper_z1' in sections,
        'auxiliary_fan_section': 'fan_generic auxiliary_fan' in sections,
        'adxl_offset_section': 'adxl345_z_offset' in sections,
        'autotune_x_section': 'autotune_tmc stepper_x' in sections,
        'autotune_y_section': 'autotune_tmc stepper_y' in sections,
        'autotune_extruder_section': 'autotune_tmc extruder' in sections,
    }
    # Exclude filenames other than known package files from public output.
    known_names = ('printer.cfg', 'adxl345_z_offset.cfg', 'adaptive_bed_mesh.cfg',
                   'independent_dual_z.cfg', 'bambu_aux_fan.cfg', 'cold_pull.cfg')
    sanitized = {name: value for name, value in files.items() if name in known_names}
    return {'file_count': len(files), 'known_file_hashes': sanitized,
            'sections_present': checks, 'unresolved_includes': unresolved}


def collect(config_file, klipper_dir, moonraker_dir, api_url):
    config = discover_config(config_file)
    account_root = config.parent.parent
    klipper = Path(klipper_dir) if klipper_dir else account_root / 'klipper'
    moonraker = Path(moonraker_dir) if moonraker_dir else account_root / 'moonraker'
    os_release = {}
    try:
        for line in Path('/etc/os-release').read_text().splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                if key in ('ID', 'VERSION_ID', 'VERSION_CODENAME', 'PRETTY_NAME'):
                    os_release[key] = value.strip('"')
    except OSError:
        pass
    report = {
        'schema': 1, 'mode': 'read_only', 'release_state': 'audit_only',
        'platform': {'architecture': platform.machine(), 'os': os_release},
        'config': config_inventory(config),
        'runtimes': {
            'klipper_python': read_command([
                str(account_root / 'klippy-env/bin/python'), '-B', '--version']),
            'moonraker_python': read_command([
                str(account_root / 'moonraker-env/bin/python'), '-B', '--version']),
        },
        'source_heads': {
            'klipper': read_command(['git', '--no-optional-locks', '-C',
                                     str(klipper), 'rev-parse', 'HEAD']),
            'moonraker': read_command(['git', '--no-optional-locks', '-C',
                                       str(moonraker), 'rev-parse', 'HEAD']),
        },
        'source_fingerprints': {name: fingerprint(klipper / name) for name in SOURCES},
        'metadata_parser': fingerprint(
            moonraker / 'moonraker/components/file_manager/metadata.py'),
        'linux_mcu': fingerprint('/usr/local/bin/klipper_mcu'),
        'api': {},
        'compatibility': {
            'full_install_certified': False,
            'reason': 'No clean stock baseline is certified in this audit-only package.',
            'hardware_verified': False,
        },
    }
    binary_path = Path('/usr/local/bin/klipper_mcu')
    try:
        report['linux_mcu']['contains_tap_command_string'] = (
            b'adxl345_tap_home' in binary_path.read_bytes())
    except OSError:
        pass
    endpoints = (
        ('state', '/printer/objects/query?webhooks&print_stats'),
        ('commands', '/printer/gcode/help'),
        ('klipper_info', '/printer/info'),
        ('moonraker_info', '/server/info'),
    )
    for label, endpoint in endpoints:
        try:
            value = get_json(api_url, endpoint)
            if label == 'state':
                status = value['status']
                report['api']['klipper_state'] = status['webhooks']['state']
                report['api']['print_state'] = status['print_stats']['state']
            elif label == 'commands':
                report['api']['feature_commands'] = {
                    name: name in value for name in FEATURE_COMMANDS}
            elif label == 'klipper_info':
                report['api']['klipper_version'] = value.get('software_version')
            else:
                report['api']['moonraker_version'] = value.get('moonraker_version')
        except Exception:
            # No URL, paths, response bodies, filenames or auth details in errors.
            report['api'][label + '_read_failed'] = True
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-file', help='Override printer.cfg discovery')
    parser.add_argument('--klipper-dir', help='Override Klipper source directory')
    parser.add_argument('--moonraker-dir', help='Override Moonraker source directory')
    parser.add_argument('--api-url', default='http://127.0.0.1:7125',
                        help='Moonraker API (GET requests only)')
    args = parser.parse_args()
    report = collect(args.config_file, args.klipper_dir, args.moonraker_dir, args.api_url)
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    # Exit zero means readable inventory, never certification or installation.
    return 0 if report['config']['file_count'] and 'klipper_state' in report['api'] else 2


if __name__ == '__main__':
    sys.exit(main())
