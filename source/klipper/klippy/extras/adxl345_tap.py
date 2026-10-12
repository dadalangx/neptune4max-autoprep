# ADXL345 Single Tap based Z probing support
#
# Copyright (C) 2026
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging

import chelper
import mcu


REG_DEVID = 0x00
REG_THRESH_TAP = 0x1D
REG_DUR = 0x21
REG_TAP_AXES = 0x2A
REG_BW_RATE = 0x2C
REG_POWER_CTL = 0x2D
REG_INT_ENABLE = 0x2E
REG_INT_SOURCE = 0x30
REG_DATA_FORMAT = 0x31
REG_FIFO_CTL = 0x38

ADXL345_DEVID = 0xE5
SINGLE_TAP = 0x40
TAP_AXIS_BITS = {'x': 0x04, 'y': 0x02, 'z': 0x01}


class ADXL345TapEndstop:
    def __init__(self, config, chip, poll_rate, arm_delay):
        self.printer = config.get_printer()
        self.chip = chip
        self._mcu = chip.mcu
        self._oid = chip.oid
        self._poll_rate = poll_rate
        self._arm_delay = arm_delay
        self._home_cmd = self._query_cmd = None
        self._trigger_completion = None
        self._last_state = {}
        ffi_main, ffi_lib = chelper.get_ffi()
        self._trdispatch = ffi_main.gc(ffi_lib.trdispatch_alloc(), ffi_lib.free)
        self._trsyncs = [mcu.MCU_trsync(self._mcu, self._trdispatch)]
        self._mcu.add_config_cmd(
            "adxl345_tap_home oid=%d clock=0 rest_ticks=0"
            " trsync_oid=0 trigger_reason=0" % (self._oid,),
            on_restart=True)
        self._mcu.register_config_callback(self._build_config)

    def get_mcu(self):
        return self._mcu

    def set_arm_delay(self, arm_delay):
        self._arm_delay = arm_delay

    def add_stepper(self, stepper):
        trsyncs = {trsync.get_mcu(): trsync for trsync in self._trsyncs}
        trsync = trsyncs.get(stepper.get_mcu())
        if trsync is None:
            trsync = mcu.MCU_trsync(stepper.get_mcu(), self._trdispatch)
            self._trsyncs.append(trsync)
        trsync.add_stepper(stepper)
        sname = stepper.get_name()
        if sname.startswith('stepper_'):
            for other_trsync in self._trsyncs:
                for other_stepper in other_trsync.get_steppers():
                    if (other_trsync is not trsync
                            and other_stepper.get_name().startswith(sname[:9])):
                        raise self.printer.config_error(
                            "Multi-mcu homing not supported on multi-mcu"
                            " shared axis")

    def get_steppers(self):
        return [stepper for trsync in self._trsyncs
                for stepper in trsync.get_steppers()]

    def _build_config(self):
        cmd_queue = self._trsyncs[0].get_command_queue()
        self._home_cmd = self._mcu.lookup_command(
            "adxl345_tap_home oid=%c clock=%u rest_ticks=%u"
            " trsync_oid=%c trigger_reason=%c", cq=cmd_queue)
        self._query_cmd = self._mcu.lookup_query_command(
            "adxl345_tap_query_state oid=%c",
            "adxl345_tap_state oid=%c homing=%c trigger_clock=%u"
            " int_source=%c poll_count=%u query_ticks=%u",
            oid=self._oid, cq=cmd_queue)

    def home_start(self, print_time, sample_time, sample_count, rest_time,
                   triggered=True):
        if not triggered:
            raise self.printer.command_error(
                "ADXL345 Tap only supports triggered probing")
        if self.chip.is_measuring():
            raise self.printer.command_error(
                "Stop accelerometer measurements before ADXL Tap probing")
        reactor = self.printer.get_reactor()
        self._trigger_completion = reactor.completion()
        expire_timeout = mcu.TRSYNC_TIMEOUT
        if len(self._trsyncs) == 1:
            expire_timeout = mcu.TRSYNC_SINGLE_MCU_TIMEOUT
        for trsync in self._trsyncs:
            trsync.start(print_time, self._trigger_completion, expire_timeout)
        etrsync = self._trsyncs[0]
        ffi_main, ffi_lib = chelper.get_ffi()
        ffi_lib.trdispatch_start(self._trdispatch,
                                 etrsync.REASON_HOST_REQUEST)
        start_clock = self._mcu.print_time_to_clock(print_time)
        arm_clock = self._mcu.print_time_to_clock(
            print_time + self._arm_delay)
        rest_ticks = self._mcu.seconds_to_clock(1. / self._poll_rate)
        self._home_cmd.send(
            [self._oid, arm_clock, rest_ticks, etrsync.get_oid(),
             etrsync.REASON_ENDSTOP_HIT], reqclock=start_clock)
        return self._trigger_completion

    def home_wait(self, home_end_time):
        etrsync = self._trsyncs[0]
        etrsync.set_home_end_time(home_end_time)
        if self._mcu.is_fileoutput():
            self._trigger_completion.complete(True)
        self._trigger_completion.wait()
        self._home_cmd.send([self._oid, 0, 0, 0, 0])
        ffi_main, ffi_lib = chelper.get_ffi()
        ffi_lib.trdispatch_stop(self._trdispatch)
        results = [trsync.stop() for trsync in self._trsyncs]
        if any(reason == etrsync.REASON_COMMS_TIMEOUT for reason in results):
            return -1.
        params = self._query_cmd.send([self._oid])
        self._last_state = dict(params)
        if results[0] != etrsync.REASON_ENDSTOP_HIT:
            return 0.
        if self._mcu.is_fileoutput():
            return home_end_time
        trigger_clock = self._mcu.clock32_to_clock64(
            params['trigger_clock'])
        return self._mcu.clock_to_print_time(trigger_clock)

    def query_endstop(self, print_time):
        if self._mcu.is_fileoutput():
            return 0
        minclock = self._mcu.print_time_to_clock(print_time)
        params = self._query_cmd.send([self._oid], minclock=minclock)
        self._last_state = dict(params)
        return bool(params['int_source'] & SINGLE_TAP)

    def get_last_state(self):
        return dict(self._last_state)


