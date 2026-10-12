"""Coordinate and failure-path regression checks; no printer connection."""
import importlib
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source' / 'klipper' / 'klippy'))
sys.modules.setdefault('chelper', SimpleNamespace())
sys.modules.setdefault('mcu', SimpleNamespace())
module = importlib.import_module('extras.adxl345_z_offset')
gmove_module = importlib.import_module('extras.gcode_move')


class Command:
    error = RuntimeError

    def __init__(self, **params):
        self.params = params
        self.messages = []

    def get(self, name, default=None):
        return self.params.get(name, default)

    def get_float(self, name, default=None, **limits):
        value = self.get(name, default)
        if value is None:
            return None
        value = float(value)
        if 'minval' in limits and value < limits['minval']:
            raise self.error('out of bounds')
        if 'maxval' in limits and value > limits['maxval']:
            raise self.error('out of bounds')
        return value

    def get_int(self, name, default=None, **limits):
        value = int(self.get(name, default))
        if 'minval' in limits and value < limits['minval']:
            raise self.error('out of bounds')
        if 'maxval' in limits and value > limits['maxval']:
            raise self.error('out of bounds')
        return value

    def get_command_parameters(self):
        return self.params

    def respond_info(self, message):
        self.messages.append(message)


class CoordinateTests(unittest.TestCase):
    def test_current_probe_recipe_is_synchronized(self):
        cfg = (ROOT / 'config/reference/adxl345_z_offset.cfg').read_text(encoding='utf-8')
        source = (ROOT / 'source/klipper/klippy/extras/adxl345_z_offset.py'
                  ).read_text(encoding='utf-8')
        self.assertIn('\nspeed: 25\n', cfg)
        self.assertIn('\naccel: 300\n', cfg)
        self.assertIn('expected = ((self.speed, 25.), (self.accel, 300.),', source)
        self.assertIn('requires 25mm/s, 300mm/s^2', source)
        self.assertIn('CLEAR (25/300/1.75g/2kHz/120ms)', source)
        self.assertNotIn('requires 30mm/s', source)

    def test_contact_fuzz_is_bounded_and_has_point_zero_one_mm_resolution(self):
        choices = iter((-300, 300))
        point = module.choose_contact_xy(
            (239.25, 194.55), 3., lambda low, high: next(choices))
        self.assertEqual(point, (236.25, 197.55))

        called = []
        self.assertEqual(
            module.choose_contact_xy(
                (239.25, 194.55), 0.,
                lambda low, high: called.append((low, high))),
            (239.25, 194.55))
        self.assertEqual(called, [])
        with self.assertRaisesRegex(ValueError, '0..3mm'):
            module.choose_contact_xy((239.25, 194.55), 3.01)

    def test_contact_plane_and_no_accumulation_using_vendor_gcode_move(self):
        # Exercise the actual matching vendor SET_GCODE_OFFSET and G1 code.
        gm = gmove_module.GCodeMove.__new__(gmove_module.GCodeMove)
        gm.homing_position = [0., 0., -2., 0.]
        gm.base_position = [0., 0., -2., 0.]
        gm.last_position = [239.25, 194.55, 10., 0.]
        gm.absolute_coord = gm.absolute_extrude = True
        gm.speed = 5.
        gm.extrude_factor = 1.
        positions = []
        mesh_z = .075
        gm.move_with_transform = lambda pos, speed: positions.append(
            pos[2] + mesh_z)
        offset = module.calculate_offset(-2.10, mesh_z, -2., .5)
        self.assertAlmostEqual(offset, -2.175)
        for _ in range(3):
            gm.cmd_SET_GCODE_OFFSET(Command(Z=offset, MOVE=0))
            gm.cmd_G1(Command(Z=.2))
            self.assertAlmostEqual(positions[-1], -2.10 + .2)
            self.assertAlmostEqual(gm.homing_position[2], -2.175)
        # MOVE=0 itself never queued a move.
        self.assertEqual(len(positions), 3)

    def test_mesh_reference_and_trim(self):
        for mesh_z in (-.2, 0., .2):
            self.assertAlmostEqual(
                module.calculate_offset(-2.1, mesh_z, -2., .5) + mesh_z,
                -2.1)
        self.assertAlmostEqual(module.calculate_offset(-2.1, .1, -2., .5, .03), -2.17)

    def test_bad_coordinates_rejected(self):
        for tap_z in (-9.39, 0., math.nan, math.inf):
            with self.assertRaises(ValueError):
                module.calculate_offset(tap_z, 0., -2., .5)


