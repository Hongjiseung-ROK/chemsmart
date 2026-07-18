"""Accessibility contracts for the provisional desktop color tokens."""

from __future__ import annotations

from chemsmart.gui import theme


def _relative_luminance(hex_color: str) -> float:
    values = [
        int(hex_color[index : index + 2], 16) / 255
        for index in (1, 3, 5)
    ]
    linear = [
        value / 12.92
        if value <= 0.04045
        else ((value + 0.055) / 1.055) ** 2.4
        for value in values
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_muted_small_text_meets_wcag_contrast_in_both_palettes() -> None:
    for palette in (theme.LIGHT, theme.DARK):
        for background in (palette.surface_0, palette.surface_1):
            assert _contrast_ratio(palette.text_muted, background) >= 4.5


def test_stylesheet_uses_current_system_font_size(monkeypatch) -> None:
    monkeypatch.setattr(theme, "system_font_point_size", lambda: 17)

    qss = theme.stylesheet("light")

    assert "font-size: 17pt" in qss
    assert "font-size: 19pt" in qss
