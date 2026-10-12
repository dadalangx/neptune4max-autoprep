[简体中文](software.md) | **English**

# Adapting the Factory Software and Building Source

## Identify the target printer first

These reference versions explain the interfaces; they are not a list of targets safe for direct replacement:

| Component | Reference environment |
|---|---|
| Platform | aarch64, Debian 10 / Armbian 22.05.0-trunk |
| Klipper | `v0.10.0-530-g3387a9c2-dirty`, Python 2.7.16 |
| Moonraker | `v0.7.1-609-gbdd0222-dirty`, Python 3.7.3 |
| autotune upstream | `andrewmcgr/klipper_tmc_autotune`, `191d1bfd69336d05de1d7f3907937e32a21b616d` with compatibility changes |

This approach retains the target's factory Klipper, Moonraker, touchscreen, and Python. Reference Klipper uses `/home/mks/klippy-env/bin/python` 2.7.16; Moonraker uses `/home/mks/moonraker-env/bin/python` 3.7.3. The terminal's `python3` version does not identify Klipper's service interpreter.

Inspect actual service arguments, Git HEAD, dirty files, and relevant source. `tools/preflight.py` only inventories the environment. Matching HEAD, reference file hashes, or a successful check do not prove that a stock printer can safely accept wholesale replacement. For different versions, have the agent compare interfaces, merge necessary logic, and identify unverified behavior.

Do not copy the owner's entire directory, backups, saved_variables, mesh, or PID data. Merge only sections required for selected features; check include paths, duplicate macros, rename_existing, pin conflicts, and SAVE_CONFIG overrides.

## Factory startup coordinates do not prove real homing

The inspected factory configuration includes delayed macro `KINEMATIC_POSITION`, which assigns X110/Y110/Z0 through `SET_KINEMATIC_POSITION`. It performs no physical homing and may leave displayed position and homed flags inconsistent with reality. Any additional touchscreen involvement has not been independently confirmed.

