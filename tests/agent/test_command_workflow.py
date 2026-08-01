from __future__ import annotations

import hashlib
import shlex

import pytest

from chemsmart.agent.cli_schema import build_chemsmart_cli_schema
from chemsmart.agent.command_workflow import (
    ArtifactBinding,
    CanonicalCommandInvocation,
    CommandNode,
    CommandWorkflowCompiler,
    CommandWorkflowSpec,
    CompilationContext,
    ProjectReference,
    ResolvedArtifact,
    ResolvedProject,
    cli_schema_digest,
    migrate_v8_compact_spec,
)


WATER_XYZ = "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n"
ENVIRONMENT_DIGEST = "e" * 64


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _schema_and_digest():
    schema = build_chemsmart_cli_schema()
    return schema, cli_schema_digest(schema)


def _water_binding(tmp_path) -> tuple[ArtifactBinding, ResolvedArtifact]:
    path = tmp_path / "water.xyz"
    path.write_text(WATER_XYZ, encoding="utf-8")
    digest = _sha256(path)
    binding = ArtifactBinding(
        artifact_id="geom-water",
        sha256=digest,
        kind="geometry.xyz",
        target_parameter="filename",
    )
    return binding, ResolvedArtifact(
        artifact_id="geom-water",
        sha256=digest,
        kind="geometry.xyz",
        path=path,
    )


def _context(tmp_path, *artifacts, projects=None) -> CompilationContext:
    return CompilationContext(
        workspace_root=tmp_path,
        environment_digest=ENVIRONMENT_DIGEST,
        artifacts={artifact.artifact_id: artifact for artifact in artifacts},
        projects=projects or {},
    )


def _workflow(schema_digest: str, *nodes: CommandNode) -> CommandWorkflowSpec:
    return CommandWorkflowSpec(
        workflow_id="workflow-command-ir",
        task_spec_id="task-command-ir",
        cli_schema_digest=schema_digest,
        nodes=nodes,
    )


def _rule_ids(compilation) -> set[str]:
    return {item.rule_id for item in compilation.counterexamples}


def test_model_facing_command_maps_are_deeply_immutable_and_canonical() -> None:
    first = CommandNode(
        node_id="xtb-opt",
        command_path="run/xtb/opt",
        parameters={
            "solvent_id": "water",
            "metadata": {"selectors": ["a", "b"]},
            "gfn_version": "gfn2",
        },
        charge=0,
        multiplicity=1,
    )
    second = CommandNode(
        node_id="xtb-opt",
        command_path="run/xtb/opt",
        parameters={
            "gfn_version": "gfn2",
            "metadata": {"selectors": ["a", "b"]},
            "solvent_id": "water",
        },
        charge=0,
        multiplicity=1,
    )

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    with pytest.raises(TypeError, match="immutable"):
        first.parameters["gfn_version"] = "gfn1"
    with pytest.raises(TypeError, match="immutable"):
        first.parameters["metadata"]["selectors"] = ("changed",)
    with pytest.raises((TypeError, AttributeError)):
        first.parameters["metadata"]["selectors"].append("changed")

    empty = CommandNode(node_id="xtb-sp", command_path="run/xtb/sp")
    with pytest.raises(TypeError, match="immutable"):
        empty.parameters["grad"] = True
    empty_invocation = CanonicalCommandInvocation(
        workflow_id="workflow-command-ir",
        node_id="xtb-sp",
        command_path=("run", "xtb", "sp"),
        argv=("chemsmart", "run", "xtb", "sp"),
        display_command="chemsmart run xtb sp",
        command_sha256="a" * 64,
        cli_schema_digest="b" * 64,
        environment_digest="c" * 64,
    )
    with pytest.raises(TypeError, match="immutable"):
        empty_invocation.intent_projection["program"] = "xtb"


def test_compiler_revalidates_unchecked_model_copy_updates(tmp_path) -> None:
    schema, schema_digest = _schema_and_digest()
    binding, artifact = _water_binding(tmp_path)
    workflow = _workflow(
        schema_digest,
        CommandNode(
            node_id="xtb-sp",
            command_path="run/xtb/sp",
            input_artifacts=(binding,),
            charge=0,
            multiplicity=1,
        ),
    )
    copied_node = workflow.nodes[0].model_copy(
        update={"parameters": {"gfn_version": "gfn2"}}
    )
    assert type(copied_node.parameters) is dict
    unchecked = workflow.model_copy(update={"nodes": (copied_node,)})

    compilation = CommandWorkflowCompiler(schema).compile(
        unchecked,
        _context(tmp_path, artifact),
    )

    assert compilation.status == "previewable"
    with pytest.raises(TypeError, match="immutable"):
        compilation.invocations[0].intent_projection["program"] = "gaussian"


def test_compiler_snapshots_nested_cli_schema() -> None:
    schema, original_digest = _schema_and_digest()
    compiler = CommandWorkflowCompiler(schema)

    schema["subcommands"].clear()

    assert compiler.schema_digest == original_digest
    assert compiler.schema_digest == cli_schema_digest(compiler._schema)


