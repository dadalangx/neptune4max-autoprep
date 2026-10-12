[简体中文](slicer.md) | **English**

# Bambu Studio Project and Start/End G-code

## Importing the project

`slicer/naptune4max.3mf` is a Bambu Studio project, not a printer software installer. The reference save version is `02.08.02.60`, with the Elegoo Neptune 4 Max 0.4 nozzle preset, a custom process, and Generic PETG. Choose **Open project** to load its settings, inspect them, and save your own user presets. Importing only the model does not load the printer configuration.

The project retains 3DBenchy. The public copy removes DesignerUserId from model metadata without changing the mesh, project settings, or start/end code. The original input remains unchanged; export hashes and cleanup records are in `slicer/export-report.json`.

Temperature, flow, retraction, speed, and PA values describe the reference setup, not an optimal recipe for every material. Use your own printer address, filament, and calibrated settings after importing.

## Important start-code parameters

`ADXL_Z_OFFSET_PREPARE_WIPE` receives the first-layer bed temperature from Bambu, uses SOAK=300, and creates a one-use wipe session. The dual Z wrapper aligns the gantry after preparation but before wiping and the new mesh, so the complete setup needs no extra Z_TILT call.

`ADXL bed heat soak` reports stabilization: once the bed enters target ±1°C it must remain there for 300 continuous seconds, restarting the timer if it leaves that range. The preparation nozzle temperature is 140°C. `stable=120/300s` means 120 stable seconds have elapsed. See [heat soak logging](features.en.md#bed-stabilization-and-console-messages); do not restart preparation simply because no movement is visible.

The supplied file moves first to Z10/X0, then includes `G1 Z2 F300` before purging 100 mm. Older comments still describe staying at Z10; **follow the actual commands**. After breaking the purge strand it retracts 10 mm, returns to Z10, and travels along the left side to the silicone strip at Y430. X10–30, Z-0.5, the temporary -2 offset, and two fast wiping rounds require calibration of your bracket geometry and clearance.

After clearing the temporary offset, it creates the adaptive profile. Once the new adaptive configuration and module are merged, the existing `ADAPTIVE_BED_MESH` call automatically uses center-reference drift correction; do not duplicate the command in start code. The added 180-second near-bed hold and references every five points increase preparation time and are separate from the 300-second bed soak. See [drift correction](adaptive-mesh-drift.en.md) for operation and progress; query status after long-request timeouts.

The final ADXL measurement requires the same bed temperature, SOAK=0, AFTER_WIPE=1, and FUZZ=3. It does not repeat the five-minute soak, but still checks temperatures. It selects one random point within ±3 mm on each axis; all three taps and internal retries share that point, and the next calibration selects again to distribute repeated contact. The mesh reserves coverage. See [random contact points](features.en.md#random-contact-points-and-local-wear). Final `Z_ADJUST=0.140` is the owner's measured first-layer correction; determine your own.

## Known adaptation items in the original files

Both start and end files contain `SET_SKEW CLEAR=1`. The reference printer's current command table has no SET_SKEW. For the same environment, generate a target template without this line; if the target actually uses skew_correction, handle it accordingly. Do not change an existing skew configuration just to remove a command error.

The end-code line `;PRINT_END` is a comment and **does not execute PRINT_END**. Its `M106 S0` turns off only the main fan and does not ensure PC9 auxiliary cooling stops. In a target end template with fan routing already available, use `M107` for both fans or add `M106 P2 S0`. Do not describe the original file as already doing this. The reference printer and original user files were not modified during that documentation work.

The reference end template parks, clears the mesh, turns heaters off, and uses `M84 X Y E` to retain both Z motors. Other fault, cancellation, or idle paths may release Z; not every exit preserves gantry height. Check the old ACCEL_TO_DECEL parameter of `SET_VELOCITY_LIMIT` against the target interface too.

Before parking, the end code restores reference motion limits so a final `M204` cannot leave low acceleration affecting parking or the next job. ADXL restores the acceleration that was active when probing started; it does not reread the printer.cfg baseline. Use the target printer's baseline and inspect generated files. See [acceleration between jobs](lessons-learned.en.md#acceleration-from-one-job-can-affect-the-next).

## First use

Before running full preparation, validate software Ready, real homing, positive upward motion on both sides, PA11, wiper geometry, and the ADXL contact window. Importing the 3MF does not satisfy these conditions. The agent should explain the selected actions, waits, and stopping method; successful import is not print acceptance.

Auxiliary cooling needs a nonzero auxiliary fan setting in the filament profile and emitted `M106 P2` commands to use PC9. Main fan 100% in the interface corresponds to 70% PWM; auxiliary 100% corresponds to 100% PWM.

`slicer/COLD_PULL_150mm_90C.gcode` is a maintenance file with expanded actions. Running it heats, moves, and extrudes; understand the material recipe and 90°C retraction conditions first. Do not replace its contents with a COLD_PULL macro call: once virtual SD printing begins, that macro's idle-state protection rejects it.
