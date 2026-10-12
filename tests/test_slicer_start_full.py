import unittest
from pathlib import Path


START_GCODE = (Path(__file__).resolve().parents[1]
               / 'tests/fixtures/slicer-start-regression.gcode').read_text(encoding='utf-8')
END_GCODE = (Path(__file__).resolve().parents[1]
             / 'tests/fixtures/slicer-end-regression.gcode').read_text(encoding='utf-8')


class SlicerStartWipeTests(unittest.TestCase):
    def test_motion_limits_are_reset_at_both_job_boundaries(self):
        reset = (
            'SET_VELOCITY_LIMIT VELOCITY=500 ACCEL=2000 '
            'ACCEL_TO_DECEL=20000 SQUARE_CORNER_VELOCITY=9')
        self.assertIn(reset, START_GCODE)
        self.assertLess(START_GCODE.index(reset),
                        START_GCODE.index('ADXL_Z_OFFSET_PREPARE_WIPE'))

        self.assertIn(reset, END_GCODE)
        self.assertLess(END_GCODE.index(reset), END_GCODE.index('G1 E-1.5'))
        self.assertLess(END_GCODE.index(reset), END_GCODE.index('G1 X10 Y336'))
        self.assertIn('M400 ; 停车完成后再清床网', END_GCODE)
        self.assertIn('BED_MESH_CLEAR', END_GCODE)
        self.assertIn('M84 X Y E', END_GCODE)
        self.assertNotIn('M84 X Y Z E', END_GCODE)
        self.assertNotIn('ACCEL_TO_DECEL=1000', END_GCODE)

    def test_suspended_purge_and_fast_bed_edge_cut(self):
        self.assertIn(
            'M109 S{nozzle_temperature_initial_layer[initial_extruder] + 10}',
            START_GCODE)
        self.assertIn('G1 E100 F180', START_GCODE)
        self.assertIn('G1 Z10 F300\nG1 X0 F6000', START_GCODE)
        self.assertNotIn('G1 X0 Y0 F6000', START_GCODE)
        self.assertNotIn('G1 E50 F180', START_GCODE)
        self.assertNotIn('G1 X100 E30', START_GCODE)
        self.assertNotIn('G1 Z0.4 F300', START_GCODE)
        self.assertEqual(START_GCODE.count('G1 X100 F12000'), 3)
        self.assertEqual(START_GCODE.count('G1 X0 F12000'), 4)
        self.assertIn('G1 X200 F12000\nG1 X0 F12000', START_GCODE)
        self.assertIn('G1 E-5 F300', START_GCODE)
        fan_on = START_GCODE.index('M106 S255')
        first_cut = START_GCODE.index('G1 X100 F12000')
        self.assertLess(fan_on, first_cut)

    def test_five_fast_wipes_then_contact_cooling(self):
        self.assertIn('G1 X10 F3000\nG1 Z-0.5 F300', START_GCODE)
        self.assertEqual(START_GCODE.count('G1 X30 F12000'), 10)
        # Five hot returns, one move from center to the low-temperature start,
        # and five low-temperature returns.
        self.assertEqual(START_GCODE.count('G1 X10 F12000'), 11)
        sequence = [
            'M106 S255',
            'G1 X20 F12000',
            'M104 S140',
            'TEMPERATURE_WAIT SENSOR=extruder MAXIMUM=142',
            'G1 X10 F12000',
            'G1 X30 F12000',
            'G1 X20 F12000',
            'M106 S0',
            'G1 Z10 F300',
            'QUERY_ENDSTOPS',
            'G1 X100 F6000',
            'G28 X',
            'G28 Y',
            'SET_GCODE_OFFSET Z=0 MOVE=0',
            ('ADAPTIVE_BED_MESH X_MIN={first_layer_print_min[0]} '
             'Y_MIN={first_layer_print_min[1]} '
             'X_MAX={first_layer_print_max[0]} '
             'Y_MAX={first_layer_print_max[1]} '
             'MARGIN=10 PROFILE=adaptive'),
            ('ADXL_Z_OFFSET PROFILE=adaptive '
             'BED_TEMP=[bed_temperature_initial_layer_single] '
             'SOAK=0 AFTER_WIPE=1 FUZZ=3'),
        ]
        cursor = -1
        for item in sequence:
            cursor = START_GCODE.find(item, cursor + 1)
            self.assertNotEqual(cursor, -1, item)
        homing_block = (
            'G1 Z10 F300\n'
            'M400\n'
            'G4 P2000\n\n'
            '; 输出擦嘴后虚拟限位状态，便于区分短行程和传感器提前触发。\n'
            'QUERY_ENDSTOPS\n\n'
            '; 利用PREPARE_WIPE阶段的真实G28坐标先离开左端，制造明确且可观察的X归位行程。\n'
            'G1 X100 F6000\n'
            'M400\n'
            'G4 P2000\n\n'
            '; 分轴归位：先X后Y；不归位Z，避免在此处增加一次喷嘴碰床。\n'
            'G28 X\n'
            'G4 P2000\n'
            'G28 Y')
        self.assertIn(homing_block, START_GCODE)
        self.assertNotIn('G28 X Y', START_GCODE)

    def test_print_restores_temperature_then_draws_factory_purge_line(self):
        final_temperature = (
            'M109 S{nozzle_temperature_initial_layer[initial_extruder]}')
        sequence = [
            ('ADAPTIVE_BED_MESH X_MIN={first_layer_print_min[0]} '
             'Y_MIN={first_layer_print_min[1]} '
             'X_MAX={first_layer_print_max[0]} '
             'Y_MAX={first_layer_print_max[1]} '
             'MARGIN=10 PROFILE=adaptive'),
            ('ADXL_Z_OFFSET PROFILE=adaptive '
             'BED_TEMP=[bed_temperature_initial_layer_single] '
             'SOAK=0 AFTER_WIPE=1 FUZZ=3'),
            'SET_GCODE_OFFSET Z_ADJUST=0.100 MOVE=0',
            'G1 X165 Y0.5 F6000',
            final_temperature,
            'G90',
            'M83',
            'G92 E0',
            'G1 X165 Y0.5 Z0.4 F300',
            'G1 X265 E30 F400',
            'G1 Z0.6 F120.0',
            'G1 X260 F3000',
            'M82',
            'G92 E0',
        ]
        cursor = -1
        for item in sequence:
            cursor = START_GCODE.find(item, cursor + 1)
            self.assertNotEqual(cursor, -1, item)
        self.assertTrue(START_GCODE.rstrip().endswith('G92 E0'))


if __name__ == '__main__':
    unittest.main()
