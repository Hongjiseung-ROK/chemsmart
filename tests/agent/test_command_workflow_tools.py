from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from chemsmart.agent.command_workflow import CommandNode, CommandWorkflowCompiler
from chemsmart.agent.command_workflow_tools import (
    inspect_command_workflow,
    repair_command,
    synthesize_command,
)
from chemsmart.agent.harness.command_semantics import CommandSemanticResult
from chemsmart.agent.scientific_task import (
    ConstraintBinding,
    ElectronicState,
    GeometryIdentity,
    NodeScientificRequirement,
    ScientificTaskSpec,
    _validate_generated_preview,
    _validate_xtb_job_controls,
    task_spec_sha256,
)
from chemsmart.agent.registry import ToolRegistry
from chemsmart.agent.workspace_bindings import discover_workspace_bindings


WATER_XYZ = "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n"


def _preview_task(*, method: str = "PBE") -> ScientificTaskSpec:
    return ScientificTaskSpec(
        task_spec_id="preview-task",
        molecule_id="water",
        geometry=GeometryIdentity(
            frame_id="frame-water",
            artifact_id="geometry-water",
            sha256="a" * 64,
            ordered_geometry_sha256="b" * 64,
        ),
        electronic_state=ElectronicState(charge=0, multiplicity=1),
        requested_observable="Gaussian single-point preview",
        node_requirements=(
            NodeScientificRequirement(
                node_id="gaussian-sp",
                program="gaussian",
                job_kind="sp",
                settings_source="project",
                method=method,
                basis_or_ecp="def2-SVP",
            ),
        ),
    )


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
    requirement_properties = parameters["properties"]["scientific_task"][
        "properties"
    ]["node_requirements"]["items"]["properties"]
    assert "optimization_level" in requirement_properties
    assert "gradient_required" in requirement_properties
    obligation_schema = parameters["properties"]["scientific_task"]["properties"][
        "post_execution_validation_obligations"
    ]
    assert obligation_schema["uniqueItems"] is True
    assert obligation_schema["items"]["pattern"] == "^[a-z][a-z0-9_]{0,127}$"


def test_preview_requires_one_artifact_satisfying_all_semantics() -> None:
    task = _preview_task()
    requirement = task.node_requirements[0]
    semantic = CommandSemanticResult(
        verdict="ok",
        command="chemsmart run gaussian sp",
        generated_inputs=(
            {
                "charge": 0,
                "multiplicity": 1,
                "ordered_geometry_sha256": "c" * 64,
                "route": "# PBE/def2-SVP sp",
            },
            {
                "charge": 1,
                "multiplicity": 2,
                "ordered_geometry_sha256": "b" * 64,
                "route": "# PBE/def2-SVP sp",
            },
        ),
    )
    findings = []

    _validate_generated_preview(
        task,
        "gaussian-sp",
        requirement,
        semantic,
        findings,
    )

    assert "cmd.science.preview.identity_split_across_artifacts" in {
        finding.rule_id for finding in findings
    }
    assert "cmd.science.preview.route_identity_unbound" in {
        finding.rule_id for finding in findings
    }


def test_preview_rejects_method_substring_match() -> None:
    task = _preview_task(method="PBE")
    semantic = CommandSemanticResult(
        verdict="ok",
        command="chemsmart run gaussian sp",
        generated_inputs=(
            {
                "charge": 0,
                "multiplicity": 1,
                "ordered_geometry_sha256": "b" * 64,
                "route": "# PBE0/def2-SVP sp",
            },
        ),
    )
    findings = []

    _validate_generated_preview(
        task,
        "gaussian-sp",
        task.node_requirements[0],
        semantic,
        findings,
    )

    assert any(
        finding.rule_id == "cmd.science.preview.route_setting_mismatch"
        and finding.failed_field == "method"
        for finding in findings
    )


def test_preview_accepts_realistic_gaussian_basis_and_solvent_atoms() -> None:
    task = _preview_task(method="PBE0")
    requirement = task.node_requirements[0].model_copy(
        update={
            "basis_or_ecp": "6-31+G(d,p)",
            "solvent_model": "SMD",
            "solvent_id": "Water",
        }
    )
    task = task.model_copy(update={"node_requirements": (requirement,)})
    semantic = CommandSemanticResult(
        verdict="ok",
        command="chemsmart run gaussian sp",
        generated_inputs=(
            {
                "charge": 0,
                "multiplicity": 1,
                "ordered_geometry_sha256": "b" * 64,
                "route": "# PBE0/6-31+G(d,p) SCRF=(SMD,Solvent=Water)",
            },
        ),
    )
    findings = []

    _validate_generated_preview(
        task,
        "gaussian-sp",
        requirement,
        semantic,
        findings,
    )

    assert findings == []


