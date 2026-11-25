"""CALIBRATION task — Asyril hand-eye calibration with the SCARA.

Runs from the CALIBRATION button only. The SCARA takes the calibration target
from its stand, places it at four poses where the Asyril takes an image of
it, returns it, then the Asyril computes the calibration and goes back into
production. An exception here faults the cell; if it happens after the
feeder left production, INITIALIZE puts it back (it restarts production with
the recipe from config.yaml).
"""

from typing import Dict

from core import AppContext
from devices import AsyrilEyePlus, Device, MecaRobot

import robot_programs as rp
from cell_tools import or_simulated
from prod import timeout_s

#: Asyril recipe used for the hand-eye calibration.
CALIBRATION_RECIPE_ID = 13186
#: Where the SCARA places the target for each calibration image (robot variables
#: CalibPoses.x / CalibPoses.y, mm, SCARA frame). Also sent to the Asyril.
CALIB_POSES_XY_MM = [(67, -120), (67, -160), (25, -120), (25, -160)]


def calib(devices: Dict[str, Device], context: AppContext):
    scara: MecaRobot = devices["scara"]
    asyril: AsyrilEyePlus = devices["asyril"]
    timeout = timeout_s(context)

    with context.step("Start feeder calibration"):
        asyril.api.stop_production()
        reply = or_simulated(asyril.api.start_calibration(CALIBRATION_RECIPE_ID), "200")
        if not str(reply).startswith("200"):
            raise RuntimeError(f"The Asyril refused to start calibration (recipe "
                               f"{CALIBRATION_RECIPE_ID}): {reply}")

    with context.step("Take calibration target"):
        scara.api.WaitIdle(timeout=timeout)
        rp.run(scara, rp.SCARA_CALIB_STAND_PICK, timeout=timeout)

    with context.step("Capture calibration images"):
        for x_mm, y_mm in CALIB_POSES_XY_MM:
            scara.api.SetVariable("CalibPoses.x", x_mm)
            scara.api.SetVariable("CalibPoses.y", y_mm)
            asyril.api.set_calibration_pose(x_mm, y_mm)
            rp.run(scara, rp.SCARA_CALIB_PLACE, timeout=timeout)
            asyril.api.take_calibration_image()
            rp.run(scara, rp.SCARA_CALIB_PICK, timeout=timeout)

    with context.step("Return calibration target"):
        rp.run(scara, rp.SCARA_CALIB_STAND_PLACE, timeout=timeout)

    with context.step("Compute calibration"):
        asyril.api.calibrate()          # raises RuntimeError when the Eye+ rejects it

    with context.step("Restart feeder production"):
        asyril.api.start_production()
