"""PROD task — one production cycle of the Seymour demo cell.

The app calls ``prod_cycle(devices, context)`` in a loop while PROD runs:
home() first, then cycles until STOP, then home() again. ABORT interrupts the
cycle where it is (a robot wait raises) and skips the exit home. Nothing here
checks for STOP or ABORT.

Sequence (declared under ``sequences: prod_cycle`` in config.yaml):
  1. Pick part from feeder   scara picks from the Asyril until its vacuum holds a part
                             (skipped when it already holds one)
  2. Present part            meca_lmi parked (first cycle), meca_insert ready + scara
                             presents the part at the same time, then meca_lmi approaches
  3. Scan part               LMI scan, up to ``scan_retries`` times until x and z are valid
  4. Insert part             meca_insert inserts, corrected by the scan     } only when the
  5. Verify insertion        second scan pass after the insertion           } scan was valid
  6. Retract                 meca_insert retracts; every robot heads back for the next cycle

Robot programs are listed in robot_programs.py; the functions shared with the
Manual tab (asyril_pick, scan_once, release_part, shake_feeder) live here so a
manual action tests exactly the code PROD runs.
"""

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

from core import AppContext
from devices import AsyrilEyePlus, Device, LMISensor, MecaRobot

import robot_programs as rp
from cell_tools import expect_checkpoint, or_simulated

#: The feeder reports rz in degrees. Parts within this many degrees of 90 are
#: known to fail downstream, so the feeder is asked for another one.
REJECTED_RZ_DEG, REJECTED_RZ_TOLERANCE_DEG = 90.0, 10.0
#: Scan values arrive in micrometres; robot variables take millimetres.
UM_PER_MM = 1000.0

# What simulated devices "return", so the simulated smoke test runs the whole
# cycle. Real drivers always return a value for these calls.
SIMULATED_PART = {"resp": 200, "x": 0.0, "y": 0.0, "rz": 0.0}
SIMULATED_SCAN_RESULT = "0,0.0,0.0"
SIMULATED_VACUUM_KPA = 100.0     # "part held": a simulated PROD skips the pick (the Asyril Pick manual action runs it)


# ---------------------------------------------------------------------------
# Building blocks, shared with manual_actions.py
# ---------------------------------------------------------------------------

def timeout_s(context: AppContext) -> float:
    return float(context.get_param("program_timeout_s", 120))


def scara_part_in_hand(devices: Dict[str, Device], context: AppContext) -> bool:
    """True when the SCARA's vacuum says it holds a part."""
    scara: MecaRobot = devices["scara"]
    threshold = float(context.get_param("scara_vacuum_threshold_kpa", 60))
    pressure = or_simulated(scara.api.GetRtVacuumPressure(), SIMULATED_VACUUM_KPA)
    return abs(pressure) > threshold


def request_part(devices: Dict[str, Device], context: AppContext) -> Optional[dict]:
    """Ask the Asyril for a pickable part. Returns its pose, or None when it has none.

    Parts near rz = 90° are skipped (another one is requested), at most
    ``feeder_retries`` requests in all. ``get_part()`` blocks until the Eye+
    answers (its part timeout, 30 s) and is not interrupted by ABORT.
    """
    asyril: AsyrilEyePlus = devices["asyril"]
    retries = int(context.get_param("feeder_retries", 5))
    for attempt in range(1, retries + 1):
        pose = or_simulated(asyril.api.get_part(), SIMULATED_PART)
        if pose.get("resp") != 200:
            asyril.logger.warning(f"No part pose from the feeder: {pose}")
            return None
        if abs(pose["rz"] - REJECTED_RZ_DEG) < REJECTED_RZ_TOLERANCE_DEG:
            asyril.logger.info(f"Part at rz={pose['rz']:.1f}° skipped (attempt {attempt}/{retries}).")
            continue
        asyril.logger.info(f"Part pose: x={pose['x']}, y={pose['y']}, rz={pose['rz']}")
        return pose
    asyril.logger.warning(f"Only near-vertical parts after {retries} requests.")
    return None


def asyril_pick(devices: Dict[str, Device], context: AppContext) -> bool:
    """Get a part pose from the Asyril and run the SCARA pick there. False when the feeder had none."""
    scara: MecaRobot = devices["scara"]
    pose = request_part(devices, context)
    if pose is None:
        scara.logger.warning("No pickable part on the feeder: pick skipped.")
        return False
    # Robot variables read by the pick program.
    scara.api.SetVariable(name="PickPose.x", value=pose["x"])
    scara.api.SetVariable(name="PickPose.y", value=pose["y"])
    scara.api.SetVariable(name="PickPose.rz", value=pose["rz"])
    rp.run(scara, rp.SCARA_PICK, timeout=timeout_s(context))
    return True


def shake_feeder(devices: Dict[str, Device], context: AppContext) -> None:
    """Vibrate the Asyril platform, let it settle, and have it prepare a new part."""
    asyril: AsyrilEyePlus = devices["asyril"]
    asyril.api.force_execute_vibration()
    remaining_ms = or_simulated(asyril.api.get_remaining_duration_of_current_vibration(), 0)
    time.sleep(max(0.0, float(remaining_ms)) / 1000)
    asyril.api.prepare_part()


def release_part(devices: Dict[str, Device], context: AppContext) -> None:
    """SCARA releases whatever it holds, then goes home."""
    rp.run(devices["scara"], rp.SCARA_RELEASE, rp.SCARA_HOME, timeout=timeout_s(context))


