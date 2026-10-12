[简体中文](implementation-reuse.md) | **English**

# Reproduce the setup from existing implementations

The main features already have source code and configuration used by the reference printer. Start with those files, retain their implementation, and adapt target-version interfaces, wiring, geometry, and calibration. Workflow documents explain when to do each step; they do not replace the code.

## Find code by feature

[implementation-map.json](../implementation-map.json) maps features to exact files, configuration sections, dependencies, destination paths, and evidence limits. Select the needed features first, then read their files instead of loading all source code or historical debugging records.

Run these commands with Python 3 in the repository on the **control computer**:

```sh
python tools/reference_bundle.py
python tools/reference_bundle.py dual-z
python tools/reference_bundle.py dual-z --config
python tools/reference_bundle.py adaptive-mesh --with-dependencies
python tools/reference_bundle.py --check
```

Without a feature ID, the tool lists features. An ID produces a small implementation index; `--config` prints the corresponding sections from the original files; `--with-dependencies` includes dependencies of the supplied implementation; `--check` validates paths, sections, and dependency relationships. It only reads local files. It does not install, connect to a printer, or execute G-code. Output is for adaptation review, not a configuration to load directly. Excerpts omit some file-header guidance, so also read the indexed prerequisites and necessary original files.

The reader is a newly added, offline-checked tool, distinguished from Klipper code running on the reference printer. Python 3 on the control computer does not require upgrading the printer's Python.

## Features and implementation entry points

