"""Every robot program this workspace starts, and how Python waits for each.

The motion of this cell lives in programs saved on the three controllers.
Python only decides *when* a program runs; this file is the single list of
them (README.md, "Robot programs", mirrors it).

Waiting for a program
---------------------
The framework's standard (cell_tools.run_program) waits for a checkpoint the
program sets on its last line, ``SetCheckpoint(<n>)``. The app drives the
robots in mecademicpy's asynchronous mode, where ``StartProgram`` only sends
the command, so a ``WaitIdle()`` right after it can in principle return
before the program queued its first move. A checkpoint cannot.

These programs predate that convention and were always waited for with
``WaitIdle()``, which has worked on this cell. So each ``Program`` below has
``done_checkpoint=None`` (wait with ``WaitIdle``) until its controller program
ends with ``SetCheckpoint(<n>)``: then put ``<n>`` here and nothing else
changes. Convention: 1-9 for home/calibration programs, 11+ for production,
unique per robot.

ABORT sends ``ClearMotion()`` to every robot, which makes both kinds of wait
raise ``InterruptException``: nothing here checks for ABORT itself.

Program meanings are inferred from how the old workspace used them.
TODO: confirm each description on the controllers.
"""

from __future__ import annotations

from typing import NamedTuple, Optional

from cell_tools import DEFAULT_PROGRAM_TIMEOUT_S, start_program


class Program(NamedTuple):
    name: str                               # program name on the controller
    done_checkpoint: Optional[int] = None   # SetCheckpoint(<n>) on its last line, or None: WaitIdle


# --- scara (Asyril pick, presents the part) ---------------------------------
SCARA_HOME = Program("11")                  # home / safe pose
SCARA_PICK = Program("12")                  # pick at robot variables PickPose.x / .y / .rz
SCARA_PRESENT = Program("13")               # bring the part to the scan / insertion station
SCARA_RELEASE = Program("14")               # release the held part
SCARA_CALIB_STAND_PICK = Program("stand_pick")    # take the calibration target from its stand
SCARA_CALIB_PLACE = Program("calib_place")        # place target at CalibPoses.x / .y
SCARA_CALIB_PICK = Program("calib_pick")          # take the target back
SCARA_CALIB_STAND_PLACE = Program("stand_place")  # return the target to its stand

# --- meca_lmi (carries the LMI sensor) --------------------------------------
LMI_HOME = Program("21")                    # home pose, end of HOME
LMI_PARK = Program("22")                    # parked clear of the station, ready for the next scan
LMI_APPROACH = Program("23")                # approach the scan start
LMI_SCAN = Program("24")                    # scan pass; sets checkpoint LMI_SCAN_TRIGGER_CHECKPOINT mid-way
LMI_SCAN_TRIGGER_CHECKPOINT = 222           # where the program wants the sensor triggered

# --- meca_insert (inserts using the scan offsets) ---------------------------
INSERT_STANDBY = Program("31")              # standby pose
INSERT_READY = Program("32")                # ready above the station
INSERT_INSERT = Program("insertion")        # insert, corrected by robot variables x_offset / z_offset (mm)
INSERT_RETRACT = Program("retract_from_inspect")  # retract from the station


class _IdleRun:
    """A program waited for with ``WaitIdle`` (no end checkpoint yet)."""

    def __init__(self, robot, program: str):
        self.robot = robot
        self.program = program

    def wait(self, timeout: float = DEFAULT_PROGRAM_TIMEOUT_S, wait_idle: bool = True) -> None:
        self.robot.api.WaitIdle(timeout=timeout)
        self.robot.logger.info(f"[{self.robot.device_id}] program '{self.program}' done (idle).")


def start(robot, *programs: Program):
    """Queue *programs* on *robot*, in order, without waiting. ``.wait(timeout)`` the result later.

    The wait covers every program queued here: they run one after the other.
    Starting programs on several robots, then waiting for each, runs them at
    the same time from the task thread.
    """
    run = None
    for program in programs:
        if program.done_checkpoint is None:
            robot.logger.info(f"[{robot.device_id}] StartProgram('{program.name}'), wait: idle.")
            robot.api.StartProgram(program.name)
            run = _IdleRun(robot, program.name)
        else:
            run = start_program(robot, program.name, program.done_checkpoint)
    return run


def run(robot, *programs: Program, timeout: float = DEFAULT_PROGRAM_TIMEOUT_S) -> None:
    """Run *programs* on *robot*, in order, and block until the last one is done."""
    start(robot, *programs).wait(timeout=timeout)
