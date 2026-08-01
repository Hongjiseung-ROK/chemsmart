"""Deterministic outcome grading for agent-harness experiments.

The tool loop's ``terminal_outcome`` describes control flow only.  In
particular, ``completed`` means that the provider turn ended; it does not mean
that a scientific tool produced a usable result.  This module therefore keeps
turn termination, the observed tool-domain result, and scientific readiness as
three independent fields.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ToolDomainOutcome(str, Enum):
    """Canonical outcome observed at the experiment tool boundary."""

    NO_TOOL_CALL = "no_tool_call"
    TOOL_ERROR = "tool_error"
    NEEDS_CLARIFICATION = "needs_clarification"
    BLOCKED = "blocked"
    INFEASIBLE = "infeasible"
    PLANNED = "planned"
    PREVIEWED = "previewed"
    EXTRACTED = "extracted"
    TOOL_OK = "tool_ok"


class ScientificReadiness(str, Enum):
    """Highest scientific state established by the observed tool result."""

    NOT_ESTABLISHED = "not_established"
    BLOCKED = "blocked"
    PLANNED = "planned"
    PREVIEWED = "previewed"


class ExpectedBehavior(str, Enum):
    """Whether an explicitly declared case oracle matched the observation."""

    NOT_DECLARED = "not_declared"
    MATCHED = "matched"
    MISMATCHED = "mismatched"


@dataclass(frozen=True)
class ExperimentOutcomeClassification:
    """A deterministic, JSON-ready separation of experiment outcome layers."""

    agent_turn_outcome: str
    tool_domain_outcome: ToolDomainOutcome
    scientific_readiness: ScientificReadiness
    observed_tool_domain_outcomes: tuple[ToolDomainOutcome, ...]
    expected_domain_outcomes: tuple[ToolDomainOutcome, ...]
    expected_behavior: ExpectedBehavior
    case_pass: bool
    tool_request_count: int
    tool_outcome_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_turn_outcome": self.agent_turn_outcome,
            "tool_domain_outcome": self.tool_domain_outcome.value,
            "scientific_readiness": self.scientific_readiness.value,
            "observed_tool_domain_outcomes": [
                item.value for item in self.observed_tool_domain_outcomes
            ],
            "expected_domain_outcomes": [
                item.value for item in self.expected_domain_outcomes
            ],
            "expected_behavior": self.expected_behavior.value,
            "case_pass": self.case_pass,
            "tool_request_count": self.tool_request_count,
            "tool_outcome_count": self.tool_outcome_count,
        }


_DOMAIN_ALIASES: dict[str, ToolDomainOutcome] = {
    "blocked": ToolDomainOutcome.BLOCKED,
    "blocked_missing_evidence": ToolDomainOutcome.BLOCKED,
    "extracted": ToolDomainOutcome.EXTRACTED,
    "infeasible": ToolDomainOutcome.INFEASIBLE,
    "needs_clarification": ToolDomainOutcome.NEEDS_CLARIFICATION,
    "needs_user": ToolDomainOutcome.NEEDS_CLARIFICATION,
    "planned": ToolDomainOutcome.PLANNED,
    "previewed": ToolDomainOutcome.PREVIEWED,
    # A legacy ``ready`` command has not passed safe preview, so the strongest
    # state it may establish here is planned.
    "ready": ToolDomainOutcome.PLANNED,
    "tool_ok": ToolDomainOutcome.TOOL_OK,
    "waiting_for_approval": ToolDomainOutcome.BLOCKED,
}
_OUTER_ERROR_STATUSES = frozenset(
    {"denied", "error", "interrupted", "skipped"}
)
_WRAPPER_KEYS = frozenset(
    {
        "display_result",
        "error_message",
        "error_type",
        "name",
        "raw_result",
        "request_id",
        "result",
    }
)

# A session-level aggregate is deliberately conservative.  A caller evaluating
# a bounded repair in isolation may pass only the final normalized outcome.
_AGGREGATE_PRIORITY = {
    ToolDomainOutcome.TOOL_ERROR: 80,
    ToolDomainOutcome.INFEASIBLE: 70,
    ToolDomainOutcome.BLOCKED: 60,
    ToolDomainOutcome.NEEDS_CLARIFICATION: 50,
    ToolDomainOutcome.PREVIEWED: 40,
    ToolDomainOutcome.PLANNED: 30,
    ToolDomainOutcome.EXTRACTED: 20,
    ToolDomainOutcome.TOOL_OK: 10,
    ToolDomainOutcome.NO_TOOL_CALL: 0,
}


def classify_experiment_outcome(
    session_result: Mapping[str, Any] | None = None,
    *,
    tool_outcomes: Sequence[Any] | None = None,
    expected_domain_outcomes: Iterable[ToolDomainOutcome | str] = (),
) -> ExperimentOutcomeClassification:
    """Classify a session result or an explicit normalized outcome sequence.

    ``terminal_outcome`` is copied into ``agent_turn_outcome`` but is never an
    input to ``tool_domain_outcome``, ``scientific_readiness``, or
    ``case_pass``.  A case can pass only when the caller supplied at least one
    expected tool-domain outcome and the deterministic observation matches it.

    When a complete session contains multiple tool outcomes, the aggregate is
    conservative: any unresolved error/blocking observation outranks a later
    positive observation.  To grade a specifically adjudicated repair result,
    pass that final normalized outcome alone through ``tool_outcomes``.
    """

    if session_result is not None and tool_outcomes is not None:
        raise ValueError(
            "provide either session_result or tool_outcomes, not both"
        )

    if session_result is None:
        agent_turn_outcome = "unknown"
        selected_outcomes: Sequence[Any] = tool_outcomes or ()
        tool_request_count = len(selected_outcomes)
    else:
        agent_turn_outcome = _agent_turn_outcome(session_result)
        selected_outcomes = _sequence_field(
            session_result.get("tool_outcomes")
        )
        requests = _sequence_field(session_result.get("tool_requests"))
        tool_request_count = len(requests)

    observed = tuple(_normalize_tool_outcome(item) for item in selected_outcomes)
    if not observed:
        aggregate = (
            ToolDomainOutcome.TOOL_ERROR
            if tool_request_count
            else ToolDomainOutcome.NO_TOOL_CALL
        )
    else:
        aggregate = max(observed, key=_AGGREGATE_PRIORITY.__getitem__)

    expected = _normalize_expected(expected_domain_outcomes)
    if not expected:
        expected_behavior = ExpectedBehavior.NOT_DECLARED
    elif aggregate in expected:
        expected_behavior = ExpectedBehavior.MATCHED
    else:
        expected_behavior = ExpectedBehavior.MISMATCHED

    return ExperimentOutcomeClassification(
        agent_turn_outcome=agent_turn_outcome,
        tool_domain_outcome=aggregate,
        scientific_readiness=_scientific_readiness(aggregate),
        observed_tool_domain_outcomes=observed,
        expected_domain_outcomes=expected,
        expected_behavior=expected_behavior,
        case_pass=expected_behavior is ExpectedBehavior.MATCHED,
        tool_request_count=tool_request_count,
        tool_outcome_count=len(observed),
    )


def _agent_turn_outcome(result: Mapping[str, Any]) -> str:
    value = result.get("agent_turn_outcome", result.get("terminal_outcome"))
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "unknown"


def _normalize_tool_outcome(item: Any) -> ToolDomainOutcome:
    if isinstance(item, Mapping):
        return _normalize_mapping(item)

    outer_status = _status_text(getattr(item, "status", None))
    if outer_status == "ask_user":
        return ToolDomainOutcome.NEEDS_CLARIFICATION
    if outer_status in _OUTER_ERROR_STATUSES or outer_status not in {"", "ok"}:
        return ToolDomainOutcome.TOOL_ERROR
    payload = getattr(item, "raw_result", None)
    if payload is None:
        payload = getattr(item, "result", None)
    return _normalize_domain_payload(payload)


def _normalize_mapping(item: Mapping[str, Any]) -> ToolDomainOutcome:
    is_wrapper = bool(_WRAPPER_KEYS.intersection(item))
    if not is_wrapper:
        return _normalize_domain_payload(item)

    outer_status = _status_text(item.get("status"))
    if outer_status == "ask_user":
        return ToolDomainOutcome.NEEDS_CLARIFICATION
    if outer_status in _OUTER_ERROR_STATUSES or outer_status not in {"", "ok"}:
        return ToolDomainOutcome.TOOL_ERROR
    payload = item.get("raw_result")
    if payload is None:
        payload = item.get("result")
    return _normalize_domain_payload(payload)


def _normalize_domain_payload(payload: Any) -> ToolDomainOutcome:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="python")
    if not isinstance(payload, Mapping):
        return ToolDomainOutcome.TOOL_OK

    status = _status_text(payload.get("status"))
    if status in _DOMAIN_ALIASES:
        return _DOMAIN_ALIASES[status]
    if status in _OUTER_ERROR_STATUSES:
        return ToolDomainOutcome.TOOL_ERROR
    if payload.get("ok") is False:
        return ToolDomainOutcome.TOOL_ERROR
    return ToolDomainOutcome.TOOL_OK


def _normalize_expected(
    values: Iterable[ToolDomainOutcome | str],
) -> tuple[ToolDomainOutcome, ...]:
    normalized: set[ToolDomainOutcome] = set()
    for value in values:
        if isinstance(value, ToolDomainOutcome):
            normalized.add(value)
            continue
        try:
            normalized.add(ToolDomainOutcome(str(value).strip()))
        except ValueError as exc:
            raise ValueError(f"unknown expected domain outcome: {value!r}") from exc
    return tuple(sorted(normalized, key=lambda item: item.value))


def _scientific_readiness(
    outcome: ToolDomainOutcome,
) -> ScientificReadiness:
    if outcome is ToolDomainOutcome.PREVIEWED:
        return ScientificReadiness.PREVIEWED
    if outcome is ToolDomainOutcome.PLANNED:
        return ScientificReadiness.PLANNED
    if outcome in {
        ToolDomainOutcome.BLOCKED,
        ToolDomainOutcome.INFEASIBLE,
        ToolDomainOutcome.NEEDS_CLARIFICATION,
    }:
        return ScientificReadiness.BLOCKED
    # Extraction and a generic successful tool call are observations, not
    # evidence that a calculation is ready, executed, or validated.
    return ScientificReadiness.NOT_ESTABLISHED


def _sequence_field(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return value
    return ()


def _status_text(value: Any) -> str:
    if isinstance(value, Enum):
        value = value.value
    return value.strip().lower() if isinstance(value, str) else ""


__all__ = [
    "ExpectedBehavior",
    "ExperimentOutcomeClassification",
    "ScientificReadiness",
    "ToolDomainOutcome",
    "classify_experiment_outcome",
]