def test_preview_rejects_wrong_solvent_model_with_same_solvent_id() -> None:
    raw = _preview_task(method="PBE0").model_dump(mode="json")
    raw["node_requirements"][0].update(
        {"solvent_model": "SMD", "solvent_id": "Water"}
    )
    task = ScientificTaskSpec.model_validate(raw)
    semantic = CommandSemanticResult(
        verdict="ok",
        command="chemsmart run gaussian sp",
        generated_inputs=(
            {
                "charge": 0,
                "multiplicity": 1,
                "ordered_geometry_sha256": "b" * 64,
                "route": "# PBE0/def2-SVP SCRF=(CPCM,Solvent=Water)",
            },
        ),
    )
    findings = []

    _validate_generated_preview(
        task, "gaussian-sp", task.node_requirements[0], semantic, findings
    )

    assert any(
        item.failed_field == "solvent_model" for item in findings
    )


def test_preview_accepts_parenthetical_orca_method_atom() -> None:
    raw = _preview_task().model_dump(mode="json")
    raw["node_requirements"][0].update(
        {
            "program": "orca",
            "method": "DLPNO-CCSD(T)",
            "basis_or_ecp": "def2-TZVP",
        }
    )
    task = ScientificTaskSpec.model_validate(raw)
    semantic = CommandSemanticResult(
        verdict="ok",
        command="chemsmart run orca sp",
        generated_inputs=(
            {
                "charge": 0,
                "multiplicity": 1,
                "ordered_geometry_sha256": "b" * 64,
                "route": "! DLPNO-CCSD(T) def2-TZVP",
            },
        ),
    )
    findings = []

    _validate_generated_preview(
        task, "gaussian-sp", task.node_requirements[0], semantic, findings
    )

    assert findings == []


def test_preview_rejects_dropped_frequency_and_extra_generated_artifact() -> None:
    raw = _preview_task().model_dump(mode="json")
    raw["node_requirements"][0]["frequency_required"] = True
    task = ScientificTaskSpec.model_validate(raw)
    artifact = {
        "charge": 0,
        "multiplicity": 1,
        "ordered_geometry_sha256": "b" * 64,
        "route": "# PBE/def2-SVP opt",
    }
    semantic = CommandSemanticResult(
        verdict="ok",
        command="chemsmart run gaussian opt",
        generated_inputs=(artifact, dict(artifact)),
    )
    findings = []

    _validate_generated_preview(
        task, "gaussian-sp", task.node_requirements[0], semantic, findings
    )

    rule_ids = {item.rule_id for item in findings}
    assert "cmd.science.preview.generated_input_cardinality" in rule_ids
    assert any(
        item.failed_field == "frequency_required" for item in findings
    )


def test_scientific_requirement_rejects_program_inapplicable_controls() -> None:
    with pytest.raises(ValidationError, match="only defined for xTB"):
        NodeScientificRequirement(
            node_id="gaussian-sp",
            program="gaussian",
            job_kind="sp",
            settings_source="project",
            method="PBE0",
            basis_or_ecp="def2-SVP",
            gradient_required=True,
        )
    with pytest.raises(ValidationError, match="only valid for the opt"):
        NodeScientificRequirement(
            node_id="xtb-sp",
            program="xtb",
            job_kind="sp",
            settings_source="xtb_command",
            method="gfn2",
            optimization_level="tight",
        )


def test_xtb_controls_reject_undeclared_gradient_and_frequency_drift() -> None:
    node = CommandNode(
        node_id="xtb-hess",
        command_path="run/xtb/hess",
        parameters={"gfn_version": "gfn2", "grad": True},
        charge=0,
        multiplicity=1,
    )
    requirement = NodeScientificRequirement(
        node_id="xtb-hess",
        program="xtb",
        job_kind="hess",
        settings_source="xtb_command",
        method="gfn2",
        frequency_required=False,
    )
    findings = []

    _validate_xtb_job_controls(node, requirement, findings)

    assert {finding.rule_id for finding in findings} == {
        "cmd.science.method.frequency_mismatch",
        "cmd.science.xtb.gradient_mismatch",
    }


