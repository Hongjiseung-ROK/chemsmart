"""The command a human reviews for an IRC carries the Hessian it will read.

An approval that admits an ORCA TS -> IRC pair freezes two edges into the
IRC: the saddle's geometry and its Hessian. The reviewed command showed
only the geometry, the executor compiled the IRC without the Hessian, and
the equality of the recompiled command with the reviewed one held --
because both had dropped the same file. Every IRC the archive holds under
such an approval (r8 goal-ts, Hetzner h1/h1b and the irc-agent-path
qualifications) launched without it.

The reviewed command now shows the Hessian as the digest-bound
placeholder of the edge that produces it, and the launched command binds
the file the handoff selected to that same placeholder, so the equality
the approval chain enforces is an equality with the Hessian in it. This
pins the gate at that invariant with the live Click compiler: a launch
without the Hessian, or with a file bound to another edge, differs from
the reviewed command.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from chemsmart.agent.capabilities import (
    EnvironmentTargetV1,
    query_environment,
    resolve_engine_binding,
    resolve_program_binding,
)
from chemsmart.agent.commands import (
    CommandProposalV1,
    build_scientific_identity_binding,
    compile_command,
)
from chemsmart.agent.execution import (
    build_execution_resource_spec,
    build_producer_edge_rule,
    build_real_execution_argv,
    project_real_execution_argv,
)
from chemsmart.agent.tool_runtime import (
    _future_auxiliary_placeholders,
    _future_auxiliary_role,
)
from tests.agent.gaussian_fake_preview import artifact, capability, validate

pytestmark = pytest.mark.capability("program_jobtype:orca:cpu:irc")

_SADDLE = (
    Path(__file__).resolve().parents[1] / "data" / "ORCATests" / "outputs"
)


def _edges():
    geometry = build_producer_edge_rule(
        producer_node_id="ts-search",
        consumer_node_id="irc-forward",
        artifact_kind="geometry_xyz",
        selection_rule="validated_optimized_geometry",
    )
    hessian = build_producer_edge_rule(
        producer_node_id="ts-search",
        consumer_node_id="irc-forward",
        artifact_kind="orca_hessian",
        selection_rule="validated_final_orca_ts_hessian",
    )
    return geometry, hessian


def _compile(tmp_path, **options):
    tmp_path.mkdir(parents=True, exist_ok=True)
    xyz = tmp_path / "saddle.xyz"
    xyz.write_text(
        (_SADDLE / "sn2_ts.xyz").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    project, validation = validate(
        tmp_path,
        "orca",
        {
            "irc": {
                "functional": "m062x",
                "basis": "def2-svp",
                "direction": "forward",
            }
        },
        "irc",
    )
    receipt = capability("orca", "irc")
    environment = query_environment(
        receipt,
        targets=(EnvironmentTargetV1("orca", "cpu", "executable", "orca"),),
        which=lambda _name: "/opt/orca/orca",
    )
    engine = resolve_engine_binding(
        resolve_program_binding(receipt), environment
    )
    geometry = artifact(xyz, "geometry_xyz")
    identity = build_scientific_identity_binding(
        task_spec_sha256="f" * 64,
        geometry_artifact=geometry,
        charge=-1,
        multiplicity=1,
    )
    invocation = compile_command(
        CommandProposalV1(
            node_id="irc-forward",
            execution_target="run",
            program="orca",
            jobtype="irc",
            project_artifact_id=project.stem,
            input_artifact_id=geometry.artifact_id,
            scientific_identity_sha256=identity.binding_sha256,
            charge=-1,
            multiplicity=1,
        ),
        capability=receipt,
        binding=engine,
        project=artifact(project, "project_yaml"),
        project_validation=validation,
        input_artifact=geometry,
        scientific_identity=identity,
        **options,
    )
    return invocation, geometry, artifact(project, "project_yaml")


def _projected(invocation, geometry, project, geometry_edge, extra=()):
    resources = build_execution_resource_spec(
        execution_target="run",
        cores=2,
        memory_gb=4,
        gpu_count=0,
        scratch_policy="server",
        node_timeout_seconds=600,
    )
    argv = build_real_execution_argv(
        compiled_argv=invocation.argv,
        command_path=invocation.command_path,
        resources=resources,
        server="",
    )
    bindings = {
        sys.executable: ("controller-python", "0" * 64),
        project.cli_value: ("project-yaml", project.sha256),
        geometry.cli_value: ("producer-geometry", geometry_edge.edge_sha256),
        **dict(extra),
    }
    return project_real_execution_argv(argv, path_bindings=bindings)


def test_the_reviewed_and_the_launched_irc_are_one_command(tmp_path):
    geometry_edge, hessian_edge = _edges()
    placeholders = _future_auxiliary_placeholders(
        (geometry_edge, hessian_edge), "irc-forward"
    )
    assert set(placeholders) == {"hess_filename"}

    reviewed, geometry, project = _compile(
        tmp_path / "review", future_job_artifact_options=placeholders
    )
    review_argv = _projected(reviewed, geometry, project, geometry_edge)
    assert "--hess-filename" in review_argv
    assert placeholders["hess_filename"] in review_argv

    hessian = artifact(_SADDLE / "sn2_ts.hess", "orca_hessian")
    launched, geometry, project = _compile(
        tmp_path / "launch", job_artifact_options={"hess_filename": hessian}
    )
    launch_argv = _projected(
        launched,
        geometry,
        project,
        geometry_edge,
        extra={
            hessian.cli_value: (
                _future_auxiliary_role("hess_filename"),
                hessian_edge.edge_sha256,
            )
        }.items(),
    )
    assert launch_argv == review_argv

    # A launch that drops the Hessian is no longer the reviewed command.
    bare, geometry, project = _compile(tmp_path / "bare")
    assert _projected(bare, geometry, project, geometry_edge) != review_argv
