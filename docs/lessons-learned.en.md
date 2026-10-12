[简体中文](lessons-learned.md) | **English**

# Selected Debugging Lessons

These conclusions from project debugging records are useful for reproduction and troubleshooting and have been checked against repository source, configuration, and slicer files. Original notes mix dated states, abandoned prototypes, and temporary settings; they are not a deployment checklist. Raw logs, printer addresses, and backup paths are not published.

## Prefer direct Moonraker API access for agent control

For repeated control and status reads, call Moonraker directly to avoid repeatedly opening pages, waiting for rendering, and clicking controls. The web interface remains useful for people observing and interacting with the printer. The distinction is between **browser UI automation** and **programmatic API calls**, not a claim that every HTTP API behind a web proxy is slow.

Project drift tests and mesh integration checks reused an authenticated SSH connection with a `direct-tcpip` channel to printer-local `127.0.0.1:7125` Moonraker HTTP API. SSH local forwarding or an HTTP client invoked on the printer through SSH are also options. Bypassing the web proxy can help with nginx 504 on long requests, inaccessible API ports, or browser automation overhead. No latency benchmark was performed, and SSH is not promised to be faster in every case.

First inspect the target's actual Moonraker listen address, port, and authentication; 7125 is a reference value. Stable direct HTTP/WebSocket access satisfying authentication can be used without adding SSH. When forwarding is needed, reuse connections and bind only the control computer's loopback. Do not open public ports, disable authentication, or change access controls just to use the API. Keep credentials private.

OpenSSH forwarding example; keep the connection in a separate terminal, replace the address placeholder, and adapt ports to the target:

```sh
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:17125:127.0.0.1:7125 mks@<printer-address>
```

The computer then accesses `http://127.0.0.1:17125` to reach printer-side Moonraker. Start with a no-motion query such as `GET /printer/objects/query?webhooks&print_stats&toolhead&extruder&heater_bed`. Submit control through `POST /printer/gcode/script` with JSON, rather than splice arbitrary G-code into a remote shell command.

Submit long commands separately and use another HTTP connection/SSH channel for status so reads are not blocked behind them. Choose timeouts for task duration and observe backend state, logs, and progress. A timeout or disconnected SSH session does not prove an accepted action has stopped; do not automatically repeat homing, heating, extrusion, or probing. Direct API access does not reduce the intrinsic time of macros/heating/probing or replace real homing, on-site conditions, or authorization.

Check interface and completion semantics against the target version. Moonraker's official [G-code and status API](https://moonraker.readthedocs.io/en/latest/external_api/printer/) documents `/printer/gcode/script` returning on completion or error; the [API introduction](https://moonraker.readthedocs.io/en/latest/external_api/introduction/) distinguishes HTTP and JSON-RPC. The project tested the old-version path above and does not require a factory software upgrade to use it.

## Separate historical approaches from the current implementation

Earlier work tried ADXL for G28 and full-bed probing. The final division is **PA11 for homing, mesh, and dual Z; ADXL only for nozzle Z offset before printing**. Do not restore old ADXL G28 handlers, macros, or full-bed probing from historical notes.

The published print-preparation recipe is 25 mm/s, 300 mm/s², 1.75g, 20ms DUR, 2kHz polling, and 120ms arming delay. Every tap starts 5 mm above the same-point PA11 coarse height. Historical 35/400, 30/300, and 30/500 settings are earlier experiments, not current recommendations. Changing this recipe requires checking configuration, source validation, and a matching high-position no-contact check together, not changing one setting alone.

Historical labels such as deployment/state confirmation or plan validation do not establish physical contact or first-layer acceptance with that version. Calibrate the published recipe and limits on the target; see [evidence and validation order](validation.en.md).

## Lower thresholds and higher polling rates are not necessarily better

| Historical observation | Reproduction lesson |
|---|---|
| With the historical 35 mm/s, 400 mm/s² recipe, a 1.4375g threshold falsely triggered 4 of 5 high-position no-contact checks | Motor vibration can trigger the sensor. A trigger before bed contact is not successful contact, and lowering thresholds is not a universal missed-trigger fix. |
| A historical 5kHz full-bed 6×6 run completed, but 10 of 36 points needed remeasurement, with 14 rejected groups and four communication timeouts | One completed run does not prove reliability. The current choice remains 2kHz. Polling load or scheduling margin is a possible explanation, not independently established. |

These are observations on the reference printer's then-current combination, not physical limits for all printers. The current flow retains controlled no-contact checks, contact windows, group ranges, and bounded retries. Investigate communication, lift, or position recovery errors rather than lower Z limits, widen windows, or reduce thresholds to bypass them.

## All three taps need consistent starting conditions

Early second and third taps started from the prior trigger's lift position, giving different heights and travel from the first. The current path disables detection before each sample, returns at 5 mm/s to the group's `PA11 coarse_z + 5 mm`, waits for movement completion, synchronizes, confirms coordinates, and then arms descent. Internal retries use the same conditions.

This makes the three samples comparable. The old Tap core's ability to continue from the current position is not a reason to bypass the print module's consistent start point. After changes, Ready does not replace contact repeatability testing. Relevant logs are `ADXL contact start: group=... sample=... raw_z=... PA11_coarse_z=...`.

## For PA calibration timeouts, inspect bounds and the first error

One PA line file reported full-bed bounds 0–420 mm, producing a 15×15 grid with 225 positions. By mesh completion the old 900-second wipe session had expired; the first error was `Prepared nozzle-wipe session expired`. Later shutdown `Lost communication with MCU` was not the original cause.

Now only explicit `PA_LINE_CALIBRATION_START/END` sections parse actual positive-extrusion lines; ordinary models retain slicer bounding boxes. Reference expiry is 1800 seconds while same-file, same-temperature, print-state, and one-use checks remain. It is not indefinite permission. The failed historical file's local 6×5 bounds received plan validation, not post-fix physical contact acceptance.

Find the first failure chronologically, then check actual bounds, grid plan, and duration. Use no-motion planning first rather than repeatedly restart the full process; see [adaptive mesh](features.en.md#adaptive-mesh).

## Acceleration from one job can affect the next

A historical single-layer file left `M204 S500` and the end flow did not restore the baseline, so the next job entered with `toolhead.max_accel` still 500. ADXL temporarily used 300 and restored **the value active on entry**. Restoring 500 is neither leaked probing acceleration nor automatic rereading of the configured 2000.

Current repository end code explicitly restores reference motion limits before parking and waits for parking completion. For another printer, use its baseline and inspect actual 3MF settings and generated G-code. Interrupted jobs skipping normal end code also need inherited-state checks. Historical templates must not replace the owner's latest files. See [slicer adaptation](slicer.en.md).

## Check actual objects and processes on old versions

Old Klipper `heater_bed` may wrap the underlying Heater that provides temperature methods. Calling wrapper `get_temp()` once caused an internal command error. The current wait function supports a direct Heater, `.heater`, and `get_heater()` without upgrading Python or all firmware.

After Python source changes, G-code `RESTART` alone does not prove reimport. Restart the Klipper process according to actual service relationships and check process identity/start time, loading, and Ready. Loading/state confirmation still does not validate mechanical contact, and real homing is required after each restart. Check Linux MCU program, matching host modules, and configuration together; see [software adaptation](software.en.md).

The current 300-second continuous stabilization and random contact points are explained in [feature principles](features.en.md), including logs, timing conditions, and distributed contact. Historical parameter scans and complete debug records are not part of routine operation.
