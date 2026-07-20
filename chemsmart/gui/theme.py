"""Application stylesheet generated from the P8 semantic design tokens.

Since P8.2 this module is a consumer of :mod:`chemsmart.gui.design.tokens` —
the single source of color truth for the workbench. The legacy ``Palette``
shape is kept as a thin mapping so existing screens and tests keep one
stable surface, but every value now derives from the token sets that the
P8.1 contrast matrix verifies.

The serif "agent voice" is retired (user decision 2026-07-19): all interface
and agent text uses the system sans family; agent identity is conveyed by
labels, cell structure, and provenance. System monospace remains reserved
for facts — commands, coordinates, energies, receipts.
"""

from __future__ import annotations

from dataclasses import dataclass

from chemsmart.gui.design.tokens import DARK as _DARK_TOKENS
from chemsmart.gui.design.tokens import LIGHT as _LIGHT_TOKENS
from chemsmart.gui.design.tokens import Tokens


@dataclass(frozen=True)
class Palette:
    """Legacy semantic color surface consumed by pre-P8.2 screens."""

    surface_0: str  # page canvas
    surface_1: str  # in-flow card / sidebar
    surface_2: str  # panel / input background
    text_primary: str
    text_secondary: str
    text_muted: str
    border: str
    border_strong: str
    accent: str  # user primary actions only
    accent_text: str  # text/icon on an accent fill
    accent_bg: str  # quiet accent tint (selection)
    success: str
    warning: str
    danger: str


def _palette_from_tokens(tokens: Tokens) -> Palette:
    return Palette(
        surface_0=tokens.canvas,
        surface_1=tokens.sidebar,
        surface_2=tokens.panel,
        text_primary=tokens.text_primary,
        text_secondary=tokens.text_secondary,
        text_muted=tokens.text_tertiary,
        border=tokens.chart_grid,
        border_strong=tokens.separator,
        accent=tokens.accent,
        accent_text=tokens.accent_on_fill,
        accent_bg=tokens.selection,
        success=tokens.verified.fg,
        warning=tokens.warning.fg,
        danger=tokens.danger.fg,
    )


LIGHT = _palette_from_tokens(_LIGHT_TOKENS)
DARK = _palette_from_tokens(_DARK_TOKENS)


# Density metrics: (control height, base font pt, pad px, radius px).
_DENSITY = {
    "comfortable": {"control": 34, "font": 13, "pad": 12, "radius": 8},
    "compact": {"control": 28, "font": 12, "pad": 8, "radius": 6},
}


def mono_font_family() -> str:
    """Preferred monospace family for commands/coordinates/energies."""
    try:
        from PySide6.QtGui import QFontDatabase, QGuiApplication

        if QGuiApplication.instance() is not None:
            family = QFontDatabase.systemFont(
                QFontDatabase.SystemFont.FixedFont
            ).family()
            if family:
                return f"'{family}'"
    except Exception:
        pass
    return "SF Mono, Menlo, Monaco, Consolas, monospace"


def sans_font_family() -> str:
    """System sans family (SF Pro on macOS via the platform default)."""
    try:
        from PySide6.QtGui import QFontDatabase, QGuiApplication

        if QGuiApplication.instance() is not None:
            family = QFontDatabase.systemFont(
                QFontDatabase.SystemFont.GeneralFont
            ).family()
            if family:
                return f"'{family}'"
    except Exception:
        pass
    return "-apple-system, 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif"


def serif_font_family() -> str:
    """Deprecated: the serif agent voice is retired (P8.2).

    Kept only so external callers keep resolving a valid family; nothing in
    the shipped stylesheet uses it anymore.
    """
    try:
        from PySide6.QtGui import QFontDatabase, QGuiApplication

        if QGuiApplication.instance() is not None:
            available = set(QFontDatabase.families())
            for family in ("New York", "Georgia", "Times New Roman"):
                if family in available:
                    return f"'{family}'"
    except Exception:
        pass
    return "serif"