def harness():
    obj = module.ADXL345ZOffset.__new__(module.ADXL345ZOffset)
    obj.profile = 'default'
    obj.bed_soak_seconds = 300.
    obj.wipe_reference_offset = -2.
    obj.wipe_session_timeout = 900.
    obj.wipe_session = {'ready': False}
    obj.baseline, obj.max_deviation, obj.contact_trim = -2., .5, 0.
    obj.contact_fuzz = 3.
    obj.pre_tap_lift = 5.
    obj.contact_sample_groups = 3
    obj.home_xy = (239.25, 194.55)
    obj.busy = False
    obj.last_calibration = {}
    obj.calls = []
    old_mesh = SimpleNamespace(calc_z=lambda *xy: .04)
    selected_mesh = SimpleNamespace(calc_z=lambda *xy: .075)
    mesh_params = {'min_x': 20., 'min_y': 30.,
                   'max_x': 395., 'max_y': 400.}
    manager = SimpleNamespace(current_profile='old')
    manager.get_profiles = lambda: {
        'default': {'mesh_params': mesh_params},
        'old': {'mesh_params': mesh_params}}
    manager.get_current_profile = lambda: manager.current_profile
    mesh = SimpleNamespace(z_mesh=old_mesh, pmgr=manager,
                           get_z_factor=lambda z: 1.)
    mesh.set_mesh = lambda value: setattr(mesh, 'z_mesh', value)
    def load(profile):
        manager.current_profile = profile
        mesh.set_mesh(selected_mesh)
    manager.load_profile = load
    position = [239.25, 194.55, 10., 0.]
    toolhead = SimpleNamespace(get_position=lambda: list(position),
                              get_max_velocity=lambda: (500., 2000.))
    reactor = SimpleNamespace(monotonic=lambda: 123.)
    print_status = {'state': 'standby', 'filename': ''}
    objects = {
        'bed_mesh': mesh,
        'toolhead': toolhead,
        'print_stats': SimpleNamespace(get_status=lambda t: print_status),
    }
    obj.printer = SimpleNamespace(
        get_reactor=lambda: reactor,
        lookup_object=lambda name: objects[name], is_shutdown=lambda: False,
        command_error=RuntimeError)
    obj.offset = -2.
    obj.gcode_move = SimpleNamespace(get_status=lambda: {'homing_origin': [0., 0., obj.offset, 0.]})
    obj.gcode = SimpleNamespace(run_script_from_command=lambda s: obj.calls.append(s))
    def set_offset(value):
        obj.offset = value
        obj.calls.append(('offset', value))
    obj._set_offset = set_offset
    obj._check_start = lambda gcmd, after_wipe=False: None
    obj._disarm_sensor = lambda: obj.calls.append('disarm')
    obj._heat_and_home = lambda *args: set_offset(0.)
    obj._safe_lift = lambda: obj.calls.append('lift')
    obj._set_accel = lambda value: obj.calls.append(('accel', value))
    obj._snapshot = lambda label: {'label': label}
    obj._no_contact = lambda gcmd, count: obj.calls.append('noncontact')
    obj._position_contact_start = lambda gcmd, coarse, xy: coarse[2] + 5.
    obj._sample_contact = lambda gcmd, contact_xy: (
        -2.10, .01, [{'trigger_pos': [contact_xy[0], contact_xy[1], z]}
                    for z in (-2.10, -2.105, -2.095)], 1)
    return obj, mesh, old_mesh


