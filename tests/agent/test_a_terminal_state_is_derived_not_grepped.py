"""How a node ended used to live in free text: a non-converged scan step
and a SHARK abort arrived as one blob, and an interrupted engine was an
empty rule-id tuple beside an English sentence nobody persisted.

The terminal vocabulary is derived on read from the sealed events plus
the artifact's own parser facts -- nothing new is written, so the
provenance of a terminal state is the event hashes and artifact digests
the derivation read. These tests drive the derivation over streams built
by the real launch fence and receipt writer, never hand-forged events.
"""

import pytest

from chemsmart.agent.execution import build_program_execution_receipt
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.terminal_states import (
    NODE_TERMINAL_STATES,
    NodeTerminalStateV1,
    derive_run_outcome,
    read_run_events,
)

from .test_runtime_v2_launch_fence import _reserve


def _stream_with_receipt(tmp_path, *, findings, execution_state="failed"):
    path = tmp_path / "events" / "runtime.jsonl"
    store = RuntimeEventStore(path, session_id="water-session")
    _, plan, _materialized, _approval, invocation = _reserve(store, tmp_path)
    receipt = build_program_execution_receipt(
        invocation,
        execution_state=execution_state,
        exit_status=1 if execution_state == "failed" else 0,
        child_exit_status=1 if execution_state == "failed" else 0,
        engine_complete=execution_state != "failed",
        validated=execution_state == "validated",
        findings=tuple(findings),
        started_at="2026-08-04T00:00:00+00:00",
        finished_at="2026-08-04T00:00:05+00:00",
    )
    store.record_program_execution_receipt(
        turn_id="turn-1",
        workflow_id=plan.workflow_id,
        run_id="run.water-approval",
        receipt=receipt,
    )
    return path


def test_a_timeout_is_its_own_ending_with_budget_facts(tmp_path):
    path = _stream_with_receipt(
        tmp_path,
        findings=(
            "execution.process.nonzero_or_unknown",
            "execution.process.timeout",
        ),
    )
    outcome = derive_run_outcome(read_run_events(path))
    assert outcome.workflow_id == "water-workflow"
    assert outcome.engine_calls_consumed == 1
    assert outcome.engine_wall_seconds == pytest.approx(5.0)
    (node,) = outcome.nodes
    assert node.state == "timeout_terminated"
    assert node.wall_seconds == pytest.approx(5.0)
    assert node.evidence_event_hashes, "the citation must not be empty"


def test_an_unconfirmed_timeout_reads_ambiguous(tmp_path):
    path = _stream_with_receipt(
        tmp_path,
        findings=(
            "execution.process.timeout",
            "execution.process.termination_ambiguous",
        ),
    )
    (node,) = derive_run_outcome(read_run_events(path)).nodes
    assert node.state == "timeout_ambiguous"


def test_a_human_interrupt_reads_as_its_own_ending(tmp_path):
    path = _stream_with_receipt(
        tmp_path, findings=("execution.process.external_signal",)
    )
    (node,) = derive_run_outcome(read_run_events(path)).nodes
    assert node.state == "external_signal_terminated"


def test_a_reservation_without_a_receipt_is_interrupted_mid_engine(
    tmp_path,
):
    path = tmp_path / "events" / "runtime.jsonl"
    store = RuntimeEventStore(path, session_id="water-session")
    _reserve(store, tmp_path)
    (node,) = derive_run_outcome(read_run_events(path)).nodes
    assert node.state == "interrupted_mid_engine"


def test_a_plain_failure_is_native_not_invented(tmp_path):
    path = _stream_with_receipt(
        tmp_path, findings=("execution.process.nonzero_or_unknown",)
    )
    (node,) = derive_run_outcome(read_run_events(path)).nodes
    assert node.state == "failed_native"
    assert node.converged is None, (
        "no artifact was readable, so convergence stays absent -- "
        "never manufactured"
    )


