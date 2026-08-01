from __future__ import annotations

import hashlib
import json

from chemsmart.agent.command_workflow import (
    ArtifactBinding,
    CommandNode,
    CommandWorkflowCompiler,
    CommandWorkflowSpec,
    CompilationContext,
    ResolvedArtifact,
)
from chemsmart.agent.harness.command_semantics import (
    CommandSemanticResult,
    evaluate_command_semantics,
)
from chemsmart.agent.harness.command_workflow_receipt import (
    COMMAND_WORKFLOW_RECEIPT_SCHEMA_VERSION,
    build_command_workflow_receipt,
)
from chemsmart.agent.harness.intent import IntentSpec, evaluate_intent


WATER_XYZ = "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n"


def test_preview_receipt_binds_safe_evidence_without_paths_or_raw_input(
    tmp_path,
) -> None:
    compilation, workflow = _compiled_xtb_workflow(tmp_path)
    invocation = compilation.invocations[0]
    semantic = evaluate_command_semantics(invocation.display_command, cwd=tmp_path)
    intent = evaluate_intent(
        invocation.display_command,
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

    receipt = build_command_workflow_receipt(
        workflow,
        compilation,
        safe_preview_results={"xtb-opt": semantic},
        intent_results={"xtb-opt": intent},
        parser_cwd=str(tmp_path),
    )
    serialized = json.dumps(receipt.to_dict(), sort_keys=True)

    assert semantic.verdict == "ok", semantic.to_dict()
    assert receipt.schema_version == COMMAND_WORKFLOW_RECEIPT_SCHEMA_VERSION
    assert receipt.status == "previewed"
    assert receipt.invocations[0].status == "previewed"
    assert receipt.invocations[0].safe_preview.mode == "run_fake_no_scratch"
    assert receipt.invocations[0].safe_preview.generated_artifacts
    assert len(
        receipt.invocations[0].safe_preview.generated_artifact_observations_sha256
    ) == 64
    assert str(tmp_path) not in serialized
    assert invocation.display_command not in serialized
    assert "water.xyz" not in serialized
    assert "content_tail" not in serialized
    assert '"route"' not in serialized
    assert '"executed"' not in serialized
    assert '"reproduced"' not in serialized


def test_unavailable_dependent_artifact_stays_planned_without_preview_claim(
    tmp_path,
) -> None:
    water = tmp_path / "water.xyz"
    water.write_text(WATER_XYZ, encoding="utf-8")
    water_hash = _sha256_file(water)
    compiler = CommandWorkflowCompiler()
    source_binding = ArtifactBinding(
        artifact_id="water-geometry",
        sha256=water_hash,
        kind="xyz_geometry",
        target_parameter="filename",
    )
    future_binding = ArtifactBinding(
        artifact_id="optimized-geometry",
        sha256="f" * 64,
        kind="xyz_geometry",
        target_parameter="filename",
        producer_node_id="source-sp",
    )
    workflow = CommandWorkflowSpec(
        workflow_id="planned-chain",
        task_spec_id="task-planned",
        cli_schema_digest=compiler.schema_digest,
        nodes=(
            CommandNode(
                node_id="source-sp",
                command_path=("run", "xtb", "sp"),
                input_artifacts=(source_binding,),
                charge=0,
                multiplicity=1,
                expected_artifact_classes=("xyz_geometry",),
            ),
            CommandNode(
                node_id="dependent-opt",
                command_path=("run", "xtb", "opt"),
                input_artifacts=(future_binding,),
                charge=0,
                multiplicity=1,
                dependencies=("source-sp",),
            ),
        ),
    )
    compilation = compiler.compile(
        workflow,
        CompilationContext(
            workspace_root=tmp_path,
            environment_digest="e" * 64,
            artifacts={
                "water-geometry": ResolvedArtifact(
                    artifact_id="water-geometry",
                    sha256=water_hash,
                    kind="xyz_geometry",
                    path=water,
                )
            },
        ),
    )

    receipt = build_command_workflow_receipt(workflow, compilation)

    assert compilation.status == "planned"
    assert receipt.status == "planned"
    assert all(node.status == "planned" for node in receipt.invocations)
    assert "executed" not in json.dumps(receipt.to_dict(), sort_keys=True)


def test_preview_receipt_redacts_raw_safe_runtime_evidence(tmp_path) -> None:
    compilation, workflow = _compiled_xtb_workflow(tmp_path)
    invocation = compilation.invocations[0]
    intent = evaluate_intent(
        invocation.display_command,
        IntentSpec(action="run", program="xtb", kind="xtb.opt"),
        cwd=str(tmp_path),
    )
    semantic = CommandSemanticResult(
        verdict="ok",
        command=invocation.display_command,
        checked_argv=(
            "/private/python",
            "-m",
            "chemsmart.cli.main",
            "run",
            "--fake",
            "--no-scratch",
            "/private/water.xyz",
        ),
        generated_inputs=(
            {
                "path": "/private/generated/sensitive.com",
                "route": "#p B3LYP credential=not-a-receipt-field",
                "content_tail": "native input and private-marker text",
                "charge": 0,
                "multiplicity": 1,
                "element_counts": {"O": 1, "H": 2},
            },
        ),
        stdout_tail="/private/output private-marker",
        stderr_tail="/private/error",
    )

    receipt = build_command_workflow_receipt(
        workflow,
        compilation,
        safe_preview_results={"xtb-opt": semantic},
        intent_results={"xtb-opt": intent},
        parser_cwd=str(tmp_path),
    )
    serialized = json.dumps(receipt.to_dict(), sort_keys=True)

    assert receipt.status == "previewed"
    assert "/private" not in serialized
    assert "private-marker" not in serialized
    assert "native input" not in serialized
    assert '"path"' not in serialized
    assert '"route"' not in serialized
    assert receipt.invocations[0].safe_preview.generated_artifacts[0].route_sha256


def _compiled_xtb_workflow(tmp_path):
    water = tmp_path / "water.xyz"
    water.write_text(WATER_XYZ, encoding="utf-8")
    water_hash = _sha256_file(water)
    compiler = CommandWorkflowCompiler()
    binding = ArtifactBinding(
        artifact_id="water-geometry",
        sha256=water_hash,
        kind="xyz_geometry",
        target_parameter="filename",
    )
    workflow = CommandWorkflowSpec(
        workflow_id="water-xtb-opt",
        task_spec_id="task-water-opt",
        cli_schema_digest=compiler.schema_digest,
        nodes=(
            CommandNode(
                node_id="xtb-opt",
                command_path=("run", "xtb", "opt"),
                parameters={"gfn_version": "gfn2"},
                input_artifacts=(binding,),
                charge=0,
                multiplicity=1,
            ),
        ),
    )
    compilation = compiler.compile(
        workflow,
        CompilationContext(
            workspace_root=tmp_path,
            environment_digest="e" * 64,
            artifacts={
                "water-geometry": ResolvedArtifact(
                    artifact_id="water-geometry",
                    sha256=water_hash,
                    kind="xyz_geometry",
                    path=water,
                )
            },
        ),
    )
    assert compilation.status == "previewable", compilation.model_dump()
    return compilation, workflow


def _sha256_file(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