def test_compiler_uses_live_schema_and_renders_canonical_long_flags(
    tmp_path,
) -> None:
    schema, schema_digest = _schema_and_digest()
    binding, artifact = _water_binding(tmp_path)
    workflow = _workflow(
        schema_digest,
        CommandNode(
            node_id="xtb-opt",
            command_path="run/xtb/opt",
            parameters={
                "gfn_version": "gfn2",
                "optimization_level": "tight",
            },
            input_artifacts=(binding,),
            charge=0,
            multiplicity=1,
        ),
    )

    compilation = CommandWorkflowCompiler(schema).compile(
        workflow, _context(tmp_path, artifact)
    )

    assert compilation.status == "previewable"
    assert compilation.ready_for_safe_preview is True
    invocation = compilation.invocations[0]
    assert invocation.argv == (
        "chemsmart",
        "run",
        "xtb",
        "--charge",
        "0",
        "--filename",
        "water.xyz",
        "--gfn-version",
        "gfn2",
        "--multiplicity",
        "1",
        "opt",
        "--optimization-level",
        "tight",
    )
    assert shlex.split(invocation.display_command) == list(invocation.argv)
    assert " -c " not in f" {invocation.display_command} "
    assert invocation.input_artifacts[0].artifact_id == "geom-water"
    assert str(tmp_path) not in invocation.model_dump_json()


def test_compiler_requires_opaque_artifact_binding_not_raw_filename(
    tmp_path,
) -> None:
    schema, schema_digest = _schema_and_digest()
    binding, artifact = _water_binding(tmp_path)
    workflow = _workflow(
        schema_digest,
        CommandNode(
            node_id="xtb-opt",
            command_path="run/xtb/opt",
            parameters={"filename": "water.xyz"},
            input_artifacts=(binding,),
            charge=0,
            multiplicity=1,
        ),
    )

    compilation = CommandWorkflowCompiler(schema).compile(
        workflow, _context(tmp_path, artifact)
    )

    assert compilation.status == "blocked"
    assert "cmd.ir.raw_artifact_path" in _rule_ids(compilation)
    assert not compilation.invocations


def test_gaussian_project_reference_is_hashed_and_method_settings_are_not_cli(
    tmp_path,
) -> None:
    schema, schema_digest = _schema_and_digest()
    binding, artifact = _water_binding(tmp_path)
    project_path = tmp_path / ".chemsmart" / "gaussian" / "water.yaml"
    project_path.parent.mkdir(parents=True)
    project_path.write_text("gaussian: {}\n", encoding="utf-8")
    project_digest = _sha256(project_path)
    project_ref = ProjectReference(
        project_id="project-gaussian-water",
        sha256=project_digest,
    )
    project = ResolvedProject(
        project_id="project-gaussian-water",
        sha256=project_digest,
        program="gaussian",
        command_value="water",
        path=project_path,
    )
    workflow = _workflow(
        schema_digest,
        CommandNode(
            node_id="gaussian-sp",
            command_path="run/gaussian/sp",
            project_ref=project_ref,
            input_artifacts=(binding,),
            charge=0,
            multiplicity=1,
        ),
    )

    compilation = CommandWorkflowCompiler(schema).compile(
        workflow,
        _context(tmp_path, artifact, projects={project.project_id: project}),
    )

    assert compilation.status == "previewable"
    invocation = compilation.invocations[0]
    assert "--project" in invocation.argv
    assert invocation.argv[invocation.argv.index("--project") + 1] == "water"
    assert invocation.project_sha256 == project_digest

    invalid = workflow.model_copy(
        update={
            "nodes": (
                workflow.nodes[0].model_copy(
                    update={"parameters": {"functional": "B3LYP"}}
                ),
            )
        }
    )
    rejected = CommandWorkflowCompiler(schema).compile(
        invalid,
        _context(tmp_path, artifact, projects={project.project_id: project}),
    )
    assert "cmd.ir.project_owned_setting" in _rule_ids(rejected)


def test_downstream_artifact_without_receipt_stays_planned_not_executable(
    tmp_path,
) -> None:
    schema, schema_digest = _schema_and_digest()
    source_binding, source_artifact = _water_binding(tmp_path)
    downstream_binding = ArtifactBinding(
        artifact_id="artifact-preopt-geometry",
        sha256="a" * 64,
        kind="geometry.xyz",
        target_parameter="filename",
        producer_node_id="preopt",
    )
    workflow = _workflow(
        schema_digest,
        CommandNode(
            node_id="preopt",
            command_path="run/xtb/opt",
            input_artifacts=(source_binding,),
            charge=0,
            multiplicity=1,
            expected_artifact_classes=("geometry.xyz",),
        ),
        CommandNode(
            node_id="downstream",
            command_path="run/xtb/opt",
            input_artifacts=(downstream_binding,),
            charge=0,
            multiplicity=1,
            dependencies=("preopt",),
        ),
    )

    compilation = CommandWorkflowCompiler(schema).compile(
        workflow, _context(tmp_path, source_artifact)
    )

    assert compilation.status == "planned"
    assert [item.node_id for item in compilation.invocations] == ["preopt"]
    assert compilation.unresolved_node_ids == ("downstream",)
    assert _rule_ids(compilation) == {"cmd.artifact.dependency_not_ready"}


