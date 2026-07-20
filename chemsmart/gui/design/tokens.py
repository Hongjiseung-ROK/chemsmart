"""Semantic color tokens for the modern workbench (master plan section 7.1).

Roles, not screen colors: every widget asks for a role such as ``panel`` or
``verified`` and never for a hex value. Fixed light/dark/increased-contrast
palettes exist so contrast is deterministic and testable; when a running
``QGuiApplication`` is present the *neutral* surface/text roles may be
re-derived from the system ``QPalette`` while the semantic state roles keep
their contrast-verified fixed values.

Every state role ships as a (foreground, tint background) pair so status is
never expressed by color alone on an unknown surface. The WCAG 2.1 contrast
math lives here so tests and tools measure the same numbers the palette was
tuned against.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class StateColor:
    """A semantic state rendered as text/icon over a quiet tint."""

    fg: str
    bg: str


@dataclass(frozen=True)
class Tokens:
    """Complete semantic palette for one appearance mode."""

    # Surfaces
    canvas: str
    sidebar: str
    panel: str
    elevated: str
    selected: str
    separator: str
    # Text
    text_primary: str
    text_secondary: str
    text_tertiary: str
    text_disabled: str
    # Accent
    accent: str
    accent_on_fill: str
    # Semantic states
    info: StateColor
    verified: StateColor
    warning: StateColor
    blocked: StateColor
    danger: StateColor
    # Special surfaces
    focus_ring: str
    selection: str
    code_surface: str
    chart_grid: str
    molecule_viewport: str


LIGHT = Tokens(
    canvas="#f5f5f4",
    sidebar="#ececea",
    panel="#ffffff",
    elevated="#ffffff",
    selected="#e2e6ea",
    separator="#c9c8c4",
    text_primary="#1f1f1e",
    text_secondary="#4b4a47",
    text_tertiary="#61605c",
    text_disabled="#9a9994",
    accent="#0f62c0",
    accent_on_fill="#ffffff",
    info=StateColor(fg="#0d5ab1", bg="#e3eefb"),
    verified=StateColor(fg="#1d6b34", bg="#e2f2e5"),
    warning=StateColor(fg="#7a5000", bg="#f7edd6"),
    blocked=StateColor(fg="#8f3f00", bg="#f9e8dc"),
    danger=StateColor(fg="#b3261e", bg="#f9e2e0"),
    focus_ring="#0f62c0",
    selection="#cfe3f8",
    code_surface="#eeedeb",
    chart_grid="#dad9d5",
    molecule_viewport="#ffffff",
)

DARK = Tokens(
    canvas="#1e1e1d",
    sidebar="#232322",
    panel="#2a2a29",
    elevated="#323231",
    selected="#39424c",
    separator="#4c4c49",
    text_primary="#f2f1ee",
    text_secondary="#c3c1bb",
    text_tertiary="#a3a19a",
    text_disabled="#75746e",
    accent="#5ba3f0",
    accent_on_fill="#0b1c30",
    info=StateColor(fg="#8cc0f7", bg="#16283c"),
    verified=StateColor(fg="#8ecf9b", bg="#18301e"),
    warning=StateColor(fg="#e4b34d", bg="#33280f"),
    blocked=StateColor(fg="#eda87a", bg="#362113"),
    danger=StateColor(fg="#f2938c", bg="#3a1c1a"),
    focus_ring="#5ba3f0",
    selection="#274b73",
    code_surface="#262625",
    chart_grid="#3c3c3a",
    molecule_viewport="#1a1a19",
)

# Increased-contrast variants keep every layout token but push text and
# structure toward the extremes; state tints collapse toward the base surface
# so the strengthened foregrounds stay readable.
LIGHT_HIGH_CONTRAST = Tokens(
    canvas="#ffffff",
    sidebar="#f2f2f1",
    panel="#ffffff",
    elevated="#ffffff",
    selected="#d5dde5",
    separator="#767572",
    text_primary="#000000",
    text_secondary="#262624",
    text_tertiary="#3c3b38",
    text_disabled="#6f6e69",
    accent="#0a4a94",
    accent_on_fill="#ffffff",
    info=StateColor(fg="#0a4a94", bg="#e3eefb"),
    verified=StateColor(fg="#14532d", bg="#e2f2e5"),
    warning=StateColor(fg="#5f3f00", bg="#f7edd6"),
    blocked=StateColor(fg="#6f3100", bg="#f9e8dc"),
    danger=StateColor(fg="#8f1d16", bg="#f9e2e0"),
    focus_ring="#0a4a94",
    selection="#bcd7f5",
    code_surface="#f2f2f1",
    chart_grid="#767572",
    molecule_viewport="#ffffff",
)

DARK_HIGH_CONTRAST = Tokens(
    canvas="#121211",
    sidebar="#181817",
    panel="#1c1c1b",
    elevated="#222221",
    selected="#3d4b5c",
    separator="#8a8985",
    text_primary="#ffffff",
    text_secondary="#e8e7e3",
    text_tertiary="#cfceca",
    text_disabled="#8f8e88",
    accent="#7fb8f5",
    accent_on_fill="#04101f",
    info=StateColor(fg="#a5cdf8", bg="#16283c"),
    verified=StateColor(fg="#a9dbb3", bg="#18301e"),
    warning=StateColor(fg="#edc470", bg="#33280f"),
    blocked=StateColor(fg="#f2bd97", bg="#362113"),
    danger=StateColor(fg="#f7ada7", bg="#3a1c1a"),
    focus_ring="#7fb8f5",
    selection="#2d5a8c",
    code_surface="#1a1a19",
    chart_grid="#8a8985",
    molecule_viewport="#121211",
)


_PALETTES = {
    ("light", False): LIGHT,
    ("dark", False): DARK,
    ("light", True): LIGHT_HIGH_CONTRAST,
    ("dark", True): DARK_HIGH_CONTRAST,
}


def resolve_tokens(
    mode: str | None = None, *, increased_contrast: bool = False
) -> Tokens:
    """Return the token set for ``mode`` ("light"/"dark"), detecting ``None``.

    Detection reuses :func:`chemsmart.gui.theme.is_dark_mode` so the design
    package and the legacy stylesheet always agree about the current
    appearance.
    """
    if mode is None:
        from chemsmart.gui.theme import is_dark_mode

        mode = "dark" if is_dark_mode() else "light"
    if mode not in ("light", "dark"):
        raise ValueError(f"unknown appearance mode: {mode!r}")
    return _PALETTES[(mode, increased_contrast)]


def token_names() -> list[str]:
    """All role names, for gallery/testing enumeration."""
    return [f.name for f in fields(Tokens)]


# --------------------------------------------------------------------------
# WCAG 2.1 contrast math (the numbers the palettes are tuned against)
# --------------------------------------------------------------------------


def _srgb_channel(value: int) -> float:
    c = value / 255.0
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance of a ``#rrggbb`` color."""
    color = hex_color.lstrip("#")
    if len(color) != 6:
        raise ValueError(f"expected #rrggbb, got {hex_color!r}")
    r, g, b = (int(color[i : i + 2], 16) for i in (0, 2, 4))
    return (
        0.2126 * _srgb_channel(r)
        + 0.7152 * _srgb_channel(g)
        + 0.0722 * _srgb_channel(b)
    )


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio between two ``#rrggbb`` colors (1.0 - 21.0)."""
    lighter = relative_luminance(foreground)
    darker = relative_luminance(background)
    if lighter < darker:
        lighter, darker = darker, lighter
    return (lighter + 0.05) / (darker + 0.05)