class ContactGroupRetryTests(unittest.TestCase):
    def make_contact(self, events):
        obj, mesh, old_mesh = harness()
        obj.tap_samples, obj.tap_samples_tolerance, obj.accel = 3, .05, 300.
        obj.probe_min_z, obj.retract_dist, obj.home_z = -3.5, 5., 10.
        obj.pre_tap_lift, obj.retract_speed = 5., 5.
        obj.offset = 0.
        toolhead = obj.printer.lookup_object('toolhead')
        position = list(obj.home_xy) + [5.06, 0.]
        toolhead.get_position = lambda: list(position)
        def manual_move(target, speed):
            for index, value in enumerate(target):
                if value is not None:
                    position[index] = value
        toolhead.manual_move = manual_move
        toolhead.wait_moves = lambda: None
        toolhead.get_status = lambda now: {
            'homed_axes': 'xyz', 'axis_maximum': [430., 430., 482.5]}
        coarse_calls, tap_calls = [], []
        obj.contact_starts = []
        obj.gcode_move.reset_last_position = lambda: None
        obj._position_contact_start = lambda gcmd, coarse, xy: (
            module.ADXL345ZOffset._position_contact_start(obj, gcmd, coarse, xy))
        def coarse(gcmd, point):
            coarse_calls.append(point)
            position[:3] = [point[0], point[1], 5.06]
            return [point[0], point[1], .06], (point[0] + 24.25, point[1] - 20.45)
        obj._run_coarse_probe = coarse
        obj._respond_tap_result = lambda *args: None
        remaining = iter(events)
        def tap(*args):
            tap_calls.append(args[2])
            obj.contact_starts.append(toolhead.get_position()[2])
            event = next(remaining)
            if isinstance(event, Exception):
                position[2] = obj.probe_min_z + obj.retract_dist
                raise event
            position[2] = event + obj.retract_dist
            return {'trigger_pos': [args[2][0], args[2][1], event],
                    'state': {'int_source': 0x40}}
        obj._run_tap_move = tap
        obj._sample_contact = lambda gcmd, point: (
            module.ADXL345ZOffset._sample_contact(obj, gcmd, point))
        return obj, coarse_calls, tap_calls

    def no_trigger(self):
        return RuntimeError('ADXL Tap probe failed: '
                            'No trigger on probe after full movement')

    def test_third_sample_no_trigger_discards_partial_group_then_applies(self):
        obj, coarse, taps = self.make_contact(
            [-2.12, -2.09, self.no_trigger(), -2.10, -2.105, -2.095])
        obj._execute(Command(FUZZ=0, SOAK=0))
        self.assertTrue(obj.last_calibration['applied'])
        self.assertEqual(obj.last_calibration['attempts'], 2)
        self.assertEqual(obj.last_calibration['samples'], [-2.10, -2.105, -2.095])
        self.assertEqual(len(coarse), 2)
        self.assertEqual(len(taps), 6)
        self.assertTrue(all(point == obj.home_xy for point in coarse + taps))

    def test_third_group_can_succeed_without_exceeding_nine_moves(self):
        obj, coarse, taps = self.make_contact(
            [-2.12, -2.09, self.no_trigger(),
             -2.11, -2.10, self.no_trigger(), -2.10, -2.105, -2.095])
        result = obj._sample_contact(Command(), obj.home_xy)
        self.assertEqual(result[3], 3)
        self.assertEqual(len(coarse), 3)
        self.assertEqual(len(taps), 9)
        self.assertEqual(obj.contact_starts, [5.06] * 9)

    def test_all_three_samples_start_at_first_sample_height(self):
        obj, coarse, taps = self.make_contact([-2.12, -2.09, -2.10])
        obj._sample_contact(Command(), obj.home_xy)
        self.assertEqual(obj.contact_starts, [5.06] * 3)
        self.assertEqual(len(coarse), 1)

    def test_unreached_fixed_height_blocks_probe(self):
        obj, coarse, taps = self.make_contact([-2.12, -2.09, -2.10])
        obj.printer.lookup_object('toolhead').manual_move = lambda *args: None
        # First sample starts at the coarse lift; after retract the second
        # start is lower and the deliberately failed normalization must abort.
        with self.assertRaisesRegex(RuntimeError, 'start position was not reached'):
            obj._sample_contact(Command(), obj.home_xy)
        self.assertEqual(len(taps), 1)

    def test_three_failed_groups_abort_without_a_fourth_group(self):
        obj, coarse, taps = self.make_contact([self.no_trigger()] * 3)
        with self.assertRaisesRegex(RuntimeError, 'after 3 sample groups'):
            obj._sample_contact(Command(), obj.home_xy)
        self.assertEqual(len(coarse), 3)
        self.assertEqual(len(taps), 3)
        self.assertEqual(obj.calls.count('lift'), 2)

    def test_communication_and_contact_window_errors_are_not_retried(self):
        for error in ('ADXL Tap probe failed: Communication timeout',
                      'ADXL Tap contact offset outside valid window',
                      'recovery move failed'):
            with self.subTest(error=error):
                obj, coarse, taps = self.make_contact([RuntimeError(error)])
                with self.assertRaisesRegex(RuntimeError, error):
                    obj._sample_contact(Command(), obj.home_xy)
                self.assertEqual(len(coarse), 1)
                self.assertEqual(len(taps), 1)
                self.assertNotIn('lift', obj.calls)

    def test_unknown_recovery_position_or_shutdown_blocks_next_contact(self):
        for fault in ('shutdown', 'xy', 'z', 'homed', 'offset', 'paused'):
            with self.subTest(fault=fault):
                obj, coarse, taps = self.make_contact([self.no_trigger()])
                toolhead = obj.printer.lookup_object('toolhead')
                if fault == 'shutdown':
                    obj.printer.is_shutdown = lambda: True
                elif fault == 'xy':
                    toolhead.get_position = lambda: [100., 100., 10., 0.]
                elif fault == 'z':
                    toolhead.get_position = lambda: list(obj.home_xy) + [-3.5, 0.]
                elif fault == 'homed':
                    toolhead.get_status = lambda now: {'homed_axes': 'xy'}
                elif fault == 'offset':
                    obj.offset = -2.
                elif fault == 'paused':
                    stats = obj.printer.lookup_object('print_stats')
                    stats.get_status = lambda now: {'state': 'paused', 'filename': ''}
                with self.assertRaises(RuntimeError):
                    obj._sample_contact(Command(), obj.home_xy)
                self.assertLessEqual(len(taps), 1)
                self.assertEqual(len(coarse), 1)

    def test_recovery_lift_failure_blocks_next_contact(self):
        obj, coarse, taps = self.make_contact([self.no_trigger()])
        def fail_lift():
            raise RuntimeError('recovery lift failed')
        obj._safe_lift = fail_lift
        with self.assertRaisesRegex(RuntimeError, 'recovery lift failed'):
            obj._sample_contact(Command(), obj.home_xy)
        self.assertEqual(len(taps), 1)
        self.assertEqual(len(coarse), 1)


