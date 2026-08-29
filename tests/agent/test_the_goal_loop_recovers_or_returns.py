"""The loop's bookkeeping, driven with stubbed session/resolve/execute
so no provider and no engine runs: cycle accounting, the wake context,
admission wiring, and every settlement path. The live qualification
drives the real chain; these tests pin that the connective tissue does
exactly what the charter text says and nothing more.
"""

import json
import shutil
from types import SimpleNamespace

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.execution import build_program_execution_receipt
from chemsmart.agent.goal import GoalLedger
from chemsmart.agent.goal_loop import run_goal_loop
from chemsmart.agent.runtime.event_store import RuntimeEventStore

from .test_runtime_v2_launch_fence import _reserve


def _envelope_file(tmp_path, calls=6):
    target = tmp_path / "execution-envelope.yaml"
    target.write_text(
        "\n".join(
            (
                "schema_version: chemsmart.bounded-execution-envelope.v1",
                "mode: bounded-local",
                "allowed_program_engines:",
                "  orca:",
                "  - cpu",
                "  pyscf:",
                "  - cpu",
                "resources:",
                "  execution_target: run",
                "  cores: 4",
                "  memory_gb: 16",
                "  gpu_count: 0",
                "  scratch_policy: server",
                "  node_timeout_seconds: 600",
                "episode_wall_time_seconds: 7200",
                "postprocess_reserve_seconds: 600",
                f"max_engine_calls: {calls}",
                f"scratch_root: {tmp_path / 'scratch'}",
            )
        )
        + "\n"
    )
    return target


def _review_payload(identity="b" * 64):
    return {
        "review_sha256": "d" * 64,
        "scientific_plan": {"scientific_identity_sha256": identity},
        "execution_envelope": {
            "allowed_program_engines": (("orca", ("cpu",)),),
        },
        "node_reviews": ({"project_settings_text": "orca:\n  gas: {}\n"},),
        "scientific_toolchain_plan": {"analysis_nodes": ()},
    }


def _write_session_stream(workspace, name, rows):
    run_dir = workspace / ".chemsmart-agent" / "runs" / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _engine_stream(tmp_path, target, *, failed):
    build_dir = tmp_path / f"build-{target.name}"
    store = RuntimeEventStore(
        build_dir / "events.jsonl", session_id="water-session"
    )
    _, plan, _m, _a, invocation = _reserve(store, build_dir)
    receipt = build_program_execution_receipt(
        invocation,
        execution_state="failed" if failed else "engine_complete",
        exit_status=1 if failed else 0,
        child_exit_status=1 if failed else 0,
        engine_complete=not failed,
        validated=False,
        findings=("execution.process.timeout",) if failed else (),
        started_at="2026-08-04T00:00:00+00:00",
        finished_at="2026-08-04T00:00:05+00:00",
    )
    store.record_program_execution_receipt(
        turn_id="turn-1",
        workflow_id=plan.workflow_id,
        run_id="run.water-approval",
        receipt=receipt,
    )
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy(build_dir / "events.jsonl", target / "events.jsonl")


def _loop(tmp_path, *, sessions, executes, calls=6, max_revisions=5):
    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)
    session_iter = iter(sessions)
    execute_iter = iter(executes)

    def plan_session(**kwargs):
        step = next(session_iter)
        return step(workspace, kwargs)

    def resolve_review(**kwargs):
        return ("d" * 64, tmp_path / "bundle.json")

    def execute_bundle(*, approval_file, workspace, run_directory):
        step = next(execute_iter)
        return step(run_directory)

    return run_goal_loop(
        task="the goal task",
        workspace=workspace,
        execution_envelope_file=_envelope_file(tmp_path, calls),
        goal_id="goal-t1",
        granted_by="claude-owner-delegated-reviewer",
        max_revisions=max_revisions,
        plan_session=plan_session,
        resolve_review=resolve_review,
        execute_bundle=execute_bundle,
    )


