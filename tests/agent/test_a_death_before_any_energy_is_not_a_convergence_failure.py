"""A program that died before its first energy did not fail to converge.

R10 Q15 g2 (CUHK Slurm 2153334): four Gaussian 16 nodes died in link 301
after 0.4 s -- "R6DS8: Unable to choose the S8 parameter" -- because this
build holds no D3(BJ) parameters for wB97X. No SCF cycle ran. The output's
class was undiagnosed (``native_runtime``) and the result validator wrote
``optimization_not_converged`` because the convergence marker was absent,
so the optimisation among them was typed ``failed_nonconverged_geometry``
and its repair menu offered a restart from the geometry the run reached.
The woken session rejected that route in its own words -- "No geometry walk
exists to restart from ... bind_reached_geometry would return the unchanged
input coordinates". The same word fell on three ORCA nodes that died in
Startup (r7m-h3, CUHK R8; "there is no admissible reached geometry to
bind") and on six sub-second ORCA deaths in the ax41 campaign
(po3-triazole-regio). Every archived non-convergence that was a real walk
carried an energy; every one of these carried ``energy_missing``.

The lines below are the archived outputs' own, with install and scratch
paths shortened.
"""

import pytest

from chemsmart.agent.terminal_states import _classify_failure
from chemsmart.io.native_failure import (
    summarize_gaussian_native_failure,
    summarize_orca_native_failure,
)

_GAUSSIAN_L301_TAIL = (
    " Integral buffers will be    131072 words long.",
    " Raffenetti 2 integral format.",
    " Two-electron integral symmetry is turned on.",
    " R6DS8: Unable to choose the S8 parameter, IExCor= 4538 IXCFnc= 57 "
    "ScaHFX=  1.000000 IDFTD=4",
    " Error termination via Lnk1e in g16/l301.exe at Thu Sep 24 "
    "23:58:24 2026.",
    " Job cpu time:       0 days  0 hours  0 minutes  2.0 seconds.",
    " Elapsed time:       0 days  0 hours  0 minutes  0.4 seconds.",
)
#: What the Gaussian result validator recorded for that node.
_GAUSSIAN_FINDINGS = (
    "execution.process.nonzero_or_unknown",
    "gaussian.native_failure.native_runtime",
    "gaussian.result.energy_missing",
    "gaussian.result.frequencies_missing",
    "gaussian.result.normal_termination",
    "gaussian.result.optimization_not_converged",
)

_ORCA_STARTUP_TAIL = (
    "Atom   3H    basis set group =>   3",
    "Atom   4H    basis set group =>   3",
    "Atom   5H    basis set group =>   3",
    "ORCA finished by error termination in Startup",
    "[file orca_tools/qcmsg.cpp, line 394]: ",
    "  .... aborting the run",
)
_ORCA_FINDINGS = (
    "execution.process.nonzero_or_unknown",
    "orca.native_failure.native_runtime",
    "orca.result.charge_mismatch",
    "orca.result.energy_missing",
    "orca.result.frequencies_missing",
    "orca.result.multiplicity_mismatch",
    "orca.result.normal_termination",
    "orca.result.optimization_not_converged",
)


@pytest.mark.capability("gate:terminal_state_vocabulary")
@pytest.mark.parametrize(
    "summarize, tail, findings, jobtype",
    [
        (
            summarize_gaussian_native_failure,
            _GAUSSIAN_L301_TAIL,
            _GAUSSIAN_FINDINGS,
            "opt",
        ),
        (
            summarize_orca_native_failure,
            _ORCA_STARTUP_TAIL,
            _ORCA_FINDINGS,
            "ts",
        ),
    ],
)
def test_a_death_before_any_energy_is_the_programs_own_ending(
    summarize, tail, findings, jobtype
):
    summary = summarize(tail)
    assert summary is not None
    # Nothing here names the cause for the classifier: it stays the
    # undiagnosed class, and the engine's own lines carry the reason.
    assert summary.error_class == "native_runtime"
    assert (
        _classify_failure(
            jobtype=jobtype,
            findings=findings,
            native_class=summary.error_class,
            converged=None,
            reached=None,
            planned=None,
            terminated_normally=False,
        )
        == "failed_native"
    )


@pytest.mark.capability("gate:terminal_state_vocabulary")
def test_a_walk_that_ran_out_of_steps_and_then_crashed_stays_a_walk():
    """The boundary: ORCA ends a relaxed scan whose step exhausted its
    iterations by aborting in SHARK, an undiagnosed class -- and the scan
    printed energies, so it is a non-converged step (r9 orca g5)."""

    assert (
        _classify_failure(
            jobtype="scan",
            findings=(
                "execution.process.nonzero_or_unknown",
                "orca.native_failure.native_runtime",
                "orca.result.normal_termination",
                "orca.result.scan_step_not_converged",
            ),
            native_class="native_runtime",
            converged=False,
            reached=1,
            planned=10,
            terminated_normally=False,
        )
        == "failed_nonconverged_scan_step"
    )
