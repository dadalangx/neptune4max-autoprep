"""Offline behavioral checks for the legacy empty-heater compatibility fix."""
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


STEPPERS = ('stepper_x', 'stepper_y', 'stepper_z', 'stepper_z1', 'extruder')
SOURCE = Path(__file__).resolve().parents[1] / 'source/klipper/klippy/extras/controller_fan.py'


class FakeFan:
    def __init__(self, config):
        self.speed = 0.0

    def get_status(self, eventtime):
        return {'speed': self.speed}

    def get_mcu(self):
        return types.SimpleNamespace(estimated_print_time=lambda eventtime: eventtime)

    def set_speed(self, print_time, speed):
        self.speed = speed


class Config:
    def __init__(self, printer, values):
        self.printer = printer
        self.values = values

    def get_printer(self):
        return self.printer

    def getlist(self, key, default=None):
        # The real old parser returns ('',) for an empty option.
        if key not in self.values:
            return default
        return tuple(part.strip() for part in self.values[key].split(','))

    def getfloat(self, key, default, **kwargs):
        return float(self.values.get(key, default))

    def getint(self, key, default, **kwargs):
        return int(self.values.get(key, default))


class ControllerFanTests(unittest.TestCase):
    def setUp(self):
        package = types.ModuleType('_controller_fan_test')
        package.__path__ = []
        fan_module = types.ModuleType('_controller_fan_test.fan')
        fan_module.Fan = FakeFan
        namespace = {'__name__': '_controller_fan_test.controller_fan',
                     '__package__': '_controller_fan_test'}
        with patch.dict(sys.modules, {package.__name__: package, fan_module.__name__: fan_module}):
            exec(compile(SOURCE.read_text(encoding='utf-8'), str(SOURCE), 'exec'), namespace)
        self.controller_class = namespace['ControllerFan']

    def create(self, values=None):
        enabled = {name: False for name in STEPPERS}
        targets = {'extruder': 0.0, 'heater_bed': 0.0}
        enable = types.SimpleNamespace(
            get_steppers=lambda: list(STEPPERS),
            lookup_enable=lambda name: types.SimpleNamespace(
                is_motor_enabled=lambda: enabled[name]))

        def heater_lookup(name):
            if name not in targets:
                raise ValueError('Unknown heater: ' + name)
            return types.SimpleNamespace(get_temp=lambda eventtime: (25.0, targets[name]))

        heaters = types.SimpleNamespace(lookup_heater=heater_lookup)
        objects = {'stepper_enable': enable, 'heaters': heaters}
        reactor = types.SimpleNamespace(monotonic=lambda: 1000.0)
        printer = types.SimpleNamespace(
            register_event_handler=lambda *args: None,
            load_object=lambda config, name: objects[name],
            lookup_object=lambda name: objects[name],
            get_reactor=lambda: reactor,
            config_error=lambda message: ValueError(message))
        config = Config(printer, values if values is not None else {
            'heater': '', 'stepper': ', '.join(STEPPERS), 'idle_timeout': 60})
        controller = self.controller_class(config)
        controller.handle_connect()
        return controller, enabled, targets

    def test_empty_legacy_heater_list_connects_and_ignores_heating(self):
        controller, enabled, targets = self.create()
        targets['extruder'] = 250.0
        targets['heater_bed'] = 80.0
        controller.callback(0.0)
        self.assertEqual(controller.fan.speed, 0.0)

    def test_each_of_five_enabled_drivers_starts_fan_without_motion(self):
        for name in STEPPERS:
            with self.subTest(stepper=name):
                controller, enabled, targets = self.create()
                enabled[name] = True
                controller.callback(0.0)
                self.assertEqual(controller.fan.speed, 1.0)

    def test_release_keeps_fan_running_for_sixty_polls_then_stops(self):
        controller, enabled, targets = self.create()
        enabled['extruder'] = True
        controller.callback(0.0)
        enabled['extruder'] = False
        for second in range(1, 61):
            controller.callback(float(second))
            self.assertEqual(controller.fan.speed, 1.0)
        controller.callback(61.0)
        self.assertEqual(controller.fan.speed, 0.0)

    def test_holding_z_keeps_fan_on_when_other_motor_is_released(self):
        controller, enabled, targets = self.create()
        enabled['stepper_z1'] = enabled['extruder'] = True
        controller.callback(0.0)
        enabled['extruder'] = False
        for second in range(1, 90):
            controller.callback(float(second))
            self.assertEqual(controller.fan.speed, 1.0)

    def test_default_extruder_heater_behavior_is_preserved(self):
        controller, enabled, targets = self.create({})
        targets['extruder'] = 250.0
        controller.callback(0.0)
        self.assertEqual(controller.fan.speed, 1.0)

    def test_valid_multiple_heaters_are_preserved(self):
        controller, enabled, targets = self.create({'heater': 'extruder, heater_bed'})
        targets['heater_bed'] = 80.0
        controller.callback(0.0)
        self.assertEqual(controller.fan.speed, 1.0)


if __name__ == '__main__':
    unittest.main()
