import sys
import os

# Ensure mecademic_demo_app is in the Python path for standalone execution
app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mecademic_demo_app'))
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from devices import Device
from typing import Dict


def shipment(devices: Dict[str, Device]):
    """Placeholder SHIPMENT task.

    The full shipment motion sequence is intentionally disabled in this repo.
    Keep this task as a no-op hook for integration tests and future expansion.
    """
    _ = devices
    return

if __name__ == '__main__':
    import logging
    from core.ApplicationController import ApplicationController

    logging.basicConfig(level=logging.INFO)
    print("Running standalone test for shipment...")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.yaml")

    # Load actual device configurations
    app_ctrl = ApplicationController(config_path=config_path)

    try:
        # Optional: uncomment to actually communicate with hardware
        app_ctrl.initialize()

        shipment(app_ctrl.devices)
    finally:
        app_ctrl.shutdown()

    print("Test completed successfully.")