[简体中文](THIRD_PARTY.md) | **English**

# Third-Party Sources and Licenses

New project documentation, configuration, and custom code are distributed under GNU GPLv3, retaining original third-party copyrights and licenses. Root LICENSE contains the full GPLv3 text. Individual resources are listed below.

| Content | Source/baseline | License and notes |
|---|---|---|
| Klipper source and derived modules | [Klipper3d/klipper](https://github.com/Klipper3d/klipper), reference HEAD `3387a9c23d940c7d449f197b272616eda11a5e3d`; host files also contain Elegoo vendor changes | GPLv3; retain file copyright comments. Custom Tap C comes from the owner's earlier project. |
| Moonraker metadata.py | [Arksine/moonraker](https://github.com/Arksine/moonraker), reference HEAD `bdd0222a1cec451fe3bf37e721cca7409877bf61` with vendor/project changes | GPLv3; original author copyright comments retained. Not all differences are original project code. |
| autotune plugin and motor database | Andrew McGregor and contributors' [klipper_tmc_autotune](https://github.com/andrewmcgr/klipper_tmc_autotune), `191d1bfd69336d05de1d7f3907937e32a21b616d` with old-environment compatibility patch | GPLv3; motor_database is upstream reference data and must match the actual motor. |
| 3DBenchy in the 3MF | Daniel Norée / Creative Tools, [3DBenchy](https://www.3dbenchy.com/) | The official [current license page](https://www.3dbenchy.com/license/) states CC0 1.0. Attribution is included; the model is not original project work. |
| Bambu Studio project settings and start/end G-code | Supplied by the owner, modified from Bambu's built-in Elegoo Neptune 4 Max preset | Only project settings and text are distributed, not Bambu software or the whole vendor preset library. Base-preset attribution is retained. |
| Board/module pin information | Owner-supplied factory mainboard wiring and ZNP K1 V2.0 pin layout, plus [official MKS hardware repository](https://github.com/makerbase-mks/MKS-StepStick-Driver) | The two diagrams are wiring references. Original author/vendor rights and licenses remain; inclusion does not make them original project work or relicense them under GPL. |
| Wiper installation and E1 UART jumper photos | Supplied and authorized for publication by the owner, in docs/images/ | Show actual assembly. Published copies remove photo metadata without changing pixels. |

New `adaptive_mesh_drift.py` is a project GPLv3 module. `tests/fixtures/vendor-bed-mesh-3387a9c2.py` is an unchanged snapshot of the reference printer's vendor Klipper mesh source for offline native-matrix tests, retaining its original copyright. It is not a file to install over target source.

Materials were organized collaboratively by the owner and Codex. Factory pause/resume, filament detection, PLR, lighting, and resonance features are not claimed as original project results. Build and interface baselines are documented in the [software guide](docs/software.en.md) and manifest.
