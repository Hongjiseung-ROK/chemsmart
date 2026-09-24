"""An operation that combines numbers is told when their levels differ.

A typed value carries its unit and its dimension, and the arithmetic checked
only those, so an ORCA VWN5 B3LYP energy and a Gaussian B3LYP energy -- two
functionals, 0.037 Eh apart on this water -- subtracted without a word, and
so did a tight-binding energy and a hybrid-DFT one.  Each program's result
now states the level it computed with (the applied functional, the method,
the basis, the dispersion, the continuum, the frozen core) and the host
compares the producers of an expression's operands.  It is an observation,
never a refusal: a composite method mixes levels on purpose.

Real ORCA 6.1.1 and Gaussian 16 C.02 outputs (CUHK Slurm 2149277), driven
through the host's own extraction and expression handlers.
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
    pytest.mark.capability("selector:orca:sp:functional"),
]

ORCA_VWN5 = "tests/data/ORCATests/functional_forms/water_route_b3lyp_vwn5.out"
ORCA_VWN3 = "tests/data/ORCATests/functional_forms/water_route_b3lypg_vwn3.out"
GAUSSIAN = "tests/data/GaussianTests/functional_forms/water_b3lyp.log"


def _artifact(path, program, artifact_id):
    resolved = Path(path).resolve()
    return TrustedArtifactRefV1(
        artifact_id=artifact_id,
        kind=reader_for(program).artifact_kind,
        sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )


def _difference(tmp_path, orca_path):
    from chemsmart.agent.runtime.event_store import RuntimeEventStore
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    orca = _artifact(orca_path, "orca", "orca-water")
    gaussian = _artifact(GAUSSIAN, "gaussian", "gaussian-water")
    event_path = tmp_path / "events.jsonl"
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(event_path, session_id="x1"),
        artifacts={orca.artifact_id: orca, gaussian.artifact_id: gaussian},
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )
    receipts = {}
    for program, artifact in (("orca", orca), ("gaussian", gaussian)):
        receipts[program] = host._extract_result_quantities(
            "turn-1",
            {
                "program": program,
                "artifact_id": artifact.artifact_id,
                "selectors": [{"quantity_id": "e", "selector": "energy"}],
            },
        )
    host._evaluate_quantity_expression(
        "turn-2",
        {
            "expression_id": "program-difference",
            "inputs": [
                {
                    "input_id": program,
                    "receipt_sha256": receipt.receipt_sha256,
                    "quantity_id": "e",
                }
                for program, receipt in receipts.items()
            ],
            "nodes": [
                {
                    "node_id": "delta",
                    "operation": "subtract",
                    "input_ids": ["orca", "gaussian"],
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
    evaluated = [
        event
        for event in events
        if "level_observations" in json.dumps(event)
        or event.get("kind") == "quantity_expression_evaluated"
    ]
    return receipts, evaluated


def test_the_producers_state_the_functional_they_applied(tmp_path):
    receipts, _ = _difference(tmp_path, ORCA_VWN5)

    assert receipts["orca"].level["functional"] == "b3lyp5"
    assert receipts["gaussian"].level["functional"] == "b3lyp"


def test_two_functionals_under_one_word_are_named_where_they_combine(
    tmp_path,
):
    _, events = _difference(tmp_path, ORCA_VWN5)

    text = json.dumps(events)
    assert "operands_at_different_levels" in text
    assert "b3lyp5" in text and '"method"' in text


def test_one_functional_in_two_programs_combines_without_a_word(tmp_path):
    receipts, events = _difference(tmp_path, ORCA_VWN3)

    assert receipts["orca"].level["functional"] == "b3lyp"
    assert "operands_at_different_levels" not in json.dumps(events)
