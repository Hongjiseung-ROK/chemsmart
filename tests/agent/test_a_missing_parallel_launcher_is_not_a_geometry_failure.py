"""A program that could not start its ranks did not fail to converge.

CUHK job 2142445 (r7m-h3, 2026-09-21): three approved ORCA nodes -- two
optimisations and a saddle search -- died in 22 seconds because ``mpirun``
was not on the search path the engine was given. The lines below are those
runs' own, taken from the archived ``acetonitrile_opt_opt.out`` and ``.err``
with only the two scratch paths shortened.

The class was undiagnosed, so it fell through to ``native_runtime``, the
engine lines quoted to the session were four basis-set assignments, and the
terminal state was ``failed_nonconverged_geometry``: a woken session was told
that a geometry had failed to converge, and offered a geometric repair, for a
job whose first SCF cycle never began. The same fall-through had already
cost six calls once (an input-check abort, REACH-1 po3); this is its second
instance, which is the reason it gets a class and not a special case.
"""

import pytest

from chemsmart.agent.terminal_states import _classify_failure
from chemsmart.io.native_failure import summarize_orca_native_failure

_OUTPUT_TAIL = (
    "Atom   3H    basis set group =>   3",
    "Atom   4H    basis set group =>   3",
    "Atom   5H    basis set group =>   3",
    "",
    "ORCA finished by error termination in Startup",
    "Calling Command: mpirun -np 8  /project/shared/bin/orca_6_1_1/"
    "orca_startup_mpi /scratch/h3/acetonitrile_opt_opt.int.tmp "
    "/scratch/h3/acetonitrile_opt_opt ",
    "[file orca_tools/qcmsg.cpp, line 394]: ",
    "  .... aborting the run",
)
_ERROR_STREAM = (
    "sh: line 1: mpirun: command not found",
    "[file orca_tools/qcmsg.cpp, line 394]: ",
    "  .... aborting the run",
)


@pytest.mark.capability("gate:terminal_state_vocabulary")
def test_the_launcher_is_named_and_the_geometry_is_not_blamed():
    summary = summarize_orca_native_failure(
        _OUTPUT_TAIL, diagnostic_lines=_ERROR_STREAM
    )

    assert summary is not None
    assert summary.error_class == "parallel_launcher_missing"
    assert "mpirun: command not found" in "\n".join(summary.engine_lines)
    assert (
        _classify_failure(
            jobtype="opt",
            findings=("orca.result.optimization_not_converged",),
            native_class=summary.error_class,
            converged=False,
            reached=None,
            planned=None,
        )
        == "failed_native"
    )


@pytest.mark.capability("gate:terminal_state_vocabulary")
def test_an_mpi_failure_inside_a_running_job_keeps_its_own_class():
    """The launcher being absent and the ranks failing are different facts."""

    summary = summarize_orca_native_failure(
        (
            "ORCA finished by error termination in GTOInt",
            "[node07:12345] PMIX ERROR: UNREACHABLE in file server.c",
            "[file orca_tools/qcmsg.cpp, line 394]: ",
            "  .... aborting the run",
        )
    )
    assert summary is not None
    assert summary.error_class == "mpi_runtime"
