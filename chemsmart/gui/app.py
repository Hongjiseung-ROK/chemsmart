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

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from chemsmart.gui import theme
from chemsmart.gui.application.runtime_projection import DesktopRuntimeProjection


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
        self.setMinimumSize(720, 520)
        self.resize(1040, 680)
        self.session_root = session_root
        self.workspace_root = Path.cwd().resolve()
        self._inspector_user_visible = True

        self._screens: dict[str, QWidget] = {}
        self._nav_buttons: dict[str, QPushButton] = {}

        root = QWidget(objectName="Root")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setAccessibleName("ChemSmart primary work surface")
        self.sidebar = self._build_sidebar()
        self.inspector = self._build_inspector()
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.stack)
        self.splitter.addWidget(self.inspector)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setCollapsible(2, True)
        self.splitter.setSizes([160, 620, 260])
        layout.addWidget(self.splitter)
        self.setCentralWidget(root)

        self._build_menus()
        self._build_status_bar()
        self._connect_system_appearance()
        self._apply_theme()
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
        sidebar.setMinimumWidth(144)
        sidebar.setMaximumWidth(220)
        sidebar.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )
        sidebar.setAccessibleName("Primary navigation")
        col = QVBoxLayout(sidebar)
        col.setContentsMargins(8, 12, 8, 12)
        col.setSpacing(1)

        group = QButtonGroup(self)
        group.setExclusive(True)
        self._nav_group = group

        current_group = None
        for entry in self._entries():
            if entry.group != current_group:
                current_group = entry.group
                col.addWidget(QLabel(entry.group, objectName="SidebarGroup"))
            button = QPushButton(entry.label, objectName="NavItem")
            button.setCheckable(True)
            button.setAccessibleName(f"Open {entry.label}")
            button.setAccessibleDescription(
                f"Shows the {entry.label} work surface."
            )
            button.clicked.connect(
                lambda _checked=False, key=entry.key: self.navigate(key)
            )
            group.addButton(button)
            col.addWidget(button)
            self._nav_buttons[entry.key] = button

        col.addStretch(1)
        return sidebar

    def _build_inspector(self) -> QWidget:
        inspector = QWidget(objectName="Inspector")
        inspector.setMinimumWidth(220)
        inspector.setMaximumWidth(340)
        inspector.setAccessibleName("Context inspector")
        col = QVBoxLayout(inspector)
        col.setContentsMargins(12, 14, 12, 14)
        inspector_title = QLabel(
            "Structure and evidence",
            objectName="ScreenTitle",
        )
        inspector_title.setWordWrap(True)
        col.addWidget(inspector_title)
        self.inspector_status = QLabel(
            "Structure, input validation, and provenance appear here as the "
            "active workflow produces them.",
            objectName="ScreenSubtitle",
        )
        self.inspector_status.setWordWrap(True)
        col.addWidget(self.inspector_status)
        self.runtime_evidence = QLabel(
            "No session receipts yet.",
            objectName="EvidenceSummary",
        )
        self.runtime_evidence.setWordWrap(True)
        self.runtime_evidence.setAccessibleName("Session and evidence status")
        col.addWidget(self.runtime_evidence)
        self._structure_viewer = None
        col.addStretch(1)
        return inspector

    def navigate(self, key: str) -> None:
        """Show the screen for ``key``, building it on first access."""
        widget = self._screens.get(key)
        if widget is None:
            widget = self._build_screen(key)
            self._screens[key] = widget
            self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)
        self._update_inspector(key)
        button = self._nav_buttons.get(key)
        if button is not None:
            button.setChecked(True)
        else:
            self._nav_group.setExclusive(False)
            for nav_button in self._nav_buttons.values():
                nav_button.setChecked(False)
            self._nav_group.setExclusive(True)

    def _update_inspector(self, key: str) -> None:
        if key == "job_builder":
            self.inspector_status.setText(
                "Interactive structure preview. Generated input validation and "
                "provenance join this panel in the end-to-end builder phase."
            )
            if self._structure_viewer is None:
                from chemsmart.gui.widgets.structure_viewer import StructureViewer

                self._structure_viewer = StructureViewer()
                self.inspector.layout().insertWidget(
                    self.inspector.layout().count() - 1,
                    self._structure_viewer,
                    stretch=1,
                )
            self._structure_viewer.setVisible(True)
            return
        if self._structure_viewer is not None:
            self._structure_viewer.setVisible(False)
        messages = {
            "chat": "Agent provenance and deterministic gate receipts appear here.",
            "database": "Selected molecule metadata appears here when P5 lands.",
            "analysis": "Selected result evidence appears here when P5 lands.",
            "settings": "Settings are applied without changing job chemistry state.",
        }
        self.inspector_status.setText(messages.get(key, "No context available."))

    def _build_menus(self) -> None:
        self.menu_actions: dict[str, QAction] = {}
        file_menu = self.menuBar().addMenu("&File")
        new_job = QAction("New Job", self)
        new_job.setShortcut(QKeySequence.StandardKey.New)
        new_job.triggered.connect(lambda: self.navigate("job_builder"))
        file_menu.addAction(new_job)
        preferences = QAction("Settings…", self)
        preferences.setShortcut(QKeySequence.StandardKey.Preferences)
        preferences.setMenuRole(QAction.MenuRole.PreferencesRole)
        preferences.triggered.connect(lambda: self.navigate("settings"))
        file_menu.addAction(preferences)
        file_menu.addSeparator()
        close_window = QAction("Close Window", self)
        close_window.setShortcut(QKeySequence.StandardKey.Close)
        close_window.triggered.connect(self.close)
        file_menu.addAction(close_window)

        edit_menu = self.menuBar().addMenu("&Edit")
        for label, standard_key, method in (
            ("Undo", QKeySequence.StandardKey.Undo, "undo"),
            ("Redo", QKeySequence.StandardKey.Redo, "redo"),
            ("Cut", QKeySequence.StandardKey.Cut, "cut"),
            ("Copy", QKeySequence.StandardKey.Copy, "copy"),
            ("Paste", QKeySequence.StandardKey.Paste, "paste"),
            ("Select All", QKeySequence.StandardKey.SelectAll, "selectAll"),
        ):
            action = QAction(label, self)
            action.setShortcut(standard_key)
            action.triggered.connect(
                lambda _checked=False, name=method: self._send_to_focus(name)
            )
            edit_menu.addAction(action)

        view_menu = self.menuBar().addMenu("&View")
        toggle_inspector = QAction("Show Context Inspector", self)
        toggle_inspector.setCheckable(True)
        toggle_inspector.setChecked(True)
        toggle_inspector.setShortcut("Ctrl+Alt+I")
        toggle_inspector.toggled.connect(self._set_inspector_visible)
        view_menu.addAction(toggle_inspector)

        job_menu = self.menuBar().addMenu("&Job")
        dry_run = QAction("Run Safe Preview", self)
        dry_run.setEnabled(False)
        dry_run.setStatusTip(
            "Available after the end-to-end fake-run artifact gate passes."
        )
        job_menu.addAction(dry_run)

        window_menu = self.menuBar().addMenu("&Window")
        minimize = QAction("Minimize", self)
        minimize.setShortcut(QKeySequence("Ctrl+M"))
        minimize.triggered.connect(self.showMinimized)
        window_menu.addAction(minimize)

        help_menu = self.menuBar().addMenu("&Help")
        about = QAction("About ChemSmart", self)
        about.triggered.connect(
            lambda: QMessageBox.about(
                self,
                "About ChemSmart",
                "ChemSmart desktop preview for safe computational chemistry "
                "workflow preparation.",
            )
        )
        help_menu.addAction(about)
        self.menu_actions.update(
            preferences=preferences,
            toggle_inspector=toggle_inspector,
            safe_preview=dry_run,
        )

    def _build_status_bar(self) -> None:
        status = self.statusBar()
        status.setAccessibleName("ChemSmart status")
        self.provider_status = QLabel("AI: optional")
        self.workspace_status = QLabel(f"Workspace: {self.workspace_root.name}")
        self.safety_status = QLabel("Safe preview")
        self.safety_status.setAccessibleDescription(
            "Desktop mode enforces fake run and blocks HPC submission."
        )
        self.task_status = QLabel("Idle")
        self.task_status.setAccessibleDescription("No background task is running.")
        for label in (
            self.provider_status,
            self.workspace_status,
            self.safety_status,
            self.task_status,
        ):
            label.setAccessibleName(label.text())
            status.addPermanentWidget(label)

    def set_workspace(self, path: Path) -> None:
        self.workspace_root = path.resolve()
        self.workspace_status.setText(f"Workspace: {self.workspace_root.name}")
        self.workspace_status.setAccessibleName(self.workspace_status.text())

    def set_provider_status(self, message: str) -> None:
        self.provider_status.setText(f"AI: {message}")
        self.provider_status.setAccessibleName(self.provider_status.text())

    def apply_runtime_projection(
        self,
        projection: DesktopRuntimeProjection,
    ) -> None:
        """Render a bounded view of canonical agent runtime state."""

        self.task_status.setText(projection.activity_label)
        self.task_status.setAccessibleName(projection.activity_label)
        self.task_status.setAccessibleDescription(projection.session_label)
        evidence = f"{projection.session_label}\n{projection.evidence_label}"
        if projection.recovery_message:
            evidence = f"{evidence}\n{projection.recovery_message}"
        self.runtime_evidence.setText(evidence)
        self.runtime_evidence.setAccessibleDescription(evidence)

    def _send_to_focus(self, method: str) -> None:
        focused = QGuiApplication.focusObject()
        callback = getattr(focused, method, None)
        if callable(callback):
            callback()

    def _set_inspector_visible(self, visible: bool) -> None:
        self._inspector_user_visible = visible
        self.inspector.setVisible(visible and self.width() >= 900)

    def _connect_system_appearance(self) -> None:
        application = QGuiApplication.instance()
        if application is None:
            return
        palette_changed = getattr(application, "paletteChanged", None)
        if palette_changed is not None:
            palette_changed.connect(self._apply_theme)
        scheme_changed = getattr(
            application.styleHints(),
            "colorSchemeChanged",
            None,
        )
        if scheme_changed is not None:
            scheme_changed.connect(self._apply_theme)

    def _apply_theme(self, *_args) -> None:
        self.setStyleSheet(theme.stylesheet())

    def resizeEvent(self, event) -> None:
        self.inspector.setVisible(
            self._inspector_user_visible and event.size().width() >= 900
        )
        super().resizeEvent(event)

    def closeEvent(self, event) -> None:
        for screen in self._screens.values():
            shutdown = getattr(screen, "shutdown", None)
            if callable(shutdown) and not shutdown(500):
                self.task_status.setText("Background: finishing before close")
                event.ignore()
                return
        super().closeEvent(event)

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
    from chemsmart.gui.screens.settings import SettingsScreen

    return SettingsScreen(window)
