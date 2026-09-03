"""An excursion is a displayed budget line for investigating an anomaly.

The literature verdict on validity gates was that the loss is in
disposition and price: a failed node's numbers can never become a claim,
and one fungible budget prices an excursion at one delivery call. The
envelope may now grant a separate, displayed, non-fungible line; a node
tagged with a host-recorded anomaly's digest is charged to that line,
never to the engine-call budget, and may feed no untagged node, so the
asked observable is never bought with the grant. Default zero: nothing
runs on the line unless the human granted it. A second approval would be
a second plane; the tag rides the reviewed plan and the one-shot bundle.
"""

from __future__ import annotations

import pytest
import yaml

from chemsmart.agent._contracts import ContractError, canonical_data
from chemsmart.agent.execution import (
    ApprovedNodeBindingV1,
    build_program_execution_receipt,
)
from chemsmart.agent.execution_envelope import (
    load_bounded_execution_envelope,
)
from chemsmart.agent.goal import (
    GOAL_SCHEMA_VERSION,
    GoalLedger,
    GoalRecordV1,
    admit_revision,
)
from chemsmart.agent.live_session import (
    _parse_bounded_execution_envelope_record,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.terminal_states import derive_run_outcome, read_run_events
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from tests.agent.neutral_workflow_fixture import (
    build_neutral_workflow_fixture,
)
from tests.agent.test_a_goal_is_one_decision_a_loop_consumes import (
    _RUN,
    _wake_stream,
)
from tests.agent.test_runtime_v2_launch_fence import _reserve

_ANOMALY = "f" * 64


def _envelope(tmp_path, *, max_engine_calls, max_excursion_calls=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    body = {
        "schema_version": "chemsmart.bounded-execution-envelope.v1",
        "mode": "bounded-local",
        "allowed_program_engines": {"orca": ["cpu"]},
        "resources": {
            "execution_target": "run",
            "cores": 2,
            "memory_gb": 8,
            "gpu_count": 0,
            "scratch_policy": "server",
            "node_timeout_seconds": 600,
        },
        "episode_wall_time_seconds": 3600,
        "postprocess_reserve_seconds": 60,
        "max_engine_calls": max_engine_calls,
        "scratch_root": str(tmp_path / "scratch"),
    }
    if max_excursion_calls is not None:
        body["max_excursion_calls"] = max_excursion_calls
    path = tmp_path / "envelope.yaml"
    path.write_text(yaml.safe_dump(body), encoding="utf-8")
    return load_bounded_execution_envelope(path)


def test_the_line_is_optional_defaults_to_zero_and_shows_only_when_granted(
    tmp_path,
):
    silent = _envelope(tmp_path / "a", max_engine_calls=2)
    assert silent.max_excursion_calls == 0
    assert "max_excursion_calls" not in silent.public_record()
    granted = _envelope(
        tmp_path / "b", max_engine_calls=2, max_excursion_calls=1
    )
    assert granted.max_excursion_calls == 1
    assert granted.public_record()["max_excursion_calls"] == 1
    with pytest.raises(ContractError, match="max_excursion_calls"):
        _envelope(tmp_path / "c", max_engine_calls=2, max_excursion_calls=-1)
    # A record minted before the line existed still verifies as zero.
    record = canonical_data(silent)
    record.pop("max_excursion_calls")
    parsed = _parse_bounded_execution_envelope_record(
        record, resources=silent.resources
    )
    assert parsed == silent
    assert (
        _parse_bounded_execution_envelope_record(
            canonical_data(granted), resources=granted.resources
        ).max_excursion_calls
        == 1
    )


def _plan(tmp_path, *, tag=None, **host_extra):
    fixture = build_neutral_workflow_fixture(tmp_path / "fixture")
    store = RuntimeEventStore(
        tmp_path / "events" / "runtime.jsonl", session_id="session"
    )
    host = CommandCompiledToolHostV1(
        event_store=store,
        task_spec_sha256s=(fixture.public_context.task_spec_sha256,),
        approved_workspace=tmp_path / "preview",
        **fixture.host_inputs,
        **host_extra,
    )
    action = next(
        item
        for item in fixture.public_context.next_actions
        if item.tool_name == "plan_scientific_workflow"
    )
    fields = dict(action.fields)
    if tag is not None:
        node_id, digest = tag
        node = next(
            item
            for item in fields["calculation_nodes"]
            if item["node_id"] == node_id
        )
        node["excursion"] = digest
    return host.dispatch(
        turn_id="turn-1",
        tool_name="plan_scientific_workflow",
        arguments=fields,
    )


@pytest.mark.capability("rule:plan.excursion_grant")
def test_an_excursion_cites_a_recorded_anomaly_or_is_refused(tmp_path):
    envelope = _envelope(tmp_path, max_engine_calls=2, max_excursion_calls=1)
    with pytest.raises(ContractError, match="the host never recorded"):
        _plan(
            tmp_path / "a",
            tag=("node.hess", _ANOMALY),
            execution_resources=envelope.resources,
            bounded_execution_envelope=envelope,
        )


@pytest.mark.capability("rule:plan.excursion_grant")
def test_an_excursion_is_charged_to_its_own_line(tmp_path):
    seeded = {"prior_anomaly_observations": [{"receipt_sha256": _ANOMALY}]}
    # One plain node and one excursion: the engine line holds one call,
    # and without a granted line the excursion is refused.
    ungranted = _envelope(tmp_path / "u", max_engine_calls=1)
    with pytest.raises(ContractError, match="1 excursion nodes for 0"):
        _plan(
            tmp_path / "a",
            tag=("node.hess", _ANOMALY),
            execution_resources=ungranted.resources,
            bounded_execution_envelope=ungranted,
            **seeded,
        )
    granted = _envelope(
        tmp_path / "g", max_engine_calls=1, max_excursion_calls=1
    )
    plan = _plan(
        tmp_path / "b",
        tag=("node.hess", _ANOMALY),
        execution_resources=granted.resources,
        bounded_execution_envelope=granted,
        **seeded,
    )
    assert plan is not None
    # The goal's own remaining line bounds a woken cycle the same way.
    with pytest.raises(ContractError, match="1 excursion nodes for 0"):
        _plan(
            tmp_path / "c",
            tag=("node.hess", _ANOMALY),
            engine_calls_remaining=1,
            excursion_calls_remaining=0,
            **seeded,
        )


@pytest.mark.capability("rule:plan.excursion_grant")
def test_an_excursion_may_never_feed_the_deliverable(tmp_path):
    envelope = _envelope(tmp_path, max_engine_calls=1, max_excursion_calls=1)
    with pytest.raises(ContractError, match="feeds 'node.hess'"):
        _plan(
            tmp_path / "a",
            tag=("node.opt", _ANOMALY),
            execution_resources=envelope.resources,
            bounded_execution_envelope=envelope,
            prior_anomaly_observations=[{"receipt_sha256": _ANOMALY}],
        )


def _goal(**envelope_extra):
    body = {
        "schema_version": GOAL_SCHEMA_VERSION,
        "goal_id": "goal-excursion-01",
        "task_spec_sha256": "a" * 64,
        "scientific_identity_sha256": "b" * 64,
        "conditions": {
            "solvents": (),
            "thermochemistry": ((298.15, 1.0, None),),
        },
        "envelope": {
            "allowed_program_engines": (("orca", ("cpu",)),),
            "max_engine_calls": 6,
            "episode_wall_time_seconds": 10800.0,
            **envelope_extra,
        },
        "max_revisions": 5,
        "granted_by": "claude-owner-delegated-reviewer",
        "initial_review_sha256": "c" * 64,
        "created_at": "2026-09-03T00:00:00+00:00",
    }
    return GoalRecordV1(**body)


def test_the_grant_and_the_budget_never_lend_to_each_other(tmp_path):
    ledger = GoalLedger(tmp_path / "goal")
    goal = _goal(max_excursion_calls=2)
    ledger.create(goal)
    ledger.append(
        "run_recorded",
        {
            "engine_calls_consumed": 1,
            "excursion_calls_consumed": 1,
            "engine_wall_seconds": 100.0,
        },
    )
    budgets = ledger.budgets(ledger.load())
    assert budgets.engine_calls_remaining == 5
    assert budgets.excursion_calls_remaining == 1

    settings = "orca:\n  gas:\n    functional: b3lyp\n"
    review = {
        "execution_envelope": {
            "allowed_program_engines": (("orca", ("cpu",)),),
        },
        "scientific_plan": {
            "nodes": (
                {"node_id": "n1"},
                {"node_id": "n2", "excursion": _ANOMALY},
                {"node_id": "n3", "excursion": _ANOMALY},
            )
        },
        "node_reviews": tuple(
            {"node_id": node_id, "project_settings_text": settings}
            for node_id in ("n1", "n2", "n3")
        ),
    }
    verdict = admit_revision(
        goal=goal,
        budgets=budgets,
        revision_review=review,
        revision_scientific_identity_sha256="b" * 64,
        session_events_path=_wake_stream(tmp_path),
        previous_run_reference=_RUN,
        prior_outcome_evidence_hashes=("e" * 64,),
    )
    assert verdict.checks["engine_budget_remains"]
    assert not verdict.checks["excursion_budget_remains"]
    assert any("2 excursion calls with 1" in r for r in verdict.reasons)


def test_a_run_charges_an_excursion_launch_to_its_own_line(tmp_path):
    path = tmp_path / "events" / "runtime.jsonl"
    store = RuntimeEventStore(path, session_id="water-session")
    _, plan, _materialized, _approval, invocation = _reserve(store, tmp_path)
    receipt = build_program_execution_receipt(
        invocation,
        # A failed launch is still a launch: the line is charged by the
        # call, not by the verdict.
        execution_state="failed",
        exit_status=1,
        child_exit_status=1,
        engine_complete=False,
        validated=False,
        findings=("orca.result.normal_termination",),
        started_at="2026-09-03T00:00:00+00:00",
        finished_at="2026-09-03T00:00:05+00:00",
    )
    store.record_program_execution_receipt(
        turn_id="turn-1",
        workflow_id=plan.workflow_id,
        run_id="run.water-approval",
        receipt=receipt,
        excursion=True,
    )
    outcome = derive_run_outcome(read_run_events(path))
    assert outcome.engine_calls_consumed == 0
    assert outcome.excursion_calls_consumed == 1
    assert outcome.engine_wall_seconds == pytest.approx(5.0)


def test_the_launch_gate_counts_each_line_apart(tmp_path):
    """At launch, receipts of each kind are counted against their own
    line: an excursion never spends an engine call, and an exhausted
    engine line still admits the granted excursion."""

    from types import SimpleNamespace

    envelope = _envelope(tmp_path, max_engine_calls=1, max_excursion_calls=1)
    host = object.__new__(CommandCompiledToolHostV1)
    host.bounded_execution_envelope = envelope
    host.execution_resources = envelope.resources
    host.execution_receipts = {}
    host._bounded_execution_started_at = __import__("time").monotonic()
    excursions = frozenset({"probe"})

    assert host._require_bounded_launch_budget(excursion_node_ids=excursions)
    host.execution_receipts["opt"] = SimpleNamespace(validated=True)
    with pytest.raises(ContractError, match="engine-call budget exhausted"):
        host._require_bounded_launch_budget(excursion_node_ids=excursions)
    assert host._require_bounded_launch_budget(
        excursion=True, excursion_node_ids=excursions
    )
    host.execution_receipts["probe"] = SimpleNamespace(validated=True)
    with pytest.raises(ContractError, match="excursion grant exhausted"):
        host._require_bounded_launch_budget(
            excursion=True, excursion_node_ids=excursions
        )
    # The excursion receipt did not touch the engine line's count.
    with pytest.raises(ContractError, match="engine-call budget exhausted"):
        host._require_bounded_launch_budget(excursion_node_ids=excursions)


def test_the_bindings_the_launch_reads_carry_the_tag():
    """The one-shot approval carries the node bindings the launch gate
    reads; the frozen approval never did (void window 1)."""

    from chemsmart.agent.execution import (
        FrozenWorkflowApprovalV1,
        WorkflowExecutionApprovalV1,
    )

    assert "node_bindings" in WorkflowExecutionApprovalV1.__dataclass_fields__
    assert "node_bindings" not in FrozenWorkflowApprovalV1.__dataclass_fields__
    assert "excursion" in ApprovedNodeBindingV1.__dataclass_fields__
