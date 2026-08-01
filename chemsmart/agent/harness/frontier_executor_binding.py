"""Fixture-only prospective one-shot executor approval binding.

This module is deliberately not imported by the active agent, CLI, tool loop,
or execution path.  It specifies and tests a future enforcement boundary using
only hashes and a caller-owned in-memory ledger; it never dispatches a command
or grants real execution authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

from chemsmart.agent.runtime.scientific_contracts import ApprovalRequest


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BINDING_VERSION = "frontier.fixture-executor-binding.v1"


@dataclass(frozen=True)
class FixtureExecutorBinding:
    """A future-only approval envelope extended with a CLI schema digest."""

    approval_id: str
    approval_request_binding_sha256: str
    command_sha256: str
    preflight_receipt_sha256s: tuple[str, ...]
    cli_schema_sha256: str
    execution_target: str
    expires_at: str
    schema_version: str = _BINDING_VERSION

    def __post_init__(self) -> None:
        if not self.approval_id or not self.execution_target:
            raise ValueError("fixture executor binding requires identifiers")
        for value in (
            self.approval_request_binding_sha256,
            self.command_sha256,
            self.cli_schema_sha256,
        ):
            _require_sha256(value)
        if not self.preflight_receipt_sha256s:
            raise ValueError("fixture executor binding requires preflight hashes")
        if tuple(sorted(set(self.preflight_receipt_sha256s))) != self.preflight_receipt_sha256s:
            raise ValueError("fixture executor binding preflight hashes must be sorted")
        for value in self.preflight_receipt_sha256s:
            _require_sha256(value)
        _parse_timestamp(self.expires_at)

    @property
    def binding_sha256(self) -> str:
        return _sha256_json(asdict(self))


@dataclass(frozen=True)
class FixtureExecutorResolution:
    """A fixture-only explicit decision over one exact executor binding."""

    approval_id: str
    executor_binding_sha256: str
    decision: Literal["approved", "denied"]
    resolved_at: str

    def __post_init__(self) -> None:
        if not self.approval_id:
            raise ValueError("fixture executor resolution requires an approval id")
        _require_sha256(self.executor_binding_sha256)
        _parse_timestamp(self.resolved_at)


@dataclass(frozen=True)
class FixtureExecutorInvocation:
    """Observed hashes for a proposed fixture-only dispatch."""

    command_sha256: str
    preflight_receipt_sha256s: tuple[str, ...]
    cli_schema_sha256: str
    execution_target: str
    observed_at: str
    execution_mode: Literal["fixture_only"] = "fixture_only"

    def __post_init__(self) -> None:
        for value in (self.command_sha256, self.cli_schema_sha256):
            _require_sha256(value)
        if not self.execution_target:
            raise ValueError("fixture executor invocation requires a target")
        if not self.preflight_receipt_sha256s:
            raise ValueError("fixture executor invocation requires preflight hashes")
        if tuple(sorted(set(self.preflight_receipt_sha256s))) != self.preflight_receipt_sha256s:
            raise ValueError("fixture executor invocation preflight hashes must be sorted")
        for value in self.preflight_receipt_sha256s:
            _require_sha256(value)
        _parse_timestamp(self.observed_at)


@dataclass(frozen=True)
class FixtureBindingOutcome:
    allowed: bool
    reason: Literal[
        "approved_fixture_only",
        "missing_resolution",
        "approval_id_mismatch",
        "binding_mismatch",
        "decision_not_approved",
        "expired",
        "command_mismatch",
        "preflight_mismatch",
        "cli_schema_mismatch",
        "execution_target_mismatch",
        "already_consumed",
    ]


class FixtureApprovalLedger:
    """In-memory one-shot consumption model for tests and protocol evidence."""

    def __init__(self) -> None:
        self._consumed: set[str] = set()

    def consume(
        self,
        binding: FixtureExecutorBinding,
        resolution: FixtureExecutorResolution | None,
        invocation: FixtureExecutorInvocation,
    ) -> FixtureBindingOutcome:
        """Evaluate a fixture binding and consume it only after an exact match.

        This method does not receive a dispatcher or a command.  A caller may
        use an allowed outcome only in a test-local fake-dispatch assertion.
        """

        if resolution is None:
            return FixtureBindingOutcome(False, "missing_resolution")
        if resolution.approval_id != binding.approval_id:
            return FixtureBindingOutcome(False, "approval_id_mismatch")
        if resolution.executor_binding_sha256 != binding.binding_sha256:
            return FixtureBindingOutcome(False, "binding_mismatch")
        if resolution.decision != "approved":
            return FixtureBindingOutcome(False, "decision_not_approved")
        if _parse_timestamp(invocation.observed_at) >= _parse_timestamp(binding.expires_at):
            return FixtureBindingOutcome(False, "expired")
        if invocation.command_sha256 != binding.command_sha256:
            return FixtureBindingOutcome(False, "command_mismatch")
        if invocation.preflight_receipt_sha256s != binding.preflight_receipt_sha256s:
            return FixtureBindingOutcome(False, "preflight_mismatch")
        if invocation.cli_schema_sha256 != binding.cli_schema_sha256:
            return FixtureBindingOutcome(False, "cli_schema_mismatch")
        if invocation.execution_target != binding.execution_target:
            return FixtureBindingOutcome(False, "execution_target_mismatch")
        if binding.binding_sha256 in self._consumed:
            return FixtureBindingOutcome(False, "already_consumed")
        self._consumed.add(binding.binding_sha256)
        return FixtureBindingOutcome(True, "approved_fixture_only")


def bind_approval_for_fixture(
    request: ApprovalRequest,
    *,
    cli_schema_sha256: str,
) -> FixtureExecutorBinding:
    """Extend an existing request in-memory with a future CLI schema pin."""

    return FixtureExecutorBinding(
        approval_id=request.approval_id,
        approval_request_binding_sha256=request.binding_sha256,
        command_sha256=request.command_sha256,
        preflight_receipt_sha256s=request.preflight_receipt_sha256s,
        cli_schema_sha256=cli_schema_sha256,
        execution_target=request.execution_target,
        expires_at=request.expires_at,
    )


def live_cli_schema_sha256_for_fixture() -> str:
    """Derive a schema digest from the current Click tree without execution."""

    from chemsmart.agent.cli_schema import (
        build_chemsmart_cli_schema,
        schema_with_metadata,
    )

    document = schema_with_metadata(build_chemsmart_cli_schema())
    value = document.get("_meta", {}).get("schema_hash")
    if not isinstance(value, str):
        raise ValueError("live CLI schema did not provide a schema hash")
    _require_sha256(value)
    return value


def _require_sha256(value: str) -> None:
    if not _SHA256.fullmatch(value):
        raise ValueError("fixture executor binding requires SHA-256 values")


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("fixture executor binding timestamps must be timezone-aware")
    return parsed


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = [
    "FixtureApprovalLedger",
    "FixtureBindingOutcome",
    "FixtureExecutorBinding",
    "FixtureExecutorInvocation",
    "FixtureExecutorResolution",
    "bind_approval_for_fixture",
    "live_cli_schema_sha256_for_fixture",
]
