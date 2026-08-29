"""The goal-directed loop: plan, one human decision, execute, read, revise.

The driver cycles the existing authority chain -- ``run_live_agent_session``
for planning, the stored-review resolution for the decision, the
provider-free executor for engines -- and adds nothing to any of them.
What is new is only the connective tissue the chain lacked: a durable
goal ledger, a typed wake context built from the same terminal
derivation a session's own tool reads, and the deterministic revision
admission from :mod:`chemsmart.agent.goal`. Detach, typed completion,
re-invoke: the session never blocks on an engine, the executor never
sees a provider, and every wake reads sealed evidence rather than a
retelling.

Dependencies are injected so the loop's bookkeeping is testable without
a provider or an engine; production callers pass nothing and get the
real chain.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from chemsmart.agent._contracts import ContractError, canonical_data
from chemsmart.agent.goal import (
    GOAL_SCHEMA_VERSION,
    GoalLedger,
    GoalRecordV1,
    admit_revision,
    conditions_from_review,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class GoalLoopResultV1:
    """How one goal ended, for the caller and the report."""

    goal_id: str
    settlement: str
    cycles: int
    revisions_admitted: int
    reasons: tuple[str, ...] = ()


def _default_plan_session(**kwargs: Any) -> Any:
    from chemsmart.agent.live_session import run_live_agent_session

    return run_live_agent_session(**kwargs)


def _default_resolve(
    *,
    review_file: Path,
    workspace: Path,
    decision: str,
    actor: str,
    approval_id: str,
) -> tuple[str, Path]:
    from chemsmart.agent.live_session import (
        inspect_workflow_execution_replay,
        resolve_workflow_execution_review,
    )

    report = inspect_workflow_execution_replay(
        review_file=review_file,
        workspace=workspace,
        task_spec_sha256="",
    )
    scope = (
        Path(workspace).resolve()
        / ".chemsmart-agent"
        / "replays"
        / approval_id
    )
    scope.mkdir(parents=True, exist_ok=True, mode=0o700)
    resolve_workflow_execution_review(
        review_file=review_file,
        reviewed_sha256=report["review_sha256"],
        decision=decision,
        actor=actor,
        output_file=scope / "bundle.json" if decision == "approve" else None,
        decision_log=scope / "decisions.jsonl",
        approval_id=approval_id,
    )
    return str(report["review_sha256"]), scope / "bundle.json"


def _default_execute(
    *, approval_file: Path, workspace: Path, run_directory: Path
) -> Any:
    from chemsmart.agent.executor import execute_approved_workflow

    return execute_approved_workflow(
        approval_file=approval_file,
        workspace=workspace,
        run_directory=run_directory,
        task_spec_sha256="",
    )


def _review_record(review_file: Path) -> Mapping[str, Any]:
    return json.loads(Path(review_file).read_text(encoding="utf-8"))


def _plan_identity_sha256(review: Mapping[str, Any]) -> str:
    plan = review.get("scientific_plan") or {}
    return str(plan.get("scientific_identity_sha256") or "")


def _session_events_path(session_result: Any, workspace: Path) -> Path:
    run_id = str(getattr(session_result, "run_id", "") or "")
    candidate = (
        Path(workspace) / ".chemsmart-agent" / "runs" / run_id / "events.jsonl"
    )
    if candidate.is_file():
        return candidate
    runs = sorted(
        (Path(workspace) / ".chemsmart-agent" / "runs").glob(
            "live-*/events.jsonl"
        )
    )
    if not runs:
        raise ContractError("the planning session left no event stream")
    return runs[-1]


def _previous_run_reference(ledger: GoalLedger) -> str:
    """The last recorded run — the run a revision answers."""

    reference = ""
    for entry in ledger.entries():
        if entry["kind"] == "run_recorded":
            reference = str(entry["payload"].get("run") or "")
    return reference


def _wake_context(
    goal: GoalRecordV1,
    ledger: GoalLedger,
    outcome: Any,
) -> dict[str, Any]:
    budgets = ledger.budgets(goal)
    trajectory = tuple(
        {
            "kind": entry["kind"],
            "at": entry["at"],
            "payload": {
                key: value
                for key, value in entry["payload"].items()
                if key
                in {
                    "cycle",
                    "engine_calls_consumed",
                    "engine_wall_seconds",
                    "workflow_state",
                    "run",
                    "reasons",
                }
            },
        }
        for entry in ledger.entries()
        if entry["kind"]
        in {"run_recorded", "revision_admitted", "revision_returned"}
    )
    return {
        "schema_version": "chemsmart.goal-wake-context.v1",
        "goal_id": goal.goal_id,
        "granted_by": goal.granted_by,
        "conditions": canonical_data(goal.conditions),
        "budgets": {
            "engine_calls_remaining": budgets.engine_calls_remaining,
            "wall_seconds_remaining": budgets.wall_seconds_remaining,
            "revisions_remaining": budgets.revisions_remaining,
        },
        "trajectory": trajectory,
        "previous_run": (
            _previous_run_reference(ledger) if outcome is not None else ""
        ),
        "previous_run_outcome": (
            outcome.public_record() if outcome is not None else {}
        ),
        "authority": (
            "This session runs under an approved goal. Read the previous "
            "run's typed outcome with inspect_run_outcome before planning "
            "a revision; a revision that changes molecular identity, "
            "electronic state, or physical conditions, or exceeds the "
            "budgets above, returns to the human instead of running."
        ),
    }


def _achieved(execute_result: Any) -> bool:
    status = str(getattr(execute_result, "status", "") or "")
    analysis = str(getattr(execute_result, "analysis_status", "") or "")
    return status == "completed" and analysis in {"completed", "none", ""}


def _settlement_evidence(events_path: Path) -> dict[str, Any]:
    """Receipts a refusal settlement cites, from the session's stream."""

    receipts: list[str] = []
    decisions = 0
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            event = json.loads(text)
        except json.JSONDecodeError:
            continue
        kind = str(event.get("kind") or "")
        payload = event.get("payload") or {}
        if kind == "scientific_decision_recorded":
            decisions += 1
        elif kind in {
            "result_quantities_extracted",
            "scientific_validation_evaluated",
            "quantity_expression_evaluated",
        }:
            digest = str(payload.get("receipt_sha256") or "")
            if digest:
                receipts.append(digest)
    if decisions and receipts:
        return {
            "scientific_decisions": decisions,
            "receipt_sha256s": tuple(receipts),
        }
    return {}