def test_xtb_omitted_gradient_is_effective_false() -> None:
    node = CommandNode(
        node_id="xtb-sp",
        command_path="run/xtb/sp",
        parameters={"gfn_version": "gfn2"},
        charge=0,
        multiplicity=1,
    )
    requirement = NodeScientificRequirement(
        node_id="xtb-sp",
        program="xtb",
        job_kind="sp",
        settings_source="xtb_command",
        method="gfn2",
        gradient_required=False,
    )
    findings = []

    _validate_xtb_job_controls(node, requirement, findings)

    assert findings == []


@pytest.mark.parametrize(
    ("required", "parameters", "expected_failure"),
    [
        (None, {"gfn_version": "gfn2"}, False),
        (None, {"gfn_version": "gfn2", "grad": False}, True),
        (False, {"gfn_version": "gfn2"}, False),
        (True, {"gfn_version": "gfn2"}, True),
    ],
)
def test_xtb_gradient_requirement_is_tristate(
    required, parameters, expected_failure
) -> None:
    node = CommandNode(
        node_id="xtb-sp",
        command_path="run/xtb/sp",
        parameters=parameters,
        charge=0,
        multiplicity=1,
    )
    requirement = NodeScientificRequirement(
        node_id="xtb-sp",
        program="xtb",
        job_kind="sp",
        settings_source="xtb_command",
        method="gfn2",
        gradient_required=required,
    )
    findings = []

    _validate_xtb_job_controls(node, requirement, findings)

    assert bool(findings) is expected_failure


def test_xtb_preview_binds_project_method_job_and_controls() -> None:
    task = ScientificTaskSpec(
        task_spec_id="xtb-hess-task",
        molecule_id="water",
        geometry=GeometryIdentity(
            frame_id="frame-water",
            artifact_id="geometry-water",
            sha256="a" * 64,
            ordered_geometry_sha256="b" * 64,
        ),
        electronic_state=ElectronicState(charge=0, multiplicity=1),
        requested_observable="project-backed xTB Hessian preview",
        node_requirements=(
            NodeScientificRequirement(
                node_id="xtb-hess",
                program="xtb",
                job_kind="hess",
                settings_source="project",
                method="gfn2",
                frequency_required=True,
                gradient_required=True,
            ),
        ),
    )
    semantic = CommandSemanticResult(
        verdict="ok",
        command="chemsmart run xtb hess",
        generated_inputs=(
            {
                "charge": 0,
                "multiplicity": 1,
                "ordered_geometry_sha256": "b" * 64,
                "route": "xtb water.xyz --gfn 1 --chrg 0 --uhf 0",
            },
        ),
    )
    findings = []

    _validate_generated_preview(
        task, "xtb-hess", task.node_requirements[0], semantic, findings
    )

    failed_fields = {item.failed_field for item in findings}
    assert {"method", "job_kind", "frequency_required", "gradient_required"}.issubset(
        failed_fields
    )


def test_equivalent_scientific_set_order_has_same_digest() -> None:
    base = _preview_task()
    constraints = (
        ConstraintBinding(
            constraint_id="constraint-b",
            kind="bond",
            definition_sha256="c" * 64,
        ),
        ConstraintBinding(
            constraint_id="constraint-a",
            kind="angle",
            definition_sha256="d" * 64,
        ),
    )
    first = base.model_copy(
        update={
            "constraints": constraints,
            "required_evidence": ("safe_preview", "cli_schema"),
            "post_execution_validation_obligations": (
                "optimization_converged",
                "exactly_one_imaginary_frequency",
            ),
        }
    )
    second = ScientificTaskSpec.model_validate(
        {
            **base.model_dump(mode="json"),
            "constraints": [
                item.model_dump(mode="json")
                for item in reversed(constraints)
            ],
            "required_evidence": ["cli_schema", "safe_preview"],
            "post_execution_validation_obligations": [
                "exactly_one_imaginary_frequency",
                "optimization_converged",
            ],
        }
    )

    first = ScientificTaskSpec.model_validate(first.model_dump(mode="json"))
    assert task_spec_sha256(first) == task_spec_sha256(second)


