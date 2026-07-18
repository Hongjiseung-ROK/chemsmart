"""Credential references never contain or log provider secrets."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from chemsmart.agent import secrets


def test_keyring_store_round_trip_uses_opaque_reference(monkeypatch) -> None:
    backend = Mock()
    backend.get_password.return_value = "private-test-value"
    monkeypatch.setattr(secrets, "_keyring_module", lambda: backend)
    store = secrets.KeyringSecretStore()

    reference = store.store("openai", "private-test-value")

    assert "private-test-value" not in reference
    assert reference == "keyring:org.zhanglab.chemsmart.agent:openai"
    assert store.resolve(reference) == "private-test-value"
    backend.set_password.assert_called_once_with(
        "org.zhanglab.chemsmart.agent",
        "openai",
        "private-test-value",
    )


def test_keyring_error_does_not_echo_secret(monkeypatch) -> None:
    backend = Mock()
    backend.set_password.side_effect = RuntimeError("backend rejected value")
    monkeypatch.setattr(secrets, "_keyring_module", lambda: backend)

    with pytest.raises(secrets.SecretStoreError) as raised:
        secrets.KeyringSecretStore().store("openai", "private-test-value")

    assert "private-test-value" not in str(raised.value)


def test_keyring_store_rejects_foreign_service_reference(monkeypatch) -> None:
    backend = Mock()
    monkeypatch.setattr(secrets, "_keyring_module", lambda: backend)
    store = secrets.KeyringSecretStore()

    with pytest.raises(secrets.SecretStoreError, match="different service"):
        store.resolve("keyring:unrelated.application:openai")

    backend.get_password.assert_not_called()


@pytest.mark.parametrize(
    "reference",
    ["", "environment:service:account", "keyring::account", "keyring:service"],
)
def test_secret_reference_rejects_malformed_values(reference: str) -> None:
    with pytest.raises(secrets.SecretStoreError):
        secrets.SecretReference.parse(reference)