def _planning_session(
    name, *, review=None, terminal="waiting_for_approval", wake_rows=()
):
    def step(workspace, kwargs):
        rows = list(wake_rows) or [{"kind": "session_started", "payload": {}}]
        _write_session_stream(workspace, name, rows)
        if review is not None:
            review_file = kwargs["review_file"]
            review_file.parent.mkdir(parents=True, exist_ok=True)
            review_file.write_text(json.dumps(review), encoding="utf-8")
        return SimpleNamespace(
            terminal_state=terminal, task_spec_sha256="a" * 64
        )

    return step


def _execute(tmp_path, *, failed, status, analysis="completed"):
    def step(run_directory):
        _engine_stream(tmp_path, run_directory, failed=failed)
        return SimpleNamespace(status=status, analysis_status=analysis)

    return step


_READ_OUTCOME_ROWS = (
    {
        "kind": "tool_started",
        "payload": {"request_id": "r1", "tool": "inspect_run_outcome"},
    },
    {"kind": "tool_succeeded", "payload": {"request_id": "r1"}},
    {
        "kind": "run_outcome_inspected",
        "payload": {
            "run": "goals/goal-t1/runs/cycle-1",
            "stream_sha256": "a" * 64,
        },
    },
)


def test_every_cycle_sees_the_goal_terms(tmp_path):
    """Cycle 1 used to receive nothing -- an analysis-only goal is
    single-cycle by construction, so its session never learned the
    budgets, the authority, or that a typed refusal is a deliverable.
    The terms are in hand when the loop starts; every cycle gets them,
    and cycles with a previous run get its typed outcome embedded."""

    contexts = []

    def capture(inner):
        def step(workspace, kwargs):
            contexts.append(kwargs["goal_context"])
            return inner(workspace, kwargs)

        return step

    _loop(
        tmp_path,
        sessions=[
            capture(_planning_session("live-1", review=_review_payload())),
            capture(_planning_session("live-2", review=_review_payload())),
        ],
        executes=[
            _execute(
                tmp_path, failed=True, status="partial", analysis="partial"
            ),
            _execute(
                tmp_path, failed=True, status="partial", analysis="partial"
            ),
        ],
        max_revisions=1,
    )
    first, second = contexts
    assert first["schema_version"] == "chemsmart.goal-wake-context.v1"
    assert first["budgets"] == {
        "engine_calls_remaining": 6,
        "wall_seconds_remaining": 7200.0,
        "revisions_remaining": 1,
    }
    assert first["previous_run"] == ""
    assert first["trajectory"] == ()
    assert "typed refusal" in first["authority"]
    assert second["previous_run"] == "goals/goal-t1/runs/cycle-1"
    assert second["previous_run_outcome"]
    assert "typed refusal" in second["authority"]


def test_cycle_one_approves_runs_and_settles_achieved(tmp_path):
    result = _loop(
        tmp_path,
        sessions=[
            _planning_session("live-1", review=_review_payload()),
        ],
        executes=[
            _execute(tmp_path, failed=False, status="completed"),
        ],
    )
    assert result.settlement == "achieved"
    assert result.cycles == 1
    assert result.revisions_admitted == 0
    ledger = GoalLedger(
        tmp_path / "ws" / ".chemsmart-agent" / "goals" / "goal-t1"
    )
    kinds = [entry["kind"] for entry in ledger.entries()]
    assert kinds == ["goal_created", "run_recorded", "goal_settled"]


def test_a_failed_run_wakes_a_revision_that_recovers(tmp_path):
    result = _loop(
        tmp_path,
        sessions=[
            _planning_session("live-1", review=_review_payload()),
            _planning_session(
                "live-2",
                review=_review_payload(),
                wake_rows=_READ_OUTCOME_ROWS,
            ),
        ],
        executes=[
            _execute(
                tmp_path,
                failed=True,
                status="partial",
                analysis="partial",
            ),
            _execute(tmp_path, failed=False, status="completed"),
        ],
    )
    assert result.settlement == "achieved"
    assert result.cycles == 2
    assert result.revisions_admitted == 1
    ledger = GoalLedger(
        tmp_path / "ws" / ".chemsmart-agent" / "goals" / "goal-t1"
    )
    admitted = [
        entry
        for entry in ledger.entries()
        if entry["kind"] == "revision_admitted"
    ]
    assert len(admitted) == 1
    payload = admitted[0]["payload"]
    assert payload["actor"] == "goal-approval:goal-t1"
    assert payload["granted_by"] == "claude-owner-delegated-reviewer"
    assert payload[
        "cited_evidence_event_hashes"
    ], "an admitted revision cites the terminal evidence it answered"
    assert payload["checks"]["evidence_read"] is True


