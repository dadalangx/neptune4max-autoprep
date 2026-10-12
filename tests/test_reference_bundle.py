"""Offline selection and dependency checks; no printer communication."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('reference_bundle', ROOT / 'tools/reference_bundle.py')
READER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READER)
CATALOG = json.loads((ROOT / 'implementation-map.json').read_text(encoding='utf-8'))


class ReferenceBundleTests(unittest.TestCase):
    def test_catalog_references_resolve(self):
        self.assertGreater(READER.validate(CATALOG, ROOT), 0)

    def test_dependency_order_and_shared_dependency_deduplication(self):
        names = READER.select_features(CATALOG, ['print-preparation'], True)
        self.assertEqual(names[-1], 'print-preparation')
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            for dependency in CATALOG['features'][name]['depends_on']:
                self.assertLess(names.index(dependency), names.index(name))

    def test_dual_z_excerpt_contains_paired_z_release_without_adxl_wrapper(self):
        text = READER.config_text(CATALOG, ['dual-z'], ROOT)
        self.assertIn('[gcode_macro DUAL_Z_LEVEL]', text)
        self.assertIn('SET_STEPPER_ENABLE STEPPER=stepper_z1 enable=0', text)
        self.assertNotIn('[gcode_macro ADXL_Z_OFFSET_PREPARE_WIPE]', text)
        self.assertNotIn('[adxl345_z_offset]', text)

    def test_offset_excerpt_does_not_load_nonexistent_default_mesh(self):
        text = READER.config_text(CATALOG, ['adxl-offset'], ROOT)
        self.assertIn('[adxl345_z_offset]', text)
        self.assertNotIn('[delayed_gcode FORCE_DEFAULT_BED_MESH]', text)
        self.assertNotIn('[gcode_macro BED_MESH_PROFILE]', text)
        self.assertNotIn('[include adaptive_bed_mesh.cfg]', text)

    def test_selected_sections_are_exact_and_shared_blocks_not_duplicated(self):
        names = READER.select_features(CATALOG, ['dual-z', 'adxl-offset'], True)
        text = READER.config_text(CATALOG, names, ROOT)
        blocks = READER.sections_from_file(ROOT / 'config/reference/host-sensors-motors.cfg')
        self.assertIn(blocks['gcode_macro M84'], text)
        self.assertEqual(text.count('[probe]'), 1)
        self.assertEqual(text.count('[gcode_macro M84]'), 1)

    def test_cycle_unknown_feature_and_missing_section_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown feature'):
            READER.select_features(CATALOG, ['missing'], True)
        cyclic = {'features': {'a': {'depends_on': ['b']}, 'b': {'depends_on': ['a']}}}
        with self.assertRaisesRegex(ValueError, 'cycle'):
            READER.select_features(cyclic, ['a'], True)
        altered = json.loads(json.dumps(CATALOG))
        altered['features']['dual-z']['configs'][0]['sections'].append('missing section')
        with self.assertRaisesRegex(ValueError, 'Missing'):
            READER.validate(altered, ROOT)

    def test_duplicate_sections_and_outside_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'duplicate.cfg'
            path.write_text('[probe]\npin: PA11\n[probe]\npin: PA12\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Duplicate section'):
                READER.sections_from_file(path)
            with self.assertRaises(ValueError):
                READER.local_file(root, '../outside.cfg')


if __name__ == '__main__':
    unittest.main()
