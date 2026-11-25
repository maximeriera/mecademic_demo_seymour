"""HOME task — bring the Seymour demo cell to its start position.

Runs from the HOME button, and automatically before the first PROD cycle and
after a graceful STOP. INITIALIZE already activated and homed every robot
(MecaRobot.initialize), so this only runs the cell's own home programs, in an
order that keeps the robots clear of each other. An exception here faults the
cell.
"""

from typing import Dict

from core import AppContext
from devices import Device, MecaRobot

import robot_programs as rp
from prod import scara_part_in_hand, timeout_s


def home(devices: Dict[str, Device], context: AppContext):
    """Park meca_lmi, home the SCARA (releasing a held part), then home the two Meca500."""
    scara: MecaRobot = devices["scara"]
    meca_lmi: MecaRobot = devices["meca_lmi"]
    meca_insert: MecaRobot = devices["meca_insert"]
    timeout = timeout_s(context)

    # meca_lmi first: it clears the shared station for the others.
    with context.step("Park LMI robot"):
        rp.run(meca_lmi, rp.LMI_PARK, timeout=timeout)

    with context.step("Home SCARA"):
        rp.run(scara, rp.SCARA_HOME, timeout=timeout)
        scara_release = None
        if scara_part_in_hand(devices, context):
            # Released while the two Meca500 home; waited for at the end.
            scara_release = rp.start(scara, rp.SCARA_RELEASE, rp.SCARA_HOME)

    with context.step("Home insertion robot"):
        rp.run(meca_insert, rp.INSERT_STANDBY, timeout=timeout)

    with context.step("Home LMI robot"):
        rp.run(meca_lmi, rp.LMI_HOME, timeout=timeout)
        if scara_release is not None:
            scara_release.wait(timeout=timeout)
