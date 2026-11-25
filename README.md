# Seymour demo cell

A SCARA picks parts from an Asyril Eye+ feeder and presents each one at a station. There a Meca500 carrying an LMI line sensor measures it. A second Meca500 inserts the part, corrected by the measured offsets, and a second scan checks the insertion. One PROD cycle handles one part.

This folder is a workspace of the Mecademic demo app (`../mecademic_demo_app`). The app provides the web UI, the device drivers and the task runner. This folder provides the cell's devices (`config.yaml`), its sequences (`*.py`), its tunable values (`context.yaml`) and an operator page (`custom_view/`).

## Run it

On the demo box: `docker compose up -d` in `~/demo_ws` starts the app on this workspace (http://localhost:8080, or through nginx on port 80). After editing a file here, use **Settings > Workspace > RELOAD CODE**. You don't need to restart the container.

Without Docker:

```bash
python ../mecademic_demo_app/app.py --workspace .
```

Press **INITIALIZE**, which connects, activates and homes every robot and puts the Asyril in production. Then press **HOME**, then **START** on the Production tab. **STOP** ends after the current cycle and homes. **ABORT** stops at once.

The **Custom view** link in the sidebar (`/view/`) opens a simple operator page: cell buttons, production counters, the last scans and the manual actions.

## Devices

| Name in code | Type | Address | Role |
|---|---|---|---|
| `scara` | Mecademic (`mecademic`) | 192.168.0.30 | Picks from the Asyril with vacuum and presents the part |
| `meca_lmi` | Mecademic (`mecademic`) | 192.168.0.20 | Carries the LMI sensor through the scan |
| `meca_insert` | Mecademic (`mecademic`) | 192.168.0.21 | Inserts the part, corrected by the scan |
| `lmi_sensor` | LMI Gocator (`lmi`) | 192.168.0.10, ports 8190 | Measures x / z of the part |
| `asyril` | Asyril Eye+ (`asyril`) | 192.168.0.50, recipe 13843 | Presents parts and returns their pose. Calibration recipe: 13186 |

## Robot programs

All motion lives in programs saved on the controllers. They must exist there before PROD runs. `robot_programs.py` lists them. The descriptions below come from how the code uses each program, so confirm them on the controllers.

| Robot | Program | What it does | Robot variables it reads | Called from |
|---|---|---|---|---|
| `scara` | `11` | Home / safe pose | – | HOME, Retract, *Release SCARA part* |
| `scara` | `12` | Pick from the feeder | `PickPose.x`, `PickPose.y`, `PickPose.rz` | Pick, *Asyril pick* |
| `scara` | `13` | Present the part at the station | – | Present part |
| `scara` | `14` | Release the held part | – | HOME (part held), Retract, *Release SCARA part* |
| `scara` | `stand_pick` / `calib_place` / `calib_pick` / `stand_place` | Calibration target handling | `CalibPoses.x`, `CalibPoses.y` | CALIBRATION |
| `meca_lmi` | `21` | Home pose | – | HOME |
| `meca_lmi` | `22` | Parked, ready to scan | – | HOME, Present part (first cycle), Retract |
| `meca_lmi` | `23` | Approach the scan start | – | Present part |
| `meca_lmi` | `24` | Scan pass. Sets checkpoint **222** where the sensor must trigger | – | Scan part, Verify insertion, *Scan* |
| `meca_insert` | `31` | Standby | – | HOME, Retract |
| `meca_insert` | `32` | Ready above the station | – | Present part |
| `meca_insert` | `insertion` | Insert | `x_offset`, `z_offset` (mm) | Insert part |
| `meca_insert` | `retract_from_inspect` | Retract from the station | – | Retract |

**How Python waits for a program.** The new framework's standard waits for a `SetCheckpoint(<n>)` on the program's last line. A `WaitIdle()` right after `StartProgram` can in principle return too early in the app's asynchronous mode. These programs don't end with a checkpoint yet, so they are still waited for with `WaitIdle()`, as before. To switch a program over, add `SetCheckpoint(<n>)` as its last line on the controller and put `<n>` in its `Program(...)` entry in `robot_programs.py`. No other file changes. Use numbers 1-9 for home/calibration programs and 11+ for production, unique per robot.

## Sequences

| Task | Steps |
|---|---|
| PROD cycle | Pick part from feeder → Present part → Scan part → Insert part → Verify insertion → Retract |
| HOME | Park LMI robot → Home SCARA (releases a held part) → Home insertion robot → Home LMI robot |
| CALIBRATION | Start feeder calibration → Take calibration target → Capture calibration images (4 poses) → Return calibration target → Compute calibration → Restart feeder production |
| SHIPMENT | Not defined for this cell yet (logs and does nothing) |

In a cycle:
- **Pick part from feeder** is skipped when the SCARA still holds a part. Otherwise it repeats pick → (shake feeder) until the vacuum holds a part. After `max_pick_attempts` it faults the cell with a message to check the feeder.
- **Insert part** and **Verify insertion** only run when one of the `scan_retries` scans gave a valid x and z. Otherwise the part is not inserted (`scan_fail_count` + 1) and the cycle goes on to Retract.
- In **Retract**, `meca_insert` heads to standby while the next cycle already picks.

## Manual actions (Manual tab and custom view)

| Button | What it does |
|---|---|
| Scan (inspection only) | One scan pass with `meca_lmi` + LMI. The result goes to the log and the custom view |
| Asyril pick | The SCARA picks one part from the feeder and keeps it. Faults if the feeder has none |
| Release SCARA part | The SCARA releases its part, then goes home |
| Shake feeder | Vibrates the Asyril and prepares a new part. No robot moves |

They call the same functions as the PROD cycle (`prod.py`) and don't change the PROD counters.

## Params and variables (Variables tab)

| Name | Kind | Default | Meaning |
|---|---|---|---|
| `program_timeout_s` | param | 120 | Longest one robot program may take before the task faults (s) |
| `scara_vacuum_threshold_kpa` | param | 60 | Vacuum (absolute, kPa) above which the SCARA holds a part |
| `max_pick_attempts` | param | 10 | Pick attempts before the cycle faults |
| `feeder_retries` | param | 5 | Part requests per pick attempt (near-vertical parts are skipped) |
| `scan_retries` | param | 3 | Scans per cycle until x and z are valid |
| `scan_settle_s` | param | 0.5 | Pause after a scan pass before reading the result (s) |
| `cycle_wait_s` | param | 0 | Idle pause between cycles (s) |
| `part_count` | variable | 0 | Parts inserted |
| `pick_try_count`, `pick_success_count` | variable | 0 | Pick attempts / successful picks |
| `scan_try_count`, `scan_success_count` | variable | 0 | Scans / valid scans |
| `scan_fail_count` | variable | 0 | Cycles without a valid scan |
| `last_scan_x_mm`, `last_scan_z_mm` | variable | 0 | Last valid measurement (mm). The insertion uses its negative |
| `lmi_robot_in_position` | variable | false | `meca_lmi` already parked for the next scan (reset at PROD start) |

The counters (`part_count` to `scan_fail_count`) reset at each PROD start and are kept across app restarts (`context.state.json`).

## Files

| File | Contents |
|---|---|
| `config.yaml` | Devices, manual actions, declared step sequences |
| `context.yaml` | Params and variables |
| `prod.py` | `prod_cycle()`, plus the building blocks shared with the manual actions |
| `home.py`, `calib.py`, `shipment.py` | HOME, CALIBRATION and SHIPMENT tasks |
| `manual_actions.py` | Manual tab buttons |
| `robot_programs.py` | Every robot program the workspace starts, and how each is waited for |
| `cell_tools.py` | Framework helpers: checkpoints, parallel branches, simulation stand-ins (copied unchanged from the new-workspace skill) |
| `custom_view/` | The operator page at `/view/` |
| `backups/` | Robot backups made from Settings > Backup / Restore |

## Before the next run on hardware

- [ ] Confirm the program descriptions in the table above. They come from how the code uses each program.
- [ ] Check that `program_timeout_s` (120 s) covers the longest program, the calibration ones included. Before the migration there was no timeout.
- [ ] Check `max_pick_attempts` (10). The old code retried picks forever.
- [ ] When convenient, end each program with `SetCheckpoint(<n>)` and fill in `robot_programs.py` (see "How Python waits for a program").

## Tested

- 2026-11-25, simulated: `check_workspace.py` (new-workspace skill) reported 0 errors and 0 warnings. INITIALIZE, HOME, CALIBRATION, SHIPMENT, the 4 manual actions and 4 PROD cycles + STOP ran on simulated devices. The custom view was loaded against the running app.
- 2026-11-25, branch tests with scripted fake devices: pick after a feeder shake, part already held, max pick attempts, near-vertical parts, invalid scans, `meca_lmi` parked on the first cycle only. The robot program order per robot matches the pre-migration code.
- Hardware: not yet.
