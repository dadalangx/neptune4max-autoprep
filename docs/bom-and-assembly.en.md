[简体中文](bom-and-assembly.md) | **English**

# Parts List and Hardware Modifications

## What parts and tools do you need?

This setup primarily reuses the Neptune 4 Max's factory hardware. It does not require replacing the original motors, leadscrews, extruder, hotend, or bed. Prepare parts for the features you choose: independent dual Z needs an additional driver and separate motor wiring, automatic wiping needs a silicone wiper and mounting materials, and both fan modifications reuse the printer's existing fans.

The quantities below reflect the reference printer's assembly method. Before buying parts, photograph the board, connectors, and wiring, and check the production revision, existing modifications, and available cable lengths.

### 1. Parts for independent dual Z and automatic wiping

| Part | Reference quantity | Purpose and selection notes |
|---|---|---|
| MKS TMC2209 V2.0 stepper driver module | 1 | Adds an independent Z driver in E1. Both sense resistors on the reference module are marked R110, corresponding to `sense_resistor: 0.110`. Check the actual model, revision, and resistor markings. |
| UART jumper cap | 1 | Must fit the E1 jumper header, usually 2.54 mm pitch. Reuse one supplied with the driver or an existing spare if available. |
| 4-pin connector housing matching the board's Z/E1 sockets | Usually 1 additional housing | One is needed if you keep one original connector and remake only the other branch; two are needed if you remake both. Often sold as “XH2.54”; check pitch, shape, and latch before buying. |
| Crimp contacts matching the housing and wire gauge | 4 per new 4-pin connector | At least four for one remade branch or eight for two. Buy a few spares and select contacts suitable for the actual wire. |
| Driver heatsink and suitable mounting materials | 1 set | No separate purchase is needed if included with the module. Secure it, keep it clear of pins and other conductors, and preserve airflow. |
| Silicone nozzle wiper compatible with the Bambu Lab A1 | 1 | Mounts on the plastic bracket at the end of the bed cable connection for automatic wiping. |
| Wiper mounting materials | As needed | Choose a secure, heat-resistant attachment for the actual bracket. Project photos show the location; they do not establish that simple adhesive mounting works on every production revision. |