class HeatSoakTests(unittest.TestCase):
    def make_soak(self, temperature, target=lambda t: 70., shutdown=lambda t: False):
        obj = module.ADXL345ZOffset.__new__(module.ADXL345ZOffset)
        clock = [0.]
        reactor = SimpleNamespace(monotonic=lambda: clock[0],
                                  pause=lambda t: clock.__setitem__(0, t))
        # Match stock Klipper: heater_bed is a wrapper and the actual
        # temperature API belongs to its ``heater`` member.
        bed_heater = SimpleNamespace(
            get_temp=lambda t: (temperature(t), target(t)))
        objects = {
            'heater_bed': SimpleNamespace(heater=bed_heater),
            'extruder': SimpleNamespace(get_heater=lambda: SimpleNamespace(
                get_temp=lambda t: (140., 140.))),
            'toolhead': SimpleNamespace(get_last_move_time=lambda: 0.)}
        obj.printer = SimpleNamespace(get_reactor=lambda: reactor,
                                      lookup_object=lambda name: objects[name],
                                      is_shutdown=lambda: shutdown(clock[0]))
        return obj, clock

    def test_wrapped_bed_heater_is_supported(self):
        obj, clock = self.make_soak(lambda t: 70.)
        bed_wrapper = obj.printer.lookup_object('heater_bed')
        self.assertFalse(hasattr(bed_wrapper, 'get_temp'))
        obj._wait_for_heat_soak(Command(), 70., 0.)
        self.assertEqual(clock[0], 0.)

    def test_counts_only_time_at_target(self):
        obj, clock = self.make_soak(lambda t: 60. if t < 10. else 70.)
        obj._wait_for_heat_soak(Command(), 70., 300.)
        self.assertEqual(clock[0], 310.)
        self.assertTrue(obj.heat_soak['complete'])

    def test_temperature_excursion_restarts_soak(self):
        obj, clock = self.make_soak(lambda t: 72. if 50. <= t < 60. else 70.)
        obj._wait_for_heat_soak(Command(), 70., 300.)
        self.assertEqual(clock[0], 360.)

    def test_target_change_aborts(self):
        obj, clock = self.make_soak(lambda t: 70.,
                                   target=lambda t: 0. if t >= 5. else 70.)
        with self.assertRaisesRegex(RuntimeError, 'target changed'):
            obj._wait_for_heat_soak(Command(), 70., 300.)
        self.assertEqual(clock[0], 5.)

    def test_shutdown_aborts_before_homing(self):
        obj, clock = self.make_soak(lambda t: 70., shutdown=lambda t: t >= 3.)
        with self.assertRaisesRegex(RuntimeError, 'shutdown'):
            obj._wait_for_heat_soak(Command(), 70., 300.)
        self.assertEqual(clock[0], 3.)