Retaining factory software does not justify trusting these coordinates. After power-on, a G-code restart, or a Klipper service restart, the agent must confirm successful real three-axis G28 in the current startup before subsequent XYZ motion. Until homed, users should not issue arbitrary moves or click web mesh calibration. See the [homing rule](validation.en.md#homing-after-power-on-or-restart) for conditions and failure handling. This is an operating requirement, not a requirement to modify startup macros or the touchscreen when preparing publication materials.

## Modules and target locations

Use the [implementation reuse guide](implementation-reuse.en.md) to select existing code, related parent sections, and dependencies by feature. The index does not require loading every module.

| Repository file | Target location or purpose |
|---|---|
| `source/klipper/klippy/extras/adxl345_tap.py` | Target Klipper `klippy/extras/`; Linux MCU Tap endstop and measurement core |
| `source/klipper/klippy/extras/adxl345_z_offset.py` | Same directory; registers print offset, checks/preparation commands, and adaptive resolver |
| `source/klipper/klippy/extras/adaptive_mesh_bounds.py` | Same directory; PA calibration geometry parsing helper |
| `source/klipper/klippy/extras/adaptive_mesh_drift.py` | Same directory; center-reference time interpolation correction; merge matching adaptive cfg without replacing native mesh/probe |
| `source/klipper/klippy/extras/adxl345.py` | Reference host driver with vendor branch differences; compare and merge rather than replace another version by default |
| `source/klipper/src/sensor_adxl345.c` | **Custom Tap build source**; requires Linux MCU compilation |
| `source/klipper/linuxprocess.config` | Minimal Linux process build selection, not an STM32 board configuration |
| `source/klipper_tmc_autotune/` | Third-party plugin on a fixed upstream baseline with Python 2/old Klipper adaptation |
| `source/moonraker/metadata.py` | Old Moonraker reference source including vendor preview interfaces and Bambu parsing changes |
| `source/klipper/klippy/extras/gcode_move.py` | Existing factory coordinate implementation for offline regression; replacement is not required |
| `source/klipper/klippy/extras/controller_fan.py` | Old driver fan reference module; merge only empty heater-name filtering rather than overwrite another version |
| `config/reference/` | Feature configurations and parent excerpts; merge and calibrate for the target |

## Linux MCU source and build

On 2026-10-11, printer file `/home/mks/klipper/src/sensor_adxl345.c` was the original source (SHA-256 `4a4a0e95...`) without Tap commands. Running `/usr/local/bin/klipper_mcu` was custom (full hash in the manifest) and matched the deployment binary retained by the earlier project. That project had restored the disk C source and later reinstalled the compiled binary.

Rebuilding directly from that disk source would therefore lose Tap. This repository publishes the earlier project's **custom Tap C**, SHA-256 `2d2a55b0dc191fe99b90c5be6c88442181325596e96329b397541248d7630287`. `patches/adxl-linux-mcu.patch` was generated against Klipper `3387a9c23d940c7d449f197b272616eda11a5e3d`.

No ready-to-install MCU binary is distributed here. Source and historical deployment files establish provenance, but the publication work did not rebuild, compare new build artifacts, or install on another machine. Compiler version and build time may change binary hashes; command dictionaries and matching interfaces also need validation.

Use a separate target-compatible build directory, preserving the active checkout and original `.config`. For the reference baseline: obtain matching Klipper source → check and apply the Tap C differences → supply the Linux process configuration → `make olddefconfig` → `make`. This version's Makefile uses Python 3 for build scripts; that does not require migrating Klippy from Python 2.

Confirm dependencies from the source and Linux toolchain. Install only missing required items rather than upgrade the system or all pip packages. Verify an executable for target aarch64, dictionary commands `adxl345_tap_home` / `adxl345_tap_query_state`, and parameter signatures matching host `adxl345_tap.py`. A `strings` match proves only that text is present, not protocol or feature correctness.

Before deployment, save the original `/usr/local/bin/klipper_mcu`, actual service definition, and modified files with permissions and hashes. The reference service is **`klipper_mcu`**, generated from SysV `/etc/init.d/klipper_mcu`, not an assumed `klipper-mcu.service` file. Stop/start using the target's actual service relationships, load matching host modules, and check Ready. Restore the old binary and matching modules on failure. Checking Ready should not automatically heat or contact the bed.

The implemented approach does not flash the STM32 mainboard. Generic build comments in a configuration header are not a reason to flash it. Historical chip descriptions conflict with vendor wording; preserve the currently working mainboard firmware.

## autotune_tmc: code adaptation without upgrading Python

Upstream is fixed at `191d1bfd69336d05de1d7f3907937e32a21b616d`. Changes are in `patches/autotune-python2-compat.patch`, with the complete adapted version in source.

Main changes:

- `from __future__ import division` avoids Python 2 integer truncation affecting TOFF and other calculations.
- Fall back from unavailable `inspect.signature` to `inspect.getargspec`.
- Replace the `Enum` dependency with validated string categories.
- Use a compatibility calculation path when old Klipper lacks `TMCtstepHelper`.
- Adapt old TOFF and enable-cache interfaces to avoid incorrectly enabling an offline motor.

These fixes do not upgrade Python. Reference X/Y/extruder use autotune; neither Z does. The plugin calculates parameters from supplied motor data and **does not measure resistance or inductance itself**. Read custom X/Y constants in the parent configuration too. An approximate QIDI extruder entry is not the actual stock motor specification.

Do not run upstream's rolling `install.sh` and assume this patch will match. Fix the baseline, inspect changes in an isolated copy, and validate against the target interpreter and interfaces.

## Driver cooling compatibility with old Klipper

After moving driver cooling from FAN6/PC7 to FAN4/PA8, merge `config/reference/driver_cooling.cfg` into the main configuration. It independently monitors `stepper_x, stepper_y, stepper_z, stepper_z1, extruder`, retaining PC7 `[heater_fan fan1]` and PB7/PC9 model-fan routing.

Reference old `configfile.getlist()` parses empty `heater:` as `("",)`. Original controller_fan then tries to find a heater with an empty name and fails. Filter empty names when reading the list in `controller_fan.py`:

```python
self.heater_names = [
    n for n in config.getlist("heater", ("extruder",)) if n]
```

This retains default extruder and valid heater-list behavior while supporting motor-only cooling. It works on Python 2 without upgrading the environment. See [controller-fan-empty-heater.patch](../patches/controller-fan-empty-heater.patch); baselines and hashes are in `patches/baselines.json`. A target that already handles empty lists needs no repeated fix. Compare different source versions and merge only this necessary logic.

Back up affected source, main configuration, and original fan configuration, then load while idle. Ordinary G-code `RESTART` does not guarantee reimport of Python already loaded by the process. Restart the Klipper process through the actual service and check Ready so cached code is not mistaken for the new implementation. Recheck this compatibility point after future source updates or replacements.

## Moonraker metadata

Changes add BaseSlicer preview fallback and BambuStudio recognition, including total layers, first-layer height, and model height. The patch is against `bdd0222a1cec451fe3bf37e721cca7409877bf61` but contains pre-existing vendor differences. **It is a comparison aid; not every difference is new project code.** Merge the minimum required changes into other Moonraker versions.

Historical `.thumbs` permission problems were fixed by correcting that directory's ownership, not by recursively chmod/chowning the whole G-code tree. Confirm the actual service user and permissions, then fix the specific directory.

## Adaptive mesh reference drift correction

The Python 2-compatible module was added on 2026-10-13 without upgrading Klipper, Python, or MCU code. It uses the current old bed_mesh/probe interfaces and real homing events; compare other versions first. It supports automatic rectangular meshes without faulty_regions. `tests/fixtures/vendor-bed-mesh-3387a9c2.py` is an offline matrix fixture, not an installation or replacement file. See [drift correction](adaptive-mesh-drift.en.md) for parameters and calls, and [agent steps](../skills/neptune4max-mods/references/adaptive-mesh-drift.md) for backups, deployment, small-grid validation, and rollback.

## Configuration dependencies

ADXL configuration includes adaptive cfg. Load ADXL before the independent dual Z PREPARE_WIPE wrapper so the original command exists when renamed. Without ADXL, do not load that dependent wrapper; initially retain only Z drivers, z_tilt, and DUAL_Z_LEVEL.

Cold pull depends on auxiliary fan routing, respond, beeper, permitted low-temperature retraction, and travel. Reference `min_extrude_temp:70` permits retraction at 90°C, but affects machine-wide protection and must not be silently lowered on someone else's printer. The original configuration's very large extrusion cross-section limit is not required for this project. Retain reasonable target limits and check the specific maintenance actions.

Parent motor constants, Z speed limits, probe/mesh parameters, touchscreen mesh redirection, auxiliary shutdown on exit, and releasing only X/Y/E cannot be implemented by copying one include. Compare excerpts, modules, and the target configuration to produce explicit merge differences.
