**简体中文** | [English](THIRD_PARTY.en.md)

# 第三方来源与许可

本项目新增说明、配置与定制代码按GNU GPLv3分发；保留第三方原有版权和许可。根目录LICENSE包含完整GPLv3文本。独立资源许可如下。

| 内容 | 来源/基线 | 许可与说明 |
|---|---|---|
| Klipper源码及派生模块 | [Klipper3d/klipper](https://github.com/Klipper3d/klipper)，参考HEAD `3387a9c23d940c7d449f197b272616eda11a5e3d`；主机文件同时有Elegoo厂商修改 | GPLv3，保留文件版权注释；Tap定制C来自机主此前项目 |
| Moonraker metadata.py | [Arksine/moonraker](https://github.com/Arksine/moonraker)，参考HEAD `bdd0222a1cec451fe3bf37e721cca7409877bf61` 加厂商/项目修改 | GPLv3；原作者版权注释保留。差异不全部归为本项目原创 |
| autotune插件及电机数据库 | Andrew McGregor及贡献者的 [klipper_tmc_autotune](https://github.com/andrewmcgr/klipper_tmc_autotune)，`191d1bfd69336d05de1d7f3907937e32a21b616d` 加旧环境兼容补丁 | GPLv3；motor_database是上游参考数据，实际电机需匹配 |
| 3MF内3DBenchy | Daniel Norée / Creative Tools，[3DBenchy](https://www.3dbenchy.com/) | 官方[当前许可页](https://www.3dbenchy.com/license/)为CC0 1.0；本项目注明出处，模型不是本项目原创 |
| Bambu Studio项目参数与首尾G-code | 机主提供，基于Bambu内置Elegoo Neptune 4 Max预设并修改 | 仅分发项目设置与文本，未打包Bambu软件或整套厂商预设库；基础预设出处保留 |
| 主板/模块引脚资料 | 机主提供的原厂主板接线图与ZNP K1 V2.0引脚布局图、[MKS官方硬件仓库](https://github.com/makerbase-mks/MKS-StepStick-Driver) | 两张图作为接线参考，原作者/厂商的权利与原许可保留，不因收录到本仓库而改为本项目原创或重新授权为GPL |
| 擦嘴条安装及E1 UART跳线照片 | 机主提供并授权随项目发布，位于docs/images/ | 照片说明实际装配，发布副本移除拍摄元数据，图像像素不变 |

新增 `adaptive_mesh_drift.py` 为本项目GPLv3模块。`tests/fixtures/vendor-bed-mesh-3387a9c2.py` 是参考机Klipper厂商树的未改动床网源码快照，用于离线测试原生矩阵生成，保留原版权；不得当作需要安装或覆盖目标机的文件。

项目资料由机主与Codex协作整理。现有原厂暂停、断料、PLR、灯光和共振能力不作为本项目原创成果宣传。代码构建及接口基线详见软件说明与manifest。
