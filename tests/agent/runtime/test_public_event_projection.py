from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from chemsmart.agent.runtime.events import EventKind, RuntimeEvent
from chemsmart.agent.runtime.public_event_projection import (
    PUBLIC_EVENT_PROJECTION_FIELD,
    PUBLIC_EVENT_PROJECTION_RULE_ID,
    PublicEventProjectionReceiptV1,
    project_runtime_events_for_public,
    public_event_projection_receipt_sha256,
)
from chemsmart.agent.runtime.reducer import reduce_events


def test_projection_is_deterministic_replayable_and_content_addressed():
    private_events = _events(
        cwd="/Users/researcher/private-worktree/chemsmart"
    )
    before = tuple(event.model_dump(mode="json") for event in private_events)

    first = project_runtime_events_for_public(
        private_events,
        repository_identity="repo://chemsmart",
    )
    second = project_runtime_events_for_public(
        private_events,
        repository_identity="repo://chemsmart",
    )
    projected = _parse_jsonl(first.projected_jsonl_bytes)

    assert first == second
    assert tuple(
        event.model_dump(mode="json") for event in private_events
    ) == before
    assert len(projected) == len(private_events) == 2
    assert projected[0].payload == {
        "cwd": "repo://chemsmart",
        "workspace_role": "development",
    }
    assert projected[1].payload == private_events[1].payload
    for private, public in zip(private_events, projected, strict=True):
        assert public.schema_version == private.schema_version
        assert public.sequence == private.sequence
        assert public.event_id == private.event_id
        assert public.session_id == private.session_id
        assert public.turn_id == private.turn_id
        assert public.kind is private.kind
        assert public.timestamp == private.timestamp
        assert public.idempotency_key == private.idempotency_key
    assert projected[0].previous_hash == ""
    assert projected[1].previous_hash == projected[0].event_hash
    assert all(event.verify_hash() for event in projected)
    assert projected[0].event_hash != private_events[0].event_hash
    assert projected[1].event_hash != private_events[1].event_hash

    private_jsonl = _jsonl(private_events)
    receipt = first.receipt
    assert receipt.projection_rule_id == PUBLIC_EVENT_PROJECTION_RULE_ID
    assert receipt.replacement_field == PUBLIC_EVENT_PROJECTION_FIELD
    assert receipt.repository_identity == "repo://chemsmart"
    assert receipt.replacement_count == 1
    assert receipt.event_count == 2
    assert receipt.private_exact_jsonl_sha256 == hashlib.sha256(
        private_jsonl
    ).hexdigest()
    assert receipt.projected_jsonl_sha256 == hashlib.sha256(
        first.projected_jsonl_bytes
    ).hexdigest()
    assert receipt.projected_state_sha256 == _canonical_sha256(
        reduce_events(projected).model_dump(mode="json")
    )
    assert receipt.receipt_sha256 == public_event_projection_receipt_sha256(
        receipt
    )


@pytest.mark.parametrize(
    "identity",
    (
        "/Users/researcher/chemsmart",
        "file:///Users/researcher/chemsmart",
        "https://example.test/chemsmart",
        "repo://chemsmart/subdirectory",
        "repo://../chemsmart",
        "repo://chemsmart..private",
    ),
)
def test_projection_rejects_non_path_free_repository_identity(identity):
    with pytest.raises(ValueError, match="repository identity"):
        project_runtime_events_for_public(
            _events(),
            repository_identity=identity,
        )


@pytest.mark.parametrize(
    "request_text",
    (
        "inspect /Users/researcher/private/input.xyz",
        r"inspect C:\Users\researcher\private\input.xyz",
        "inspect file:///private/input.xyz",
    ),
)
def test_projection_rejects_other_absolute_paths_in_public_payloads(
    request_text,
):
    with pytest.raises(
        ValueError,
        match=r"unexpected absolute path at event\[2\]\.payload\.request",
    ):
        project_runtime_events_for_public(
            _events(request_text=request_text),
            repository_identity="repo://chemsmart",
        )


def test_projection_accepts_scientific_slash_notation():
    projection = project_runtime_events_for_public(
        _events(
            request_text=(
                "Compare `D3`/`D3BJ` and Gaussian/ORCA without host paths."
            )
        ),
        repository_identity="repo://chemsmart",
    )

    assert b"D3BJ" in projection.projected_jsonl_bytes


def test_projection_rejects_a_broken_private_hash_chain():
    first, second = _events()
    broken = second.model_copy(update={"previous_hash": "0" * 64})

    with pytest.raises(ValueError, match="hash chain is broken"):
        project_runtime_events_for_public(
            (first, broken),
            repository_identity="repo://chemsmart",
        )


def test_projection_receipt_rejects_tampering():
    receipt = project_runtime_events_for_public(
        _events(),
        repository_identity="repo://chemsmart",
    ).receipt
    body = receipt.model_dump(mode="json")
    body["event_count"] += 1

    with pytest.raises(ValidationError, match="receipt digest mismatch"):
        PublicEventProjectionReceiptV1.model_validate(body)


def _events(
    *,
    cwd: str = "/Users/researcher/private-worktree/chemsmart",
    request_text: str = "inspect the frozen evidence",
) -> tuple[RuntimeEvent, RuntimeEvent]:
    first = RuntimeEvent.create(
        sequence=1,
        session_id="session-1",
        turn_id="bootstrap",
        kind=EventKind.SESSION_STARTED,
        payload={"cwd": cwd, "workspace_role": "development"},
        previous_hash="",
        idempotency_key="session-start",
    )
    second = RuntimeEvent.create(
        sequence=2,
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.TURN_STARTED,
        payload={"request": request_text, "phase": "route"},
        previous_hash=first.event_hash,
        idempotency_key="turn-start",
    )
    return first, second


def _parse_jsonl(value: bytes) -> tuple[RuntimeEvent, ...]:
    return tuple(
        RuntimeEvent.model_validate_json(line)
        for line in value.decode("utf-8").splitlines()
        if line
    )


def _jsonl(events: tuple[RuntimeEvent, ...]) -> bytes:
    return b"".join(
        event.model_dump_json().encode("utf-8") + b"\n" for event in events
    )


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
