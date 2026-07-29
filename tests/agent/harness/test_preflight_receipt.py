from __future__ import annotations

import json

from chemsmart.agent.harness.command_semantics import (
    evaluate_command_semantics,
)
from chemsmart.agent.harness.intent import IntentSpec, evaluate_intent
from chemsmart.agent.harness.preflight_receipt import (
    COMMAND_PREFLIGHT_SCHEMA_VERSION,
    build_command_preflight_receipt,
)

WATER_XYZ = "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n"


def test_xtb_preflight_is_path_free_and_deterministic_without_project(
    tmp_path,
) -> None:
    molecule = tmp_path / "water.xyz"
    molecule.write_text(WATER_XYZ, encoding="utf-8")
    command = "chemsmart run xtb -f water.xyz -c 0 -m 1 -g gfn2 opt"
    semantic = evaluate_command_semantics(command, cwd=tmp_path)
    intent = evaluate_intent(
        command,
        IntentSpec(
            action="run",
            program="xtb",
            kind="xtb.opt",
            charge=0,
            multiplicity=1,
            execution_mode="local",
            chemistry={"gfn_version": "gfn2"},
        ),
        cwd=str(tmp_path),
    )

    first = build_command_preflight_receipt(
        command,
        semantic,
        intent,
        cwd=tmp_path,
    ).to_dict()
    second = build_command_preflight_receipt(
        command,
        semantic,
        intent,
        cwd=tmp_path,
    ).to_dict()

    assert semantic.verdict == "ok", semantic.to_dict()
    assert first == second
    assert first["schema_version"] == COMMAND_PREFLIGHT_SCHEMA_VERSION
    assert first["parser"] == {
        "verdict": "ok",
        "program": "xtb",
        "kind": "xtb.opt",
    }
    assert first["semantic_gate"]["verdict"] == "ok"
    assert first["intent_gate"]["verdict"] == "ok"
    assert first["normalized_spec"]["chemistry"] == {"gfn_version": "gfn2"}
    assert first["molecule"]["basename"] == "water.xyz"
    assert len(first["molecule"]["input_sha256"]) == 64
    assert first["expected_artifacts"] == (
        "xtb_output",
        "optimized_geometry",
    )
    encoded = json.dumps(first, sort_keys=True)
    assert str(tmp_path) not in encoded
    assert command not in encoded
    assert '"project"' not in encoded


def test_supplied_studio_molecule_identity_never_accepts_path_keys(
    tmp_path,
) -> None:
    (tmp_path / "water.xyz").write_text(WATER_XYZ, encoding="utf-8")
    command = "chemsmart run xtb -f water.xyz -c 0 -m 1 sp"
    semantic = evaluate_command_semantics(command, cwd=tmp_path)

    receipt = build_command_preflight_receipt(
        command,
        semantic,
        cwd=tmp_path,
        molecule_identity={
            "artifact_id": "artifact_123",
            "basename": "/not-exposed/current-molecule.xyz",
            "revision": 7,
            "geometry_hash": "abc123",
            "path": "/private/secret/current-molecule.xyz",
        },
    ).to_dict()

    assert receipt["molecule"]["artifact_id"] == "artifact_123"
    assert receipt["molecule"]["basename"] == "current-molecule.xyz"
    assert receipt["molecule"]["revision"] == 7
    assert "path" not in receipt["molecule"]
    assert "/private/secret" not in json.dumps(receipt)
