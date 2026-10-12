[简体中文](README.md) | **English**

# Neptune 4 Max AutoPrep

Automated print preparation for the Elegoo Neptune 4 Max / ZNP K1 V2.0, with modification guides, custom source code, reference configurations, and an AI handoff guide.

This project documents the modifications developed on a printer in regular use. Give the repository to Codex or another AI agent so it can inspect your printer, adapt the features you choose, back up the affected files, and validate each change. The project shares an approach and its implementation; it does not provide an installer that overwrites the factory configuration.

**The owner confirms that the reference printer operates normally. The complete setup has not yet been reproduced and accepted on a second, unmodified Neptune 4 Max.** Coordinates, motor directions, currents, and nozzle contact windows include calibration values specific to the reference machine. They are not universal settings for every 4 Max.

**After powering on or restarting Klipper, perform real homing before moving XYZ or calibrating the bed mesh.** The factory startup sequence may assign default toolhead coordinates, making the displayed position and homed state disagree with the physical position. Until real Home has completed during the current startup, users must not issue arbitrary toolhead moves or click the web interface's bed mesh calibration button. After every power-on, `RESTART`, `FIRMWARE_RESTART`, or Klipper service restart, an agent must confirm that a real `G28` has succeeded before subsequent XYZ moves; checking `homed_axes` alone is insufficient. Before homing, check the travel path, clearance, and probe conditions as well. See the [homing rules after startup or restart](docs/validation.md#上电与重启后的归位规则).

## Features

| Feature | Purpose and implementation |
|---|---|
| Independent dual Z and automatic gantry alignment | An added MKS TMC2209 V2.0 lets the original Z and E1 channels drive the two leadscrews independently. The PA11 proximity probe measures three nearby points on each side; `Z_TILT_ADJUST` aligns the gantry, followed by Z homing. |
| Automatic nozzle Z offset before printing | Reuses the stock toolhead's ADXL345. The median of three nozzle contacts and the bed mesh value at the contact point determine a temporary offset. PA11 remains responsible for routine homing and bed mesh probing. |
| Heat stabilization, purging, and silicone wiping | Waits for sustained bed temperature stability at the first-layer target, then performs a hot wipe followed by a cooler wipe. The final contact measurement uses a one-time wipe session tied to the current file. |
| Adaptive bed mesh | Probes the area needed for Bambu Studio's first-layer bounds while keeping the ADXL contact area covered. Also supports parsing explicitly marked pressure advance calibration line bounds. |
| Independent auxiliary cooling fan | The main fan uses FAN2/PB7 and the auxiliary fan uses FAN3/PC9. Bambu `M106 P2` controls the auxiliary fan independently. |
| Dedicated driver cooling fan | Moves the driver fan from FAN6/PC7, which shares the hotend cooling output, to FAN4/PA8. Runs at full speed while any stepper is enabled, then turns off 60 seconds after all steppers are released. |
| Proportional main fan control | Maps a 0–100% command to 0–70% PWM while retaining the full command range. The auxiliary channel still supports 100% PWM. |
| Cold-pull maintenance | Homes, moves to Z200, purges 150 mm at 250°C, then cools through 110°C to 90°C for retraction. Releases the extruder motor, holds the nozzle target at 90°C, and beeps twice. |
| Bambu metadata support | Adds recognition of Bambu layer count, layer height, model height, and previews to the older Moonraker version. The corresponding older Fluidd version estimates the current layer from Z. |
| Compatibility with the original software | Keeps the factory Klipper/Python environment and provides `autotune_tmc` source and patches adapted for Python 2 and older Klipper interfaces. |

The aim is to reduce repetitive manual leveling and preparation. First-layer quality, walls, and cooling still depend on mechanical condition, material, and calibration. Software cannot straighten a bent leadscrew or replace mechanical bed leveling.

## Hardware modifications

- Remove the top Z synchronization belt and the toothed timing pulleys on both leadscrews.
- Install an **MKS TMC2209 V2.0** in E1. The reference module has two current-sense resistors marked **R110**, configured as `sense_resistor: 0.110`. Bridge **UART only**; leave M0/M1/M2 open.
- Separate the two previously parallel Z motor leads and crimp them for two independent driver channels: **original Z and E1**.
- Connect the auxiliary fan to FAN3/PC9 and keep the main fan on FAN2/PB7.
- Move the driver cooling fan from FAN6/PC7 to FAN4/PA8 so it follows stepper enable state independently. FAN1/PC7 continues to cool the hotend.
- Use a readily available **silicone nozzle wiper for the Bambu Lab A1**, mounted on the **plastic bracket at the heated bed's cable connection end**, as shown below. Measure wiping coordinates and contact height on your own printer.

**Verify which driver controls each physical side.** The agent must have the person performing the modification observe small, slow motor tests to confirm the side and positive direction before configuring gantry alignment coordinates. See [hardware and dual Z](docs/hardware.md).

E1 jumpers: bridge UART only and leave M0/M1/M2 open. The driver module is temporarily absent in the photo so the jumper position is visible.

![E1 with only the UART jumper installed](docs/images/e1-uart-jumper.jpg)

