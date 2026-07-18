"""Secret references for provider credentials.

The configuration file stores an opaque reference while the credential stays
in the operating-system credential store.  ``keyring`` selects the native
backend (macOS Keychain for the desktop target and Windows Credential Manager
for the later Windows port) without exposing a platform command to callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4


_REFERENCE_SCHEME = "keyring"
_DEFAULT_SERVICE = "org.zhanglab.chemsmart.agent"


class SecretStoreError(RuntimeError):
    """Raised when a credential cannot be stored or resolved safely."""


class SecretStore(Protocol):
    """Minimal cross-platform credential-store boundary."""

    def store(self, account: str, secret: str) -> str:
        """Persist ``secret`` and return an opaque configuration reference."""

    def resolve(self, reference: str) -> str:
        """Resolve an opaque reference into process memory."""

    def delete(self, reference: str) -> None:
        """Delete a referenced secret when rolling back a failed write."""


@dataclass(frozen=True)
class SecretReference:
    """Parsed, non-secret identity for one credential-store entry."""

    service: str
    account: str

    def encode(self) -> str:
        return f"{_REFERENCE_SCHEME}:{self.service}:{self.account}"

    @classmethod
    def parse(cls, value: str) -> "SecretReference":
        try:
            scheme, service, account = value.split(":", 2)
        except ValueError as exc:
            raise SecretStoreError("Malformed provider secret reference.") from exc
        if scheme != _REFERENCE_SCHEME or not service or not account:
            raise SecretStoreError("Unsupported provider secret reference.")
        return cls(service=service, account=account)


class KeyringSecretStore:
    """Credential store backed by the native backend selected by keyring."""

    def __init__(self, *, service: str = _DEFAULT_SERVICE) -> None:
        if not service.strip() or ":" in service:
            raise ValueError("Credential service must be non-empty and colon-free.")
        self._service = service

    def store(self, account: str, secret: str) -> str:
        account = _validate_account(account)
        if not secret:
            raise SecretStoreError("Cannot store an empty provider credential.")
        keyring = _keyring_module()
        try:
            keyring.set_password(self._service, account, secret)
        except Exception as exc:
            raise SecretStoreError(
                "The system credential store rejected the provider credential."
            ) from exc
        return SecretReference(self._service, account).encode()

    def resolve(self, reference: str) -> str:
        parsed = SecretReference.parse(reference)
        self._require_owned_service(parsed)
        keyring = _keyring_module()
        try:
            secret = keyring.get_password(parsed.service, parsed.account)
        except Exception as exc:
            raise SecretStoreError(
                "The provider credential could not be read from the system store."
            ) from exc
        if not secret:
            raise SecretStoreError(
                "The provider credential is missing from the system store."
            )
        return secret

    def delete(self, reference: str) -> None:
        parsed = SecretReference.parse(reference)
        self._require_owned_service(parsed)
        keyring = _keyring_module()
        try:
            keyring.delete_password(parsed.service, parsed.account)
        except Exception as exc:
            # Keyring backends do not expose a uniform "not found" exception.
            # Rollback is best-effort, but backend failures remain visible.
            raise SecretStoreError(
                "The provider credential could not be removed from the system store."
            ) from exc

    def _require_owned_service(self, reference: SecretReference) -> None:
        if reference.service != self._service:
            raise SecretStoreError(
                "The provider secret reference belongs to a different service."
            )


def _validate_account(account: str) -> str:
    normalized = account.strip()
    if not normalized or ":" in normalized:
        raise ValueError("Credential account must be non-empty and colon-free.")
    return normalized


def new_secret_account(provider: str) -> str:
    """Return a unique staging account for one credential transaction."""
    normalized = _validate_account(provider)
    return f"{normalized}-{uuid4().hex}"


def _keyring_module():
    try:
        import keyring
    except ImportError as exc:
        raise SecretStoreError(
            "System credential support is unavailable in this installation."
        ) from exc
    return keyring


__all__ = [
    "KeyringSecretStore",
    "new_secret_account",
    "SecretReference",
    "SecretStore",
    "SecretStoreError",
]
