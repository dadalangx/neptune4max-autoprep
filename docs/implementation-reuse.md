**简体中文** | [English](implementation-reuse.en.md)

# 从现成实现开始复刻

本项目主要功能已有参考机使用的源码和配置。复刻应从这些文件出发，保留实现逻辑，再处理目标版本接口、接线、几何和标定差异。流程文档负责说明何时做什么，不能替代对应代码。

## 按功能找到代码

[implementation-map.json](../implementation-map.json) 将功能对应到具体文件、配置节、依赖、目标位置和验证范围。智能体先选择所需功能，再读取这些文件；不必为了单个功能遍历全部源码或历史调试记录。

在**控制电脑**的仓库目录，用 Python 3 执行：

```sh
python tools/reference_bundle.py
python tools/reference_bundle.py dual-z
python tools/reference_bundle.py dual-z --config
python tools/reference_bundle.py adaptive-mesh --with-dependencies
python tools/reference_bundle.py --check
```

不带功能名时列出功能；指定功能时输出小份索引；`--config` 输出原文件中的对应配置节；`--with-dependencies` 包含所给实现的依赖入口；`--check` 检查路径、配置节和依赖关系。工具只读本地文件，不安装、不联网、不执行 G-code；其输出用于适配审查，不能直接当成目标机配置加载。提取结果不含原文件的全部头部说明，使用前仍读索引的前置条件及必要原文件。

这个查找工具是本次新增、经过离线检查的工具，与参考机实际运行的 Klipper 代码分开标记。控制电脑使用 Python 3 不要求升级打印机的 Python。

## 功能与实现入口

