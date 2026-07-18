"""First-run onboarding: choose a provider and store the API key.

Reuses the CLI's config code path — :meth:`Config.write_agent_provider_config`
writes ``~/.chemsmart/agent/agent.yaml`` in exactly the schema
:mod:`chemsmart.agent.provider_config` expects, so no new secrets format is
introduced (plan Phase 2). The key is entered with echo masked and is never
logged.

v1 offers ``openai`` and ``anthropic`` only; the local provider stays a
CLI-only path (approved scope). The "Test connection" button pings the
provider on a worker thread so a bad key is caught before the window opens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from chemsmart.gui import theme
from chemsmart.gui.application.task_controller import (
    QtTaskController,
    TaskContext,
    TaskFailure,
)

if TYPE_CHECKING:
    from chemsmart.agent.secrets import SecretStore

_DEFAULT_MODEL = {
    "openai": "gpt-5.4",
    "anthropic": "claude-sonnet-4-6",
}
_OFFICIAL_BASE_URL = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
}


@dataclass(frozen=True)
class ProviderSetupDraft:
    """In-memory provider settings used for connection validation."""

    provider_type: str
    api_key: str = field(repr=False)
    model: str

    @property
    def base_url(self) -> str:
        """Reviewed first-party endpoint for a built-in provider choice."""
        try:
            return _OFFICIAL_BASE_URL[self.provider_type]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported desktop provider: {self.provider_type!r}"
            ) from exc

    @property
    def signature(self) -> tuple[str, str, str]:
        """Identity used to invalidate a successful test after edits."""
        fingerprint = hashlib.sha256(self.api_key.encode("utf-8")).hexdigest()
        return (self.provider_type, fingerprint, self.model)

    def build_provider(self):
        """Construct a provider without reading or writing user config."""
        from chemsmart.agent.providers import (
            AnthropicProvider,
            OpenAIProvider,
        )

        if self.provider_type == "openai":
            return OpenAIProvider(
                self.api_key,
                model=self.model,
                base_url=self.base_url,
            )
        if self.provider_type == "anthropic":
            return AnthropicProvider(
                self.api_key,
                model=self.model,
                base_url=self.base_url,
            )
        raise ValueError(f"Unsupported desktop provider: {self.provider_type!r}")


def _ping_provider(draft: ProviderSetupDraft, context: TaskContext) -> str:
    """Ping one in-memory provider draft without persisting credentials."""
    context.report_indeterminate("Testing provider connection")
    context.raise_if_cancelled()
    draft.build_provider().ping()
    context.raise_if_cancelled()
    return "Connected."


class OnboardingDialog(QDialog):
    """Modal first-run wizard. Returns True from :meth:`run` on completion."""

    def __init__(
        self,
        parent=None,
        *,
        secret_store: SecretStore | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set up ChemSmart")
        self.setMinimumWidth(420)
        self.setStyleSheet(theme.stylesheet())
        self._pending_signature: tuple[str, str, str] | None = None
        self._tested_signature: tuple[str, str, str] | None = None
        self._secret_store = secret_store
        self._task_controller: QtTaskController[str] = QtTaskController(self)
        self._task_controller.succeeded.connect(self._on_ping_succeeded)
        self._task_controller.failed.connect(self._on_ping_failed)
        self._task_controller.cancelled.connect(self._on_ping_cancelled)
        self._task_controller.drained.connect(self._refresh_actions)

        layout = QVBoxLayout(self)
        title = QLabel("Connect an AI provider", objectName="ScreenTitle")
        self.privacy_notice = QLabel(
            "The connection test sends a minimal request directly to "
            "api.openai.com. Saving stores the credential in your system "
            "Keychain; ChemSmart settings keep only a reference.",
            objectName="ScreenSubtitle",
        )
        self.privacy_notice.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(self.privacy_notice)

        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItems(["openai", "anthropic"])
        self.provider.currentTextChanged.connect(self._on_provider_changed)
        self.provider.currentTextChanged.connect(self._invalidate_test)

        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("sk-…")
        self.api_key.textChanged.connect(self._invalidate_test)

        self.model = QLineEdit(_DEFAULT_MODEL["openai"])
        self.model.textChanged.connect(self._invalidate_test)

        provider_label = QLabel("Provider", objectName="FieldLabel")
        provider_label.setBuddy(self.provider)
        key_label = QLabel("API key", objectName="FieldLabel")
        key_label.setBuddy(self.api_key)
        model_label = QLabel("Model", objectName="FieldLabel")
        model_label.setBuddy(self.model)
        form.addRow(provider_label, self.provider)
        form.addRow(key_label, self.api_key)
        form.addRow(model_label, self.model)
        layout.addLayout(form)

        self.status = QLabel("", objectName="ScreenSubtitle")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName("Provider connection progress")
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        buttons = QHBoxLayout()
        self.test_button = QPushButton("Test connection")
        self.test_button.clicked.connect(self._on_test)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._on_cancel)
        self.save_button = QPushButton("Save", objectName="Primary")
        self.save_button.clicked.connect(self._on_save)
        buttons.addWidget(self.test_button)
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self._refresh_actions()

    def _on_provider_changed(self, provider: str) -> None:
        self.model.setText(_DEFAULT_MODEL.get(provider, ""))
        host = {
            "openai": "api.openai.com",
            "anthropic": "api.anthropic.com",
        }.get(provider, "the selected provider")
        self.privacy_notice.setText(
            f"The connection test sends a minimal request directly to {host}. "
            "Saving stores the credential in your system Keychain; ChemSmart "
            "settings keep only a reference."
        )

    def _invalidate_test(self, *_args) -> None:
        self._tested_signature = None
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        """Enable actions only for complete input and a drained worker."""
        if not hasattr(self, "test_button"):
            return
        worker_live = bool(self._task_controller.active_thread_count)
        inputs_valid = bool(
            self.api_key.text().strip() and self.model.text().strip()
        )
        self.test_button.setEnabled(inputs_valid and not worker_live)
        current_signature = None
        if inputs_valid:
            current_signature = ProviderSetupDraft(
                self.provider.currentText(),
                self.api_key.text().strip(),
                self.model.text().strip(),
            ).signature
        self.save_button.setEnabled(
            not worker_live
            and current_signature is not None
            and current_signature == self._tested_signature
        )

    def _current_draft(self) -> ProviderSetupDraft | None:
        key = self.api_key.text().strip()
        if not key:
            self.status.setText("Enter an API key first.")
            return None
        return ProviderSetupDraft(
            provider_type=self.provider.currentText(),
            api_key=key,
            model=self.model.text().strip(),
        )

    def _write_config(self, draft: ProviderSetupDraft) -> None:
        from chemsmart.agent.secrets import (
            KeyringSecretStore,
            new_secret_account,
        )
        from chemsmart.cli.config import Config

        store = self._secret_store or KeyringSecretStore()
        config = Config()
        previous_reference = config.agent_provider_secret_reference(
            draft.provider_type
        )
        reference = store.store(
            new_secret_account(draft.provider_type),
            draft.api_key,
        )
        try:
            if store.resolve(reference) != draft.api_key:
                raise RuntimeError(
                    "Credential store verification returned a different value."
                )
            config.write_agent_provider_config(
                draft.provider_type,
                api_key_ref=reference,
                model=draft.model,
                base_url=draft.base_url,
            )
        except Exception:
            try:
                store.delete(reference)
            except Exception:
                pass
            raise
        if previous_reference and previous_reference != reference:
            try:
                store.delete(previous_reference)
            except Exception:
                # The new reference is already durable. An old orphan is safer
                # than rolling back a successfully committed provider update.
                pass

    def _on_test(self) -> None:
        draft = self._current_draft()
        if draft is None:
            return
        self._pending_signature = draft.signature
        self.status.setText("Testing…")
        self.test_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.progress.setVisible(True)
        self._task_controller.start(
            lambda context: _ping_provider(draft, context),
            timeout_ms=30_000,
            retain_for_retry=False,
        )

    def _on_ping_succeeded(self, message: str) -> None:
        self.progress.setVisible(False)
        current = self._current_draft()
        if (
            current is not None
            and self._pending_signature is not None
            and current.signature == self._pending_signature
        ):
            self._tested_signature = current.signature
            self.status.setText(message)
        else:
            self.status.setText("Values changed. Test the current settings again.")
        self._pending_signature = None
        self._refresh_actions()

    def _on_ping_failed(self, failure: TaskFailure) -> None:
        self._pending_signature = None
        self.progress.setVisible(False)
        self.status.setText(
            "Couldn't connect. Check the credential, model, and network. "
            f"({failure.diagnostic_type})"
        )
        self._refresh_actions()

    def _on_ping_cancelled(self) -> None:
        self._pending_signature = None
        self.progress.setVisible(False)
        self.status.setText("Connection test cancelled.")
        self._refresh_actions()

    def _on_cancel(self) -> None:
        if self._task_controller.active_thread_count:
            self._task_controller.cancel()
            self.status.setText("Cancelling connection test…")
            return
        self.reject()

    def _on_save(self) -> None:
        draft = self._current_draft()
        if draft is None:
            return
        if draft.signature != self._tested_signature:
            self.status.setText("Test this provider configuration before saving.")
            return
        try:
            self._write_config(draft)
        except Exception:
            self.status.setText(
                "Couldn't save securely. No credential was written to "
                "ChemSmart settings."
            )
            return
        self.api_key.clear()
        self._pending_signature = None
        self._tested_signature = None
        self.accept()

    def run(self) -> bool:
        """Show modally; return True when the user completed setup."""
        return self.exec() == QDialog.DialogCode.Accepted

    def accept(self) -> None:
        """Never hide the dialog while its provider worker is still live."""
        if not self._task_controller.shutdown(500):
            self.status.setText("Finishing the connection test before saving…")
            return
        super().accept()

    def reject(self) -> None:
        """Keep timeout/cancel recovery visible until the worker drains."""
        if not self._task_controller.shutdown(500):
            self.status.setText("Finishing the connection test before closing…")
            return
        super().reject()

    def closeEvent(self, event) -> None:
        """Do not destroy a dialog while its provider worker is still live."""
        if not self._task_controller.shutdown(500):
            self.status.setText("Finishing the connection test before closing…")
            event.ignore()
            return
        super().closeEvent(event)
