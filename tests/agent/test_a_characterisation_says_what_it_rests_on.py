"""A Hessian's credit to its producer says what it rests on.

The goal driver credits a producer's stationary point to the consumer
whose printed modes describe the structure the producer handed it. Two
things were wrong with that credit on archived runs:

- ``surfaces_agree`` answers None when it cannot compare two surfaces,
  its own contract says a caller must not read None as agreement, and
  36 of the 37 archived credits were given on None with nothing on the
  record saying so (every ORCA, Gaussian and xTB pair; PySCF results
  written before surfaces were recorded).
- 12 of those credits went to producers whose consumer had moved the
  structure -- an ORCA scan's refined well, an optimisation
  re-optimised -- so the modes described the consumer's own structure.

The records here are the host's own evaluator output over archived real
bytes, driven through the organ the goal driver calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.driver import _analysis_delivery
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from tests.agent.test_a_hessian_characterises_only_its_own_surface import (
    _verified_record,
)

pytestmark = pytest.mark.capability("program_jobtype:pyscf:cpu:hess")

ORCA = Path(__file__).resolve().parents[1] / "data" / "ORCATests" / "outputs"


def _orca_record(name: str, node_id: str, jobtype: str) -> dict:
    path = ORCA / name
    artifact = TrustedArtifactRefV1(
        artifact_id=f"result.{name}",
        kind="orca_output",
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=str(path),
    )
    evaluation = CommandCompiledToolHostV1._evaluate_execution_outputs(
        program="orca",
        jobtype=jobtype,
        charge=0,
        multiplicity=1,
        expected_settings={"freq": True},
        output_artifacts=(artifact,),
        exit_status=0,
    )
    return {
        "node_id": node_id,
        "state": "valid" if evaluation.validated else "invalid",
        "jobtype": jobtype,
        "observations": dict(evaluation.observations),
        "output_artifacts": [{"sha256": artifact.sha256}],
    }


def _stream(tmp_path, producer: dict, consumer: dict) -> Path:
    rows = [
        {"kind": "program_result_verified", "payload": {"record": producer}},
        {"kind": "program_result_verified", "payload": {"record": consumer}},
        {
            "kind": "optimized_geometry_handed_off",
            "payload": {
                "status": "validated_handoff",
                "producer_node_id": producer["node_id"],
                "consumer_node_id": consumer["node_id"],
            },
        },
    ]
    path = tmp_path / "run.jsonl"
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    return path


def test_a_credit_on_surfaces_that_cannot_be_compared_says_so(tmp_path):
    producer = _verified_record("water_opt", "producer")
    consumer = _verified_record("water_hess", "consumer")
    delivery = _analysis_delivery(_stream(tmp_path, producer, consumer))

    # The credit stands, as it did ...
    assert producer["output_artifacts"][0]["sha256"] in set(
        delivery.characterised_artifact_sha256s
    )
    # ... and the comparison that was not made is on the record.
    assert delivery.surface_uncompared_characterisations == (
        ("producer", "consumer"),
    )
    assert delivery.surface_mismatched_characterisations == ()


def test_a_consumer_that_moved_the_structure_characterises_only_its_own(
    tmp_path,
):
    """An optimisation's printed modes belong to the structure it reached."""

    consumer = _orca_record("CO2.out", "consumer", "opt")
    assert consumer["state"] == "valid"
    assert consumer["observations"]["orca"]["vibrational_mode_count"] > 0
    producer = _verified_record("water_opt", "producer")
    delivery = _analysis_delivery(_stream(tmp_path, producer, consumer))

    assert producer["output_artifacts"][0]["sha256"] not in set(
        delivery.characterised_artifact_sha256s
    )
    assert delivery.surface_uncompared_characterisations == ()
