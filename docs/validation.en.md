[简体中文](validation.md) | **English**

# Validation, Troubleshooting, and Rollback

## Available evidence

The owner has used the modified reference printer over time and confirms normal operation. Historical records include dual Z side/direction checks, main and auxiliary fan tests, beep listening tests, ADXL repeatability, and first-layer use. After replacement with the MKS driver, R110 was configured as 0.110 ohm and UART registers read successfully. This single-machine history is not batch compatibility testing on stock printers.

Offline regression covers coordinates/mesh compensation, stabilization timing, one-use sessions, bounds parsing, whole-group contact retries, and failure recovery. Fault paths use simulated objects, not fresh bed impacts or forced communication loss. Historical slicer tests use an archived fixture separate from the latest user-supplied start/end files.

The independent Python 2 autotune patch was previously applied to a fixed upstream copy and matched the modified printer's source hashes. The required custom Linux MCU C was collected without rebuilding or deploying it during that publication work. Full adaptation, contact, and print acceptance have not been completed on a second stock 4 Max.

Dedicated FAN4 driver cooling was added on 2026-10-12. Compatibility syntax was checked in actual Python 2; loading reached Ready, with other parsed settings unchanged. No movement, extrusion, or heating was performed. Briefly enabling the extruder changed fan output from 0 to 1; after release it remained 1 at 30 seconds and became 0 at 63 seconds, confirming an approximately 60-second delay. The owner confirmed actual fan operation and original Z left/E1 right on the reference machine. Public documentation keeps conclusions, not private run records.

Center-reference time interpolation was added on 2026-10-13. A fixed-XY experiment with 90 samples and 18 independent references supported method selection. Ten new offline tests passed locally and in actual Python 2.7.16. A real-XY 4×4 scan completed 16 points and four additional references; every native matrix value matched independently recalculated corrected points. This check included neither ADXL contact nor a first-layer print and is not complete modification or cross-machine precision certification. See the [drift validation record](validation/adaptive-mesh-drift-20261013.en.md) for protocol, data, and limits.

## Homing after power-on or restart

**After each power-on or Klipper restart, perform real Home before subsequent XYZ movement or mesh calibration.** The reference factory configuration contains delayed macro `KINEMATIC_POSITION`: about three seconds after startup it assigns X110, Y110, Z0 through `SET_KINEMATIC_POSITION`. This assigns coordinates without locating physical origins; actual toolhead position may be entirely different. Additional touchscreen involvement has not been independently established, so the behavior is not attributed solely to the touchscreen.

User reminder: **until physically homed after power-on, do not issue arbitrary toolhead moves or click web interface mesh calibration**, including direct `BED_MESH_CALIBRATE`. Default coordinates, Ready, or a homed indicator do not replace real homing.

After `RESTART`, `FIRMWARE_RESTART`, a Klipper service restart, or detected power cycling, the agent must re-establish homing evidence. Confirm the printer is idle, a person is beside it, homing paths and lift clearance are unobstructed, and wiring/probe conditions permit safe homing. Within authorization, execute real three-axis `G28` and check successful completion before ordinary `G0/G1`, individual motor checks, wiping, tilt adjustment, or mesh calibration. Checking only `toolhead.homed_axes` is insufficient; do not bypass this with `SET_KINEMATIC_POSITION` or forced motion.

Homing itself moves the printer and must not be attempted blindly with unknown new driver direction, probe operation, or clearance. If safe homing is impossible or fails, resolve wiring, mechanics, and space with the user and stop subsequent movement; do not first move away using assumed coordinates. Valid real homing in the current startup permits continued motion without G28 before every command. A new restart invalidates that evidence. Read-only or fan-enable checks without XYZ motion do not require physical homing first.

## Validation order when reproducing the setup

This is a brief sequence. Agents start from the [replication workflow](../skills/neptune4max-mods/references/replication-workflow.md) and follow deployment/calibration stages with prerequisites, evidence, and failure handling. Missing dependencies prevent use of the complete start code.

1. Inspect software baselines, interpreters, services, and current configuration. Back up affected files, Linux MCU program, and permissions, and download the backup to the computer. Compare unknown vendor changes before preparing differences.
2. Complete wiring checks with power off. First check UART without XYZ motion and establish safe homing conditions. Resolve uncertain new driver direction or probe operation with the user before moving or homing.
3. While idle with an observer and confirmed paths/clearance, perform real XYZ G28, confirm PA11 triggering and successful homing, and follow the restart rule above. Only then make small, slow individual side/direction checks. Restore gantry alignment before full dual Z adjustment. Do not guess z_positions from unclear observations.
4. Validate selected independent fan channels, mesh reachability, and plans. Driver cooling can be checked by briefly enabling a motor without turning it, then restoring enable state to check the delay. Do not release Z motors holding the gantry merely to test fan stopping. PLAN_ONLY checks mesh planning, not physical reachability.
5. For ADXL, verify the custom Linux MCU protocol, then high-position no-contact behavior, controlled contact repeatability, contact window, and first layer. Do not run silicone contact paths without the mount. Lower thresholds, larger windows, or lower Z limits are not general error fixes.
6. Run the adapted complete slicer preparation and first-layer test. Record features, parameters, versions, results, and unaccepted items. Validate cold pulls, beeps, and material recipes separately as optional maintenance features.

An nginx 504 on a long G-code request may leave the backend running. Query state and progress before taking further action; do not automatically repeat homing, heating, extrusion, or contact commands.

## When something fails

- UART errors: recheck power, module/jumpers, pins, and address before changing mechanical coordinates.
- Z_TILT makes alignment worse: stop and check actual sides, z_positions order, and direction; do not hide it by relaxing tolerance.
- ADXL misses contact or triggers above the bed: stop contact probing and check raw axis, sensor, Linux MCU commands, recipe, and mechanical response. Communication or position-recovery errors prohibit blind repeated descent.
- First-layer error: check the PA11 reference, mesh compensation at the measurement point, existing offsets, and your filament's first-layer trim. Do not copy +0.140.
- Malformed `RESPOND`: the old extended-command parser truncates at semicolons even inside quotes. Use text such as “and” instead of `;`. Repository cold-pull messages already use the corrected form.
- Wrong web layer information: inspect metadata, actual UI estimation, variable layer height, and Z-hop. Do not assume a whole Klipper upgrade is needed.

## Rollback

Confirm the printer is idle and identify changed files. Restore the matching original Linux MCU program, host modules, and configuration, then restart through the actual services. Compare current files before restoring so later user changes are not overwritten. Retain sanitized evidence and failure logs.

Run `python -B -m unittest discover -s tests -v` on the development computer for offline checks; it does not connect to the printer. Passing on Python 3 does not prove Python 2 deployment. Also perform compatibility checks with the target interpreter without operating hardware.
