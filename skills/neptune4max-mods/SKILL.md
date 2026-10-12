---
name: neptune4max-mods
description: Adapt or troubleshoot the Neptune 4 Max ZNP K1 V2.0 modification project, including independent Z, ADXL nozzle offset, wiping, adaptive mesh, Bambu fans and old Python compatibility. Use for this project’s replication or maintenance.
---

# Neptune 4 Max 改装接手

把本项目作为已使用改装机的工程参考，按用户所选功能适配目标机器。它不是经过原装全系列验收的一键安装包。准备发布材料不意味着授权修改机主正常运行的打印机；只读请求保持只读。

## 开始时确认什么

读取用户提供的仓库 README、目标地址与任务范围。地址由用户自行确定，仓库不包含参考机IP；常见原厂SSH为mks/makerbase，用户修改后的凭据按其提供处理。如果skill被单独安装，先取得项目源码目录，再使用其中的source/config/patches，而不是以为skill含有全部程序。

先读取实际服务解释器、原厂版本、dirty源码、主板/模块型号、include与宏冲突。参考环境Klipper Python2.7.16、Moonraker Python3.7.3。保留目标原厂软件，默认不升级系统、Klipper、Moonraker或Python，不用改装机哈希充当原装白名单。`tools/preflight.sh`是可选只读盘点工具，不是安装器。

## 按任务读取资料

- 双Z、驱动、风扇或擦嘴：读[硬件和几何](references/hardware-and-geometry.md)，再读项目docs/hardware.md与相关cfg。
- ADXL、床网、老Python或源补丁：读[软件和ADXL](references/software-and-adxl.md)，再读docs/software.md、docs/features.md及对应实现。
- 上线、排错、切片或回退：读[验证与切片](references/validation-and-slicer.md)，再读docs/validation.md与docs/slicer.md。

只加载本次有关资料。按现有授权实施必要改动，不把其他模块或全机调参自动并入任务。

## 决策中保留的关键事实

1. MKS TMC2209 V2.0、R110 → sense_resistor0.110，E1 PB6 UART、地址0，UART跳线单独闭合。参考电流0.6A、threshold0。侧别/方向由实际观察决定；原Z不是E0挤出机通道。
2. `z_positions`顺序对应stepper_z、stepper_z1。历史侧别记录与近期文字/注释冲突，不从其中任选一个当作当前事实。
3. PA11继续负责G28、床网和Z_TILT；ADXL仅做打印前offset。普通G28不自动校正双Z。wrapper在热稳定准备后、擦嘴/网格前校正。
4. Tap需要定制Linux MCU C和配套Python。参考机磁盘C是原版，但运行程序是Tap版；仓库source里的定制C来自原项目，不能用参考机磁盘原C重编译代替。
5. adaptive cfg的ADAPTIVE_MESH_RESOLVE由ADXL模块注册；仅选床网时需要独立适配注册入口。源码patch可能带厂商原有差异，比较后合并，不覆盖未知分支。
6. +0.140首层修正、擦嘴坐标、-2临时基线、PA11偏移、接触窗口、PID/PA/共振频率属于单机数据。

## 落地与结束

先在隔离本地目录准备逐文件差异及备份/回退清单，保留用户已有配置与保护。安装所选源码时按实际解释器和MCU协议验证；不复制整份printer.cfg、saved_variables或床网，不为实现冷拔而静默降低低温挤出保护。

运动、归零、风扇、加热、挤出和接触测试应符合用户授权，并在机器旁的用户已确认相关空间/硬件条件时执行。授权和条件已经明确则继续，不重复询问；条件缺失时先完成不依赖它的准备和只读检查。

长请求超时先查后端状态，不能盲目重发实体动作。通信、恢复位置、回抬或接触窗口异常时停止接触，不通过降低阈值、扩大窗口或更低Z下限伪造成功。

交付时说明具体修改、测试证据、备份位置及未完成的机械/首层验证。区分离线模拟、Ready/UART检查和真实打印成绩；未做第二台原装验证不能写“全系列兼容”。发布时仅导出所需文件，检查普通文本、3MF压缩成员与Git历史，排除实际IP、密钥、私有日志和备份。
