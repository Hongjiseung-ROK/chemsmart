"""The goal driver: plan, one human decision, execute, read, revise.

Every entry point that drives a goal -- ``chemsmart agent goal``, the
terminal interface, a scheduler job re-entering a parked run -- is a
view of this one step machine. Each phase boundary is a durable ledger
entry, so a process may stop after any step and a later process may
resume from the ledger: that is what lets an approved partition be
submitted to a scheduler, the driver exit, and the job's own tail wake
the goal when the engines are done.

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
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence

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


def _settle_from_delivery(
    ledger: GoalLedger,
    *,
    goal_id: str,
    cycles: int,
    revisions_admitted: int,
    events_path: Path,
    terminal: str,
) -> GoalLoopResultV1:
    """Settle a goal from one stream's typed delivery facts.

    Serves two shapes: a planning session that ended without an
    executable partition (its own stream carries the delivery), and an
    admitted revision whose approved bundle launched no engine -- the
    executor walks the analysis chain into the run directory's stream
    and no workflow run is recorded, which is a legitimate cycle
    ending, not a defect.
    """

    delivery = _analysis_delivery(events_path)
    evidence = _settlement_evidence(delivery)
    certified = (
        terminal == "complete" and delivery.completion_status == "passed"
    )
    if delivery.doubted_quantity_ids:
        # The session claimed from a receipt its own recorded decision
        # doubts. Whatever the completion word says -- partial by the
        # gate, or passed because the doubt came after -- a doubted
        # number is the human's to read.
        settled = "returned_to_human"
        reasons = (
            "a rendered claim stands on a receipt the session's "
            "own recorded decision doubts: "
            + ", ".join(delivery.doubted_quantity_ids),
        )
    elif (
        certified
        and delivery.limitation_output_ids
        and delivery.decisions
        and evidence
    ):
        # The plan's own completion receipt says a required output's
        # producer was declared blocked: the requested observable was
        # not delivered, and the recorded decision with its receipts is
        # the typed refusal.
        settled = "unreachable_from_evidence"
        reasons = (
            "the completion receipt names required outputs "
            "delivered without: " + ", ".join(delivery.limitation_output_ids),
        )
    elif certified and delivery.unanswered_verdicts:
        # The host itself rendered a verdict saying a delivered structure
        # is not what the task required, and no recorded decision cites
        # it. The required outputs are all present, so the completion
        # gate is green and the goal is not "achieved" in any sense a
        # scientist would sign: a human reads it.
        settled = "returned_to_human"
        reasons = (
            "a validation verdict failed and no recorded decision cites "
            "it: " + ", ".join(delivery.unanswered_verdicts),
        )
    elif certified and delivery.claims:
        settled = "achieved"
        reasons = ("the host completion gate certified the delivery",)
    elif delivery.claims or delivery.decisions:
        # Something was recorded, but the host never certified
        # completion -- a human reads it, whatever the session's
        # terminal word was.
        settled = "returned_to_human"
        reasons = (
            f"session terminal state: {terminal}; the session "
            "recorded analysis but the host completion gate "
            "did not pass",
        )
    else:
        settled = "returned_to_human"
        reasons = (f"session terminal state: {terminal}",)
    ledger.settle(settled, reasons=reasons, evidence=evidence)
    return GoalLoopResultV1(
        goal_id=goal_id,
        settlement=settled,
        cycles=cycles,
        revisions_admitted=revisions_admitted,
        reasons=reasons,
    )


def _typed_error_settlement(
    ledger: GoalLedger,
    *,
    goal_id: str,
    cycles: int,
    revisions_admitted: int,
    stage: str,
    error: ContractError,
) -> GoalLoopResultV1:
    """Settle a typed error instead of letting it escape unsettled.

    Observed live (C5): a session attempted terminal completion against
    a red gate, the event store's ContractError propagated through the
    loop, the process died, and the goal's durable story ended at
    wake_composed with no settlement -- violating "a goal settles into
    one typed state". A typed contract error is an outcome the human
    reads, not a crash; a non-contract exception stays a crash, because
    a genuine defect must not be laundered into a settlement.
    """

    reason = f"cycle {cycles}, {stage}: {error}"
    ledger.settle("returned_to_human", reasons=(reason,))
    return GoalLoopResultV1(
        goal_id=goal_id,
        settlement="returned_to_human",
        cycles=cycles,
        revisions_admitted=revisions_admitted,
        reasons=(reason,),
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
#: The closing act is adversarial and points at a tool call, never at
#: re-reading one's own prose: intrinsic self-review without external
#: feedback degrades, while one further typed observation can refute.
_OBSERVABLE_RESTATEMENT_ASK = (
    "As this cycle's first typed act, restate the requested observable "
    "through declare_requested_observable -- identifier, reporting "
    "unit, one sentence of meaning; the completion gate checks the "
    "delivery against that declaration by kind and unit, never value. "
)

_ADVERSARIAL_CLOSE = (
    "Before recording the scientific decision, attempt to refute the "
    "delivery with one further typed read; a refutation that stands is "
    "a finding to deliver, not a failure. "
)

_RECOVERY_ROUTE = (
    " If deliverables names an unanswered failed verdict, the previous "
    "run delivered a structure the host judged not to be what the task "
    "required, and this cycle exists so that you can answer it. The "
    "legal routes are ordinary work, not special permissions: step the "
    "offending structure along the mode that is wrong with "
    "displace_along_vibrational_mode and optimise again; change the "
    "internal coordinate the mode moves with edit_molecular_geometry; "
    "seed a transition-state search from a validated frequency-bearing "
    "producer's Hessian; or, if you judge the delivery sound as it "
    "stands, record a scientific decision citing that validation "
    "receipt and say why. Recovering and standing by the result are "
    "both answers. Leaving it unanswered is the one thing that is not, "
    "and it returns the goal to the human. Nothing here tells you which "
    "answer is right -- the physics does that, after you act."
    " Whatever you do about the structure, deliverables also names any "
    "stale quantity: a number the previous run rendered from the "
    "rejected result, whose arithmetic was sound and whose structure no "
    "longer stands. Recovering the structure does not recover those "
    "numbers. Re-derive each one on the result you end up standing "
    "behind and render it as a claim, because an expression that is "
    "evaluated and never claimed is not delivered; a live run recomputed "
    "the right value, rendered nothing, and left the superseded number "
    "as its answer."
)

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
                envelope_record.get("max_engine_calls") or 0
            ),
            "wall_seconds_remaining": float(
                envelope_record.get("episode_wall_time_seconds") or 0.0
            ),
            "revisions_remaining": int(max_revisions),
        },
        # Cycle 1 has delivered nothing yet, but it carries the same
        # keys a wake does: one shape across every cycle is what lets a
        # session read the record the same way each time.
        "deliverables": _deliverables_record(
            _AnalysisDelivery("", (), 0, 0, ())
        ),
        "trajectory": (),
        "previous_run": "",
        "previous_run_outcome": {},
        "authority": (
            "This session plans cycle 1 of an approved goal; the "
            "budgets above are the whole grant. A plan that changes "
            "molecular identity, electronic state, or physical "
            "conditions later, or exceeds these budgets, returns to "
            "the human instead of running. "
            + _OBSERVABLE_RESTATEMENT_ASK
            + _ADVERSARIAL_CLOSE
            + _REFUSAL_AFFORDANCE
        ),
    }


def _deliverables_record(delivery: _AnalysisDelivery) -> dict[str, Any]:
    """What the previous run's own stream says stands delivered.

    Names quantities and stated limitations, never values: the goal's
    demand is in the task, and this record lets a wake session see what
    it has already delivered, what the chain declared it could not, and
    what its own decisions doubt -- so the next action can follow the
    gap rather than the tool list.
    """

    return {
        "delivered_quantity_ids": delivery.delivered_quantity_ids,
        "limitation_output_ids": delivery.limitation_output_ids,
        "doubted_quantity_ids": delivery.doubted_quantity_ids,
        "unanswered_failed_verdicts": delivery.unanswered_verdicts,
        "stale_quantity_ids": delivery.stale_quantity_ids,
        "unclaimed_output_ids": delivery.unclaimed_output_ids,
    }


def _wake_context(
    goal: GoalRecordV1,
    ledger: GoalLedger,
    outcome: Any,
    *,
    workspace: Path | None = None,
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
    previous_run = (
        _previous_run_reference(ledger) if outcome is not None else ""
    )
    deliverables: dict[str, Any] = {
        "delivered_quantity_ids": (),
        "limitation_output_ids": (),
        "doubted_quantity_ids": (),
    }
    if previous_run and workspace is not None:
        deliverables = _deliverables_record(
            _analysis_delivery(
                Path(workspace)
                / ".chemsmart-agent"
                / Path(*previous_run.split("/"))
                / "events.jsonl"
            )
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
        "deliverables": deliverables,
        "trajectory": trajectory,
        "previous_run": previous_run,
        "previous_run_outcome": (
            outcome.public_record() if outcome is not None else {}
        ),
        "authority": (
            "This session runs under an approved goal. The previous "
            "run's typed outcome is embedded above and inspect_run_outcome "
            "re-reads it or any earlier run; a revision that changes "
            "molecular identity, electronic state, or physical "
            "conditions, or exceeds the budgets above, returns to the "
            "human instead of running. "
            + _RECOVERY_ROUTE
            + _OBSERVABLE_RESTATEMENT_ASK
            + _ADVERSARIAL_CLOSE
            + _REFUSAL_AFFORDANCE
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
    #: Claim quantities whose supporting receipt a recorded decision
    #: doubts (``doubt:{receipt}`` evidence references intersected with
    #: the rendered claims' source receipts) -- computed here from the
    #: stream so a doubt recorded after the completion event still
    #: reaches the settlement.
    doubted_quantity_ids: tuple[str, ...] = ()
    #: Every quantity a rendered claim delivered, by its own id.
    delivered_quantity_ids: tuple[str, ...] = ()
    #: Host-rendered verdicts that failed and that no recorded decision
    #: has cited. A failed verdict is the host saying the delivered
    #: structure is not what the task required -- a minimum that is a
    #: saddle, a transition state with the wrong imaginary-mode count.
    #: It never made a goal partial and it never opened a cycle, so a
    #: run could deliver every required output, display "failed" in its
    #: own report, and settle achieved with budget in hand. A decision
    #: that cites the validation receipt has answered it; one that does
    #: not has left it open.
    unanswered_verdicts: tuple[str, ...] = ()
    #: Delivered quantities whose own receipt lineage traces back to a
    #: result a failed verdict rejected. A recovery cycle that replaces
    #: the structure does not replace the numbers computed from the old
    #: one, and the wake record used to name those numbers as delivered
    #: in the same breath as the verdict invalidating them -- so a live
    #: session cleared the verdict, recomputed the value into an
    #: expression receipt, never rendered it as a claim, and settled
    #: with the superseded number standing as the answer. Stale is not
    #: wrong: the arithmetic held, the structure beneath it did not.
    stale_quantity_ids: tuple[str, ...] = ()
    #: Artifact digests a verdict rejected. A rejection is a fact about
    #: bytes and does not expire, so a goal carries these across cycles:
    #: a later cycle may render a claim from a result an earlier cycle
    #: already rejected.
    rejected_artifact_sha256s: tuple[str, ...] = ()
    #: Whether this run rendered any claim at all. A run that rendered
    #: none did not replace the standing delivery -- which is exactly how
    #: a recovery that fixed the structure and claimed nothing left the
    #: superseded number standing as the goal's answer.
    claims_rendered: bool = False
    #: Quantities an expression exported and no claim ever rendered. The
    #: host computed them from real program output and no reader of the
    #: delivery can see them: across the recorded campaign 89 of 242
    #: exported quantities were never claimed, and five goals exported
    #: quantities and claimed none at all -- four of those settled
    #: achieved with engine calls still unspent. An expression that is
    #: evaluated and never claimed is not delivered.
    unclaimed_output_ids: tuple[str, ...] = ()


def _stale_quantity_ids(
    *,
    claim_pairs: Sequence[tuple[str, str]],
    rejected_bindings: Sequence[tuple[str, str]],
    expression_outputs: Sequence[tuple[str, str, tuple[str, ...]]],
    artifact_by_receipt: Mapping[str, str],
    inherited_rejected_artifacts: Sequence[str] = (),
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Delivered quantities standing on a result its own verdict rejected.

    What a verdict rejects is a **result**, and a result is not a
    receipt: one finished calculation is routinely read by several
    extraction calls, each with its own receipt.  Keying the rejection
    on the receipt the failed rule happened to read lets every other
    read of the same result escape -- one live run extracted
    frequencies and coordinates from one saddle in two calls, and the
    torsion of that rejected structure, which was the task's own
    requested observable, was reported as delivered beside the
    zero-point energy that was correctly withheld.  So the seed
    resolves to artifact digests and taints every receipt that read
    them.

    A rule that reads an expression output rather than an extraction
    resolves backwards through that output's own sources, because the
    verdict is about the structure underneath, not about the
    arithmetic: one run computed a complexation energy and a barrier in
    a single expression, and only the barrier stood on the rejected
    result.

    Returns the stale quantity ids and the rejected artifact digests,
    the latter so a goal can carry them across cycles -- a rejection is
    a fact about bytes and does not expire.
    """

    sources_by_output = {
        (receipt, output_id): sources
        for receipt, output_id, sources in expression_outputs
    }
    rejected_artifacts = {
        str(item) for item in inherited_rejected_artifacts if item
    }

    def _resolve(receipt: str, quantity_id: str, depth: int = 0) -> None:
        """Name the results a rejected binding ultimately rests on."""

        if depth > 8:
            return
        artifact = artifact_by_receipt.get(receipt)
        if artifact:
            rejected_artifacts.add(artifact)
            return
        for source in sources_by_output.get((receipt, quantity_id), ()):
            if not source:
                continue
            producer = artifact_by_receipt.get(source)
            if producer:
                rejected_artifacts.add(producer)
                continue
            for other, output_id in sources_by_output:
                if other == source:
                    _resolve(other, output_id, depth + 1)

    for receipt, quantity_id in rejected_bindings:
        if receipt:
            _resolve(receipt, quantity_id)

    # Every read of a rejected result, not only the one the rule saw.
    tainted_receipts = {
        receipt
        for receipt, artifact in artifact_by_receipt.items()
        if artifact in rejected_artifacts
    }
    seeded = set(tainted_receipts)
    tainted_outputs: set[tuple[str, str]] = set()
    while True:
        grew = False
        for receipt, output_id, sources in expression_outputs:
            if (receipt, output_id) in tainted_outputs:
                continue
            if not tainted_receipts.intersection(sources):
                continue
            tainted_outputs.add((receipt, output_id))
            tainted_receipts.add(receipt)
            grew = True
        if not grew:
            break
    stale = tuple(
        sorted(
            {
                quantity_id
                for receipt, quantity_id in claim_pairs
                if quantity_id
                and (
                    receipt in seeded
                    or (receipt, quantity_id) in tainted_outputs
                )
            }
        )
    )
    return stale, tuple(sorted(rejected_artifacts))


