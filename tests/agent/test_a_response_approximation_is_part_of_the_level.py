"""Two excitations from two response approximations are named where they meet.

The Tamm-Dancoff approximation and full linear-response TD-DFT are two
approximations of one root: on acrolein (PBE0/def2-SVP, CUHK Slurm 2150076)
TDA lies 0.026 eV above full TD-DFT for the n->pi* S1 and 0.44 eV above it
for the bright pi->pi* S2.  A typed excitation energy carries its unit and
dimension and nothing else, so before R10 Q8 an operation subtracting a TDA
root from a full TD-DFT root returned a number with no word: the level
identity held method, basis, dispersion, solvation and frozen core, and
ORCA's level did not even state the response it ran.

The response is compared only between excited-root operands: an SCF energy
read from a TDA run and one read from a full TD-DFT run are the same SCF,
and telling a session otherwise would be a false word.

Real Gaussian 16 C.02 and ORCA 6.1.1 outputs of one request per response
(tests/data/{GaussianTests/tddft,ORCATests/excited_states}), driven through
the host's own extraction and expression handlers.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1
from chemsmart.analysis.result_readers import reader_for

pytestmark = [pytest.mark.capability("tool:evaluate_quantity_expression")]

_DATA = Path(__file__).resolve().parents[1] / "data"
_RUNS = {
    ("gaussian", "tda"): _DATA
    / "GaussianTests/tddft/acrolein_pbe0_def2svp_tda_singlet6.log",
    ("gaussian", "tddft"): _DATA
    / "GaussianTests/tddft/acrolein_pbe0_def2svp_td_singlet6.log",
    ("orca", "tda"): _DATA
    / "ORCATests/excited_states/acrolein_pbe0_def2svp_tda_singlet6.out",
    ("orca", "tddft"): _DATA
    / "ORCATests/excited_states/acrolein_pbe0_def2svp_td_singlet6.out",
}


def _artifact(program, response):
    resolved = _RUNS[(program, response)].resolve()
    return TrustedArtifactRefV1(
        artifact_id=f"{program}-{response}",
        kind=reader_for(program).artifact_kind,
        sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )


def _difference(tmp_path, first, second, selector):
    """``first[0] - second[0]`` of one selector through the host's handlers."""

    from chemsmart.agent.runtime.event_store import RuntimeEventStore
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    artifacts = {
        key: _artifact(*key) for key in dict.fromkeys((first, second))
    }
    event_path = tmp_path / "events.jsonl"
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(event_path, session_id="q8"),
        artifacts={item.artifact_id: item for item in artifacts.values()},
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )
    receipts = {}
    for key, artifact in artifacts.items():
        receipts[key] = host._extract_result_quantities(
            "turn-1",
            {
                "program": key[0],
                "artifact_id": artifact.artifact_id,
                "selectors": [{"quantity_id": "v", "selector": selector}],
            },
        )
    scalar = selector != "scf_energy"
    nodes = []
    for name, key in (("a", first), ("b", second)):
        if scalar:
            nodes.append(
                {
                    "node_id": f"{name}0",
                    "operation": "ref",
                    "reference": name,
                    "indices": [0],
                }
            )
    nodes.append(
        {
            "node_id": "delta",
            "operation": "subtract",
            "input_ids": ["a0", "b0"] if scalar else ["a", "b"],
        }
    )
    host._evaluate_quantity_expression(
        "turn-2",
        {
            "expression_id": "response-difference",
            "inputs": [
                {
                    "input_id": name,
                    "receipt_sha256": receipts[key].receipt_sha256,
                    "quantity_id": "v",
                }
                for name, key in (("a", first), ("b", second))
            ],
            "nodes": nodes,
            "output_node_ids": ["delta"],
        },
    )
    events = [
        json.loads(line)
        for line in event_path.read_text().splitlines()
        if line.strip()
    ]
    return receipts, json.dumps(events)


@pytest.mark.capability("selector:orca:td:excitation_energies")
def test_an_orca_result_states_the_response_it_applied():
    reader = reader_for("orca")
    for response in ("tda", "tddft"):
        output = reader.open_output(_RUNS[("orca", response)])
        level = dict(reader.level_for_output(output))
        assert (
            level["response_method"],
            level["state_manifold"],
            level["nstates"],
        ) == (response, "singlet", 6)


@pytest.mark.capability("selector:gaussian:td:excitation_energies")
@pytest.mark.capability("selector:orca:td:excitation_energies")
def test_a_tda_root_minus_a_full_response_root_is_named(tmp_path):
    _, text = _difference(
        tmp_path, ("gaussian", "tda"), ("orca", "tddft"), "excitation_energies"
    )
    assert "operands_at_different_levels" in text
    assert '"response_method"' in text


@pytest.mark.capability("selector:gaussian:td:excitation_energies")
@pytest.mark.capability("selector:orca:td:excitation_energies")
def test_one_response_in_two_programs_combines_without_a_word(tmp_path):
    _, text = _difference(
        tmp_path,
        ("gaussian", "tddft"),
        ("orca", "tddft"),
        "excitation_energies",
    )
    assert "operands_at_different_levels" not in text


@pytest.mark.capability("selector:orca:td:scf_energy")
def test_the_reference_beneath_two_responses_is_one_level(tmp_path):
    """The SCF of a TDA run and of a full TD-DFT run is one SCF."""

    _, text = _difference(
        tmp_path, ("orca", "tda"), ("orca", "tddft"), "scf_energy"
    )
    assert "operands_at_different_levels" not in text
