# Mecademic Demo Seymour Tasks

This repository contains task scripts and runtime configuration for a Mecademic demo cell.

The scripts are designed to run with a host application that provides:
- `core.ApplicationController`
- device drivers in `devices`

The standalone runners in each task file automatically add `../mecademic_demo_app` to `sys.path`.

## What Is In This Repo

- `config.yaml`: device declarations and production context file path
- `production_context.yaml`: typed runtime params and variables
- `home.py`: home/parking sequence for the robots
- `calib.py`: Asyril + SCARA calibration sequence
- `prod.py`: production cycle (pick, scan, insert, retract)
- `shipment.py`: shipment hook (currently a no-op placeholder)
- `__init__.py`: task exports

## Exposed Tasks

- `home`
- `calib`
- `prod_cycle`
- `shipment`

## Device IDs Expected In config.yaml

The task scripts expect these keys in `devices`:

- `scara`
- `meca_lmi`
- `meca_insert`
- `asyril`
- `lmi_sensor`

Update IP addresses and recipe values in `config.yaml` for your lab environment.

## Task Behavior

### home(devices)

- Runs a safe startup/parking sequence for `meca_lmi`, `scara`, and `meca_insert`
- Waits for each critical motion phase to complete before continuing

### calib(devices)

- Starts Asyril calibration mode
- Moves SCARA through four calibration poses and captures images
- Executes `asyril.api.calibrate()` and then resumes production mode

### prod_cycle(devices, context=None)

- Uses SCARA vacuum pressure to confirm if a part is already held
- Triggers Asyril part detection and updates SCARA `PickPose` variables
- Executes LMI scan with retry logic (`SCAN_RETRY_NUMBER = 3`)
- Applies insertion offsets on `meca_insert` from scan data
- Runs insertion, verification scan, and retract sequence

### shipment(devices)

- Placeholder hook
- Intentionally a no-op in this repository

## Run Standalone

Each task module has a `__main__` block that:

1. Builds `ApplicationController` from local YAML files
2. Calls `initialize()`
3. Runs the selected task
4. Always calls `shutdown()` in `finally`

Examples:

```bash
python home.py
python calib.py
python prod.py
python shipment.py
```

## Prerequisites

1. `../mecademic_demo_app` exists (or `core`/`devices` are available via `PYTHONPATH`)
2. Device controllers are reachable at the IPs in `config.yaml`
3. Robot programs referenced in the scripts are loaded with matching names

## Safety Notes

- These scripts command real hardware motion
- Validate fixtures, clearances, and safe zones before running
- Program calls and waits are blocking and assume expected robot/controller states

## Cleanup Summary

Recent cleanup focused on readability and maintainability:

- removed dead/unreachable logic from `shipment.py`
- fixed type hint/import issues in `home.py`
- simplified and documented key flow in `prod.py`
- normalized constants and naming in `calib.py`