def _analysis_delivery(
    events_path: Path,
    *,
    inherited_rejected_artifacts: Sequence[str] = (),
) -> _AnalysisDelivery:
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
    failed_verdicts: list[tuple[str, str, str]] = []
    decision_refs: set[str] = set()
    claims = 0
    decisions = 0
    receipts: list[str] = []
    doubt_refs: set[str] = set()
    claim_pairs: list[tuple[str, str]] = []
    rejected_bindings: list[tuple[str, str]] = []
    expression_outputs: list[tuple[str, str, tuple[str, ...]]] = []
    artifact_by_receipt: dict[str, str] = {}
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
            record = payload.get("record") or {}
            for reference in record.get("evidence_refs") or ():
                text_ref = str(reference)
                if text_ref.startswith("doubt:"):
                    doubt_refs.add(text_ref[len("doubt:") :])
                # A decision that cites the validation receipt has looked
                # at the failed verdict and stood by its delivery. That is
                # the scientist's call to make, and citing the receipt is
                # how it is made without the host grading prose.
                decision_refs.add(text_ref.split(":")[-1])
        elif kind == "analysis_claims_recorded":
            claims += 1
            if digest:
                receipts.append(digest)
            record = payload.get("record") or {}
            for claim in record.get("claims") or ():
                claim_pairs.append(
                    (
                        str(claim.get("source_receipt_sha256") or ""),
                        str(claim.get("quantity_id") or ""),
                    )
                )
        elif kind == "analysis_completion_evaluated":
            completion_status = str(payload.get("status") or "")
            limitations = tuple(
                str(item)
                for item in (payload.get("limitation_output_ids") or ())
            )
            if digest:
                receipts.append(digest)
        elif kind == "scientific_validation_evaluated":
            if digest:
                receipts.append(digest)
            if not bool(payload.get("all_rules_passed", True)):
                node_id = str(payload.get("node_id") or "")
                record = payload.get("record") or {}
                bindings = {
                    str(binding.get("input_id") or ""): (
                        str(binding.get("source_receipt_sha256") or ""),
                        str(binding.get("quantity_id") or ""),
                    )
                    for binding in record.get("input_bindings") or ()
                }
                for rule in record.get("rule_results") or ():
                    if not bool(rule.get("passed", True)):
                        failed_verdicts.append(
                            (
                                node_id,
                                str(rule.get("rule_id") or ""),
                                digest,
                            )
                        )
                        # The rule read these receipts and rejected what
                        # it found in them; everything else computed from
                        # the same receipts describes the same rejected
                        # structure.
                        for input_id in rule.get("input_ids") or ():
                            binding = bindings.get(str(input_id))
                            if binding and binding[0]:
                                rejected_bindings.append(binding)
        elif kind in {
            "result_quantities_extracted",
            "quantity_expression_evaluated",
            "thermochemistry_derived",
        }:
            if digest:
                receipts.append(digest)
            if kind == "result_quantities_extracted" and digest:
                # The result this receipt read. A verdict rejects the
                # result, and one result is routinely read by several
                # extraction calls.
                record = payload.get("record") or {}
                artifact = str(
                    payload.get("artifact_sha256")
                    or record.get("artifact_sha256")
                    or ""
                )
                if artifact:
                    artifact_by_receipt[digest] = artifact
            if kind == "quantity_expression_evaluated" and digest:
                record = payload.get("record") or {}
                for dependency in record.get("output_dependencies") or ():
                    expression_outputs.append(
                        (
                            digest,
                            str(dependency.get("output_id") or ""),
                            tuple(
                                str(item)
                                for item in (
                                    dependency.get("source_receipt_sha256s")
                                    or ()
                                )
                            ),
                        )
                    )
    unanswered = tuple(
        f"{node_id}/{rule_id}"
        for node_id, rule_id, digest in failed_verdicts
        if digest not in decision_refs
    )
    stale, rejected_artifacts = _stale_quantity_ids(
        claim_pairs=claim_pairs,
        rejected_bindings=rejected_bindings,
        expression_outputs=expression_outputs,
        artifact_by_receipt=artifact_by_receipt,
        inherited_rejected_artifacts=inherited_rejected_artifacts,
    )
    # An expression's exported outputs, as opposed to the intermediate
    # node_values it computed on the way: the receipt contract pins
    # output_dependencies' ids to outputs' quantity_ids, in order, so the
    # lineage already collected names exactly what was exported.
    claimed_ids = {
        quantity_id for _receipt, quantity_id in claim_pairs if quantity_id
    }
    exported_output_ids = {
        output_id
        for _digest, output_id, _sources in expression_outputs
        if output_id
    }
    return _AnalysisDelivery(
        unclaimed_output_ids=tuple(sorted(exported_output_ids - claimed_ids)),
        unanswered_verdicts=unanswered,
        completion_status=completion_status,
        limitation_output_ids=limitations,
        claims=claims,
        decisions=decisions,
        receipt_sha256s=tuple(receipts),
        doubted_quantity_ids=tuple(
            sorted(
                {
                    quantity_id
                    for receipt, quantity_id in claim_pairs
                    if quantity_id and receipt in doubt_refs
                }
            )
        ),
        delivered_quantity_ids=tuple(
            sorted(
                {
                    quantity_id
                    for _receipt, quantity_id in claim_pairs
                    if quantity_id and quantity_id not in stale
                }
            )
        ),
        stale_quantity_ids=stale,
        rejected_artifact_sha256s=rejected_artifacts,
        claims_rendered=bool(claims),
    )