def test_the_scan_classification_needs_the_observed_facts():
    from chemsmart.agent.terminal_states import _classify_failure

    assert (
        _classify_failure(
            jobtype="scan",
            findings=("execution.process.nonzero_or_unknown",),
            native_class="native_runtime",
            converged=False,
            reached=2,
            planned=12,
        )
        == "failed_nonconverged_scan_step"
    )
    assert (
        _classify_failure(
            jobtype="opt",
            findings=("orca.result.optimization_not_converged",),
            native_class="",
            converged=False,
            reached=None,
            planned=None,
        )
        == "failed_nonconverged_geometry"
    )
    assert (
        _classify_failure(
            jobtype="sp",
            findings=(),
            native_class="scf_convergence",
            converged=None,
            reached=None,
            planned=None,
        )
        == "failed_nonconverged_scf"
    )


def test_a_withdrawn_grant_survives_the_process(tmp_path):
    """The executor wrote cancelled into an in-memory record only, so
    a human's withdrawal derived as not_launched afterwards -- the
    withdrawn grant and a node that never came up shared one word.
    The durable vocabulary now carries it: a pending node cancels, a
    launched node never does, and the workflow summary word follows."""

    from chemsmart.agent.execution import (
        ContractError,
        build_workflow_run_state,
        transition_workflow_node,
    )

    from .test_runtime_v2_launch_fence import _frontier

    plan, _materialized, approval, _invocation = _frontier(tmp_path)
    run_state = build_workflow_run_state(
        plan=plan,
        approval=approval,
        run_id="run.water-approval",
        approval_consumed=True,
    )
    (row,) = run_state.nodes
    assert row.state == "pending"
    cancelled = transition_workflow_node(
        run_state,
        node_id="sp-initial",
        new_state="cancelled",
        plan=plan,
        failure_rule_ids=("execution.cancelled.human",),
        timestamp="2026-08-04T00:00:01+00:00",
    )
    (node,) = cancelled.nodes
    assert node.state == "cancelled"
    assert node.failure_rule_ids == ("execution.cancelled.human",)
    assert cancelled.state == "cancelled"
    assert cancelled.finished_at

    running = transition_workflow_node(
        run_state,
        node_id="sp-initial",
        new_state="running",
        plan=plan,
        invocation_sha256="5" * 64,
        timestamp="2026-08-04T00:00:01+00:00",
    )
    with pytest.raises(ContractError, match="invalid workflow node state"):
        transition_workflow_node(
            running,
            node_id="sp-initial",
            new_state="cancelled",
            plan=plan,
            timestamp="2026-08-04T00:00:02+00:00",
        )


def test_every_state_the_derivation_can_emit_is_declared():
    with pytest.raises(ValueError, match="unsupported node terminal"):
        NodeTerminalStateV1(
            node_id="n",
            program="orca",
            jobtype="sp",
            state="made_up",
        )
    assert "cancelled" in NODE_TERMINAL_STATES


def test_a_second_run_cannot_even_be_forged_into_a_stream(tmp_path):
    """Defense in depth, from the outside in.

    The launch fence refuses a second workflow run into a recorded
    directory outright, so a two-run stream cannot be produced by any
    production writer; and a doctored reservation event fails its own
    record digest at construction, before the run-record map could ever
    hold two entries. The derivation's exactly-one guard therefore sits
    behind two working fences -- pinned here so weakening either one
    fails a test.
    """

    import dataclasses

    from chemsmart.agent._contracts import ContractError

    path = tmp_path / "events" / "runtime.jsonl"
    store = RuntimeEventStore(path, session_id="water-session")
    _reserve(store, tmp_path)
    events = read_run_events(path)
    reservation = next(
        event
        for event in events
        if event.kind == "workflow_node_launch_reserved"
    )
    # The forge dies at event *construction*: the typed event validates
    # its reservation record's own digest, so a doctored run id cannot
    # even become an event, let alone reach the run-record map.
    with pytest.raises(ContractError, match="digest mismatch"):
        dataclasses.replace(
            reservation,
            sequence=reservation.sequence + len(events),
            payload={
                **reservation.payload,
                "run_id": "run.other",
                "record": {
                    **(reservation.payload.get("record") or {}),
                    "run_id": "run.other",
                },
            },
        )
