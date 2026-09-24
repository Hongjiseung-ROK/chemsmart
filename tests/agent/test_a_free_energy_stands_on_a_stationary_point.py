"""A free energy is a property of a stationary point, and says which one.

The characterisation refused to give an order to a structure whose measured
gradient exceeds the optimiser's criterion, and the thermochemistry
derivation asked nothing, so the same host derived a free energy from:

- a Gaussian ``modred`` optimisation held at H-O-O-H = 90 deg (its project
  default runs the frequency step, so the modes are there);
- an ORCA OptTS that printed its own non-convergence (po3-r19, archived:
  one approved chain and two live sessions delivered a free energy of
  activation of 23.19 kcal/mol standing on it);
- PySCF's ``water_stretched_hess``, at max|g| = 0.0185 Eh/Bohr, the very
  artifact the characterisation refuses an order on.

Both organs now read one function (``structure_stationarity``), a
structure shown not to be stationary is refused with the route that
remains, and every derived receipt states what its free energy stands on
-- including ``unmeasured`` where the result was handed its geometry and
binds no gradient to it. Driven through the host's own
``derive_thermochemistry`` handler on real archived output.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from chemsmart.agent._contracts import ContractError, TrustedArtifactRefV1
from chemsmart.analysis.result_readers import reader_for

pytestmark = [
    pytest.mark.capability("tool:derive_thermochemistry"),
    pytest.mark.capability(
        "gate:thermochemistry.free_energy_needs_a_stationary_point"
    ),
]

_DATA = Path(__file__).resolve().parents[1] / "data"
RESULTS = {
    "gaussian-modred-hooh90": (
        "gaussian",
        _DATA
        / "GaussianTests/constrained_dihedral/h2o2_b3lyp_def2svp_hooh90.log",
    ),
    "orca-unconverged-optts": (
        "orca",
        _DATA
        / "ORCATests/unconverged_saddle_search/presaddle-esterc4_optts_optts.out",
    ),
    "pyscf-stretched-hess": (
        "pyscf",
        _DATA
        / "PySCFTests/outputs/water_stretched_hess/water_stretched_hess_gas_phase.h5",
    ),
    "pyscf-water-hess": (
        "pyscf",
        _DATA / "PySCFTests/outputs/water_hess/water_hess_gas_phase.h5",
    ),
    "gaussian-nh3-opt-freq": (
        "gaussian",
        _DATA / "GaussianTests/basis_forms/nh3_opt_b3lyp_631gd_g2.log",
    ),
    "orca-h-atom": (
        "orca",
        _DATA / "ORCATests/atoms/h_atom_opt_freq_b3lyp.out",
    ),
    "xtb-acetaldehyde-hess": (
        "xtb",
        _DATA / "XTBTests/outputs/acetaldehyde_hess/acetaldehyde_hess.out",
    ),
}


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


def _derive(host, artifact_id):
    return host._derive_thermochemistry(
        "turn-1",
        {
            "program": RESULTS[artifact_id][0],
            "artifact_id": artifact_id,
            "temperature_k": 298.15,
            "pressure_atm": 1.0,
        },
    )


@pytest.mark.parametrize(
    "artifact_id,diagnosis",
    [
        ("gaussian-modred-hooh90", "held 1 internal coordinate"),
        ("orca-unconverged-optts", "did not converge"),
        ("pyscf-stretched-hess", "0.0185 Eh/Bohr"),
    ],
)
def test_a_structure_shown_not_to_be_stationary_has_no_free_energy(
    tmp_path, artifact_id, diagnosis
):
    with pytest.raises(ContractError) as refused:
        _derive(_host(tmp_path), artifact_id)
    message = str(refused.value)
    assert "free_energy_needs_a_stationary_point" in message
    assert diagnosis in message
    # The refusal names what stays readable and the route a free energy has.
    assert "stay readable" in message
    assert "reach a stationary point of the same surface" in message


@pytest.mark.parametrize(
    "artifact_id,stated",
    [
        ("pyscf-water-hess", "stationary point: the largest gradient"),
        ("gaussian-nh3-opt-freq", "stationary point: the gaussian opt search"),
        ("orca-h-atom", "stationary point: one atom"),
        ("xtb-acetaldehyde-hess", "stationarity unmeasured"),
    ],
)
def test_every_free_energy_says_what_it_stands_on(
    tmp_path, artifact_id, stated
):
    receipt = _derive(_host(tmp_path), artifact_id)
    assert any(
        line.startswith(stated) for line in receipt.assumptions
    ), receipt.assumptions


@pytest.mark.capability("tool:characterise_stationary_point")
@pytest.mark.parametrize(
    "artifact_id",
    [
        "gaussian-modred-hooh90",
        "orca-unconverged-optts",
        "pyscf-stretched-hess",
    ],
)
def test_an_order_is_refused_where_a_free_energy_is(artifact_id):
    """One question, one function: the characterisation asked only the
    gradient, so it certified the unconverged po3-r19 saddle search as a
    first-order saddle and would certify a held structure's order."""

    from chemsmart.agent.execution import (
        build_stationary_point_characterisation,
    )
    from chemsmart.agent.terminal_states import (
        consequential_imaginary_mode_count,
    )

    program, path = RESULTS[artifact_id]
    resolved = path.resolve()
    output = reader_for(program).open_output(str(resolved))
    observed = consequential_imaginary_mode_count(
        tuple(float(value) for value in output.vibrational_frequencies)
    )
    with pytest.raises(ContractError) as refused:
        build_stationary_point_characterisation(
            result_artifact=TrustedArtifactRefV1(
                artifact_id=artifact_id,
                kind=reader_for(program).artifact_kind,
                sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
                size_bytes=resolved.stat().st_size,
                path=str(resolved),
                cli_value=str(resolved),
            ),
            program=program,
            order_claimed=observed,
        )
    report = getattr(refused.value, "failure_report", {})
    assert report.get("gate") == "result.order_needs_a_stationary_point"
    assert "not a stationary point" in report["diagnosis"]


