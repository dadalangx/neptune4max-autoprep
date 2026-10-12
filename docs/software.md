# 旧版环境的适配与源码构建

## 先识别目标机器

参考环境如下，用于理解接口，不是目标机器可直接覆盖的版本白名单：

| 项目 | 参考环境 |
|---|---|
| 平台 | aarch64，Debian 10 / Armbian 22.05.0-trunk |
| Klipper | `v0.10.0-530-g3387a9c2-dirty`，Python 2.7.16 |
| Moonraker | `v0.7.1-609-gbdd0222-dirty`，Python 3.7.3 |
| autotune 上游 | `andrewmcgr/klipper_tmc_autotune`，`191d1bfd69336d05de1d7f3907937e32a21b616d` 加兼容修改 |

保留目标原厂 Klipper、Moonraker、触摸屏和 Python 是本方案的路线。参考 Klipper 使用 `/home/mks/klippy-env/bin/python` 2.7.16，Moonraker 使用 `/home/mks/moonraker-env/bin/python` 3.7.3；终端里的 `python3` 版本不代表 Klipper 服务解释器。

读取实际服务启动参数、Git HEAD、dirty 文件及相关源文件。`tools/preflight.py` 只做环境盘点；HEAD、改装机文件哈希或检查程序成功都不是原装机器可直接覆盖的证明。目标版本不同时让 AI 比较接口、合并必要逻辑，并说明尚未验证的内容。

不要复制整棵机主目录、配置备份、saved_variables、床网或 PID 数据。只合并所选功能需要的 sections，并检查 include、同名宏、rename_existing、重复引脚及 SAVE_CONFIG 尾段覆盖关系。

## 原厂启动坐标不等于真实归位

本机已读取的原厂配置包含启动延迟宏`KINEMATIC_POSITION`，通过`SET_KINEMATIC_POSITION`赋予工具头默认X110/Y110/Z0坐标。它不会执行实体归位，可能使位置显示及homed标志与真实位置不符。触摸屏是否另有相关动作尚未单独确认。

