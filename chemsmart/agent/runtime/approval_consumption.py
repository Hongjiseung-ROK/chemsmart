"""Pure approval-consumption evaluation for a future Runtime V2 executor seam.

This module is intentionally isolated from the active runtime lifecycle and
all command-execution paths. It accepts immutable, digest-only records and
returns a verdict; it has no persistence, external hooks, process surface, network
client, or command text.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Literal, Mapping, Sequence

from pydantic import Field, model_validator

from chemsmart.agent.harness.preflight_receipt import (
    COMMAND_PREFLIGHT_SCHEMA_VERSION,
    CommandPreflightReceipt,
)
from chemsmart.agent.runtime.contracts import RuntimeContract
from chemsmart.agent.runtime.scientific_contracts import (
    ApprovalDecision,
    ApprovalInvalidation,
    ApprovalRequest,
    ApprovalResolution,
    approval_resolution_matches,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_USER_ROLE = "user"


class ExecutorInvocation(RuntimeContract):
    """Digest-only invocation shape for the non-executing library boundary."""

    contract_version: Literal[1] = 1
    approval_id: str = Field(min_length=1, max_length=128)
    approval_request_binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_name: str = Field(min_length=1, max_length=128)
    command_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_preflight_receipt_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    cli_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_target: str = Field(min_length=1, max_length=128)
    requested_at: str = Field(min_length=1, max_length=64)
    expires_at: str = Field(min_length=1, max_length=64)
    observed_at: str = Field(min_length=1, max_length=64)
    execution_mode: Literal["library_only"] = "library_only"

    @model_validator(mode="after")
    def _requires_a_positive_window(self) -> "ExecutorInvocation":
        requested_at = _parse_timestamp(self.requested_at)
        expires_at = _parse_timestamp(self.expires_at)
        _parse_timestamp(self.observed_at)
        if requested_at >= expires_at:
            raise ValueError("executor invocation requires a positive window")
        return self

    @property
    def binding_sha256(self) -> str:
        """Return the proposed surface bound before the later observation."""

        body = self.model_dump(mode="json")
        body.pop("observed_at")
        return _sha256_json(body)


class ExecutorResolution(RuntimeContract):
    """A separate, user-only outer decision over one exact invocation digest."""

    contract_version: Literal[1] = 1
    approval_id: str = Field(min_length=1, max_length=128)
    executor_invocation_binding_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    decision: Literal["approved", "denied"]
    actor_role: Literal["user", "policy", "system"]
    resolved_at: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _requires_a_timestamp(self) -> "ExecutorResolution":
        _parse_timestamp(self.resolved_at)
        return self


class ApprovalConsumptionVerdict(RuntimeContract):
    """Safe outcome only; no action is represented or triggered here."""

    allowed: bool
    reason: str = Field(min_length=1, max_length=128)


def evaluate_approval_consumption(
    *,
    request: ApprovalRequest,
    approval_resolutions: Sequence[ApprovalResolution],
    approval_invalidations: Sequence[ApprovalInvalidation],
    executor_invocation: ExecutorInvocation,
    executor_resolutions: Sequence[ExecutorResolution],
    preflight_receipt: CommandPreflightReceipt,
    current_cli_schema_document: Mapping[str, Any],
) -> ApprovalConsumptionVerdict:
    """Fail closed unless every immutable approval and preflight fact agrees.

    The input sequences must retain all terminal records for the relevant
    approval identifier so duplicated records cannot be hidden by a caller.
    """

    mismatch = _invocation_request_mismatch(executor_invocation, request)
    if mismatch is not None:
        return _deny(mismatch)

    preflight_issue = _preflight_receipt_issue(preflight_receipt)
    if preflight_issue is not None:
        return _deny(preflight_issue)
    receipt_sha256 = canonical_preflight_receipt_sha256(preflight_receipt)
    if preflight_receipt.command_sha256 != request.command_sha256:
        return _deny("preflight_command_mismatch")
    if receipt_sha256 not in request.preflight_receipt_sha256s:
        return _deny("preflight_not_in_request")
    if receipt_sha256 != executor_invocation.canonical_preflight_receipt_sha256:
        return _deny("invocation_preflight_mismatch")

    try:
        current_cli_schema_sha256 = cli_schema_sha256_from_document(
            current_cli_schema_document
        )
    except ValueError:
        return _deny("current_cli_schema_invalid")
    if executor_invocation.cli_schema_sha256 != current_cli_schema_sha256:
        return _deny("invocation_cli_schema_mismatch")

    try:
        requested_at = _parse_timestamp(request.requested_at)
        expires_at = _parse_timestamp(request.expires_at)
        observed_at = _parse_timestamp(executor_invocation.observed_at)
    except ValueError:
        return _deny("request_timestamp_invalid")
    if requested_at >= expires_at:
        return _deny("invalid_approval_window")
    if observed_at >= expires_at:
        return _deny("expired")

    base_resolution = _matching_base_resolution(request, approval_resolutions)
    if isinstance(base_resolution, str):
        return _deny(base_resolution)
    if not approval_resolution_matches(request, base_resolution):
        return _deny("base_resolution_not_approved")
    if base_resolution.actor_role != _USER_ROLE:
        return _deny("base_resolution_actor_not_user")
    try:
        base_resolved_at = _parse_timestamp(base_resolution.resolved_at)
    except ValueError:
        return _deny("base_resolution_timestamp_invalid")
    if base_resolved_at <= requested_at:
        return _deny("base_resolution_before_request")
    if base_resolved_at >= expires_at:
        return _deny("base_resolution_expired")
    if observed_at < base_resolved_at:
        return _deny("invocation_before_base_resolution")

    invalidation_issue = _matching_invalidation_issue(
        request,
        approval_invalidations,
        observed_at,
    )
    if invalidation_issue is not None:
        return _deny(invalidation_issue)

    outer_resolution = _matching_outer_resolution(
        executor_invocation,
        executor_resolutions,
    )
    if isinstance(outer_resolution, str):
        return _deny(outer_resolution)
    if outer_resolution.decision != "approved":
        return _deny("outer_resolution_not_approved")
    if outer_resolution.actor_role != _USER_ROLE:
        return _deny("outer_resolution_actor_not_user")
    try:
        outer_resolved_at = _parse_timestamp(outer_resolution.resolved_at)
    except ValueError:
        return _deny("outer_resolution_timestamp_invalid")
    if outer_resolved_at <= requested_at:
        return _deny("outer_resolution_before_request")
    if outer_resolved_at >= expires_at:
        return _deny("outer_resolution_expired")
    if outer_resolved_at < base_resolved_at:
        return _deny("outer_resolution_before_base")
    if observed_at < outer_resolved_at:
        return _deny("invocation_before_outer_resolution")

    return ApprovalConsumptionVerdict(
        allowed=True,
        reason="approved_library_only",
    )


def canonical_preflight_receipt_sha256(
    receipt: CommandPreflightReceipt,
) -> str:
    """Return a deterministic digest of the public preflight receipt shape."""

    return _sha256_json(receipt.to_dict())


def cli_schema_sha256_from_document(document: Mapping[str, Any]) -> str:
    """Validate supplied schema metadata against its schema body before use."""

    metadata = document.get("_meta")
    if not isinstance(metadata, Mapping):
        raise ValueError("schema document lacks metadata")
    declared = metadata.get("schema_hash")
    if not isinstance(declared, str) or not _SHA256.fullmatch(declared):
        raise ValueError("schema document lacks a valid digest")
    body = {key: value for key, value in document.items() if key != "_meta"}
    from chemsmart.agent.cli_schema import schema_with_metadata

    recomputed = schema_with_metadata(body).get("_meta", {}).get("schema_hash")
    if declared != recomputed:
        raise ValueError("schema metadata does not match its body")
    return declared


def _invocation_request_mismatch(
    invocation: ExecutorInvocation,
    request: ApprovalRequest,
) -> str | None:
    if invocation.approval_id != request.approval_id:
        return "approval_id_mismatch"
    if invocation.approval_request_binding_sha256 != request.binding_sha256:
        return "base_request_binding_mismatch"
    if (
        invocation.tool_name != request.tool_name
        or invocation.command_sha256 != request.command_sha256
        or invocation.execution_target != request.execution_target
        or invocation.requested_at != request.requested_at
        or invocation.expires_at != request.expires_at
    ):
        return "invocation_request_surface_mismatch"
    return None


def _matching_base_resolution(
    request: ApprovalRequest,
    resolutions: Sequence[ApprovalResolution],
) -> ApprovalResolution | str:
    matches = tuple(
        resolution
        for resolution in resolutions
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
    invalidations: Sequence[ApprovalInvalidation],
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
    invocation: ExecutorInvocation,
    resolutions: Sequence[ExecutorResolution],
) -> ExecutorResolution | str:
    matches = tuple(
        resolution
        for resolution in resolutions
        if resolution.approval_id == invocation.approval_id
        and resolution.executor_invocation_binding_sha256
        == invocation.binding_sha256
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


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return parsed


def _deny(reason: str) -> ApprovalConsumptionVerdict:
    return ApprovalConsumptionVerdict(allowed=False, reason=reason)


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = [
    "ApprovalConsumptionVerdict",
    "ExecutorInvocation",
    "ExecutorResolution",
    "canonical_preflight_receipt_sha256",
    "cli_schema_sha256_from_document",
    "evaluate_approval_consumption",
]
