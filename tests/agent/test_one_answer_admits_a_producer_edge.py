"""One answer says whether a consumer may wait on its producer.

"May this consumer wait on its producer inside one approval, and what
will the host hand it?" had an answer in the execution review, another
in the frontier that tells a session whether its workflow can be
approved, a third in the reply to a waiting node, and a fourth in the
handoff that runs after the producer has finished.  They disagreed on
real plans:

- An ORCA relaxed scan carrying its minimum-energy point into an
  optimisation (``validated_scan_minimum_geometry``) was admitted by the
  review and called blocking by the frontier.  Every one of 24 archived
  planning sessions that planned that edge (Hetzner, 2026-08-21 to
  09-04) ended "workflow recorded but not approvable; these nodes still
  block approval: <the consumer>", and 11 of those edges then executed.
- An ORCA ``modred`` feeding a saddle search was admitted by the review,
  ran 19,578 s, validated, and was then refused by the handoff as "not a
  converged OPT or TS" (CUHK r9o-g5 cycle 2), which recorded the node
  that had run as a launch refusal.
"""

from __future__ import annotations

import ast
import warnings
from pathlib import Path
from types import SimpleNamespace

import pytest

from chemsmart.agent.execution_envelope import load_bounded_execution_envelope
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.agent.workflows import (
    ScientificWorkflowEdgeV2,
    ScientificWorkflowNodeV2,
    build_scientific_workflow_plan,
)

pytestmark = pytest.mark.capability("gate:resolver.one_answer_per_question")


def _node(node_id: str, stage: str, program: str = "orca", **extra):
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


def _geometry_edge(source: str, target: str):
    return ScientificWorkflowEdgeV2(
        edge_id=f"data.{source}.{target}.filename",
        source_node_id=source,
        target_node_id=target,
        edge_kind="data",
        artifact_class="geometry_xyz",
        producer_output_id="geometry",
        consumer_input_id="filename",
    )


def _plan(producer_stage: str, producer_program: str = "orca"):
    return build_scientific_workflow_plan(
        workflow_id="producer-edge",
        task_spec_sha256="a" * 64,
        scientific_identity_sha256="b" * 64,
        nodes=(
            _node("producer", producer_stage, program=producer_program),
            _node(
                "consumer",
                "opt",
                program=producer_program,
                support_state="unresolved_future",
            ),
        ),
        edges=(_geometry_edge("producer", "consumer"),),
    )


def _host(tmp_path: Path, program: str):
    envelope_path = tmp_path / "envelope.yaml"
    envelope_path.write_text(
        "\n".join(
            (
                "schema_version: chemsmart.bounded-execution-envelope.v1",
                "mode: bounded-local",
                f"allowed_program_engines: {{{program}: [cpu]}}",
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
    host._node_is_previewed = lambda node_id, **_kw: node_id == "producer"
    # The review's own resolver answers for the consumer's project,
    # capability and environment; this test asks only the edge question,
    # so the resolver resolves.
    host._bounded_node_context = lambda **_kw: SimpleNamespace()
    return host


def test_a_scan_minimum_consumer_waits_where_the_review_admits_it(tmp_path):
    """The one route out of a torsional saddle is not told to delete itself."""

    plan = _plan("scan")
    readiness = _host(tmp_path, "orca")._approval_readiness(plan)

    nodes = {node["node_id"]: node for node in readiness["nodes"]}
    assert nodes["consumer"]["approval_state"] == "deferred_admissible", nodes[
        "consumer"
    ]
    assert readiness["blocking_node_ids"] == ()
    assert readiness["approvable"] is True


CHEMSMART = Path(__file__).resolve().parents[2] / "chemsmart"

#: The per-rule predicates the one owner composes, and the functions
#: allowed to call each. Everyone else asks
#: ``producer_edge_selection_rule`` -- a new organ that grows its own
#: answer is how the frontier and the review came to disagree.
OWNED_PREDICATES = {
    "is_validated_optimized_geometry_edge": {"producer_edge_selection_rule"},
    "is_validated_scan_minimum_geometry_edge": {
        "producer_edge_selection_rule"
    },
    "is_validated_orca_ts_hessian_edge": {"producer_edge_selection_rule"},
    "is_validated_producer_orca_hessian_edge": {
        "producer_edge_selection_rule"
    },
    # The stage question beneath the optimized-geometry rule: its own
    # predicate, and the native handoff, which must hand on exactly the
    # stages that rule admitted.
    "_ends_on_one_reached_structure": {
        "is_validated_optimized_geometry_edge",
        "handoff_optimized_native_geometry",
    },
}


def _bypasses(source: str, path: str) -> list[str]:
    """Calls of an owned predicate from outside the functions it names.

    Every function is walked, owners included, so a helper nested
    inside an allowed function is judged by its own name.
    """

    with warnings.catch_warnings():
        # Some host modules carry regex strings with escapes that parse
        # with a SyntaxWarning; the lint reads their structure only.
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(source)
    found = []
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func
            name = (
                callee.id
                if isinstance(callee, ast.Name)
                else callee.attr if isinstance(callee, ast.Attribute) else ""
            )
            allowed = OWNED_PREDICATES.get(name)
            if allowed is not None and function.name not in allowed:
                found.append(f"{path}::{function.name} calls {name}")
    return found


def test_only_the_owner_asks_the_per_rule_predicates():
    """The bypass is forbidden mechanically, not by a comment."""

    offenders = []
    for path in sorted(CHEMSMART.rglob("*.py")):
        offenders += _bypasses(
            path.read_text(encoding="utf-8"),
            str(path.relative_to(CHEMSMART.parent)),
        )
    assert (
        not offenders
    ), "ask producer_edge_selection_rule instead:\n" + "\n".join(offenders)


def test_the_lint_sees_a_planted_bypass():
    planted = (
        "def _frontier(plan, edge):\n"
        "    return is_validated_scan_minimum_geometry_edge(plan, edge)\n"
        "def producer_edge_selection_rule(plan, edge):\n"
        "    return is_validated_scan_minimum_geometry_edge(plan, edge)\n"
    )
    assert _bypasses(planted, "planted.py") == [
        "planted.py::_frontier calls is_validated_scan_minimum_geometry_edge"
    ]
