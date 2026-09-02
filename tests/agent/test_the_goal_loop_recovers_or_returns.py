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
from chemsmart.agent.driver import run_goal_loop
from chemsmart.agent.execution import build_program_execution_receipt
from chemsmart.agent.goal import GoalLedger
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


def _engine_stream(
    tmp_path, target, *, failed, findings=("execution.process.timeout",)
):
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
        findings=tuple(findings) if failed else (),
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
    assert "attempt to refute" in first["authority"]
    assert first["deliverables"] == {
        "delivered_quantity_ids": (),
        "limitation_output_ids": (),
        "doubted_quantity_ids": (),
        "unanswered_failed_verdicts": (),
        "stale_quantity_ids": (),
        "unclaimed_output_ids": (),
    }
    assert second["previous_run"] == "goals/goal-t1/runs/cycle-1"
    assert second["previous_run_outcome"]
    assert "typed refusal" in second["authority"]
    assert "attempt to refute" in second["authority"]
    # The wake states what the previous run's own stream delivered --
    # here an engine failure with no claims, so every list is empty but
    # the record is present for the session to read.
    assert set(second["deliverables"]) == {
        "delivered_quantity_ids",
        "limitation_output_ids",
        "doubted_quantity_ids",
        # A host-rendered verdict saying a delivered structure is not
        # what the task required now reaches the wake beside what was
        # delivered: it is exactly the gap the next action should follow.
        "unanswered_failed_verdicts",
        # And beside it, the numbers that verdict took down with it --
        # rendered from the rejected result, sound arithmetic, no
        # structure left underneath.
        "stale_quantity_ids",
        # And what the host computed and no claim ever showed a reader.
        "unclaimed_output_ids",
    }


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
    claim_source="",
    doubt_ref="",
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
        claims_payload = {"receipt_sha256": "a1" + "a" * 62}
        if claim_source:
            claims_payload["record"] = {
                "claims": (
                    {
                        "source_receipt_sha256": claim_source,
                        "quantity_id": "dg_solv",
                    },
                )
            }
        rows.append(
            {
                "kind": "analysis_claims_recorded",
                "payload": claims_payload,
            }
        )
    if decision:
        decision_payload = {}
        if doubt_ref:
            decision_payload["record"] = {
                "evidence_refs": ("doubt:" + doubt_ref,)
            }
        rows.append(
            {
                "kind": "scientific_decision_recorded",
                "payload": decision_payload,
            }
        )
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


def test_a_claim_from_a_doubted_receipt_returns_to_the_human(tmp_path):
    """The r3 residue: a session wrote the correct doubt and claimed
    the doubted number anyway. Typed as doubt:{receipt}, the settlement
    returns the number to the human even when the completion certified
    before the decision landed -- the intersection is computed from the
    stream, not from the completion word."""

    result = _loop(
        tmp_path,
        sessions=[
            _planning_session(
                "live-1",
                terminal="complete",
                wake_rows=_delivery_rows(
                    claim_source="e" * 64, doubt_ref="e" * 64
                ),
            ),
        ],
        executes=[],
    )
    assert result.settlement == "returned_to_human"
    assert any("dg_solv" in reason for reason in result.reasons)


def test_a_doubt_about_an_unclaimed_receipt_changes_nothing(tmp_path):
    result = _loop(
        tmp_path,
        sessions=[
            _planning_session(
                "live-1",
                terminal="complete",
                wake_rows=_delivery_rows(
                    claim_source="e" * 64, doubt_ref="9" * 64
                ),
            ),
        ],
        executes=[],
    )
    assert result.settlement == "achieved"


def test_the_wake_deliverables_come_from_the_previous_runs_stream(tmp_path):
    """Names quantities and stated limitations, never values: the wake
    session sees what already stands delivered, what the chain declared
    it could not produce, and what its own decisions doubt."""

    from chemsmart.agent.driver import (
        _analysis_delivery,
        _deliverables_record,
    )

    workspace = tmp_path / "ws"
    _write_session_stream(
        workspace,
        "cycle-1",
        _delivery_rows(
            limitations=("dg",),
            claim_source="e" * 64,
            doubt_ref="e" * 64,
        ),
    )
    record = _deliverables_record(
        _analysis_delivery(
            workspace
            / ".chemsmart-agent"
            / "runs"
            / "cycle-1"
            / "events.jsonl"
        )
    )

    assert record == {
        "delivered_quantity_ids": ("dg_solv",),
        "limitation_output_ids": ("dg",),
        "doubted_quantity_ids": ("dg_solv",),
        "unanswered_failed_verdicts": (),
        "stale_quantity_ids": (),
        "unclaimed_output_ids": (),
    }


