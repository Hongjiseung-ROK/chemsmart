"""Content-addressed R0--R6 milestone status for frontier-agent development."""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PHASE_STATUS_LEDGER_SCHEMA_VERSION = "chemsmart.phase-status-ledger.v1"
_SHA256 = r"^[0-9a-f]{64}$"
_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class FrontierPhase(str, Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"
    R5 = "R5"
    R6 = "R6"


class PhaseState(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    EVIDENCE_PENDING = "evidence_pending"
    VALIDATED = "validated"
    BLOCKED = "blocked"
    FAILED = "failed"


class PhaseRecord(_Contract):
    phase: FrontierPhase
    state: PhaseState
    source_snapshot_sha256: str | None = Field(default=None, pattern=_SHA256)
    receipt_ids: tuple[str, ...] = ()
    check_ids: tuple[str, ...] = ()
    blocker_rule_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _state_has_required_evidence(self) -> "PhaseRecord":
        for field_name in ("receipt_ids", "check_ids", "blocker_rule_ids"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)) or tuple(sorted(values)) != values:
                raise ValueError(f"{field_name} must be unique and sorted")
            if any(not _is_identifier(value) for value in values):
                raise ValueError(f"{field_name} contains an unsafe identifier")
        if self.state is PhaseState.VALIDATED:
            if self.source_snapshot_sha256 is None:
                raise ValueError("validated phase requires source snapshot")
            if not self.receipt_ids or not self.check_ids:
                raise ValueError("validated phase requires receipts and checks")
            if self.blocker_rule_ids:
                raise ValueError("validated phase cannot retain blockers")
        if self.state in {PhaseState.BLOCKED, PhaseState.FAILED}:
            if not self.blocker_rule_ids:
                raise ValueError("blocked or failed phase requires rule IDs")
        if self.state is PhaseState.NOT_STARTED and any(
            (
                self.source_snapshot_sha256,
                self.receipt_ids,
                self.check_ids,
                self.blocker_rule_ids,
            )
        ):
            raise ValueError("not-started phase cannot claim observations")
        return self


class PhaseStatusLedger(_Contract):
    """The only machine-readable authority for selecting the next phase."""

    schema_version: Literal[PHASE_STATUS_LEDGER_SCHEMA_VERSION] = (
        PHASE_STATUS_LEDGER_SCHEMA_VERSION
    )
    ledger_id: str = Field(pattern=_SHA256)
    branch: str = Field(min_length=1, max_length=240)
    baseline_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    records: tuple[PhaseRecord, ...] = Field(min_length=7, max_length=7)
    historical_foundation_receipts_are_current: Literal[False] = False

    @model_validator(mode="after")
    def _phase_order_and_dependencies_are_closed(self) -> "PhaseStatusLedger":
        if tuple(item.phase for item in self.records) != tuple(FrontierPhase):
            raise ValueError("phase ledger must contain R0 through R6 in order")
        for index, record in enumerate(self.records):
            if record.state is not PhaseState.VALIDATED:
                continue
            previous = self.records[:index]
            if any(item.state is not PhaseState.VALIDATED for item in previous):
                raise ValueError("validated phase requires all earlier phases")
        r6 = self.records[-1]
        if r6.state is PhaseState.VALIDATED and not any(
            receipt.startswith("prp6:sealed-corpus:")
            for receipt in r6.receipt_ids
        ):
            raise ValueError("validated R6 requires sealed-corpus evidence")
        if self.ledger_id != phase_status_ledger_id(self):
            raise ValueError("ledger ID must content-address the phase ledger")
        return self


def phase_status_ledger_id(
    ledger: PhaseStatusLedger | dict[str, object],
) -> str:
    if isinstance(ledger, PhaseStatusLedger):
        payload = ledger.model_dump(mode="json", exclude={"ledger_id"})
    else:
        payload = {
            key: _jsonable(value)
            for key, value in ledger.items()
            if key != "ledger_id"
        }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _is_identifier(value: str) -> bool:
    import re

    return re.fullmatch(_IDENTIFIER, value) is not None


__all__ = [
    "PHASE_STATUS_LEDGER_SCHEMA_VERSION",
    "FrontierPhase",
    "PhaseRecord",
    "PhaseState",
    "PhaseStatusLedger",
    "phase_status_ledger_id",
]
