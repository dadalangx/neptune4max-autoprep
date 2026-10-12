; Neptune 4 Max - cold pull maintenance
; Created 2026-10-10. Start this file only when ready for the maintenance cycle.
; Home XYZ; raise to Z200; heat nozzle to 250C.
; Purge 150mm at 3mm/s; cool with auxiliary fan to 110C.
; Fan off; cool to 90C; retract 30mm at 1mm/s.
; Disable extruder motor; keep nozzle target at 90C; beep twice.
; Beeper: owner-selected 50% PWM, 1000Hz, two 100ms tones.
; Complete G-Code sequence; no COLD_PULL macro call required.

M400
SAVE_GCODE_STATE NAME=COLD_PULL_STATE
M220 S100
M221 S100
G90
SET_GCODE_OFFSET Z=0 MOVE=0
BED_MESH_CLEAR
M106 P2 S0
RESPOND TYPE=echo MSG="Cold pull: homing and raising to Z200."
G28
G1 Z200 F600
M400
RESPOND TYPE=echo MSG="Cold pull: heating to 250C and purging 150mm at 3mm/s."
M109 S250
M83
G1 E150 F180
M400
; Flush extrusion before enabling the auxiliary fan and lowering the target.
M106 P2 S255
M104 S110
RESPOND TYPE=echo MSG="Cold pull: auxiliary fan on. Cooling to 110C."
TEMPERATURE_WAIT SENSOR=extruder MAXIMUM=110
M106 P2 S0
; A new target is required here; leaving it at 110 would prevent cooling.
M104 S90
RESPOND TYPE=echo MSG="Cold pull: auxiliary fan off. Cooling to 90C."
TEMPERATURE_WAIT SENSOR=extruder MAXIMUM=90
G1 E-30 F60
M400
SET_STEPPER_ENABLE STEPPER=extruder ENABLE=0
M104 S90
RESTORE_GCODE_STATE NAME=COLD_PULL_STATE MOVE=0
; The owner selected 50% after listening to 1%, 2%, 20% and 50%.
; Keep each beep short (100ms), with a 150ms gap.
; PWM duty is not a calibrated acoustic volume percentage.
SET_PIN PIN=beeper VALUE=0.5 CYCLE_TIME=0.001
G4 P100
SET_PIN PIN=beeper VALUE=0 CYCLE_TIME=0.001
G4 P150
SET_PIN PIN=beeper VALUE=0.5 CYCLE_TIME=0.001
G4 P100
SET_PIN PIN=beeper VALUE=0 CYCLE_TIME=0.001
M400
RESPOND TYPE=echo MSG="Cold pull complete. Nozzle target held at 90C and extruder motor off."
