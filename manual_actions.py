from __future__ import annotations

import os
import sys
import time
from typing import Dict

# Ensure mecademic_demo_app is in the Python path for standalone execution
app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mecademic_demo_app'))
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from devices import Device
from typing import Dict, Optional

from core.ProductionContext import ProductionContext

from devices import Device
from devices import LMISensor, MecaRobot, AsyrilEyePlus


def scan(devices: Dict[str, Device], context=None):
    """Example manual runtime action.

    Implement project-specific inspection-only logic here.
    """
    lmi_sensor: LMISensor = devices["lmi_sensor"]
    meca_lmi: MecaRobot = devices["meca_lmi"]

    meca_lmi.api.ExpectExternalCheckpoint(222)
    meca_lmi.api.StartProgram("24")
    meca_lmi.api.WaitForAnyCheckpoint()
    lmi_sensor.api.trigger()
    meca_lmi.api.WaitIdle()
    time.sleep(0.5)

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


def get_manual_actions():
    """Return project-specific manual actions exposed in the Manual tab."""
    return {
        "scan": scan,
        "asyril_pick": asyril_pick,
    }