**Connector specification:** the official JST XH series has a nominal pitch of **2.50 mm**. The marketplace name “XH2.54” may be imprecise. Match the original socket rather than assuming all 2.54 mm four-pin connectors are interchangeable. The housing pitch and UART jumper pitch are separate specifications. [Official JST XH information](https://www.jst-mfg.com/product/index.php?lang=2&series=277)

### 2. Reused factory fans and optional wiring materials

| Part or material | Reference quantity | When it is needed |
|---|---|---|
| Auxiliary part-cooling fan | No purchase needed | Reuse the Neptune 4 Max's factory auxiliary fan and reconnect it to FAN3 (PC9). |
| Stepper driver cooling fan | No purchase needed | Move the existing driver cooling fan from FAN6 to FAN4. |
| Wire, extension cables, matching housings, and contacts | As needed | Use when cable length or connectors no longer fit after separating motor wiring or relocating fan connections. Check motor and fan wiring specifications separately. |
| Heat-shrink tubing or insulating sleeves | As needed | Insulate any actual wire joints; do not add unnecessary joints. |
| Cable ties or clips | Several | Secure wiring while allowing movement, avoiding connector strain, abrasion, or contact with moving parts. |

The main part-cooling, auxiliary part-cooling, hotend heatsink, and driver cooling fans all reuse factory hardware. Fan rewiring only needs extension cables, housings, or contacts if the original cables or connectors do not fit.

### 3. Tools

| Tool | Purpose and selection notes |
|---|---|
| Hex keys | Remove covers and timing pulleys; the supplied printer tools may be sufficient. |
| Diagonal cutters | Cut and trim wires that need modification. Confirm the wiring plan before cutting. |
| Wire stripping tool | Remove insulation while preserving the copper strands; use a stripper suitable for the wire gauge. |
| Small open-barrel terminal crimper | The die must match the contact and wire gauge, crimping the conductor and insulation wings separately. A model name such as SN-2549 alone does not guarantee compatibility with the purchased contacts. |
| Digital multimeter, strongly recommended | With power off and the motors and wiring disconnected from the board, check coil pairs, continuity, and crimp results. |
| Ruler or caliper | Measure wiper position and height, leadscrew positions, and connector dimensions. |

If you do not want to crimp wires, use correctly wired independent motor cables with matching connectors. Premade cables still need checks for pin order, length, and reliable contact.

## What hardware modifications are required?

### 1. Independent dual Z

The factory arrangement uses one driver for both Z motors and a timing belt linking the two leadscrews at the top. After modification, the original Z driver and the added E1 driver independently control the motors, allowing automatic gantry alignment.

1. Photograph and label both motors and their wiring before disconnecting anything. Switch the printer off and unplug its power cable before disassembly.
2. Remove the top Z synchronization belt and both **timing pulleys**, retaining the remaining leadscrew supports and transmission parts. The toothed parts that rotate with the leadscrews are timing pulleys.
3. Separate the parallel motor wiring so that each Z motor has its own four wires and driver channel. Motor phase wires must no longer connect the outputs of the two drivers together.
4. Identify each motor's two coil pairs and connector pin order before crimping and inserting contacts. Keep a record of the original connector wiring and consult the board and driver documentation. Do not infer pairing from wire colors or assume pins 1 and 2 always form a pair.
5. Install an **MKS TMC2209 V2.0** and heatsink in E1. Use the module and board pin labels to verify orientation and full insertion. For this reference combination, **bridge only UART; leave M0, M1, and M2 open**.
6. Connect one Z motor to the original Z socket and the other to E1. Gently tug each wire to check contact retention, and check connector seating, insulation, and cable slack.
7. After assembly checks, adapt and validate Klipper: check UART communication and safe homing conditions first, complete real homing, then ask the person at the printer to observe controlled small movements to confirm motor sides and positive upward motion. Configure and validate automatic Z tilt adjustment afterward.

Viewed from the front, the reference printer's **original Z driver controls the left motor and E1 controls the right motor**. Verify every target printer physically. The agent must record the observations before assigning drivers and leadscrew positions for automatic leveling.

No additional Z motors or leadscrews are needed. With the belt removed, the sides can move independently; maintain the gantry's alignment during assembly and avoid a large height difference.

See the [hardware guide](hardware.en.md) for the jumper photo and board pin information. The photo omits the driver to expose the jumpers; the driver must be installed for operation.

### 2. Automatic nozzle wiping

1. Fit a silicone wiper compatible with the Bambu Lab A1 to the **plastic bracket at the rear of the bed, at the end of the bed cable connection**, following the project photo for location.
2. Check secure mounting and stability when heated. Ensure the wiper and toolhead do not pinch wiring, and check clearance throughout toolhead and bed travel.
3. Measure your own contact position, height, and available travel, then have the agent generate a path. After safe homing and checking the path above the wiper, validate contact wiping gradually.

This does not require redesigning the whole toolhead. Wiping coordinates, contact height, and temporary Z offset are calibrated for the reference printer and must be measured again on another machine.

See the [wiper installation photo](images/a1-wiper-installation.jpg).

### 3. Auxiliary part-cooling fan

1. Reuse the Neptune 4 Max's factory auxiliary fan. Check cable length and connector compatibility after relocation; no additional auxiliary fan is needed.
2. With power off, connect it to independent **FAN3 (PC9)** and check the connector, voltage, and polarity. Keep the main part-cooling fan on **FAN2 (PB7)**.
3. Configure the independent channel and Bambu Studio command mapping. Test on, off, and speed control for both fans separately, confirming that one does not operate the other.

This lets Bambu Studio's auxiliary part-cooling setting control the fan independently. The fans must physically use different outputs for software routing to provide independent speed control.

### 4. Dedicated stepper driver cooling fan

1. With power off, move the existing driver fan from **FAN6** to **FAN4 (PA8)**. Retain the hotend heatsink fan and its existing control.
2. Factory FAN1 and FAN6 share **PC7**. Moving the driver fan to FAN4 gives it independent control instead of starting only with hotend temperature.
3. Use Klipper `controller_fan` to monitor X, Y, both Z motors, and the extruder. Run the fan while any monitored motor is enabled, then stop after a delay once all are released. The reference delay is 60 seconds.
4. Check actual fan rotation and delayed stopping, and verify that hotend cooling still works.

**Enabled includes stationary holding.** A driver fan that keeps running while the gantry is stationary but its Z motors remain energized is behaving as intended.

### 5. ADXL automatic Z offset and mesh drift correction

These features primarily require the matching software and calibration; the reference setup adds no sensors for them:

- Automatic Z offset reuses the factory toolhead's **ADXL345** to detect the cleaned nozzle touching the build plate.
- Mesh measurement and drift correction use the factory proximity probe and additional reference measurements to estimate drift, without another temperature sensor.

Check that the target printer has the required sensors, working connections, and compatible software. ADXL contact measurement needs the project's matching code and calibrated triggering conditions and controlled probing limits. Completing hardware assembly alone does not make the supplied start code ready to run.

## Basic checks after assembly

Change drivers, motor wiring, jumpers, and fan connections only with power completely off. Never plug or unplug a motor or driver while powered.

Before powering on, check driver orientation, contact pin order and retention, insulation, heatsink attachment, and airflow. Check that the wiper and wiring remain clear throughout toolhead and bed travel. Keep original wiring photos and software backups, then validate each feature using the project workflow.

**After each power-on or Klipper restart, complete real Home under confirmed safe homing conditions before subsequent XYZ movement or mesh calibration.** Default coordinates and a homed indicator do not replace physical homing. If new driver direction, probe operation, or clearance remains uncertain, resolve it before attempting homing. Until real homing is complete, do not issue arbitrary moves or click web interface mesh calibration.

The complete setup needs separate validation of communication, motor sides and direction, fans, wiper position, sensors, and the first layer. Production revisions and existing modifications may differ; adapt parts, wiring, and configuration to the actual printer.
