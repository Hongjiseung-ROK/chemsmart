"""Type scale for the modern workbench (master plan section 7.2).

One system sans family for all interface *and* agent text — the serif "agent
voice" is retired by user decision (2026-07-19); agent identity is conveyed by
label, role, and cell structure instead. System monospace is reserved for
facts: commands, coordinates, identifiers, energies, and receipts.

Font-family resolution is delegated to :mod:`chemsmart.gui.theme` so the
legacy stylesheet and the new primitives can never disagree about the resolved
system fonts.
"""

from __future__ import annotations

from dataclasses import dataclass

from chemsmart.gui.theme import (
    mono_font_family,
    sans_font_family,
    system_font_point_size,
)

# 4 pt spacing base with the approved steps (section 7.2).
SPACE_UNIT = 4
SPACING_STEPS = (4, 8, 12, 16, 24, 32)

# Control heights: compact data regions vs comfortable reading regions.
CONTROL_HEIGHT_COMPACT = 28
CONTROL_HEIGHT_COMFORTABLE = 32

# Compact metadata may never drop below this (contrast-verified floor).
MIN_POINT_SIZE = 11


@dataclass(frozen=True)
class TypeScale:
    """Point sizes for the semantic text roles, derived from the system size."""

    title: int
    section: int
    body: int
    label: int
    caption: int
    code: int


def type_scale() -> TypeScale:
    """Build the current scale from the live system UI point size.

    The macOS default resolves to body 13 pt, giving 16/14/13/12/11/12. Large
    system text shifts every role up with the same offsets, so the hierarchy
    survives accessibility text sizes.
    """
    body = max(MIN_POINT_SIZE + 2, system_font_point_size())
    return TypeScale(
        title=body + 3,
        section=body + 1,
        body=body,
        label=max(MIN_POINT_SIZE, body - 1),
        caption=max(MIN_POINT_SIZE, body - 2),
        code=max(MIN_POINT_SIZE, body - 1),
    )


def sans_family() -> str:
    """System sans family (quoted for QSS use)."""
    return sans_font_family()


def mono_family() -> str:
    """System monospace family (quoted for QSS use); facts only."""
    return mono_font_family()


def sans_qfont(point_size: int, *, weight_medium: bool = False):
    """A ``QFont`` for interface text; titles use weight, not a new face."""
    from PySide6.QtGui import QFont

    font = QFont()
    font.setPointSize(point_size)
    if weight_medium:
        font.setWeight(QFont.Weight.DemiBold)
    return font


def mono_qfont(point_size: int):
    """A ``QFont`` for scientific facts and commands."""
    from PySide6.QtGui import QFontDatabase

    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSize(point_size)
    return font
