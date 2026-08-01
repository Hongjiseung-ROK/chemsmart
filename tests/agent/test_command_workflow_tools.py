from __future__ import annotations

import json

from chemsmart.agent.command_workflow import CommandWorkflowCompiler
from chemsmart.agent.command_workflow_tools import repair_command, synthesize_command
from chemsmart.agent.scientific_task import ScientificTaskSpec, task_spec_sha256
from chemsmart.agent.registry import ToolRegistry
from chemsmart.agent.workspace_bindings import discover_workspace_bindings


WATER_XYZ = "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n"


def test_default_frontier_synthesis_schema_accepts_only_typed_ir() -> None:
    registry = ToolRegistry.default(groups=["synthesis"])
    synth = registry.get_tool("synthesize_command")
    repair = registry.get_tool("repair_command")

    assert synth is not None
    assert repair is not None
    parameters = synth.openai_tool_def()["function"]["parameters"]
    assert set(parameters["properties"]) == {"scientific_task", "workflow"}
    assert "request" not in parameters["properties"]
    assert "command" not in parameters["properties"]
    assert "$ref" not in json.dumps(parameters)
    assert registry.call("synthesize_command", {"request": "optimize water"})[
        "ok"
    ] is False
    repair_parameters = repair.openai_tool_def()["function"]["parameters"]
    assert {
        "prior_task_spec_sha256",
        "prior_receipt_sha256",
    }.issubset(repair_parameters["required"])
    assert "command" not in repair_parameters["properties"]


def test_typed_xtb_workflow_can_be_safely_previewed(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    water = tmp_path / "water.xyz"
    water.write_text(WATER_XYZ, encoding="utf-8")
    bindings = discover_workspace_bindings(tmp_path)
    geometry = bindings.public_inventory()["geometry_artifacts"][0]
    compiler = CommandWorkflowCompiler()
    task = {
        "task_spec_id": "water-opt-task",
        "molecule_id": "water",
        "geometry": {
            "frame_id": "water-frame-1",
            "artifact_id": geometry["artifact_id"],
            "sha256": geometry["sha256"],
            "ordered_geometry_sha256": geometry["ordered_geometry_sha256"],
        },
        "electronic_state": {"charge": 0, "multiplicity": 1},
        "requested_observable": "GFN2-xTB optimized geometry preview",
        "node_requirements": [
            {
                "node_id": "xtb-opt",
                "program": "xtb",
                "job_kind": "opt",
                "settings_source": "xtb_command",
                "method": "gfn2",
            }
        ],
    }
    workflow = {
        "workflow_id": "water-xtb-workflow",
        "task_spec_id": "water-opt-task",
        "cli_schema_digest": compiler.schema_digest,
        "nodes": [
            {
                "node_id": "xtb-opt",
                "command_path": "run/xtb/opt",
                "parameters": {"gfn_version": "gfn2"},
                "input_artifacts": [
                    {
                        "artifact_id": geometry["artifact_id"],
                        "sha256": geometry["sha256"],
                        "kind": "geometry.xyz",
                        "target_parameter": "filename",
                    }
                ],
                "charge": 0,
                "multiplicity": 1,
            }
        ],
    }

    result = synthesize_command(task, workflow)

    assert result["status"] == "previewed", result
    assert result["cli_grounded"] is True
    assert result["receipt"]["status"] == "previewed"
    assert result["receipt"]["task_spec_sha256"] == result["task_spec_sha256"]
    generated = result["receipt"]["invocations"][0]["safe_preview"][
        "generated_artifacts"
    ][0]
    assert generated["ordered_geometry_sha256"] == geometry[
        "ordered_geometry_sha256"
    ]
    assert generated["element_counts"] == {"H": 2, "O": 1}
    assert result["command"].startswith("chemsmart run xtb")
    assert "--fake" not in result["command"]
    assert "native_input" not in json.dumps(result)


def test_repair_rejects_changes_to_scientific_bindings() -> None:
    task = {
        "task_spec_id": "task-repair",
        "molecule_id": "water",
        "geometry": {
            "frame_id": "water-frame-1",
            "artifact_id": "geometry-water",
            "sha256": "a" * 64,
            "ordered_geometry_sha256": "b" * 64,
        },
        "electronic_state": {"charge": 0, "multiplicity": 1},
        "requested_observable": "xTB optimization preview",
        "node_requirements": [
            {
                "node_id": "xtb-opt",
                "program": "xtb",
                "job_kind": "opt",
                "settings_source": "xtb_command",
                "method": "gfn2",
            }
        ],
    }
    prior = {
        "workflow_id": "repair-workflow",
        "task_spec_id": "task-repair",
        "cli_schema_digest": "c" * 64,
        "nodes": [
            {
                "node_id": "xtb-opt",
                "command_path": "run/xtb/opt",
                "parameters": {"gfn_version": "gfn2"},
                "input_artifacts": [
                    {
                        "artifact_id": "geometry-water",
                        "sha256": "a" * 64,
                        "kind": "geometry.xyz",
                        "target_parameter": "filename",
                    }
                ],
                "charge": 0,
                "multiplicity": 1,
            }
        ],
    }
    candidate = json.loads(json.dumps(prior))
    candidate["nodes"][0]["charge"] = 1

    result = repair_command(
        task,
        prior,
        candidate,
        {
            "rule_id": "cmd.science.xtb.gfn_mismatch",
            "node_id": "xtb-opt",
            "failed_field": "gfn_version",
            "evidence_id": "ce-repair-test",
        },
        repair_attempt=1,
        prior_task_spec_sha256=task_spec_sha256(ScientificTaskSpec.model_validate(task)),
        prior_receipt_sha256="d" * 64,
    )

    assert result["status"] == "blocked"
    assert result["counterexamples"][0]["rule_id"] == (
        "cmd.repair.scientific_binding_changed"
    )


def test_repair_rejects_a_changed_scientific_task_digest() -> None:
    task = {
        "task_spec_id": "task-repair",
        "molecule_id": "water",
        "geometry": {
            "frame_id": "water-frame-1",
            "artifact_id": "geometry-water",
            "sha256": "a" * 64,
            "ordered_geometry_sha256": "b" * 64,
        },
        "electronic_state": {"charge": 0, "multiplicity": 1},
        "requested_observable": "xTB optimization preview",
        "node_requirements": [
            {
                "node_id": "xtb-opt",
                "program": "xtb",
                "job_kind": "opt",
                "settings_source": "xtb_command",
                "method": "gfn2",
            }
        ],
    }
    workflow = {
        "workflow_id": "repair-workflow",
        "task_spec_id": "task-repair",
        "cli_schema_digest": "c" * 64,
        "nodes": [
            {
                "node_id": "xtb-opt",
                "command_path": "run/xtb/opt",
                "parameters": {"gfn_version": "gfn2"},
                "input_artifacts": [
                    {
                        "artifact_id": "geometry-water",
                        "sha256": "a" * 64,
                        "kind": "geometry.xyz",
                        "target_parameter": "filename",
                    }
                ],
                "charge": 0,
                "multiplicity": 1,
            }
        ],
    }

    result = repair_command(
        task,
        workflow,
        workflow,
        {
            "rule_id": "cmd.science.xtb.gfn_mismatch",
            "node_id": "xtb-opt",
            "failed_field": "gfn_version",
            "evidence_id": "ce-repair-test",
        },
        repair_attempt=1,
        prior_task_spec_sha256="f" * 64,
        prior_receipt_sha256="d" * 64,
    )

    assert result["status"] == "blocked"
    assert result["counterexamples"][0]["rule_id"] == (
        "cmd.repair.scientific_task_changed"
    )
