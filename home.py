import sys
import os

# Ensure mecademic_demo_app is in the Python path for standalone execution
app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mecademic_demo_app'))
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from devices import Device, MecaRobot
from typing import Dict


def home(devices: Dict[str, Device]):
    """Logic for HOME task."""
    scara: MecaRobot = devices["scara"]
    meca_lmi: MecaRobot = devices["meca_lmi"]
    meca_insert: MecaRobot = devices["meca_insert"]

    # Park LMI robot first to clear shared workspace.
    meca_lmi.api.StartProgram("22")
    meca_lmi.api.WaitIdle()

    # Return SCARA to home via known-safe sequence.
    scara.api.StartProgram("11")
    scara.api.WaitIdle()
    scara.api.StartProgram("14")
    scara.api.StartProgram("11")

    # Return insert robot to standby.
    meca_insert.api.StartProgram("31")
    meca_insert.api.WaitIdle()

    meca_lmi.api.StartProgram("21")
    meca_lmi.api.WaitIdle()
    scara.api.WaitIdle()
    
if __name__ == '__main__':
    import logging
    from core.ApplicationController import ApplicationController

    logging.basicConfig(level=logging.INFO)
    print("Running standalone test for home...")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.yaml")

    # Load actual device configurations
    app_ctrl = ApplicationController(config_path=config_path)

    try:
        # Optional: uncomment to actually communicate with hardware
        app_ctrl.initialize()

        home(app_ctrl.devices)
    finally:
        app_ctrl.shutdown()

    print("Test completed successfully.")