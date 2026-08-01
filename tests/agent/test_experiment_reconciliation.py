from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from chemsmart.agent.experiment_outcomes import (
    ScientificReadiness,
    ToolDomainOutcome,
)
from chemsmart.agent.experiment_reconciliation import (
    AuthoritativeTurnOutcome,
    ExperimentReconciliationError,
    ReconciliationRule,
    reconcile_experiment_outcome,
)


def _event(
    sequence: int,
    kind: str,
    *,
    previous_hash: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = {
        "schema_version": 1,
        "sequence": sequence,
        "event_id": f"event-{sequence}",
        "session_id": "session-1",
        "turn_id": "turn_0001",
        "kind": kind,
        "timestamp": f"2026-08-01T00:00:0{sequence}+00:00",
        "payload": payload or {},
        "idempotency_key": "",
        "previous_hash": previous_hash,
    }
    event_hash = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {**body, "event_hash": event_hash}


def _stream(
    terminal: str,
    *,
    reason: str = "",
    rule_ids: list[str] | None = None,
) -> bytes:
    first = _event(1, "session_started", previous_hash="")
    terminal_event = _event(
        2,
        terminal,
        previous_hash=first["event_hash"],
        payload={"reason": reason, "rule_ids": rule_ids or []},
    )
    return (
        "\n".join(
            json.dumps(item, sort_keys=True)
            for item in (first, terminal_event)
        )
        + "\n"
    ).encode()


def _tool_outcome(
    domain_status: str | None = None,
    *,
    outer_status: str = "ok",
) -> dict[str, Any]:
    result = None
    if outer_status == "ok":
        result = {"ok": True}
        if domain_status is not None:
            result["status"] = domain_status
    return {
        "name": "paper_tool",
        "status": outer_status,
        "result": result,
    }


@pytest.mark.parametrize(
    (
        "case_id",
        "public_terminal",
        "reason",
        "tool_outcome",
        "expected_tool",
        "expected_readiness",
    ),
    [
        (
            "artifact_swap_negative",
            "completed",
            "runtime.command.preview_not_green",
            _tool_outcome("needs_clarification"),
            ToolDomainOutcome.NEEDS_CLARIFICATION,
            ScientificReadiness.BLOCKED,
        ),
        (
            "engineering_assumption_preview",
            "completed",
            "runtime.project.render_required",
            _tool_outcome("previewed"),
            ToolDomainOutcome.PREVIEWED,
            ScientificReadiness.PREVIEWED,
        ),
        (
            "missing_state_negative",
            "completed",
            "runtime.command.preview_required",
            _tool_outcome("blocked_missing_evidence"),
            ToolDomainOutcome.BLOCKED,
            ScientificReadiness.BLOCKED,
        ),
        (
            "missing_state_negative_repeat",
            "completed",
            "runtime.command.preview_required",
            _tool_outcome(outer_status="error"),
            ToolDomainOutcome.TOOL_ERROR,
            ScientificReadiness.NOT_ESTABLISHED,
        ),
    ],
)
def test_known_public_runtime_mismatches_are_preserved_as_receipts(
    case_id: str,
    public_terminal: str,
    reason: str,
    tool_outcome: dict[str, Any],
    expected_tool: ToolDomainOutcome,
    expected_readiness: ScientificReadiness,
) -> None:
    public_source = {
        "schema_version": "chemsmart.deepseek-paper-pilot.v1",
        "cases": [
            {
                "case_id": case_id,
                "terminal_outcome": public_terminal,
                "tool_requests": [{"name": "paper_tool"}],
                "tool_outcomes": [tool_outcome],
            }
        ],
    }

    receipt = reconcile_experiment_outcome(
        runtime_events_jsonl=_stream(
            "turn_blocked",
            reason=reason,
            rule_ids=[reason],
        ),
        public_source=public_source,
        case_id=case_id,
    )

    assert receipt.terminal.outcome is AuthoritativeTurnOutcome.BLOCKED
    assert receipt.terminal.reason == reason
    assert receipt.public_turn_outcome == public_terminal
    assert receipt.outcome_classification.tool_domain_outcome is expected_tool
    assert (
        receipt.outcome_classification.scientific_readiness
        is expected_readiness
    )
    assert receipt.reconciled is False
    assert [item.rule_id for item in receipt.mismatches] == [
        ReconciliationRule.PUBLIC_TERMINAL_MISMATCH
    ]
    assert receipt.verify_hash() is True


def test_turn_completed_does_not_promote_tool_or_scientific_outcome() -> None:
    receipt = reconcile_experiment_outcome(
        runtime_events_jsonl=_stream("turn_completed"),
        public_source={
            "case_id": "no-tool",
            "terminal_outcome": "completed",
            "tool_requests": [],
            "tool_outcomes": [],
        },
    )

    assert receipt.reconciled is True
    assert receipt.terminal.outcome is AuthoritativeTurnOutcome.COMPLETED
    assert (
        receipt.outcome_classification.tool_domain_outcome
        is ToolDomainOutcome.NO_TOOL_CALL
    )
    assert (
        receipt.outcome_classification.scientific_readiness
        is ScientificReadiness.NOT_ESTABLISHED
    )


def test_historical_turn_failed_is_supported_and_hash_is_deterministic() -> None:
    runtime_events = _stream("turn_failed", reason="provider_error")
    public_source = {
        "case_id": "provider-failure",
        "terminal_outcome": "failed",
        "tool_requests": [],
        "tool_outcomes": [],
    }

    first = reconcile_experiment_outcome(
        runtime_events_jsonl=runtime_events,
        public_source=public_source,
    )
    second = reconcile_experiment_outcome(
        runtime_events_jsonl=runtime_events,
        public_source=dict(reversed(list(public_source.items()))),
    )

    assert first.terminal.outcome is AuthoritativeTurnOutcome.FAILED
    assert first.reconciled is True
    assert first.receipt_sha256 == second.receipt_sha256
    assert first.to_dict() == second.to_dict()


def test_runtime_hash_tampering_fails_closed_with_stable_rule() -> None:
    lines = _stream("turn_blocked").decode().splitlines()
    terminal = json.loads(lines[-1])
    terminal["payload"]["reason"] = "tampered"
    lines[-1] = json.dumps(terminal)

    with pytest.raises(ExperimentReconciliationError) as exc_info:
        reconcile_experiment_outcome(
            runtime_events_jsonl="\n".join(lines),
            public_source={"terminal_outcome": "blocked"},
        )

    assert exc_info.value.rule_id is ReconciliationRule.EVENT_HASH_MISMATCH


def test_multiple_terminal_events_for_one_turn_fail_closed() -> None:
    first = _event(1, "session_started", previous_hash="")
    blocked = _event(
        2,
        "turn_blocked",
        previous_hash=first["event_hash"],
    )
    failed = _event(
        3,
        "turn_failed",
        previous_hash=blocked["event_hash"],
    )
    stream = "\n".join(json.dumps(item) for item in (first, blocked, failed))

    with pytest.raises(ExperimentReconciliationError) as exc_info:
        reconcile_experiment_outcome(
            runtime_events_jsonl=stream,
            public_source={"terminal_outcome": "failed"},
        )

    assert exc_info.value.rule_id is ReconciliationRule.TERMINAL_MULTIPLE
