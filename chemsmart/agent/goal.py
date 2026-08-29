"""The goal: one human decision that a bounded recovery loop consumes.

A frozen graph per approval means an agent cannot recover through
failure: the correct next move after a typed terminal state -- read it,
revise the route, continue -- was structurally unreachable, because the
approval was spent and every revision was a returning human action. The
goal moves the grain: the human approves the observables, the identity
bindings, the physical conditions, the envelope with its engine-call,
wall-clock, and revision budgets, and the complete initial plan; the
host then admits a revised workflow only when it cites the typed
terminal evidence it answers and preserves every invariant the human
approved. The model never approves. The goal approval is the sole
authority a revision consumes, and every admission names it beside the
human who granted it.

What lives here is deliberately deterministic: records, a ledger, the
condition extractor, and the admission checks. No provider call, no
retry policy, no judgement of whether a revision is scientifically
wise -- grading a route is what execution and validation are for.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from chemsmart.agent._contracts import (
    ContractError,
    canonical_data,
    canonical_sha256,
    require_identifier,
)

GOAL_SCHEMA_VERSION = "chemsmart.goal.v1"

#: Terminal goal settlements. ``unreachable_from_evidence`` is the typed
#: refusal the loop exists to make as deliverable as an answer: settling
#: there requires receipts, never prose alone.
GOAL_SETTLEMENTS = (
    "achieved",
    "exhausted",
    "unreachable_from_evidence",
    "returned_to_human",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_plan_conditions(
    *,
    project_settings_texts: tuple[str, ...],
    thermochemistry_controls: tuple[
        tuple[float | None, float | None, float | None], ...
    ],
) -> dict[str, Any]:
    """The physical conditions a plan runs under, as comparable data.

    Solvent names are conditions -- water versus toluene changes the
    chemistry -- while the continuum model that implements them is
    method, free to move under ruling 2. So the extractor collects
    every ``solvent`` value from the effective project settings and the
    (temperature, pressure, concentration) triples from planned
    thermochemistry, and nothing else. A revision must reproduce the
    sets exactly: adding a solvent, dropping solvation, or moving a
    temperature is a new goal and a returning human decision.
    """

    solvents: set[str] = set()
    for text in project_settings_texts:
        try:
            loaded = yaml.safe_load(text) or {}
        except yaml.YAMLError:
            continue

        def _walk(value: Any) -> None:
            if isinstance(value, Mapping):
                for key, item in value.items():
                    if str(key).strip().lower() == "solvent" and isinstance(
                        item, str
                    ):
                        cleaned = item.strip().lower()
                        if cleaned:
                            solvents.add(cleaned)
                    else:
                        _walk(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    _walk(item)

        _walk(loaded)
    thermo = sorted(
        (
            (
                None if t is None else round(float(t), 6),
                None if p is None else round(float(p), 6),
                None if c is None else round(float(c), 6),
            )
            for t, p, c in thermochemistry_controls
        ),
    )
    return {
        "solvents": tuple(sorted(solvents)),
        "thermochemistry": tuple(thermo),
    }


def conditions_from_review(review: Mapping[str, Any]) -> dict[str, Any]:
    """Extract the conditions a stored execution review displays."""

    node_reviews = review.get("node_reviews") or ()
    texts = tuple(
        str(item.get("project_settings_text") or "")
        for item in node_reviews
        if isinstance(item, Mapping)
    )
    toolchain = review.get("scientific_toolchain_plan") or {}
    controls: list[tuple[float | None, float | None, float | None]] = []
    for node in toolchain.get("analysis_nodes") or ():
        if not isinstance(node, Mapping):
            continue
        if str(node.get("analysis_kind") or "") != "thermochemistry":
            continue
        controls.append(
            (
                node.get("temperature_k"),
                node.get("pressure_atm"),
                node.get("concentration_mol_l"),
            )
        )
    return extract_plan_conditions(
        project_settings_texts=texts,
        thermochemistry_controls=tuple(controls),
    )


@dataclass(frozen=True)
class GoalRecordV1:
    """What the one human decision covers, digest-bound."""

    schema_version: str
    goal_id: str
    task_spec_sha256: str
    scientific_identity_sha256: str
    conditions: Mapping[str, Any]
    envelope: Mapping[str, Any]
    max_revisions: int
    granted_by: str
    initial_review_sha256: str
    created_at: str
    goal_sha256: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != GOAL_SCHEMA_VERSION:
            raise ContractError("unsupported goal schema")
        require_identifier(self.goal_id, "goal_id")
        if not self.granted_by.strip():
            raise ContractError("a goal names the human who granted it")
        if (
            isinstance(self.max_revisions, bool)
            or not isinstance(self.max_revisions, int)
            or self.max_revisions < 0
        ):
            raise ContractError("max_revisions must be a non-negative integer")
        body = canonical_data(
            {
                "schema_version": self.schema_version,
                "goal_id": self.goal_id,
                "task_spec_sha256": self.task_spec_sha256,
                "scientific_identity_sha256": (
                    self.scientific_identity_sha256
                ),
                "conditions": canonical_data(self.conditions),
                "envelope": canonical_data(self.envelope),
                "max_revisions": self.max_revisions,
                "granted_by": self.granted_by,
                "initial_review_sha256": self.initial_review_sha256,
                "created_at": self.created_at,
            }
        )
        digest = canonical_sha256(body)
        if self.goal_sha256:
            if self.goal_sha256 != digest:
                raise ContractError("goal record digest mismatch")
        else:
            object.__setattr__(self, "goal_sha256", digest)

    @property
    def actor(self) -> str:
        """The composite authority a host-admitted revision records."""

        return f"goal-approval:{self.goal_id}"


@dataclass(frozen=True)
class GoalBudgetsV1:
    """What remains of the human's grant, from durable evidence only."""

    engine_calls_remaining: int
    wall_seconds_remaining: float
    revisions_remaining: int