def _settlement_evidence(delivery: _AnalysisDelivery) -> dict[str, Any]:
    """Receipts a settlement cites, from the session's own stream."""

    if delivery.decisions and delivery.receipt_sha256s:
        return {
            "scientific_decisions": delivery.decisions,
            "receipt_sha256s": delivery.receipt_sha256s,
        }
    return {}


#: The goal's task text, kept beside its ledger so a resumed driver plans
#: the next cycle against exactly what the human asked.
TASK_FILE = "task.md"

#: How the driver was constructed -- envelope, grant, provider, dispatch
#: -- so a process that wakes the goal needs only the workspace and id.
DRIVER_FILE = "driver.json"

#: Where an approved run is executed: in this process, or handed to the
#: server profile's scheduler with the job waking the goal when done.
DISPATCH_MODES = ("local", "scheduler")

#: The phases one goal cycle passes through, in order. ``parked`` and
#: ``settled`` are where a process may stop: a parked goal has a run in
#: a scheduler's hands and resumes at ``outcome``; a settled goal is
#: finished.
GOAL_PHASES = (
    "plan",
    "decide",
    "execute",
    "outcome",
    "settle",
    "parked",
    "settled",
)


@dataclass(frozen=True)
class GoalStepV1:
    """One phase the driver just performed."""

    phase: str
    next_phase: str
    cycle: int
    result: GoalLoopResultV1 | None = None


