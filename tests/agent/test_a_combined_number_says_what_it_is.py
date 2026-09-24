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

Within one formula the reaction cancels, so each number is also placed on
the geometry it belongs to (the structural state its selector declares):
a composite at one geometry says nothing more, while a thermal part beside
another geometry's energy -- R10 Q21 g1-hooh's approved plan built "G at
90 deg" as G(cis saddle) + E(held 90) - E(cis saddle) -- is named, with the
distance between the geometries and whether the energy's structure is
stationary at all.
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
    # Water at three geometries: the B3LYP minimum (its Hessian, and a
    # CCSD(T) single point handed that geometry), the MP2 minimum, and the
    # B3LYP minimum with one O-H stretched 0.02 A (not stationary).
    "dft-hess": (
        "pyscf",
        _DATA / "PySCFTests/outputs/water_hess/water_hess_gas_phase.h5",
    ),
    "ccsdt-on-dft": (
        "pyscf",
        _DATA
        / "PySCFTests/outputs/water_ccsdt_sp/water_ccsdt_sp_gas_phase.h5",
    ),
    "mp2-opt": (
        "pyscf",
        _DATA / "PySCFTests/outputs/water_mp2_opt/water_mp2_opt_gas_phase.h5",
    ),
    "stretched": (
        "pyscf",
        _DATA
        / "PySCFTests/outputs/water_stretched_hess"
        / "water_stretched_hess_gas_phase.h5",
    ),
    "hooh-scan": (
        "orca",
        _DATA / "ORCATests/outputs/hooh_relaxed_scan_excerpt.out",
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
        for item in event["payload"].get("kind_observations") or ()
        if item.get("kind")
        in {
            "output_is_an_orbital_rotation_curvature",
            "orbital_energy_combined_with_a_state_energy",
            "one_species_at_two_coefficients",
            "reaction_the_output_measures",
            "structures_of_one_composition",
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


def _one_composition(tmp_path, energy_of, thermal_of):
    """``E(energy_of) + [G(thermal_of) - E(thermal_of)]``, or, with no
    ``thermal_of``, ``E(energy_of) - E(dft-hess)``, and what the host said
    about the geometries entering it."""

    host, event_path = _host(tmp_path)
    energy = _extract(host, energy_of, [("e", "energy")])
    reference = _extract(host, thermal_of or "dft-hess", [("e", "energy")])
    inputs = {"e-high": (energy, "e"), "e-low": (reference, "e")}
    nodes = [
        {
            "node_id": "out",
            "operation": "subtract",
            "input_ids": ["e-high", "e-low"],
        }
    ]
    if thermal_of:
        thermochemistry = host._derive_thermochemistry(
            "turn-1",
            {
                "program": "pyscf",
                "artifact_id": thermal_of,
                "temperature_k": 298.15,
                "pressure_atm": 1.0,
            },
        )
        inputs["g-low"] = (thermochemistry, "gibbs_free_energy")
        nodes = [
            {
                "node_id": "correction",
                "operation": "subtract",
                "input_ids": ["g-low", "e-low"],
            },
            {
                "node_id": "out",
                "operation": "add",
                "input_ids": ["e-high", "correction"],
            },
        ]
    return [
        item
        for item in _evaluate(host, event_path, inputs, nodes, ["out"])
        if item["kind"] == "structures_of_one_composition"
    ]


def test_a_composite_at_one_geometry_is_one_structure(tmp_path):
    """CCSD(T) on the B3LYP minimum plus that minimum's own thermal
    correction: three numbers, two results, one geometry -- a composite,
    with nothing to say about structures."""

    assert _one_composition(tmp_path, "ccsdt-on-dft", "dft-hess") == []


@pytest.mark.parametrize(
    "energy_of,thermal_of,difference,not_stationary",
    [
        # One minimum located by two methods: the thermal part is the
        # other method's, at its own geometry.
        ("mp2-opt", "dft-hess", 0.014, False),
        # The g1-hooh shape: another structure's thermal correction beside
        # the energy of a structure that is not stationary.
        ("stretched", "dft-hess", 0.020, True),
    ],
)
def test_a_thermal_part_beside_another_geometry_is_named(
    tmp_path, energy_of, thermal_of, difference, not_stationary
):
    """R10 Q21 g1-hooh's first plan built "G at 90 deg" as G(cis saddle) +
    E(held 90) - E(cis saddle): a free energy of no state, which cancels at
    the formula and which only the geometries tell apart from a composite."""

    (observation,) = _one_composition(tmp_path, energy_of, thermal_of)
    stated = {
        item["operands"]: (item["coefficient"], item["layers"])
        for item in observation["structures"]
    }
    assert stated["e-high"] == (1.0, ["electronic"])
    assert stated["e-low, g-low"] == (
        1.0,
        ["zero_point", "thermal", "pV", "minus_TS"],
    )
    assert observation["borrowed_thermal_part"] is True
    assert observation["largest_geometry_difference_angstrom"] == (
        pytest.approx(difference, abs=1e-3)
    )
    meaning = observation["meaning"]
    assert "another geometry" in meaning
    assert ("free energy of no state" in meaning) is not_stationary
    assert ("0.0185 Eh/Bohr" in meaning) is not_stationary


def test_a_difference_between_two_geometries_says_so(tmp_path):
    (observation,) = _one_composition(tmp_path, "stretched", None)
    stated = {
        item["operands"]: (item["coefficient"], item["layers"])
        for item in observation["structures"]
    }
    assert stated == {
        "e-high": (1.0, ["electronic"]),
        "e-low": (-1.0, ["electronic"]),
    }
    assert observation["borrowed_thermal_part"] is False
    assert "no single layer" not in observation["meaning"]


def test_two_points_of_one_scan_are_two_structures(tmp_path):
    """An element of a scan's energies is one point of the scan: two of
    them are two structures, whose geometries the result's own positions
    (the last point) do not describe. Counted as one result, the
    difference cancelled and nothing was said."""

    host, event_path = _host(tmp_path)
    scan = _extract(host, "hooh-scan", [("e", "scan_energies")])
    (observation,) = [
        item
        for item in _evaluate(
            host,
            event_path,
            {"e": (scan, "e")},
            [
                {
                    "node_id": "first",
                    "operation": "ref",
                    "reference": "e",
                    "indices": [0],
                },
                {
                    "node_id": "last",
                    "operation": "ref",
                    "reference": "e",
                    "indices": [2],
                },
                {
                    "node_id": "out",
                    "operation": "subtract",
                    "input_ids": ["last", "first"],
                },
            ],
            ["out"],
        )
        if item["kind"] == "structures_of_one_composition"
    ]
    assert [
        (item["coefficient"], item["geometry_read"])
        for item in observation["structures"]
    ] == [(-1.0, False), (1.0, False)]
    assert "could not read which geometry" in observation["meaning"]
