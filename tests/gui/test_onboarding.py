"""Provider setup keeps unverified credentials out of persistent config."""

from __future__ import annotations

import time
from unittest.mock import Mock

import pytest
import yaml


pytest.importorskip("PySide6")


def test_ping_worker_validates_in_memory_without_persisting(monkeypatch) -> None:
    from chemsmart.cli.config import Config
    from chemsmart.gui.screens.onboarding import (
        ProviderSetupDraft,
        _ping_provider,
    )

    provider = Mock()
    persist = Mock()
    draft = ProviderSetupDraft("openai", "not-a-real-key", "test-model")
    monkeypatch.setattr(draft.__class__, "build_provider", lambda _self: provider)
    monkeypatch.setattr(Config, "write_agent_provider_config", persist)

    context = Mock()
    _ping_provider(draft, context)

    provider.ping.assert_called_once_with()
    context.report_indeterminate.assert_called_once()
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
    assert "not-a-real-key" not in repr(draft.signature)


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


def test_provider_update_preserves_unknown_providers_and_fields(
    tmp_path, monkeypatch
) -> None:
    from chemsmart.cli.config import Config

    destination = tmp_path / ".chemsmart"
    agent_yaml = destination / "agent" / "agent.yaml"
    agent_yaml.parent.mkdir(parents=True)
    agent_yaml.write_text(
        """
active: lab_gateway
custom_top_level: keep-me
providers:
  lab_gateway:
    type: openai
    api_key_env: LAB_KEY
    model: lab-model
    base_url: https://lab.example/v1
    extra_headers:
      X-Lab: keep-me
  openai:
    type: openai
    api_key: old-value
    model: old-model
    custom_provider_field: keep-me
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        Config,
        "chemsmart_dest",
        property(lambda _self: destination),
    )

    Config().write_agent_provider_config(
        "openai",
        api_key_ref="keyring:test.service:openai",
        model="gpt-test",
        base_url="https://api.openai.com/v1",
    )
    payload = yaml.safe_load(agent_yaml.read_text(encoding="utf-8"))

    assert payload["custom_top_level"] == "keep-me"
    assert payload["providers"]["lab_gateway"]["extra_headers"] == {
        "X-Lab": "keep-me"
    }
    assert (
        payload["providers"]["openai"]["custom_provider_field"]
        == "keep-me"
    )
    assert payload["providers"]["openai"]["api_key"] == ""
    assert payload["providers"]["openai"]["api_key_ref"].startswith(
        "keyring:"
    )
    assert agent_yaml.stat().st_mode & 0o777 == 0o600


def test_desktop_save_persists_only_a_keyring_reference(
    qapp, monkeypatch
) -> None:
    from chemsmart.cli.config import Config
    from chemsmart.gui.screens.onboarding import (
        OnboardingDialog,
        ProviderSetupDraft,
    )

    class FakeStore:
        def store(self, account, secret):
            assert account.startswith("openai-")
            assert secret == "private-test-value"
            return f"keyring:test.service:{account}"

        def resolve(self, reference):
            assert reference.startswith("keyring:test.service:openai-")
            return "private-test-value"

        def delete(self, reference):
            raise AssertionError("successful save must not roll back")

    persist = Mock()
    monkeypatch.setattr(Config, "write_agent_provider_config", persist)
    monkeypatch.setattr(
        Config,
        "agent_provider_secret_reference",
        lambda _self, _provider: "",
    )
    dialog = OnboardingDialog(secret_store=FakeStore())
    draft = ProviderSetupDraft("openai", "private-test-value", "gpt-test")

    dialog._write_config(draft)

    kwargs = persist.call_args.kwargs
    assert persist.call_args.args == ("openai",)
    assert kwargs["api_key_ref"].startswith("keyring:test.service:openai-")
    assert kwargs["model"] == "gpt-test"
    assert kwargs["base_url"] == "https://api.openai.com/v1"
    assert "private-test-value" not in repr(persist.call_args)
    dialog.close()


def test_failed_provider_update_removes_only_staged_reference(
    qapp, monkeypatch
) -> None:
    from chemsmart.cli.config import Config
    from chemsmart.gui.screens.onboarding import (
        OnboardingDialog,
        ProviderSetupDraft,
    )

    deleted = []

    class FakeStore:
        staged = ""

        def store(self, account, secret):
            assert account.startswith("openai-")
            assert secret == "new-private-value"
            self.staged = f"keyring:test.service:{account}"
            return self.staged

        def resolve(self, reference):
            assert reference == self.staged
            return "new-private-value"

        def delete(self, reference):
            deleted.append(reference)

    monkeypatch.setattr(
        Config,
        "agent_provider_secret_reference",
        lambda _self, _provider: "keyring:test.service:existing",
    )
    monkeypatch.setattr(
        Config,
        "write_agent_provider_config",
        Mock(side_effect=OSError("simulated atomic write failure")),
    )
    store = FakeStore()
    dialog = OnboardingDialog(secret_store=store)
    draft = ProviderSetupDraft("openai", "new-private-value", "gpt-test")

    with pytest.raises(OSError, match="simulated"):
        dialog._write_config(draft)

    assert deleted == [store.staged]
    assert "keyring:test.service:existing" not in deleted
    dialog.close()


def test_successful_provider_update_commits_then_retires_previous_reference(
    qapp, monkeypatch
) -> None:
    from chemsmart.cli.config import Config
    from chemsmart.gui.screens.onboarding import (
        OnboardingDialog,
        ProviderSetupDraft,
    )

    events = []

    class FakeStore:
        def store(self, account, secret):
            events.append("store-new")
            return f"keyring:test.service:{account}"

        def resolve(self, reference):
            return "new-private-value"

        def delete(self, reference):
            events.append(f"delete:{reference}")

    monkeypatch.setattr(
        Config,
        "agent_provider_secret_reference",
        lambda _self, _provider: "keyring:test.service:existing",
    )

    def persist(_self, *_args, **_kwargs):
        events.append("commit-yaml")

    monkeypatch.setattr(Config, "write_agent_provider_config", persist)
    dialog = OnboardingDialog(secret_store=FakeStore())

    dialog._write_config(
        ProviderSetupDraft("openai", "new-private-value", "gpt-test")
    )

    assert events == [
        "store-new",
        "commit-yaml",
        "delete:keyring:test.service:existing",
    ]
    dialog.close()


def test_save_requires_a_successful_test_for_current_values(qapp, monkeypatch) -> None:
    from chemsmart.gui.screens.onboarding import OnboardingDialog

    dialog = OnboardingDialog()
    persist = Mock()
    monkeypatch.setattr(dialog, "_write_config", persist)
    dialog.api_key.setText("not-a-real-key")

    assert not dialog.save_button.isEnabled()

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
    dialog._refresh_actions()

    assert dialog.save_button.isEnabled()

    dialog._on_save()

    persist.assert_called_once_with(draft)
    assert dialog.result() == dialog.DialogCode.Accepted
    dialog.close()


def test_provider_actions_follow_input_and_exact_tested_signature(qapp) -> None:
    from chemsmart.gui.screens.onboarding import OnboardingDialog

    dialog = OnboardingDialog()
    assert not dialog.test_button.isEnabled()
    assert not dialog.save_button.isEnabled()

    dialog.api_key.setText("not-a-real-key")
    assert dialog.test_button.isEnabled()
    assert not dialog.save_button.isEnabled()

    draft = dialog._current_draft()
    assert draft is not None
    dialog._tested_signature = draft.signature
    dialog._refresh_actions()
    assert dialog.save_button.isEnabled()

    dialog.model.setText("different-model")
    assert not dialog.save_button.isEnabled()
    dialog.close()


def test_timed_out_noncooperative_ping_cannot_hide_live_worker(qapp) -> None:
    from PySide6.QtTest import QTest

    from chemsmart.gui.application.task_controller import TaskStatus
    from chemsmart.gui.screens.onboarding import OnboardingDialog

    dialog = OnboardingDialog()
    dialog.show()

    def noncooperative(_context):
        time.sleep(0.15)
        return "late"

    dialog._task_controller.start(
        noncooperative,
        timeout_ms=20,
        retain_for_retry=False,
    )
    deadline = time.monotonic() + 1
    while dialog._task_controller.snapshot.status is not TaskStatus.TIMED_OUT:
        assert time.monotonic() < deadline
        qapp.processEvents()
        QTest.qWait(5)

    dialog._on_cancel()

    assert dialog.isVisible()
    assert dialog._task_controller.active_thread_count == 1
    deadline = time.monotonic() + 1
    while dialog._task_controller.active_thread_count:
        assert time.monotonic() < deadline
        qapp.processEvents()
        QTest.qWait(5)

    dialog._on_cancel()
    assert not dialog.isVisible()
