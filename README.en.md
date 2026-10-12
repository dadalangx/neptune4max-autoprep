[简体中文](README.md) | **English**

# Neptune 4 Max AutoPrep

Automate more of the Neptune 4 Max's print preparation and reduce repetitive leveling, wiping, and first-layer height adjustment. This project provides source code, reference configurations, and an agent guide for a setup in regular use. Give it to Codex or another AI agent to adapt the features you choose to your own printer.

The owner confirms that the reference printer works normally. The complete setup has not yet been reproduced and accepted on a second, unmodified Neptune 4 Max; each feature needs inspection and calibration.

## What it offers

| Feature | User benefit |
|---|---|
| Independent dual Z | Automatically aligns the two sides of the gantry before printing |
| Automatic nozzle Z offset | Measures the first-layer height reference after cleaning the nozzle |
| Automated print preparation | Connects bed stabilization, purging, silicone wiping, and calibration |
| Adaptive bed mesh | Probes the area needed for the current model |
| Improved fan control | Independent auxiliary cooling, automatic driver cooling, and adjustable main fan output |
| Cold-pull maintenance | Runs a defined maintenance sequence using a macro or G-code file |
| Bambu Studio support | Supplies a reference project and start/end code, with improved web interface metadata recognition |
| Factory software compatibility | Keeps the original software environment and merges changes for the actual version |

You can choose only some features. Dual Z, wiping, and fan modifications require the corresponding hardware work. The complete setup can use an **MKS TMC2209 V2.0** and a **silicone nozzle wiper for the Bambu Lab A1**. Have the agent prepare a parts and assembly list for your selected features using the [hardware guide and photos](docs/hardware.md).

## How to use it

1. Select **Code → Download ZIP** on GitHub and extract the project.
2. Open the extracted directory in an agent that can read local files and use SSH, such as Codex. Provide your printer's address and the features you want.
3. Copy the prompt below. Have the agent inspect the printer, prepare an adaptation and backup plan, then implement the work in stages.
4. Follow its instructions for assembly with power off, measurements, and on-site observations. Validate each feature before a first-layer print.

> Read skills/neptune4max-mods/SKILL.md in this project and follow its replication workflow to adapt my Neptune 4 Max. Printer address: `<your printer address>`; desired features: `<complete setup or list selected features>`. First inspect the existing environment, hardware, and configuration. Prepare the changes and backup plan, then implement each stage within my authorized scope. When assembly, measurements, or observations require my help, explain exactly what I need to do. Record completed steps and anything not yet validated.

Find the printer address on its screen or in your router. Common factory SSH credentials are username `mks` and password `makerbase`; use your own if they have changed. Downloading the project or reading the skill does not install anything or modify the printer. The user still performs the physical assembly and assists with on-site validation.

The overall process is inspection → adaptation for selected features → assembly and calibration → first-layer acceptance. The agent reads detailed procedures from the skill as needed.

**After powering on or restarting Klipper, perform real homing before moving the toolhead or calibrating the bed mesh.** Default interface coordinates and the homed indicator may disagree with the physical position. Until real Home has completed, do not issue arbitrary moves or click the web interface's bed mesh calibration button. The agent checks homing conditions using the [validation guide](docs/validation.md#上电与重启后的归位规则).

## Using the Bambu Studio preset

After adapting the printer and completing basic validation, open [naptune4max.3mf](slicer/naptune4max.3mf) in Bambu Studio as a **project**. Load its printer, process, and filament settings, then save your own user presets.

The project contains reference settings and a 3DBenchy model. Separate [start code](slicer/start_gcode.txt) and [end code](slicer/end_gcode.txt) are also provided. Have the agent adapt your preset for your hardware, wiper position, and first-layer calibration, then slice again. **Do not run the supplied start code on a stock printer before the required assembly and calibration are complete.** See the [slicer guide](docs/slicer.md).

## Further reading

- [Agent entry point](skills/neptune4max-mods/SKILL.md): replication, maintenance, and troubleshooting guidance.
- [Hardware and photos](docs/hardware.md): driver, wiring, fan, and wiper assembly references.
- [Feature principles](docs/features.md), [software adaptation](docs/software.md), [validation and rollback](docs/validation.md), and [selected lessons](docs/lessons-learned.md): details for agents and interested users.

The detailed guides and skill are currently in Chinese. Source code and new project documentation are released under [GNU GPLv3](LICENSE); third-party assets retain their own licenses, as described in the [source notes](THIRD_PARTY.md). Contributions of sanitized reproduction results and adaptation patches are welcome. Results depend on mechanical condition, materials, and calibration; software cannot replace leadscrew or mechanical bed maintenance.
