"""Desktop settings for provider security, workspace, and safe mode."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from chemsmart.gui.application.task_controller import (
    QtTaskController,
    TaskFailure,
    TaskStatus,
)


class SettingsScreen(QWidget):
    """User-owned desktop settings; job-specific fields stay in Builder."""

    def __init__(self, window) -> None:
        super().__init__(objectName="Screen")
        self.window_ref = window
        self._migration: QtTaskController = QtTaskController(self)
        self._migration.succeeded.connect(self._on_migration_succeeded)
        self._migration.failed.connect(self._on_migration_failed)
        self._migration.cancelled.connect(self._on_migration_cancelled)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content = QWidget(objectName="ScrollContent")
        outer = QVBoxLayout(content)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.addWidget(QLabel("Settings", objectName="ScreenTitle"))
        subtitle = QLabel(
            "Provider credentials use the system Keychain. Job-specific "
            "chemistry settings remain in Job builder.",
            objectName="ScreenSubtitle",
        )
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        provider_box = QGroupBox("AI provider (optional)")
        provider_layout = QVBoxLayout(provider_box)
        provider_help = QLabel(
            "ChemSmart works without AI. Connect a provider only when you "
            "want agent assistance.",
            objectName="ScreenSubtitle",
        )
        provider_help.setWordWrap(True)
        provider_layout.addWidget(provider_help)
        provider_actions = QVBoxLayout()
        self.connect_button = QPushButton("Connect or update provider")
        self.connect_button.setAccessibleDescription(
            "Tests an in-memory provider draft before storing its credential "
            "in the system Keychain."
        )
        self.connect_button.clicked.connect(self._open_provider_setup)
        self.migrate_button = QPushButton("Migrate legacy plaintext key")
        self.migrate_button.setAccessibleDescription(
            "Moves an existing literal API key from agent.yaml into the "
            "system Keychain after this explicit action."
        )
        self.migrate_button.clicked.connect(self._start_migration)
        provider_actions.addWidget(self.connect_button)
        provider_actions.addWidget(self.migrate_button)
        provider_layout.addLayout(provider_actions)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName("Credential migration progress")
        self.progress.setVisible(False)
        provider_layout.addWidget(self.progress)
        self.provider_status = QLabel(
            "No provider is required for Job builder.",
            objectName="ScreenSubtitle",
        )
        self.provider_status.setWordWrap(True)
        provider_layout.addWidget(self.provider_status)
        outer.addWidget(provider_box)

        workspace_box = QGroupBox("Workspace")
        workspace_form = QFormLayout(workspace_box)
        self.workspace_path = QLineEdit(
            str(window.workspace_root),
        )
        self.workspace_path.setReadOnly(True)
        self.workspace_path.setAccessibleName("Current workspace path")
        self.choose_workspace = QPushButton("Choose…")
        self.choose_workspace.setAccessibleName("Choose ChemSmart workspace")
        self.choose_workspace.clicked.connect(self._choose_workspace)
        workspace_label = QLabel("Current workspace", objectName="FieldLabel")
        workspace_label.setBuddy(self.workspace_path)
        workspace_form.addRow(workspace_label, self.workspace_path)
        workspace_actions = QHBoxLayout()
        workspace_actions.addStretch(1)
        workspace_actions.addWidget(self.choose_workspace)
        workspace_form.addRow("", workspace_actions)
        outer.addWidget(workspace_box)

        visualization_box = QGroupBox("Optional visualization")
        visualization_layout = QVBoxLayout(visualization_box)
        visualization_help = QLabel(
            "Interactive 3D works without PyMOL. To use the optional Zhang "
            "Lab render, choose its local executable explicitly when a "
            "Finder-launched app cannot discover it on PATH.",
            objectName="ScreenSubtitle",
        )
        visualization_help.setWordWrap(True)
        visualization_layout.addWidget(visualization_help)
        self.pymol_path = QLineEdit(
            str(window.pymol_executable) if window.pymol_executable else ""
        )
        self.pymol_path.setReadOnly(True)
        self.pymol_path.setPlaceholderText("PyMOL not found on PATH")
        self.pymol_path.setAccessibleName("Configured PyMOL executable")
        self.choose_pymol = QPushButton("Choose PyMOL…")
        self.choose_pymol.setAccessibleName("Choose PyMOL executable")
        self.choose_pymol.clicked.connect(self._choose_pymol_executable)
        self.use_path_pymol = QPushButton("Use PATH")
        self.use_path_pymol.setAccessibleName("Discover PyMOL on PATH")
        self.use_path_pymol.clicked.connect(self._use_path_pymol)
        pymol_label = QLabel("PyMOL executable", objectName="FieldLabel")
        pymol_label.setBuddy(self.pymol_path)
        form = QFormLayout()
        form.addRow(pymol_label, self.pymol_path)
        visualization_layout.addLayout(form)
        pymol_actions = QHBoxLayout()
        pymol_actions.addStretch(1)
        pymol_actions.addWidget(self.choose_pymol)
        pymol_actions.addWidget(self.use_path_pymol)
        visualization_layout.addLayout(pymol_actions)
        self.pymol_status = QLabel(
            window.pymol_preference_issue
            or (
                "PyMOL is ready for optional local rendering."
                if window.pymol_executable
                else "PyMOL is optional and currently unavailable."
            ),
            objectName="ScreenSubtitle",
        )
        self.pymol_status.setWordWrap(True)
        self.pymol_status.setAccessibleName("PyMOL configuration status")
        visualization_layout.addWidget(self.pymol_status)
        outer.addWidget(visualization_box)

        safety_box = QGroupBox("Safety and appearance")
        safety_layout = QVBoxLayout(safety_box)
        self.safe_mode = QCheckBox("Safe fake-run mode is enforced")
        self.safe_mode.setChecked(True)
        self.safe_mode.setEnabled(False)
        self.safe_mode.setAccessibleDescription(
            "Desktop v1 cannot disable fake-run safety or submit HPC jobs."
        )
        safety_layout.addWidget(self.safe_mode)
        appearance_help = QLabel(
            "Appearance, contrast, and fonts follow macOS system settings.",
            objectName="ScreenSubtitle",
        )
        appearance_help.setWordWrap(True)
        safety_layout.addWidget(appearance_help)
        outer.addWidget(safety_box)
        outer.addStretch(1)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll.setWidget(content)
        root.addWidget(self.scroll)

    def _open_provider_setup(self) -> None:
        from chemsmart.gui.screens.onboarding import OnboardingDialog

        dialog = OnboardingDialog(self)
        if dialog.run():
            self.provider_status.setText(
                "Provider saved. The credential is stored in the system "
                "Keychain; settings contain only its reference."
            )
            self.window_ref.set_provider_status("Provider configured")

    def _start_migration(self) -> None:
        if self._migration.snapshot.status in {
            TaskStatus.RUNNING,
            TaskStatus.CANCELLING,
        }:
            return
        self.progress.setVisible(True)
        self.connect_button.setEnabled(False)
        self.migrate_button.setEnabled(False)
        self.migrate_button.setText("Migrating…")
        self.provider_status.setText("Migrating credential to Keychain…")
        # Credential-store + atomic YAML replacement is one side-effecting
        # transaction. Offering a timeout/cancel after commit could falsely
        # report "cancelled" even though migration succeeded.
        self._migration.start(self._migrate_secret)

    @staticmethod
    def _migrate_secret(context):
        from chemsmart.agent.provider_config import (
            migrate_plaintext_provider_secret,
        )

        context.report_indeterminate("Migrating credential")
        context.raise_if_cancelled()
        result = migrate_plaintext_provider_secret()
        context.raise_if_cancelled()
        return result

    def _on_migration_succeeded(self, result) -> None:
        self._reset_migration_controls()
        messages = {
            "migrated": "Legacy credential moved to the system Keychain.",
            "already_referenced": "Credential already uses the system Keychain.",
            "no_plaintext_secret": "No plaintext credential needs migration.",
        }
        self.provider_status.setText(
            messages.get(result.status, "Migration complete.")
        )
        if result.status in {"migrated", "already_referenced"}:
            self.window_ref.set_provider_status("Provider configured")

    def _on_migration_failed(self, failure: TaskFailure) -> None:
        self._reset_migration_controls()
        self.provider_status.setText(
            "Credential migration failed without replacing the existing "
            f"settings. ({failure.diagnostic_type})"
        )

    def _on_migration_cancelled(self) -> None:
        self._reset_migration_controls()
        self.provider_status.setText("Credential migration cancelled.")

    def _reset_migration_controls(self) -> None:
        self.progress.setVisible(False)
        self.connect_button.setEnabled(True)
        self.migrate_button.setEnabled(True)
        self.migrate_button.setText("Migrate legacy plaintext key")

    def _choose_workspace(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose ChemSmart workspace",
            str(self.window_ref.workspace_root),
        )
        if selected:
            path = Path(selected).resolve()
            self.window_ref.set_workspace(path)
            self.workspace_path.setText(str(path))

    def _choose_pymol_executable(self) -> None:
        current = self.window_ref.pymol_executable
        start = str(current.parent if current else Path("/Applications"))
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            "Choose the PyMOL executable",
            start,
            "Executable files (*)",
        )
        if not selected:
            return
        try:
            executable = self.window_ref.configure_pymol_executable(selected)
        except (OSError, RuntimeError, ValueError) as exc:
            self.pymol_status.setText(
                "PyMOL was not changed. Choose an executable regular file. "
                f"({type(exc).__name__})"
            )
            return
        self.pymol_path.setText(str(executable))
        self.pymol_status.setText(
            "PyMOL is ready for optional local rendering."
        )

    def _use_path_pymol(self) -> None:
        try:
            executable = self.window_ref.use_path_pymol_executable()
        except RuntimeError as exc:
            self.pymol_status.setText(
                "PyMOL was not changed while the previous render stops. "
                f"({type(exc).__name__})"
            )
            return
        self.pymol_path.setText(str(executable) if executable else "")
        self.pymol_status.setText(
            "PyMOL is ready from PATH."
            if executable
            else "PyMOL was not found on PATH; interactive 3D remains available."
        )

    def shutdown(self, timeout_ms: int = 500) -> bool:
        return self._migration.shutdown(timeout_ms)
