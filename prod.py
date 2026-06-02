import sys
import os
import time

# Ensure mecademic_demo_app is in the Python path for standalone execution
app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mecademic_demo_app'))
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from devices import Device
from typing import Dict, Optional

try:
    from .manual_actions import *
except ImportError:
    from manual_actions import *

from core.ProductionContext import ProductionContext
from devices import LMISensor, MecaRobot, AsyrilEyePlus

SCAN_RETRY_NUMBER = 3

SCARA_VACUUM_THRESHOLD = 60

def scara_part_in_hand(devices: Dict[str, Device], context: Optional[ProductionContext] = None) -> bool:
    """Return True when SCARA vacuum indicates a picked part."""
    _ = context  # Kept for task API consistency.
    scara: MecaRobot = devices["scara"]
    pressure = abs(scara.api.GetRtVacuumPressure())
    return pressure > SCARA_VACUUM_THRESHOLD

'''
def asyril_pick(devices: Dict[str, Device], context: Optional[ProductionContext] = None) -> None:
    """Pick one part from Asyril and update SCARA pick variables."""
    _ = context  # Kept for task API consistency.
    scara: MecaRobot = devices["scara"]
    asyril: AsyrilEyePlus = devices["asyril"]

    asyril.logger.info("force taking image for pick")
    asyril.api.force_take_image()
    
    asyril.logger.info("getting part pose for pick")
    pose = asyril.api.get_part()

    # Reject near-vertical part orientations that are known to fail downstream.
    while abs(pose['rz'] - 90) < 10:
        pose = asyril.api.get_part()

    asyril.logger.info(f"pose response: {pose}")
    if pose['resp'] == 200:
        scara.api.SetVariable(name='PickPose.x', value=pose['x'])
        scara.api.SetVariable(name='PickPose.y', value=pose['y'])
        scara.api.SetVariable(name='PickPose.rz', value=pose['rz'])
    else:
        asyril.logger.warning("Failed to get part pose (timeout)")
        scara.logger.warning("Failed to get part pose (timeout) - skiping pick")
        return
    
    scara.api.StartProgram("12")
    scara.api.WaitIdle()
    
    return


def scan(devices: Dict[str, Device], context: Optional[ProductionContext] = None):
    lmi_sensor: LMISensor = devices["lmi_sensor"]
    meca_lmi: MecaRobot = devices["meca_lmi"]

    meca_lmi.api.ExpectExternalCheckpoint(222)
    meca_lmi.api.StartProgram("24")
    meca_lmi.api.WaitForAnyCheckpoint()
    lmi_sensor.api.trigger()
    meca_lmi.api.WaitIdle()
    time.sleep(0.5)
'''

def scan_insert_retract(devices: Dict[str, Device], context: Optional[ProductionContext] = None) -> None:
    """Run LMI scan, insertion, verification scan, and retract sequence."""
    _ = context  # Kept for task API consistency.
    lmi_sensor: LMISensor = devices["lmi_sensor"]
    meca_lmi: MecaRobot = devices["meca_lmi"]
    scara: MecaRobot = devices["scara"]
    meca_insert: MecaRobot = devices["meca_insert"]
    context: ProductionContext = context

    meca_lmi.api.StartProgram("22")
    meca_lmi.api.WaitIdle()

    meca_insert.api.StartProgram("32")
    scara.api.StartProgram("13")
    scara.api.WaitIdle()
    meca_insert.api.WaitIdle()

    meca_lmi.api.StartProgram("23")
    meca_lmi.api.WaitIdle()

    scan_ok = False
    x = "INVALID"
    z = "INVALID"

    for _ in range(SCAN_RETRY_NUMBER):
        scan_try_count = context.get_variable("scan_try_count", 0)
        context.set_variable("scan_try_count", scan_try_count + 1, force=True)
        scan(devices=devices, context=context)

        result = lmi_sensor.api.get_formatted_result()

        x, z = result.split(",")[1:3]
        lmi_sensor.logger.info(f"Received measurements: x={x}, z={z}")

        if x != "INVALID" and z !="INVALID":
            scan_ok = True
            break

    if scan_ok:
        scan_success_count = context.get_variable("scan_success_count", 0)
        context.set_variable("scan_success_count", scan_success_count + 1, force=True)

        meca_insert.logger.info(f"Setting insert position based on LMI measurements: x={x}, z={z}")
        meca_insert.api.SetVariable("x_offset", -float(x)/1000)  # Convert from microns to mm 
        meca_insert.api.SetVariable("z_offset", -float(z)/1000)  # Convert from microns to mm 
        meca_insert.api.StartProgram("insertion")
        meca_insert.api.WaitIdle()

        # Re-scan after insertion to verify.
        meca_lmi.api.ExpectExternalCheckpoint(222)
        meca_lmi.api.StartProgram("24")
        meca_lmi.api.WaitForAnyCheckpoint()

        lmi_sensor.api.trigger()

        meca_lmi.api.WaitIdle()
        time.sleep(0.5)

    # Retract sequence and return both robots to ready state.
    meca_insert.api.StartProgram("retract_from_inspect")
    meca_insert.api.WaitIdle()
    meca_insert.api.StartProgram("31")
    scara.api.StartProgram("11")
    scara.api.StartProgram("14")
    scara.api.StartProgram("11")
    scara.api.WaitIdle()
    meca_insert.api.WaitIdle()

    meca_lmi.api.StartProgram("22")
    meca_lmi.api.StartProgram("21")
    

def prod_cycle(devices: Dict[str, Device], context: Optional[ProductionContext] = None):
    """Logic for PROD task."""
    context = context 
    scara: MecaRobot = devices["scara"]
    asyril: AsyrilEyePlus = devices["asyril"]
    meca_lmi: MecaRobot = devices["meca_lmi"]

    while not scara_part_in_hand(devices=devices, context=context):
        pick_try_count = context.get_variable("pick_try_count", 0)
        context.set_variable("pick_try_count", pick_try_count + 1, force=True)
        asyril_pick(devices=devices, context=context)
        asyril.api.force_execute_vibration()
        time.sleep(asyril.api.get_remaining_duration_of_current_vibration()/1000)  # Allow time for vibration to settle before checking vacuum again.
        asyril.api.prepare_part()

    pick_success_count = context.get_variable("pick_success_count", 0)
    context.set_variable("pick_success_count", pick_success_count + 1, force=True)

    scan_insert_retract(devices=devices, context=context)

    scara.api.WaitIdle()
    meca_lmi.api.WaitIdle()

    return

if __name__ == '__main__':
    import os
    from core.ApplicationController import ApplicationController

    print("Running standalone test for prod_cycle...")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.yaml")
    context_path = os.path.join(script_dir, "production_context.yaml")

    # 1. Initialize ApplicationController to parse real configs and create device objects
    app_ctrl = ApplicationController(
        config_path=config_path,
        production_context_path=context_path
    )

    try:
        # Optional: uncomment to actually communicate with hardware
        app_ctrl.initialize()

        # Execute the cycle using the loaded devices and production context
        prod_cycle(app_ctrl.devices, context=app_ctrl.production_context)
        
    finally:
        # Ensure to cleanly shut down any background thread created by the controller
        app_ctrl.shutdown()

    print("prod_cycle executed successfully.")