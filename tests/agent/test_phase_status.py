from __future__ import annotations

import pytest
from pydantic import ValidationError

from chemsmart.agent.phase_status import (
    FrontierPhase,
    PhaseRecord,
    PhaseState,
    PhaseStatusLedger,
    phase_status_ledger_id,
)


def _ledger_body(records: tuple[PhaseRecord, ...]) -> dict[str, object]:
    return {
        "schema_version": "chemsmart.phase-status-ledger.v1",
        "branch": "codex/frontier-agent-live-pilot",
        "baseline_sha": "8" * 40,
        "records": records,
        "historical_foundation_receipts_are_current": False,
    }


def _pending_records() -> tuple[PhaseRecord, ...]:
    return tuple(
        PhaseRecord(phase=phase, state=PhaseState.NOT_STARTED)
        for phase in FrontierPhase
    )


def test_phase_ledger_is_content_addressed_and_ordered() -> None:
    body = _ledger_body(_pending_records())
    ledger = PhaseStatusLedger.model_validate(
        {**body, "ledger_id": phase_status_ledger_id(body)}
    )

    assert ledger.records[0].phase is FrontierPhase.R0
    assert ledger.records[-1].phase is FrontierPhase.R6


def test_later_phase_cannot_validate_before_predecessors() -> None:
    records = list(_pending_records())
    records[1] = PhaseRecord(
        phase=FrontierPhase.R1,
        state=PhaseState.VALIDATED,
        source_snapshot_sha256="a" * 64,
        receipt_ids=("receipt:r1",),
        check_ids=("check:r1",),
    )
    body = _ledger_body(tuple(records))

    with pytest.raises(ValidationError, match="all earlier phases"):
        PhaseStatusLedger.model_validate(
            {**body, "ledger_id": phase_status_ledger_id(body)}
        )


def test_blocked_phase_requires_explicit_rule() -> None:
    with pytest.raises(ValidationError, match="requires rule IDs"):
        PhaseRecord(phase=FrontierPhase.R6, state=PhaseState.BLOCKED)
