# 软件、坐标和接触约束

参考Klipper HEAD3387a9c23d940c7d449f197b272616eda11a5e3d，Python2.7.16；Moonraker HEADbdd0222a1cec451fe3bf37e721cca7409877bf61，Python3.7.3，均dirty厂商树。源码哈希是改装机参考，不是expected-before清洁原装基线。

autotune固定上游191d1bfd69336d05de1d7f3907937e32a21b616d。futuredivision防Py2整数截断，signature/getargspec回退、Enum替代、旧TstepHelper/TOFF兼容。X/Y/挤出机启用，Z两个未启用。近似QIDI数据库项不证明机主换了挤出机；读取自定义电机常量并核对真实电机。只适配需要的源码，不升级解释器来掩盖接口差异。

驱动专用controller_fan在FAN4/PA8，heater留空。参考旧getlist把空字符串解析成("",)，需在controller_fan.py读取heater_names时过滤空项；保留默认和有效加热器列表。对应source和固定基线patch见docs/software.md。目标已支持空列表则不重复打补丁；已导入模块的源码变动需重启实际Klipper进程才能可靠重新加载，不凭G-code RESTART推断代码已更新。

**Linux MCU**：参考机活动二进制为Tap版、哈希d34a7fd4...，磁盘C源为stock4a4a0e95...。仓库定制C2d2a55b0...来自旧项目保留副本；不要从参考机磁盘原C构建。独立构建目录使用兼容完整Klipper树、Tap补丁、Linux process配置，检查Tap命令字典、签名、aarch64及服务实际路径。服务参考名klipper_mcu，SysV生成；备份并配套恢复程序/模块/config，不假定systemd unit路径。

PA11原厂探针继续归零/网格/Z_TILT；probe.z_offset0是参考raw坐标体系，与手动-2基线协同，不能给目标仅改z_offset0。参考原厂启动延迟宏KINEMATIC_POSITION用SET_KINEMATIC_POSITION赋X110/Y110/Z0，可产生与真实位置不符的坐标和homed标志；触摸屏是否参与未单独确认。每次上电或重启Klipper后，任何后续XYZ移动前必须确认本次启动的真实三轴G28成功，不能靠Ready或homed_axes放行。归位路径/余量/接线/探针不满足时先协调用户处理，禁止盲归位或强制移动绕过。

ADXL工具头spidev0.0、axes_map x,z,-y，rawY检测Z Single Tap，Linux MCU C 2kHz轮询trsync停主MCU步进；存在跨MCU延迟。配方代码校验25mm/s、300mm/s²、1.75g、20msDUR、2kHz、120ms武装延迟，配置与源码同步，不任意改一项。

高位检查固定中心239.25/194.55，真实contact中心±3mm一次选点。PA11同点coarse；每次从coarse+5开始，三Tap同点中位数，极差≤0.050，最多3组，明确无触发整组丢弃安全恢复后再PA11。通信、恢复/回抬、窗口异常不盲重试。rawZ下限-3.5、接触窗口1.50～2.80、baseline-2/maxdeviation0.5都是需校准的机械条件，不能扩大限制来获得结果。

offset=median_tap_z-mesh_at_actual_contact_xy+trim，MOVE0临时应用，不加旧offset、不SAVE_CONFIG。FUZZ3让X/Y各在中心±3mm以0.01mm步距一次随机选点（方形区域），用于分散长期重复接触；不是三Tap各选一点，也不保证下次不重复。高位检查不随机，真实三Tap和各重试组使用同一个随机点，mesh必须覆盖可能接触区域，并取实际接触XY的mesh值。

床温目标±1连续300秒，进入温区后计时、越界重计时；喷嘴准备140，完成要求实测140±2。ADXL bed heat soak日志的stable=120/300s是已连续稳定120秒，不是剩余120秒；约30秒报告一次。prepare产生绑定同文件/床温/状态的单次会话，参考cfg的TTL1800；AFTER_WIPE要求SOAK0/相同BED_TEMP，失败亦消耗，不再重复300秒等待但仍查温度。双Zwrapper在prepare后tilt/rehomeZ，再恢复擦嘴-2；擦净后清该offset、测mesh、ADXL、单机微调、恢复打印温度。解释日志及热稳定目的见项目docs/features.md。

自适应mesh保留接触中心±3+0.25余量，PA11网格不随机。3～15点、小lagrange/大bicubic、无有效bbox回退6x6。ADAPTIVE_MESH_RESOLVE是adxl345_z_offset.py注册；只选mesh需拆出独立入口。PA校准只解析显式PA_LINE_CALIBRATION_START/END正挤出线段，普通模型使用Bambu变量，不凭文件名猜。

adxl345.py和metadata补丁含厂商已有差异，先比较目标接口而非盲覆盖；gcode_move.py仅测试参考。项目没有要求替换原bed_mesh/G28。旧完整Tap归零/床网原型已弃用，不从历史项目恢复它。