class LifecycleTests(unittest.TestCase):
    def test_slicer_bed_temperature_and_soak_pass_through(self):
        obj, _, _ = harness()
        args = []
        obj._heat_and_home = lambda gcmd, target, soak: args.append((target, soak))
        obj._execute(Command(BED_TEMP=70, SOAK=600))
        self.assertEqual(args, [(70., 600.)])
        self.assertEqual(obj.last_calibration['bed_target'], 70.)

    def test_apply_and_repeat(self):
        obj, mesh, _ = harness()
        for _ in range(2):
            obj._execute(Command())
            self.assertAlmostEqual(obj.offset, -2.175)
            self.assertTrue(obj.last_calibration['applied'])
            self.assertFalse(obj.busy)
        self.assertEqual(mesh.pmgr.current_profile, 'default')

    def test_only_real_contact_is_fuzzed_and_selected_xy_drives_mesh_lookup(self):
        obj, mesh, _ = harness()
        events = []
        obj._no_contact = lambda gcmd, count: events.append(
            ('noncontact', tuple(obj.home_xy)))
        obj._sample_contact = lambda gcmd, xy: (
            events.append(('contact', tuple(xy))) or
            (-2.10, .01, [{'trigger_pos': [xy[0], xy[1], -2.10]}] * 3, 1))
        looked_up = []
        mesh_value = mesh.pmgr
        original_load = mesh_value.load_profile
        def load(profile):
            original_load(profile)
            mesh.z_mesh.calc_z = lambda *xy: looked_up.append(tuple(xy)) or .075
        mesh_value.load_profile = load
        original_choose = module.choose_contact_xy
        module.choose_contact_xy = lambda center, fuzz: (241.25, 192.55)
        try:
            obj._execute(Command(FUZZ=3))
        finally:
            module.choose_contact_xy = original_choose
        self.assertEqual(events[0], ('noncontact', (239.25, 194.55)))
        self.assertEqual(events[1], ('contact', (241.25, 192.55)))
        self.assertEqual(looked_up, [(241.25, 192.55)])
        self.assertEqual(obj.last_calibration['contact_xy'], [241.25, 192.55])
        self.assertEqual(obj.last_calibration['contact_fuzz'], 3.)

    def test_preview_preserves_manual_offset(self):
        obj, _, _ = harness()
        obj._execute(Command(APPLY=0))
        self.assertEqual(obj.offset, -2.)
        self.assertAlmostEqual(obj.last_calibration['offset'], -2.175)
        self.assertFalse(obj.last_calibration['applied'])

    def test_prepare_wipe_sets_temporary_offset_and_one_time_session(self):
        obj, _, _ = harness()
        cmd = Command(BED_TEMP=70, SOAK=0)
        obj.cmd_ADXL_Z_OFFSET_PREPARE_WIPE(cmd)
        self.assertEqual(obj.offset, -2.)
        self.assertTrue(obj.wipe_session['ready'])
        self.assertEqual(obj.wipe_session['bed_target'], 70.)
        self.assertEqual(obj.wipe_session['expires_at'], 1023.)
        self.assertTrue(any('temporary_offset' in m for m in cmd.messages))

    def test_after_wipe_calibration_consumes_session(self):
        obj, _, _ = harness()
        obj.wipe_session = {'ready': True, 'bed_target': 60.}
        obj._execute(Command(AFTER_WIPE=1, SOAK=0))
        self.assertTrue(obj.last_calibration['after_wipe'])
        self.assertFalse(obj.wipe_session['ready'])
        self.assertTrue(obj.wipe_session['consumed'])
        with self.assertRaisesRegex(RuntimeError, 'not ready'):
            obj._execute(Command(AFTER_WIPE=1, SOAK=0))

    def test_after_wipe_requires_zero_soak_and_same_bed_target(self):
        obj, _, _ = harness()
        obj.wipe_session = {'ready': True, 'bed_target': 60.}
        with self.assertRaisesRegex(RuntimeError, 'SOAK=0'):
            obj._execute(Command(AFTER_WIPE=1, SOAK=300))
        self.assertTrue(obj.wipe_session['ready'])
        with self.assertRaisesRegex(RuntimeError, 'BED_TEMP'):
            obj._execute(Command(AFTER_WIPE=1, SOAK=0, BED_TEMP=70))
        self.assertTrue(obj.wipe_session['ready'])

    def test_missing_mesh_fails_before_heating_or_motion(self):
        obj, _, _ = harness()
        with self.assertRaises(RuntimeError):
            obj._execute(Command(PROFILE='missing'))
        self.assertEqual(obj.calls, [])

    def test_sample_failure_rolls_back_and_turns_off_heat(self):
        obj, mesh, old_mesh = harness()
        def fail(gcmd):
            raise RuntimeError('Communication timeout during homing probe')
        obj._sample_contact = lambda gcmd, xy: fail(gcmd)
        with self.assertRaisesRegex(RuntimeError, 'Communication timeout'):
            obj._execute(Command())
        self.assertIs(mesh.z_mesh, old_mesh)
        self.assertEqual(mesh.pmgr.current_profile, 'old')
        self.assertEqual(obj.offset, -2.)
        self.assertFalse(obj.busy)
        self.assertFalse(obj.last_calibration['valid'])
        self.assertIn(('accel', 2000.), obj.calls)
        self.assertEqual(obj.calls[-1], 'TURN_OFF_HEATERS')

    def test_false_trigger_does_not_reach_contact(self):
        obj, _, _ = harness()
        def false_trigger(gcmd, count):
            raise RuntimeError('false trigger')
        obj._no_contact = false_trigger
        obj._sample_contact = lambda gcmd, xy: self.fail('contact must not run')
        with self.assertRaisesRegex(RuntimeError, 'false trigger'):
            obj._execute(Command())

    def test_failed_final_retract_still_restores_offset_mesh_and_accel(self):
        obj, mesh, old_mesh = harness()
        lifts = []
        def lift():
            lifts.append(1)
            if len(lifts) == 2:
                raise RuntimeError('recovery move failed')
        obj._safe_lift = lift
        with self.assertRaisesRegex(RuntimeError, 'recovery move failed'):
            obj._execute(Command())
        self.assertEqual(obj.offset, -2.)
        self.assertIs(mesh.z_mesh, old_mesh)
        self.assertIn(('accel', 2000.), obj.calls)
        self.assertFalse(obj.last_calibration['valid'])
        self.assertEqual(obj.calls[-1], 'TURN_OFF_HEATERS')

    def test_imprecise_groups_retry_but_unclassified_errors_do_not(self):
        obj, _, _ = harness()
        obj.tap_samples_retries = 3
        obj.tap_samples, obj.tap_samples_tolerance, obj.accel = 3, .05, 250.
        obj._run_coarse_probe = lambda *args: ([0., 0., 0.], (0., 0.))
        obj._respond_tap_result = lambda *args: None
        values = iter((-2.0, -2.1, -2.2, -2.1, -2.105, -2.095))
        obj._run_tap_move = lambda *args: {'trigger_pos': [0, 0, next(values)],
                                          'state': {'int_source': 0x40}}
        # Restore real method overridden by the general lifecycle harness.
        result = module.ADXL345ZOffset._sample_contact(
            obj, Command(), (239.25, 194.55))
        self.assertEqual(result[3], 2)
        self.assertAlmostEqual(result[0], -2.1)
        calls = []
        def fail(*args):
            calls.append(1)
            raise RuntimeError('No trigger')
        obj._run_tap_move = fail
        with self.assertRaises(RuntimeError):
            module.ADXL345ZOffset._sample_contact(
                obj, Command(), (239.25, 194.55))
        self.assertEqual(len(calls), 1)

    def test_contact_outside_selected_mesh_fails_before_motion(self):
        obj, mesh, _ = harness()
        mesh.pmgr.get_profiles = lambda: {
            'default': {'mesh_params': {
                'min_x': 20., 'min_y': 30.,
                'max_x': 239.25, 'max_y': 194.55}}}
        original_choose = module.choose_contact_xy
        module.choose_contact_xy = lambda center, fuzz: (240., 195.)
        try:
            with self.assertRaisesRegex(RuntimeError, 'outside PA11 mesh'):
                obj._execute(Command(FUZZ=3))
        finally:
            module.choose_contact_xy = original_choose
        self.assertEqual(obj.calls, [])

    def test_slicer_start_allowed_midprint_and_console_rejected(self):
        obj, _, _ = harness()
        status = {'state': 'printing', 'filament_used': 0., 'print_duration': 0.}
        obj.chip = SimpleNamespace(is_measuring=lambda: False)
        objects = {
            'print_stats': SimpleNamespace(get_status=lambda t: status),
            'virtual_sdcard': SimpleNamespace(is_cmd_from_sd=lambda: True)}
        obj.printer = SimpleNamespace(
            get_reactor=lambda: SimpleNamespace(monotonic=lambda: 0.),
            lookup_object=lambda name, default=None: objects.get(name, default))
        check = lambda: module.ADXL345ZOffset._check_start(obj, Command())
        check()
        status['filament_used'] = 1.
        with self.assertRaises(RuntimeError):
            check()
        status['filament_used'] = 0.
        objects['virtual_sdcard'].is_cmd_from_sd = lambda: False
        with self.assertRaises(RuntimeError):
            check()
        status['state'] = 'paused'
        with self.assertRaises(RuntimeError):
            check()

    def test_post_wipe_token_allows_only_same_sd_print_before_expiry(self):
        obj, _, _ = harness()
        clock = [100.]
        status = {'state': 'printing', 'filament_used': 30.,
                  'print_duration': 400., 'filename': 'part.gcode'}
        obj.chip = SimpleNamespace(is_measuring=lambda: False)
        sdcard = SimpleNamespace(is_cmd_from_sd=lambda: True)
        objects = {
            'print_stats': SimpleNamespace(get_status=lambda t: status),
            'virtual_sdcard': sdcard,
        }
        obj.printer = SimpleNamespace(
            get_reactor=lambda: SimpleNamespace(monotonic=lambda: clock[0]),
            lookup_object=lambda name, default=None: objects.get(name, default))
        obj.wipe_session = {'ready': True, 'expires_at': 1000.,
                            'print_state': 'printing', 'filename': 'part.gcode'}
        module.ADXL345ZOffset._check_start(
            obj, Command(), after_wipe=True)
        status['filename'] = 'other.gcode'
        with self.assertRaisesRegex(RuntimeError, 'same SD print'):
            module.ADXL345ZOffset._check_start(
                obj, Command(), after_wipe=True)
        status['filename'] = 'part.gcode'
        clock[0] = 1001.
        with self.assertRaisesRegex(RuntimeError, 'expired'):
            module.ADXL345ZOffset._check_start(
                obj, Command(), after_wipe=True)


if __name__ == '__main__':
    unittest.main()
