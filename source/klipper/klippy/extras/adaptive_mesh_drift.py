# Independent center references for adaptive PA11 meshes (Python 2.7).
# Copyright (C) 2026
# This file may be distributed under the terms of the GNU GPLv3 license.
import json
import logging
import math
import re
from . import manual_probe


def finite(value):
    return not (math.isnan(value) or math.isinf(value))


def correct_block(samples, previous, following, baseline):
    """Keep spatial XYZ; remove only the time-interpolated reference drift.

    Samples: (print_time, [nozzle_x, nozzle_y, measured_z]).
    References: (print_time, measured_z). No extrapolation or integer division.
    """
    t0, r0 = previous
    t1, r1 = following
    if not all(finite(v) for v in (t0, r0, t1, r1, baseline)) or t1 <= t0:
        raise ValueError('Invalid reference times or values')
    result = []
    for stamp, position in samples:
        if not finite(stamp) or stamp < t0 or stamp > t1:
            raise ValueError('Mesh sample is not bracketed by references')
        if len(position) != 3 or not all(finite(v) for v in position):
            raise ValueError('Invalid mesh position')
        fraction = float(stamp - t0) / float(t1 - t0)
        drift = (r0 - baseline) + fraction * (r1 - r0)
        result.append([position[0], position[1], position[2] - drift])
    return result