@pytest.mark.capability("tool:evaluate_quantity_expression")
@pytest.mark.parametrize(
    "artifact_id,control",
    [("pyscf-stretched-hess", False), ("pyscf-water-hess", True)],
)
def test_a_zero_point_energy_rebuilt_by_hand_says_what_its_modes_are(
    tmp_path, artifact_id, control
):
    """The door beside the refusal: the same modes, extracted and summed by
    harmonic_zero_point_energy, are named as the curvature of a structure
    that is not stationary -- and a stationary Hessian stays silent."""

    import json

    host = _host(tmp_path)
    extraction = host._extract_result_quantities(
        "turn-1",
        {
            "program": "pyscf",
            "artifact_id": artifact_id,
            "selectors": [
                {"quantity_id": "e", "selector": "energy"},
                {"quantity_id": "nu", "selector": "vibrational_frequencies"},
            ],
        },
    )
    host._evaluate_quantity_expression(
        "turn-2",
        {
            "expression_id": "e0-by-hand",
            "inputs": [
                {
                    "input_id": name,
                    "receipt_sha256": extraction.receipt_sha256,
                    "quantity_id": name,
                }
                for name in ("e", "nu")
            ],
            "nodes": [
                {
                    "node_id": "zpe",
                    "operation": "harmonic_zero_point_energy",
                    "input_ids": ["nu"],
                },
                {
                    "node_id": "e0",
                    "operation": "add",
                    "input_ids": ["e", "zpe"],
                },
            ],
            "output_node_ids": ["e0"],
        },
    )
    events = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    observations = [
        item
        for event in events
        if event.get("kind") == "quantity_expression_evaluated"
        for item in event["payload"].get("level_observations") or ()
        if item.get("kind")
        == "vibrational_energy_of_a_structure_not_stationary"
    ]
    if control:
        assert not observations
    else:
        assert len(observations) == 1
        assert "0.0185 Eh/Bohr" in observations[0]["meaning"]


def test_the_gate_is_wired_where_it_is_raised():
    """The ladder read raisers from the agent layer only, so a gate the
    analysis plane raises read as declared and unwired."""

    from chemsmart.agent.capability_registry import build_capability_registry

    wired = {
        record.id: record.wired_by
        for record in build_capability_registry()
        if record.kind == "gate"
    }
    assert "result_quantities.py" in (
        wired["thermochemistry.free_energy_needs_a_stationary_point"]
    )
