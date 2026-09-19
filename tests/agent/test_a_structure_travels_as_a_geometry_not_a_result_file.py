"""A consumer fed its producer's result file is told how to be approved.

CUHK g3-ethane (2026-09-20) planned two PySCF optimisations -- the
supplied staggered structure and an eclipsed one it built -- feeding a
Hessian on each and two IRC branches from the eclipsed one, every edge
carrying the producer's ``pyscf_hdf5``. A result file exists only after
its producer has run, so none of the four consumers could be previewed or
deferred, the workflow could not be approved, and the producers never ran.
Every reply named routes that clear a node lacking a preview; none named
the one that clears this node: hand the structure on as ``geometry_xyz``,
which defers until the producer's validated structure exists.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from chemsmart.agent.execution import result_file_structure_edges
from chemsmart.agent.execution_envelope import load_bounded_execution_envelope
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.agent.workflows import (
    ScientificWorkflowEdgeV2,
    ScientificWorkflowNodeV2,
    build_scientific_workflow_plan,
)

pytestmark = pytest.mark.capability("tool:select_execution_wave")


def _node(node_id: str, stage: str, program: str = "pyscf", **extra):
    return ScientificWorkflowNodeV2(
        node_id=node_id,
        stage=stage,
        requested_program=program,
        program=program,
        engine="cpu",
        project_role=f"project.{stage}",
        unresolved_fields=(),
        **extra,
    )


def _edge(source: str, target: str, artifact_class: str):
    return ScientificWorkflowEdgeV2(
        edge_id=f"data.{source}.{target}.filename",
        source_node_id=source,
        target_node_id=target,
        edge_kind="data",
        artifact_class=artifact_class,
        producer_output_id="result",
        consumer_input_id="filename",
    )


def _plan(artifact_class: str, producer_program: str = "pyscf"):
    return build_scientific_workflow_plan(
        workflow_id="ethane-rotation",
        task_spec_sha256="a" * 64,
        scientific_identity_sha256="b" * 64,
        nodes=(
            _node("opt-eclipsed", "opt"),
            _node("hess-ecl", "hess", support_state="unresolved_future"),
            _node("irc-fwd", "irc", support_state="unresolved_future"),
            _node("irc-src", "irc", program=producer_program),
            _node("hess-end", "hess", support_state="unresolved_future"),
        ),
        edges=tuple(
            sorted(
                (
                    _edge("opt-eclipsed", "hess-ecl", artifact_class),
                    _edge("opt-eclipsed", "irc-fwd", artifact_class),
                    _edge("irc-src", "hess-end", artifact_class),
                ),
                key=lambda edge: edge.edge_id,
            )
        ),
    )


def test_a_geometry_edge_or_a_producer_without_one_structure_is_not():
    geometry = _plan("geometry_xyz")
    assert result_file_structure_edges(geometry, "hess-ecl") == ()
    # ORCA's IRC log holds no endpoint, so its result is not a structure
    # this rule could have sent as geometry_xyz either.
    orca = _plan("orca_output", producer_program="orca")
    assert result_file_structure_edges(orca, "hess-end") == ()


def _host(tmp_path, plan):
    envelope_path = tmp_path / "envelope.yaml"
    envelope_path.write_text(
        "\n".join(
            (
                "schema_version: chemsmart.bounded-execution-envelope.v1",
                "mode: bounded-local",
                "allowed_program_engines: {pyscf: [cpu]}",
                "resources: {execution_target: run, cores: 8, memory_gb: 28,"
                " gpu_count: 0, scratch_policy: server,"
                " node_timeout_seconds: 600}",
                "episode_wall_time_seconds: 3600",
                "postprocess_reserve_seconds: 300",
                "max_engine_calls: 6",
                f"scratch_root: {tmp_path / 'scratch'}",
            )
        ),
        encoding="utf-8",
    )
    host = object.__new__(CommandCompiledToolHostV1)
    host.bounded_execution_envelope = load_bounded_execution_envelope(
        envelope_path
    )
    previewed = {"opt-eclipsed", "irc-src"}
    host._node_is_previewed = lambda node_id, **_kw: node_id in previewed
    host._resolve_program_workflow = lambda _wid: SimpleNamespace(
        draft=SimpleNamespace(
            workflow_id=plan.workflow_id,
            nodes=tuple(
                SimpleNamespace(node_id=node.node_id, inputs=())
                for node in plan.nodes
            ),
        ),
        scientific_plan=plan,
    )
    host._workflow_context = lambda draft, **_kw: SimpleNamespace(
        ready_node_ids=("opt-eclipsed", "irc-src"),
        node=lambda node_id: None,
    )
    return host


def test_the_frontier_and_the_wave_reply_name_the_geometry_route(tmp_path):
    plan = _plan("pyscf_hdf5")
    host = _host(tmp_path, plan)

    readiness = host._approval_readiness(plan)
    assert readiness["approvable"] is False
    nodes = {node["node_id"]: node for node in readiness["nodes"]}
    # Every consumer fed a result file -- by an optimisation, and by a
    # PySCF IRC branch, which ends on one structure too -- is told the
    # edge class that clears it, and which producer's output it reads.
    for consumer, producer in (
        ("hess-ecl", "opt-eclipsed"),
        ("irc-fwd", "opt-eclipsed"),
        ("hess-end", "irc-src"),
    ):
        reason = nodes[consumer]["blocking_reason"]
        assert "geometry_xyz" in reason and producer in reason, reason
    assert "blocking_reason" not in nodes["opt-eclipsed"]

    # The wave reply, which is where the session last looks before it
    # ends, carries each of those reasons rather than only the routes
    # that clear a node lacking a preview.
    reply = host._select_execution_wave(
        "t1",
        {"workflow_id": plan.workflow_id, "node_ids": ["opt-eclipsed"]},
    )
    assert reply["workflow_approvable"] is False
    for consumer in ("hess-ecl", "irc-fwd", "hess-end"):
        assert nodes[consumer]["blocking_reason"] in reply["next_action"]
