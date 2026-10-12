import math
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MACRO = (ROOT / 'config/reference/adaptive_bed_mesh.cfg').read_text(encoding='utf-8')
ADXL_CONFIG = (ROOT / 'config/reference/adxl345_z_offset.cfg').read_text(encoding='utf-8')


def setting(name):
    match = re.search(r'^variable_' + re.escape(name) + r':\s*([-0-9.]+)\s*$',
                      MACRO, re.MULTILINE)
    if not match:
        raise AssertionError('missing setting: ' + name)
    return float(match.group(1))


def calculate(model_bounds, margin=10.0):
    """Reference calculation matching the macro, without Jinja rendering."""
    safe_min_x = setting('mesh_min_x')
    safe_min_y = setting('mesh_min_y')
    safe_max_x = setting('mesh_max_x')
    safe_max_y = setting('mesh_max_y')
    ref_x = setting('reference_x')
    ref_y = setting('reference_y')
    contact_fuzz = setting('adxl_contact_fuzz')
    rounding_guard = setting('probe_rounding_guard')
    count_x = int(setting('base_probe_count_x'))
    count_y = int(setting('base_probe_count_y'))
    x_min, y_min, x_max, y_max = model_bounds

    adapted_min_x = max(
        min(x_min - margin, ref_x - contact_fuzz - rounding_guard), safe_min_x)
    adapted_min_y = max(
        min(y_min - margin, ref_y - contact_fuzz - rounding_guard), safe_min_y)
    adapted_max_x = min(
        max(x_max + margin, ref_x + contact_fuzz + rounding_guard), safe_max_x)
    adapted_max_y = min(
        max(y_max + margin, ref_y + contact_fuzz + rounding_guard), safe_max_y)
    spacing_x = (safe_max_x - safe_min_x) / (count_x - 1)
    spacing_y = (safe_max_y - safe_min_y) / (count_y - 1)
    points_x = math.ceil((adapted_max_x - adapted_min_x) / spacing_x) + 1
    points_y = math.ceil((adapted_max_y - adapted_min_y) / spacing_y) + 1
    if max(points_x, points_y) > 6:
        algorithm, minimum = 'bicubic', 4
    else:
        algorithm, minimum = 'lagrange', 3
    points_x = min(max(points_x, minimum), count_x)
    points_y = min(max(points_y, minimum), count_y)
    return ((adapted_min_x, adapted_min_y),
            (adapted_max_x, adapted_max_y),
            (points_x, points_y), algorithm)


class AdaptiveBedMeshMacroTests(unittest.TestCase):
    def test_is_standalone_and_does_not_override_native_calibration(self):
        self.assertIn('[gcode_macro ADAPTIVE_BED_MESH]', MACRO)
        self.assertIn('ADAPTIVE_MESH_RESOLVE {rawparams}', MACRO)
        self.assertIn('[gcode_macro _ADAPTIVE_BED_MESH_BUILD]', MACRO)
        self.assertNotIn('[gcode_macro BED_MESH_CALIBRATE]', MACRO)
        self.assertNotIn('rename_existing:', MACRO)
        self.assertIn('[include adaptive_bed_mesh.cfg]', ADXL_CONFIG)

    def test_bambu_bounds_profile_and_plan_only_are_supported(self):
        for name in ('X_MIN', 'Y_MIN', 'X_MAX', 'Y_MAX'):
            self.assertIn('params.' + name, MACRO)
        self.assertIn('params.PROFILE | default("adaptive")', MACRO)
        self.assertIn('params.PLAN_ONLY | default(0)', MACRO)
        self.assertIn('BED_MESH_CALIBRATE PROFILE={profile}', MACRO)

    def test_pa11_mesh_has_no_random_fuzz_and_reserves_contact_square(self):
        self.assertNotIn('| random', MACRO)
        self.assertNotIn('params.FUZZ', MACRO)
        self.assertEqual(setting('adxl_contact_fuzz'), 3.0)
        self.assertEqual(setting('probe_rounding_guard'), 0.25)
        self.assertIn('reference_x - contact_fuzz - rounding_guard', MACRO)
        self.assertIn('reference_x + contact_fuzz + rounding_guard', MACRO)
        self.assertIn('reference_y - contact_fuzz - rounding_guard', MACRO)
        self.assertIn('reference_y + contact_fuzz + rounding_guard', MACRO)

    def test_center_print_stays_safe_and_contains_adxl_reference(self):
        lower, upper, points, algorithm = calculate(
            (180.0, 180.0, 220.0, 220.0))
        self.assertGreaterEqual(lower[0], 20.0)
        self.assertGreaterEqual(lower[1], 30.0)
        self.assertLessEqual(upper[0], 395.0)
        self.assertLessEqual(upper[1], 400.0)
        self.assertLessEqual(lower[0], 239.25 - 3.25)
        self.assertGreaterEqual(upper[0], 239.25 + 3.25)
        self.assertLessEqual(lower[1], 194.55 - 3.25)
        self.assertGreaterEqual(upper[1], 194.55 + 3.25)
        self.assertGreaterEqual(points[0], 3)
        self.assertGreaterEqual(points[1], 3)
        self.assertIn(algorithm, ('lagrange', 'bicubic'))

    def test_edge_print_is_clamped_and_density_never_exceeds_15(self):
        lower, upper, points, _ = calculate(
            (385.0, 390.0, 425.0, 425.0))
        self.assertEqual(upper, (395.0, 400.0))
        self.assertLessEqual(lower[0], 239.25 - 3.25)
        self.assertLessEqual(lower[1], 194.55 - 3.25)
        self.assertLessEqual(points[0], 15)
        self.assertLessEqual(points[1], 15)

    def test_full_safe_area_reproduces_base_density(self):
        _, _, points, algorithm = calculate((20.0, 30.0, 395.0, 400.0))
        self.assertEqual(points, (15, 15))
        self.assertEqual(algorithm, 'bicubic')

    def test_invalid_bounds_have_explicit_six_by_six_fallback(self):
        self.assertEqual(setting('fallback_probe_count'), 6.0)
        self.assertIn('invalid Bambu Studio bounds', MACRO)
        self.assertIn('{% set points_x = fallback_count %}', MACRO)
        self.assertIn('{% set points_y = fallback_count %}', MACRO)


if __name__ == '__main__':
    unittest.main()