保留原厂环境不意味着信任这些默认坐标。每次上电、G-code重启或Klipper服务重启后，智能体在任何后续XYZ移动前必须确认本次启动中真实三轴G28已成功完成。用户未归位时不要随意移动工具头，也不要点击网页端床网补偿校准。具体前置条件与失败处理见[归位规则](validation.md#上电与重启后的归位规则)。这里是操作要求，不要求为了发布资料去修改启动宏或触摸屏。

## 模块与目标位置

| 仓库文件 | 目标位置或用途 |
|---|---|
| `source/klipper/klippy/extras/adxl345_tap.py` | 对应 Klipper `klippy/extras/`，提供 Linux MCU Tap endstop 和测量核心 |
| `source/klipper/klippy/extras/adxl345_z_offset.py` | 同上，注册打印前 offset、检查/准备命令与 adaptive resolver |
| `source/klipper/klippy/extras/adaptive_mesh_bounds.py` | 同上，PA 校准几何解析辅助模块 |
| `source/klipper/klippy/extras/adaptive_mesh_drift.py` | 同上，中心参考时间插值修正；需合并对应adaptive cfg，不替换原生床网/probe |
| `source/klipper/klippy/extras/adxl345.py` | 参考机主机端驱动；含厂商分支差异，应比较后合并，不能默认替换其他版本 |
| `source/klipper/src/sensor_adxl345.c` | **定制 Tap 构建源码**，需要编译 Linux MCU |
| `source/klipper/linuxprocess.config` | 最小 Linux process 构建选择，不是 STM32 主板配置 |
| `source/klipper_tmc_autotune/` | 固定上游基线加 Python 2/旧 Klipper 适配的第三方插件 |
| `source/moonraker/metadata.py` | 旧 Moonraker 元数据参考文件；包含厂商预览接口和 Bambu 解析改动 |
| `source/klipper/klippy/extras/gcode_move.py` | 既有原厂坐标实现，仅供离线回归；本方案不要求替换它 |
| `source/klipper/klippy/extras/controller_fan.py` | 旧版驱动风扇参考模块；只合并空加热器名称过滤，避免覆盖其他版本实现 |
| `config/reference/` | 参考机功能配置及父配置节选；按目标机器合并和标定 |

## Linux MCU 源码与构建

2026-10-11 读取时，打印机 `/home/mks/klipper/src/sensor_adxl345.c` 是原版（SHA-256 `4a4a0e95...`），没有 Tap 命令。实际运行的 `/usr/local/bin/klipper_mcu` 是定制程序（完整哈希见 manifest），与旧项目保留的部署程序哈希一致。旧项目曾恢复磁盘 C 源码，之后再次安装了已编译程序。

因此不能从打印机当时磁盘 C 源码直接重新编译，否则会丢掉 Tap。本仓库发布的是旧项目保留的 **Tap 定制 C**，SHA-256 `2d2a55b0dc191fe99b90c5be6c88442181325596e96329b397541248d7630287`。`patches/adxl-linux-mcu.patch` 相对 Klipper `3387a9c23d940c7d449f197b272616eda11a5e3d` 生成。

本仓库不分发可直接安装的 MCU 二进制。源码和旧部署文件提供了明确的工程来源，但本次未重新编译、对照构建产物或在另一机器安装。编译器版本和构建时间可能改变产物哈希；功能命令字典和匹配接口同样要验证。

让 AI 在独立的目标兼容构建目录操作，保留原活动仓库和原 `.config`。对于上述参考基线，构建步骤是：取得匹配 Klipper 源树 → 检查并应用 Tap C 差异 → 放入 Linux process 配置 → `make olddefconfig` → `make`。该版本 Makefile 用 Python 3 运行构建脚本；这不要求把 Klippy 从 Python 2 改为 Python 3。

构建依赖应按源码和目标 Linux 工具链确认，缺依赖时只安装所需项，不整体升级系统或所有 pip 包。验证生成文件是目标 aarch64 可执行程序、命令字典含 `adxl345_tap_home` / `adxl345_tap_query_state`，且主机端 `adxl345_tap.py` 的参数签名与字典相符。单纯 `strings` 命中只能证明存在文本，不能代替协议/功能验证。

部署前保存旧 `/usr/local/bin/klipper_mcu`、实际服务定义及被改文件，记录权限和哈希。参考机服务名是 **`klipper_mcu`**，来自 `/etc/init.d/klipper_mcu` 的 SysV 生成服务，不是默认假设的 `klipper-mcu.service` 文件。按目标的实际服务关系停启、加载配套主机模块并确认 Ready；失败恢复旧程序和配套模块。Ready 检查不应自动加热或碰床。

此方案的已实现路径没有刷写主板 STM32。不要因配置头里的通用编译注释而顺带刷主板；芯片型号与厂商说明的历史文字还存在冲突，应保留当前正常主板固件。

## autotune_tmc：Python 没升级，代码做了兼容

上游固定为 `191d1bfd69336d05de1d7f3907937e32a21b616d`，适配差异见 `patches/autotune-python2-compat.patch`，完整适配版本同时位于 source。

主要改动：

- `from __future__ import division`，避免 Python 2 中整型相除截断，影响 TOFF 等计算。
- `inspect.signature` 不可用时回退 `inspect.getargspec`。
- 将 `Enum` 依赖改为有校验的字符串类别实现。
- 旧 Klipper 缺少 `TMCtstepHelper` 时使用兼容计算路径。
- 同步 TOFF 与 enable 缓存的旧接口处理，避免离线电机状态被错误启用。

这些不是通过升级 Python 解决的。参考 X/Y/挤出机启用 autotune，两个 Z 未启用；插件根据输入电机数据计算参数，**不会自行测量电阻或电感**。父配置中自定义 X/Y 电机常量也需一起读取，近似 QIDI 挤出机条目不得当成实际原厂电机规格。

不要运行上游滚动版 `install.sh` 后假设本补丁必然匹配。先固定基线并在隔离副本检查差异，再按目标解释器和接口验证。

## 驱动专用散热风扇的旧版兼容

硬件将驱动散热风扇从 FAN6/PC7 移至 FAN4/PA8 后，在主配置中加载 `config/reference/driver_cooling.cfg` 对应内容。它独立监控 `stepper_x, stepper_y, stepper_z, stepper_z1, extruder`，保持 PC7 的 `[heater_fan fan1]` 设置及 PB7/PC9 模型风扇路由。

参考旧版 `configfile.getlist()` 把空 `heater:` 解析成 `("",)`，原 controller_fan 会查找名称为空的加热器而报错。因此在 `controller_fan.py` 读取列表时过滤空名称：

```python
self.heater_names = [
    n for n in config.getlist("heater", ("extruder",)) if n]
```

这保留默认 extruder 和有效加热器列表的行为，同时允许电机专用散热。改动兼容 Python 2，不需要升级环境。补丁为 [controller-fan-empty-heater.patch](../patches/controller-fan-empty-heater.patch)，基线和哈希见 `patches/baselines.json`。目标版本若已经正确支持空列表，则无需重复修改；不同源码先比较并合并这处必要逻辑。

备份被修改的源码、主配置以及原风扇配置，在机器空闲时加载。源码已经被进程导入时，普通 G-code `RESTART` 不保证重新导入 Python 模块；按实际服务方式重启 Klipper 进程并检查 Ready，避免仍运行缓存旧实现。日后更新或覆盖源码时，也应重新核对该兼容点。

## Moonraker 元数据

补齐 BaseSlicer 的预览接口回退和 BambuStudio 识别，解析总层数、首层高度、模型高度等。补丁相对 `bdd0222a1cec451fe3bf37e721cca7409877bf61`，但它包含参考机器预先存在的厂商差异。**补丁用途是帮助比较，不能宣称所有差异都是本项目新增代码。** 在其他 Moonraker 上应按接口合并最小改动。

历史 `.thumbs` 权限问题通过修复该目录所有者处理，不意味着需要对整棵 gcode 目录递归 chmod/chown。确认实际服务用户和目录权限后处理具体目录即可。

## 自适应床网参考温漂修正

2026-10-13新增Python2兼容模块，未升级Klipper/Python/MCU。它依赖当前旧版bed_mesh/probe及实际归位事件接口，在其他版本先比较；只支持自动矩形网格、无faulty_regions。`tests/fixtures/vendor-bed-mesh-3387a9c2.py`是离线矩阵验证fixture，不是安装/替换文件。详细参数和调用见[专题文档](adaptive-mesh-drift.md)，完整备份、部署、小网格测试和回退见[智能体步骤](../skills/neptune4max-mods/references/adaptive-mesh-drift.md)。

## 配置依赖

ADXL 配置 include adaptive cfg；主配置加载 ADXL 后，再加载独立双 Z 的 PREPARE_WIPE 包装宏，避免 rename 时原命令尚不存在。若不选择 ADXL，不能把依赖它的 wrapper 一并载入；可先仅保留 Z 驱动、z_tilt、DUAL_Z_LEVEL。

冷拔依赖辅助风扇路由、respond、beeper、允许低温回抽的配置和行程。参考 `min_extrude_temp:70` 允许 90°C 回抽，但这是影响整台机器的保护设置，不能在他人机器上静默下调。原配置中超大的挤出截面积上限也不是安装本项目的必要条件，保留目标机器合理限制并针对维护动作检查即可。

父配置的自定义电机常量、Z 运动限速、探针/床网参数、触摸屏床网重定向、退出时辅助风扇关闭和仅释放 X/Y/E 等不能靠复制一个 include 完成。请对照节选、模块实现与目标现有配置生成清楚的合并差异。