class GoalLedger:
    """Append-only account of one goal's cycles under its grant."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.goal_path = self.directory / "goal.json"
        self.ledger_path = self.directory / "ledger.jsonl"

    def create(self, record: GoalRecordV1) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.goal_path.exists():
            raise ContractError("goal already exists; a goal is created once")
        body = canonical_data(
            {
                "schema_version": record.schema_version,
                "goal_id": record.goal_id,
                "task_spec_sha256": record.task_spec_sha256,
                "scientific_identity_sha256": (
                    record.scientific_identity_sha256
                ),
                "conditions": canonical_data(record.conditions),
                "envelope": canonical_data(record.envelope),
                "max_revisions": record.max_revisions,
                "granted_by": record.granted_by,
                "initial_review_sha256": record.initial_review_sha256,
                "created_at": record.created_at,
                "goal_sha256": record.goal_sha256,
            }
        )
        self.goal_path.write_text(
            json.dumps(body, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.append("goal_created", {"goal_sha256": record.goal_sha256})

    def load(self) -> GoalRecordV1:
        raw = json.loads(self.goal_path.read_text(encoding="utf-8"))
        return GoalRecordV1(**raw)

    def append(self, kind: str, payload: Mapping[str, Any]) -> None:
        entry = {
            "kind": str(kind),
            "at": _utc_now(),
            "payload": canonical_data(payload),
        }
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")

    def entries(self) -> tuple[dict[str, Any], ...]:
        if not self.ledger_path.exists():
            return ()
        rows = []
        for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if text:
                rows.append(json.loads(text))
        return tuple(rows)

    def budgets(self, record: GoalRecordV1) -> GoalBudgetsV1:
        """Remaining grant, decremented by the ledger's recorded runs.

        The wall clock is durable here by construction: each recorded
        run carries the engine seconds its receipts state, so a goal
        resumed in a new process still knows what it has spent -- the
        per-invocation monotonic clock never was durable and is not
        consulted.
        """

        envelope = dict(record.envelope)
        calls = int(envelope.get("max_engine_calls") or 0)
        wall = float(envelope.get("episode_wall_time_seconds") or 0.0)
        revisions = record.max_revisions
        for entry in self.entries():
            if entry["kind"] == "run_recorded":
                calls -= int(
                    entry["payload"].get("engine_calls_consumed") or 0
                )
                wall -= float(
                    entry["payload"].get("engine_wall_seconds") or 0.0
                )
            elif entry["kind"] == "revision_admitted":
                revisions -= 1
        return GoalBudgetsV1(
            engine_calls_remaining=max(calls, 0),
            wall_seconds_remaining=max(wall, 0.0),
            revisions_remaining=max(revisions, 0),
        )

    def settle(
        self,
        state: str,
        *,
        reasons: tuple[str, ...],
        evidence: Mapping[str, Any] | None = None,
    ) -> None:
        if state not in GOAL_SETTLEMENTS:
            raise ContractError(f"unsupported goal settlement: {state!r}")
        if state == "unreachable_from_evidence" and not (evidence or {}):
            raise ContractError(
                "unreachable_from_evidence settles on receipts, never "
                "prose alone"
            )
        self.append(
            "goal_settled",
            {
                "state": state,
                "reasons": tuple(reasons),
                "evidence": canonical_data(evidence or {}),
            },
        )


def session_read_run_outcome(session_events_path: str | Path) -> bool:
    """Whether a session actually pulled a typed run outcome.

    The evidence gate does not ask the model to copy digests: the
    session's own sealed stream records every tool call, so the host
    verifies that ``inspect_run_outcome`` was called and succeeded.
    What this proves is that the typed outcome entered the session's
    context; comprehension is graded by the human reading, as always.
    """

    succeeded: set[str] = set()
    started: dict[str, str] = {}
    try:
        lines = (
            Path(session_events_path).read_text(encoding="utf-8").splitlines()
        )
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
        payload = event.get("payload") or {}
        if event.get("kind") == "tool_started":
            started[str(payload.get("request_id") or "")] = str(
                payload.get("tool") or ""
            )
        elif event.get("kind") == "tool_succeeded":
            request = str(payload.get("request_id") or "")
            if started.get(request) == "inspect_run_outcome":
                succeeded.add(request)
    return bool(succeeded)


@dataclass(frozen=True)
class RevisionAdmissionV1:
    """One deterministic admission verdict, with every check named."""

    admitted: bool
    checks: Mapping[str, bool]
    reasons: tuple[str, ...] = ()
    cited_evidence_event_hashes: tuple[str, ...] = ()


def admit_revision(
    *,
    goal: GoalRecordV1,
    budgets: GoalBudgetsV1,
    revision_review: Mapping[str, Any],
    revision_scientific_identity_sha256: str,
    session_events_path: str | Path,
    prior_outcome_evidence_hashes: tuple[str, ...],
) -> RevisionAdmissionV1:
    """Admit or return one revision, deterministically.

    Every check is a comparison the human's one decision already
    covered. A failed check returns the revision to the human with the
    named reason -- it never silently narrows, never retries, and never
    grades the science: whether the revised route is *wise* is what
    execution, validation, and the reading scientist are for.
    """

    checks: dict[str, bool] = {}
    reasons: list[str] = []

    checks["identity_preserved"] = (
        revision_scientific_identity_sha256 == goal.scientific_identity_sha256
    )
    if not checks["identity_preserved"]:
        reasons.append(
            "the revision binds different molecular identities or "
            "electronic states than the goal approved"
        )

    revision_conditions = canonical_data(
        conditions_from_review(revision_review)
    )
    checks["conditions_preserved"] = revision_conditions == canonical_data(
        goal.conditions
    )
    if not checks["conditions_preserved"]:
        reasons.append(
            "the revision changes physical conditions (solvent or "
            "thermochemical state) the goal approved"
        )

    goal_envelope = dict(goal.envelope)
    review_envelope = dict(revision_review.get("execution_envelope") or {})
    goal_pairs = {
        str(program): tuple(engines)
        for program, engines in (
            goal_envelope.get("allowed_program_engines") or ()
        )
    }
    review_pairs = {
        str(program): tuple(engines)
        for program, engines in (
            review_envelope.get("allowed_program_engines") or ()
        )
    }
    checks["programs_within_envelope"] = all(
        program in goal_pairs and set(engines) <= set(goal_pairs[program])
        for program, engines in review_pairs.items()
    )
    if not checks["programs_within_envelope"]:
        reasons.append(
            "the revision names a program or engine outside the goal's "
            "envelope"
        )

    executable = tuple(
        item
        for item in (revision_review.get("node_reviews") or ())
        if isinstance(item, Mapping)
    )
    checks["engine_budget_remains"] = (
        len(executable) <= budgets.engine_calls_remaining
    )
    if not checks["engine_budget_remains"]:
        reasons.append(
            f"the revision plans {len(executable)} engine calls with "
            f"{budgets.engine_calls_remaining} remaining in the grant"
        )

    checks["revision_budget_remains"] = budgets.revisions_remaining > 0
    if not checks["revision_budget_remains"]:
        reasons.append("the goal's revision budget is exhausted")

    checks["evidence_read"] = session_read_run_outcome(session_events_path)
    if not checks["evidence_read"]:
        reasons.append(
            "the revising session never read a typed run outcome; a "
            "plan that answers a failure it never read is answering a "
            "guess"
        )

    admitted = all(checks.values())
    return RevisionAdmissionV1(
        admitted=admitted,
        checks=checks,
        reasons=tuple(reasons),
        cited_evidence_event_hashes=(
            tuple(prior_outcome_evidence_hashes) if admitted else ()
        ),
    )


__all__ = [
    "GOAL_SCHEMA_VERSION",
    "GOAL_SETTLEMENTS",
    "GoalBudgetsV1",
    "GoalLedger",
    "GoalRecordV1",
    "RevisionAdmissionV1",
    "admit_revision",
    "conditions_from_review",
    "extract_plan_conditions",
    "session_read_run_outcome",
]
