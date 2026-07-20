"""Motion constants and reduced-motion policy (master plan section 5.4).

Motion communicates causality only — drawer expansion, task insertion,
progress, selected-context transitions. One easing family, 120-180 ms, no
decorative loops. Reduced-motion mode removes nonessential transitions and
never removes status.
"""

from __future__ import annotations

import subprocess
import sys

DURATION_FAST_MS = 120
DURATION_STANDARD_MS = 160
DURATION_SLOW_MS = 180

# Explicit app-level override (e.g. a future Accessibility preference).
# None means "follow the platform"; True/False wins over detection.
_reduced_motion_override: bool | None = None
_platform_reduce_motion_cache: bool | None = None


def easing_curve():
    """The single approved easing family."""
    from PySide6.QtCore import QEasingCurve

    return QEasingCurve(QEasingCurve.Type.OutCubic)


def set_reduced_motion_override(value: bool | None) -> None:
    """Force reduced motion on/off, or ``None`` to follow the platform."""
    global _reduced_motion_override
    _reduced_motion_override = value


def _platform_reduce_motion() -> bool:
    """Read the macOS "Reduce Motion" accessibility setting (cached).

    Qt does not surface this setting, so on macOS it is read once from the
    user defaults domain the system writes. Any failure (non-macOS, key
    unset, tool missing) reports False — callers still must never encode
    information in motion alone.
    """
    global _platform_reduce_motion_cache
    if _platform_reduce_motion_cache is not None:
        return _platform_reduce_motion_cache
    detected = False
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                [
                    "/usr/bin/defaults",
                    "read",
                    "com.apple.universalaccess",
                    "reduceMotion",
                ],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            detected = result.stdout.strip() == "1"
        except Exception:
            detected = False
    _platform_reduce_motion_cache = detected
    return detected


def reduce_motion() -> bool:
    """True when motion should be minimized.

    The explicit override wins; otherwise the platform setting is used.
    Reduced-motion mode removes nonessential transitions and never removes
    status: callers must apply final states directly when this returns True.
    """
    if _reduced_motion_override is not None:
        return _reduced_motion_override
    return _platform_reduce_motion()


def effective_duration_ms(requested_ms: int) -> int:
    """Duration to actually animate with: 0 under reduced motion."""
    return 0 if reduce_motion() else requested_ms
