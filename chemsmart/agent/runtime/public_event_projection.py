"""Deterministic, path-free public projections of Runtime V2 event streams."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Literal, Sequence

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from chemsmart.agent.runtime.events import EventKind, RuntimeEvent
from chemsmart.agent.runtime.reducer import RuntimeState, reduce_events
from chemsmart.agent.runtime.research_events import (
    is_research_event_kind,
    validate_research_event_payload,
)


PUBLIC_EVENT_PROJECTION_SCHEMA_VERSION = (
    "chemsmart.runtime-public-event-projection-receipt.v1"
)
PUBLIC_EVENT_PROJECTION_RULE_ID = (
    "runtime.public_event_projection.session_cwd_repository_identity.v1"
)
PUBLIC_EVENT_PROJECTION_FIELD = "session_started.payload.cwd"

_SHA256 = r"^[0-9a-f]{64}$"
_REPOSITORY_IDENTITY = re.compile(
    r"^repo://[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?$"
)
_POSIX_ABSOLUTE_FRAGMENT = re.compile(
    r"(?<![A-Za-z0-9_+.:/])/(?:[A-Za-z0-9._~%-]+/)+(?:[^\s\"'<>]*)"
)
_WINDOWS_ABSOLUTE_FRAGMENT = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|\\\\[^\\\s]+[\\/])"
)


class PublicEventProjectionReceiptV1(BaseModel):
    """Content-addressed binding between private and projected event JSONL."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "chemsmart.runtime-public-event-projection-receipt.v1"
    ] = PUBLIC_EVENT_PROJECTION_SCHEMA_VERSION
    projection_rule_id: Literal[
        "runtime.public_event_projection.session_cwd_repository_identity.v1"
    ] = PUBLIC_EVENT_PROJECTION_RULE_ID
    replacement_field: Literal["session_started.payload.cwd"] = (
        PUBLIC_EVENT_PROJECTION_FIELD
    )
    repository_identity: str
    replacement_count: int = Field(ge=0)
    event_count: int = Field(ge=1)
    private_exact_jsonl_sha256: str = Field(pattern=_SHA256)
    projected_jsonl_sha256: str = Field(pattern=_SHA256)
    projected_state_sha256: str = Field(pattern=_SHA256)
    receipt_sha256: str = Field(pattern=_SHA256)

    @field_validator("repository_identity")
    @classmethod
    def _identity_is_path_free(cls, value: str) -> str:
        return _validated_repository_identity(value)

    @model_validator(mode="after")
    def _receipt_is_content_addressed(self) -> "PublicEventProjectionReceiptV1":
        if self.replacement_count > self.event_count:
            raise ValueError("replacement count exceeds event count")
        if self.receipt_sha256 != public_event_projection_receipt_sha256(self):
            raise ValueError("public event projection receipt digest mismatch")
        return self


@dataclass(frozen=True)
class PublicEventProjection:
    projected_jsonl_bytes: bytes
    receipt: PublicEventProjectionReceiptV1


def project_runtime_events_for_public(
    events: Sequence[RuntimeEvent],
    *,
    repository_identity: str,
) -> PublicEventProjection:
    """Project an exact private event sequence into path-free public JSONL.

    The input sequence is validated and deterministically serialized without
    mutation. Only an absolute ``SESSION_STARTED`` ``payload.cwd`` is replaced.
    All event identity fields are retained while the hash chain is rebuilt.
    """

    identity = _validated_repository_identity(repository_identity)
    private_events = tuple(events)
    _validate_event_sequence(private_events)
    private_jsonl = _event_jsonl_bytes(private_events)

    projected: list[RuntimeEvent] = []
    previous_hash = ""
    replacement_count = 0
    for event in private_events:
        payload = deepcopy(event.payload)
        if event.kind is EventKind.SESSION_STARTED:
            cwd = payload.get("cwd")
            if isinstance(cwd, str) and _is_absolute_path_value(cwd):
                payload["cwd"] = identity
                replacement_count += 1
        projected_event = _projected_event(
            event,
            payload=payload,
            previous_hash=previous_hash,
        )
        projected.append(projected_event)
        previous_hash = projected_event.event_hash

    projected_events = tuple(projected)
    _reject_remaining_absolute_paths(projected_events)
    projected_state = _validate_event_sequence(projected_events)
    projected_jsonl = _event_jsonl_bytes(projected_events)
    body = {
        "schema_version": PUBLIC_EVENT_PROJECTION_SCHEMA_VERSION,
        "projection_rule_id": PUBLIC_EVENT_PROJECTION_RULE_ID,
        "replacement_field": PUBLIC_EVENT_PROJECTION_FIELD,
        "repository_identity": identity,
        "replacement_count": replacement_count,
        "event_count": len(projected_events),
        "private_exact_jsonl_sha256": _content_sha256(private_jsonl),
        "projected_jsonl_sha256": _content_sha256(projected_jsonl),
        "projected_state_sha256": _canonical_json_sha256(
            projected_state.model_dump(mode="json")
        ),
    }
    receipt = PublicEventProjectionReceiptV1.model_validate(
        {**body, "receipt_sha256": _canonical_json_sha256(body)}
    )
    return PublicEventProjection(
        projected_jsonl_bytes=projected_jsonl,
        receipt=receipt,
    )


