"""Provider setup keeps unverified credentials out of persistent config."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
import yaml


pytest.importorskip("PySide6")


def test_ping_worker_validates_in_memory_without_persisting(monkeypatch) -> None:
    from chemsmart.cli.config import Config
    from chemsmart.gui.screens.onboarding import (
        ProviderSetupDraft,
        _PingWorker,
    )

    provider = Mock()
    persist = Mock()
    draft = ProviderSetupDraft("openai", "not-a-real-key", "test-model")
    monkeypatch.setattr(draft.__class__, "build_provider", lambda _self: provider)
    monkeypatch.setattr(Config, "write_agent_provider_config", persist)

    worker = _PingWorker(draft)
    worker.run()

    provider.ping.assert_called_once_with()
    persist.assert_not_called()


@pytest.mark.parametrize(
    ("provider_type", "expected_url", "provider_class"),
    [
        ("openai", "https://api.openai.com/v1", "OpenAIProvider"),
        ("anthropic", "https://api.anthropic.com", "AnthropicProvider"),
    ],
)
def test_provider_draft_uses_explicit_first_party_endpoint(
    monkeypatch, provider_type, expected_url, provider_class
) -> None:
    import chemsmart.agent.providers as providers
    from chemsmart.gui.screens.onboarding import ProviderSetupDraft

    constructor = Mock(return_value=Mock())
    monkeypatch.setattr(providers, provider_class, constructor)
    draft = ProviderSetupDraft(provider_type, "not-a-real-key", "test-model")

    draft.build_provider()

    constructor.assert_called_once_with(
        "not-a-real-key",
        model="test-model",
        base_url=expected_url,
    )


def test_provider_draft_repr_redacts_the_api_key() -> None:
    from chemsmart.gui.screens.onboarding import ProviderSetupDraft

    draft = ProviderSetupDraft("openai", "not-a-real-key", "test-model")

    assert "not-a-real-key" not in repr(draft)


@pytest.mark.parametrize(
    ("provider_type", "expected_url"),
    [
        ("openai", "https://api.openai.com/v1"),
        ("anthropic", "https://api.anthropic.com"),
    ],
)
def test_saved_desktop_provider_keeps_the_reviewed_endpoint(
    tmp_path, monkeypatch, provider_type, expected_url
) -> None:
    from chemsmart.cli.config import Config

    destination = tmp_path / ".chemsmart"
    monkeypatch.setattr(
        Config,
        "chemsmart_dest",
        property(lambda _self: destination),
    )
    config = Config()

    path = config.write_agent_provider_config(
        provider_type,
        api_key="placeholder-test-key",
        model="test-model",
        base_url=expected_url,
    )
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert payload["providers"][provider_type]["base_url"] == expected_url


def test_save_requires_a_successful_test_for_current_values(qapp, monkeypatch) -> None:
    from chemsmart.gui.screens.onboarding import OnboardingDialog

    dialog = OnboardingDialog()
    persist = Mock()
    monkeypatch.setattr(dialog, "_write_config", persist)
    dialog.api_key.setText("not-a-real-key")

    dialog._on_save()

    persist.assert_not_called()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert "Test" in dialog.status.text()
    dialog.close()


def test_save_persists_only_the_exact_tested_values(qapp, monkeypatch) -> None:
    from chemsmart.gui.screens.onboarding import OnboardingDialog

    dialog = OnboardingDialog()
    persist = Mock()
    monkeypatch.setattr(dialog, "_write_config", persist)
    dialog.api_key.setText("not-a-real-key")
    draft = dialog._current_draft()
    assert draft is not None
    dialog._tested_signature = draft.signature

    dialog._on_save()

    persist.assert_called_once_with(draft)
    assert dialog.result() == dialog.DialogCode.Accepted
    dialog.close()
