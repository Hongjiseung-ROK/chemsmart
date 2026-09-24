"""A run the program finished and the host refused is not an engine failure.

``failed_native`` says "the program stopped on its own error", and the
repair menu tells the session so. It was the word for every failure no
other ending explained, including runs whose output ends in the program's
own normal termination and whose only findings are a host reader's or
validator's: R10 Q14's census of the R8-R10 CUHK goals and the ax41
campaign found 17 such calls among 133 failures -- two ORCA outputs ending
ORCA TERMINATED NORMALLY (Q12 g1-hi, an atomic-guess log counted as a
second result), six Gaussian logs ending Normal termination (Q5, a
dispersion spelled in the route) and xTB runs whose settings a reader
could not find. Replaying the archived streams through the derivation
turns exactly those whose output is still readable (13) into the new word
and moves nothing else (1,036 engine calls compared).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from chemsmart.agent.terminal_states import (
    NODE_TERMINAL_STATES,
    REPAIRABLE_NODE_STATES,
    _artifact_terminated_normally,
    _classify_failure,
)

pytestmark = pytest.mark.capability("gate:terminal_state_vocabulary")

#: A real ORCA output that ended ORCA TERMINATED NORMALLY (R10 Q9 G1).
FINISHED = Path("tests/data/ORCATests/atoms/h_atom_uks_wb97xd3bj_sp.out")


def _record(path: Path, program: str = "orca") -> dict:
    return {
        "program": program,
        "output_artifacts": [
            {
                "kind": f"{program}_output",
                "path": str(path.resolve()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        ],
    }


def _word(**overrides) -> str:
    facts = {
        "jobtype": "sp",
        "findings": ("orca.result.output_count",),
        "native_class": "",
        "converged": None,
        "reached": None,
        "planned": None,
        "terminated_normally": True,
    }
    facts.update(overrides)
    return _classify_failure(**facts)


def test_the_program_s_own_output_says_it_finished():
    assert _artifact_terminated_normally(_record(FINISHED)) is True
    moved = _record(FINISHED)
    moved["output_artifacts"][0]["sha256"] = "0" * 64
    assert _artifact_terminated_normally(moved) is None


def test_a_finished_run_a_host_rule_refused_has_its_own_word():
    assert _word() == "failed_result_validation"
    assert "failed_result_validation" in NODE_TERMINAL_STATES
    assert "failed_result_validation" in REPAIRABLE_NODE_STATES
    # An archived class that names no cause does not outrank the output.
    assert _word(native_class="incomplete_output") == (
        "failed_result_validation"
    )


def test_the_engine_keeps_its_word_where_it_stopped_or_nothing_can_say():
    # Nothing readable says the program finished: the program's word.
    assert _word(terminated_normally=None) == "failed_native"
    assert _word(terminated_normally=False) == "failed_native"
    # A class that names a cause is the program's own account.
    assert _word(native_class="input_check") == "failed_native"
    # Endings that explain a finished run keep their meaning.
    assert (
        _word(
            findings=("orca.result.optimization_not_converged",),
            jobtype="opt",
        )
        == "failed_nonconverged_geometry"
    )
    assert (
        _word(findings=("result.stationary_point_order",), jobtype="opt")
        == "failed_wrong_stationary_point"
    )
