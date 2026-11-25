"""SHIPMENT task — not defined for this cell yet.

Runs from the SHIPMENT button only. It does nothing but say so: the robots
are folded for transport by hand (or with HOME). The file must exist anyway:
without it the app would run the demo shipment() shipped in
mecademic_demo_app/app_logic/, written for other devices.

To add one: write the transport-pose programs on each controller, list them
in robot_programs.py, run them here in steps, and declare the steps under
``sequences: shipment`` in config.yaml.
"""

from typing import Dict

from core import AppContext
from devices import Device


def shipment(devices: Dict[str, Device], context: AppContext):
    with context.step("No shipment sequence defined"):
        devices["scara"].logger.info("SHIPMENT: no shipment sequence defined for this cell; nothing moved.")
