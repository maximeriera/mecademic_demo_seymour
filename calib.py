import sys
import os

# Ensure mecademic_demo_app is in the Python path for standalone execution
app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mecademic_demo_app'))
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from devices import Device
from typing import Dict

from devices import MecaRobot, AsyrilEyePlus

CALIBRATION_RECIPE_ID = 13186

def calib(devices: Dict[str, Device]):
    """Logic for CALIB task."""
    calib_poses_x = [67, 67, 25, 25]
    calib_poses_y = [-120, -150, -120, -150]
    
    scara: MecaRobot = devices["scara"]
    asyril: AsyrilEyePlus = devices["asyril"]

    asyril.api.stop_production()
    asyril.api.start_calibration(CALIBRATION_RECIPE_ID)

    if not asyril.api._in_calib:
        raise RuntimeError("Failed to start calibration")

    # Make sure SCARA is in a stable state before calibration sequence starts.
    scara.api.WaitIdle()

    for i, (x_pos, y_pos) in enumerate(zip(calib_poses_x, calib_poses_y)):
        scara.api.SetVariable("CalibPoses.x", x_pos)
        scara.api.SetVariable("CalibPoses.y", y_pos)
        asyril.api.set_calibration_pose(x_pos, y_pos)
        scara.api.StartProgram("calib_place")
        scara.api.WaitIdle()
        asyril.api.take_calibration_image()
        if i < 3:
            scara.api.StartProgram("calib_pick")
            scara.api.WaitIdle()

    asyril.api.calibrate()

    asyril.api.start_production()
    return

if __name__ == '__main__':
    import logging
    from core.ApplicationController import ApplicationController

    logging.basicConfig(level=logging.INFO)
    print("Running standalone test for calib...")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.yaml")

    # Load actual device configurations
    app_ctrl = ApplicationController(config_path=config_path)

    try:
        # Optional: uncomment to actually communicate with hardware
        app_ctrl.initialize()

        calib(app_ctrl.devices)
    finally:
        app_ctrl.shutdown()

    print("Test completed successfully.")