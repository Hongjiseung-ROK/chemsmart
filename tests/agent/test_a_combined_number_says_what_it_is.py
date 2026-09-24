"""A combined number says what it is, beyond its unit.

Dimensional analysis let three things through that mean nothing, and the
archive holds each (R10 Q21 census over 1,381 expressions):

- ``min`` over PySCF's internal, external and real -> complex stability
  eigenvalues -- eigenvalues of three different matrices -- claimed as
  "the lowest eigenvalue", and a spread of two eigenvalues read in the
  session's prose as "~3.2 kcal/mol" (R10 Q13 dans);
- ``[E(OH) - E(O) - E(H)] - ZPE(OH)``, OH's electronic energy at +1 and
  its own zero-point energy at -1, delivered as a D0 of -105.90 kcal/mol
  (R10 Q14 G2 cycle 3);
- and every energy difference whose direction -- which species were the
  reactants -- nobody stated: 20 of 58 archived ax41 bond and binding
  energy claims are negative.

The expression handler now reads each operand's kind from the vocabulary
(``ENERGY_KINDS``) and its species from the result, and says what each
output is. Observations, never refusals. Driven through the host's own
extraction and expression handlers on archived ORCA and PySCF output.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1
from chemsmart.analysis.result_readers import reader_for

pytestmark = pytest.mark.capability("tool:evaluate_quantity_expression")

_DATA = Path(__file__).resolve().parents[1] / "data"
RESULTS = {
    "water": ("orca", _DATA / "ORCATests/outputs/water_opt.out"),
    "hydroxyl": (
        "orca",
        _DATA / "ORCATests/outputs/orca_hydroxyl_hirshfeld_gas_phase.out",
    ),
    "hydrogen": ("orca", _DATA / "ORCATests/atoms/h_atom_opt_freq_b3lyp.out"),
    "o2-singlet": (
        "pyscf",
        _DATA
        / "PySCFTests/outputs/o2_singlet_sp_stability_heard"
        / "o2_singlet_sp_stability_heard_gas_phase.h5",
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
    event_path = tmp_path / "events.jsonl"
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(event_path, session_id="s"),
        artifacts=artifacts,
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )
    return host, event_path


def _extract(host, artifact_id, selectors):
    return host._extract_result_quantities(
        "turn-1",
        {
            "program": RESULTS[artifact_id][0],
            "artifact_id": artifact_id,
            "selectors": [
                {"quantity_id": quantity_id, "selector": selector}
                for quantity_id, selector in selectors
            ],
        },
    )


def _evaluate(host, event_path, inputs, nodes, outputs):
    host._evaluate_quantity_expression(
        "turn-2",
        {
            "expression_id": "combination",
            "inputs": [
                {
                    "input_id": input_id,
                    "receipt_sha256": receipt.receipt_sha256,
                    "quantity_id": quantity_id,
                }
                for input_id, (receipt, quantity_id) in inputs.items()
            ],
            "nodes": nodes,
            "output_node_ids": outputs,
        },
    )
    events = [
        json.loads(line)
        for line in event_path.read_text().splitlines()
        if line.strip()
    ]
    event = [
        item
        for item in events
        if item.get("kind") == "quantity_expression_evaluated"
    ][-1]
    return [
        item
        for item in event["payload"].get("level_observations") or ()
        if item.get("kind")
        in {
            "output_is_an_orbital_rotation_curvature",
            "orbital_energy_combined_with_a_state_energy",
            "one_species_at_two_coefficients",
            "reaction_the_output_measures",
        }
    ]


def _bond_energy(tmp_path, zpe_sign):
    host, event_path = _host(tmp_path)
    water = _extract(
        host, "water", [("e", "energy"), ("nu", "vibrational_frequencies")]
    )
    hydroxyl = _extract(host, "hydroxyl", [("e", "energy")])
    hydrogen = _extract(host, "hydrogen", [("e", "energy")])
    return _evaluate(
        host,
        event_path,
        {
            "e-h2o": (water, "e"),
            "nu-h2o": (water, "nu"),
            "e-oh": (hydroxyl, "e"),
            "e-h": (hydrogen, "e"),
        },
        [
            {
                "node_id": "fragments",
                "operation": "add",
                "input_ids": ["e-oh", "e-h"],
            },
            {
                "node_id": "de",
                "operation": "subtract",
                "input_ids": ["fragments", "e-h2o"],
            },
            {
                "node_id": "zpe",
                "operation": "harmonic_zero_point_energy",
                "input_ids": ["nu-h2o"],
            },
            {
                "node_id": "d0",
                "operation": "add" if zpe_sign > 0 else "subtract",
                "input_ids": ["de", "zpe"],
            },
        ],
        ["de", "d0"],
    )


def test_a_species_whose_own_layers_disagree_is_named(tmp_path):
    # The Q14 G2 pattern on archived output: water's electronic energy
    # enters at -1 and its own zero-point energy at +1.
    observations = _bond_energy(tmp_path, zpe_sign=+1)
    named = [
        item
        for item in observations
        if item["kind"] == "one_species_at_two_coefficients"
    ]
    assert [item["output_id"] for item in named] == ["d0"]
    assert named[0]["species"] == "H2O"
    assert named[0]["layers"] == {"electronic": -1.0, "zero_point": 1.0}
    assert "no reaction" in named[0]["meaning"]


def test_a_consistent_combination_states_its_reaction(tmp_path):
    observations = _bond_energy(tmp_path, zpe_sign=-1)
    assert not [
        item
        for item in observations
        if item["kind"] == "one_species_at_two_coefficients"
    ]
    reactions = {
        item["output_id"]: item
        for item in observations
        if item["kind"] == "reaction_the_output_measures"
    }
    assert reactions["de"]["reaction"] == "H2O -> H + HO"
    assert reactions["de"]["atoms_balance"] is True
    assert reactions["d0"]["reaction"] == "H2O -> H + HO"
    # Water enters as E0; the atom and the radical as E -- stated, not
    # judged (an atom has no zero-point energy; the radical's is missing).
    assert reactions["d0"]["treatments"]["H2O"].startswith("E0")
    assert reactions["d0"]["treatments"]["HO"] == "E"


def test_stability_eigenvalues_are_curvatures_of_their_own_matrices(tmp_path):
    host, event_path = _host(tmp_path)
    stability = _extract(
        host,
        "o2-singlet",
        [
            ("internal", "scf_stability_internal_lowest_eigenvalue"),
            ("external", "scf_stability_external_lowest_eigenvalue"),
            ("complex", "scf_stability_real_to_complex_lowest_eigenvalue"),
        ],
    )
    observations = _evaluate(
        host,
        event_path,
        {
            "internal": (stability, "internal"),
            "external": (stability, "external"),
            "complex": (stability, "complex"),
        },
        [
            {
                "node_id": "lowest",
                "operation": "min",
                "input_ids": ["internal", "external", "complex"],
            },
            {
                "node_id": "external-kcal",
                "operation": "convert",
                "input_ids": ["external"],
                "target_unit": "kcal/mol",
            },
        ],
        ["lowest", "external-kcal"],
    )
    by_output = {item["output_id"]: item for item in observations}
    lowest = by_output["lowest"]
    assert lowest["kind"] == "output_is_an_orbital_rotation_curvature"
    assert len(lowest["normalisations"]) == 3
    assert lowest["magnitudes_comparable"] is False
    assert "signs compare" in lowest["meaning"]
    converted = by_output["external-kcal"]
    assert converted["magnitudes_comparable"] is True
    assert "never a kcal/mol of anything" in converted["meaning"]


def test_an_orbital_energy_beside_a_state_energy_is_named(tmp_path):
    host, event_path = _host(tmp_path)
    hydroxyl = _extract(host, "hydroxyl", [("e", "energy"), ("h", "homo")])
    observations = _evaluate(
        host,
        event_path,
        {"e": (hydroxyl, "e"), "h": (hydroxyl, "h")},
        [
            {
                "node_id": "mixed",
                "operation": "subtract",
                "input_ids": ["e", "h"],
            }
        ],
        ["mixed"],
    )
    assert [item["kind"] for item in observations] == [
        "orbital_energy_combined_with_a_state_energy"
    ]


def test_every_energy_names_its_kind():
    """A kind is declared once, in the vocabulary, for every number the
    host serves in energy: a selector a reader declares in hartree, and
    every energy a thermochemistry receipt writes. One arriving without
    a kind would pass every check by its unit alone."""

    from chemsmart.analysis.result_quantities import (
        DERIVABLE_THERMOCHEMISTRY_QUANTITIES,
        ENERGY,
        ENERGY_KINDS,
        QUASI_HARMONIC_COUNTERPARTS,
        supported_selectors,
    )
    from chemsmart.analysis.result_readers import selector_dimension

    energy_selectors = {
        selector
        for selector in supported_selectors()
        if selector_dimension(selector) == ENERGY
    }
    harmonic_energies = {
        name
        for name in DERIVABLE_THERMOCHEMISTRY_QUANTITIES
        if name
        not in {
            "entropy",
            "heat_capacity_cv",
            "near_zero_mode_count",
            "pressure",
            "temperature",
        }
    }
    counterparts = {
        counterpart
        for harmonic, (counterpart, _needs) in (
            QUASI_HARMONIC_COUNTERPARTS.items()
        )
        if harmonic in harmonic_energies
    }
    thermochemistry = harmonic_energies | counterparts
    unkinded = sorted((energy_selectors | thermochemistry) - set(ENERGY_KINDS))
    assert not unkinded, unkinded
    stale = sorted(set(ENERGY_KINDS) - energy_selectors - thermochemistry)
    assert not stale, stale
