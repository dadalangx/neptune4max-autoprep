[简体中文](adaptive-mesh-drift-20261013.md) | **English**

# Printer Integration Validation Record

Completed: 2026-10-13 05:48:29 UTC+8. Result: passed.

This run validates the connection between actual XY scanning, center-reference interpolation, and the resulting mesh matrix. It does not measure complete print quality or establish that all thermal errors are eliminated.

## Physical test sequence

- Bed 60°C, nozzle 140°C; main and auxiliary part-cooling fans off.
- After deployment restart, existing DUAL_Z_LEVEL completed real XYZ homing and dual Z alignment.
- Original ADAPTIVE_BED_MESH interface used model bounds X180–220/Y180–220 with MARGIN=10; the existing resolver retained ADXL contact coverage.
- Generated 4×4, or 16, actual grid positions. Center reference was bed coordinate (215,215), corresponding to nozzle (239.25,194.55) on this printer.
- Actual near-bed hold was 180.333 seconds, followed by an independent three-sample median baseline.
- Additional three-sample median references followed points 5, 10, 15, and 16. The final one-point group was also bracketed by references.
- Mesh and reference measurements took approximately 72.495 seconds, excluding homing, heating, and the 180-second hold.

## Center-reference measurements

| Completed grid points | Time from baseline / s | Reference median / mm | Change from initial reference / mm |
|---|---|---|---|
| 0 | 0.000 | 0.135000 | +0.000000 |
| 5 | 21.885 | 0.142500 | +0.007500 |
| 10 | 43.506 | 0.147500 | +0.012500 |
| 15 | 65.049 | 0.152500 | +0.017500 |
| 16 | 72.495 | 0.150000 | +0.015000 |

Maximum applied correction: 0.016660 mm. Only the time-interpolated reference change is removed; grid XY and actual spatial height differences remain.

## Automated checks

- Independently recalculated piecewise linear interpolation at every point matched module corrections within 1e-9 mm.
- All 16 actual bed_mesh.probed_matrix values matched corrected points mapped through the original serpentine order, within 1e-6 mm to allow native status rounding.
- A separate test profile was generated, then default restored; SAVE_CONFIG was not executed.
- Ten offline tests passed locally and in actual Python 2.7.16, covering 90 points/18 references, factory matrix construction, Python 2 floating-point division, the final partial group, real homing, and failure cleanup.
- Original backups and SHA256 of the two installed files were verified. Ten snapshotted files, including native bed_mesh.py, probe.py, and the ADXL module, remained unchanged. Of 184 root cfg files, only adaptive_bed_mesh.cfg changed.

## End state

Toolhead stopped at actual Z10. Bed and nozzle heater targets were 0, main and auxiliary fans were off, and the pre-test offset and default mesh were restored. The new module remained loaded; ADAPTIVE_BED_MESH in the original Bambu Studio start code automatically uses it.

Raw points and references are in the [grid data](adaptive-mesh-drift-20261013-mesh-points.csv) and [reference data](adaptive-mesh-drift-20261013-center-references.csv). Device and deployment *.private.json records are for local auditing only and excluded from publication.

## Fixed-XY experiment before method selection

On the same printer at bed 60°C/nozzle 140°C, first cool the probe away from the bed (Z100, auxiliary fan for 60 seconds, then fan off for 300 seconds), then hold near the bed for about 180 seconds. Collect 90 independent simulated mesh samples at the center with an independent three-sample median reference every five points, for 18 references. Actual XY stays fixed and lateral travel is simulated with dwell times; this is not a spatial bed mesh. The experiment compares before/after correction on the same raw samples.

| Metric / mm | Raw | Time-interpolated correction |
|---|---:|---:|
| Maximum absolute baseline deviation | 0.122500 | 0.015427 |
| Overall range | 0.117500 | 0.022866 |
| RMSE relative to baseline | 0.082267 | 0.003133 |

No maximum-deviation samples were removed, and mesh samples were not reused as references. This experiment alone cannot establish effects of actual XY travel, local temperatures, or how representative one reference is. The 4×4 physical scan above validates integration and the actual matrix; repeatability, different model bounds/bed temperatures, and first-layer printing still need checks on the target printer.
