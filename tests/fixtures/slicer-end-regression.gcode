;PRINT_END

SET_SKEW CLEAR=1
M400 ; 先让模型的最后一批运动完成

; 恢复printer.cfg运动基准，避免切片文件最后一次M204影响停车和下一任务。
SET_VELOCITY_LIMIT VELOCITY=500 ACCEL=2000 ACCEL_TO_DECEL=20000 SQUARE_CORNER_VELOCITY=9
M220 S100
M221 S100

G90 ; Absolute positioning
M83 ; Extruder relative mode

G92 E0
G1 E-1.5 F1800 ; Retract

; Small spiral move while raising Z by 0.5 mm; clamp the target at printable height.
G2 I1 J0 Z{min(max_layer_z+0.5, printable_height)} F3000

G90
G1 X10 Y336 Z{min(max_layer_z+50, printable_height)} E-5 F{travel_speed*60} ; Park and raise nozzle
M400 ; 停车完成后再清床网、关加热和释放电机

BED_MESH_CLEAR

M106 S0 ; Fan off
M104 S0 ; Hotend off
M140 S0 ; Bed off

; 保持双Z电机使能，避免大尺寸龙门在任务结束后立即失去保持力。
; Klipper的idle_timeout仍可能在之后统一释放电机；下次上电/重启后依然必须先G28。
M84 X Y E
