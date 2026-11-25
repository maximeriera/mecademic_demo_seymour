"""Custom view of the Seymour demo cell — a simple operator page at /view/.

The page (index.html) only uses the app's REST API: controller status,
production metrics, the context variables, the manual actions, and the
``scan`` channel that prod.scan_once() publishes after every LMI scan.

So there is nothing to sample here: setup() registers no source. Add one with
``hub.add_source(...)`` (see mecademic_demo_app/app_logic/custom_view/) when
the page should plot a live value, e.g. the SCARA vacuum through
``robot.rt.GetRtVacuumPressure(synchronous_update=False)``.
"""


def setup(hub, devices):
    """Called by the controller at every INITIALIZE. Nothing to register yet."""
    return None
