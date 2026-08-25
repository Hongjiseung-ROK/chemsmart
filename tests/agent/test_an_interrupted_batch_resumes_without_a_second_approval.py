"""A consumed, incomplete run may continue; everything else still refuses.

One-shot consumption protects one thing: a spent approval must never
authorize MORE work.  A continuation authorizes none -- the per-node
launch fence replays terminal receipts instead of re-executing and the
engine-call budget counts replays -- so the recorded decision may finish
across invocations.  Admission is deliberately narrow: the consumption
ledger must have consumed this exact bundle, the run directory's durable
stream must record a run of this approval, and that run must be
genuinely incomplete.  A fresh run directory is a second independent
execution (refused); a completed approval is not re-runnable (refused);
and there is no new approval, no re-display, and no second control
plane anywhere in the path.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.executor import ApprovedWorkflowExecutor
from chemsmart.agent.live_session import (
    continue_workflow_execution_approval_bundle,
)
from chemsmart.agent.runtime.event_store import (
    ExecutionBundleAlreadyConsumedError,
    RuntimeEventStore,
)
from chemsmart.agent.runtime.events import EventKind


def _bundle(workspace):
    return SimpleNamespace(
        bundle_sha256="1" * 64,
        review_sha256="2" * 64,
        workflow_approval=SimpleNamespace(
            approval_id="approval-batch",
            workflow_id="batch",
            workspace=str(workspace),
        ),
        frozen_workflow_approval=SimpleNamespace(
            approved_node_ids=("opt-a", "opt-b"),
        ),
    )


def _ledger(tmp_path):
    return RuntimeEventStore(
        tmp_path / "consumption-events.jsonl",
        session_id="approval-approval-batch",
    )


def test_the_second_claim_raises_the_typed_refusal(tmp_path):
    ledger = _ledger(tmp_path)
    bundle = _bundle(tmp_path)
    ledger.claim_execution_bundle(turn_id="t1", bundle=bundle)

    with pytest.raises(
        ExecutionBundleAlreadyConsumedError, match="already been consumed"
    ):
        ledger.claim_execution_bundle(turn_id="t2", bundle=bundle)


def test_a_continuation_without_a_prior_claim_is_refused(tmp_path):
    ledger = _ledger(tmp_path)

    with pytest.raises(ContractError, match="never claimed"):
        ledger.continue_execution_bundle(
            turn_id="t1",
            bundle=_bundle(tmp_path),
            run_id="run.approval-batch",
            remaining_node_ids=("opt-b",),
        )


def test_each_continuation_is_its_own_recorded_event(tmp_path):
    ledger = _ledger(tmp_path)
    bundle = _bundle(tmp_path)
    ledger.claim_execution_bundle(turn_id="t1", bundle=bundle)

    ledger.continue_execution_bundle(
        turn_id="t2",
        bundle=bundle,
        run_id="run.approval-batch",
        remaining_node_ids=("opt-b", "opt-a"),
    )
    ledger.continue_execution_bundle(
        turn_id="t3",
        bundle=bundle,
        run_id="run.approval-batch",
        remaining_node_ids=("opt-b",),
    )

    continued = [
        event
        for event in ledger.read_events()
        if event.kind == EventKind.EXECUTION_BUNDLE_CONTINUED.value
    ]
    assert len(continued) == 2
    assert continued[0].payload["remaining_node_ids"] == ["opt-a", "opt-b"]
    assert continued[1].payload["remaining_node_ids"] == ["opt-b"]
    assert continued[0].payload["status"] == "resumed"


def _frontier_store(node_states):
    nodes = tuple(
        SimpleNamespace(node_id=node_id, state=state)
        for node_id, state in node_states.items()
    )
    run_state = None if node_states is None else SimpleNamespace(nodes=nodes)
    return SimpleNamespace(
        workflow_frontier=lambda **_kwargs: SimpleNamespace(
            run_state=run_state
        )
    )


def _claimed_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bundle = _bundle(workspace)
    ledger_root = (
        workspace / ".chemsmart-agent" / "approvals" / "approval-batch"
    )
    ledger_root.mkdir(parents=True)
    RuntimeEventStore(
        ledger_root / "consumption-events.jsonl",
        session_id="approval-approval-batch",
    ).claim_execution_bundle(turn_id="t1", bundle=bundle)
    return workspace, bundle, ledger_root


def test_an_incomplete_recorded_run_is_admitted_naming_the_remainder(
    tmp_path,
):
    workspace, bundle, ledger_root = _claimed_workspace(tmp_path)
    store = _frontier_store({"opt-a": "validated", "opt-b": "pending"})

    continue_workflow_execution_approval_bundle(
        bundle, workspace=workspace, run_event_store=store
    )

    ledger = RuntimeEventStore(
        ledger_root / "consumption-events.jsonl",
        session_id="approval-approval-batch",
    )
    continued = [
        event
        for event in ledger.read_events()
        if event.kind == EventKind.EXECUTION_BUNDLE_CONTINUED.value
    ]
    assert len(continued) == 1
    assert continued[0].payload["remaining_node_ids"] == ["opt-b"]


def test_a_fresh_run_directory_is_a_second_execution_and_refuses(tmp_path):
    workspace, bundle, _ledger_root = _claimed_workspace(tmp_path)
    empty = SimpleNamespace(
        workflow_frontier=lambda **_kwargs: SimpleNamespace(run_state=None)
    )

    with pytest.raises(ContractError, match="original run directory"):
        continue_workflow_execution_approval_bundle(
            bundle, workspace=workspace, run_event_store=empty
        )


def test_a_completed_approval_is_not_re_runnable(tmp_path):
    workspace, bundle, _ledger_root = _claimed_workspace(tmp_path)
    store = _frontier_store({"opt-a": "validated", "opt-b": "validated"})

    with pytest.raises(ContractError, match="not re-runnable"):
        continue_workflow_execution_approval_bundle(
            bundle, workspace=workspace, run_event_store=store
        )


def test_the_executor_routes_only_the_typed_refusal_to_continuation(
    tmp_path, monkeypatch
):
    from chemsmart.agent import live_session

    calls = []
    monkeypatch.setattr(
        live_session,
        "claim_workflow_execution_approval_bundle",
        lambda bundle, workspace: (_ for _ in ()).throw(
            ExecutionBundleAlreadyConsumedError("already been consumed")
        ),
    )
    monkeypatch.setattr(
        live_session,
        "continue_workflow_execution_approval_bundle",
        lambda bundle, *, workspace, run_event_store: calls.append(
            (bundle, workspace, run_event_store)
        ),
    )
    executor = object.__new__(ApprovedWorkflowExecutor)
    executor.execution_bundle = SimpleNamespace(
        node_review=lambda node_id: SimpleNamespace()
    )
    executor.host = SimpleNamespace(
        verify_reviewed_real_execution_argv=lambda **_kwargs: None,
        event_store=SimpleNamespace(),
    )
    executor.approval_workspace = tmp_path
    executor.claim_workspace_bundle = True
    executor._bundle_claimed = False

    executor._verify_launch_and_claim_once(
        node_id="opt-a", invocation_sha256="3" * 64
    )

    assert len(calls) == 1
    assert executor._bundle_claimed is True

    # An ordinary refusal (not the typed already-consumed) must NOT fall
    # through to continuation.
    monkeypatch.setattr(
        live_session,
        "claim_workflow_execution_approval_bundle",
        lambda bundle, workspace: (_ for _ in ()).throw(
            ContractError("execution bundle targets another workspace")
        ),
    )
    executor._bundle_claimed = False
    with pytest.raises(ContractError, match="another workspace"):
        executor._verify_launch_and_claim_once(
            node_id="opt-a", invocation_sha256="3" * 64
        )
    assert len(calls) == 1
