import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source' / 'klipper' / 'klippy'))
module = importlib.import_module('extras.adaptive_mesh_bounds')
FIXTURE = ROOT / 'tests/fixtures/pa-calibration.gcode'


class Command:
    error = RuntimeError

    def __init__(self, **params):
        self.params, self.messages = params, []

    def get_command_parameters(self):
        return self.params

    def get_int(self, name, default, **limits):
        result = int(self.params.get(name, default))
        if result < limits['minval'] or result > limits['maxval']:
            raise self.error('out of bounds')
        return result

    def respond_info(self, message):
        self.messages.append(message)


class CalibrationBoundsTests(unittest.TestCase):
    def test_calibration_fixture_includes_pattern_not_surrounding_purge(self):
        self.assertEqual(module.read_calibration_bounds(str(FIXTURE)),
                         (160., 175., 264., 241.5))

    def test_ordinary_file_keeps_slicer_bounds(self):
        self.assertIsNone(module.calibration_bounds(
            ['G90', 'M83', 'G1 X0 Y0', 'G1 X100 Y100 E10']))

    def test_relative_xy_and_absolute_e_reset(self):
        lines = ['G90', 'M82', 'G92 E100', 'G1 X20 Y30', module.START,
                 'G91', 'G1 X10 E101', 'G92 E0', 'G1 Y20 E1',
                 'G1 X-5 E0', module.END]
        self.assertEqual(module.calibration_bounds(lines), (20., 30., 30., 50.))

    def test_incomplete_unsupported_and_nonfinite_blocks_fail_closed(self):
        prefix = ['G90', 'M83', 'G1 X20 Y30', module.START]
        for suffix in (['G1 X40 Y50 E1'],
                       ['G2 X40 Y50 E1', module.END],
                       ['G1 Xnan Y50 E1', module.END],
                       ['G92 X0', module.END]):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                module.calibration_bounds(prefix + suffix)

    def test_sd_command_overrides_even_full_bed_slicer_bounds(self):
        scripts = []
        sdcard = SimpleNamespace(is_cmd_from_sd=lambda: True,
                                 file_path=lambda: str(FIXTURE))
        printer = SimpleNamespace(lookup_object=lambda name, default: sdcard)
        gcode = SimpleNamespace(run_script_from_command=scripts.append)
        command = Command(X_MIN='0', Y_MIN='0', X_MAX='420', Y_MAX='420',
                          MARGIN='10', PROFILE='adaptive')
        module.resolve_mesh_command(printer, gcode, command)
        self.assertIn('X_MIN=160.0', scripts[0])
        self.assertIn('Y_MIN=175.0', scripts[0])
        self.assertIn('X_MAX=264.0', scripts[0])
        self.assertIn('Y_MAX=241.5', scripts[0])
        self.assertIn('PA calibration extrusion bounds', command.messages[0])

    def test_console_selected_file_is_not_implicitly_used(self):
        scripts = []
        sdcard = SimpleNamespace(is_cmd_from_sd=lambda: False,
                                 file_path=lambda: str(FIXTURE))
        printer = SimpleNamespace(lookup_object=lambda name, default: sdcard)
        module.resolve_mesh_command(
            printer, SimpleNamespace(run_script_from_command=scripts.append),
            Command(X_MIN='180', Y_MIN='180', X_MAX='220', Y_MAX='220',
                    PLAN_ONLY='1'))
        self.assertIn('X_MIN=180.0', scripts[0])

    def test_source_file_requires_dry_run_and_cannot_escape_sd_root(self):
        sdcard = SimpleNamespace(sdcard_dirname=str(FIXTURE.parent),
                                 is_cmd_from_sd=lambda: False)
        printer = SimpleNamespace(lookup_object=lambda name, default: sdcard)
        gcode = SimpleNamespace(run_script_from_command=lambda cmd: None)
        for params in ({'SOURCE_FILE': 'pa-calibration.gcode'},
                       {'SOURCE_FILE': '../outside.gcode', 'PLAN_ONLY': '1'},
                       {'PROFILE': 'adaptive\n', 'PLAN_ONLY': '1'},
                       {'PROFILE': 'adaptive\nG28', 'PLAN_ONLY': '1'}):
            with self.subTest(params=params), self.assertRaises(RuntimeError):
                module.resolve_mesh_command(printer, gcode, Command(**params))

    def test_full_mesh_timeout_remains_bounded(self):
        cfg = (ROOT / 'config/reference/adxl345_z_offset.cfg').read_text(encoding='utf-8')
        self.assertIn('wipe_session_timeout: 1800', cfg)
        source = (ROOT / 'source/klipper/klippy/extras/adxl345_z_offset.py'
                  ).read_text(encoding='utf-8')
        self.assertIn("now > session.get('expires_at', 0.)", source)
        self.assertIn("900., above=0., maxval=1800.", source)


if __name__ == '__main__':
    unittest.main()
