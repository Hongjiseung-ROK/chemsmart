"""Main window: sidebar + stacked screens (tool-first IA).

Layout follows the approved information architecture (principle #5): Job
builder is the home surface; Chat, Database, and Analysis are equal sidebar
peers, grouped into ``Build`` and ``Explore`` sections (HIG grouping +
progressive disclosure).

Screens are constructed lazily on first navigation so importing/opening the
window stays cheap and heavy scientific deps (rdkit/pymatgen) are only pulled
in when a screen that needs them is first shown — the GUI counterpart of the
CLI's ``DeferredGroup`` discipline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from chemsmart.gui import theme


@dataclass(frozen=True)
class NavEntry:
    """One sidebar item and the factory that builds its screen on demand."""

    key: str
    label: str
    group: str  # "Build" or "Explore"
    factory: Callable[["MainWindow"], QWidget]


class MainWindow(QMainWindow):
    """Top-level window hosting the sidebar and the screen stack."""

    def __init__(self, session_root: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("ChemSmart")
        self.resize(1040, 680)
        self.session_root = session_root

        self._screens: dict[str, QWidget] = {}
        self._nav_buttons: dict[str, QPushButton] = {}

        root = QWidget(objectName="Root")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        sidebar = self._build_sidebar()
        layout.addWidget(sidebar)
        layout.addWidget(self.stack, stretch=1)
        self.setCentralWidget(root)

        self.setStyleSheet(theme.stylesheet())
        # Job builder is home (principle #5).
        self.navigate("job_builder")

    # -- navigation ----------------------------------------------------- #

    def _entries(self) -> list[NavEntry]:
        # Imports are deferred to the factories so unopened screens never
        # import their heavy dependencies.
        return [
            NavEntry("job_builder", "Job builder", "Build", _make_job_builder),
            NavEntry("chat", "Chat", "Build", _make_chat),
            NavEntry("database", "Database", "Explore", _make_database),
            NavEntry("analysis", "Analysis", "Explore", _make_analysis),
        ]

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget(objectName="Sidebar")
        sidebar.setFixedWidth(176)
        col = QVBoxLayout(sidebar)
        col.setContentsMargins(8, 12, 8, 12)
        col.setSpacing(1)

        group = QButtonGroup(self)
        group.setExclusive(True)

        current_group = None
        for entry in self._entries():
            if entry.group != current_group:
                current_group = entry.group
                col.addWidget(QLabel(entry.group, objectName="SidebarGroup"))
            button = QPushButton(entry.label, objectName="NavItem")
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, key=entry.key: self.navigate(key)
            )
            group.addButton(button)
            col.addWidget(button)
            self._nav_buttons[entry.key] = button

        col.addStretch(1)
        settings = QPushButton("Settings", objectName="NavItem")
        settings.setCheckable(True)
        settings.clicked.connect(
            lambda _checked=False: self.navigate("settings")
        )
        group.addButton(settings)
        col.addWidget(settings)
        self._nav_buttons["settings"] = settings
        return sidebar

    def navigate(self, key: str) -> None:
        """Show the screen for ``key``, building it on first access."""
        widget = self._screens.get(key)
        if widget is None:
            widget = self._build_screen(key)
            self._screens[key] = widget
            self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)
        button = self._nav_buttons.get(key)
        if button is not None:
            button.setChecked(True)

    def _build_screen(self, key: str) -> QWidget:
        if key == "settings":
            return _make_settings(self)
        for entry in self._entries():
            if entry.key == key:
                return entry.factory(self)
        placeholder = QWidget(objectName="Screen")
        QVBoxLayout(placeholder).addWidget(QLabel(f"Unknown screen: {key}"))
        return placeholder


# -- screen factories (import inside to keep navigation lazy) ------------- #


def _make_job_builder(window: MainWindow) -> QWidget:
    from chemsmart.gui.screens.job_builder import JobBuilderScreen

    return JobBuilderScreen(window)


def _make_chat(window: MainWindow) -> QWidget:
    from chemsmart.gui.screens.chat import ChatScreen

    return ChatScreen(window)


def _make_database(window: MainWindow) -> QWidget:
    from chemsmart.gui.screens.unavailable import UnavailableFeatureScreen

    return UnavailableFeatureScreen(
        "Database",
        "P5",
        "Database browsing is not available in this build yet. Existing "
        "database commands remain available in the ChemSmart CLI.",
        window,
    )


def _make_analysis(window: MainWindow) -> QWidget:
    from chemsmart.gui.screens.unavailable import UnavailableFeatureScreen

    return UnavailableFeatureScreen(
        "Analysis",
        "P5",
        "Grouper and thermochemistry tools are not available in this build "
        "yet. Their existing CLI workflows are unchanged.",
        window,
    )


def _make_settings(window: MainWindow) -> QWidget:
    from chemsmart.gui.screens.unavailable import UnavailableFeatureScreen

    return UnavailableFeatureScreen(
        "Settings",
        "P2",
        "Desktop provider and workspace settings are not available in this "
        "build yet. The Job builder remains usable without an AI provider.",
        window,
    )