def parse_scan(result) -> Optional[Tuple[float, float]]:
    """(x, z) in mm from the LMI's formatted result ``<time>,<x>,<z>,...``, or None when invalid."""
    fields = str(result).split(",")
    if len(fields) < 3:
        return None
    try:
        x_um, z_um = float(fields[1]), float(fields[2])   # "INVALID" fails here too
    except ValueError:
        return None
    return x_um / UM_PER_MM, z_um / UM_PER_MM


def scan_pass(devices: Dict[str, Device], context: AppContext) -> None:
    """Run the scan program on meca_lmi and trigger the sensor at its mid checkpoint."""
    lmi_sensor: LMISensor = devices["lmi_sensor"]
    meca_lmi: MecaRobot = devices["meca_lmi"]
    timeout = timeout_s(context)

    at_trigger = expect_checkpoint(meca_lmi, rp.LMI_SCAN_TRIGGER_CHECKPOINT)   # armed before the start
    scan = rp.start(meca_lmi, rp.LMI_SCAN)
    at_trigger.wait(timeout=timeout)
    lmi_sensor.api.trigger()
    scan.wait(timeout=timeout)
    time.sleep(float(context.get_param("scan_settle_s", 0.5)))    # let the sensor finish the result


def scan_once(devices: Dict[str, Device], context: AppContext) -> Optional[Tuple[float, float]]:
    """One scan pass, then read the result. Returns (x, z) in mm, or None when invalid.

    Publishes every scan to the custom view (channel ``scan``).
    """
    lmi_sensor: LMISensor = devices["lmi_sensor"]
    scan_pass(devices, context)
    result = or_simulated(lmi_sensor.api.get_formatted_result(), SIMULATED_SCAN_RESULT)
    measured = parse_scan(result)
    lmi_sensor.logger.info(f"Scan result '{result}' -> {measured if measured else 'INVALID'}")
    context.publish("scan", {"ok": measured is not None,
                             "x_mm": measured[0] if measured else None,
                             "z_mm": measured[1] if measured else None})
    return measured


def _increment(context: AppContext, name: str) -> None:
    context.set_variable(name, int(context.get_variable(name, 0)) + 1)


# ---------------------------------------------------------------------------
# The cycle
# ---------------------------------------------------------------------------

def prod_cycle(devices: Dict[str, Device], context: AppContext):
    """Pick, present, scan, insert, verify, retract."""
    scara: MecaRobot = devices["scara"]
    meca_lmi: MecaRobot = devices["meca_lmi"]
    meca_insert: MecaRobot = devices["meca_insert"]
    timeout = timeout_s(context)

    # 1. Pick until the vacuum holds a part (none needed if one is still held).
    if not scara_part_in_hand(devices, context):
        with context.step("Pick part from feeder"):
            max_attempts = int(context.get_param("max_pick_attempts", 10))
            for _ in range(max_attempts):
                _increment(context, "pick_try_count")
                asyril_pick(devices, context)
                if scara_part_in_hand(devices, context):
                    _increment(context, "pick_success_count")
                    break
                with context.step("Shake feeder"):
                    shake_feeder(devices, context)
            else:
                raise RuntimeError(f"No part picked after {max_attempts} attempts: check the parts "
                                   f"on the Asyril platform and the SCARA vacuum.")

    # 2. Bring the part and the robots to the station.
    with context.step("Present part"):
        if not context.get_variable("lmi_robot_in_position", False):
            rp.run(meca_lmi, rp.LMI_PARK, timeout=timeout)
            context.set_variable("lmi_robot_in_position", True)
        insert_ready = rp.start(meca_insert, rp.INSERT_READY)
        present = rp.start(scara, rp.SCARA_PRESENT)
        present.wait(timeout=timeout)
        insert_ready.wait(timeout=timeout)
        rp.run(meca_lmi, rp.LMI_APPROACH, timeout=timeout)

    # 3. Scan until x and z are both valid.
    with context.step("Scan part"):
        measured = None
        for _ in range(int(context.get_param("scan_retries", 3))):
            _increment(context, "scan_try_count")
            measured = scan_once(devices, context)
            if measured is not None:
                _increment(context, "scan_success_count")
                break

    if measured is not None:
        x_mm, z_mm = measured
        context.set_variable("last_scan_x_mm", x_mm)
        context.set_variable("last_scan_z_mm", z_mm)

        # 4. Insert, corrected by the scan.
        with context.step("Insert part"):
            meca_insert.logger.info(f"Insertion offsets from the scan: x={-x_mm} mm, z={-z_mm} mm")
            meca_insert.api.SetVariable("x_offset", -x_mm)
            meca_insert.api.SetVariable("z_offset", -z_mm)
            rp.run(meca_insert, rp.INSERT_INSERT, timeout=timeout)

        # 5. Second pass to verify the insertion (logged and shown in the custom view).
        with context.step("Verify insertion"):
            scan_once(devices, context)
        _increment(context, "part_count")
    else:
        _increment(context, "scan_fail_count")
        meca_insert.logger.warning("No valid scan: part not inserted, cycle goes on to retract.")

    # 6. Retract and send every robot back for the next cycle.
    with context.step("Retract"):
        rp.run(meca_insert, rp.INSERT_RETRACT, timeout=timeout)
        # meca_insert goes to standby while the next cycle picks: not waited for
        # here; its queue runs INSERT_READY after it in the next cycle.
        rp.start(meca_insert, rp.INSERT_STANDBY)
        scara_back = rp.start(scara, rp.SCARA_HOME, rp.SCARA_RELEASE)
        lmi_back = rp.start(meca_lmi, rp.LMI_PARK)
        scara_back.wait(timeout=timeout)
        lmi_back.wait(timeout=timeout)

    # Optional pause between cycles. Outside any step: it shows as idle time.
    time.sleep(float(context.get_param("cycle_wait_s", 0.0)))
