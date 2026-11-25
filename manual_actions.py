"""Manual actions of the Seymour demo cell — the buttons of the Manual tab
(and of the custom view).

Each key returned by :func:`get_manual_actions` must also be listed under
``manual_actions:`` in config.yaml (label, description, confirmation text),
and every key listed there must be returned here, or the app refuses to
start the workspace.

A manual action runs as an exclusive task, like HOME, so the cell must be
READY. It is the only kind of task allowed while a device is released. An
exception here faults the cell.

Every action calls the same functions as prod_cycle (prod.py), so testing a
piece by hand tests the code PROD runs. Manual actions don't touch the PROD
counters.
"""

from __future__ import annotations

from typing import Dict

from core import AppContext
from devices import Device

from prod import asyril_pick as _asyril_pick
from prod import release_part as _release_part
from prod import scan_once, shake_feeder as _shake_feeder


def scan(devices: Dict[str, Device], context: AppContext):
    """One LMI scan pass with meca_lmi, result logged and shown in the custom view. Nothing else moves."""
    with context.step("Scan part"):
        measured = scan_once(devices, context)
    devices["lmi_sensor"].logger.info(
        f"Manual scan: {'x=%.3f mm, z=%.3f mm' % measured if measured else 'INVALID'}")


def asyril_pick(devices: Dict[str, Device], context: AppContext):
    """Pick one part from the Asyril with the SCARA (sets PickPose.x/.y/.rz on the SCARA)."""
    with context.step("Pick part from feeder"):
        picked = _asyril_pick(devices, context)
    if not picked:
        raise RuntimeError("The Asyril found no pickable part: shake the feeder or add parts.")


def release_part(devices: Dict[str, Device], context: AppContext):
    """SCARA releases whatever it holds, then goes home."""
    with context.step("Release part"):
        _release_part(devices, context)


def shake_feeder(devices: Dict[str, Device], context: AppContext):
    """Vibrate the Asyril platform and have it prepare a new part."""
    with context.step("Shake feeder"):
        _shake_feeder(devices, context)


def get_manual_actions():
    """Keys must match the ``key:`` entries under ``manual_actions:`` in config.yaml."""
    return {
        "scan": scan,
        "asyril_pick": asyril_pick,
        "release_part": release_part,
        "shake_feeder": shake_feeder,
    }
