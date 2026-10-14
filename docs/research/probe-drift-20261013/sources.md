# Sources and verification scope

Reviewed on 2026-10-15. Links below are references, not instructions to operate a printer.

| Source | What was verified | Limits |
|---|---|---|
| [Klipper: Probe calibration — Temperature Bias](https://www.klipper3d.org/Probe_Calibrate.html#temperature-bias) | Consistent thermal conditions, waiting, and the documented no-rehome/no-motor-release cold/hot comparison | Not a specific diagnosis of this Neptune sensor and not endorsement of center-reference interpolation |
| [Klipper: probe configuration](https://www.klipper3d.org/Config_Reference.html#probe) | Sample aggregation, within-group tolerance, and retry semantics | Current documentation; legacy semantics were also checked in the saved experiment-time source |
| [Klipper: adaptive meshes](https://www.klipper3d.org/Bed_Mesh.html#adaptive-meshes) | Object-area bounds, margins and probe-count scaling | Not a measured A/B comparison or a claim about all third-party macros |
| [OrcaSlicer: Adaptive Bed Mesh](https://github.com/OrcaSlicer/OrcaSlicer/wiki/printer_basic_information_adaptive_bed_mesh) | Direct parameterized bed-calibration example; bounds, count, interpolation settings | No claim of having inspected every Orca release or a specific user's start macro |
| [AutoPrep correction source, fixed commit](https://github.com/dadalangx/neptune4max-autoprep/blob/468c40c689b60bea7c9cf67f59210503890fcade/source/klipper/klippy/extras/adaptive_mesh_drift.py) | `correct_block`, separate references, native matrix finalization; no `SET_GCODE_OFFSET` in the drift module | Implementation evidence, not proof of physical accuracy |
| [Neptune4.help page supplied in the comment](http://neptune4.help:8000/doku.php?id=tune_probe_configurations) | Retrieval attempted using the supplied URL and HTTPS variant; site contents were unavailable | Specific recommended numbers and the full guide were not verified; no criticism of unseen content is claimed |

The 12 local CSV files are direct copies of the owner's 2026-10-13 experiment records. Original record identifiers and SHA256 hashes are in [source-manifest.json](source-manifest.json). The first five runs have completed flags and equal before/after configuration-file hashes in the retained local audit records. Private status snapshots, printer address, credentials and raw command logs are excluded from this proposed public package.

The real-XY integration audit was previously published in [the project validation record](https://github.com/dadalangx/neptune4max-autoprep/blob/468c40c689b60bea7c9cf67f59210503890fcade/docs/validation/adaptive-mesh-drift-20261013.en.md). The new offline script verifies its copied point/reference CSV arithmetic; it does not pretend to rerun the physical experiment or independently remeasure the bed.
