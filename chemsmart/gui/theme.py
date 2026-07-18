"""Design tokens and QSS stylesheet for the ChemSmart GUI.

Encodes the approved design north star — CDS restraint + Codex density — as a
small set of semantic tokens with light/dark variants, rendered into a Qt
stylesheet. Screens must reference these tokens (via the generated QSS object
names / classes) rather than hard-coding colors, so both appearance modes and
the density split stay consistent.

Principles implemented here:
- One accent, semantic tokens only, no gradients/shadows (principle #1).
- Density adapts to surface: ``comfortable`` vs ``compact`` metrics
  (principle #2). Screens opt into a density by setting the ``density``
  dynamic property on their root widget.
- Monospace is the surface of fact — commands/coordinates/energies use the
  ``mono`` object name / ``QFont`` from :func:`mono_font` (principles #3, #9).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """Semantic color tokens for a single appearance mode.

    Values are close to the CDS ramp stops but expressed as literal hex here
    because Qt has no dynamic token layer; :func:`stylesheet` is the single
    place that maps tokens to widgets.
    """

    surface_0: str  # page canvas
    surface_1: str  # in-flow card / sidebar
    surface_2: str  # panel / input background
    text_primary: str
    text_secondary: str
    text_muted: str
    border: str
    border_strong: str
    accent: str  # user primary actions only (principle #4)
    accent_text: str  # text/icon on an accent fill
    accent_bg: str  # quiet accent tint (selection, AI marker)
    success: str
    warning: str
    danger: str


LIGHT = Palette(
    surface_0="#f7f6f2",
    surface_1="#f1efe8",
    surface_2="#ffffff",
    text_primary="#2c2c2a",
    text_secondary="#5f5e5a",
    text_muted="#686761",
    border="#e2e0d8",
    border_strong="#c9c7bd",
    accent="#185fa5",
    accent_text="#ffffff",
    accent_bg="#e6f1fb",
    success="#3b6d11",
    warning="#854f0b",
    danger="#a32d2d",
)

DARK = Palette(
    surface_0="#1c1c1a",
    surface_1="#242422",
    surface_2="#2f2f2c",
    text_primary="#f1efe8",
    text_secondary="#b4b2a9",
    text_muted="#9c9b94",
    border="#3a3a37",
    border_strong="#4a4a46",
    accent="#378add",
    accent_text="#04182c",
    accent_bg="#0c2c47",
    success="#97c459",
    warning="#ef9f27",
    danger="#e24b4a",
)


# Density metrics: (control height, base font pt, dense font pt, pad px).
_DENSITY = {
    "comfortable": {"control": 34, "font": 13, "pad": 12, "radius": 8},
    "compact": {"control": 28, "font": 12, "pad": 8, "radius": 6},
}


def mono_font_family() -> str:
    """Preferred monospace family for commands/coordinates/energies."""
    return "SF Mono, Menlo, Monaco, Consolas, monospace"


def sans_font_family() -> str:
    """System sans family (SF Pro on macOS via the platform default)."""
    return "-apple-system, 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif"


def serif_font_family() -> str:
    """Serif family reserved for the agent's voice (principle #3)."""
    return "'New York', Georgia, 'Times New Roman', serif"


def is_dark_mode() -> bool:
    """Best-effort detection of the system appearance via Qt style hints.

    Falls back to light when the running Qt is older than 6.5 (no
    ``colorScheme``) or no ``QGuiApplication`` exists yet.
    """
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
        mode = "dark" if is_dark_mode() else "light"
    return DARK if mode == "dark" else LIGHT


def stylesheet(mode: str | None = None) -> str:
    """Build the application QSS for the given appearance mode.

    Widgets select their look through object names and the ``density`` dynamic
    property. Keeping every color in this one function is the Qt equivalent of
    CDS's "reference tokens, never raw hex" rule.
    """
    p = palette_for(mode)
    comfortable = _DENSITY["comfortable"]
    compact = _DENSITY["compact"]
    sans = sans_font_family()
    mono = mono_font_family()

    return f"""
    * {{
        font-family: {sans};
        font-size: {comfortable['font']}px;
        color: {p.text_primary};
    }}
    QWidget#Root {{ background: {p.surface_0}; }}

    /* Sidebar (principle #5 tool-first nav) */
    QWidget#Sidebar {{
        background: {p.surface_1};
        border-right: 1px solid {p.border};
    }}
    QLabel#SidebarGroup {{
        color: {p.text_muted};
        font-size: 10px;
        text-transform: uppercase;
        padding: 10px 12px 4px 12px;
    }}
    QPushButton#NavItem {{
        text-align: left;
        border: none;
        background: transparent;
        color: {p.text_secondary};
        padding: 7px 10px;
        border-radius: {comfortable['radius']}px;
    }}
    QPushButton#NavItem:hover {{ background: {p.surface_2}; }}
    QPushButton#NavItem:checked {{
        background: {p.accent};
        color: {p.accent_text};
    }}

    /* Content panels */
    QWidget#Screen {{ background: {p.surface_0}; }}
    QLabel#ScreenTitle {{ font-size: 15px; font-weight: 500; }}
    QLabel#ScreenSubtitle {{ color: {p.text_muted}; font-size: 11px; }}
    QLabel#FieldLabel {{ color: {p.text_secondary}; font-size: 11px; }}

    /* Inputs — compact + monospace on the dense/data surfaces */
    QLineEdit, QComboBox, QPlainTextEdit, QTextEdit {{
        background: {p.surface_2};
        border: 1px solid {p.border};
        border-radius: {compact['radius']}px;
        padding: 4px 8px;
        selection-background-color: {p.accent_bg};
    }}
    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
        border: 1px solid {p.accent};
    }}
    *[density="compact"] QLineEdit,
    *[density="compact"] QComboBox {{
        font-family: {mono};
        min-height: {compact['control']}px;
    }}
    QPlainTextEdit#Preview, QPlainTextEdit#MonoOutput {{
        font-family: {mono};
        font-size: {compact['font']}px;
        color: {p.text_secondary};
        background: {p.surface_1};
    }}

    /* Buttons — one accent primary per view (principle #4) */
    QPushButton {{
        background: {p.surface_2};
        border: 1px solid {p.border_strong};
        border-radius: {compact['radius']}px;
        padding: 5px 12px;
    }}
    QPushButton:hover {{ background: {p.surface_1}; }}
    QPushButton#Primary {{
        background: {p.accent};
        color: {p.accent_text};
        border: none;
    }}
    QPushButton#Primary:disabled {{
        background: {p.surface_1};
        color: {p.text_muted};
        border: 1px solid {p.border};
    }}

    /* Agent voice: serif, quiet accent left border (principles #3, #4) */
    QLabel#AgentText, QTextEdit#AgentText {{
        font-family: {serif_font_family()};
        color: {p.text_secondary};
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
    """
