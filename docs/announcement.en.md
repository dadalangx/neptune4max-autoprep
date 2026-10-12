[简体中文](announcement.md) | **English**

# Publication Copy

## GitHub project description

Neptune 4 Max AutoPrep automates print preparation with independent dual Z, automatic Z offset, A1 silicone wiping, adaptive mesh, independent cooling, and Bambu Studio support. Includes source, reference configurations, and an AI skill.

## Project announcement

I have organized the modifications to my Neptune 4 Max into the open-source **Neptune 4 Max AutoPrep** project, sharing print-preparation automation for others interested in this large-format printer.

The setup retains the factory toolhead, hotend, extruder, motors, and bed. Working within the factory software environment, it adds independent dual Z, pre-print gantry alignment, ADXL nozzle-contact Z offset measurement, silicone wiping, adaptive mesh, independent auxiliary cooling, and dedicated stepper driver cooling. It also includes cold-pull maintenance macros, proportional main fan output, Bambu metadata adaptation, and compatibility changes for old Python.

The added Z driver is the MKS TMC2209 V2.0 tested by the owner. Only UART is bridged at E1; an R110 module uses 0.110 ohm sense resistance. The project explains how to verify wiring, direction, and leveling coordinates.

Wiping uses a readily available Bambu Lab A1-compatible silicone strip mounted on the plastic bracket at the end of the bed cable connection. The repository includes installation and UART jumper photos, factory wiring, and board pin diagrams. Original Z controls the reference printer's left side and E1 its right, but every reproduction needs physical checks. Driver cooling moves to FAN4 and runs while motors are energized, stopping 60 seconds after all are released.

The approach is modification ideas + source + reference configurations + an AI skill. Have Codex or another agent inspect the project and your printer environment before adapting selected features. You do not need to become a Linux expert first, but wiring, initial contact checks, and first-layer validation still require a person beside the printer.

The project supplies my Bambu Studio 3MF and separate start/end G-code. Open it as a project to inspect and load settings, then save your own user presets. Machine-specific wiping positions and first-layer corrections need recalibration.

The full combination comes from one printer in actual use and has not completed full reproduction acceptance on a second stock 4 Max. Sanitized environment reports, wiring photos, reproduction results, and adaptation patches are welcome to build an evidence-based support range.

Project: [Neptune 4 Max AutoPrep](https://github.com/dadalangx/neptune4max-autoprep)

## Initial release notes

Reference-material release, dated 2026-10-12. Contents:

- Hardware combination, pins, R110 parameters, and motor-side validation.
- Custom ADXL Python modules, Linux MCU Tap C, and fixed-baseline patches.
- Reference configurations for independent dual Z, auxiliary fans, dedicated driver cooling, cold pull, and adaptive mesh.
- Old-Python autotune compatibility and reference Moonraker metadata adaptation.
- Bambu Studio project, start/end code, AI skill, and offline regression tests.

Personal identifiers were removed from published copies; the owner's printer IP, private backups, and logs are excluded. A1 wiper and E1 jumper photos are included. Complete acceptance on another stock printer remains outstanding.
