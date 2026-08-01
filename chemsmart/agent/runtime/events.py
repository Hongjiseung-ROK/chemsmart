"""Versioned append-only runtime event definitions.

Runtime V2 keeps its v1 event kinds and hash format.  Scientific records live
in an optional, typed ``scientific_v1`` namespace so legacy records and CLI
paths remain valid without a schema or routing change.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from chemsmart.agent.runtime.scientific_contracts import (
    ScientificV1Extension,
    ValidationStatus,
)


class EventKind(str, Enum):
    SESSION_STARTED = "session_started"
    TURN_STARTED = "turn_started"
    EXPOSURE_PLANNED = "exposure_planned"
    TOOL_STARTED = "tool_started"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"
    PERMISSION_RESOLVED = "permission_resolved"
    PROJECT_SELECTED = "project_selected"
    COMMAND_SYNTHESIZED = "command_synthesized"
    CLARIFICATION_REQUESTED = "clarification_requested"
    ARTIFACT_RECORDED = "artifact_recorded"
    SHADOW_VIOLATION = "shadow_violation"
    TURN_COMPLETED = "turn_completed"
    TURN_BLOCKED = "turn_blocked"


_SCIENTIFIC_V1_RECORD_FIELDS = frozenset(
    {
        "provider_capabilities",
        "task_spec",
        "task_graph",
        "resource_budget",
        "approval_request",
        "approval_resolution",
        "approval_invalidation",
        "evidence",
        "validation",
        "claim",
        "review_finding",
        "report_manifest",
        "budget_exhaustion",
        "phase_close",
    }
)

# This registry intentionally maps only existing v1 events.  Adding an event
# kind would make older readers reject the new log before they could ignore an
# optional payload namespace.
SCIENTIFIC_V1_FIELD_REGISTRY: dict[EventKind, frozenset[str]] = {
    EventKind.SESSION_STARTED: frozenset({"provider_capabilities"}),
    EventKind.TURN_STARTED: frozenset(
        {"task_spec", "task_graph", "resource_budget"}
    ),
    EventKind.PERMISSION_RESOLVED: frozenset(
        {
            "approval_request",
            "approval_resolution",
            "approval_invalidation",
        }
    ),
    EventKind.TOOL_SUCCEEDED: frozenset(
        {"evidence", "validation", "budget_exhaustion"}
    ),
    EventKind.TOOL_FAILED: frozenset(
        {"evidence", "validation", "budget_exhaustion"}
    ),
    EventKind.TURN_COMPLETED: frozenset(
        {"claim", "review_finding", "report_manifest", "phase_close"}
    ),
    EventKind.TURN_BLOCKED: frozenset(
        {
            "claim",
            "review_finding",
            "report_manifest",
            "budget_exhaustion",
            "phase_close",
        }
    ),
}

_FORBIDDEN_SCIENTIFIC_FIELD_NAMES = frozenset(
    {
        "reasoning",
        "chain_of_thought",
        "cot",
        "prompt",
        "prompt_text",
        "system_prompt",
        "provider_transcript",
        "raw_response",
        "completion",
        "api_key",
        "apikey",
        "authorization",
        "access_token",
        "token",
        "password",
        "secret",
        "credential",
    }
)
_SECRET_VALUE_PATTERNS = (
    re.compile(
        r"(?i)\b(?:api[_-]?key|authorization|password|secret|"
        r"access[_-]?token)\s*[:=]"
    ),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~-]{8,}"),
    re.compile(r"\bsk-[a-zA-Z0-9_-]{12,}"),
)


class EventPayloadRegistry:
    """Validate optional typed namespaces without rewriting raw event data."""

    @classmethod
    def validate(
        cls,
        kind: EventKind,
        payload: Mapping[str, Any],
    ) -> ScientificV1Extension | None:
        if "scientific_v1" not in payload:
            return None
        if kind not in SCIENTIFIC_V1_FIELD_REGISTRY:
            raise ValueError(
                f"scientific_v1 is not registered for event kind {kind.value!r}"
            )

        raw_extension = payload["scientific_v1"]
        if not isinstance(raw_extension, Mapping):
            raise ValueError("scientific_v1 must be an object")
        _reject_forbidden_scientific_surface(raw_extension)
        extension = ScientificV1Extension.model_validate(raw_extension)
        present_fields = {
            field_name
            for field_name in _SCIENTIFIC_V1_RECORD_FIELDS
            if getattr(extension, field_name) is not None
        }
        unexpected_fields = present_fields - SCIENTIFIC_V1_FIELD_REGISTRY[kind]
        if unexpected_fields:
            joined = ", ".join(sorted(unexpected_fields))
            raise ValueError(
                f"scientific_v1 fields are not registered for {kind.value!r}: "
                f"{joined}"
            )
        _validate_scientific_event_semantics(kind, payload, extension)
        return extension


def scientific_extension_from_payload(
    kind: EventKind,
    payload: Mapping[str, Any],
) -> ScientificV1Extension | None:
    """Return a validated extension while leaving ``payload`` byte-equivalent."""

    return EventPayloadRegistry.validate(kind, payload)


def _reject_forbidden_scientific_surface(value: Any, path: str = "scientific_v1") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("scientific_v1 object keys must be strings")
            normalized = key.strip().lower().replace("-", "_")
            if normalized in _FORBIDDEN_SCIENTIFIC_FIELD_NAMES:
                raise ValueError(
                    f"scientific_v1 does not permit protected field {key!r}"
                )
            _reject_forbidden_scientific_surface(child, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_forbidden_scientific_surface(child, f"{path}[{index}]")
        return
    if isinstance(value, str) and any(
        pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS
    ):
        raise ValueError("scientific_v1 does not permit secret-shaped values")


def _validate_scientific_event_semantics(
    kind: EventKind,
    payload: Mapping[str, Any],
    extension: ScientificV1Extension,
) -> None:
    if kind is EventKind.PERMISSION_RESOLVED:
        approval_records = (
            extension.approval_request,
            extension.approval_resolution,
            extension.approval_invalidation,
        )
        if sum(record is not None for record in approval_records) != 1:
            raise ValueError(
                "permission_resolved scientific_v1 requires exactly one approval record"
            )
        decision = str(payload.get("decision") or "")
        if extension.approval_request is not None and decision != "needs_user":
            raise ValueError(
                "approval request must accompany a needs_user permission decision"
            )
        if (
            extension.approval_resolution is not None
            and decision != extension.approval_resolution.decision.value
        ):
            raise ValueError(
                "approval resolution decision must match the permission decision"
            )
        if extension.approval_invalidation is not None and decision != "invalidated":
            raise ValueError(
                "approval invalidation must accompany an invalidated decision"
            )
    if (
        kind is EventKind.TOOL_FAILED
        and extension.validation is not None
        and extension.validation.status is ValidationStatus.PASS
    ):
        raise ValueError("a failed tool event cannot carry a passing validation")
    if extension.phase_close is not None:
        if (
            kind is EventKind.TURN_COMPLETED
            and extension.phase_close.outcome != "passed"
        ):
            raise ValueError("turn_completed requires a passed phase close")
        if (
            kind is EventKind.TURN_BLOCKED
            and extension.phase_close.outcome != "blocked"
        ):
            raise ValueError("turn_blocked requires a blocked phase close")


class RuntimeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    sequence: int = Field(ge=1)
    event_id: str
    session_id: str
    turn_id: str
    kind: EventKind
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = ""
    previous_hash: str = ""
    event_hash: str

    @model_validator(mode="after")
    def _validates_optional_scientific_namespace(self) -> "RuntimeEvent":
        EventPayloadRegistry.validate(self.kind, self.payload)
        return self

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        session_id: str,
        turn_id: str,
        kind: EventKind,
        payload: dict[str, Any],
        previous_hash: str,
        idempotency_key: str = "",
    ) -> "RuntimeEvent":
        body = {
            "schema_version": 1,
            "sequence": sequence,
            "event_id": uuid4().hex,
            "session_id": session_id,
            "turn_id": turn_id,
            "kind": kind.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
            "idempotency_key": idempotency_key,
            "previous_hash": previous_hash,
        }
        event_hash = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return cls(**body, event_hash=event_hash)

    def verify_hash(self) -> bool:
        body = self.model_dump(exclude={"event_hash"}, mode="json")
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return digest == self.event_hash


__all__ = [
    "EventKind",
    "EventPayloadRegistry",
    "RuntimeEvent",
    "SCIENTIFIC_V1_FIELD_REGISTRY",
    "scientific_extension_from_payload",
]