def system_font_point_size() -> int:
    """Return the user's current Qt system UI point size."""
    try:
        from PySide6.QtGui import QFontDatabase, QGuiApplication

        if QGuiApplication.instance() is not None:
            size = QFontDatabase.systemFont(
                QFontDatabase.SystemFont.GeneralFont
            ).pointSizeF()
            if size > 0:
                return max(9, round(size))
    except Exception:
        pass
    return _DENSITY["comfortable"]["font"]


def is_dark_mode() -> bool:
    """Best-effort detection of the system appearance via Qt style hints."""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        if app is None:
            return False
        hints = app.styleHints()
        scheme = getattr(hints, "colorScheme", None)
        if scheme is None:
            return False
        return scheme() == Qt.ColorScheme.Dark
    except Exception:
        return False


def palette_for(mode: str | None = None) -> Palette:
    """Return the palette for ``mode`` ("light"/"dark"), auto-detecting None."""
    if mode is None:
        system = _system_palette()
        if system is not None:
            return system
        mode = "dark" if is_dark_mode() else "light"
    return DARK if mode == "dark" else LIGHT


def _system_palette() -> Palette | None:
    """Map current QPalette semantic roles into ChemSmart surface tokens.

    This keeps system increased-contrast palettes authoritative: when the OS
    supplies extreme colors, the stylesheet renders them instead of the fixed
    token sets.
    """
    try:
        from PySide6.QtGui import QGuiApplication, QPalette

        application = QGuiApplication.instance()
        if application is None:
            return None
        palette = application.palette()

        def color(role: QPalette.ColorRole) -> str:
            return palette.color(role).name()

        fallback = DARK if is_dark_mode() else LIGHT
        return Palette(
            surface_0=color(QPalette.ColorRole.Window),
            surface_1=color(QPalette.ColorRole.AlternateBase),
            surface_2=color(QPalette.ColorRole.Base),
            text_primary=color(QPalette.ColorRole.WindowText),
            text_secondary=color(QPalette.ColorRole.Text),
            text_muted=color(QPalette.ColorRole.PlaceholderText),
            border=color(QPalette.ColorRole.Midlight),
            border_strong=color(QPalette.ColorRole.Mid),
            accent=color(QPalette.ColorRole.Highlight),
            accent_text=color(QPalette.ColorRole.HighlightedText),
            accent_bg=color(QPalette.ColorRole.AlternateBase),
            success=fallback.success,
            warning=fallback.warning,
            danger=fallback.danger,
        )
    except Exception:
        return None


