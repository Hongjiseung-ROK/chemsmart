"""An IRC endpoint reached by minimising is not an endpoint the path walked.

The PySCF IRC validator has always measured whether geomeTRIC switched
from Gonzalez-Schlegel path steps to plain minimisation, and where. Until
this round nothing under ``chemsmart/agent`` read it, so "the IRC reached
separated H2 and CO" and "a minimisation started from the IRC's tail
reached separated H2 and CO" were the same sentence to a session.

These are the bytes where the difference is real. The saddle is the one a
live goal's third transition-state search found for H2CO -> H2 + CO
(CUHK 2141229 g3-h2co-elimination cycle 3, which then ran out of
revisions before it could confirm it); the Hessian and the two branches
are the diagnostic that finished the question (CUHK 2141482). The
backward branch records 77 frames, of which **37 are path steps and 40
are the minimisation after them**.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pytest

from chemsmart.agent.terminal_states import (
    _path_account,
    consequential_imaginary_mode_count,
)
from chemsmart.analysis.result_readers import reader_for
from chemsmart.jobs.pyscf.settings import PySCFJobSettings
from chemsmart.jobs.pyscf.validation import validate_pyscf_result

FIXTURES = Path(__file__).resolve().parent / "data" / "PySCFTests" / "outputs"

CASES = {
    "hess": (
        "h2co_elimination_ts_hess",
        "g3_ts_hess_gas_phase.h5",
    ),
    "forward": (
        "h2co_elimination_irc_fwd",
        "g3_irc_fwd_gas_phase.h5",
    ),
    "backward": (
        "h2co_elimination_irc_bwd_minimisation_tail",
        "g3_irc_bwd_gas_phase.h5",
    ),
}

pytestmark = pytest.mark.capability("program_jobtype:pyscf:cpu:irc")


def _path(key: str) -> Path:
    directory, name = CASES[key]
    return FIXTURES / directory / name


def _open(key: str):
    return reader_for("pyscf").open_output(_path(key))


def _validate(key: str):
    output = _open(key)
    spec = output.spec
    values = {
        "jobtype": str(spec["jobtype"]),
        "ab_initio": "hf",
        "basis": spec["basis"],
        "charge": int(spec["charge"]),
        "multiplicity": int(spec["multiplicity"]),
    }
    if str(spec["jobtype"]) == "hess":
        values["freq"] = True
    else:
        values["opt_maxsteps"] = int(spec["opt_maxsteps"])
        values["irc_direction"] = str(spec["irc_direction"])
    return validate_pyscf_result(
        _path(key),
        settings=PySCFJobSettings(**values),
        expected_jobtype=str(spec["jobtype"]),
        expected_charge=int(output.charge),
        expected_multiplicity=int(output.multiplicity),
        expected_symbols=list(output.chemical_symbols),
        **(
            {"expected_positions": spec["positions"]}
            if str(spec["jobtype"]) == "hess"
            else {}
        ),
    )


def _distances(output) -> dict[str, float]:
    positions = np.asarray(output.positions, dtype=float)
    symbols = list(output.chemical_symbols)
    return {
        f"{symbols[i]}{i}-{symbols[j]}{j}": float(
            np.linalg.norm(positions[i] - positions[j])
        )
        for i, j in itertools.combinations(range(len(symbols)), 2)
    }


def _account(key: str):
    return _path_account("pyscf", {"result_validation": _validate(key)})


def test_the_saddle_a_live_search_found_is_a_first_order_saddle():
    hessian = _open("hess")
    frequencies = tuple(float(v) for v in hessian.vibrational_frequencies)
    assert consequential_imaginary_mode_count(frequencies) == 1
    assert abs(frequencies[0] - (-2191.9)) < 1.0
    assert (
        reader_for("pyscf").stationarity_gradient_for_output(hessian) < 4.5e-4
    )
    assert _validate("hess")["state"] == "validated"


def test_the_forward_branch_walks_to_formaldehyde():
    account = _account("forward")
    assert account["path_converged"] is True
    assert account["reached_by"] == "path_step"
    assert account["minimisation_frames"] == 0
    distances = _distances(_open("forward"))
    assert abs(distances["C0-O1"] - 1.1843) < 0.01
    assert abs(distances["C0-H2"] - 1.0915) < 0.01
    assert abs(distances["C0-H3"] - 1.0915) < 0.01


def test_the_backward_branch_reached_its_end_by_minimising():
    """The case the record exists for. The endpoint is separated H2 and
    CO -- and more than half the frames that got there are not path
    steps, which is a fact about the evidence and not about the
    chemistry."""

    account = _account("backward")
    assert account["switched_to_minimisation"] is True
    assert account["reached_by"] == "minimisation_from_path_tail"
    assert account["frames"] == 77
    assert account["path_step_frames"] == 37
    assert account["minimisation_frames"] == 40
    assert (
        account["path_step_frames"] + account["minimisation_frames"]
        == account["frames"]
    )
    # Only the path steps are compared against steepest descent; the
    # minimisation's are deliberately left out.
    assert account["steepest_descent_steps_compared"] == 36
    # Where it ended: free H2 and free CO, well apart.
    distances = _distances(_open("backward"))
    assert abs(distances["H2-H3"] - 0.73) < 0.02
    assert abs(distances["C0-O1"] - 1.1135) < 0.02
    assert distances["C0-H2"] > 3.0


def test_both_branches_start_where_the_hessian_looked():
    hessian_frequencies = [
        round(float(v), 1) for v in _open("hess").vibrational_frequencies
    ]
    for key in ("forward", "backward"):
        start = _account(key)["start_frequencies_cm1"]
        assert [round(float(v), 1) for v in start] == hessian_frequencies[:3]
        assert _account(key)["start_max_abs_gradient_eh_per_bohr"] < 4.5e-4


def test_the_archived_receipts_say_what_the_runs_said():
    for key in CASES:
        recorded = json.loads(
            _path(key).with_suffix(".receipt.json").read_text()
        )["result_validation"]["state"]
        assert recorded == "validated", key
        assert _validate(key)["state"] == recorded, key
