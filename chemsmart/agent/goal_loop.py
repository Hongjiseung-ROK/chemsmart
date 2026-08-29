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


#: The refusal affordance, present from cycle 1: the first live goal
#: round's honest refusal was invisible to the settlement layer partly
#: because no session was ever told the typed route exists.
_REFUSAL_AFFORDANCE = (
    "If the requested observable is unreachable from the admissible "
    "evidence, deliver what is reachable, retain the unreachable "
    "observable as a blocked analysis intent naming its required "
    "producer, and record the scientific decision citing its "
    "receipts; the goal then settles as a typed refusal, which is a "
    "deliverable."
)


def _goal_terms_context(
    *,
    goal_id: str,
    granted_by: str,
    envelope_record: Mapping[str, Any],
    max_revisions: int,
) -> dict[str, Any]:
    """Cycle 1's context: the goal's terms before any run exists.

    The first live goal round handed cycle 1 nothing -- an
    analysis-only goal is single-cycle by construction, so its session
    never saw the budgets (a zero engine-call grant would have said
    "analysis only" before the session drafted engine work), the
    authority in force, or the refusal affordance. The terms are all
    in hand when the loop starts; only the trajectory is empty.
    """

    return {
        "schema_version": "chemsmart.goal-wake-context.v1",
        "goal_id": goal_id,
        "granted_by": granted_by,
        "conditions": {},
        "budgets": {
            "engine_calls_remaining": int(
                envelope_record["max_engine_calls"]
            ),
            "wall_seconds_remaining": float(
                envelope_record["episode_wall_time_seconds"]
            ),
            "revisions_remaining": int(max_revisions),
        },
        "trajectory": (),
        "previous_run": "",
        "previous_run_outcome": {},
        "authority": (
            "This session plans cycle 1 of an approved goal; the "
            "budgets above are the whole grant. A plan that changes "
            "molecular identity, electronic state, or physical "
            "conditions later, or exceeds these budgets, returns to "
            "the human instead of running. " + _REFUSAL_AFFORDANCE
        ),
    }


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
            "This session runs under an approved goal. The previous "
            "run's typed outcome is embedded above and inspect_run_outcome "
            "re-reads it or any earlier run; a revision that changes "
            "molecular identity, electronic state, or physical "
            "conditions, or exceeds the budgets above, returns to the "
            "human instead of running. " + _REFUSAL_AFFORDANCE
        ),
    }


def _achieved(execute_result: Any) -> bool:
    status = str(getattr(execute_result, "status", "") or "")
    analysis = str(getattr(execute_result, "analysis_status", "") or "")
    return status == "completed" and analysis in {"completed", ""}


@dataclass(frozen=True)
class _AnalysisDelivery:
    """What one session's durable stream says it delivered."""

    completion_status: str
    limitation_output_ids: tuple[str, ...]
    claims: int
    decisions: int
    receipt_sha256s: tuple[str, ...]


def _analysis_delivery(events_path: Path) -> _AnalysisDelivery:
    """Read the delivery facts a settlement stands on.

    Every field is a typed record the host itself wrote: the
    completion receipt with its stated limitations, the claim and
    decision records, and the receipt digests a settlement cites. The
    first live goal round's classifier read none of these -- it
    watched validation rules, the one place an honest refusal leaves
    no trace -- and settled a receipts-backed refusal as achieved.
    """

    completion_status = ""
    limitations: tuple[str, ...] = ()
    claims = 0
    decisions = 0
    receipts: list[str] = []
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
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
        digest = str(payload.get("receipt_sha256") or "")
        if kind == "scientific_decision_recorded":
            decisions += 1
        elif kind == "analysis_claims_recorded":
            claims += 1
            if digest:
                receipts.append(digest)
        elif kind == "analysis_completion_evaluated":
            completion_status = str(payload.get("status") or "")
            limitations = tuple(
                str(item)
                for item in (payload.get("limitation_output_ids") or ())
            )
            if digest:
                receipts.append(digest)
        elif kind in {
            "result_quantities_extracted",
            "scientific_validation_evaluated",
            "quantity_expression_evaluated",
            "thermochemistry_derived",
        }:
            if digest:
                receipts.append(digest)
    return _AnalysisDelivery(
        completion_status=completion_status,
        limitation_output_ids=limitations,
        claims=claims,
        decisions=decisions,
        receipt_sha256s=tuple(receipts),
    )


def _settlement_evidence(delivery: _AnalysisDelivery) -> dict[str, Any]:
    """Receipts a settlement cites, from the session's own stream."""

    if delivery.decisions and delivery.receipt_sha256s:
        return {
            "scientific_decisions": delivery.decisions,
            "receipt_sha256s": delivery.receipt_sha256s,
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
            _wake_context(goal, ledger, outcome)
            if goal is not None
            else _goal_terms_context(
                goal_id=goal_id,
                granted_by=granted_by,
                envelope_record=envelope_record,
                max_revisions=max_revisions,
            )
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
            delivery = _analysis_delivery(events_path)
            evidence = _settlement_evidence(delivery)
            certified = (
                terminal == "complete"
                and delivery.completion_status == "passed"
            )
            if (
                certified
                and delivery.limitation_output_ids
                and delivery.decisions
                and evidence
            ):
                # The plan's own completion receipt says a required
                # output's producer was declared blocked: the requested
                # observable was not delivered, and the recorded
                # decision with its receipts is the typed refusal.
                settled = "unreachable_from_evidence"
                reasons = (
                    "the completion receipt names required outputs "
                    "delivered without: "
                    + ", ".join(delivery.limitation_output_ids),
                )
            elif certified and delivery.claims:
                settled = "achieved"
                reasons = (
                    "the host completion gate certified the delivery",
                )
            elif delivery.claims or delivery.decisions:
                # Something was recorded, but the host never certified
                # completion -- a human reads it, whatever the
                # session's terminal word was.
                settled = "returned_to_human"
                reasons = (
                    f"session terminal state: {terminal}; the session "
                    "recorded analysis but the host completion gate "
                    "did not pass",
                )
            else:
                settled = "returned_to_human"
                reasons = (f"session terminal state: {terminal}",)
            ledger.settle(
                settled,
                reasons=reasons,
                evidence=evidence,
            )
            return GoalLoopResultV1(
                goal_id=goal_id,
                settlement=settled,
                cycles=cycles,
                revisions_admitted=revisions_admitted,
                reasons=reasons,
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


__all__ = ["GoalLoopResultV1", "run_goal_loop"]
