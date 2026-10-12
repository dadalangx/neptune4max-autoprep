# Pre-print nozzle offset calibration; PA11 retains G28 and bed mesh.
# Copyright (C) 2026
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging
import math
import random

from .adxl345_tap import ADXL345Tap, SINGLE_TAP
from .adaptive_mesh_bounds import resolve_mesh_command


def calculate_offset(tap_z, mesh_z, baseline, max_deviation, trim=0.):
    """At full mesh compensation: physical Z = gcode Z + offset + mesh Z.

    Tap measures physical contact with the mesh disabled.  Subtract the
    saved mesh's value at that same nozzle XY; never add the old offset.
    A positive trim raises the nozzle. Baseline is only a plausibility guard.
    """
    values = (tap_z, mesh_z, baseline, max_deviation, trim)
    if not all(not (math.isnan(v) or math.isinf(v)) for v in values):
        raise ValueError("Non-finite Z offset input")
    offset = tap_z - mesh_z + trim
    if abs(offset - baseline) > max_deviation + 1.e-9:
        raise ValueError(
            "Calculated offset %.6f differs from manual baseline %.6f"
            " by more than %.3f mm" % (offset, baseline, max_deviation))
    return offset


def choose_contact_xy(home_xy, fuzz, randint=None):
    """Choose one 0.01mm-resolution point for an entire contact group.

    This is deliberately separate from the fixed high-Z non-contact check.
    A caller-provided randint keeps the safety calculation deterministic in
    regression tests while production uses Python's process-seeded PRNG.
    """
    values = tuple(home_xy) + (fuzz,)
    if len(home_xy) != 2 or any(math.isnan(v) or math.isinf(v) for v in values):
        raise ValueError('Non-finite ADXL contact XY/fuzz')
    if fuzz < 0. or fuzz > 3.:
        raise ValueError('ADXL contact fuzz must be within 0..3mm')
    steps = int(round(fuzz * 100.))
    if not steps:
        return tuple(home_xy)
    chooser = random.randint if randint is None else randint
    return (round(home_xy[0] + chooser(-steps, steps) / 100., 2),
            round(home_xy[1] + chooser(-steps, steps) / 100., 2))