class GoalDriver:
    """Drive one goal to settlement under one human decision, one step at
    a time.

    ``initial_decision`` is the human's: "approve" records it under
    ``granted_by`` exactly as ``agent review --decision approve`` would,
    and anything else settles the goal ``returned_to_human`` before any
    engine runs. Every later cycle's decision is host-admitted under the
    goal and recorded with the composite actor.

    ``dispatch_run``, when given, replaces the in-process engine walk:
    it hands the approved bundle and run directory to a scheduler and
    returns a receipt naming the job; the driver records
    ``run_dispatched`` and parks. :meth:`resume` rebuilds a driver from
    the ledger at the ``outcome`` phase once the job has finished.
    """

    def __init__(
        self,
        *,
        task: str,
        workspace: str | Path,
        execution_envelope_file: str | Path | None,
        goal_id: str,
        granted_by: str,
        max_revisions: int = 5,
        provider: str | None = None,
        provider_config_file: str | Path | None = None,
        analysis_completion_file: str | Path | None = None,
        plan_session: Callable[..., Any] = _default_plan_session,
        resolve_review: Callable[..., tuple[str, Path]] = _default_resolve,
        execute_bundle: Callable[..., Any] = _default_execute,
        dispatch_run: Callable[..., Any] | None = None,
        dispatch: str = "local",
        server: str | None = None,
        initial_decision: str = "approve",
        stop_file: str | Path | None = None,
        session_kwargs: Mapping[str, Any] | None = None,
        _resuming: bool = False,
    ) -> None:
        if dispatch not in DISPATCH_MODES:
            raise ContractError(
                f"unsupported dispatch mode {dispatch!r}; "
                f"choose one of {DISPATCH_MODES}"
            )
        self.task = task
        self.workspace = Path(workspace).resolve()
        self.goal_id = goal_id
        self.granted_by = granted_by
        self.max_revisions = max_revisions
        self.provider = provider
        self.provider_config_file = provider_config_file
        self.execution_envelope_file = execution_envelope_file
        self.analysis_completion_file = analysis_completion_file
        self.plan_session = plan_session
        self.resolve_review = resolve_review
        self.execute_bundle = execute_bundle
        self.dispatch = dispatch
        self.server = server
        if dispatch_run is None and dispatch == "scheduler":
            from functools import partial

            from chemsmart.agent.dispatch import dispatch_run_to_scheduler

            dispatch_run = partial(dispatch_run_to_scheduler, server=server)
        self.dispatch_run = dispatch_run
        self.initial_decision = initial_decision
        self.stop_file = stop_file
        self.session_kwargs = dict(session_kwargs or {})

        self.goal_dir = self.workspace / ".chemsmart-agent" / "goals" / goal_id
        self.ledger = GoalLedger(self.goal_dir)
        self.ledger.directory.mkdir(parents=True, exist_ok=True)
        if not _resuming and self.ledger.goal_path.exists():
            raise ContractError(
                "this goal already exists; a goal is one human decision, "
                "not a resumable queue. A parked goal is resumed with "
                "GoalDriver.resume (chemsmart agent wake)."
            )
        if not _resuming:
            # The task text is what every later cycle plans against; a
            # process that resumes a parked goal reads it from here, and
            # the construction record beside it says how to drive on.
            (self.goal_dir / TASK_FILE).write_text(str(task), encoding="utf-8")
            (self.goal_dir / DRIVER_FILE).write_text(
                json.dumps(
                    {
                        "schema_version": "chemsmart.goal-driver.v1",
                        "execution_envelope_file": _resolved_or_none(
                            execution_envelope_file
                        ),
                        "granted_by": granted_by,
                        "max_revisions": int(max_revisions),
                        "provider": provider,
                        "provider_config_file": _resolved_or_none(
                            provider_config_file
                        ),
                        "analysis_completion_file": _resolved_or_none(
                            analysis_completion_file
                        ),
                        "dispatch": dispatch,
                        "server": server,
                        "stop_file": _resolved_or_none(stop_file),
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

        self.envelope = None
        self.envelope_record: dict[str, Any] = {}
        if execution_envelope_file is not None:
            from chemsmart.agent.execution_envelope import (
                load_bounded_execution_envelope,
            )

            self.envelope = load_bounded_execution_envelope(
                execution_envelope_file
            )
            self.envelope_record = {
                "allowed_program_engines": (
                    self.envelope.allowed_program_engines
                ),
                "max_engine_calls": self.envelope.max_engine_calls,
                "episode_wall_time_seconds": (
                    self.envelope.episode_wall_time_seconds
                ),
            }

        self.goal: GoalRecordV1 | None = None
        self.outcome: Any = None
        self.cycles = 0
        self.revisions_admitted = 0
        # A rejection is a fact about bytes and does not expire, so the
        # rejected results accumulate; the *standing* delivery is
        # whatever the most recent claim-rendering cycle said, because
        # that is what the goal currently answers with. Keying this on
        # quantity ids instead would ask a later cycle to reuse an
        # earlier cycle's names: one live recovery re-derived a torsion
        # correctly under a new id and would have been held open forever
        # over a number it had already replaced.
        self.rejected_artifacts: set[str] = set()
        self.standing_stale: tuple[str, ...] = ()

        self.phase = "plan"
        self.result: GoalLoopResultV1 | None = None
        self.wake: dict[str, Any] | None = None
        self.session: Any = None
        self.events_path: Path | None = None
        self.review_file: Path | None = None
        self.bundle_file: Path | None = None
        self.run_directory: Path | None = None
        self.execute_result: Any = None
        self.dispatch_receipt: Any = None

    # -- public surface ---------------------------------------------------

    @classmethod
    def resume(
        cls, *, workspace: str | Path, goal_id: str, **kwargs: Any
    ) -> "GoalDriver":
        """Rebuild a parked goal's driver from its ledger, at ``outcome``.

        Admitted only when the ledger's last run was dispatched and never
        recorded, and the goal is not settled: the same one human
        decision continues in its own run directory, and nothing here
        creates a second one.
        """

        goal_dir = (
            Path(workspace).resolve() / ".chemsmart-agent" / "goals" / goal_id
        )
        try:
            recorded = json.loads(
                (goal_dir / DRIVER_FILE).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            recorded = {}
        for key in (
            "execution_envelope_file",
            "granted_by",
            "max_revisions",
            "provider",
            "provider_config_file",
            "analysis_completion_file",
            "dispatch",
            "server",
            "stop_file",
        ):
            if key not in kwargs and recorded.get(key) is not None:
                kwargs[key] = recorded[key]
        if "granted_by" not in kwargs:
            raise ContractError(
                f"goal {goal_id!r} has no recorded grant to resume under"
            )
        driver = cls(
            task=str(kwargs.pop("task", "")),
            workspace=workspace,
            goal_id=goal_id,
            _resuming=True,
            **kwargs,
        )
        if not driver.ledger.goal_path.exists():
            raise ContractError(f"goal {goal_id!r} has no ledger to resume")
        entries = driver.ledger.entries()
        if any(entry["kind"] == "goal_settled" for entry in entries):
            raise ContractError(f"goal {goal_id!r} is settled")
        dispatched = [
            entry for entry in entries if entry["kind"] == "run_dispatched"
        ]
        recorded_cycles = {
            int(entry["payload"].get("cycle", 0))
            for entry in entries
            if entry["kind"] == "run_recorded"
        }
        parked = [
            entry
            for entry in dispatched
            if int(entry["payload"].get("cycle", 0)) not in recorded_cycles
        ]
        if not parked:
            raise ContractError(
                f"goal {goal_id!r} has no parked run to resume"
            )
        entry = parked[-1]
        driver.goal = driver.ledger.load()
        if not driver.task:
            try:
                driver.task = (driver.goal_dir / TASK_FILE).read_text(
                    encoding="utf-8"
                )
            except OSError as exc:
                raise ContractError(
                    f"goal {goal_id!r} has no recorded task text to resume"
                ) from exc
        driver.cycles = int(entry["payload"]["cycle"])
        driver.revisions_admitted = sum(
            1 for item in entries if item["kind"] == "revision_admitted"
        )
        # Replay the standing delivery from every earlier recorded run, in
        # order, so a rejection made in cycle 1 still taints cycle 3.
        for item in entries:
            if item["kind"] != "run_recorded":
                continue
            delivery = _analysis_delivery(
                driver.workspace
                / ".chemsmart-agent"
                / Path(*str(item["payload"].get("run") or "").split("/"))
                / "events.jsonl",
                inherited_rejected_artifacts=tuple(
                    sorted(driver.rejected_artifacts)
                ),
            )
            driver.rejected_artifacts.update(
                delivery.rejected_artifact_sha256s
            )
            if delivery.claims_rendered:
                driver.standing_stale = delivery.stale_quantity_ids
        driver.run_directory = (
            driver.goal_dir / "runs" / f"cycle-{driver.cycles}"
        )
        driver.dispatch_receipt = dict(entry["payload"])
        driver.execute_result = _recorded_execution_result(
            driver.run_directory
        )
        driver.phase = "outcome"
        return driver

    @classmethod
    def from_review(
        cls,
        *,
        review_file: str | Path,
        task_spec_sha256: str = "",
        **kwargs: Any,
    ) -> "GoalDriver":
        """A driver at ``decide`` over a review a session already wrote.

        This is how a stored review is re-presented for one fresh human
        decision -- the terminal interface's resume, `agent review` --
        without planning again: the review file stands in for cycle 1's
        session, and everything from the decision on is the same
        machine.
        """

        driver = cls(**kwargs)
        driver.cycles = 1
        driver.review_file = Path(review_file)
        driver.session = SimpleNamespace(
            terminal_state="waiting_for_approval",
            task_spec_sha256=str(task_spec_sha256 or ""),
        )
        driver.phase = "decide"
        return driver

    def run(self) -> GoalLoopResultV1:
        """Step until the goal settles or parks."""

        while self.phase not in {"settled", "parked"}:
            self.step()
        assert self.result is not None
        return self.result

    def step(self) -> GoalStepV1:
        """Perform exactly one phase and say which comes next."""

        phase = self.phase
        if phase in {"settled", "parked"}:
            raise ContractError(f"goal {self.goal_id!r} is {phase}")
        handler = {
            "plan": self._plan,
            "decide": self._decide,
            "execute": self._execute,
            "outcome": self._outcome,
            "settle": self._settle,
        }[phase]
        handler()
        return GoalStepV1(
            phase=phase,
            next_phase=self.phase,
            cycle=self.cycles,
            result=self.result,
        )

    # -- phases -------------------------------------------------------------

    def _stopped(self) -> bool:
        return bool(self.stop_file and Path(self.stop_file).exists())

    def _settled(
        self, settlement: str, reasons: tuple[str, ...]
    ) -> GoalLoopResultV1:
        self.result = GoalLoopResultV1(
            goal_id=self.goal_id,
            settlement=settlement,
            cycles=self.cycles,
            revisions_admitted=self.revisions_admitted,
            reasons=reasons,
        )
        self.phase = "settled"
        return self.result

    def _settle_delivery(self, terminal: str) -> GoalLoopResultV1:
        if self.events_path is None:
            # Nothing durable to read a delivery from: the goal still ends
            # in a typed state, and the reason says why a human reads it.
            reason = (
                f"session terminal state: {terminal}; the planning session "
                "left no event stream"
            )
            self.ledger.settle("returned_to_human", reasons=(reason,))
            return self._settled("returned_to_human", (reason,))
        self.result = _settle_from_delivery(
            self.ledger,
            goal_id=self.goal_id,
            cycles=self.cycles,
            revisions_admitted=self.revisions_admitted,
            events_path=self.events_path,
            terminal=terminal,
        )
        self.phase = "settled"
        return self.result

    def _typed_error(self, stage: str, error: ContractError) -> None:
        self.result = _typed_error_settlement(
            self.ledger,
            goal_id=self.goal_id,
            cycles=self.cycles,
            revisions_admitted=self.revisions_admitted,
            stage=stage,
            error=error,
        )
        self.phase = "settled"

    def _goal_record(
        self,
        *,
        identity: str,
        conditions: Mapping[str, Any],
        review_sha256: str,
    ) -> GoalRecordV1:
        return GoalRecordV1(
            schema_version=GOAL_SCHEMA_VERSION,
            goal_id=self.goal_id,
            task_spec_sha256=str(
                getattr(self.session, "task_spec_sha256", "") or ""
            ),
            scientific_identity_sha256=identity,
            conditions=conditions,
            envelope=self.envelope_record,
            max_revisions=self.max_revisions,
            granted_by=self.granted_by,
            initial_review_sha256=review_sha256,
            created_at=_utc_now(),
        )

    def _plan(self) -> None:
        self.cycles += 1
        if self._stopped():
            self.ledger.append(
                "cancelled_by_human",
                {"cycle": self.cycles, "at": _utc_now()},
            )
            self.ledger.settle(
                "returned_to_human",
                reasons=("cancelled by the human's stop file",),
            )
            self._settled("returned_to_human", ("cancelled",))
            return
        self.review_file = (
            self.goal_dir / "reviews" / f"cycle-{self.cycles}.json"
        )
        self.review_file.parent.mkdir(parents=True, exist_ok=True)
        self.wake = (
            _wake_context(
                self.goal, self.ledger, self.outcome, workspace=self.workspace
            )
            if self.goal is not None
            else _goal_terms_context(
                goal_id=self.goal_id,
                granted_by=self.granted_by,
                envelope_record=self.envelope_record,
                max_revisions=self.max_revisions,
            )
        )
        if self.wake is not None and self.wake.get("previous_run"):
            # Host attestation for the evidence gate: this cycle's
            # session was handed the named run's typed outcome.
            self.ledger.append(
                "wake_composed",
                {"cycle": self.cycles, "run": self.wake["previous_run"]},
            )
        try:
            self.session = self.plan_session(
                task=self.task,
                provider=self.provider,
                provider_config_file=self.provider_config_file,
                workspace=self.workspace,
                execution_enabled=False,
                approval_file=None,
                execution_envelope_file=self.execution_envelope_file,
                analysis_completion_file=self.analysis_completion_file,
                review_file=self.review_file,
                goal_context=self.wake,
                **self.session_kwargs,
            )
        except ContractError as exc:
            self._typed_error("planning session", exc)
            return
        terminal = str(getattr(self.session, "terminal_state", "") or "")
        try:
            self.events_path = _session_events_path(
                self.session, self.workspace
            )
        except ContractError:
            # A session that left no stream can still be decided on if it
            # prepared a review; it cannot settle a delivery or carry the
            # evidence a revision must cite, and those paths say so.
            self.events_path = None
        if terminal != "waiting_for_approval":
            # No executable partition was planned. Either the session
            # delivered over registered results, refused with receipts,
            # or stopped; each settles the goal from durable evidence.
            if self.goal is None:
                self.goal = self._goal_record(
                    identity="",
                    conditions={"solvents": (), "thermochemistry": ()},
                    review_sha256="",
                )
                self.ledger.create(self.goal)
            self._settle_delivery(terminal)
            return
        self.phase = "decide"

    def _decide(self) -> None:
        assert self.review_file is not None
        review = _review_record(self.review_file)
        if self.goal is None:
            if not self.envelope_record:
                # No envelope file was given (the terminal interface
                # over a stored review): the envelope the human is
                # deciding on is the one the review itself displays.
                shown = dict(review.get("execution_envelope") or {})
                self.envelope_record = {
                    "allowed_program_engines": canonical_data(
                        shown.get("allowed_program_engines") or ()
                    ),
                    "max_engine_calls": int(
                        shown.get("max_engine_calls") or 0
                    ),
                    "episode_wall_time_seconds": float(
                        shown.get("episode_wall_time_seconds") or 0.0
                    ),
                }
            if self.initial_decision != "approve":
                self.ledger.create(
                    self._goal_record(
                        identity=_plan_identity_sha256(review),
                        conditions=conditions_from_review(review),
                        review_sha256="",
                    )
                )
                self.ledger.settle(
                    "returned_to_human",
                    reasons=("the human declined the initial review",),
                )
                self._settled(
                    "returned_to_human", ("initial review declined",)
                )
                return
            review_sha256, self.bundle_file = self.resolve_review(
                review_file=self.review_file,
                workspace=self.workspace,
                decision="approve",
                actor=self.granted_by,
                approval_id=f"goal-{self.goal_id}-cycle-{self.cycles}",
            )
            self.goal = self._goal_record(
                identity=_plan_identity_sha256(review),
                conditions=conditions_from_review(review),
                review_sha256=review_sha256,
            )
            self.ledger.create(self.goal)
            self.phase = "execute"
            return
        if self.events_path is None:
            raise ContractError(
                "a revision must come from a session with an event stream"
            )
        budgets = self.ledger.budgets(self.goal)
        verdict = admit_revision(
            goal=self.goal,
            budgets=budgets,
            revision_review=review,
            revision_scientific_identity_sha256=_plan_identity_sha256(review),
            session_events_path=self.events_path,
            prior_outcome_evidence_hashes=tuple(
                digest
                for node in (self.outcome.nodes if self.outcome else ())
                for digest in node.evidence_event_hashes
            ),
            previous_run_reference=_previous_run_reference(self.ledger),
            wake_embedded_run=str((self.wake or {}).get("previous_run") or ""),
        )
        if not verdict.admitted:
            self.ledger.append(
                "revision_returned",
                {"cycle": self.cycles, "reasons": verdict.reasons},
            )
            self.ledger.settle("returned_to_human", reasons=verdict.reasons)
            self._settled("returned_to_human", verdict.reasons)
            return
        review_sha256, self.bundle_file = self.resolve_review(
            review_file=self.review_file,
            workspace=self.workspace,
            decision="approve",
            actor=self.goal.actor,
            approval_id=f"goal-{self.goal_id}-cycle-{self.cycles}",
        )
        self.revisions_admitted += 1
        self.ledger.append(
            "revision_admitted",
            {
                "cycle": self.cycles,
                "review_sha256": review_sha256,
                "actor": self.goal.actor,
                "granted_by": self.goal.granted_by,
                "checks": dict(verdict.checks),
                "cited_evidence_event_hashes": (
                    verdict.cited_evidence_event_hashes
                ),
            },
        )
        self.phase = "execute"

    def _execute(self) -> None:
        assert self.bundle_file is not None
        self.run_directory = self.goal_dir / "runs" / f"cycle-{self.cycles}"
        self.run_directory.mkdir(parents=True, exist_ok=True)
        run_reference = f"goals/{self.goal_id}/runs/cycle-{self.cycles}"
        if self.dispatch_run is not None:
            try:
                receipt = self.dispatch_run(
                    approval_file=self.bundle_file,
                    workspace=self.workspace,
                    run_directory=self.run_directory,
                    goal_id=self.goal_id,
                    cycle=self.cycles,
                )
            except ContractError as exc:
                self._typed_error("scheduler dispatch", exc)
                return
            self.dispatch_receipt = receipt
            payload = {
                "cycle": self.cycles,
                "run": run_reference,
                **{
                    key: value
                    for key, value in _record_of(receipt).items()
                    if key
                    in {
                        "scheduler",
                        "job_id",
                        "submitted_at",
                        "submit_script",
                        "wake_job_id",
                    }
                },
            }
            self.ledger.append("run_dispatched", payload)
            self.result = GoalLoopResultV1(
                goal_id=self.goal_id,
                settlement="parked",
                cycles=self.cycles,
                revisions_admitted=self.revisions_admitted,
                reasons=(
                    f"cycle {self.cycles} submitted as "
                    f"{payload.get('scheduler', 'scheduler')} job "
                    f"{payload.get('job_id', '?')}; resume with "
                    f"chemsmart agent wake --goal {self.goal_id}",
                ),
            )
            self.phase = "parked"
            return
        try:
            self.execute_result = self.execute_bundle(
                approval_file=self.bundle_file,
                workspace=self.workspace,
                run_directory=self.run_directory,
            )
        except ContractError as exc:
            self._typed_error("approved execution", exc)
            return
        self.phase = "outcome"

    def _outcome(self) -> None:
        assert self.run_directory is not None
        from chemsmart.agent.terminal_states import (
            derive_run_outcome,
            read_run_events,
        )

        run_reference = f"goals/{self.goal_id}/runs/cycle-{self.cycles}"
        events_path = self.run_directory / "events.jsonl"
        try:
            self.outcome = derive_run_outcome(read_run_events(events_path))
        except (ValueError, OSError) as exc:
            if isinstance(exc, ValueError) and "found 0" not in str(exc):
                raise
            # An admitted revision whose approved bundle launched no
            # engine: the executor walked the analysis chain into the
            # run stream and recorded no workflow run. Observed live
            # (C8): the cycle is a legitimate delivery-or-return, and
            # letting the derivation's own contract error escape left
            # the goal unsettled. Settle from the run stream's typed
            # delivery, exactly as a no-partition planning cycle does.
            self.ledger.append(
                "run_recorded",
                {
                    "cycle": self.cycles,
                    "run": run_reference,
                    "workflow_state": "analysis_only",
                    "engine_calls_consumed": 0,
                    "engine_wall_seconds": 0.0,
                },
            )
            self.events_path = events_path
            self._settle_delivery("complete")
            return
        payload = {
            "cycle": self.cycles,
            "run": run_reference,
            "workflow_state": self.outcome.workflow_state,
            "engine_calls_consumed": self.outcome.engine_calls_consumed,
            "engine_wall_seconds": self.outcome.engine_wall_seconds,
        }
        if self.dispatch_receipt is not None:
            payload["queue_wait_seconds"] = _queue_wait_seconds(
                self.dispatch_receipt, events_path
            )
        self.ledger.append("run_recorded", payload)
        if self.execute_result is None:
            self.execute_result = _recorded_execution_result(
                self.run_directory
            ) or SimpleNamespace(
                status=(
                    "completed"
                    if self.outcome.workflow_state == "completed"
                    else self.outcome.workflow_state
                ),
                analysis_status="",
            )
        self.phase = "settle"

    def _settle(self) -> None:
        assert self.run_directory is not None and self.goal is not None
        run_delivery = _analysis_delivery(
            self.run_directory / "events.jsonl",
            inherited_rejected_artifacts=tuple(
                sorted(self.rejected_artifacts)
            ),
        )
        self.rejected_artifacts.update(run_delivery.rejected_artifact_sha256s)
        if run_delivery.claims_rendered:
            self.standing_stale = run_delivery.stale_quantity_ids
        unrefreshed = self.standing_stale
        budgets = self.ledger.budgets(self.goal)
        recovery_affordable = (
            budgets.engine_calls_remaining > 0
            and budgets.revisions_remaining > 0
            and budgets.wall_seconds_remaining > 0
        )
        open_delivery = bool(
            run_delivery.unanswered_verdicts
            or unrefreshed
            or run_delivery.unclaimed_output_ids
        )
        achieved = _achieved(self.execute_result)
        if achieved and open_delivery and recovery_affordable:
            # Every required output arrived and a host-rendered verdict
            # says one of the structures behind them is not what the
            # task required. Two live cases settled achieved here in one
            # cycle with four engine calls unspent, so no session was
            # ever asked whether it wanted to answer the failure it had
            # just been shown. Withhold the word and wake another cycle
            # while a recovery is still affordable; the session may
            # recover, or cite the validation receipt in its decision
            # and stand by the delivery. What it may not do is have the
            # choice made for it by a settlement.
            self.ledger.append(
                "recovery_opened",
                {
                    "cycle": self.cycles,
                    "verdicts": list(run_delivery.unanswered_verdicts),
                    "stale_quantity_ids": list(unrefreshed),
                    "unclaimed_output_ids": list(
                        run_delivery.unclaimed_output_ids
                    ),
                    "engine_calls_remaining": budgets.engine_calls_remaining,
                },
            )
            self.phase = "plan"
            return
        if achieved and open_delivery:
            # Same failure, nothing left to answer it with.
            if run_delivery.unanswered_verdicts:
                reason = (
                    f"cycle {self.cycles}: a validation verdict failed and "
                    "no budget remains to answer it: "
                    + ", ".join(run_delivery.unanswered_verdicts)
                )
                open_items = run_delivery.unanswered_verdicts
            elif unrefreshed:
                reason = (
                    f"cycle {self.cycles}: a verdict rejected the result "
                    "these quantities were computed from and no budget "
                    "remains to re-derive them: " + ", ".join(unrefreshed)
                )
                open_items = unrefreshed
            else:
                # The host computed these from real program output and
                # no reader of the delivery can see them.
                reason = (
                    f"cycle {self.cycles}: these quantities were computed "
                    "and never rendered as a claim, and no budget remains "
                    "to deliver them: "
                    + ", ".join(run_delivery.unclaimed_output_ids)
                )
                open_items = run_delivery.unclaimed_output_ids
            self.ledger.settle("returned_to_human", reasons=(reason,))
            self._settled("returned_to_human", open_items)
            return
        if achieved:
            self.ledger.settle(
                "achieved",
                reasons=(
                    f"cycle {self.cycles}: workflow completed with its "
                    "analysis chain",
                ),
            )
            self._settled("achieved", ())
            return
        if (
            budgets.revisions_remaining <= 0
            or budgets.engine_calls_remaining <= 0
            or budgets.wall_seconds_remaining <= 0
        ):
            self.ledger.settle(
                "exhausted",
                reasons=(
                    f"engine calls remaining "
                    f"{budgets.engine_calls_remaining}, wall seconds "
                    f"remaining {budgets.wall_seconds_remaining:.0f}, "
                    f"revisions remaining "
                    f"{budgets.revisions_remaining}",
                ),
            )
            self._settled("exhausted", ("budgets exhausted",))
            return
        # A run that did not complete, with budget in hand: the next
        # cycle's session reads the typed outcome and may revise.
        self.phase = "plan"


def _resolved_or_none(path: str | Path | None) -> str | None:
    return str(Path(path).resolve()) if path is not None else None


def _record_of(receipt: Any) -> dict[str, Any]:
    """A receipt's public fields, whatever kind of object carries them."""

    if isinstance(receipt, Mapping):
        return dict(receipt)
    if hasattr(receipt, "public_record"):
        return dict(receipt.public_record())
    if hasattr(receipt, "__dataclass_fields__"):
        from dataclasses import asdict

        return asdict(receipt)
    return dict(vars(receipt))


#: Where a dispatched run's job writes the executor's own result record,
#: so the driver that resumes it reads the same status words a local run
#: returns in memory.
EXECUTION_RESULT_FILE = "execution-result.json"


def _recorded_execution_result(run_directory: Path) -> Any:
    path = Path(run_directory) / EXECUTION_RESULT_FILE
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(record, Mapping):
        return None
    return SimpleNamespace(
        status=str(record.get("status") or ""),
        analysis_status=str(record.get("analysis_status") or ""),
    )


def _queue_wait_seconds(receipt: Any, events_path: Path) -> float | None:
    """Seconds between submission and the run's first recorded event."""

    submitted = str(_record_of(receipt).get("submitted_at") or "")
    if not submitted:
        return None
    try:
        first = events_path.read_text(encoding="utf-8").splitlines()[0]
        started = str(json.loads(first).get("at") or "")
        start = datetime.fromisoformat(started)
        submit = datetime.fromisoformat(submitted)
    except (OSError, IndexError, ValueError, json.JSONDecodeError):
        return None
    return max(0.0, (start - submit).total_seconds())


def run_goal_loop(**kwargs: Any) -> GoalLoopResultV1:
    """Drive one goal to settlement or parking in this process."""

    return GoalDriver(**kwargs).run()


__all__ = [
    "DISPATCH_MODES",
    "DRIVER_FILE",
    "EXECUTION_RESULT_FILE",
    "TASK_FILE",
    "GOAL_PHASES",
    "GoalDriver",
    "GoalLoopResultV1",
    "GoalStepV1",
    "run_goal_loop",
]