class AdaptiveMeshDrift:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        self.reference_xy = config.getfloatlist(
            'reference_position', (215., 215.), count=2)
        self.interval = config.getint('reference_interval', 5, minval=1, maxval=20)
        self.condition_seconds = config.getfloat(
            'condition_seconds', 180., minval=0., maxval=600.)
        self.max_drift = config.getfloat('max_reference_drift', .5, above=0.)
        self.max_jump = config.getfloat('max_reference_jump', .08, above=0.)
        if not all(finite(v) for v in self.reference_xy):
            raise config.error('Reference position must be finite')
        self.real_homed = set()
        self.running = False
        self.phase = 'idle'
        self.last_run = {'valid': False}
        self.printer.register_event_handler('homing:home_rails_begin',
                                            self.handle_home_begin)
        self.printer.register_event_handler('homing:home_rails_end',
                                            self.handle_home_end)
        self.printer.register_event_handler('stepper_enable:motor_off',
                                            self.handle_motor_off)
        self.gcode.register_command('ADAPTIVE_MESH_DRIFT_CALIBRATE',
            self.cmd_CALIBRATE, desc='Adaptive mesh with time-interpolated center references')
        self.gcode.register_command('ADAPTIVE_MESH_DRIFT_STATUS',
            self.cmd_STATUS, desc='Report reference-corrected adaptive mesh status')

    def rail_axes(self, rails):
        # Homing.get_axes() may list ALL requested axes while only X has homed.
        # Use the rails that actually completed physical homing instead.
        axes = set()
        for rail in rails:
            name = rail.get_name()
            for index, prefix in enumerate(('stepper_x', 'stepper_y', 'stepper_z')):
                if name == prefix or name.startswith(prefix + '_'):
                    axes.add(index)
        return axes

    def handle_home_begin(self, homing_state, rails):
        self.real_homed.difference_update(self.rail_axes(rails))

    def handle_home_end(self, homing_state, rails):
        self.real_homed.update(self.rail_axes(rails))

    def handle_motor_off(self, print_time):
        self.real_homed.clear()

    def get_status(self, eventtime):
        return {'running': self.running, 'phase': self.phase,
                'real_homed_axes': ''.join('xyz'[i] for i in sorted(self.real_homed)),
                'reference_position': list(self.reference_xy),
                'reference_interval': self.interval,
                'condition_seconds': self.condition_seconds,
                'last_run': self.last_run}

    def cmd_STATUS(self, gcmd):
        status = self.get_status(self.reactor.monotonic())
        summary = dict(status)
        summary['last_run'] = dict((k, v) for k, v in self.last_run.items()
                                  if k not in ('raw_points', 'corrected_points', 'references'))
        gcmd.respond_info('ADAPTIVE_MESH_DRIFT: ' + json.dumps(summary, sort_keys=True))

    def guard_home(self, toolhead, gcmd):
        status = toolhead.get_status(self.reactor.monotonic())
        if self.real_homed != set((0, 1, 2)) or status['homed_axes'] != 'xyz':
            raise gcmd.error('ADAPTIVE_MESH_DRIFT requires real XYZ homing after restart; run G28 first')
        return status

    def probe_command(self, gcmd, count):
        params = dict(gcmd.get_command_parameters())
        params['SAMPLES'] = str(count)
        params['SAMPLES_RESULT'] = 'median'
        return self.gcode.create_gcode_command('ADAPTIVE_MESH_DRIFT_CALIBRATE', '', params)

    def travel(self, toolhead, xy, clearance, lift_speed, xy_speed):
        toolhead.manual_move([None, None, clearance], lift_speed)
        toolhead.manual_move(list(xy), xy_speed)

    def measure(self, toolhead, probe, command):
        position = list(probe.run_probe(command))
        # Same Klipper/MCU print-time clock for every sample and reference.
        stamp = float(toolhead.get_last_move_time())
        if len(position) != 3 or not all(finite(v) for v in position) or not finite(stamp):
            raise command.error('Non-finite native probe result')
        return stamp, position

    def cmd_CALIBRATE(self, gcmd):
        if self.running:
            raise gcmd.error('ADAPTIVE_MESH_DRIFT already running')
        if gcmd.get('METHOD', 'automatic').lower() != 'automatic':
            raise gcmd.error('Reference correction requires automatic probing')
        profile = gcmd.get('PROFILE', 'adaptive')
        if not re.match(r'^[A-Za-z0-9_-]+\Z', profile):
            raise gcmd.error('Invalid adaptive mesh profile name')
        condition = gcmd.get_float('CONDITION_SECONDS', self.condition_seconds,
                                   minval=0., maxval=600.)
        if not finite(condition):
            raise gcmd.error('Non-finite conditioning duration')
        manual_probe.verify_no_manual_probe(self.printer)
        toolhead = self.printer.lookup_object('toolhead')
        status = self.guard_home(toolhead, gcmd)
        probe = self.printer.lookup_object('probe')
        bedmesh = self.printer.lookup_object('bed_mesh')
        bmc = bedmesh.bmc
        offsets = probe.get_offsets()
        reference_nozzle = [self.reference_xy[i] - offsets[i] for i in (0, 1)]
        for i in (0, 1):
            if not status['axis_minimum'][i] <= reference_nozzle[i] <= status['axis_maximum'][i]:
                raise gcmd.error('Center reference is outside nozzle travel limits')
            if not bmc.orig_config['mesh_min'][i] <= self.reference_xy[i] <= bmc.orig_config['mesh_max'][i]:
                raise gcmd.error('Center reference is outside the configured probe-safe bed area')
        if bmc.faulty_regions or bmc.radius is not None:
            raise gcmd.error('Reference correction supports rectangular meshes without faulty regions')
        bmc.update_config(gcmd)
        points = [list(point) for point in bmc._get_adjusted_points()]
        clearance, xy_speed = bmc.probe_helper.horizontal_move_z, bmc.probe_helper.speed
        lift_speed = probe.get_lift_speed(gcmd)
        if not finite(clearance) or clearance < offsets[2]:
            raise gcmd.error('horizontal_move_z is below probe z_offset')
        if not status['axis_minimum'][2] <= clearance <= status['axis_maximum'][2]:
            raise gcmd.error('horizontal_move_z is outside Z travel limits')
        for point in points:
            if len(point) != 2 or not all(finite(v) for v in point):
                raise gcmd.error('Invalid generated mesh point')
            for i in (0, 1):
                nozzle = point[i] - offsets[i]
                if not status['axis_minimum'][i] <= nozzle <= status['axis_maximum'][i]:
                    raise gcmd.error('Generated mesh point is outside nozzle travel limits')
        reference_command = self.probe_command(gcmd, 3)
        initial_command = self.probe_command(gcmd, 1)
        self.run_scan(gcmd, toolhead, probe, bedmesh, bmc, points, offsets,
                      reference_nozzle, clearance, lift_speed, xy_speed,
                      reference_command, initial_command, condition, profile)

    def run_scan(self, gcmd, toolhead, probe, bedmesh, bmc, points, offsets,
                 reference_nozzle, clearance, lift_speed, xy_speed,
                 reference_command, initial_command, condition, profile):
        self.running = True
        self.phase = 'starting'
        self.last_run = {'valid': False, 'profile': profile,
                         'reference_probe_xy': list(self.reference_xy),
                         'reference_nozzle_xy': reference_nozzle,
                         'reference_interval': self.interval,
                         'condition_seconds': condition,
                         'total_points': len(points), 'completed_points': 0,
                         'completed_references': 0, 'raw_points': [],
                         'corrected_points': [], 'references': []}
        multi_started = False
        try:
            bedmesh.set_mesh(None)
            bmc._profile_name = profile
            probe.multi_probe_begin()
            multi_started = True
            self.travel(toolhead, reference_nozzle, clearance, xy_speed, xy_speed)
            if condition:
                self.phase = 'conditioning'
                self.measure(toolhead, probe, initial_command)
                gcmd.respond_info('ADAPTIVE_MESH_DRIFT: near-bed conditioning %.0fs.' % condition)
                condition_start = self.reactor.monotonic()
                deadline = condition_start + condition
                while True:
                    self.guard_home(toolhead, gcmd)
                    remaining = deadline - self.reactor.monotonic()
                    if remaining <= 0.:
                        break
                    duration = min(5., remaining)
                    toolhead.dwell(duration)
                    toolhead.wait_moves()
                self.last_run['actual_condition_seconds'] = self.reactor.monotonic() - condition_start
                self.travel(toolhead, reference_nozzle, clearance, lift_speed, xy_speed)
            stamp, base_pos = self.measure(toolhead, probe, reference_command)
            baseline = base_pos[2]
            previous = (stamp, baseline)
            self.last_run.update({'baseline_z': baseline, 'baseline_print_time': stamp})
            self.last_run['references'].append({'after_point': 0, 'print_time': stamp,
                                                'median_z': baseline, 'drift': 0.})
            gcmd.respond_info('ADAPTIVE_MESH_DRIFT: baseline %.6f, reference probe XY %.2f,%.2f, every %d points.'
                              % (baseline, self.reference_xy[0], self.reference_xy[1], self.interval))
            block = []
            corrected_positions = []
            for index, point in enumerate(points, 1):
                self.guard_home(toolhead, gcmd)
                self.phase = 'mesh'
                nozzle_xy = [point[i] - offsets[i] for i in (0, 1)]
                self.travel(toolhead, nozzle_xy, clearance, lift_speed, xy_speed)
                sample = self.measure(toolhead, probe, gcmd)
                block.append(sample)
                self.last_run['raw_points'].append({'point': index,
                    'print_time': sample[0], 'position': sample[1]})
                self.last_run['completed_points'] = index
                if len(block) == self.interval or index == len(points):
                    self.phase = 'reference'
                    self.travel(toolhead, reference_nozzle, clearance, lift_speed, xy_speed)
                    stamp, ref_pos = self.measure(toolhead, probe, reference_command)
                    following = (stamp, ref_pos[2])
                    drift = following[1] - baseline
                    if abs(drift) > self.max_drift:
                        raise gcmd.error('Center reference drift %.6f exceeds %.3fmm limit'
                                          % (drift, self.max_drift))
                    if abs(following[1] - previous[1]) > self.max_jump:
                        raise gcmd.error('Center reference jump exceeds %.3fmm limit' % self.max_jump)
                    try:
                        corrected = correct_block(block, previous, following, baseline)
                    except ValueError as exc:
                        raise gcmd.error(str(exc))
                    corrected_positions.extend(corrected)
                    self.last_run['corrected_points'].extend(corrected)
                    self.last_run['references'].append({'after_point': index,
                        'print_time': stamp, 'median_z': following[1], 'drift': drift})
                    self.last_run['completed_references'] += 1
                    gcmd.respond_info('ADAPTIVE_MESH_DRIFT: reference after %d/%d points, drift %+.6fmm; time-interpolated %d points.'
                                      % (index, len(points), drift, len(block)))
                    previous, block = following, []
            toolhead.manual_move([None, None, clearance], lift_speed)
            toolhead.get_last_move_time()
            probe.multi_probe_end()
            multi_started = False
            # Extra center samples never reach the native spatial matrix.
            # Native finalization preserves XY sorting, interpolation, offsets
            # and the profile consumed by the later ADXL Z-offset routine.
            bmc.probe_finalize(offsets, corrected_positions)
            self.last_run.update({'valid': True, 'final_reference_drift': previous[1] - baseline,
                'max_applied_correction': max(abs(raw['position'][2] - corrected[2])
                    for raw, corrected in zip(self.last_run['raw_points'], corrected_positions)),
                'elapsed_seconds': previous[0] - self.last_run['baseline_print_time']})
            self.phase = 'complete'
            logging.info('adaptive_mesh_drift complete: %s', json.dumps(self.last_run, sort_keys=True))
            gcmd.respond_info('ADAPTIVE_MESH_DRIFT: complete, %d mesh points + %d references, profile %s.'
                % (len(points), self.last_run['completed_references'], profile))
        except Exception as exc:
            self.last_run['valid'] = False
            self.last_run['error'] = str(exc)
            self.phase = 'failed'
            bedmesh.set_mesh(None)
            raise
        finally:
            if multi_started:
                try:
                    probe.multi_probe_end()
                except Exception:
                    logging.exception('adaptive_mesh_drift: native probe cleanup failed')
            self.running = False


def load_config(config):
    return AdaptiveMeshDrift(config)