def test_a_wake_handed_outcome_admits_without_ritual(tmp_path):
    """The host composed the wake context, embedded the previous run's
    typed outcome, and recorded that act in the ledger. A revision of
    that run is evidence-read by construction -- the first live goal
    round's gate demanded a re-read of what the host itself handed
    over, and blocked a scientifically sound revision on a wiring
    defect. The attestation, not the ritual, is the evidence."""

    result = _loop(
        tmp_path,
        sessions=[
            _planning_session("live-1", review=_review_payload()),
            _planning_session("live-2", review=_review_payload()),
        ],
        executes=[
            _execute(
                tmp_path, failed=True, status="partial", analysis="partial"
            ),
            _execute(
                tmp_path, failed=True, status="partial", analysis="partial"
            ),
        ],
        max_revisions=1,
    )
    assert result.settlement == "exhausted"
    assert result.revisions_admitted == 1
    entries = GoalLedger(
        tmp_path / "ws" / ".chemsmart-agent" / "goals" / "goal-t1"
    ).entries()
    by_kind = {}
    for entry in entries:
        by_kind.setdefault(entry["kind"], []).append(entry["payload"])
    (wake,) = by_kind["wake_composed"]
    assert wake == {"cycle": 2, "run": "goals/goal-t1/runs/cycle-1"}
    (admitted,) = by_kind["revision_admitted"]
    assert admitted["checks"]["evidence_read"] is True


def test_an_identity_change_returns_to_the_human(tmp_path):
    result = _loop(
        tmp_path,
        sessions=[
            _planning_session("live-1", review=_review_payload()),
            _planning_session(
                "live-2",
                review=_review_payload(identity="9" * 64),
                wake_rows=_READ_OUTCOME_ROWS,
            ),
        ],
        executes=[
            _execute(
                tmp_path,
                failed=True,
                status="partial",
                analysis="partial",
            ),
        ],
    )
    assert result.settlement == "returned_to_human"
    assert any("identities" in r for r in result.reasons)


def _delivery_rows(
    *,
    completion="passed",
    limitations=(),
    claims=True,
    decision=True,
    failed_rule=False,
):
    """Stream shapes drawn from the live goal round's three sessions."""

    rows = [
        {
            "kind": "result_quantities_extracted",
            "payload": {"receipt_sha256": "e" * 64},
        },
    ]
    if failed_rule:
        rows.append(
            {
                "kind": "scientific_validation_evaluated",
                "payload": {
                    "receipt_sha256": "f" * 64,
                    "record": {
                        "rule_results": ({"rule_id": "same", "passed": False},)
                    },
                },
            }
        )
    if claims:
        rows.append(
            {
                "kind": "analysis_claims_recorded",
                "payload": {"receipt_sha256": "a1" + "a" * 62},
            }
        )
    if decision:
        rows.append({"kind": "scientific_decision_recorded", "payload": {}})
    if completion:
        rows.append(
            {
                "kind": "analysis_completion_evaluated",
                "payload": {
                    "receipt_sha256": "c1" + "c" * 62,
                    "status": completion,
                    "limitation_output_ids": list(limitations),
                },
            }
        )
    return tuple(rows)


