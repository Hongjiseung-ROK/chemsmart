"""Desktop settings for provider security, workspace, and safe mode."""

from __future__ import annotations

from pathlib import Path

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

        outer = QVBoxLayout(self)
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
        provider_layout.addWidget(
            QLabel(
                "ChemSmart works without AI. Connect a provider only when you "
                "want agent assistance.",
                objectName="ScreenSubtitle",
            )
        )
        provider_actions = QHBoxLayout()
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
        provider_actions.addStretch(1)
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
        choose_workspace = QPushButton("Choose…")
        choose_workspace.clicked.connect(self._choose_workspace)
        workspace_row = QHBoxLayout()
        workspace_row.addWidget(self.workspace_path, stretch=1)
        workspace_row.addWidget(choose_workspace)
        workspace_label = QLabel("Current workspace", objectName="FieldLabel")
        workspace_label.setBuddy(choose_workspace)
        workspace_form.addRow(workspace_label, workspace_row)
        outer.addWidget(workspace_box)

        safety_box = QGroupBox("Safety and appearance")
        safety_layout = QVBoxLayout(safety_box)
        self.safe_mode = QCheckBox("Safe fake-run mode is enforced")
        self.safe_mode.setChecked(True)
        self.safe_mode.setEnabled(False)
        self.safe_mode.setAccessibleDescription(
            "Desktop v1 cannot disable fake-run safety or submit HPC jobs."
        )
        safety_layout.addWidget(self.safe_mode)
        safety_layout.addWidget(
            QLabel(
                "Appearance, contrast, and fonts follow macOS system settings.",
                objectName="ScreenSubtitle",
            )
        )
        outer.addWidget(safety_box)
        outer.addStretch(1)

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
        self.provider_status.setText(messages.get(result.status, "Migration complete."))
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

    def shutdown(self, timeout_ms: int = 500) -> bool:
        return self._migration.shutdown(timeout_ms)
