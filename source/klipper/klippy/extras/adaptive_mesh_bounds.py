# Bambu Studio PA-line calibration bounds resolver (Python 2.7 compatible).
import math
import os
import re

START = '; PA_LINE_CALIBRATION_START'
END = '; PA_LINE_CALIBRATION_END'
MAX_BYTES = 8 * 1024 * 1024


def calibration_bounds(lines):
    """Only override explicit PA-line blocks; never include start/end purges.

    Bound every positive-extrusion XY segment by both endpoints, including
    printed labels. Unsupported geometry in a recognized block fails closed.
    """
    lines = list(lines)
    markers = set(raw.strip() for raw in lines)
    if START not in markers:
        if END in markers:
            raise ValueError('PA calibration end without start')
        return None
    xy = [None, None]
    e = 0.
    absolute_xy, absolute_e = True, True
    active = found = ended = False
    bounds = None
    for raw in lines:
        line = raw.strip()
        if line == START:
            if found:
                raise ValueError('Multiple PA calibration blocks')
            active = found = True
            continue
        if line == END:
            if not active:
                raise ValueError('PA calibration end without start')
            active, ended = False, True
            continue
        code = line.split(';', 1)[0].strip().upper()
        if not code:
            continue
        command = code.split()[0]
        values = {}
        if command in ('G0', 'G1', 'G92'):
            for token in code.split()[1:]:
                if token[0] in 'XYZE':
                    if token[0] in values:
                        raise ValueError('Duplicate PA coordinate word')
                    try:
                        values[token[0]] = float(token[1:])
                    except ValueError:
                        raise ValueError('Malformed PA coordinate word')
        if any(math.isnan(v) or math.isinf(v) for v in values.values()):
            raise ValueError('Non-finite PA coordinates')
        if command == 'G90':
            absolute_xy = True
        elif command == 'G91':
            absolute_xy = False
        elif command == 'M82':
            absolute_e = True
        elif command == 'M83':
            absolute_e = False
        elif command == 'G92':
            if active and ('X' in values or 'Y' in values):
                raise ValueError('PA calibration G92 XY is unsupported')
            if 'E' in values:
                e = values['E']
        elif command in ('G0', 'G1'):
            previous = list(xy)
            for index, axis in enumerate(('X', 'Y')):
                if axis in values:
                    if absolute_xy:
                        xy[index] = values[axis]
                    elif xy[index] is not None:
                        xy[index] += values[axis]
                    elif active:
                        raise ValueError('Unknown relative PA XY origin')
            delta_e = 0.
            if 'E' in values:
                delta_e = values['E'] - e if absolute_e else values['E']
                e = values['E'] if absolute_e else e + delta_e
            if active and delta_e > 0. and previous != xy:
                if None in previous or None in xy:
                    raise ValueError('Unknown PA extrusion segment endpoint')
                for point in (previous, xy):
                    if bounds is None:
                        bounds = [point[0], point[1], point[0], point[1]]
                    else:
                        bounds = [min(bounds[0], point[0]),
                                  min(bounds[1], point[1]),
                                  max(bounds[2], point[0]),
                                  max(bounds[3], point[1])]
        elif active and command not in ('M73', 'M204', 'M220', 'M221',
                                         'M106', 'M107', 'G21',
                                         'SET_PRESSURE_ADVANCE'):
            raise ValueError('Unsupported PA calibration command: ' + command)
    if not found:
        return None
    if not ended or active or bounds is None:
        raise ValueError('Incomplete or empty PA calibration block')
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        raise ValueError('Degenerate PA calibration bounds')
    return tuple(bounds)


def read_calibration_bounds(path):
    with open(path, 'rb') as source:
        data = source.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        # Ordinary large model files keep their slicer bounds. A PA marker
        # in the scanned prefix must not yield silently truncated geometry.
        if START.encode('ascii') in data:
            raise ValueError('PA calibration file exceeds 8MiB scan limit')
        return None
    return calibration_bounds(data.decode('utf-8', 'replace').splitlines())


def resolve_mesh_command(printer, gcode, gcmd):
    params = dict(gcmd.get_command_parameters())
    plan_only = gcmd.get_int('PLAN_ONLY', 0, minval=0, maxval=1)
    source_file = params.pop('SOURCE_FILE', None)
    sdcard = printer.lookup_object('virtual_sdcard', None)
    path = None
    if source_file is not None:
        if not plan_only or sdcard is None:
            raise gcmd.error('SOURCE_FILE requires PLAN_ONLY=1 and virtual_sdcard')
        root = os.path.realpath(sdcard.sdcard_dirname)
        path = os.path.realpath(os.path.join(root, source_file))
        if not path.startswith(root + os.sep) or not os.path.isfile(path):
            raise gcmd.error('SOURCE_FILE must be a file inside the SD directory')
    elif sdcard is not None and sdcard.is_cmd_from_sd():
        path = sdcard.file_path()
    try:
        bounds = read_calibration_bounds(path) if path else None
    except (IOError, OSError, ValueError) as exc:
        raise gcmd.error('Unable to resolve PA calibration bounds: %s' % exc)
    if bounds is not None:
        for name, value in zip(('X_MIN', 'Y_MIN', 'X_MAX', 'Y_MAX'), bounds):
            params[name] = '%.5f' % value
        gcmd.respond_info('ADAPTIVE_BED_MESH: PA calibration extrusion bounds'
                          ' %.3f,%.3f..%.3f,%.3f replace slicer bounds.' % bounds)
    allowed = ('X_MIN', 'Y_MIN', 'X_MAX', 'Y_MAX', 'MARGIN', 'PROFILE', 'PLAN_ONLY')
    if any(name not in allowed for name in params):
        raise gcmd.error('Unsupported ADAPTIVE_BED_MESH parameter')
    # Validate forwarded tokens; no newlines or executable text reach the macro.
    for name, value in params.items():
        if name == 'PROFILE':
            if not re.match(r'^[A-Za-z0-9_-]+\Z', value):
                raise gcmd.error('Invalid mesh profile name')
        else:
            try:
                numeric = float(value)
            except ValueError:
                raise gcmd.error('Invalid numeric mesh parameter: ' + name)
            if math.isnan(numeric) or math.isinf(numeric):
                raise gcmd.error('Non-finite mesh parameter: ' + name)
            params[name] = str(numeric)
    gcode.run_script_from_command('_ADAPTIVE_BED_MESH_BUILD ' + ' '.join(
        '%s=%s' % (name, params[name]) for name in sorted(params)))
