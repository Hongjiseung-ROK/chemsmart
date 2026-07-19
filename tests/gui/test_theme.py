"""Accessibility contracts for the provisional desktop color tokens."""

from __future__ import annotations

from chemsmart.gui import theme


def _relative_luminance(hex_color: str) -> float:
    values = [
        int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)
    ]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
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


def test_stylesheet_exposes_two_pixel_keyboard_focus_indicators() -> None:
    qss = theme.stylesheet("light")

    assert "QPushButton:focus" in qss
    assert "QCheckBox:focus" in qss
    assert "QAbstractSpinBox:focus" in qss
    assert "QAbstractItemView:focus" in qss
    assert "QPushButton#Primary:focus" in qss
    assert "border: 2px solid #185fa5" in qss


def test_primary_action_has_a_visible_keyboard_focus_ring(qapp) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    window = QWidget()
    layout = QVBoxLayout(window)
    primary = QPushButton("Compute", objectName="Primary")
    alternate = QPushButton("Alternate")
    layout.addWidget(primary)
    layout.addWidget(alternate)
    window.setStyleSheet(theme.stylesheet("light"))
    window.show()

    def render_button() -> QImage:
        return primary.grab().toImage()

    try:
        alternate.setFocus(Qt.FocusReason.TabFocusReason)
        qapp.processEvents()
        unfocused = render_button()
        primary.setFocus(Qt.FocusReason.TabFocusReason)
        qapp.processEvents()
        focused = render_button()

        assert primary.hasFocus()
        assert focused != unfocused
        assert (
            focused.pixelColor(primary.width() // 2, 1).name()
            == theme.LIGHT.accent_text
        )
    finally:
        window.close()


def test_explicit_appearance_styles_scroll_content_consistently() -> None:
    light = theme.stylesheet("light")
    dark = theme.stylesheet("dark")

    assert "QWidget#ScrollContent, QScrollArea" in light
    assert f"background: {theme.LIGHT.surface_0}" in light
    assert f"background: {theme.DARK.surface_0}" in dark


def test_agent_voice_uses_an_installed_serif_or_generic_fallback(qapp) -> None:
    from PySide6.QtGui import QFontDatabase

    family = theme.serif_font_family().strip("'")
    assert family == "serif" or family in QFontDatabase.families()


def test_system_high_contrast_palette_is_preserved_in_stylesheet(qapp) -> None:
    from PySide6.QtGui import QColor, QPalette

    original = qapp.palette()
    palette = QPalette(original)
    roles = {
        QPalette.ColorRole.Window: "#000000",
        QPalette.ColorRole.AlternateBase: "#101010",
        QPalette.ColorRole.Base: "#000000",
        QPalette.ColorRole.WindowText: "#ffffff",
        QPalette.ColorRole.Text: "#ffffff",
        QPalette.ColorRole.PlaceholderText: "#ffffff",
        QPalette.ColorRole.Midlight: "#ffffff",
        QPalette.ColorRole.Mid: "#ffffff",
        QPalette.ColorRole.Highlight: "#ffff00",
        QPalette.ColorRole.HighlightedText: "#000000",
    }
    try:
        for role, colour in roles.items():
            palette.setColor(role, QColor(colour))
        qapp.setPalette(palette)
        qss = theme.stylesheet()

        assert "background: #000000" in qss
        assert "color: #ffffff" in qss
        assert "border: 2px solid #ffff00" in qss
    finally:
        qapp.setPalette(original)