def test_goal_terms_are_restated_in_the_recency_slot(tmp_path):
    """Alphabetical canonical JSON lands the goal block mid-context --
    the attention trough. A goal session's coordinator message now ends
    with the goal terms restated verbatim; a plain session's message
    shape is untouched."""

    from chemsmart.agent.live_session import _coordinator_base_messages

    goal = {"goal_id": "goal-t1", "budgets": {"engine_calls_remaining": 2}}
    with_goal = _coordinator_base_messages(
        context={"task": "t", "goal": goal},
        approved_workflow=None,
    )
    without = _coordinator_base_messages(
        context={"task": "t"},
        approved_workflow=None,
    )

    assert len(without) == 2
    assert len(with_goal) == 3
    tail = with_goal[-1]
    assert tail["role"] == "user"
    assert "restated for recency" in tail["content"]
    assert '"goal_id":"goal-t1"' in tail["content"].replace(" ", "")


def test_a_typed_error_settles_instead_of_escaping(tmp_path):
    """C5's live crash: a session attempted terminal completion against
    a red gate, the ContractError escaped the loop, and the goal's
    durable story ended at wake_composed with no settlement. A typed
    contract error now settles returned_to_human naming the stage."""

    def raising_session(workspace, kwargs):
        raise ContractError("a required completion gate is red")

    result = _loop(
        tmp_path,
        sessions=[raising_session],
        executes=[],
    )

    assert result.settlement == "returned_to_human"
    assert any(
        "a required completion gate is red" in reason
        for reason in result.reasons
    )
    ledger = GoalLedger(
        tmp_path / "ws" / ".chemsmart-agent" / "goals" / "goal-t1"
    )
    assert ledger.entries()[-1]["kind"] == "goal_settled"


def test_a_typed_engine_error_settles_the_same_way(tmp_path):
    def raising_execute(run_directory):
        raise ContractError("approval bundle names a missing artifact")

    result = _loop(
        tmp_path,
        sessions=[_planning_session("live-1", review=_review_payload())],
        executes=[raising_execute],
    )

    assert result.settlement == "returned_to_human"
    assert any("approved execution" in reason for reason in result.reasons)


def test_an_engineless_cycle_settles_from_its_delivery(tmp_path):
    """C8's live crash: an admitted revision launched no engine, the
    run directory recorded no workflow run, and derive_run_outcome's
    ValueError escaped the loop unsettled. The cycle now settles from
    the run stream's typed delivery, exactly as a no-partition
    planning cycle does."""

    def analysis_only_execute(run_directory):
        store = RuntimeEventStore(
            run_directory / "events.jsonl", session_id="exec-1"
        )
        store.append(
            turn_id="t1",
            kind="session_started",
            payload={"phase": "route", "task_id": "t"},
        )
        return SimpleNamespace(status="partial", analysis_status="partial")

    result = _loop(
        tmp_path,
        sessions=[_planning_session("live-1", review=_review_payload())],
        executes=[analysis_only_execute],
    )

    assert result.settlement == "returned_to_human"
    ledger = GoalLedger(
        tmp_path / "ws" / ".chemsmart-agent" / "goals" / "goal-t1"
    )
    kinds = [entry["kind"] for entry in ledger.entries()]
    assert kinds[-1] == "goal_settled"
    run_rows = [
        entry for entry in ledger.entries() if entry["kind"] == "run_recorded"
    ]
    assert run_rows[-1]["payload"]["workflow_state"] == "analysis_only"


def test_a_dispatched_run_parks_the_goal_and_resumes_at_its_outcome(
    tmp_path,
):
    """The one human decision continues in its own run directory.

    With a scheduler in the loop the driver does not wait: it records
    the job it submitted, parks, and a later process -- the job's own
    tail, or a human's `agent wake` -- rebuilds the driver from the
    ledger at the outcome phase and settles from the run's durable
    record. Nothing here creates a second decision.
    """

    from chemsmart.agent.driver import (
        EXECUTION_RESULT_FILE,
        GoalDriver,
        GoalLoopResultV1,
    )

    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)
    submitted: dict = {}

    def dispatch_run(**kwargs):
        submitted.update(kwargs)
        return SimpleNamespace(
            scheduler="SLURM",
            job_id="191",
            submitted_at="2026-09-01T00:00:00+00:00",
            submit_script=str(kwargs["run_directory"] / "sub.sh"),
        )

    def never_execute(**_kwargs):
        raise AssertionError("a dispatched run is not executed in-process")

    driver = GoalDriver(
        task="the goal task",
        workspace=workspace,
        execution_envelope_file=_envelope_file(tmp_path),
        goal_id="goal-parked",
        granted_by="claude-owner-delegated-reviewer",
        plan_session=lambda **kw: _planning_session(
            "live-1", review=_review_payload()
        )(workspace, kw),
        resolve_review=lambda **_kw: ("d" * 64, tmp_path / "bundle.json"),
        execute_bundle=never_execute,
        dispatch_run=dispatch_run,
    )
    parked = driver.run()
    assert isinstance(parked, GoalLoopResultV1)
    assert parked.settlement == "parked"
    assert "job 191" in parked.reasons[0]
    assert submitted["cycle"] == 1
    kinds = [entry["kind"] for entry in driver.ledger.entries()]
    assert kinds[-1] == "run_dispatched"
    assert "goal_settled" not in kinds
    assert (driver.goal_dir / "task.md").read_text() == "the goal task"

    # A fresh process may not start the goal over ...
    with pytest.raises(ContractError, match="already exists"):
        GoalDriver(
            task="the goal task",
            workspace=workspace,
            execution_envelope_file=_envelope_file(tmp_path),
            goal_id="goal-parked",
            granted_by="claude-owner-delegated-reviewer",
        )

    # ... but it resumes it once the job has written the run's record.
    run_directory = driver.run_directory
    _engine_stream(tmp_path, run_directory, failed=False)
    (run_directory / EXECUTION_RESULT_FILE).write_text(
        json.dumps({"status": "completed", "analysis_status": ""}),
        encoding="utf-8",
    )

    def no_session(**_kw):
        raise AssertionError("no new session is needed to settle")

    resumed = GoalDriver.resume(
        workspace=workspace,
        goal_id="goal-parked",
        execution_envelope_file=_envelope_file(tmp_path),
        granted_by="claude-owner-delegated-reviewer",
        plan_session=no_session,
        execute_bundle=never_execute,
    )
    assert resumed.phase == "outcome"
    assert resumed.task == "the goal task"
    assert resumed.cycles == 1
    result = resumed.run()
    assert result.settlement == "achieved"
    recorded = [
        entry
        for entry in resumed.ledger.entries()
        if entry["kind"] == "run_recorded"
    ]
    assert recorded[-1]["payload"]["cycle"] == 1
    assert recorded[-1]["payload"]["queue_wait_seconds"] > 0.0

    # Settled goals do not resume, and a goal with no parked run does not.
    with pytest.raises(ContractError, match="is settled"):
        GoalDriver.resume(
            workspace=workspace,
            goal_id="goal-parked",
            execution_envelope_file=_envelope_file(tmp_path),
            granted_by="claude-owner-delegated-reviewer",
        )


