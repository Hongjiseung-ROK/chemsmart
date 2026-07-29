"""Privacy boundary for provider-only reasoning metadata."""

from __future__ import annotations

from typing import Any

PRIVATE_REASONING_FIELDS = frozenset(
    {
        "reasoning_content",
        "thinking",
        "analysis",
        "<think>",
    }
)


def strip_private_reasoning_fields(value: Any) -> Any:
    """Return a recursive copy without provider-private reasoning fields.

    Active provider messages must keep these fields until their tool-call
    continuation completes. Call this function only when projecting that
    in-memory state into a session file, decision log, or training record.
    """

    if isinstance(value, dict):
        return {
            key: strip_private_reasoning_fields(item)
            for key, item in value.items()
            if key not in PRIVATE_REASONING_FIELDS
        }
    if isinstance(value, list):
        return [strip_private_reasoning_fields(item) for item in value]
    if isinstance(value, tuple):
        return tuple(strip_private_reasoning_fields(item) for item in value)
    return value


__all__ = [
    "PRIVATE_REASONING_FIELDS",
    "strip_private_reasoning_fields",
]
