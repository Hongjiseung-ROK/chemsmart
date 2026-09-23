"""An operation combining free energies is told when their conventions differ.

A Gibbs energy in hartree carries its unit and its dimension, and the
arithmetic checked only those, so a Gibbs energy at 1 atm and one at
1 mol/L subtracted without a word -- RT ln 24.47 = 1.894 kcal/mol per
molecule at 298.15 K, measured by oracle O1 on ten molecules -- and so did
a harmonic and a quasi-harmonic one, or a program's printed value and the
host's. Each thermochemistry receipt already states its conditions; the
host now compares, per output, the conventions of the thermochemical
quantities it reads. It is an observation, never a refusal: a treatment
spread is a measurement worth making.

Real archived Gaussian 16 output, through the host's own derivation,
extraction and expression handlers.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1
from chemsmart.analysis.result_readers import reader_for

pytestmark = [
    pytest.mark.capability("tool:evaluate_quantity_expression"),
    pytest.mark.capability("tool:derive_thermochemistry"),
]

GAUSSIAN_CO2 = "tests/data/GaussianTests/outputs/co2.log"


def _host(tmp_path):
    from chemsmart.agent.runtime.event_store import RuntimeEventStore
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    resolved = Path(GAUSSIAN_CO2).resolve()
    artifact = TrustedArtifactRefV1(
        artifact_id="gaussian-co2",
        kind=reader_for("gaussian").artifact_kind,
        sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )
    event_path = tmp_path / "events.jsonl"
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(event_path, session_id="x1"),
        artifacts={artifact.artifact_id: artifact},
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )
    return host, event_path


def _derive(host, **controls):
    return host._derive_thermochemistry(
        "turn-1",
        {
            "program": "gaussian",
            "artifact_id": "gaussian-co2",
            "temperature_k": 298.15,
            "pressure_atm": 1.0,
            **controls,
        },
    )


def _difference(host, event_path, first, second):
    host._evaluate_quantity_expression(
        "turn-2",
        {
            "expression_id": "difference",
            "inputs": [
                {
                    "input_id": name,
                    "receipt_sha256": receipt.receipt_sha256,
                    "quantity_id": quantity,
                }
                for name, (receipt, quantity) in (
                    ("first", first),
                    ("second", second),
                )
            ],
            "nodes": [
                {
                    "node_id": "delta",
                    "operation": "subtract",
                    "input_ids": ["first", "second"],
                }
            ],
            "output_node_ids": ["delta"],
        },
    )
    events = [
        json.loads(line)
        for line in event_path.read_text().splitlines()
        if line.strip()
    ]
    return [
        event
        for event in events
        if event.get("kind") == "quantity_expression_evaluated"
    ][-1]


def test_two_standard_states_are_named_where_they_combine(tmp_path):
    host, event_path = _host(tmp_path)
    gas = _derive(host)
    solution = _derive(host, concentration_mol_l=1.0)
    event = _difference(
        host,
        event_path,
        (gas, "gibbs_free_energy"),
        (solution, "gibbs_free_energy"),
    )
    text = json.dumps(event)
    assert "operands_at_different_thermochemical_conventions" in text
    assert "standard_state" in text and "1 mol/L" in text


def test_a_harmonic_and_a_grimme_gibbs_energy_are_named(tmp_path):
    host, event_path = _host(tmp_path)
    grimme = _derive(host, entropy_method="grimme", entropy_cutoff_cm1=100.0)
    event = _difference(
        host,
        event_path,
        (grimme, "quasi_harmonic_gibbs_free_energy"),
        (grimme, "gibbs_free_energy"),
    )
    text = json.dumps(event)
    assert "operands_at_different_thermochemical_conventions" in text
    assert "grimme entropy" in text and "harmonic (RRHO)" in text


def test_a_printed_and_a_derived_gibbs_energy_are_named(tmp_path):
    host, event_path = _host(tmp_path)
    derived = _derive(host)
    printed = host._extract_result_quantities(
        "turn-1",
        {
            "program": "gaussian",
            "artifact_id": "gaussian-co2",
            "selectors": [
                {"quantity_id": "g", "selector": "gibbs_free_energy"}
            ],
        },
    )
    event = _difference(
        host, event_path, (printed, "g"), (derived, "gibbs_free_energy")
    )
    text = json.dumps(event)
    assert "operands_at_different_thermochemical_conventions" in text
    assert "printed by gaussian" in text and "host derivation" in text


def test_one_convention_combines_without_a_word(tmp_path):
    host, event_path = _host(tmp_path)
    gas = _derive(host)
    event = _difference(
        host,
        event_path,
        (gas, "gibbs_free_energy"),
        (gas, "electronic_energy"),
    )
    assert "thermochemical_conventions" not in json.dumps(event)


def test_a_printed_free_energy_says_whose_it_is(tmp_path):
    # Read alone, a program's printed free energy is still the program's
    # quantity: the extraction says which convention it carries.
    host, event_path = _host(tmp_path)
    host._extract_result_quantities(
        "turn-1",
        {
            "program": "gaussian",
            "artifact_id": "gaussian-co2",
            "selectors": [
                {"quantity_id": "g", "selector": "gibbs_free_energy"}
            ],
        },
    )
    events = [
        json.loads(line)
        for line in event_path.read_text().splitlines()
        if line.strip()
    ]
    extracted = [
        event
        for event in events
        if event.get("kind") == "result_quantities_extracted"
    ][-1]
    text = json.dumps(extracted)
    assert "printed_thermochemistry" in text
    assert "harmonic (RRHO)" in text
    assert "Gaussian's own rotational symmetry number" in text