def test_a_failed_run_opens_a_typed_recovery_with_a_repair_menu(tmp_path):
    """A timeout is ordinary work: the ledger says a recovery opened and
    names how each node ended, and the next wake carries the route that
    answers it. The host names the route; the physics grades it."""

    from chemsmart.agent.driver import REPAIR_MENU, GoalDriver

    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)
    wakes: list = []

    def plan_session(**kwargs):
        wakes.append(kwargs["goal_context"])
        name = f"live-{len(wakes)}"
        rows = list(_READ_OUTCOME_ROWS) if len(wakes) > 1 else ()
        return _planning_session(
            name, review=_review_payload(), wake_rows=rows
        )(workspace, kwargs)

    executes = iter(
        (
            _execute(tmp_path, failed=True, status="failed"),
            _execute(tmp_path, failed=False, status="completed"),
        )
    )
    driver = GoalDriver(
        task="the goal task",
        workspace=workspace,
        execution_envelope_file=_envelope_file(tmp_path),
        goal_id="goal-repair",
        granted_by="claude-owner-delegated-reviewer",
        plan_session=plan_session,
        resolve_review=lambda **_kw: ("d" * 64, tmp_path / "bundle.json"),
        execute_bundle=lambda **kw: next(executes)(kw["run_directory"]),
    )
    result = driver.run()
    assert result.settlement == "achieved"
    assert result.cycles == 2
    opened = [
        entry
        for entry in driver.ledger.entries()
        if entry["kind"] == "recovery_opened"
    ]
    assert len(opened) == 1
    assert opened[0]["payload"]["cycle"] == 1
    assert set(opened[0]["payload"]["terminal_states"].values()) == {
        "timeout_terminated"
    }
    second_wake = wakes[1]
    assert second_wake["repair_menu"] == {
        "timeout_terminated": REPAIR_MENU["timeout_terminated"]
    }
    assert "repair_menu names" in second_wake["authority"]
    assert wakes[0]["deliverables"]["delivered_quantity_ids"] == ()


def test_a_run_no_revision_can_answer_returns_to_the_human(tmp_path):
    """A launch that never happened is not evidence a revision can stand
    on; re-planning over it would spend budget on the host's own gap."""

    from chemsmart.agent.driver import GoalDriver

    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)

    def execute(run_directory):
        _engine_stream(
            tmp_path,
            run_directory,
            failed=True,
            findings=("execution.process.launch_failed",),
        )
        return SimpleNamespace(status="failed", analysis_status="")

    sessions = 0

    def plan_session(**kwargs):
        nonlocal sessions
        sessions += 1
        return _planning_session("live-1", review=_review_payload())(
            workspace, kwargs
        )

    driver = GoalDriver(
        task="the goal task",
        workspace=workspace,
        execution_envelope_file=_envelope_file(tmp_path),
        goal_id="goal-unanswerable",
        granted_by="claude-owner-delegated-reviewer",
        plan_session=plan_session,
        resolve_review=lambda **_kw: ("d" * 64, tmp_path / "bundle.json"),
        execute_bundle=lambda **kw: execute(kw["run_directory"]),
    )
    result = driver.run()
    assert result.settlement == "returned_to_human"
    assert "no revision can answer" in result.reasons[0]
    assert "launch_failed" in result.reasons[0]
    assert sessions == 1, "no second planning session was started"
