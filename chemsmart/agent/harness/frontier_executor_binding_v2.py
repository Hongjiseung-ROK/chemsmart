"""Fixture-only prospective approval lineage and preflight binding.

This module is deliberately not imported by the active Runtime V2, CLI, tool
loop, or command-execution path.  It models a future enforcement boundary from
typed, immutable records and an archived-shaped preflight receipt.  It accepts
no command string, dispatcher, process handle, engine client, or network
client, and can only permit a test-local fake-dispatch observation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal, Mapping

from chemsmart.agent.harness.preflight_receipt import (
    COMMAND_PREFLIGHT_SCHEMA_VERSION,
    CommandPreflightReceipt,
)
from chemsmart.agent.runtime.scientific_contracts import (
    ApprovalInvalidation,
    ApprovalRequest,
    ApprovalResolution,
    approval_resolution_matches,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BINDING_VERSION = "frontier.fixture-executor-binding.v2"
_USER_ROLE = "user"


@dataclass(frozen=True)
class FixtureExecutorBindingV2:
    """Future-only exact binding for an archived-shaped preflight receipt."""

    approval_id: str
    approval_request_binding_sha256: str
    command_sha256: str
    preflight_receipt_sha256s: tuple[str, ...]
    canonical_preflight_receipt_sha256: str
    cli_schema_sha256: str
    execution_target: str
    requested_at: str
    expires_at: str
    schema_version: str = _BINDING_VERSION

    def __post_init__(self) -> None:
        if not self.approval_id or not self.execution_target:
            raise ValueError("fixture v2 binding requires identifiers")
        if self.schema_version != _BINDING_VERSION:
            raise ValueError("fixture v2 binding schema version is invalid")
        for value in (
            self.approval_request_binding_sha256,
            self.command_sha256,
            self.canonical_preflight_receipt_sha256,
            self.cli_schema_sha256,
        ):
            _require_sha256(value)
        _require_sorted_sha256s(self.preflight_receipt_sha256s)
        if self.canonical_preflight_receipt_sha256 not in self.preflight_receipt_sha256s:
            raise ValueError("fixture v2 binding requires its canonical preflight digest")
        requested_at = _parse_timestamp(self.requested_at)
        expires_at = _parse_timestamp(self.expires_at)
        if requested_at >= expires_at:
            raise ValueError("fixture v2 binding requires a positive approval window")

    @property
    def binding_sha256(self) -> str:
        return _sha256_json(asdict(self))


@dataclass(frozen=True)
class FixtureExecutorResolutionV2:
    """Fixture-only user decision over one exact v2 outer binding."""

    approval_id: str
    executor_binding_sha256: str
    decision: Literal["approved", "denied"]
    actor_role: Literal["user", "policy", "system"]
    resolved_at: str

    def __post_init__(self) -> None:
        if not self.approval_id:
            raise ValueError("fixture v2 resolution requires an approval id")
        _require_sha256(self.executor_binding_sha256)
        _parse_timestamp(self.resolved_at)


@dataclass(frozen=True)
class FixtureApprovalLineageV2:
    """Ordered, immutable typed records for a prospective fixture decision."""

    approval_resolutions: tuple[ApprovalResolution, ...]
    approval_invalidations: tuple[ApprovalInvalidation, ...] = ()
    executor_resolutions: tuple[FixtureExecutorResolutionV2, ...] = ()


@dataclass(frozen=True)
class FixtureExecutorInvocationV2:
    """Observed hashes for a proposed fixture-only dispatch."""

    command_sha256: str
    preflight_receipt_sha256: str
    cli_schema_sha256: str
    execution_target: str
    observed_at: str
    execution_mode: Literal["fixture_only"] = "fixture_only"

    def __post_init__(self) -> None:
        for value in (
            self.command_sha256,
            self.preflight_receipt_sha256,
            self.cli_schema_sha256,
        ):
            _require_sha256(value)
        if not self.execution_target:
            raise ValueError("fixture v2 invocation requires an execution target")
        _parse_timestamp(self.observed_at)


@dataclass(frozen=True)
class FixtureBindingV2Outcome:
    allowed: bool
    reason: str


class FixtureApprovalLineageLedgerV2:
    """In-memory, one-shot fixture ledger with no dispatch capability."""

    def __init__(self) -> None:
        self._consumed: set[str] = set()

    def consume(
        self,
        *,
        request: ApprovalRequest,
        binding: FixtureExecutorBindingV2,
        preflight_receipt: CommandPreflightReceipt,
        lineage: FixtureApprovalLineageV2,
        invocation: FixtureExecutorInvocationV2,
        current_cli_schema_document: Mapping[str, Any],
    ) -> FixtureBindingV2Outcome:
        """Evaluate an exact fixture-only lineage without dispatching anything."""

        request_match = _binding_request_mismatch(binding, request)
        if request_match is not None:
            return FixtureBindingV2Outcome(False, request_match)

        preflight_issue = _preflight_receipt_issue(preflight_receipt)
        if preflight_issue is not None:
            return FixtureBindingV2Outcome(False, preflight_issue)
        receipt_sha256 = canonical_preflight_receipt_sha256(preflight_receipt)
        if preflight_receipt.command_sha256 != request.command_sha256:
            return FixtureBindingV2Outcome(False, "preflight_command_mismatch")
        if receipt_sha256 not in request.preflight_receipt_sha256s:
            return FixtureBindingV2Outcome(False, "preflight_not_in_request")
        if receipt_sha256 not in binding.preflight_receipt_sha256s:
            return FixtureBindingV2Outcome(False, "preflight_not_in_binding")
        if receipt_sha256 != binding.canonical_preflight_receipt_sha256:
            return FixtureBindingV2Outcome(False, "preflight_receipt_mismatch")
        if invocation.preflight_receipt_sha256 != receipt_sha256:
            return FixtureBindingV2Outcome(False, "invocation_preflight_mismatch")
        if invocation.command_sha256 != request.command_sha256:
            return FixtureBindingV2Outcome(False, "command_mismatch")
        if invocation.execution_target != binding.execution_target:
            return FixtureBindingV2Outcome(False, "execution_target_mismatch")

        try:
            current_cli_schema_sha256 = cli_schema_sha256_from_document(
                current_cli_schema_document
            )
        except ValueError:
            return FixtureBindingV2Outcome(False, "current_cli_schema_invalid")
        if invocation.cli_schema_sha256 != current_cli_schema_sha256:
            return FixtureBindingV2Outcome(False, "invocation_cli_schema_mismatch")
        if binding.cli_schema_sha256 != current_cli_schema_sha256:
            return FixtureBindingV2Outcome(False, "cli_schema_mismatch")

        try:
            requested_at = _parse_timestamp(request.requested_at)
            expires_at = _parse_timestamp(request.expires_at)
            observed_at = _parse_timestamp(invocation.observed_at)
        except ValueError:
            return FixtureBindingV2Outcome(False, "request_timestamp_invalid")
        if requested_at >= expires_at:
            return FixtureBindingV2Outcome(False, "invalid_approval_window")
        if observed_at >= expires_at:
            return FixtureBindingV2Outcome(False, "expired")

        base_resolution = _matching_base_resolution(request, lineage)
        if isinstance(base_resolution, str):
            return FixtureBindingV2Outcome(False, base_resolution)
        if not approval_resolution_matches(request, base_resolution):
            return FixtureBindingV2Outcome(False, "base_resolution_not_approved")
        if base_resolution.actor_role != _USER_ROLE:
            return FixtureBindingV2Outcome(False, "base_resolution_actor_not_user")
        try:
            base_resolved_at = _parse_timestamp(base_resolution.resolved_at)
        except ValueError:
            return FixtureBindingV2Outcome(False, "base_resolution_timestamp_invalid")
        if base_resolved_at <= requested_at:
            return FixtureBindingV2Outcome(False, "base_resolution_before_request")
        if base_resolved_at >= expires_at:
            return FixtureBindingV2Outcome(False, "base_resolution_expired")
        if observed_at < base_resolved_at:
            return FixtureBindingV2Outcome(False, "invocation_before_base_resolution")

        invalidation_issue = _matching_invalidation_issue(
            request,
            lineage.approval_invalidations,
            observed_at,
        )
        if invalidation_issue is not None:
            return FixtureBindingV2Outcome(False, invalidation_issue)

        outer_resolution = _matching_outer_resolution(binding, lineage)
        if isinstance(outer_resolution, str):
            return FixtureBindingV2Outcome(False, outer_resolution)
        if outer_resolution.decision != "approved":
            return FixtureBindingV2Outcome(False, "outer_resolution_not_approved")
        if outer_resolution.actor_role != _USER_ROLE:
            return FixtureBindingV2Outcome(False, "outer_resolution_actor_not_user")
        outer_resolved_at = _parse_timestamp(outer_resolution.resolved_at)
        if outer_resolved_at <= requested_at:
            return FixtureBindingV2Outcome(False, "outer_resolution_before_request")
        if outer_resolved_at >= expires_at:
            return FixtureBindingV2Outcome(False, "outer_resolution_expired")
        if outer_resolved_at < base_resolved_at:
            return FixtureBindingV2Outcome(False, "outer_resolution_before_base")
        if observed_at < outer_resolved_at:
            return FixtureBindingV2Outcome(False, "invocation_before_outer_resolution")
        if binding.binding_sha256 in self._consumed:
            return FixtureBindingV2Outcome(False, "already_consumed")

        self._consumed.add(binding.binding_sha256)
        return FixtureBindingV2Outcome(True, "approved_fixture_only")


def bind_approval_for_fixture_v2(
    request: ApprovalRequest,
    *,
    preflight_receipt: CommandPreflightReceipt,
    cli_schema_document: Mapping[str, Any] | None = None,
) -> FixtureExecutorBindingV2:
    """Create a v2 binding from a typed request and accepted local receipt.

    The receipt is used only to calculate a canonical local digest.  Neither
    its content nor a command string is stored by this fixture contract.
    """

    preflight_issue = _preflight_receipt_issue(preflight_receipt)
    if preflight_issue is not None:
        raise ValueError(f"fixture v2 preflight receipt is not acceptable: {preflight_issue}")
    if preflight_receipt.command_sha256 != request.command_sha256:
        raise ValueError("fixture v2 receipt command digest must match the request")
    receipt_sha256 = canonical_preflight_receipt_sha256(preflight_receipt)
    if receipt_sha256 not in request.preflight_receipt_sha256s:
        raise ValueError("fixture v2 receipt digest must be bound by the request")
    document = (
        live_cli_schema_document_for_fixture()
        if cli_schema_document is None
        else cli_schema_document
    )
    return FixtureExecutorBindingV2(
        approval_id=request.approval_id,
        approval_request_binding_sha256=request.binding_sha256,
        command_sha256=request.command_sha256,
        preflight_receipt_sha256s=request.preflight_receipt_sha256s,
        canonical_preflight_receipt_sha256=receipt_sha256,
        cli_schema_sha256=cli_schema_sha256_from_document(document),
        execution_target=request.execution_target,
        requested_at=request.requested_at,
        expires_at=request.expires_at,
    )


def canonical_preflight_receipt_sha256(
    receipt: CommandPreflightReceipt,
) -> str:
    """Hash a receipt locally using a deterministic, path-free JSON form."""

    return _sha256_json(receipt.to_dict())


def live_cli_schema_document_for_fixture() -> dict[str, Any]:
    """Read the current Click tree without invoking a ChemSmart command."""

    from chemsmart.agent.cli_schema import (
        build_chemsmart_cli_schema,
        schema_with_metadata,
    )

    return schema_with_metadata(build_chemsmart_cli_schema())


def cli_schema_sha256_from_document(document: Mapping[str, Any]) -> str:
    """Verify the metadata hash against its schema body before using it."""

    metadata = document.get("_meta")
    if not isinstance(metadata, Mapping):
        raise ValueError("fixture v2 schema document lacks metadata")
    declared = metadata.get("schema_hash")
    if not isinstance(declared, str):
        raise ValueError("fixture v2 schema document lacks a schema digest")
    _require_sha256(declared)
    body = {key: value for key, value in document.items() if key != "_meta"}
    from chemsmart.agent.cli_schema import schema_with_metadata

    recomputed = schema_with_metadata(body).get("_meta", {}).get("schema_hash")
    if declared != recomputed:
        raise ValueError("fixture v2 schema metadata does not match its body")
    return declared


def _binding_request_mismatch(
    binding: FixtureExecutorBindingV2,
    request: ApprovalRequest,
) -> str | None:
    if binding.approval_id != request.approval_id:
        return "approval_id_mismatch"
    if binding.approval_request_binding_sha256 != request.binding_sha256:
        return "base_request_binding_mismatch"
    if (
        binding.command_sha256 != request.command_sha256
        or binding.preflight_receipt_sha256s != request.preflight_receipt_sha256s
        or binding.execution_target != request.execution_target
        or binding.requested_at != request.requested_at
        or binding.expires_at != request.expires_at
    ):
        return "binding_request_surface_mismatch"
    return None


def _matching_base_resolution(
    request: ApprovalRequest,
    lineage: FixtureApprovalLineageV2,
) -> ApprovalResolution | str:
    matches = tuple(
        resolution
        for resolution in lineage.approval_resolutions
        if resolution.approval_id == request.approval_id
        and resolution.request_binding_sha256 == request.binding_sha256
    )
    if not matches:
        return "missing_base_resolution"
    if len(matches) != 1:
        return "multiple_base_terminal_resolutions"
    return matches[0]


def _matching_invalidation_issue(
    request: ApprovalRequest,
    invalidations: tuple[ApprovalInvalidation, ...],
    observed_at: datetime,
) -> str | None:
    for invalidation in invalidations:
        if (
            invalidation.approval_id != request.approval_id
            or invalidation.previous_binding_sha256 != request.binding_sha256
        ):
            continue
        try:
            invalidated_at = _parse_timestamp(invalidation.invalidated_at)
        except ValueError:
            return "invalidation_timestamp_invalid"
        if invalidated_at <= observed_at:
            return "binding_invalidated"
    return None


def _matching_outer_resolution(
    binding: FixtureExecutorBindingV2,
    lineage: FixtureApprovalLineageV2,
) -> FixtureExecutorResolutionV2 | str:
    matches = tuple(
        resolution
        for resolution in lineage.executor_resolutions
        if resolution.approval_id == binding.approval_id
        and resolution.executor_binding_sha256 == binding.binding_sha256
    )
    if not matches:
        return "missing_outer_resolution"
    if len(matches) != 1:
        return "multiple_outer_terminal_resolutions"
    return matches[0]


def _preflight_receipt_issue(receipt: CommandPreflightReceipt) -> str | None:
    if receipt.schema_version != COMMAND_PREFLIGHT_SCHEMA_VERSION:
        return "preflight_schema_version_invalid"
    if not isinstance(receipt.command_sha256, str) or not _SHA256.fullmatch(
        receipt.command_sha256
    ):
        return "preflight_command_digest_invalid"
    if not _gate_verdict_is_ok(receipt.parser):
        return "preflight_parser_not_ok"
    if not _gate_verdict_is_ok(receipt.semantic_gate):
        return "preflight_semantic_gate_not_ok"
    if not _gate_verdict_is_ok(receipt.intent_gate):
        return "preflight_intent_gate_not_ok"
    return None


def _gate_verdict_is_ok(value: object) -> bool:
    return isinstance(value, Mapping) and value.get("verdict") == "ok"


def _require_sha256(value: str) -> None:
    if not _SHA256.fullmatch(value):
        raise ValueError("fixture v2 requires SHA-256 values")


def _require_sorted_sha256s(values: tuple[str, ...]) -> None:
    if not values or tuple(sorted(set(values))) != values:
        raise ValueError("fixture v2 requires sorted, unique SHA-256 values")
    for value in values:
        _require_sha256(value)


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("fixture v2 timestamps must be timezone-aware")
    return parsed


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = [
    "FixtureApprovalLineageLedgerV2",
    "FixtureApprovalLineageV2",
    "FixtureBindingV2Outcome",
    "FixtureExecutorBindingV2",
    "FixtureExecutorInvocationV2",
    "FixtureExecutorResolutionV2",
    "bind_approval_for_fixture_v2",
    "canonical_preflight_receipt_sha256",
    "cli_schema_sha256_from_document",
    "live_cli_schema_document_for_fixture",
]
