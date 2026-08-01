"""Reconcile public experiment outcomes with historical Runtime V2 events.

Runtime V2 is the authority for turn termination.  Public campaign receipts
remain useful observations of the provider and tool boundary, but they cannot
rewrite a hash-chained terminal event.  This module reads historical JSONL
without migrating it and records any disagreement in a content-addressed
receipt.

The three outcome layers stay deliberately independent:

* the Runtime V2 terminal event describes turn control flow;
* the observed tool result describes the tool-domain outcome; and
* deterministic tool evidence establishes (at most) scientific readiness.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from chemsmart.agent.experiment_outcomes import (
    ExperimentOutcomeClassification,
    ToolDomainOutcome,
    classify_experiment_outcome,
)


class AuthoritativeTurnOutcome(str, Enum):
    """Terminal kinds understood across current and historical streams."""

    COMPLETED = "turn_completed"
    BLOCKED = "turn_blocked"
    FAILED = "turn_failed"


class ReconciliationRule(str, Enum):
    """Stable identifiers for fail-closed parsing and reconciliation."""

    INVALID_JSONL = "experiment.reconciliation.invalid_jsonl"
    INVALID_EVENT = "experiment.reconciliation.invalid_event"
    EVENT_HASH_MISMATCH = "experiment.reconciliation.event_hash_mismatch"
    HASH_CHAIN_MISMATCH = "experiment.reconciliation.hash_chain_mismatch"
    SEQUENCE_MISMATCH = "experiment.reconciliation.sequence_mismatch"
    SESSION_MISMATCH = "experiment.reconciliation.session_mismatch"
    TERMINAL_MISSING = "experiment.reconciliation.terminal_missing"
    TERMINAL_MULTIPLE = "experiment.reconciliation.terminal_multiple"
    TERMINAL_NOT_FINAL = "experiment.reconciliation.terminal_not_final"
    PUBLIC_CASE_MISSING = "experiment.reconciliation.public_case_missing"
    PUBLIC_CASE_MULTIPLE = "experiment.reconciliation.public_case_multiple"
    PUBLIC_TERMINAL_MISSING = (
        "experiment.reconciliation.public_terminal_missing"
    )
    PUBLIC_TERMINAL_MISMATCH = (
        "experiment.reconciliation.public_terminal_mismatch"
    )


class ExperimentReconciliationError(ValueError):
    """A fail-closed error carrying a machine-stable rule identifier."""

    def __init__(self, rule_id: ReconciliationRule, message: str) -> None:
        self.rule_id = rule_id
        super().__init__(f"{rule_id.value}: {message}")


@dataclass(frozen=True)
class RuntimeTerminalObservation:
    """Hash-bound observation of the selected terminal Runtime V2 event."""

    session_id: str
    turn_id: str
    sequence: int
    outcome: AuthoritativeTurnOutcome
    reason: str
    rule_ids: tuple[str, ...]
    event_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "sequence": self.sequence,
            "outcome": self.outcome.value,
            "reason": self.reason,
            "rule_ids": list(self.rule_ids),
            "event_hash": self.event_hash,
        }


@dataclass(frozen=True)
class OutcomeMismatch:
    """An evidence-linked disagreement; no source is changed to resolve it."""

    rule_id: ReconciliationRule
    field: str
    expected: str
    observed: str
    runtime_event_hash: str
    public_outcome_sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id.value,
            "field": self.field,
            "expected": self.expected,
            "observed": self.observed,
            "runtime_event_hash": self.runtime_event_hash,
            "public_outcome_sha256": self.public_outcome_sha256,
        }


@dataclass(frozen=True)
class ExperimentReconciliationReceipt:
    """Deterministic reconciliation of one public case and one runtime turn."""

    schema_version: str
    case_id: str
    runtime_events_sha256: str
    public_source_sha256: str
    public_outcome_sha256: str
    terminal: RuntimeTerminalObservation
    public_turn_outcome: str
    outcome_classification: ExperimentOutcomeClassification
    mismatches: tuple[OutcomeMismatch, ...]
    receipt_sha256: str

    @property
    def reconciled(self) -> bool:
        return not self.mismatches

    def to_dict(self, *, include_receipt_sha256: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "runtime_events_sha256": self.runtime_events_sha256,
            "public_source_sha256": self.public_source_sha256,
            "public_outcome_sha256": self.public_outcome_sha256,
            "terminal": self.terminal.to_dict(),
            "public_turn_outcome": self.public_turn_outcome,
            "tool_domain_outcome": (
                self.outcome_classification.tool_domain_outcome.value
            ),
            "scientific_readiness": (
                self.outcome_classification.scientific_readiness.value
            ),
            "outcome_classification": self.outcome_classification.to_dict(),
            "mismatches": [item.to_dict() for item in self.mismatches],
            "reconciled": self.reconciled,
        }
        if include_receipt_sha256:
            body["receipt_sha256"] = self.receipt_sha256
        return body

    def verify_hash(self) -> bool:
        return self.receipt_sha256 == _sha256_json(
            self.to_dict(include_receipt_sha256=False)
        )


_TERMINAL_KINDS = frozenset(item.value for item in AuthoritativeTurnOutcome)
_PUBLIC_TERMINAL_MAP = {
    "completed": AuthoritativeTurnOutcome.COMPLETED.value,
    "blocked": AuthoritativeTurnOutcome.BLOCKED.value,
    "failed": AuthoritativeTurnOutcome.FAILED.value,
    "turn_completed": AuthoritativeTurnOutcome.COMPLETED.value,
    "turn_blocked": AuthoritativeTurnOutcome.BLOCKED.value,
    "turn_failed": AuthoritativeTurnOutcome.FAILED.value,
}


def reconcile_experiment_outcome(
    *,
    runtime_events_jsonl: bytes | str,
    public_source: Mapping[str, Any],
    case_id: str | None = None,
    turn_id: str | None = None,
    expected_domain_outcomes: Iterable[ToolDomainOutcome | str] | None = None,
) -> ExperimentReconciliationReceipt:
    """Reconcile one public outcome against its authoritative runtime turn.

    ``public_source`` may be a single session/case mapping or a campaign
    receipt with a ``cases`` sequence.  In the latter form, ``case_id`` is
    required unless the campaign contains exactly one case.

    Historical bytes are parsed and verified in memory.  The function never
    writes, repairs, normalizes, or migrates either source.
    """

    runtime_bytes = _runtime_bytes(runtime_events_jsonl)
    events = _parse_runtime_events(runtime_bytes)
    terminal = _select_terminal(events, turn_id=turn_id)
    public_outcome = _select_public_outcome(public_source, case_id=case_id)
    selected_case_id = _selected_case_id(public_outcome, case_id=case_id)

    public_source_sha256 = _sha256_json(public_source)
    public_outcome_sha256 = _sha256_json(public_outcome)
    public_turn_outcome = _public_turn_outcome(public_outcome)

    expected = expected_domain_outcomes
    if expected is None:
        expected = _embedded_expected_domain_outcomes(public_outcome)
    classification = classify_experiment_outcome(
        public_outcome,
        expected_domain_outcomes=expected,
    )

    mismatches: list[OutcomeMismatch] = []
    normalized_public_terminal = _PUBLIC_TERMINAL_MAP.get(
        public_turn_outcome.lower()
    )
    if not public_turn_outcome:
        mismatches.append(
            OutcomeMismatch(
                rule_id=ReconciliationRule.PUBLIC_TERMINAL_MISSING,
                field="turn_outcome",
                expected=terminal.outcome.value,
                observed="missing",
                runtime_event_hash=terminal.event_hash,
                public_outcome_sha256=public_outcome_sha256,
            )
        )
    elif normalized_public_terminal != terminal.outcome.value:
        mismatches.append(
            OutcomeMismatch(
                rule_id=ReconciliationRule.PUBLIC_TERMINAL_MISMATCH,
                field="turn_outcome",
                expected=terminal.outcome.value,
                observed=public_turn_outcome,
                runtime_event_hash=terminal.event_hash,
                public_outcome_sha256=public_outcome_sha256,
            )
        )

    ordered_mismatches = tuple(
        sorted(
            mismatches,
            key=lambda item: (
                item.rule_id.value,
                item.field,
                item.expected,
                item.observed,
            ),
        )
    )
    body = {
        "schema_version": "chemsmart.experiment-reconciliation.v1",
        "case_id": selected_case_id,
        "runtime_events_sha256": hashlib.sha256(runtime_bytes).hexdigest(),
        "public_source_sha256": public_source_sha256,
        "public_outcome_sha256": public_outcome_sha256,
        "terminal": terminal.to_dict(),
        "public_turn_outcome": public_turn_outcome,
        "tool_domain_outcome": classification.tool_domain_outcome.value,
        "scientific_readiness": classification.scientific_readiness.value,
        "outcome_classification": classification.to_dict(),
        "mismatches": [item.to_dict() for item in ordered_mismatches],
        "reconciled": not ordered_mismatches,
    }
    return ExperimentReconciliationReceipt(
        schema_version=body["schema_version"],
        case_id=selected_case_id,
        runtime_events_sha256=body["runtime_events_sha256"],
        public_source_sha256=public_source_sha256,
        public_outcome_sha256=public_outcome_sha256,
        terminal=terminal,
        public_turn_outcome=public_turn_outcome,
        outcome_classification=classification,
        mismatches=ordered_mismatches,
        receipt_sha256=_sha256_json(body),
    )


def reconcile_experiment_files(
    *,
    runtime_events_path: str | Path,
    public_source_path: str | Path,
    case_id: str | None = None,
    turn_id: str | None = None,
    expected_domain_outcomes: Iterable[ToolDomainOutcome | str] | None = None,
) -> ExperimentReconciliationReceipt:
    """Read two evidence files without mutation and reconcile one case."""

    runtime_bytes = Path(runtime_events_path).read_bytes()
    public_bytes = Path(public_source_path).read_bytes()
    try:
        public_source = json.loads(public_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExperimentReconciliationError(
            ReconciliationRule.INVALID_JSONL,
            f"invalid public JSON: {exc}",
        ) from exc
    if not isinstance(public_source, Mapping):
        raise ExperimentReconciliationError(
            ReconciliationRule.INVALID_EVENT,
            "public source must be a JSON object",
        )
    return reconcile_experiment_outcome(
        runtime_events_jsonl=runtime_bytes,
        public_source=public_source,
        case_id=case_id,
        turn_id=turn_id,
        expected_domain_outcomes=expected_domain_outcomes,
    )


def _parse_runtime_events(runtime_bytes: bytes) -> tuple[dict[str, Any], ...]:
    events: list[dict[str, Any]] = []
    previous_hash = ""
    session_id: str | None = None

    try:
        text = runtime_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExperimentReconciliationError(
            ReconciliationRule.INVALID_JSONL,
            "runtime event stream is not UTF-8",
        ) from exc

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ExperimentReconciliationError(
                ReconciliationRule.INVALID_JSONL,
                f"invalid runtime JSON at line {line_number}: {exc.msg}",
            ) from exc
        if not isinstance(parsed, dict):
            raise ExperimentReconciliationError(
                ReconciliationRule.INVALID_EVENT,
                f"runtime event at line {line_number} is not an object",
            )
        _validate_event_shape(parsed, line_number=line_number)

        sequence = parsed["sequence"]
        expected_sequence = len(events) + 1
        if sequence != expected_sequence:
            raise ExperimentReconciliationError(
                ReconciliationRule.SEQUENCE_MISMATCH,
                f"line {line_number} has sequence {sequence}; "
                f"expected {expected_sequence}",
            )
        if parsed["previous_hash"] != previous_hash:
            raise ExperimentReconciliationError(
                ReconciliationRule.HASH_CHAIN_MISMATCH,
                f"line {line_number} does not link to the prior event",
            )
        observed_session_id = parsed["session_id"]
        if session_id is None:
            session_id = observed_session_id
        elif observed_session_id != session_id:
            raise ExperimentReconciliationError(
                ReconciliationRule.SESSION_MISMATCH,
                f"line {line_number} changes session_id",
            )

        event_hash = parsed["event_hash"]
        hash_body = dict(parsed)
        hash_body.pop("event_hash")
        if event_hash != _sha256_json(hash_body):
            raise ExperimentReconciliationError(
                ReconciliationRule.EVENT_HASH_MISMATCH,
                f"runtime event hash mismatch at line {line_number}",
            )
        previous_hash = event_hash
        events.append(parsed)

    if not events:
        raise ExperimentReconciliationError(
            ReconciliationRule.TERMINAL_MISSING,
            "runtime event stream is empty",
        )
    return tuple(events)


def _validate_event_shape(event: Mapping[str, Any], *, line_number: int) -> None:
    required = {
        "sequence": int,
        "session_id": str,
        "turn_id": str,
        "kind": str,
        "payload": dict,
        "previous_hash": str,
        "event_hash": str,
    }
    for field, expected_type in required.items():
        value = event.get(field)
        if not isinstance(value, expected_type) or (
            expected_type is str and field != "previous_hash" and not value
        ):
            raise ExperimentReconciliationError(
                ReconciliationRule.INVALID_EVENT,
                f"line {line_number} has invalid {field}",
            )


def _select_terminal(
    events: Sequence[Mapping[str, Any]],
    *,
    turn_id: str | None,
) -> RuntimeTerminalObservation:
    terminals = [event for event in events if event["kind"] in _TERMINAL_KINDS]
    if turn_id is None and terminals:
        turn_id = str(terminals[-1]["turn_id"])
    selected = [event for event in terminals if event["turn_id"] == turn_id]
    if not selected:
        target = turn_id or "<any>"
        raise ExperimentReconciliationError(
            ReconciliationRule.TERMINAL_MISSING,
            f"no terminal event for turn {target}",
        )
    if len(selected) != 1:
        raise ExperimentReconciliationError(
            ReconciliationRule.TERMINAL_MULTIPLE,
            f"turn {turn_id} has {len(selected)} terminal events",
        )
    terminal = selected[0]
    if any(
        event["turn_id"] == turn_id
        and event["sequence"] > terminal["sequence"]
        for event in events
    ):
        raise ExperimentReconciliationError(
            ReconciliationRule.TERMINAL_NOT_FINAL,
            f"turn {turn_id} has events after its terminal event",
        )

    payload = terminal["payload"]
    raw_rule_ids = payload.get("rule_ids", ())
    if not isinstance(raw_rule_ids, Sequence) or isinstance(
        raw_rule_ids, (str, bytes, bytearray)
    ):
        raw_rule_ids = ()
    return RuntimeTerminalObservation(
        session_id=str(terminal["session_id"]),
        turn_id=str(terminal["turn_id"]),
        sequence=int(terminal["sequence"]),
        outcome=AuthoritativeTurnOutcome(str(terminal["kind"])),
        reason=_text(payload.get("reason")),
        rule_ids=tuple(sorted({_text(item) for item in raw_rule_ids if _text(item)})),
        event_hash=str(terminal["event_hash"]),
    )


def _select_public_outcome(
    public_source: Mapping[str, Any],
    *,
    case_id: str | None,
) -> Mapping[str, Any]:
    cases = public_source.get("cases")
    if not isinstance(cases, Sequence) or isinstance(
        cases, (str, bytes, bytearray)
    ):
        return public_source

    mappings = [item for item in cases if isinstance(item, Mapping)]
    if case_id is None:
        if len(mappings) == 1:
            return mappings[0]
        raise ExperimentReconciliationError(
            ReconciliationRule.PUBLIC_CASE_MISSING,
            "case_id is required for a multi-case public source",
        )
    matches = [item for item in mappings if item.get("case_id") == case_id]
    if not matches:
        raise ExperimentReconciliationError(
            ReconciliationRule.PUBLIC_CASE_MISSING,
            f"public source has no case_id {case_id!r}",
        )
    if len(matches) != 1:
        raise ExperimentReconciliationError(
            ReconciliationRule.PUBLIC_CASE_MULTIPLE,
            f"public source repeats case_id {case_id!r}",
        )
    return matches[0]


def _selected_case_id(
    public_outcome: Mapping[str, Any],
    *,
    case_id: str | None,
) -> str:
    selected = _text(public_outcome.get("case_id")) or _text(case_id)
    return selected or "session"


def _public_turn_outcome(public_outcome: Mapping[str, Any]) -> str:
    value = public_outcome.get(
        "terminal_outcome",
        public_outcome.get("agent_turn_outcome"),
    )
    if isinstance(value, Enum):
        value = value.value
    return _text(value)


def _embedded_expected_domain_outcomes(
    public_outcome: Mapping[str, Any],
) -> tuple[str, ...]:
    classification = public_outcome.get("outcome_classification")
    if not isinstance(classification, Mapping):
        return ()
    values = classification.get("expected_domain_outcomes")
    if not isinstance(values, Sequence) or isinstance(
        values, (str, bytes, bytearray)
    ):
        return ()
    return tuple(_text(item) for item in values if _text(item))


def _runtime_bytes(value: bytes | str) -> bytes:
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8")


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


__all__ = [
    "AuthoritativeTurnOutcome",
    "ExperimentReconciliationError",
    "ExperimentReconciliationReceipt",
    "OutcomeMismatch",
    "ReconciliationRule",
    "RuntimeTerminalObservation",
    "reconcile_experiment_files",
    "reconcile_experiment_outcome",
]