def run_goal_loop(
    *,
    task: str,
    workspace: str | Path,
    execution_envelope_file: str | Path,
    goal_id: str,
    granted_by: str,
    max_revisions: int = 5,
    provider: str | None = None,
    provider_config_file: str | Path | None = None,
    analysis_completion_file: str | Path | None = None,
    plan_session: Callable[..., Any] = _default_plan_session,
    resolve_review: Callable[..., tuple[str, Path]] = _default_resolve,
    execute_bundle: Callable[..., Any] = _default_execute,
    initial_decision: str = "approve",
    stop_file: str | Path | None = None,
) -> GoalLoopResultV1:
    """Drive one goal to settlement under one human decision.

    ``initial_decision`` is the human's: "approve" records it under
    ``granted_by`` exactly as ``agent review --decision approve`` would,
    and anything else settles the goal ``returned_to_human`` before any
    engine runs. Every later cycle's decision is host-admitted under
    the goal and recorded with the composite actor.
    """

    workspace = Path(workspace).resolve()
    goal_dir = workspace / ".chemsmart-agent" / "goals" / goal_id
    ledger = GoalLedger(goal_dir)
    ledger.directory.mkdir(parents=True, exist_ok=True)
    if ledger.goal_path.exists():
        raise ContractError(
            "this goal already exists; a goal is one human decision, "
            "not a resumable queue"
        )

    from chemsmart.agent.execution_envelope import (
        load_bounded_execution_envelope,
    )

    envelope = load_bounded_execution_envelope(execution_envelope_file)
    envelope_record = {
        "allowed_program_engines": envelope.allowed_program_engines,
        "max_engine_calls": envelope.max_engine_calls,
        "episode_wall_time_seconds": envelope.episode_wall_time_seconds,
    }

    goal: GoalRecordV1 | None = None
    outcome = None
    cycles = 0
    revisions_admitted = 0

    def _stopped() -> bool:
        return bool(stop_file and Path(stop_file).exists())

    while True:
        cycles += 1
        if _stopped():
            ledger.append(
                "cancelled_by_human", {"cycle": cycles, "at": _utc_now()}
            )
            ledger.settle(
                "returned_to_human",
                reasons=("cancelled by the human's stop file",),
            )
            return GoalLoopResultV1(
                goal_id=goal_id,
                settlement="returned_to_human",
                cycles=cycles,
                revisions_admitted=revisions_admitted,
                reasons=("cancelled",),
            )
        review_file = goal_dir / "reviews" / f"cycle-{cycles}.json"
        review_file.parent.mkdir(parents=True, exist_ok=True)
        wake = (
            _wake_context(goal, ledger, outcome) if goal is not None else None
        )
        if wake is not None and wake.get("previous_run"):
            # Host attestation for the evidence gate: this cycle's
            # session was handed the named run's typed outcome.
            ledger.append(
                "wake_composed",
                {"cycle": cycles, "run": wake["previous_run"]},
            )
        session = plan_session(
            task=task,
            provider=provider,
            provider_config_file=provider_config_file,
            workspace=workspace,
            execution_enabled=False,
            approval_file=None,
            execution_envelope_file=execution_envelope_file,
            analysis_completion_file=analysis_completion_file,
            review_file=review_file,
            goal_context=wake,
        )
        terminal = str(getattr(session, "terminal_state", "") or "")
        events_path = _session_events_path(session, workspace)

        if terminal != "waiting_for_approval":
            # No executable partition was planned. Either the session
            # delivered over registered results, refused with receipts,
            # or stopped; each settles the goal from durable evidence.
            if goal is None:
                goal = GoalRecordV1(
                    schema_version=GOAL_SCHEMA_VERSION,
                    goal_id=goal_id,
                    task_spec_sha256=str(
                        getattr(session, "task_spec_sha256", "") or ""
                    ),
                    scientific_identity_sha256="",
                    conditions={"solvents": (), "thermochemistry": ()},
                    envelope=envelope_record,
                    max_revisions=max_revisions,
                    granted_by=granted_by,
                    initial_review_sha256="",
                    created_at=_utc_now(),
                )
                ledger.create(goal)
            evidence = _settlement_evidence(events_path)
            if terminal == "complete" and evidence:
                ledger.settle(
                    (
                        "unreachable_from_evidence"
                        if _refusal_declared(events_path)
                        else "achieved"
                    ),
                    reasons=(f"session terminal state: {terminal}",),
                    evidence=evidence,
                )
                settled = (
                    "unreachable_from_evidence"
                    if _refusal_declared(events_path)
                    else "achieved"
                )
            elif terminal == "complete":
                ledger.settle(
                    "achieved",
                    reasons=("analysis-only delivery",),
                )
                settled = "achieved"
            else:
                ledger.settle(
                    "returned_to_human",
                    reasons=(f"session terminal state: {terminal}",),
                )
                settled = "returned_to_human"
            return GoalLoopResultV1(
                goal_id=goal_id,
                settlement=settled,
                cycles=cycles,
                revisions_admitted=revisions_admitted,
                reasons=(terminal,),
            )

        review = _review_record(review_file)
        if goal is None:
            if initial_decision != "approve":
                ledger_goal = GoalRecordV1(
                    schema_version=GOAL_SCHEMA_VERSION,
                    goal_id=goal_id,
                    task_spec_sha256=str(
                        getattr(session, "task_spec_sha256", "") or ""
                    ),
                    scientific_identity_sha256=_plan_identity_sha256(review),
                    conditions=conditions_from_review(review),
                    envelope=envelope_record,
                    max_revisions=max_revisions,
                    granted_by=granted_by,
                    initial_review_sha256="",
                    created_at=_utc_now(),
                )
                ledger.create(ledger_goal)
                ledger.settle(
                    "returned_to_human",
                    reasons=("the human declined the initial review",),
                )
                return GoalLoopResultV1(
                    goal_id=goal_id,
                    settlement="returned_to_human",
                    cycles=cycles,
                    revisions_admitted=revisions_admitted,
                    reasons=("initial review declined",),
                )
            review_sha256, bundle_file = resolve_review(
                review_file=review_file,
                workspace=workspace,
                decision="approve",
                actor=granted_by,
                approval_id=f"goal-{goal_id}-cycle-{cycles}",
            )
            goal = GoalRecordV1(
                schema_version=GOAL_SCHEMA_VERSION,
                goal_id=goal_id,
                task_spec_sha256=str(
                    getattr(session, "task_spec_sha256", "") or ""
                ),
                scientific_identity_sha256=_plan_identity_sha256(review),
                conditions=conditions_from_review(review),
                envelope=envelope_record,
                max_revisions=max_revisions,
                granted_by=granted_by,
                initial_review_sha256=review_sha256,
                created_at=_utc_now(),
            )
            ledger.create(goal)
        else:
            budgets = ledger.budgets(goal)
            verdict = admit_revision(
                goal=goal,
                budgets=budgets,
                revision_review=review,
                revision_scientific_identity_sha256=(
                    _plan_identity_sha256(review)
                ),
                session_events_path=events_path,
                prior_outcome_evidence_hashes=tuple(
                    digest
                    for node in (outcome.nodes if outcome else ())
                    for digest in node.evidence_event_hashes
                ),
                previous_run_reference=_previous_run_reference(ledger),
                wake_embedded_run=str(
                    (wake or {}).get("previous_run") or ""
                ),
            )
            if not verdict.admitted:
                ledger.append(
                    "revision_returned",
                    {"cycle": cycles, "reasons": verdict.reasons},
                )
                ledger.settle("returned_to_human", reasons=verdict.reasons)
                return GoalLoopResultV1(
                    goal_id=goal_id,
                    settlement="returned_to_human",
                    cycles=cycles,
                    revisions_admitted=revisions_admitted,
                    reasons=verdict.reasons,
                )
            review_sha256, bundle_file = resolve_review(
                review_file=review_file,
                workspace=workspace,
                decision="approve",
                actor=goal.actor,
                approval_id=f"goal-{goal_id}-cycle-{cycles}",
            )
            revisions_admitted += 1
            ledger.append(
                "revision_admitted",
                {
                    "cycle": cycles,
                    "review_sha256": review_sha256,
                    "actor": goal.actor,
                    "granted_by": goal.granted_by,
                    "checks": dict(verdict.checks),
                    "cited_evidence_event_hashes": (
                        verdict.cited_evidence_event_hashes
                    ),
                },
            )

        run_directory = goal_dir / "runs" / f"cycle-{cycles}"
        run_directory.mkdir(parents=True, exist_ok=True)
        execute_result = execute_bundle(
            approval_file=bundle_file,
            workspace=workspace,
            run_directory=run_directory,
        )
        from chemsmart.agent.terminal_states import (
            derive_run_outcome,
            read_run_events,
        )

        outcome = derive_run_outcome(
            read_run_events(run_directory / "events.jsonl")
        )
        ledger.append(
            "run_recorded",
            {
                "cycle": cycles,
                "run": f"goals/{goal_id}/runs/cycle-{cycles}",
                "workflow_state": outcome.workflow_state,
                "engine_calls_consumed": outcome.engine_calls_consumed,
                "engine_wall_seconds": outcome.engine_wall_seconds,
            },
        )

        if _achieved(execute_result):
            ledger.settle(
                "achieved",
                reasons=(
                    f"cycle {cycles}: workflow completed with its "
                    "analysis chain",
                ),
            )
            return GoalLoopResultV1(
                goal_id=goal_id,
                settlement="achieved",
                cycles=cycles,
                revisions_admitted=revisions_admitted,
                reasons=(),
            )
        budgets = ledger.budgets(goal)
        if (
            budgets.revisions_remaining <= 0
            or budgets.engine_calls_remaining <= 0
            or budgets.wall_seconds_remaining <= 0
        ):
            ledger.settle(
                "exhausted",
                reasons=(
                    f"engine calls remaining "
                    f"{budgets.engine_calls_remaining}, wall seconds "
                    f"remaining {budgets.wall_seconds_remaining:.0f}, "
                    f"revisions remaining "
                    f"{budgets.revisions_remaining}",
                ),
            )
            return GoalLoopResultV1(
                goal_id=goal_id,
                settlement="exhausted",
                cycles=cycles,
                revisions_admitted=revisions_admitted,
                reasons=("budgets exhausted",),
            )


def _refusal_declared(events_path: Path) -> bool:
    """Whether the session's decision names the goal unanswerable.

    Deterministic and shallow on purpose: it detects that a scientific
    decision was recorded whose rationale declares the requested
    quantity unobtainable, by the presence of a validation that was
    planned to fail or an explicit decision event, never by grading
    prose.
    """

    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            event = json.loads(text)
        except json.JSONDecodeError:
            continue
        if str(event.get("kind") or "") != ("scientific_validation_evaluated"):
            continue
        record = (event.get("payload") or {}).get("record") or {}
        for result in record.get("rule_results") or ():
            if isinstance(result, Mapping) and result.get("passed") is (False):
                return True
    return False


__all__ = ["GoalLoopResultV1", "run_goal_loop"]
