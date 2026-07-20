"""Contrast and completeness gates for the P8.1 semantic tokens.

Text must reach 4.5:1 and non-text state/focus indicators 3:1 (master plan
section 11) in every appearance mode, including increased contrast. These
tests measure the same WCAG math the palettes were tuned against, so a token
edit that silently breaks readability fails here first.
"""

from __future__ import annotations

import pytest

from chemsmart.gui.design.tokens import (
    DARK,
    DARK_HIGH_CONTRAST,
    LIGHT,
    LIGHT_HIGH_CONTRAST,
    StateColor,
    Tokens,
    contrast_ratio,
    resolve_tokens,
    token_names,
)

ALL_PALETTES = {
    "light": LIGHT,
    "dark": DARK,
    "light-hc": LIGHT_HIGH_CONTRAST,
    "dark-hc": DARK_HIGH_CONTRAST,
}

TEXT_MINIMUM = 4.5
NON_TEXT_MINIMUM = 3.0

READING_SURFACES = ("canvas", "sidebar", "panel", "elevated")
TEXT_ROLES = ("text_primary", "text_secondary", "text_tertiary")
STATE_ROLES = ("info", "verified", "warning", "blocked", "danger")


@pytest.mark.parametrize("mode", sorted(ALL_PALETTES))
@pytest.mark.parametrize("surface", READING_SURFACES)
@pytest.mark.parametrize("text_role", TEXT_ROLES)
def test_interface_text_contrast(mode, surface, text_role) -> None:
    tokens = ALL_PALETTES[mode]
    ratio = contrast_ratio(
        getattr(tokens, text_role), getattr(tokens, surface)
    )
    assert (
        ratio >= TEXT_MINIMUM
    ), f"{mode}: {text_role} on {surface} is {ratio:.2f}:1"


@pytest.mark.parametrize("mode", sorted(ALL_PALETTES))
@pytest.mark.parametrize("state_role", STATE_ROLES)
def test_state_text_on_its_tint(mode, state_role) -> None:
    """State foregrounds are used as text over their paired tint."""
    tokens = ALL_PALETTES[mode]
    state: StateColor = getattr(tokens, state_role)
    ratio = contrast_ratio(state.fg, state.bg)
    assert (
        ratio >= TEXT_MINIMUM
    ), f"{mode}: {state_role} fg on its tint is {ratio:.2f}:1"


@pytest.mark.parametrize("mode", sorted(ALL_PALETTES))
@pytest.mark.parametrize("state_role", STATE_ROLES)
@pytest.mark.parametrize("surface", ("canvas", "panel"))
def test_state_indicator_on_plain_surfaces(mode, state_role, surface) -> None:
    """State icons must stay identifiable on ordinary surfaces (non-text)."""
    tokens = ALL_PALETTES[mode]
    state: StateColor = getattr(tokens, state_role)
    ratio = contrast_ratio(state.fg, getattr(tokens, surface))
    assert (
        ratio >= NON_TEXT_MINIMUM
    ), f"{mode}: {state_role} icon on {surface} is {ratio:.2f}:1"


@pytest.mark.parametrize("mode", sorted(ALL_PALETTES))
def test_accent_and_focus_contrast(mode) -> None:
    tokens = ALL_PALETTES[mode]
    assert contrast_ratio(tokens.accent_on_fill, tokens.accent) >= TEXT_MINIMUM
    for surface in READING_SURFACES:
        ratio = contrast_ratio(tokens.focus_ring, getattr(tokens, surface))
        assert (
            ratio >= NON_TEXT_MINIMUM
        ), f"{mode}: focus ring on {surface} is {ratio:.2f}:1"
    assert (
        contrast_ratio(tokens.accent, tokens.canvas) >= NON_TEXT_MINIMUM
    ), f"{mode}: accent fill is not identifiable on the canvas"


@pytest.mark.parametrize("mode", sorted(ALL_PALETTES))
def test_code_surface_keeps_primary_text_readable(mode) -> None:
    tokens = ALL_PALETTES[mode]
    assert (
        contrast_ratio(tokens.text_primary, tokens.code_surface)
        >= TEXT_MINIMUM
    )


def test_increased_contrast_never_weaker_than_default() -> None:
    for default, stronger in (
        (LIGHT, LIGHT_HIGH_CONTRAST),
        (DARK, DARK_HIGH_CONTRAST),
    ):
        for text_role in TEXT_ROLES:
            base = contrast_ratio(getattr(default, text_role), default.canvas)
            raised = contrast_ratio(
                getattr(stronger, text_role), stronger.canvas
            )
            assert raised >= base, (
                f"increased contrast weakened {text_role}: "
                f"{raised:.2f} < {base:.2f}"
            )


def test_resolver_rejects_unknown_modes() -> None:
    with pytest.raises(ValueError):
        resolve_tokens("sepia")


def test_resolver_returns_each_variant() -> None:
    assert resolve_tokens("light") is LIGHT
    assert resolve_tokens("dark") is DARK
    assert resolve_tokens("light", increased_contrast=True) is (
        LIGHT_HIGH_CONTRAST
    )
    assert resolve_tokens("dark", increased_contrast=True) is (
        DARK_HIGH_CONTRAST
    )


def test_token_vocabulary_is_complete() -> None:
    names = token_names()
    for required in (
        "canvas",
        "sidebar",
        "panel",
        "elevated",
        "selected",
        "separator",
        "text_primary",
        "text_secondary",
        "text_tertiary",
        "text_disabled",
        "accent",
        "accent_on_fill",
        "info",
        "verified",
        "warning",
        "blocked",
        "danger",
        "focus_ring",
        "selection",
        "code_surface",
        "chart_grid",
        "molecule_viewport",
    ):
        assert required in names
    for palette in ALL_PALETTES.values():
        assert isinstance(palette, Tokens)
        for state_role in STATE_ROLES:
            assert isinstance(getattr(palette, state_role), StateColor)


def test_contrast_math_reference_values() -> None:
    """Anchor the WCAG implementation to known reference ratios."""
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0)
    assert contrast_ratio("#777777", "#ffffff") == pytest.approx(
        4.48, abs=0.01
    )