def test_compiler_rejects_shell_syntax_even_when_it_is_a_parameter_value(
    tmp_path,
) -> None:
    schema, schema_digest = _schema_and_digest()
    binding, artifact = _water_binding(tmp_path)
    workflow = _workflow(
        schema_digest,
        CommandNode(
            node_id="xtb-opt",
            command_path="run/xtb/opt",
            parameters={"label": "water; rm -rf /"},
            input_artifacts=(binding,),
            charge=0,
            multiplicity=1,
        ),
    )

    compilation = CommandWorkflowCompiler(schema).compile(
        workflow, _context(tmp_path, artifact)
    )

    assert compilation.status == "blocked"
    assert "cmd.ir.shell_syntax" in _rule_ids(compilation)


def test_compiler_rejects_environment_and_ampersand_insertion(tmp_path) -> None:
    schema, schema_digest = _schema_and_digest()
    binding, artifact = _water_binding(tmp_path)
    workflow = _workflow(
        schema_digest,
        CommandNode(
            node_id="xtb-opt",
            command_path="run/xtb/opt",
            parameters={"label": "$HOME&&unexpected"},
            input_artifacts=(binding,),
            charge=0,
            multiplicity=1,
        ),
    )

    compilation = CommandWorkflowCompiler(schema).compile(
        workflow, _context(tmp_path, artifact)
    )

    assert compilation.status == "blocked"
    assert "cmd.ir.shell_syntax" in _rule_ids(compilation)


def test_compiler_rejects_native_input_as_a_computational_geometry(tmp_path) -> None:
    schema, schema_digest = _schema_and_digest()
    native = tmp_path / "legacy.com"
    native.write_text("#p b3lyp\n\nlegacy\n\n0 1\nH 0 0 0\n", encoding="utf-8")
    digest = _sha256(native)
    binding = ArtifactBinding(
        artifact_id="legacy-native-input",
        sha256=digest,
        kind="native_input.gaussian",
        target_parameter="filename",
    )
    artifact = ResolvedArtifact(
        artifact_id="legacy-native-input",
        sha256=digest,
        kind="native_input.gaussian",
        path=native,
    )
    workflow = _workflow(
        schema_digest,
        CommandNode(
            node_id="xtb-opt",
            command_path="run/xtb/opt",
            input_artifacts=(binding,),
            charge=0,
            multiplicity=1,
        ),
    )

    compilation = CommandWorkflowCompiler(schema).compile(
        workflow, _context(tmp_path, artifact)
    )

    assert compilation.status == "blocked"
    assert "cmd.artifact.geometry_required" in _rule_ids(compilation)


def test_v8_reader_migrates_only_resolved_artifacts_and_live_subcommands(
    tmp_path,
) -> None:
    schema, schema_digest = _schema_and_digest()
    binding, artifact = _water_binding(tmp_path)
    compact_spec = {
        "intent": "workflow",
        "jobs": [
            {
                "id": "preopt",
                "kind": "xtb.opt",
                "file": "water.xyz",
                "charge": 0,
                "mult": 1,
                "settings": {"gfn_version": "gfn2"},
            }
        ],
    }

    migration = migrate_v8_compact_spec(
        compact_spec,
        cli_schema_digest=schema_digest,
        artifact_bindings={"file:water.xyz": binding},
        project_references={},
        schema=schema,
    )

    assert migration.status == "migrated"
    assert migration.workflow is not None
    compilation = CommandWorkflowCompiler(schema).compile(
        migration.workflow, _context(tmp_path, artifact)
    )
    assert compilation.status == "previewable"
    assert "<upstream-geometry>" not in compilation.invocations[0].display_command


def test_v8_reader_refuses_upstream_geometry_placeholder_and_route_aliases(
    tmp_path,
) -> None:
    schema, schema_digest = _schema_and_digest()
    binding, _artifact = _water_binding(tmp_path)
    placeholder = migrate_v8_compact_spec(
        {
            "intent": "workflow",
            "jobs": [
                {
                    "id": "bad",
                    "kind": "xtb.opt",
                    "file": "<upstream-geometry>",
                }
            ],
        },
        cli_schema_digest=schema_digest,
        artifact_bindings={},
        project_references={},
        schema=schema,
    )
    alias = migrate_v8_compact_spec(
        {
            "intent": "workflow",
            "jobs": [
                {
                    "id": "td",
                    "kind": "gaussian.tddft",
                    "file": "water.xyz",
                }
            ],
        },
        cli_schema_digest=schema_digest,
        artifact_bindings={"file:water.xyz": binding},
        project_references={},
        schema=schema,
    )

    assert placeholder.status == "needs_clarification"
    assert "cmd.migration.placeholder_or_path" in {
        item.rule_id for item in placeholder.counterexamples
    }
    assert alias.status == "needs_clarification"
    assert "cmd.migration.kind_unrepresentable" in {
        item.rule_id for item in alias.counterexamples
    }