| 功能 / 索引 ID | 已有代码入口 | 复用时处理的差异 |
|---|---|---|
| PA11 基础 `probe-base` | [父配置节选](../config/reference/printer-sections.cfg)的 `probe`、`safe_z_home`、原 Z；[主机与运动配置](../config/reference/host-sensors-motors.cfg)的 `printer`、`bed_mesh` | 目标机的探针偏移、真实归位、行程和原有坐标基准 |
| 独立双 Z `dual-z` | [独立双 Z 配置](../config/reference/independent_dual_z.cfg)的驱动、`z_tilt`、`DUAL_Z_LEVEL`；[现有 M17/M84](../config/reference/host-sensors-motors.cfg) | 实测侧别/方向、丝杆几何；不重新编写调平宏或漏掉两个 Z 的使能/释放 |
| 主／辅助风扇 `part-cooling` | [现有 M106/M107 路由](../config/reference/bambu_aux_fan.cfg)及[父配置](../config/reference/printer-sections.cfg)的 `[fan]` | 对应引脚与风扇；直接复用路由和比例映射 |
| 驱动散热 `driver-cooling` | [FAN4 配置](../config/reference/driver_cooling.cfg)、[旧版兼容补丁](../patches/controller-fan-empty-heater.patch) | 监控电机列表必须实际存在；仅必要时合并空 heater 列表修正 |
| Tap 底层 `adxl-linux` | [Tap 主机模块](../source/klipper/klippy/extras/adxl345_tap.py)、[主机 ADXL 驱动](../source/klipper/klippy/extras/adxl345.py)、[定制 C](../source/klipper/src/sensor_adxl345.c)、[Linux 构建配置](../source/klipper/linuxprocess.config) | 在兼容完整源码树重编译 Linux MCU，核对服务和协议；无需重新发明触发算法 |
| 自动 offset `adxl-offset` | [打印前模块](../source/klipper/klippy/extras/adxl345_z_offset.py)、[对应配置](../config/reference/adxl345_z_offset.cfg)、[必要解析依赖](../source/klipper/klippy/extras/adaptive_mesh_bounds.py) | 接触窗口、同点 PA11 基准、首层标定；沿用热稳定、随机点、三 Tap 和一次性会话状态机 |
| 参考温漂修正 `mesh-drift` | [已有修正模块](../source/klipper/klippy/extras/adaptive_mesh_drift.py)及[配置](../config/reference/adaptive_bed_mesh.cfg)的 `[adaptive_mesh_drift]` | 探针中心与喷嘴坐标、旧版接口；沿用三次中位数、每五点参考和时间插值 |
| 自适应床网 `adaptive-mesh` | [现有 builder 宏](../config/reference/adaptive_bed_mesh.cfg)、[范围解析](../source/klipper/klippy/extras/adaptive_mesh_bounds.py)、ADXL 模块中的 `cmd_ADAPTIVE_MESH_RESOLVE` | 范围、点数及接触区覆盖；完整方案复用现有注册入口 |
| 完整准备 `print-preparation` | [开始代码](../slicer/start_gcode.txt)、[结束代码](../slicer/end_gcode.txt)、[3MF](../slicer/naptune4max.3mf)、双 Z 文件中的 PREPARE_WIPE 包装宏 | 以现有顺序为起点；适配擦嘴坐标、首层修正和[已知切片事项](slicer.md#原文件保留的已知适配事项) |
| 屏幕床网兼容 `mesh-profile-compat` | [现有 BED_MESH_PROFILE 包装及延迟加载](../config/reference/adxl345_z_offset.cfg) | 可选项；目标机先有自己的 `default` 网格，不能复制机主网格或提前加载不存在的 profile |
| autotune `autotune` | [完整兼容版本](../source/klipper_tmc_autotune/autotune_tmc.py)、[motor_constants](../source/klipper_tmc_autotune/motor_constants.py)、[数据库](../source/klipper_tmc_autotune/motor_database.cfg)、[兼容补丁](../patches/autotune-python2-compat.patch) | 固定版本与电机输入；不重新写 Python 2 适配，不把近似数据库条目当作实际电机规格 |
| 层数元数据 `metadata` | [已有 metadata.py](../source/moonraker/metadata.py)的 `BambuStudio`、`BaseSlicer` 及[差异补丁](../patches/moonraker-metadata-reference-vs-upstream.patch) | 最小合并到目标 Moonraker；旧界面的当前层估算仍有限制 |
| 冷拔 `cold-pull` | [现有冷拔与提示音宏](../config/reference/cold_pull.cfg)、[展开维护 G-code](../slicer/COLD_PULL_150mm_90C.gcode) | 材料、低温回抽保护与音量；无需重写维护序列 |
| 结束／取消 `print-exit` | [本次补齐的实际宏节选](../config/reference/print-exit-macros.cfg)及现有结束 G-code | 合并到目标原宏，核对 PLR 依赖、恢复限值和是否保持 Z；不要定义重复宏 |

## 本次审查发现的缺口

主要算法的实现已经公开，缺口集中在**检索、父配置中的关联代码和退出路径参考**。本次补齐功能索引、配置节提取工具，以及参考机的 `PRINT_END` / `CANCEL_PRINT` 宏。两次保存的运行配置中这两个宏完全一致；导出保留原实现，仅规范行末空白，没有修改打印机或重新执行取消动作。来源与哈希追加到 [reference-manifest.json](../reference-manifest.json)。

也有尚未提供“独立且实机验证”版本的内容，应保留边界：

- **仅床网的自动范围解析入口：** 完整方案的 `ADAPTIVE_MESH_RESOLVE` 由 ADXL 模块注册。复制现有完整依赖即可复用；独立的 `ADAPTIVE_MESH_DRIFT_CALIBRATE` 可以直接接收明确网格范围，不依赖 ADXL resolver。若要求无 ADXL 的自动 Bambu 范围解析，需要单独适配注册入口，仓库没有把新入口描述成已经验证的代码。
- **Linux MCU 构建产物：** 定制源码、补丁、配置和历史部署来源已经公开；未分发可直接安装的二进制，也未完成本次重新构建及第二台原装验证。按[构建步骤](software.md#linux-mcu-源码与构建)完成目标平台编译和协议检查。
- **另一台机器的标定数据：** 擦嘴路径、Z 侧别、接触窗口、首层修正、PID、床网等必须取得目标机自己的结果。复用算法不能省去这些测量。

`gcode_move.py` 和厂商床网测试 fixture 供离线回归，不是安装列表。原厂暂停、断料、PLR 等保留目标机实现，不需要为了复刻而重新编写或复制整份厂商配置。

## 给智能体的复用规则

先用索引得到功能依赖和现成文件，再比较目标机，只修改确有差异的接口、配置与标定值。代码已存在时，不从文字说明重新实现状态机、网格调度、风扇路由或兼容计算。确需改变实现时记录原因、改动范围及对应验证，原实现仍作为比较基准。

所选代码、适配差异、目标机测量结果和验证证据一起进入私有接手记录。按[复刻流程](../skills/neptune4max-mods/references/replication-workflow.md)分批加载和验收；源码复用不会自动证明第二台机器已完成接触或打印验证。