def public_event_projection_receipt_sha256(
    value: PublicEventProjectionReceiptV1 | dict[str, Any],
) -> str:
    if isinstance(value, BaseModel):
        body = value.model_dump(mode="json", exclude={"receipt_sha256"})
    else:
        body = {
            key: item
            for key, item in value.items()
            if key != "receipt_sha256"
        }
    return _canonical_json_sha256(body)


def _validated_repository_identity(value: str) -> str:
    if not isinstance(value, str) or not _REPOSITORY_IDENTITY.fullmatch(value):
        raise ValueError(
            "repository identity must be a path-free repo://<identifier> value"
        )
    identifier = value.removeprefix("repo://")
    if ".." in identifier:
        raise ValueError("repository identity cannot contain traversal syntax")
    return value


def _projected_event(
    event: RuntimeEvent,
    *,
    payload: dict[str, Any],
    previous_hash: str,
) -> RuntimeEvent:
    body = event.model_dump(
        mode="json",
        exclude={"event_hash", "previous_hash"},
    )
    body["payload"] = payload
    body["previous_hash"] = previous_hash
    event_hash = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return RuntimeEvent.model_validate({**body, "event_hash": event_hash})


def _validate_event_sequence(events: tuple[RuntimeEvent, ...]) -> RuntimeState:
    if not events:
        raise ValueError("runtime event sequence must not be empty")
    previous_hash = ""
    for expected_sequence, event in enumerate(events, start=1):
        if not isinstance(event, RuntimeEvent):
            raise TypeError("runtime event sequence contains a non-event value")
        if event.sequence != expected_sequence:
            raise ValueError("runtime event sequence is not contiguous")
        if event.previous_hash != previous_hash:
            raise ValueError("runtime event hash chain is broken")
        if not event.verify_hash():
            raise ValueError("runtime event hash is invalid")
        canonical_payload = validate_research_event_payload(
            event.kind,
            event.payload,
        )
        if (
            is_research_event_kind(event.kind)
            and canonical_payload != event.payload
        ):
            raise ValueError("runtime research payload is noncanonical")
        previous_hash = event.event_hash

    first = reduce_events(events)
    second = reduce_events(events)
    first_payload = first.model_dump(mode="json")
    if first_payload != second.model_dump(mode="json"):
        raise ValueError("runtime event replay is non-deterministic")
    if (
        first.latest_sequence != events[-1].sequence
        or first.latest_event_hash != events[-1].event_hash
    ):
        raise ValueError("runtime replay state is not at the event-log tip")
    return first


def _reject_remaining_absolute_paths(
    events: tuple[RuntimeEvent, ...],
) -> None:
    for index, event in enumerate(events, start=1):
        location = _first_absolute_path_location(
            event.payload,
            path=f"event[{index}].payload",
        )
        if location is not None:
            raise ValueError(
                "projected public payload retains an unexpected absolute path "
                f"at {location}"
            )


def _first_absolute_path_location(
    value: Any,
    *,
    path: str,
) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            found = _first_absolute_path_location(
                item,
                path=f"{path}.{key}",
            )
            if found is not None:
                return found
        return None
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found = _first_absolute_path_location(
                item,
                path=f"{path}[{index}]",
            )
            if found is not None:
                return found
        return None
    if isinstance(value, str) and _contains_absolute_path_fragment(value):
        return path
    return None


def _is_absolute_path_value(value: str) -> bool:
    if value.casefold().startswith("file://"):
        return True
    return PurePosixPath(value).is_absolute() or PureWindowsPath(
        value
    ).is_absolute()


def _contains_absolute_path_fragment(value: str) -> bool:
    if _REPOSITORY_IDENTITY.fullmatch(value):
        return False
    if "file://" in value.casefold():
        return True
    if _is_absolute_path_value(value):
        return True
    return bool(
        _POSIX_ABSOLUTE_FRAGMENT.search(value)
        or _WINDOWS_ABSOLUTE_FRAGMENT.search(value)
    )


def _event_jsonl_bytes(events: tuple[RuntimeEvent, ...]) -> bytes:
    return b"".join(
        event.model_dump_json().encode("utf-8") + b"\n" for event in events
    )


def _content_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return _content_sha256(payload)


__all__ = [
    "PUBLIC_EVENT_PROJECTION_FIELD",
    "PUBLIC_EVENT_PROJECTION_RULE_ID",
    "PUBLIC_EVENT_PROJECTION_SCHEMA_VERSION",
    "PublicEventProjection",
    "PublicEventProjectionReceiptV1",
    "project_runtime_events_for_public",
    "public_event_projection_receipt_sha256",
]