def test_post_execution_obligations_remain_pending_after_safe_preview(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    water = tmp_path / "water.xyz"
    water.write_text(WATER_XYZ, encoding="utf-8")
    bindings = discover_workspace_bindings(tmp_path)
    geometry = bindings.public_inventory()["geometry_artifacts"][0]
    compiler = CommandWorkflowCompiler()
    task = {
        "task_spec_id": "water-hess-task",
        "molecule_id": "water",
        "geometry": {
            "frame_id": "water-frame-1",
            "artifact_id": geometry["artifact_id"],
            "sha256": geometry["sha256"],
            "ordered_geometry_sha256": geometry["ordered_geometry_sha256"],
        },
        "electronic_state": {"charge": 0, "multiplicity": 1},
        "requested_observable": "xTB Hessian preview",
        "node_requirements": [
            {
                "node_id": "xtb-hess",
                "program": "xtb",
                "job_kind": "hess",
                "settings_source": "xtb_command",
                "method": "gfn2",
                "frequency_required": True,
                "gradient_required": True,
            }
        ],
        "required_evidence": ["safe_preview"],
        "post_execution_validation_obligations": [
            "optimization_converged",
            "exactly_one_imaginary_frequency",
        ],
    }
    workflow = {
        "workflow_id": "water-hess-workflow",
        "task_spec_id": "water-hess-task",
        "cli_schema_digest": compiler.schema_digest,
        "nodes": [
            {
                "node_id": "xtb-hess",
                "command_path": "run/xtb/hess",
                "parameters": {"gfn_version": "gfn2", "grad": True},
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
    expected = [
        "exactly_one_imaginary_frequency",
        "optimization_converged",
    ]
    assert result["scientific_task"][
        "post_execution_validation_obligations"
    ] == expected
    for stage in ("scientific_preflight", "scientific_preview"):
        assert result[stage]["scientific_identity"][
            "post_execution_validation_obligations"
        ] == expected
        assert result[stage]["post_execution_validation"] == {
            "status": "pending_execution",
            "satisfied_obligations": [],
        }


def test_post_execution_obligations_require_unique_safe_identifiers() -> None:
    base = _preview_task().model_dump(mode="json")

    with pytest.raises(ValidationError):
        ScientificTaskSpec.model_validate(
            {
                **base,
                "post_execution_validation_obligations": [
                    "optimization_converged",
                    "optimization_converged",
                ],
            }
        )
    with pytest.raises(ValidationError):
        ScientificTaskSpec.model_validate(
            {
                **base,
                "post_execution_validation_obligations": [
                    "frequency:exactly-one-imaginary-mode"
                ],
            }
        )


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


def test_project_backed_xtb_is_discovered_compiled_and_previewed(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    water = tmp_path / "water.xyz"
    water.write_text(WATER_XYZ, encoding="utf-8")
    project_dir = tmp_path / ".chemsmart" / "xtb"
    project_dir.mkdir(parents=True)
    (project_dir / "paper_xtb.yaml").write_text(
        """\
sp:
  gfn_version: gfn2
opt:
  gfn_version: gfn2
  optimization_level: tight
hess:
  gfn_version: gfn2
""",
        encoding="utf-8",
    )
    bindings = discover_workspace_bindings(tmp_path)
    inventory = bindings.public_inventory()
    geometry = inventory["geometry_artifacts"][0]
    project = inventory["project_artifacts"][0]
    assert project["program"] == "xtb"
    compiler = CommandWorkflowCompiler()
    task = {
        "task_spec_id": "project-xtb-task",
        "molecule_id": "water",
        "geometry": {
            "frame_id": "water-frame-1",
            "artifact_id": geometry["artifact_id"],
            "sha256": geometry["sha256"],
            "ordered_geometry_sha256": geometry["ordered_geometry_sha256"],
        },
        "electronic_state": {"charge": 0, "multiplicity": 1},
        "requested_observable": "project-backed GFN2-xTB optimized geometry",
        "node_requirements": [
            {
                "node_id": "xtb-opt",
                "program": "xtb",
                "job_kind": "opt",
                "settings_source": "project",
                "method": "gfn2",
                "optimization_level": "tight",
            }
        ],
    }
    workflow = {
        "workflow_id": "project-xtb-workflow",
        "task_spec_id": "project-xtb-task",
        "cli_schema_digest": compiler.schema_digest,
        "nodes": [
            {
                "node_id": "xtb-opt",
                "command_path": "run/xtb/opt",
                "project_ref": {
                    "project_id": project["project_id"],
                    "sha256": project["sha256"],
                },
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
    assert "--project paper_xtb" in result["command"]
    route = result["receipt"]["invocations"][0]["safe_preview"][
        "generated_artifacts"
    ][0]
    assert route["route_sha256"]

    overridden = json.loads(json.dumps(workflow))
    overridden["nodes"][0]["parameters"] = {"gfn_version": "gfn1"}
    rejected = inspect_command_workflow(task, overridden)
    assert rejected["status"] == "blocked"
    assert "cmd.ir.project_owned_setting" in {
        item["rule_id"] for item in rejected["counterexamples"]
    }


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
