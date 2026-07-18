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

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from chemsmart.gui import theme

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
        return (self.provider_type, self.api_key, self.model)

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


class _PingWorker(QObject):
    """Runs ``get_provider().ping()`` off the UI thread (principle #8)."""

    done = Signal(bool, str)

    def __init__(self, draft: ProviderSetupDraft) -> None:
        super().__init__()
        self._draft = draft

    def run(self) -> None:
        try:
            self._draft.build_provider().ping()
            self.done.emit(True, "Connected.")
        except Exception as exc:  # provider/network/credential failure
            self.done.emit(False, str(exc))


class OnboardingDialog(QDialog):
    """Modal first-run wizard. Returns True from :meth:`run` on completion."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set up ChemSmart")
        self.setMinimumWidth(420)
        self.setStyleSheet(theme.stylesheet())
        self._thread: QThread | None = None
        self._worker: _PingWorker | None = None
        self._pending_draft: ProviderSetupDraft | None = None
        self._tested_signature: tuple[str, str, str] | None = None

        layout = QVBoxLayout(self)
        title = QLabel("Connect an AI provider", objectName="ScreenTitle")
        self.privacy_notice = QLabel(
            "The connection test sends a minimal request directly to "
            "api.openai.com. Saving stores the key in local ChemSmart "
            "settings until Keychain migration is available.",
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

        form.addRow(QLabel("Provider", objectName="FieldLabel"), self.provider)
        form.addRow(QLabel("API key", objectName="FieldLabel"), self.api_key)
        form.addRow(QLabel("Model", objectName="FieldLabel"), self.model)
        layout.addLayout(form)

        self.status = QLabel("", objectName="ScreenSubtitle")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.test_button = QPushButton("Test connection")
        self.test_button.clicked.connect(self._on_test)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save", objectName="Primary")
        save.clicked.connect(self._on_save)
        buttons.addWidget(self.test_button)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _on_provider_changed(self, provider: str) -> None:
        self.model.setText(_DEFAULT_MODEL.get(provider, ""))
        host = {
            "openai": "api.openai.com",
            "anthropic": "api.anthropic.com",
        }.get(provider, "the selected provider")
        self.privacy_notice.setText(
            f"The connection test sends a minimal request directly to {host}. "
            "Saving stores the key in local ChemSmart settings until "
            "Keychain migration is available."
        )

    def _invalidate_test(self, *_args) -> None:
        self._tested_signature = None

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
        from chemsmart.cli.config import Config

        Config().write_agent_provider_config(
            draft.provider_type,
            api_key=draft.api_key,
            model=draft.model,
            base_url=draft.base_url,
        )

    def _on_test(self) -> None:
        draft = self._current_draft()
        if draft is None:
            return
        self._pending_draft = draft
        self.status.setText("Testing…")
        self.test_button.setEnabled(False)

        self._thread = QThread(self)
        self._worker = _PingWorker(draft)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_ping_done)
        self._worker.done.connect(self._thread.quit)
        self._thread.start()

    def _on_ping_done(self, ok: bool, message: str) -> None:
        self.test_button.setEnabled(True)
        current = self._current_draft()
        if (
            ok
            and current is not None
            and self._pending_draft is not None
            and current.signature == self._pending_draft.signature
        ):
            self._tested_signature = current.signature
        self.status.setText(message if ok else f"Couldn't connect. {message}")

    def _on_save(self) -> None:
        draft = self._current_draft()
        if draft is None:
            return
        if draft.signature != self._tested_signature:
            self.status.setText("Test this provider configuration before saving.")
            return
        self._write_config(draft)
        self.accept()

    def run(self) -> bool:
        """Show modally; return True when the user completed setup."""
        return self.exec() == QDialog.DialogCode.Accepted