def stylesheet(mode: str | None = None) -> str:
    """Build the application QSS for the given appearance mode.

    Widgets select their look through object names and the ``density``
    dynamic property. Keeping every color in this one function is the Qt
    equivalent of the "reference tokens, never raw hex" rule.
    """
    p = palette_for(mode)
    system_size = system_font_point_size()
    comfortable = {**_DENSITY["comfortable"], "font": system_size}
    compact = {
        **_DENSITY["compact"],
        "font": max(9, system_size - 1),
    }
    sans = sans_font_family()
    mono = mono_font_family()

    return f"""
    * {{
        font-family: {sans};
        font-size: {comfortable['font']}pt;
        color: {p.text_primary};
    }}
    QWidget#Root {{ background: {p.surface_0}; }}

    /* Activity rail: icon-over-label navigation (P8.2 workbench) */
    QWidget#Sidebar {{
        background: {p.surface_1};
        border-right: 1px solid {p.border};
    }}
    QWidget#Inspector {{
        background: {p.surface_1};
        border-left: 1px solid {p.border};
    }}
    QLabel#SidebarGroup {{
        color: {p.text_muted};
        font-size: {max(9, system_size - 4)}pt;
        font-weight: 600;
        padding: 10px 0 2px 0;
        qproperty-alignment: AlignHCenter;
    }}
    QToolButton#NavItem {{
        border: none;
        background: transparent;
        color: {p.text_secondary};
        padding: 6px 2px;
        border-radius: {comfortable['radius']}px;
        font-size: {max(9, system_size - 3)}pt;
    }}
    QToolButton#NavItem:hover {{ background: {p.surface_2}; }}
    QToolButton#NavItem:checked {{
        background: {p.accent_bg};
        color: {p.text_primary};
        font-weight: 600;
    }}
    QToolButton#NavItem:focus {{
        border: 2px solid {p.accent};
        padding: 4px 0;
    }}

    /* Content panels */
    QWidget#Screen {{ background: {p.surface_0}; }}
    QWidget#ScrollContent, QScrollArea {{
        background: {p.surface_0};
    }}
    QLabel#ScreenTitle {{ font-size: {system_size + 2}pt; font-weight: 600; }}
    QLabel#ScreenSubtitle {{ color: {p.text_muted}; font-size: {max(9, system_size - 2)}pt; }}
    QLabel#FieldLabel {{ color: {p.text_secondary}; font-size: {max(9, system_size - 2)}pt; }}
    QLabel#EvidenceSummary {{
        color: {p.text_secondary};
        font-family: {mono};
        font-size: {max(9, system_size - 2)}pt;
        background: {p.surface_2};
        border: 1px solid {p.border};
        border-radius: {compact['radius']}px;
        padding: 6px;
    }}

    /* Inputs — compact + monospace on the dense/data surfaces */
    QLineEdit, QComboBox, QPlainTextEdit, QTextEdit {{
        background: {p.surface_2};
        border: 1px solid {p.border};
        border-radius: {compact['radius']}px;
        padding: 4px 8px;
        selection-background-color: {p.accent_bg};
    }}
    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus,
    QAbstractSpinBox:focus, QAbstractItemView:focus {{
        border: 2px solid {p.accent};
    }}
    *[density="compact"] QLineEdit,
    *[density="compact"] QComboBox {{
        font-family: {mono};
        min-height: {compact['control']}px;
    }}
    QPlainTextEdit#Preview, QPlainTextEdit#MonoOutput {{
        font-family: {mono};
        font-size: {compact['font']}pt;
        color: {p.text_secondary};
        background: {p.surface_1};
    }}

    /* Buttons — one accent primary per view */
    QPushButton {{
        background: {p.surface_2};
        border: 1px solid {p.border_strong};
        border-radius: {compact['radius']}px;
        padding: 5px 12px;
        min-height: {compact['control']}px;
    }}
    QPushButton:hover {{ background: {p.surface_1}; }}
    QPushButton:focus {{
        border: 2px solid {p.accent};
        padding: 4px 11px;
    }}
    QPushButton:disabled {{
        background: {p.surface_1};
        color: {p.border_strong};
        border: 1px solid {p.border};
    }}
    QPushButton#Primary {{
        background: {p.accent};
        color: {p.accent_text};
        border: none;
        font-weight: 600;
    }}
    QPushButton#Primary:focus {{
        border: 2px solid {p.accent_text};
        padding: 3px 10px;
    }}
    QPushButton#Primary:disabled {{
        background: {p.surface_1};
        color: {p.border_strong};
        border: 1px solid {p.border};
    }}
    QCheckBox:focus {{
        border: 2px solid {p.accent};
        border-radius: {compact['radius']}px;
    }}
    QTabBar::tab:focus {{
        border-bottom: 2px solid {p.accent};
    }}

    /* Agent text: sans like everything else; identity comes from the quiet
       accent border and labels, never a different typeface. */
    QLabel#AgentText, QTextEdit#AgentText {{
        color: {p.text_primary};
        border-left: 2px solid {p.accent};
        padding-left: 10px;
    }}

    QTableView, QTableWidget {{
        background: {p.surface_2};
        gridline-color: {p.border};
        border: 1px solid {p.border};
        border-radius: {compact['radius']}px;
    }}
    QHeaderView::section {{
        background: {p.surface_1};
        color: {p.text_muted};
        border: none;
        border-bottom: 1px solid {p.border};
        padding: 4px 8px;
    }}
    QStatusBar {{
        background: {p.surface_1};
        border-top: 1px solid {p.border};
    }}
    QStatusBar QLabel {{
        color: {p.text_secondary};
        font-size: {compact['font']}pt;
        padding: 0 6px;
    }}
    QProgressBar {{
        min-height: 6px;
        max-height: 6px;
        border: none;
        background: {p.surface_1};
        border-radius: 3px;
    }}
    QProgressBar::chunk {{ background: {p.accent}; border-radius: 3px; }}
    QSplitter::handle {{ background: {p.border}; width: 1px; }}
    """