Bambu Lab A1 silicone wiper mounted on the plastic bracket at the bed cable connection end:

![Installed Bambu Lab A1 silicone nozzle wiper](docs/images/a1-wiper-installation.jpg)

The [factory mainboard wiring diagram](docs/images/stock-mainboard-wiring.png) and [ZNP K1 V2.0 pin layout](docs/images/znp-k1-v2-pinout.png) help identify connectors. See [hardware reference diagrams](docs/hardware.md#接线和引脚参考图) for all illustrations.

The toolhead, hotend, extruder, axis motors, and heated bed remain stock. The QIDI motor database entry in the configuration is an approximate parameter choice; it does not indicate an actual extruder replacement.

## Reproduce the setup with an AI agent

Download or clone this repository. Give your agent the following prompt and replace `<your printer address>` with the actual address:

> Read this project's README and skills/neptune4max-mods/SKILL.md, then adapt the Neptune 4 Max for the features I choose. My printer address is `<your printer address>`. First inspect the factory software versions, interpreters, services, and existing configuration. Do not upgrade Klipper, Moonraker, or Python. Provide the hardware prerequisites, file-by-file changes, and backup plan before implementing each feature within my authorized scope. Do not overwrite the entire printer.cfg or treat the reference machine's side mapping, contact windows, wiping coordinates, or first-layer correction as my calibration values. After each power-on or Klipper restart, do not trust default coordinates or homed_axes; confirm that a real G28 has succeeded before moving XYZ or calibrating the bed mesh. Perform motion and contact validation with me beside the printer after I confirm the available clearance.

Common factory SSH credentials are username `mks` and password `makerbase`. These are public factory login details; use your own credentials if they have been changed. Find your printer's address on its screen or in your router. The owner's actual address is not included in this repository.

The skill is a working guide for an AI agent; reading it does not install software. Have the agent read it directly from the repository, or install the entire `skills/neptune4max-mods` directory according to your tool's local skill instructions.

Work through the modules in stages: environment inventory → dual Z/fans as applicable → software compatibility → basic PA11 calibration → ADXL and wiper calibration → slicer and first-layer validation. See [software adaptation](docs/software.md) and [validation and rollback](docs/validation.md) for dependencies and details.

**Documentation language:** this README is available in English and Chinese. The detailed guides and AI skill are currently in Chinese.

## Bambu Studio files

Open [slicer/naptune4max.3mf](slicer/naptune4max.3mf) as a **project** to load its printer, process, and filament settings, then save them as your own user presets. The reference export was made with `BambuStudio-02.08.02.60`, a 0.4 mm nozzle, Generic PETG, and a 3DBenchy model.

The standalone [start G-code](slicer/start_gcode.txt) and [end G-code](slicer/end_gcode.txt) preserve the owner's supplied content and match the code embedded in the 3MF. Read the [slicer adaptation guide](docs/slicer.md) before using them: a stock printer without the wiper must not execute the wiping path, and `+0.140 mm` is the reference machine's first-layer correction.

## Software baseline and sources

| Component | Inspected reference environment |
|---|---|
| Platform | aarch64, Debian 10 / Armbian 22.05.0-trunk |
| Klipper | `v0.10.0-530-g3387a9c2-dirty`, Python **2.7.16** |
| Moonraker | `v0.7.1-609-gbdd0222-dirty`, Python **3.7.3** |
| Upstream autotune | `andrewmcgr/klipper_tmc_autotune`, `191d1bfd69336d05de1d7f3907937e32a21b616d`, with compatibility modifications |
| Tap Linux MCU | Custom `klipper_mcu` built from matching C source. This approach does not require reflashing the mainboard STM32. |

Identical Git HEADs do not prove identical vendor modifications. `reference-manifest.json` records the modified reference printer's fingerprints; it is not an allowlist of supported stock versions. The deployed Linux MCU program and the C source on disk previously diverged, as explained in the [build notes](docs/software.md#linux-mcu-源码与构建).

For a read-only environment check, run `bash tools/preflight.sh` on the printer's Linux system. It outputs JSON without installing, restarting, moving, or heating anything. Check your report for sensitive information before sharing it publicly.

## Repository guide

- [AI skill](skills/neptune4max-mods/SKILL.md): project context and working rules for agents.
- [Features and principles](docs/features.md): measurement order and the differences between dual Z alignment, bed mesh, and offset.
- [Hardware](docs/hardware.md), [software](docs/software.md), [slicer](docs/slicer.md), and [validation](docs/validation.md).
- `source/`: custom modules and required reference source files, rather than a complete Klipper or Moonraker image.
- `config/reference/`: example configurations to understand and merge for the target printer.
- `patches/`: diffs against fixed baselines and their fingerprints. Patches containing vendor differences are identified explicitly.
- [Publication copy](docs/announcement.md) and [third-party sources](THIRD_PARTY.md).

Source code and new project documentation are released under [GNU GPLv3](LICENSE). Independent third-party assets, including models, retain their own licenses; see the source notes. This project has no vendor endorsement. Contributions of sanitized environment reports, reproduction results, and adaptation patches are welcome.
