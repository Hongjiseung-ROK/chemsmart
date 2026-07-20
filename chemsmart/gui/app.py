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

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from chemsmart import __version__
from chemsmart.gui import theme
from chemsmart.gui.application.runtime_projection import (
    DesktopRuntimeProjection,
)


@dataclass(frozen=True)
class NavEntry:
    """One activity-rail item and the factory building its screen on demand."""

    key: str
    label: str
    group: str  # "Build" or "Explore"
    icon: str  # pinned icon name (chemsmart.gui.design.icons)
    factory: Callable[["MainWindow"], QWidget]


class MainWindow(QMainWindow):
    """Top-level window hosting the sidebar and the screen stack."""

    def __init__(
        self,
        session_root: Path | None = None,
        preference_store=None,
    ) -> None:
        super().__init__()
        # A closed top-level window owns QtWebEngine children. Delete it at the
        # accepted close boundary so repeated windows do not retain renderer
        # processes until interpreter shutdown (notably in tests and relaunch).
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle("ChemSmart")
        self.setMinimumSize(720, 520)
        self.resize(1280, 800)
        self.session_root = session_root
        self.workspace_root = Path.cwd().resolve()
        self._preference_store = preference_store
        self._pymol_preference_issue = ""
        self._pymol_executable = self._load_pymol_executable()
        self._inspector_user_visible = True

        self._screens: dict[str, QWidget] = {}
        self._nav_buttons: dict[str, QToolButton] = {}

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
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(2, True)
        self.splitter.setSizes([84, 880, 316])
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
            NavEntry(
                "job_builder",
                "Job builder",
                "Build",
                "flask-conical",
                _make_job_builder,
            ),
            NavEntry("chat", "Chat", "Build", "message-square", _make_chat),
            NavEntry(
                "database", "Database", "Explore", "database", _make_database
            ),
            NavEntry(
                "analysis",
                "Analysis",
                "Explore",
                "chart-column",
                _make_analysis,
            ),
        ]

    def _build_sidebar(self) -> QWidget:
        """The activity rail: icon-over-label buttons in a fixed column."""
        sidebar = QWidget(objectName="Sidebar")
        sidebar.setMinimumWidth(84)
        sidebar.setMaximumWidth(84)
        sidebar.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        sidebar.setAccessibleName("Primary navigation")
        col = QVBoxLayout(sidebar)
        col.setContentsMargins(6, 10, 6, 10)
        col.setSpacing(2)

        group = QButtonGroup(self)
        group.setExclusive(True)
        self._nav_group = group
        self._nav_icons: dict[str, str] = {}

        current_group = None
        for entry in self._entries():
            if entry.group != current_group:
                current_group = entry.group
                col.addWidget(QLabel(entry.group, objectName="SidebarGroup"))
            button = QToolButton(objectName="NavItem")
            button.setText(entry.label)
            button.setCheckable(True)
            button.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextUnderIcon
            )
            button.setIconSize(QSize(20, 20))
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            button.setMinimumHeight(52)
            button.setAccessibleName(f"Open {entry.label}")
            button.setAccessibleDescription(
                f"Shows the {entry.label} work surface."
            )
            button.setToolTip(entry.label)
            button.clicked.connect(
                lambda _checked=False, key=entry.key: self.navigate(key)
            )
            group.addButton(button)
            col.addWidget(button)
            self._nav_buttons[entry.key] = button
            self._nav_icons[entry.key] = entry.icon

        col.addStretch(1)
        return sidebar

    def _refresh_nav_icons(self) -> None:
        """Recolor rail icons for the current appearance mode."""
        from chemsmart.gui.design import icons as design_icons

        palette = theme.palette_for()
        for key, button in self._nav_buttons.items():
            icon_name = self._nav_icons.get(key)
            if not icon_name:
                continue
            color = (
                palette.text_primary
                if button.isChecked()
                else palette.text_secondary
            )
            try:
                button.setIcon(design_icons.icon(icon_name, color, 20))
            except design_icons.IconError:
                # A missing/tampered icon must never break navigation; the
                # text label remains the accessible, visible fallback.
                continue

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
        self._refresh_nav_icons()

    def _update_inspector(self, key: str) -> None:
        if key == "job_builder":
            self.inspector_status.setText(
                "Choose a local molecule to inspect its structure. Safe preview "
                "adds the generated route, state, and deterministic receipt here."
            )
            if self._structure_viewer is not None:
                self._structure_viewer.setVisible(True)
            return
        if self._structure_viewer is not None:
            self._structure_viewer.setVisible(False)
        messages = {
            "chat": "Agent provenance and deterministic gate receipts appear here.",
            "database": (
                "Select a database row to inspect its structured metadata and "
                "molecular geometry."
            ),
            "analysis": (
                "Analysis receipts identify the library result, input scope, and "
                "whether any files were written."
            ),
            "settings": "Settings are applied without changing job chemistry state.",
        }
        self.inspector_status.setText(
            messages.get(key, "No context available.")
        )

    def ensure_structure_viewer(self):
        """Create the QtWebEngine-backed viewer only after source selection."""
        if self._structure_viewer is None:
            from chemsmart.gui.services.pymol_render_service import (
                PyMOLRenderService,
            )
            from chemsmart.gui.widgets.structure_viewer import StructureViewer

            service = PyMOLRenderService(executable=self._pymol_executable)
            self._pymol_executable = service.executable
            self._structure_viewer = StructureViewer(pymol_service=service)
            self.inspector.layout().insertWidget(
                self.inspector.layout().count() - 1,
                self._structure_viewer,
                stretch=1,
            )
        self._structure_viewer.setVisible(True)
        return self._structure_viewer

    @property
    def pymol_executable(self) -> Path | None:
        return self._pymol_executable

    @property
    def pymol_preference_issue(self) -> str:
        return self._pymol_preference_issue

    def configure_pymol_executable(self, executable: str | Path) -> Path:
        """Validate, apply, and persist one explicit PyMOL executable."""
        from chemsmart.gui.services.pymol_render_service import (
            PyMOLRenderService,
        )

        service = PyMOLRenderService(executable=Path(executable))
        if self._structure_viewer is not None:
            self._structure_viewer.set_pymol_service(service)
        self._pymol_executable = service.executable
        self._pymol_preference_issue = ""
        if self._preference_store is not None:
            self._preference_store.setValue(
                "visualization/pymol_executable",
                str(service.executable),
            )
            self._preference_store.sync()
        return service.executable

    def use_path_pymol_executable(self) -> Path | None:
        """Return to PATH discovery and remove an explicit preference."""
        from chemsmart.gui.services.pymol_render_service import (
            PyMOLRenderService,
        )

        service = PyMOLRenderService()
        if self._structure_viewer is not None:
            self._structure_viewer.set_pymol_service(service)
        self._pymol_executable = service.executable
        self._pymol_preference_issue = ""
        if self._preference_store is not None:
            self._preference_store.remove("visualization/pymol_executable")
            self._preference_store.sync()
        return service.executable

    def _load_pymol_executable(self) -> Path | None:
        from chemsmart.gui.services.pymol_render_service import (
            discover_pymol_executable,
            validate_pymol_executable,
        )

        detected = discover_pymol_executable()
        if self._preference_store is None:
            return detected
        saved = self._preference_store.value(
            "visualization/pymol_executable",
            "",
        )
        if not str(saved).strip():
            return detected
        try:
            return validate_pymol_executable(str(saved))
        except ValueError:
            self._pymol_preference_issue = (
                "The saved PyMOL executable is no longer available. "
                "Choose it again or use PATH discovery."
            )
            return detected

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
        quit_application = QAction("Quit ChemSmart", self)
        quit_application.setShortcut(QKeySequence.StandardKey.Quit)
        quit_application.setMenuRole(QAction.MenuRole.QuitRole)
        quit_application.triggered.connect(QApplication.closeAllWindows)
        file_menu.addAction(quit_application)

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
        command_palette = QAction("Command Palette…", self)
        command_palette.setShortcut(QKeySequence("Ctrl+Shift+P"))
        command_palette.setStatusTip(
            "Search and run any available ChemSmart action."
        )
        command_palette.triggered.connect(self.open_command_palette)
        view_menu.addAction(command_palette)

        job_menu = self.menuBar().addMenu("&Job")
        dry_run = QAction("Run Safe Preview", self)
        dry_run.setEnabled(False)
        dry_run.setStatusTip(
            "Generate and validate inputs with enforced fake and no-scratch mode."
        )
        job_menu.addAction(dry_run)

        window_menu = self.menuBar().addMenu("&Window")
        minimize = QAction("Minimize", self)
        minimize.setShortcut(QKeySequence("Ctrl+M"))
        minimize.triggered.connect(self.showMinimized)
        window_menu.addAction(minimize)

        help_menu = self.menuBar().addMenu("&Help")
        help_contents = QAction("ChemSmart Help…", self)
        help_contents.setShortcut(QKeySequence.StandardKey.HelpContents)
        help_contents.triggered.connect(self._show_help)
        help_menu.addAction(help_contents)
        support_bundle = QAction("Create Support Bundle…", self)
        support_bundle.setStatusTip(
            "Create a bounded, redacted diagnostic ZIP to review before sharing."
        )
        support_bundle.triggered.connect(self._create_support_bundle)
        help_menu.addAction(support_bundle)
        help_menu.addSeparator()
        about = QAction("About ChemSmart", self)
        about.triggered.connect(
            lambda: QMessageBox.about(
                self,
                "About ChemSmart",
                f"ChemSmart {__version__}\n\n"
                "Safe desktop preparation for computational chemistry "
                "workflows. Real calculations and HPC submission remain "
                "outside desktop mode.",
            )
        )
        help_menu.addAction(about)
        self.menu_actions.update(
            preferences=preferences,
            quit=quit_application,
            toggle_inspector=toggle_inspector,
            command_palette=command_palette,
            safe_preview=dry_run,
            help=help_contents,
            support_bundle=support_bundle,
            about=about,
        )

    def open_command_palette(self) -> None:
        """Open the searchable, contract-authorized command palette."""
        from chemsmart.gui.design.tokens import resolve_tokens
        from chemsmart.gui.workbench.command_palette import (
            CommandPalette,
            commands_for_window,
        )

        palette = CommandPalette(
            commands_for_window(self),
            tokens=resolve_tokens(),
            parent=self,
        )
        palette.exec()

    def _build_status_bar(self) -> None:
        status = self.statusBar()
        status.setAccessibleName("ChemSmart status")
        self.provider_status = QLabel("AI: optional")
        self.workspace_status = QLabel(self._workspace_status_text())
        self.safety_status = QLabel("Safe preview")
        self.safety_status.setAccessibleDescription(
            "Desktop mode enforces fake run and blocks HPC submission."
        )
        self.task_status = QLabel("Idle")
        self.task_status.setAccessibleDescription(
            "No background task is running."
        )
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
        self.workspace_status.setText(self._workspace_status_text())
        self.workspace_status.setAccessibleName(self.workspace_status.text())
        # The Job builder validates its safe preview against the active
        # workspace. Refresh an already-created builder immediately so a
        # Settings change cannot leave Generate input in a stale state.
        builder = self._screens.get("job_builder")
        refresh = getattr(builder, "refresh_workspace_state", None)
        if callable(refresh):
            refresh()

    def _workspace_status_text(self) -> str:
        """Return a non-empty, compact workspace label, including for ``/``."""
        label = self.workspace_root.name or str(self.workspace_root)
        return f"Workspace: {label}"

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

    def _show_help(self) -> None:
        QMessageBox.information(
            self,
            "ChemSmart Help",
            "Start in Job builder: choose a local molecule source, review the "
            "exact ChemSmart command, then generate a safe fake-run input.\n\n"
            "Chat is optional. Database and Analysis use structured local "
            "ChemSmart results and do not launch Gaussian, ORCA, or HPC jobs.\n\n"
            "For a background task, use Cancel when it is available. After an "
            "error, correct the named input and use Retry; no output is accepted "
            "until its receipt is verified.\n\n"
            "Interactive 3D works offline. Configure an optional local PyMOL "
            "executable in Settings when Finder cannot discover it on PATH.\n\n"
            "The desktop always enforces fake-run safety. Real calculations and "
            "HPC submission remain in the existing approved CLI workflow.\n\n"
            "Create Support Bundle in this Help menu writes a bounded, redacted "
            "ZIP. Review it before sharing; configuration, project files, provider "
            "payloads, sessions, and Keychain data are excluded.",
        )

    def _create_support_bundle(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        from chemsmart.gui.application.support_bundle import (
            create_support_bundle,
        )

        suggested = Path.home() / "Desktop" / "ChemSmart-support.zip"
        filename, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save ChemSmart Support Bundle",
            str(suggested),
            "ZIP archive (*.zip)",
        )
        if not filename:
            return
        destination = Path(filename)
        if destination.suffix.lower() != ".zip":
            destination = destination.with_suffix(".zip")
        try:
            receipt = create_support_bundle(destination)
        except FileExistsError:
            QMessageBox.critical(
                self,
                "Support Bundle Not Created",
                "A file already exists there. Choose a new filename.",
            )
            return
        except (OSError, ValueError) as exc:
            QMessageBox.critical(
                self,
                "Support Bundle Not Created",
                f"ChemSmart could not create the support bundle. {exc}",
            )
            return
        QMessageBox.information(
            self,
            "Support Bundle Created",
            f"Saved {receipt.output_path}.\n\n"
            f"Included logs: {receipt.included_log_count}\n"
            f"Redacted sensitive values: {receipt.redaction_count}\n\n"
            "Review the ZIP "
            "before sharing it. Configuration, project files, provider "
            "payloads, sessions, and Keychain data were not included.",
        )

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
        self._refresh_nav_icons()

    def resizeEvent(self, event) -> None:
        self.inspector.setVisible(
            self._inspector_user_visible and event.size().width() >= 900
        )
        super().resizeEvent(event)

    def closeEvent(self, event) -> None:
        # Phase 1: ask every task-owning surface to cancel and drain.  No
        # irreversible UI resource is released during this phase, so a single
        # rejecting participant cannot leave a still-visible partial window.
        drained = True
        for screen in self._screens.values():
            shutdown = getattr(screen, "shutdown", None)
            if callable(shutdown) and not shutdown(500):
                drained = False
        viewer = self._structure_viewer
        if viewer is not None:
            prepare = getattr(viewer, "prepare_shutdown", None)
            if callable(prepare) and not prepare(500):
                drained = False
        if not drained:
            self.task_status.setText("Background: finishing before close")
            event.ignore()
            return

        # Phase 2: all workers are drained, so owned WebEngine resources can be
        # released atomically at the accepted window-close boundary.
        if viewer is not None:
            finalize = getattr(viewer, "finalize_shutdown", None)
            if callable(finalize):
                finalize()
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
    from chemsmart.gui.screens.database import DatabaseScreen

    return DatabaseScreen(window)


def _make_analysis(window: MainWindow) -> QWidget:
    from chemsmart.gui.screens.analysis import AnalysisScreen

    return AnalysisScreen(window)


def _make_settings(window: MainWindow) -> QWidget:
    from chemsmart.gui.screens.settings import SettingsScreen

    return SettingsScreen(window)