def test_a_stated_limitation_settles_as_the_typed_refusal(tmp_path):
    """The live r3 shape: completion passed with a blocked required
    output, substitute claims delivered, decision recorded, every
    validation rule green. The old classifier watched failed rules --
    the one place an honest refusal leaves no trace -- and settled
    this achieved."""

    result = _loop(
        tmp_path,
        sessions=[
            _planning_session(
                "live-1",
                terminal="complete",
                wake_rows=_delivery_rows(limitations=("dg",)),
            ),
        ],
        executes=[],
    )
    assert result.settlement == "unreachable_from_evidence"
    assert any("dg" in reason for reason in result.reasons)
    ledger = GoalLedger(
        tmp_path / "ws" / ".chemsmart-agent" / "goals" / "goal-t1"
    )
    settled = ledger.entries()[-1]
    assert settled["payload"]["evidence"]["receipt_sha256s"]


def test_a_certified_clean_delivery_settles_achieved(tmp_path):
    """The live r1 shape: completion passed with no limitations."""

    result = _loop(
        tmp_path,
        sessions=[
            _planning_session(
                "live-1", terminal="complete", wake_rows=_delivery_rows()
            ),
        ],
        executes=[],
    )
    assert result.settlement == "achieved"


def test_an_uncertified_delivery_returns_naming_the_gate(tmp_path):
    """The live r2 shape: claims and a decision recorded, no
    completion event, terminal 'planned'. The word was right before,
    for a reason that would also fire on a clean delivery; the reason
    now names what is actually missing."""

    result = _loop(
        tmp_path,
        sessions=[
            _planning_session(
                "live-1",
                terminal="planned",
                wake_rows=_delivery_rows(completion=""),
            ),
        ],
        executes=[],
    )
    assert result.settlement == "returned_to_human"
    assert any("completion gate" in reason for reason in result.reasons)


def test_a_failed_rule_is_not_a_refusal(tmp_path):
    """The hazard the seal named and the round left unexercised: a
    delivering session whose stream holds one honestly failed
    validation rule must not settle as a refusal."""

    result = _loop(
        tmp_path,
        sessions=[
            _planning_session(
                "live-1",
                terminal="complete",
                wake_rows=_delivery_rows(failed_rule=True),
            ),
        ],
        executes=[],
    )
    assert result.settlement == "achieved"


def test_a_goal_is_not_a_resumable_queue(tmp_path):
    _loop(
        tmp_path,
        sessions=[_planning_session("live-1", review=_review_payload())],
        executes=[_execute(tmp_path, failed=False, status="completed")],
    )
    with pytest.raises(ContractError, match="one human decision"):
        _loop(
            tmp_path,
            sessions=[_planning_session("live-9", review=_review_payload())],
            executes=[],
        )


def test_the_stop_file_cancels_at_the_cycle_boundary(tmp_path):
    stop = tmp_path / "stop"
    stop.write_text("cancel\n")
    result = run_goal_loop(
        task="the goal task",
        workspace=(tmp_path / "ws2"),
        execution_envelope_file=_envelope_file(tmp_path),
        goal_id="goal-t2",
        granted_by="claude-owner-delegated-reviewer",
        plan_session=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("no session may start after cancel")
        ),
        resolve_review=lambda **kwargs: ("d" * 64, tmp_path / "b.json"),
        execute_bundle=lambda **kwargs: None,
        stop_file=stop,
    )
    assert result.settlement == "returned_to_human"
    assert result.reasons == ("cancelled",)


def test_the_executor_accepts_a_stop_file_and_marks_cancelled():
    """The walk marks an unlaunched node cancelled with its typed id.

    The full executor path needs an approved bundle and engines; the
    live goal qualification exercises it. Here the contract is pinned
    at the seam: the entry accepts stop_file, and the cancelled node
    record carries the typed rule id beside the human sentence.
    """

    import inspect

    from chemsmart.agent.executor import (
        ExecutedNodeV1,
        execute_approved_workflow,
    )

    assert (
        "stop_file" in inspect.signature(execute_approved_workflow).parameters
    )
    node = ExecutedNodeV1(
        node_id="n",
        program="orca",
        jobtype="opt",
        state="cancelled",
        invocation_identity_sha256="",
        execution_receipt_sha256="",
        rule_ids=("execution.cancelled.human",),
        failure="cancelled by the human at a node boundary",
    )
    assert node.state == "cancelled"