class ADXL345ZOffset(ADXL345Tap):
    def __init__(self, config):
        # The vendor's active klippy-env still uses Python 2.7 and the
        # historical Tap class is an old-style class there.
        ADXL345Tap.__init__(self, config, register_commands=False)
        self.baseline = config.getfloat('manual_baseline', -2.)
        self.max_deviation = config.getfloat(
            'max_offset_deviation', .5, above=0., maxval=1.)
        self.contact_trim = config.getfloat(
            'contact_trim', 0., minval=-.2, maxval=.2)
        self.contact_fuzz = config.getfloat(
            'contact_fuzz', 3., minval=0., maxval=3.)
        self.contact_sample_groups = config.getint(
            'contact_sample_groups', 3, minval=1, maxval=3)
        self.profile = config.get('mesh_profile', 'default')
        self.bed_soak_seconds = config.getfloat(
            'bed_soak_seconds', 300., minval=0., maxval=3600.)
        self.wipe_reference_offset = config.getfloat(
            'wipe_reference_offset', -2., minval=-3., maxval=0.)
        self.wipe_session_timeout = config.getfloat(
            'wipe_session_timeout', 900., above=0., maxval=1800.)
        self.heat_soak = {}
        self.wipe_session = {'ready': False}
        self.last_calibration = {'valid': False, 'applied': False}
        self.busy = False
        # This experiment deliberately has one fixed motion/sensor recipe.
        expected = ((self.speed, 25.), (self.accel, 300.),
                    (self.threshold_g, 1.75), (self.poll_rate, 2000.),
                    (self.arm_delay, .120), (self.duration_ms, 20.))
        if any(abs(actual - wanted) > 1.e-9 for actual, wanted in expected):
            raise config.error(
                'adxl345_z_offset requires 25mm/s, 300mm/s^2, 1.75g,'
                ' 2000Hz, 120ms arm delay and 20ms duration')
        if not self.align_probe_to_nozzle or self.pre_tap_lift != 5.:
            raise config.error('Z offset requires same-point PA11 and 5mm lift')
        if self.tap_samples != 3 or self.tap_samples_tolerance > .050:
            raise config.error('Z offset requires 3 samples and <=0.050 tolerance')
        for name, handler, description in (
                ('ADXL_Z_OFFSET', self.cmd_ADXL_Z_OFFSET,
                 'Soak bed, fixed non-contact check, fuzzed contact and offset'),
                ('ADXL_Z_OFFSET_CHECK', self.cmd_ADXL_Z_OFFSET_CHECK,
                 'Soak bed at BED_TEMP, PA11 home and test non-contact motion'),
                ('ADXL_Z_OFFSET_PREPARE_WIPE',
                 self.cmd_ADXL_Z_OFFSET_PREPARE_WIPE,
                 'Soak, PA11 home and authorize one post-wipe calibration'),
                ('ADXL_Z_OFFSET_STATUS', self.cmd_ADXL_Z_OFFSET_STATUS,
                 'Report the last pre-print calibration and sensor state'),
                ('ADAPTIVE_MESH_RESOLVE', self.cmd_ADAPTIVE_MESH_RESOLVE,
                 'Resolve Bambu PA calibration bounds before mesh planning')):
            self.gcode.register_command(name, handler, desc=description)

    def cmd_ADAPTIVE_MESH_RESOLVE(self, gcmd):
        resolve_mesh_command(self.printer, self.gcode, gcmd)

    def get_status(self, eventtime):
        result = ADXL345Tap.get_status(self, eventtime)
        result.update({'busy': self.busy,
                       'probe_speed': self.speed,
                       'probe_accel': self.accel,
                       'contact_start_mode': 'pa11_coarse_plus_5mm',
                       'contact_sample_groups': self.contact_sample_groups,
                       'heat_soak': dict(self.heat_soak),
                       'wipe_session': dict(self.wipe_session),
                       'last_calibration': dict(self.last_calibration)})
        return result

    def _check_wipe_session(self, gcmd, status, now):
        session = self.wipe_session
        if not session.get('ready'):
            raise gcmd.error('No prepared nozzle-wipe session; run'
                             ' ADXL_Z_OFFSET_PREPARE_WIPE first')
        if now > session.get('expires_at', 0.):
            self.wipe_session = {'ready': False, 'expired': True}
            raise gcmd.error('Prepared nozzle-wipe session expired')
        prepared_state = session.get('print_state')
        current_state = status.get('state')
        if prepared_state == 'printing':
            sdcard = self.printer.lookup_object('virtual_sdcard', None)
            if (current_state != 'printing' or sdcard is None
                    or not sdcard.is_cmd_from_sd()
                    or status.get('filename', '') != session.get('filename', '')):
                raise gcmd.error('Post-wipe calibration must continue from the'
                                 ' same SD print that prepared it')
        elif current_state in ('printing', 'paused'):
            raise gcmd.error('Console-prepared wipe session cannot cross into a print')

    def _check_start(self, gcmd, after_wipe=False):
        if self.busy:
            raise gcmd.error('ADXL Z offset already running')
        now = self.printer.get_reactor().monotonic()
        status = self.printer.lookup_object('print_stats').get_status(now)
        if status['state'] == 'paused':
            raise gcmd.error('ADXL Z offset is not available during a paused print')
        if after_wipe:
            self._check_wipe_session(gcmd, status, now)
        elif status['state'] == 'printing':
            sdcard = self.printer.lookup_object('virtual_sdcard', None)
            if (sdcard is None or not sdcard.is_cmd_from_sd()
                    or status['filament_used'] > .000001
                    or status['print_duration'] > 1.):
                raise gcmd.error(
                    'ADXL Z offset must run in slicer start G-code before'
                    ' any extrusion; it cannot run mid-print')
        if self.chip.is_measuring():
            raise gcmd.error('Stop accelerometer recording before calibration')

    def _set_offset(self, offset):
        self.gcode.run_script_from_command(
            'SET_GCODE_OFFSET Z=%.9f MOVE=0' % offset)
        self.gcode_move.reset_last_position()

    def _snapshot(self, label):
        toolhead = self.printer.lookup_object('toolhead')
        gc = self.gcode_move.get_status()
        mesh = self.printer.lookup_object('bed_mesh')
        snapshot = {
            'toolhead': list(toolhead.get_position()),
            'position': list(gc['position']),
            'gcode_position': list(gc['gcode_position']),
            'homing_origin': list(gc['homing_origin']),
            'profile': mesh.get_status()['profile_name'],
        }
        logging.info('ADXL Z offset %s: %s', label, snapshot)
        return snapshot

    def _safe_lift(self):
        toolhead = self.printer.lookup_object('toolhead')
        toolhead.manual_move(
            [None, None, max(self.home_z, toolhead.get_position()[2])],
            self.retract_speed)
        toolhead.wait_moves()
        self.gcode_move.reset_last_position()

    def _wait_for_heat_soak(self, gcmd, bed_temp, soak_seconds):
        reactor = self.printer.get_reactor()
        # ``heater_bed`` is a PrinterHeaterBed wrapper in stock Klipper;
        # temperature methods live on its underlying Heater instance.  Some
        # vendor forks expose the Heater directly, and a few expose it via
        # ``get_heater()`` (as the extruder object does), so normalize the
        # object before polling it.  Calling get_temp() on the wrapper raises
        # AttributeError and is reported by Klipper as an internal command
        # error, which used to shut the printer down during ADXL_Z_OFFSET.
        bed = self.printer.lookup_object('heater_bed')
        if not hasattr(bed, 'get_temp'):
            bed = getattr(bed, 'heater', bed)
        if not hasattr(bed, 'get_temp') and hasattr(bed, 'get_heater'):
            bed = bed.get_heater()
        if not hasattr(bed, 'get_temp'):
            raise gcmd.error('heater_bed object has no temperature interface')
        nozzle = self.printer.lookup_object('extruder').get_heater()
        toolhead = self.printer.lookup_object('toolhead')
        started = reactor.monotonic()
        stable_since = None
        next_report = started
        while True:
            now = reactor.monotonic()
            if self.printer.is_shutdown():
                raise gcmd.error('Printer shutdown during bed heat soak')
            actual, target = bed.get_temp(now)
            nozzle_temp, nozzle_target = nozzle.get_temp(now)
            if abs(target - bed_temp) > .01 or abs(nozzle_target - 140.) > .01:
                raise gcmd.error('Heater target changed during bed heat soak')
            in_band = abs(actual - bed_temp) <= 1.
            if in_band:
                if stable_since is None:
                    stable_since = now
            else:
                stable_since = None
            elapsed = 0. if stable_since is None else now - stable_since
            self.heat_soak = {'bed_target': bed_temp, 'bed_temperature': actual,
                              'required_seconds': soak_seconds,
                              'stable_seconds': elapsed, 'complete': False}
            if (in_band and elapsed >= soak_seconds
                    and abs(nozzle_temp - 140.) <= 2.):
                self.heat_soak['complete'] = True
                gcmd.respond_info('ADXL bed heat soak complete: %.1fC, %.0fs stable'
                                  % (bed_temp, elapsed))
                return
            if now - started > 1800. + soak_seconds:
                raise gcmd.error('Timed out waiting for stable bed temperature')
            if now >= next_report:
                gcmd.respond_info('ADXL bed heat soak: bed=%.1f/%.1fC stable=%.0f/%.0fs'
                                  % (actual, bed_temp, elapsed, soak_seconds))
                next_report = now + 30.
            # Keep the same MCU/idle-timeout activity as TEMPERATURE_WAIT;
            # reactor.pause keeps status and shutdown handling responsive.
            toolhead.get_last_move_time()
            reactor.pause(now + 1.)

    def _heat_and_home(self, gcmd, bed_temp, soak_seconds):
        # Full G28 intentionally homes real XY despite vendor fake homed_axes.
        self.gcode.run_script_from_command(
            'SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=%.3f\n'
            'SET_HEATER_TEMPERATURE HEATER=extruder TARGET=140' % bed_temp)
        self._wait_for_heat_soak(gcmd, bed_temp, soak_seconds)
        self.gcode.run_script_from_command('G28')
        self._set_offset(0.)
        self._safe_lift()

    def _run_coarse_probe(self, gcmd, tap_xy):
        # Leave the nozzle at safe Z after alignment. Do not drop to coarse_z
        # just to lift again at the beginning of the first Tap.
        probe = self.printer.lookup_object('probe')
        toolhead = self.printer.lookup_object('toolhead')
        offsets = probe.get_offsets()
        probe_xy = (tap_xy[0] - offsets[0], tap_xy[1] - offsets[1])
        status = toolhead.get_status(self.printer.get_reactor().monotonic())
        for xy in (tap_xy, probe_xy):
            if any(not status['axis_minimum'][i] <= xy[i]
                   <= status['axis_maximum'][i] for i in (0, 1)):
                raise gcmd.error('Same-point PA11/nozzle alignment exceeds XY limits')
        self._safe_lift()
        toolhead.manual_move([probe_xy[0], probe_xy[1], None], self.xy_speed)
        toolhead.wait_moves()
        coarse_pos = probe.run_probe(gcmd)
        toolhead.manual_move(
            [None, None, coarse_pos[2] + self.pre_tap_lift], self.retract_speed)
        toolhead.manual_move([tap_xy[0], tap_xy[1], None], self.xy_speed)
        toolhead.wait_moves()
        self.gcode_move.reset_last_position()
        # The historical floor is raw toolhead Z after PA11 G28 (offset zero).
        # Reject an unexpected coordinate regime rather than translating or
        # relaxing that fixed floor.
        if not -.5 <= coarse_pos[2] <= .5:
            raise gcmd.error('Unexpected PA11 coarse Z %.6f; check coordinates'
                             % coarse_pos[2])
        return coarse_pos, probe_xy

    def _recover_contact_group(self, gcmd, contact_xy, print_context):
        # _run_tap_move already retracts and restores acceleration in finally.
        # Do not interpret an unknown position or incomplete recovery as retryable.
        if self.printer.is_shutdown():
            raise gcmd.error('Printer shutdown; ADXL contact retry is unavailable')
        now = self.printer.get_reactor().monotonic()
        current_print = self.printer.lookup_object('print_stats').get_status(now)
        if (current_print.get('state') == 'paused'
                or (current_print.get('state'), current_print.get('filename', ''))
                != print_context):
            raise gcmd.error('Print state changed; ADXL contact retry is unavailable')
        toolhead = self.printer.lookup_object('toolhead')
        toolhead.wait_moves()
        status = toolhead.get_status(now)
        position = toolhead.get_position()
        if (not all(axis in status['homed_axes'] for axis in 'xyz')
                or any(math.isnan(v) or math.isinf(v) for v in position[:3])
                or abs(self.gcode_move.get_status()['homing_origin'][2]) > 1.e-6
                or any(abs(position[i] - contact_xy[i]) > .05 for i in (0, 1))
                or position[2] < self.probe_min_z + self.retract_dist - .05
                or position[2] > status['axis_maximum'][2]
                or self.home_z > status['axis_maximum'][2]):
            raise gcmd.error('Unsafe ADXL recovery coordinates; refusing contact retry')
        self._disarm_sensor()
        self._safe_lift()

    def _position_contact_start(self, gcmd, coarse_pos, contact_xy):
        # The legacy Tap core starts from whatever height the last 5mm retract
        # reached. This pre-print path deliberately normalizes EVERY sample.
        if self.printer.is_shutdown():
            raise gcmd.error('Printer shutdown before ADXL contact start positioning')
        toolhead = self.printer.lookup_object('toolhead')
        toolhead.wait_moves()
        now = self.printer.get_reactor().monotonic()
        status = toolhead.get_status(now)
        position = toolhead.get_position()
        start_z = coarse_pos[2] + self.pre_tap_lift
        if (not all(axis in status['homed_axes'] for axis in 'xyz')
                or any(math.isnan(v) or math.isinf(v)
                       for v in position[:3] + [start_z, coarse_pos[2]])
                or not -.5 <= coarse_pos[2] <= .5
                or abs(self.gcode_move.get_status()['homing_origin'][2]) > 1.e-6
                or any(abs(position[i] - contact_xy[i]) > .05 for i in (0, 1))
                or position[2] < self.probe_min_z + self.retract_dist - .05
                or position[2] > status['axis_maximum'][2]
                or not self.probe_min_z < start_z <= status['axis_maximum'][2]):
            raise gcmd.error('Unsafe coordinates before fixed-height ADXL contact')
        # No sensor armed during positioning; the Tap core arms after it ends.
        self._disarm_sensor()
        toolhead.manual_move([None, None, start_z], self.retract_speed)
        toolhead.wait_moves()
        self.gcode_move.reset_last_position()
        actual = toolhead.get_position()
        if (any(math.isnan(v) or math.isinf(v) for v in actual[:3])
                or abs(actual[2] - start_z) > .01
                or any(abs(actual[i] - contact_xy[i]) > .05 for i in (0, 1))):
            raise gcmd.error('ADXL contact start position was not reached')
        return start_z

    def _sample_contact(self, gcmd, contact_xy):
        now = self.printer.get_reactor().monotonic()
        initial_print = self.printer.lookup_object('print_stats').get_status(now)
        print_context = (initial_print.get('state'), initial_print.get('filename', ''))
        max_groups = self.contact_sample_groups
        coarse_pos, probe_xy = self._run_coarse_probe(gcmd, contact_xy)
        for attempt in range(max_groups):
            results = []
            no_trigger = False
            for sample in range(self.tap_samples):
                try:
                    start_z = self._position_contact_start(gcmd, coarse_pos, contact_xy)
                    gcmd.respond_info(
                        'ADXL contact start: group=%d/%d sample=%d/%d'
                        ' raw_z=%.6f PA11_coarse_z=%.6f clearance=%.3f'
                        % (attempt + 1, max_groups, sample + 1, self.tap_samples,
                           start_z, coarse_pos[2], self.pre_tap_lift))
                    result = self._run_tap_move(
                        gcmd, coarse_pos, contact_xy, probe_xy, self.accel)
                except self.printer.command_error as exc:
                    if str(exc) != ('ADXL Tap probe failed: '
                                    'No trigger on probe after full movement'):
                        raise
                    no_trigger = True
                    gcmd.respond_info(
                        'ADXL Z offset group: attempt=%d/%d sample=%d/%d'
                        ' NO_TRIGGER; discard %d valid sample(s)'
                        % (attempt + 1, max_groups, sample + 1,
                           self.tap_samples, len(results)))
                    break
                if not result['state'].get('int_source', 0) & SINGLE_TAP:
                    raise gcmd.error('Tap result has no Single Tap event')
                self._respond_tap_result(gcmd, result)
                results.append(result)
            if no_trigger:
                if attempt + 1 >= max_groups:
                    raise gcmd.error('ADXL Z offset failed after %d sample groups:'
                                     ' No trigger on probe after full movement'
                                     % max_groups)
                self._recover_contact_group(gcmd, contact_xy, print_context)
                # Keep the same fuzz point; refresh its PA11 reference, never
                # deepen the absolute probe floor or reuse a partial group.
                coarse_pos, probe_xy = self._run_coarse_probe(gcmd, contact_xy)
                continue
            values = sorted(r['trigger_pos'][2] for r in results)
            spread = values[-1] - values[0]
            gcmd.respond_info(
                'ADXL Z offset group: attempt=%d samples=%s range=%.6f %s'
                % (attempt + 1, ','.join('%.6f' % z for z in values), spread,
                   'ACCEPT' if spread <= self.tap_samples_tolerance + 1.e-9
                   else 'REJECT'))
            if spread <= self.tap_samples_tolerance + 1.e-9:
                return values[1], spread, results, attempt + 1
        raise gcmd.error('ADXL Z offset sample groups exceeded tolerance')

    def _check_profile_covers_contact(self, gcmd, mesh, profile, contact_xy):
        profile_data = mesh.pmgr.get_profiles().get(profile, {})
        params = profile_data.get('mesh_params', {})
        required = ('min_x', 'min_y', 'max_x', 'max_y')
        if any(name not in params for name in required):
            raise gcmd.error('PA11 mesh [%s] has no usable XY bounds' % profile)
        x, y = contact_xy
        tolerance = 1.e-6
        if not (params['min_x'] - tolerance <= x <= params['max_x'] + tolerance
                and params['min_y'] - tolerance <= y <= params['max_y'] + tolerance):
            raise gcmd.error(
                'ADXL contact XY %.2f,%.2f is outside PA11 mesh [%s]'
                ' bounds %.2f,%.2f..%.2f,%.2f'
                % (x, y, profile, params['min_x'], params['min_y'],
                   params['max_x'], params['max_y']))

    def _no_contact(self, gcmd, count):
        toolhead = self.printer.lookup_object('toolhead')
        self._safe_lift()
        toolhead.manual_move(
            [self.home_xy[0], self.home_xy[1], None], self.xy_speed)
        toolhead.wait_moves()
        for sample in range(count):
            start = toolhead.get_position()
            target = list(start)
            target[2] -= 5.
            if target[2] < 5.:
                raise gcmd.error('Non-contact diagnostic must remain above raw Z5')
            old_accel = toolhead.get_max_velocity()[1]
            triggered = False
            try:
                self._set_accel(self.accel)
                self._prepare_sensor()
                try:
                    self.printer.lookup_object('homing').probing_move(
                        self.endstop, target, self.speed)
                    triggered = True
                except self.printer.command_error as exc:
                    if 'No trigger on probe after full movement' not in str(exc):
                        raise
            finally:
                self._disarm_sensor()
                try:
                    if not self.printer.is_shutdown():
                        toolhead.manual_move([None, None, start[2]], self.retract_speed)
                        toolhead.wait_moves()
                finally:
                    self.gcode_move.reset_last_position()
                    self._set_accel(old_accel)
            if triggered:
                raise gcmd.error('ADXL false trigger in high-Z non-contact check')
            gcmd.respond_info('ADXL non-contact %d/%d: CLEAR (25/300/1.75g/2kHz/120ms)'
                              % (sample + 1, count))

    def _execute(self, gcmd, check_only=False):
        # Consume only documented options: no hidden override of Tap recipe.
        allowed = {'COUNT'} if check_only else {'PROFILE', 'APPLY', 'FUZZ'}
        allowed.update(('BED_TEMP', 'SOAK'))
        if not check_only:
            allowed.add('AFTER_WIPE')
        unknown = set(gcmd.get_command_parameters()) - allowed
        if unknown:
            raise gcmd.error('Unknown ADXL Z offset parameter(s): %s'
                             % ','.join(sorted(unknown)))
        after_wipe = (False if check_only else
                      bool(gcmd.get_int('AFTER_WIPE', 0, minval=0, maxval=1)))
        self._check_start(gcmd, after_wipe=after_wipe)
        apply = False if check_only else bool(gcmd.get_int('APPLY', 1, minval=0, maxval=1))
        count = gcmd.get_int('COUNT', 1, minval=1, maxval=20) if check_only else 1
        bed_temp = gcmd.get_float('BED_TEMP', 60., minval=1., maxval=100.)
        soak_seconds = gcmd.get_float(
            'SOAK', self.bed_soak_seconds, minval=0., maxval=3600.)
        contact_fuzz = (0. if check_only else
                        gcmd.get_float('FUZZ', self.contact_fuzz,
                                       minval=0., maxval=3.))
        if any(math.isnan(v) or math.isinf(v)
               for v in (bed_temp, soak_seconds, contact_fuzz)):
            raise gcmd.error('BED_TEMP, SOAK and FUZZ must be finite')
        mesh = self.printer.lookup_object('bed_mesh')
        profile = None if check_only else gcmd.get('PROFILE', self.profile)
        if not check_only and profile not in mesh.pmgr.get_profiles():
            raise gcmd.error('Saved PA11 mesh [%s] is missing; create/load it first' % profile)
        contact_xy = None
        if not check_only:
            try:
                contact_xy = choose_contact_xy(tuple(self.home_xy), contact_fuzz)
            except ValueError as exc:
                raise gcmd.error(str(exc))
            self._check_profile_covers_contact(gcmd, mesh, profile, contact_xy)
        if after_wipe:
            if not self.wipe_session.get('ready'):
                raise gcmd.error('Prepared nozzle-wipe session is not ready')
            if not apply:
                raise gcmd.error('Post-wipe calibration must use APPLY=1')
            if abs(soak_seconds) > 1.e-9:
                raise gcmd.error('Post-wipe calibration requires SOAK=0')
            prepared_bed = self.wipe_session.get('bed_target')
            if prepared_bed is None or abs(prepared_bed - bed_temp) > .01:
                raise gcmd.error('Post-wipe BED_TEMP differs from prepared session')
            # Single-use authorization. Unhandled motion, sensor or temperature
            # failures require a fresh prepare cycle. Bounded internal contact
            # group retries do not renew or reuse this authorization.
            self.wipe_session['ready'] = False
            self.wipe_session['consumed'] = True
        old_mesh = mesh.z_mesh
        old_profile = mesh.pmgr.get_current_profile()
        old_offset = self.gcode_move.get_status()['homing_origin'][2]
        original_accel = self.printer.lookup_object('toolhead').get_max_velocity()[1]
        self.last_calibration = {'valid': False, 'applied': False}
        self.busy = True
        homed = False
        succeeded = False
        try:
            self._disarm_sensor()
            mesh.set_mesh(None)
            self._heat_and_home(gcmd, bed_temp, soak_seconds)
            homed = True
            before = self._snapshot('PA11 homed, mesh OFF, offset 0')
            # A short fixed-recipe false-trigger gate is not parameter tuning.
            self._no_contact(gcmd, count)
            if check_only:
                succeeded = True
                return
            # The high-Z false-trigger check above always stays at home_xy.
            # Only the real PA11-aligned nozzle contacts use the one randomly
            # selected point, held constant for all samples and retries.
            gcmd.respond_info(
                'ADXL contact fuzz: center=%.2f,%.2f fuzz=%.2f selected=%.2f,%.2f'
                % (self.home_xy[0], self.home_xy[1], contact_fuzz,
                   contact_xy[0], contact_xy[1]))
            tap_z, spread, results, attempts = self._sample_contact(
                gcmd, contact_xy)
            self._safe_lift()
            mesh.pmgr.load_profile(profile)
            mesh_z = mesh.z_mesh.calc_z(*contact_xy)
            try:
                offset = calculate_offset(
                    tap_z, mesh_z, self.baseline, self.max_deviation, self.contact_trim)
            except ValueError as exc:
                raise gcmd.error(str(exc))
            # Formula assumes the first layer lies below fade_start in the
            # transform's coordinates. Reject unusual meshes/configurations.
            if mesh.get_z_factor(offset + 1.) != 1.:
                raise gcmd.error('Mesh fade is active at first-layer height')
            physical_before = list(self.printer.lookup_object('toolhead').get_position())
            self._set_offset(offset if apply else old_offset)
            physical_after = self.printer.lookup_object('toolhead').get_position()
            if physical_after != physical_before:
                raise gcmd.error('Unexpected physical motion while applying MOVE=0 offset')
            after = self._snapshot('calibration applied' if apply else 'preview')
            self.last_calibration = {
                'valid': True, 'applied': apply, 'offset': offset,
                'after_wipe': after_wipe,
                'previous_offset': old_offset, 'manual_baseline': self.baseline,
                'bed_target': bed_temp, 'heat_soak_seconds': soak_seconds,
                'tap_z': tap_z, 'mesh_z': mesh_z, 'contact_trim': self.contact_trim,
                'contact_xy': list(contact_xy), 'contact_fuzz': contact_fuzz,
                'sample_range': spread, 'attempts': attempts,
                'samples': [r['trigger_pos'][2] for r in results],
                'profile': profile, 'before': before, 'after': after,
            }
            gcmd.respond_info(
                'ADXL Z offset %s: tap_z=%.6f mesh_z=%.6f trim=%.6f'
                ' offset=%.6f previous=%.6f baseline=%.6f range=%.6f profile=%s'
                ' contact_xy=%.2f,%.2f fuzz=%.2f'
                % ('APPLIED' if apply else 'PREVIEW', tap_z, mesh_z,
                   self.contact_trim, offset, old_offset, self.baseline, spread,
                   profile, contact_xy[0], contact_xy[1], contact_fuzz))
            succeeded = True
        except Exception as exc:
            self.last_calibration = {'valid': False, 'applied': False, 'error': str(exc)}
            raise
        finally:
            self._disarm_sensor()
            try:
                if not self.printer.is_shutdown():
                    try:
                        if homed:
                            self._safe_lift()
                    except Exception:
                        succeeded = False
                        raise
                    finally:
                        try:
                            if not succeeded or check_only:
                                mesh.pmgr.current_profile = old_profile
                                mesh.set_mesh(old_mesh)
                                self._set_offset(old_offset)
                        finally:
                            self._set_accel(original_accel)
            except Exception as exc:
                succeeded = False
                self.last_calibration = {
                    'valid': False, 'applied': False, 'error': str(exc)}
                raise
            finally:
                self.busy = False
                if not succeeded and not self.printer.is_shutdown():
                    self.gcode.run_script_from_command('TURN_OFF_HEATERS')

    def cmd_ADXL_Z_OFFSET(self, gcmd):
        self._execute(gcmd)

    def cmd_ADXL_Z_OFFSET_CHECK(self, gcmd):
        self._execute(gcmd, check_only=True)

    def cmd_ADXL_Z_OFFSET_PREPARE_WIPE(self, gcmd):
        self.wipe_session = {'ready': False}
        self._execute(gcmd, check_only=True)
        self._set_offset(self.wipe_reference_offset)
        now = self.printer.get_reactor().monotonic()
        status = self.printer.lookup_object('print_stats').get_status(now)
        bed_temp = gcmd.get_float('BED_TEMP', 60., minval=1., maxval=100.)
        self.wipe_session = {
            'ready': True,
            'prepared_at': now,
            'expires_at': now + self.wipe_session_timeout,
            'timeout': self.wipe_session_timeout,
            'bed_target': bed_temp,
            'reference_offset': self.wipe_reference_offset,
            'print_state': status.get('state'),
            'filename': status.get('filename', ''),
        }
        gcmd.respond_info(
            'Nozzle-wipe session prepared: temporary_offset=%.6f'
            ' expires_in=%.0fs' %
            (self.wipe_reference_offset, self.wipe_session_timeout))

    def cmd_ADXL_Z_OFFSET_STATUS(self, gcmd):
        self.cmd_ADXL_TAP_QUERY(gcmd)
        gcmd.respond_info('ADXL Z offset: %s' % self.last_calibration)
        gcmd.respond_info('ADXL nozzle-wipe session: %s' % self.wipe_session)


def load_config(config):
    return ADXL345ZOffset(config)
