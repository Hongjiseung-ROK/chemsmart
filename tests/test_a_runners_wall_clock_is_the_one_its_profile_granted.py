"""No runner holds a wall clock that outranks the profile it was built from.

A server profile's ``NUM_HOURS`` is what the operator granted: it is what
``#SBATCH --time`` asks the scheduler for, and on the Agent's path it is
written from the node timeout a human approved.  A runner that bounds its
engine by any other number has made a second authority, and the smaller one
wins silently.

It did.  The PySCF runner carried ``NODE_TIMEOUT_SECONDS = 600`` as a class
attribute that no profile, flag or envelope could reach.  A live goal approved
7200 s per node, the review displayed 7200 s, and an IRC branch was killed at
600.3 s (CUHK job 2142445, node ``irc-rev``, 2026-09-21); the claim chain that
depended on it was skipped.  No earlier campaign had run a PySCF node for ten
minutes, so nobody had seen it.

The invariant is stated over every engine the Agent may execute, so the next
runner that learns to watch its child is held to it from its first commit.
It says nothing about *how* a grant becomes seconds -- an exact grant or one
with a margin before the scheduler's own kill is the runner's policy, in
``JobRunner.granted_wall_seconds`` -- only that the number comes from the
profile and moves when the profile moves.
"""

import importlib
import subprocess
import sys

import pytest

from chemsmart.jobs.runner import JobRunner
from chemsmart.settings.capabilities import EXECUTABLE_PROGRAMS


def _engine_runners():
    for program in sorted(EXECUTABLE_PROGRAMS):
        importlib.import_module(f"chemsmart.jobs.{program}.runner")
    return sorted(
        (
            runner
            for runner in JobRunner.subclasses()
            if not getattr(runner, "FAKE", False)
            and str(getattr(runner, "PROGRAM", "")).lower()
            in EXECUTABLE_PROGRAMS
        ),
        key=lambda runner: runner.__name__,
    )


def _profile(path, hours):
    granted = "" if hours is None else f"    NUM_HOURS: {hours}\n"
    path.write_text(
        "SERVER:\n"
        "    SCHEDULER: SLURM\n"
        f"{granted}"
        "    MEM_GB: 4\n"
        "    NUM_CORES: 1\n"
        "    NUM_GPUS: 0\n"
        "    NUM_THREADS: 1\n"
        "    SUBMIT_COMMAND: sbatch\n"
        "    SCRATCH_DIR: null\n"
        "GAUSSIAN:\n    EXEFOLDER: /opt/g16\n    LOCAL_RUN: true\n"
        "ORCA:\n    EXEFOLDER: /opt/orca\n    LOCAL_RUN: true\n"
        "XTB:\n    LOCAL_RUN: true\n"
        "PYSCF:\n    LOCAL_RUN: true\n"
    )
    return str(path)


def _bound_held_while_running(runner_class, profile):
    """The wall clock a runner actually held a real child under, if any."""

    runner = runner_class(server=profile, scratch=False)
    child = subprocess.Popen(
        [sys.executable, "-c", "pass"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    runner._run(child)
    record = getattr(runner, "_process_observation", None)
    held = None if record is None else record["timeout_seconds"]
    return runner, record is not None, held


def test_the_agent_executes_at_least_the_four_engines():
    names = {runner.__name__ for runner in _engine_runners()}
    assert {
        "GaussianJobRunner",
        "ORCAJobRunner",
        "PySCFJobRunner",
        "XTBJobRunner",
    } <= names


@pytest.mark.parametrize(
    "runner_class", _engine_runners(), ids=lambda runner: runner.__name__
)
def test_a_longer_grant_is_a_longer_clock_and_never_a_private_one(
    runner_class, tmp_path
):
    _, watches, under_two = _bound_held_while_running(
        runner_class, _profile(tmp_path / "two.yaml", 2)
    )
    _, _, under_six = _bound_held_while_running(
        runner_class, _profile(tmp_path / "six.yaml", 6)
    )
    if not watches:
        pytest.skip("this runner holds no clock; only the profile's can bind")

    assert under_two is not None and under_six is not None
    assert under_two <= 2 * 3600 and under_six <= 6 * 3600
    assert under_six > under_two, (
        f"{runner_class.__name__} held its engine for {under_two} s under a "
        f"2 h grant and {under_six} s under a 6 h grant: that clock is the "
        "runner's own, not the profile's"
    )


@pytest.mark.parametrize(
    "runner_class", _engine_runners(), ids=lambda runner: runner.__name__
)
@pytest.mark.parametrize("hours", [2, None], ids=["granted", "unstated"])
def test_the_clock_a_runner_holds_is_the_one_it_says_it_was_granted(
    runner_class, hours, tmp_path
):
    runner, watches, held = _bound_held_while_running(
        runner_class, _profile(tmp_path / "site.yaml", hours)
    )

    if watches:
        assert held == runner.granted_wall_seconds
    if hours is None:
        # A profile that states no hours grants no particular clock; a runner
        # may not invent one in its place.
        assert runner.granted_wall_seconds is None