class ADXL345Tap:
    cmd_ADXL_TAP_PROBE_help = "Run a bounded ADXL345 Tap Z probe"
    cmd_ADXL_TAP_HOME_help = (
        "Set Z zero from a median-filtered ADXL345 Tap sample group")
    cmd_ADXL_TAP_BED_MESH_CALIBRATE_help = (
        "Build a Klipper bed mesh from median-filtered ADXL345 Tap groups")
    cmd_ADXL_TAP_NO_CONTACT_help = (
        "Run a bounded ADXL345 Tap move above the bed for false-trigger tests")
    cmd_ADXL_TAP_QUERY_help = "Report the latest ADXL345 Tap MCU state"

    def __init__(self, config, register_commands=True):
        self.printer = config.get_printer()
        sensor_name = config.get('sensor', 'adxl345 x')
        self.chip = self.printer.lookup_object(sensor_name)
        self.threshold_g = config.getfloat(
            'threshold', 1.50, minval=0.0625, maxval=15.9375)
        self.duration_ms = config.getfloat(
            'duration_ms', 20., minval=0.625, maxval=159.375)
        axis = config.getchoice('axis', TAP_AXIS_BITS, 'y')
        self.threshold_reg = int(self.threshold_g / .0625 + .5)
        self.duration_reg = int(self.duration_ms / .625 + .5)
        self.axis_reg = axis
        self.axis_name = next(
            name for name, bits in TAP_AXIS_BITS.items() if bits == axis)
        self.poll_rate = config.getfloat(
            'poll_rate', 2000., minval=100., maxval=10000.)
        self.arm_delay = config.getfloat(
            'arm_delay', .120, minval=0., maxval=.500)
        self.speed = config.getfloat('speed', 20., above=0., maxval=40.)
        self.accel = config.getfloat('accel', 250., above=0., maxval=1000.)
        self.max_travel = config.getfloat(
            'max_travel', 3.5, above=0., maxval=3.5)
        # Absolute lower Z bound for real nozzle-contact probing.  Unlike
        # max_travel (used by the no-contact diagnostic), this does not reduce
        # the available search distance when a probe starts from a higher Z.
        self.probe_min_z = config.getfloat(
            'probe_min_z', -3.5, minval=-3.5, maxval=0.)
        self.pre_tap_lift = config.getfloat(
            'pre_tap_lift', .75, minval=0., maxval=5.)
        self.tap_samples = config.getint('tap_samples', 3, minval=3)
        if not self.tap_samples & 1:
            raise config.error("tap_samples must be an odd number")
        self.tap_samples_tolerance = config.getfloat(
            'tap_samples_tolerance', .050, minval=0.)
        self.tap_samples_retries = config.getint(
            'tap_samples_retries', 3, minval=0)
        self.min_valid_contact_offset = config.getfloat(
            'min_valid_contact_offset', 1.50, minval=0.)
        self.max_valid_contact_offset = config.getfloat(
            'max_valid_contact_offset', 2.80,
            above=self.min_valid_contact_offset, maxval=10.)
        self.home_xy = config.getfloatlist(
            'home_xy_position', (239.25, 194.55), count=2)
        self.home_z = config.getfloat('home_z_position', 10., above=0.)
        self.mesh_horizontal_z = config.getfloat(
            'mesh_horizontal_z', 10., above=0.)
        self.retract_dist = config.getfloat(
            'retract_dist', 5., above=0.)
        self.retract_speed = config.getfloat(
            'retract_speed', 5., above=0.)
        self.align_probe_to_nozzle = config.getboolean(
            'align_probe_to_nozzle', True)
        self.alignment_lift = config.getfloat(
            'alignment_lift', 5., above=0.)
        self.xy_speed = config.getfloat('xy_speed', 200., above=0.)
        self.endstop = ADXL345TapEndstop(
            config, self.chip, self.poll_rate, self.arm_delay)
        self.printer.register_event_handler(
            'klippy:mcu_identify', self._handle_mcu_identify)
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode_move = self.printer.lookup_object('gcode_move')
        # A pre-print-only extension can reuse the endstop and sampling core
        # without exposing the historical ADXL homing/mesh commands.
        if not register_commands:
            return
        self.gcode.register_command(
            'ADXL_TAP_PROBE', self.cmd_ADXL_TAP_PROBE,
            desc=self.cmd_ADXL_TAP_PROBE_help)
        self.gcode.register_command(
            'ADXL_TAP_HOME', self.cmd_ADXL_TAP_HOME,
            desc=self.cmd_ADXL_TAP_HOME_help)
        self.gcode.register_command(
            'ADXL_TAP_BED_MESH_CALIBRATE',
            self.cmd_ADXL_TAP_BED_MESH_CALIBRATE,
            desc=self.cmd_ADXL_TAP_BED_MESH_CALIBRATE_help)
        self.gcode.register_command(
            'ADXL_TAP_NO_CONTACT', self.cmd_ADXL_TAP_NO_CONTACT,
            desc=self.cmd_ADXL_TAP_NO_CONTACT_help)
        self.gcode.register_command(
            'ADXL_TAP_QUERY', self.cmd_ADXL_TAP_QUERY,
            desc=self.cmd_ADXL_TAP_QUERY_help)

    def _handle_mcu_identify(self):
        kin = self.printer.lookup_object('toolhead').get_kinematics()
        for stepper in kin.get_steppers():
            if stepper.is_active_axis('z'):
                self.endstop.add_stepper(stepper)

    def get_status(self, eventtime):
        state = self.endstop.get_last_state()
        return {
            'homing': state.get('homing', 0),
            'int_source': state.get('int_source', 0),
            'poll_count': state.get('poll_count', 0),
        }

    def _get_test_axes(self, gcmd):
        raw_axes = gcmd.get('AXES', self.axis_name)
        axes = raw_axes.lower().replace(',', '').replace(' ', '')
        if (not axes or any(axis not in TAP_AXIS_BITS for axis in axes)):
            raise gcmd.error(
                "AXES must contain only x, y, and/or z")
        axes_label = ''.join(
            axis for axis in ('x', 'y', 'z') if axis in axes)
        axes_reg = 0
        for axis in axes_label:
            axes_reg |= TAP_AXIS_BITS[axis]
        return axes_reg, axes_label

    def _prepare_sensor(self, threshold_reg=None, duration_reg=None,
                        axes_reg=None):
        if self.chip.is_measuring():
            raise self.printer.command_error(
                "Stop accelerometer measurements before ADXL Tap probing")
        if self.chip.read_reg(REG_DEVID) != ADXL345_DEVID:
            raise self.printer.command_error("Invalid ADXL345 device id")
        self.chip.set_reg(REG_INT_ENABLE, 0x00)
        self.chip.set_reg(REG_POWER_CTL, 0x00)
        self.chip.set_reg(REG_DATA_FORMAT, 0x00)
        self.chip.set_reg(REG_FIFO_CTL, 0x00)
        self.chip.set_reg(REG_BW_RATE, 0x0A)
        if threshold_reg is None:
            threshold_reg = self.threshold_reg
        if duration_reg is None:
            duration_reg = self.duration_reg
        if axes_reg is None:
            axes_reg = self.axis_reg
        self.chip.set_reg(REG_THRESH_TAP, threshold_reg)
        self.chip.set_reg(REG_DUR, duration_reg)
        self.chip.set_reg(REG_TAP_AXES, axes_reg)
        self.chip.read_reg(REG_INT_SOURCE)
        self.chip.set_reg(REG_POWER_CTL, 0x08)
        toolhead = self.printer.lookup_object('toolhead')
        toolhead.dwell(.020)
        toolhead.wait_moves()

    def _disarm_sensor(self):
        try:
            self.chip.set_reg(REG_INT_ENABLE, 0x00)
            self.chip.read_reg(REG_INT_SOURCE)
        except Exception:
            logging.exception("Unable to disarm ADXL345 Tap")

    def _set_accel(self, accel):
        self.gcode.run_script_from_command(
            "SET_VELOCITY_LIMIT ACCEL=%.6f" % (accel,))

    def _run_coarse_probe(self, gcmd, tap_xy):
        coarse_probe = self.printer.lookup_object('probe')
        if not self.align_probe_to_nozzle:
            return coarse_probe.run_probe(gcmd), tuple(tap_xy)

        toolhead = self.printer.lookup_object('toolhead')
        x_offset, y_offset, unused_z_offset = coarse_probe.get_offsets()
        probe_xy = (tap_xy[0] - x_offset, tap_xy[1] - y_offset)
        eventtime = self.printer.get_reactor().monotonic()
        status = toolhead.get_status(eventtime)
        axis_min = status['axis_minimum']
        axis_max = status['axis_maximum']
        if not (axis_min[0] <= probe_xy[0] <= axis_max[0]
                and axis_min[1] <= probe_xy[1] <= axis_max[1]):
            raise gcmd.error(
                "Cannot align probe at nozzle XY %.3f,%.3f:"
                " required toolhead XY %.3f,%.3f is outside limits"
                % (tap_xy[0], tap_xy[1], probe_xy[0], probe_xy[1]))

        lift_speed = coarse_probe.get_lift_speed(gcmd)
        current_pos = toolhead.get_position()
        safe_z = min(current_pos[2] + self.alignment_lift, axis_max[2])
        toolhead.manual_move([None, None, safe_z], lift_speed)
        toolhead.manual_move([probe_xy[0], probe_xy[1], None], self.xy_speed)
        toolhead.wait_moves()

        coarse_pos = coarse_probe.run_probe(gcmd)
        safe_z = min(coarse_pos[2] + self.alignment_lift, axis_max[2])
        toolhead.manual_move([None, None, safe_z], lift_speed)
        toolhead.manual_move([tap_xy[0], tap_xy[1], None], self.xy_speed)
        toolhead.manual_move([None, None, coarse_pos[2]], lift_speed)
        toolhead.wait_moves()
        self.gcode_move.reset_last_position()
        return coarse_pos, probe_xy

    def _check_available(self, gcmd, command_name):
        toolhead = self.printer.lookup_object('toolhead')
        eventtime = self.printer.get_reactor().monotonic()
        if 'xyz' != toolhead.get_status(eventtime)['homed_axes']:
            raise gcmd.error("%s requires XYZ homed" % (command_name,))
        if self.printer.lookup_object('print_stats').get_status(
                eventtime)['state'] == 'printing':
            raise gcmd.error("%s is unavailable while printing"
                             % (command_name,))

    def _run_tap_move(self, gcmd, coarse_pos, tap_xy, probe_xy,
                      test_accel, pre_tap_lift=None, threshold_g=None,
                      duration_ms=None, axes_reg=None, axes_label=None):
        toolhead = self.printer.lookup_object('toolhead')
        if pre_tap_lift is None:
            pre_tap_lift = self.pre_tap_lift
        if threshold_g is None:
            threshold_g = self.threshold_g
        if duration_ms is None:
            duration_ms = self.duration_ms
        if axes_reg is None:
            axes_reg = self.axis_reg
        if axes_label is None:
            axes_label = self.axis_name
        threshold_reg = int(threshold_g / .0625 + .5)
        duration_reg = int(duration_ms / .625 + .5)
        self._disarm_sensor()
        old_accel = toolhead.get_max_velocity()[1]
        self._set_accel(test_accel)
        tap_move_started = False
        tap_error = None
        tap_pos = None
        start_pos = None
        pre_tap_lift_applied = False
        try:
            # If the toolhead is already above the coarse reference, start the
            # probing move directly from its current height.  This avoids a
            # visible stop at a fixed pre-probe Z during mesh calibration.  A
            # coarse probe itself ends at coarse_z, and a failed full-range
            # probe may retract to at/below coarse_z; only those cases need the
            # configured lift before another probing move.
            probe_start_pos = toolhead.get_position()
            if probe_start_pos[2] <= coarse_pos[2]:
                probe_start_pos[2] = coarse_pos[2] + pre_tap_lift
                toolhead.manual_move(probe_start_pos, self.retract_speed)
                toolhead.wait_moves()
                self.gcode_move.reset_last_position()
                pre_tap_lift_applied = True
            self._prepare_sensor(
                threshold_reg=threshold_reg, duration_reg=duration_reg,
                axes_reg=axes_reg)
            start_pos = toolhead.get_position()
            target_pos = list(start_pos)
            target_pos[2] = self.probe_min_z
            if target_pos[2] >= start_pos[2]:
                raise gcmd.error(
                    "ADXL Tap probe start Z %.6f is not above absolute"
                    " lower bound %.6f"
                    % (start_pos[2], self.probe_min_z))
            tap_move_started = True
            phoming = self.printer.lookup_object('homing')
            tap_pos = phoming.probing_move(
                self.endstop, target_pos, self.speed)
        except self.printer.command_error as error:
            tap_error = error
        finally:
            self._disarm_sensor()
            try:
                if tap_move_started and not self.printer.is_shutdown():
                    current_pos = toolhead.get_position()
                    retract_pos = list(current_pos)
                    retract_pos[2] += self.retract_dist
                    toolhead.move(retract_pos, self.retract_speed)
                    toolhead.wait_moves()
            finally:
                # Restore even when a retract itself fails.  After MCU
                # shutdown movement is unavailable; never queue recovery Z.
                self.gcode_move.reset_last_position()
                self._set_accel(old_accel)
        if tap_error is not None:
            raise gcmd.error("ADXL Tap probe failed: %s" % (tap_error,))

        state = self.endstop.get_last_state()
        result = {
            'tap_xy': tuple(tap_xy), 'probe_xy': tuple(probe_xy),
            'coarse_pos': list(coarse_pos), 'start_pos': list(start_pos),
            'target_pos': list(target_pos),
            'trigger_pos': list(tap_pos), 'accel': test_accel,
            'pre_tap_lift': pre_tap_lift,
            'pre_tap_lift_applied': pre_tap_lift_applied,
            'threshold_g': threshold_g,
            'duration_ms': duration_ms,
            'axes_label': axes_label,
            'state': state,
        }
        self.last_tap_result = result
        tap_travel = start_pos[2] - tap_pos[2]
        contact_offset = coarse_pos[2] - tap_pos[2]
        result['tap_travel'] = tap_travel
        result['contact_offset'] = contact_offset
        if (contact_offset < self.min_valid_contact_offset
                or contact_offset > self.max_valid_contact_offset):
            raise gcmd.error(
                "ADXL Tap contact offset %.6f (travel %.6f) is outside"
                " valid window"
                " %.6f..%.6f"
                % (contact_offset, tap_travel,
                   self.min_valid_contact_offset,
                   self.max_valid_contact_offset))
        return result

    def _respond_tap_result(self, gcmd, result):
        tap_xy = result['tap_xy']
        probe_xy = result['probe_xy']
        coarse_pos = result['coarse_pos']
        start_pos = result['start_pos']
        tap_pos = result['trigger_pos']
        state = result['state']
        gcmd.respond_info(
            "ADXL Tap: tap_xy=%.3f,%.3f probe_xy=%.3f,%.3f"
            " coarse_z=%.6f start_z=%.6f trigger_z=%.6f"
            " target_z=%.6f pre_tap_lift=%.3f lift_applied=%d accel=%.3f"
            " threshold=%.4f duration_ms=%.3f axes=%s"
            " travel=%.6f contact_offset=%.6f"
            " source=0x%02x polls=%d query_ticks=%d"
            % (tap_xy[0], tap_xy[1], probe_xy[0], probe_xy[1],
               coarse_pos[2], start_pos[2], tap_pos[2],
               result['target_pos'][2],
                result['pre_tap_lift'], result['pre_tap_lift_applied'],
                result['accel'],
               result['threshold_g'], result['duration_ms'],
               result['axes_label'],
               result['tap_travel'], result['contact_offset'],
               state.get('int_source', 0), state.get('poll_count', 0),
               state.get('query_ticks', 0)))

    def _run_tap_group(self, gcmd, tap_xy, test_accel,
                       coarse_reference=None):
        sample_count = gcmd.get_int(
            'TAP_SAMPLES', self.tap_samples, minval=3)
        if not sample_count & 1:
            raise gcmd.error("TAP_SAMPLES must be an odd number")
        tolerance = gcmd.get_float(
            'TAP_SAMPLES_TOLERANCE', self.tap_samples_tolerance, minval=0.)
        retries = gcmd.get_int(
            'TAP_SAMPLES_RETRIES', self.tap_samples_retries, minval=0)

        for attempt in range(retries + 1):
            if coarse_reference is None:
                coarse_pos, probe_xy = self._run_coarse_probe(gcmd, tap_xy)
            else:
                coarse_pos, probe_xy = coarse_reference
            results = []
            sample_error = None
            for sample_index in range(sample_count):
                try:
                    result = self._run_tap_move(
                        gcmd, coarse_pos, tap_xy, probe_xy, test_accel)
                except self.printer.command_error as error:
                    sample_error = error
                    break
                results.append(result)
                self._respond_tap_result(gcmd, result)
            if sample_error is not None:
                gcmd.respond_info(
                    "ADXL Tap group rejected: attempt=%d error=%s"
                    % (attempt + 1, sample_error))
                continue
            sorted_results = sorted(
                results, key=lambda item: item['trigger_pos'][2])
            z_values = [item['trigger_pos'][2] for item in results]
            sample_range = max(z_values) - min(z_values)
            if sample_range <= tolerance:
                median = sorted_results[len(sorted_results) // 2]
                gcmd.respond_info(
                    "ADXL Tap group accepted: attempt=%d samples=%s"
                    " range=%.6f tolerance=%.6f median_z=%.6f"
                    % (attempt + 1,
                       ",".join(["%.6f" % (z,) for z in z_values]),
                       sample_range, tolerance,
                       median['trigger_pos'][2]))
                return median, results, sample_range
            gcmd.respond_info(
                "ADXL Tap group rejected: attempt=%d samples=%s"
                " range=%.6f tolerance=%.6f"
                % (attempt + 1,
                   ",".join(["%.6f" % (z,) for z in z_values]),
                   sample_range, tolerance))
        raise gcmd.error(
            "ADXL Tap group failed after %d group(s)" % (retries + 1,))

    def cmd_ADXL_TAP_PROBE(self, gcmd):
        self._check_available(gcmd, 'ADXL_TAP_PROBE')
        toolhead = self.printer.lookup_object('toolhead')
        test_accel = gcmd.get_float(
            'ACCEL', self.accel, above=0., maxval=1000.)
        pre_tap_lift = gcmd.get_float(
            'PRE_TAP_LIFT', self.pre_tap_lift,
            minval=0., maxval=5.)
        threshold_g = gcmd.get_float(
            'THRESHOLD', self.threshold_g,
            minval=.0625, maxval=15.9375)
        duration_ms = gcmd.get_float(
            'DURATION_MS', self.duration_ms,
            minval=.625, maxval=159.375)
        axes_reg, axes_label = self._get_test_axes(gcmd)
        tap_xy = tuple(toolhead.get_position()[:2])
        coarse_pos, probe_xy = self._run_coarse_probe(gcmd, tap_xy)
        result = self._run_tap_move(
            gcmd, coarse_pos, tap_xy, probe_xy, test_accel,
            pre_tap_lift=pre_tap_lift, threshold_g=threshold_g,
            duration_ms=duration_ms, axes_reg=axes_reg,
            axes_label=axes_label)
        self._respond_tap_result(gcmd, result)

    def cmd_ADXL_TAP_HOME(self, gcmd):
        self._check_available(gcmd, 'ADXL_TAP_HOME')
        bedmesh = self.printer.lookup_object('bed_mesh', None)
        if bedmesh is not None:
            bedmesh.set_mesh(None)
        toolhead = self.printer.lookup_object('toolhead')
        toolhead.manual_move(
            [self.home_xy[0], self.home_xy[1], None], self.xy_speed)
        toolhead.wait_moves()
        self.gcode_move.reset_last_position()
        test_accel = gcmd.get_float(
            'ACCEL', self.accel, above=0., maxval=1000.)
        median, results, sample_range = self._run_tap_group(
            gcmd, tuple(self.home_xy), test_accel)

        median_z = median['trigger_pos'][2]
        current_pos = toolhead.get_position()
        current_pos[2] -= median_z
        toolhead.set_position(current_pos, homing_axes=(2,))
        self.gcode_move.reset_last_position()
        toolhead.manual_move([None, None, self.home_z], self.retract_speed)
        toolhead.wait_moves()
        self.gcode_move.reset_last_position()
        gcmd.respond_info(
            "ADXL Tap Z home complete: median_z=%.6f range=%.6f"
            " final_z=%.6f"
            % (median_z, sample_range, toolhead.get_position()[2]))

    def cmd_ADXL_TAP_BED_MESH_CALIBRATE(self, gcmd):
        self._check_available(gcmd, 'ADXL_TAP_BED_MESH_CALIBRATE')
        bedmesh = self.printer.lookup_object('bed_mesh')
        calibrate = bedmesh.bmc
        bedmesh.set_mesh(None)
        calibrate._profile_name = gcmd.get('PROFILE', 'default')
        calibrate.update_config(gcmd)
        points = list(calibrate._get_adjusted_points())
        toolhead = self.printer.lookup_object('toolhead')
        test_accel = gcmd.get_float(
            'ACCEL', self.accel, above=0., maxval=1000.)
        current_pos = toolhead.get_position()
        safe_z = max(current_pos[2], self.mesh_horizontal_z)
        toolhead.manual_move([None, None, safe_z], self.retract_speed)
        toolhead.manual_move(
            [self.home_xy[0], self.home_xy[1], None], self.xy_speed)
        toolhead.wait_moves()
        self.gcode_move.reset_last_position()
        coarse_pos, probe_xy = self._run_coarse_probe(
            gcmd, tuple(self.home_xy))
        gcmd.respond_info(
            "ADXL Tap mesh center coarse reference:"
            " tap_xy=%.3f,%.3f probe_xy=%.3f,%.3f coarse_z=%.6f;"
            " all mesh points will reuse this reference"
            % (self.home_xy[0], self.home_xy[1],
               probe_xy[0], probe_xy[1], coarse_pos[2]))
        coarse_reference = (coarse_pos, probe_xy)
        positions = []
        total = len(points)
        for index, point in enumerate(points):
            current_pos = toolhead.get_position()
            safe_z = max(current_pos[2], self.mesh_horizontal_z)
            toolhead.manual_move([None, None, safe_z], self.retract_speed)
            toolhead.manual_move([point[0], point[1], None], self.xy_speed)
            toolhead.wait_moves()
            self.gcode_move.reset_last_position()
            median, results, sample_range = self._run_tap_group(
                gcmd, tuple(point), test_accel,
                coarse_reference=coarse_reference)
            trigger_pos = median['trigger_pos']
            positions.append([point[0], point[1], trigger_pos[2]])
            gcmd.respond_info(
                "ADXL Tap mesh point %d/%d: x=%.3f y=%.3f"
                " median_z=%.6f range=%.6f"
                % (index + 1, total, point[0], point[1],
                   trigger_pos[2], sample_range))

        current_pos = toolhead.get_position()
        safe_z = max(current_pos[2], self.mesh_horizontal_z)
        toolhead.manual_move([None, None, safe_z], self.retract_speed)
        toolhead.manual_move(
            [self.home_xy[0], self.home_xy[1], None], self.xy_speed)
        toolhead.wait_moves()
        self.gcode_move.reset_last_position()
        calibrate.probe_finalize((0., 0., 0.), positions)

    def cmd_ADXL_TAP_NO_CONTACT(self, gcmd):
        toolhead = self.printer.lookup_object('toolhead')
        eventtime = self.printer.get_reactor().monotonic()
        status = toolhead.get_status(eventtime)
        if 'xyz' != status['homed_axes']:
            raise gcmd.error("ADXL_TAP_NO_CONTACT requires XYZ homed")
        if self.printer.lookup_object('print_stats').get_status(
                eventtime)['state'] == 'printing':
            raise gcmd.error(
                "ADXL_TAP_NO_CONTACT is unavailable while printing")

        test_accel = gcmd.get_float(
            'ACCEL', self.accel, above=0., maxval=1000.)
        travel = gcmd.get_float('TRAVEL', self.max_travel, above=0.)
        arm_delay = gcmd.get_float(
            'ARM_DELAY', self.arm_delay, minval=0., maxval=.500)
        threshold_g = gcmd.get_float(
            'THRESHOLD', self.threshold_g,
            minval=.0625, maxval=15.9375)
        duration_ms = gcmd.get_float(
            'DURATION_MS', self.duration_ms,
            minval=.625, maxval=159.375)
        axes_reg, axes_label = self._get_test_axes(gcmd)
        threshold_reg = int(threshold_g / .0625 + .5)
        duration_reg = int(duration_ms / .625 + .5)
        start_pos = toolhead.get_position()
        if start_pos[2] - travel < self.probe_min_z:
            raise gcmd.error(
                "ADXL Tap no-contact move would exceed absolute Z lower"
                " bound %.6f" % (self.probe_min_z,))

        old_accel = toolhead.get_max_velocity()[1]
        old_arm_delay = self.endstop._arm_delay
        move_started = False
        triggered = False
        unexpected_error = None
        stop_pos = list(start_pos)
        try:
            self.endstop.set_arm_delay(arm_delay)
            self._set_accel(test_accel)
            self._prepare_sensor(
                threshold_reg=threshold_reg, duration_reg=duration_reg,
                axes_reg=axes_reg)
            target_pos = list(start_pos)
            target_pos[2] -= travel
            move_started = True
            phoming = self.printer.lookup_object('homing')
            try:
                stop_pos = phoming.probing_move(
                    self.endstop, target_pos, self.speed)
                triggered = True
            except self.printer.command_error as error:
                if "No trigger on probe after full movement" not in str(error):
                    unexpected_error = error
                stop_pos = toolhead.get_position()
        finally:
            self._disarm_sensor()
            if move_started:
                toolhead.manual_move(
                    [None, None, start_pos[2]], self.retract_speed)
                toolhead.wait_moves()
                self.gcode_move.reset_last_position()
            self._set_accel(old_accel)
            self.endstop.set_arm_delay(old_arm_delay)
        if unexpected_error is not None:
            raise gcmd.error(
                "ADXL Tap no-contact test failed: %s" % (unexpected_error,))

        state = self.endstop.get_last_state()
        gcmd.respond_info(
            "ADXL Tap no-contact: result=%s start_z=%.6f stop_z=%.6f"
            " travel=%.3f speed=%.3f accel=%.3f arm_delay_ms=%.1f"
            " threshold=%.4f duration_ms=%.3f axes=%s"
            " source=0x%02x polls=%d query_ticks=%d"
            % ("TRIGGERED" if triggered else "CLEAR", start_pos[2],
               stop_pos[2], travel, self.speed, test_accel,
               arm_delay * 1000., threshold_g, duration_ms, axes_label,
               state.get('int_source', 0),
               state.get('poll_count', 0), state.get('query_ticks', 0)))

    def cmd_ADXL_TAP_QUERY(self, gcmd):
        toolhead = self.printer.lookup_object('toolhead')
        print_time = toolhead.get_last_move_time()
        self.endstop.query_endstop(print_time)
        state = self.endstop.get_last_state()
        gcmd.respond_info(
            "ADXL Tap state: homing=%d source=0x%02x"
            " trigger_clock=%d polls=%d query_ticks=%d"
            % (state.get('homing', 0), state.get('int_source', 0),
               state.get('trigger_clock', 0), state.get('poll_count', 0),
               state.get('query_ticks', 0)))


def load_config(config):
    return ADXL345Tap(config)
