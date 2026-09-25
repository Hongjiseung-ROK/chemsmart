"""A free energy at a held coordinate, and what the receipt says it is.

R10 Q21 made the host refuse a free energy at a structure that is not a
stationary point, and both live goals that met the refusal on H2O2 held at
H-O-O-H = 0, 90 and 180 deg (CUHK 2153623, 2153668) said the honest
alternative was absent. These tests drive the host's own
``derive_thermochemistry`` handler on the archived ORCA results of those
goals (``tests/data/ORCATests/hooh_torsion``, README there).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1
from chemsmart.analysis.result_readers import reader_for

pytestmark = [pytest.mark.capability("tool:derive_thermochemistry")]

_DATA = Path(__file__).resolve().parents[1] / "data" / "ORCATests"
_TORSION = _DATA / "hooh_torsion"
RESULTS = {
    # R10 Q21 g1-hooh node opt180: an ``opt`` that stopped on the trans
    # saddle (one mode at -245.88 cm^-1), typed failed_wrong_stationary_point.
    "orca-trans-saddle-by-opt": (
        "orca",
        _TORSION / "geometry-hooh-d180_opt_opt.out",
    ),
}
#: cm^-1 per hartree (CODATA 2018), for reading a zero-point energy.
_CM1_PER_HARTREE = 219474.6313632


def _host(tmp_path):
    from chemsmart.agent.runtime.event_store import RuntimeEventStore
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    artifacts = {}
    for artifact_id, (program, path) in RESULTS.items():
        resolved = path.resolve()
        artifacts[artifact_id] = TrustedArtifactRefV1(
            artifact_id=artifact_id,
            kind=reader_for(program).artifact_kind,
            sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
            size_bytes=resolved.stat().st_size,
            path=str(resolved),
            cli_value=str(resolved),
        )
    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="s"
        ),
        artifacts=artifacts,
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )


def _quantity(receipt, quantity_id):
    return next(
        item.value
        for item in receipt.quantities
        if item.quantity_id == quantity_id
    )


def test_a_named_reaction_coordinate_leaves_the_partition_function(
    tmp_path,
):
    """The mode a session names is excluded, as the receipt says it is.

    Whatever the program's job label: an ``opt`` that landed on a saddle
    is characterised order 1 by the host and its imaginary mode named; the
    zero-point energy is then half the sum of the five real modes, with no
    term left behind for the named one.
    """

    host = _host(tmp_path)
    artifact_id = "orca-trans-saddle-by-opt"
    host._characterise_stationary_point(
        "turn-1",
        {
            "result_artifact_id": artifact_id,
            "program": "orca",
            "order_claimed": 1,
        },
    )
    receipt = host._derive_thermochemistry(
        "turn-2",
        {
            "program": "orca",
            "artifact_id": artifact_id,
            "temperature_k": 298.15,
            "pressure_atm": 1.0,
            "reaction_coordinate_mode": 1,
        },
    )
    reader = reader_for("orca")
    output = reader.open_output(RESULTS[artifact_id][1])
    printed, _unit = reader.read(output, "vibrational_frequencies")
    real = [value for value in printed if value > 0.0]
    assert len(real) == len(printed) - 1
    assert any(
        "mode 1 taken as the reaction coordinate and excluded" in line
        for line in receipt.assumptions
    )
    assert _quantity(receipt, "zero_point_energy") == pytest.approx(
        0.5 * sum(real) / _CM1_PER_HARTREE, abs=2e-8
    )
