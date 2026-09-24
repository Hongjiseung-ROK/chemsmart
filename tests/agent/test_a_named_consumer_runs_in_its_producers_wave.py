"""A consumer the Agent names beside its producer runs in that wave.

An approval that admits a producer edge says the consumer may wait on
its producer inside that approval and names what the host will hand it.
The wave barrier then refused every such pair as one experiment, and
every goal cycle plans a new workflow, so the admitted consumer never
ran: in 1,810 archived run streams, 281 of 283 bound edges fed a consumer
that ran under its approval before 2026-09-17 and 0 of 92 after (the
TDA of a formaldehyde smoke goal, an ORCA IRC with its saddle's Hessian,
Hessians at 60 optimised minima).

The owner's ruling stands: a node whose dependency clears mid-wave and
that nobody named does not run. Naming it is the Agent's decision, and
the approval's one owner of producer edges decides whether the pair may
run in one line.
"""

from __future__ import annotations

import json

import pytest

from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from tests.agent.neutral_workflow_fixture import build_neutral_workflow_fixture
from tests.agent.plan_through_draft import plan_workflow

pytestmark = pytest.mark.capability("tool:select_execution_wave")


def _planned_host(tmp_path, *, structure_edge: bool):
    """A real host holding a planned opt -> hess workflow.

    ``structure_edge`` states the Hessian's input as the structure edge
    the one owner admits (``filename``/``geometry_xyz``); without it the
    same plan hands a bare ``xyz`` that no registered rule carries.
    """

    fixture = build_neutral_workflow_fixture(tmp_path / "fixture")
    store = RuntimeEventStore(
        tmp_path / "events" / "runtime.jsonl", session_id="session"
    )
    host = CommandCompiledToolHostV1(
        event_store=store,
        task_spec_sha256s=(fixture.public_context.task_spec_sha256,),
        approved_workspace=tmp_path / "preview",
        **fixture.host_inputs,
    )
    fields = json.loads(
        json.dumps(
            dict(
                next(
                    item
                    for item in fixture.public_context.next_actions
                    if item.tool_name == "plan_scientific_workflow"
                ).fields
            )
        )
    )
    if structure_edge:
        for node in fields["calculation_nodes"]:
            if node["node_id"] == "node.opt":
                node["expected_outputs"][0]["artifact_class"] = "geometry_xyz"
            if node["node_id"] == "node.hess":
                node["inputs"][0]["binding_id"] = "filename"
                node["inputs"][0]["artifact_class"] = "geometry_xyz"
    plan_workflow(host, "turn-1", fields)
    return host


def _select(host, node_ids):
    reply = host.dispatch(
        turn_id="turn-2",
        tool_name="select_execution_wave",
        arguments={
            "workflow_id": "workflow-neutral-opt-hess",
            "node_ids": list(node_ids),
        },
    )
    assert reply["status"] == "ok", reply
    return reply["result"]


def _rows(reply):
    return {row["node_id"]: row for row in reply["members"]}


def test_a_consumer_named_with_its_producer_runs_after_it(tmp_path):
    host = _planned_host(tmp_path, structure_edge=True)

    reply = _select(host, ("node.opt", "node.hess"))

    assert reply["status"] == "ready", reply
    assert reply["node_ids"] == ["node.opt", "node.hess"]
    rows = _rows(reply)
    assert rows["node.opt"]["status"] == "ready"
    assert rows["node.hess"]["status"] == "after"
    assert "node.opt" in rows["node.hess"]["detail"]
    assert "does not validate" in rows["node.hess"]["detail"]
    decision = host.execution_wave_decision
    assert decision.state == "selected"
    assert decision.node_ids == ("node.opt", "node.hess")


def test_a_consumer_nobody_named_still_waits(tmp_path):
    host = _planned_host(tmp_path, structure_edge=True)

    reply = _select(host, ("node.hess",))

    assert reply["status"] == "not_dispatchable"
    assert _rows(reply)["node.hess"]["status"] == "not_ready"
    assert "node.opt" in _rows(reply)["node.hess"]["detail"]


def test_an_edge_the_approval_does_not_carry_is_still_one_experiment(
    tmp_path,
):
    host = _planned_host(tmp_path, structure_edge=False)

    reply = _select(host, ("node.opt", "node.hess"))

    assert reply["status"] == "not_dispatchable"
    assert _rows(reply)["node.hess"]["status"] == "depends_on"


def test_a_line_is_one_element_and_single_calculations_keep_their_bytes(
    tmp_path,
):
    from chemsmart.agent.cohort import (
        build_cohort_manifest,
        cohort_lines,
        read_cohort_manifest,
    )

    lines = cohort_lines(
        ("ts", "irc-f", "gs-opt", "irc-b"),
        (("ts", "irc-f"), ("ts", "irc-b"), ("irc-f", "opt-f")),
    )
    assert lines == (("ts", "irc-f", "irc-b"), ("gs-opt",))

    common = dict(
        goal_id="g1",
        cycle=1,
        bundle_sha256="e" * 64,
        max_concurrent_tasks=2,
        created_at="2026-09-24T00:00:00+00:00",
    )
    chained = build_cohort_manifest(
        node_ids=("ts", "irc-f", "gs-opt", "irc-b"),
        element_node_ids=lines,
        **common,
    )
    assert chained.element_count == 2
    assert chained.nodes_for_element(0) == ("ts", "irc-f", "irc-b")
    assert chained.node_for_element(1) == "gs-opt"
    assert chained.element_for_node("irc-b") == 0
    chained.write(tmp_path)
    assert read_cohort_manifest(tmp_path) == chained

    plain = build_cohort_manifest(node_ids=("a1", "a2"), **common)
    also_plain = build_cohort_manifest(
        node_ids=("a1", "a2"),
        element_node_ids=cohort_lines(("a1", "a2"), ()),
        **common,
    )
    assert plain == also_plain
    assert "element_node_ids" not in plain.public_record()
    assert plain.element_count == 2
    assert plain.nodes_for_element(1) == ("a2",)