| Feature / index ID | Existing implementation | Differences to resolve |
|---|---|---|
| PA11 basis `probe-base` | `probe`, `safe_z_home`, and original Z in [parent sections](../config/reference/printer-sections.cfg); `printer` and `bed_mesh` in [host/motion sections](../config/reference/host-sensors-motors.cfg) | Target probe offsets, real homing, travel, and coordinate basis |
| Independent Z `dual-z` | Drivers, `z_tilt`, and `DUAL_Z_LEVEL` in [dual-Z configuration](../config/reference/independent_dual_z.cfg); [existing M17/M84](../config/reference/host-sensors-motors.cfg) | Observe sides/directions and measure screw geometry; reuse paired Z enable/release |
| Part cooling `part-cooling` | [Existing M106/M107 routing](../config/reference/bambu_aux_fan.cfg) and `[fan]` in [parent sections](../config/reference/printer-sections.cfg) | Pins and fan identity; reuse routing and proportional scaling |
| Driver cooling `driver-cooling` | [FAN4 configuration](../config/reference/driver_cooling.cfg) and [legacy patch](../patches/controller-fan-empty-heater.patch) | Monitored motors must exist; merge the empty-heater fix only if needed |
| Tap foundation `adxl-linux` | [Host Tap core](../source/klipper/klippy/extras/adxl345_tap.py), [ADXL host driver](../source/klipper/klippy/extras/adxl345.py), [custom C](../source/klipper/src/sensor_adxl345.c), [Linux build configuration](../source/klipper/linuxprocess.config) | Rebuild Linux MCU using a compatible complete source tree; verify service and protocol |
| Automatic offset `adxl-offset` | [Pre-print module](../source/klipper/klippy/extras/adxl345_z_offset.py), [configuration](../config/reference/adxl345_z_offset.cfg), [required parser dependency](../source/klipper/klippy/extras/adaptive_mesh_bounds.py) | Contact window, same-point PA11 basis, first-layer calibration; retain soak, fuzz, three-tap and one-use-session logic |
| Reference drift `mesh-drift` | [Existing correction module](../source/klipper/klippy/extras/adaptive_mesh_drift.py) and `[adaptive_mesh_drift]` in [configuration](../config/reference/adaptive_bed_mesh.cfg) | Probe/nozzle center coordinates and old APIs; retain median references and time interpolation |
| Adaptive mesh `adaptive-mesh` | [Existing builder macros](../config/reference/adaptive_bed_mesh.cfg), [bounds parser](../source/klipper/klippy/extras/adaptive_mesh_bounds.py), `cmd_ADAPTIVE_MESH_RESOLVE` in the ADXL module | Bounds, point counts, contact coverage; reuse the current registration for the full setup |
| Complete preparation `print-preparation` | [Start code](../slicer/start_gcode.txt), [end code](../slicer/end_gcode.txt), [3MF](../slicer/naptune4max.3mf), PREPARE_WIPE wrapper in the dual-Z file | Start with the existing order; adapt wiping geometry, first-layer trim and [known slicer issues](slicer.en.md#known-adaptation-items-in-the-original-files) |
| Screen mesh compatibility `mesh-profile-compat` | [Existing BED_MESH_PROFILE wrapper and delayed load](../config/reference/adxl345_z_offset.cfg) | Optional; create the target's own `default` profile before loading it |
| autotune `autotune` | [Complete adapted plugin](../source/klipper_tmc_autotune/autotune_tmc.py), [motor_constants](../source/klipper_tmc_autotune/motor_constants.py), [database](../source/klipper_tmc_autotune/motor_database.cfg), [compatibility patch](../patches/autotune-python2-compat.patch) | Pinned version and actual motor inputs; retain Python 2 compatibility code |
| Layer metadata `metadata` | `BambuStudio` and `BaseSlicer` in [existing metadata.py](../source/moonraker/metadata.py), [difference patch](../patches/moonraker-metadata-reference-vs-upstream.patch) | Merge necessary differences into target Moonraker; old UI current-layer estimates remain limited |
| Cold pull `cold-pull` | [Existing maintenance/beep macros](../config/reference/cold_pull.cfg), [expanded G-code](../slicer/COLD_PULL_150mm_90C.gcode) | Material, low-temperature retraction protection, and beep volume |
| Exit/cancel `print-exit` | [Newly exported existing macros](../config/reference/print-exit-macros.cfg) and existing end G-code | Merge into target handlers; check PLR dependencies, limit restoration, and Z holding behavior |

## Gaps found by this audit

The main algorithms were already published. The gaps concerned **discovery, related parent-configuration code, and exit-handler references**. This update adds the feature index, section reader, and existing reference `PRINT_END` / `CANCEL_PRINT` macros. The original macros agree exactly across two saved running configurations. The export retains their implementation with only trailing whitespace normalized. Exporting them did not modify the printer or execute cancellation. Provenance and hashes were added to [reference-manifest.json](../reference-manifest.json).

Some parts do not have an independently deployed and validated variant:

- **Adaptive bounds without ADXL:** The full setup registers `ADAPTIVE_MESH_RESOLVE` in the ADXL module. Reuse its existing dependencies for that setup. The standalone `ADAPTIVE_MESH_DRIFT_CALIBRATE` command accepts explicit mesh bounds without the ADXL resolver. Automatic Bambu bounds with no ADXL requires a separate registration adaptation; the repository does not claim that variant is already verified.
- **Linux MCU build output:** Custom source, patches, configuration, and historical deployment provenance are supplied. There is no distributable ready-to-install binary or new rebuild/second-stock-printer certification. Follow the [build procedure](software.en.md#linux-mcu-source-and-build) and verify the target protocol.
- **Another printer's calibration:** Wiper geometry, motor sides, contact windows, first-layer trim, PID, and meshes require target-machine results. Reusing algorithms does not replace measurement.

`gcode_move.py` and the vendor mesh test fixture are offline regression references, not installation files. Retain the target's factory pause, filament detection, PLR, and related implementations rather than rebuilding them or copying the entire vendor configuration.

## Reuse rules for agents

Use the index to obtain existing files and dependencies, compare the target, and change only demonstrated interface, configuration, or calibration differences. Do not rebuild state machines, mesh scheduling, fan routing, or compatibility calculations from prose when their code is already present. Record why any implementation change is needed and how it is tested; retain the original as a comparison baseline.

Record selected code, adaptation differences, target measurements, and evidence in the private handoff. Follow the [replication workflow](../skills/neptune4max-mods/references/replication-workflow.md) for staged loading and acceptance. Source reuse alone does not establish successful contact or printing on another machine.
