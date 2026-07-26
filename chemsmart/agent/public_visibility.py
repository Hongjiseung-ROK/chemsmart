"""Sanitize model- and user-visible agent payloads."""

from __future__ import annotations

import re
from typing import Any

OPAQUE_PATH = "[opaque-path]"

_COMMON_POSIX_PATH = re.compile(
    r"(?<![A-Za-z0-9:+])"
    r"(?:file://)?/"
    r"(?:Users|home|private|var|tmp|opt|Library|Volumes|Applications|"
    r"System|usr|etc|dev|proc)"
    r"(?:/[^\s\"'<>`;,)\]}]+)+"
)
_COMMON_POSIX_ROOT = re.compile(
    r"(?<![A-Za-z0-9:+])"
    r"(?:file://)?/"
    r"(?:Users|home|private|var|tmp|opt|Library|Volumes|Applications|"
    r"System|usr|etc|dev|proc)"
    r"/?(?=$|[\s\"'<>`;,.!?:)\]}])"
)
_WINDOWS_PATH = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:file:///)?[A-Za-z]:[\\/]"
    r"(?:[^\\/\s\"'<>`;,)\]}]+[\\/])*"
    r"[^\\/\s\"'<>`;,)\]}]+"
)
_WHOLE_ABSOLUTE_PATH = re.compile(r"^(?:file://)?/(?:[^/\s]+/)+[^/\s]+/?$")


def sanitize_public_payload(value: Any) -> Any:
    """Remove absolute filesystem paths without changing trusted raw state."""

    if isinstance(value, str):
        return sanitize_public_text(value)
    if isinstance(value, dict):
        return {
            key: sanitize_public_payload(item) for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_public_payload(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_public_payload(item) for item in value]
    return value


def sanitize_public_text(value: str) -> str:
    """Replace absolute filesystem locations in public text."""

    stripped = value.strip()
    if _WHOLE_ABSOLUTE_PATH.fullmatch(stripped):
        return value.replace(stripped, OPAQUE_PATH)
    public = _COMMON_POSIX_PATH.sub(OPAQUE_PATH, value)
    public = _COMMON_POSIX_ROOT.sub(OPAQUE_PATH, public)
    return _WINDOWS_PATH.sub(OPAQUE_PATH, public)


__all__ = ["OPAQUE_PATH", "sanitize_public_payload", "sanitize_public_text"]
