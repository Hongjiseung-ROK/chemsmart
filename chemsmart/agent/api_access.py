"""Bounded, no-network API credential access for ChemSmart agents.

This module deliberately does not contain HTTP clients or provider adapters.
It is the narrow boundary future harness and literature integrations use before
they make an explicitly requested network call.  A caller must provide its own
single-use permit, caller label, purpose, and finite request budget; this
module never tops up a quota or starts a network request itself.

When a caller reserves a probe, the chosen secret is held only in a short-lived
in-memory lease bound to that one permit.  The lease is not serializable and is
discarded before any public receipt is returned.

The canonical macOS Keychain locations are intentionally stable and public:

================  =======================================  ==================
provider          service                                  account
================  =======================================  ==================
DeepSeek          ``com.chemsmart.agent.credentials``       ``deepseek_api_key``
Elsevier          ``com.chemsmart.agent.credentials``       ``elsevier_api_key``
SerpAPI           ``com.chemsmart.agent.credentials``       ``serpapi_api_key``
Tavily            ``com.chemsmart.agent.credentials``       ``tavily_api_key``
================  =======================================  ==================

The catalog also records narrowly scoped legacy environment and Keychain
aliases, including the historical ``Elsivier_api_key`` spelling.  Keychain is
always consulted before an environment alias.  Public receipts intentionally
contain no key material, key length, digest, endpoint URL, or remote response.
"""

from __future__ import annotations

import os
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping


CANONICAL_KEYCHAIN_SERVICE = "com.chemsmart.agent.credentials"


class ApiProvider(str, Enum):
    """Providers allowed by this credential contract."""

    DEEPSEEK = "deepseek"
    ELSEVIER = "elsevier"
    SERPAPI = "serpapi"
    TAVILY = "tavily"


class ApiEndpointClass(str, Enum):
    """The sole allowed purpose class for each provider credential."""

    MODEL = "model"
    LITERATURE = "literature"


class CredentialStatus(str, Enum):
    """The only credential states which may be reported publicly."""

    MISSING = "missing"
    AVAILABLE = "available"
    INVALID_ENTITLEMENT = "invalid-entitlement"
    VALID = "valid"


class CredentialSource(str, Enum):
    """Non-secret source metadata for a credential receipt."""

    KEYCHAIN = "keychain"
    ENVIRONMENT = "environment"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class KeychainLocation:
    """A public service/account label, never a credential value."""

    service: str
    account: str


@dataclass(frozen=True, slots=True)
class CredentialLocator:
    """Canonical and explicit legacy locations for one provider secret."""

    provider: ApiProvider
    endpoint_class: ApiEndpointClass
    canonical_keychain: KeychainLocation
    legacy_keychain: tuple[KeychainLocation, ...]
    environment_aliases: tuple[str, ...]

    @property
    def keychain_locations(self) -> tuple[KeychainLocation, ...]:
        """Return canonical first, followed by documented legacy aliases."""

        return (self.canonical_keychain, *self.legacy_keychain)


_LEGACY_KEYCHAIN_SERVICE = "com.chemsmart"


CREDENTIAL_LOCATORS: Mapping[ApiProvider, CredentialLocator] = MappingProxyType({
    ApiProvider.DEEPSEEK: CredentialLocator(
        provider=ApiProvider.DEEPSEEK,
        endpoint_class=ApiEndpointClass.MODEL,
        canonical_keychain=KeychainLocation(
            CANONICAL_KEYCHAIN_SERVICE, "deepseek_api_key"
        ),
        legacy_keychain=(
            KeychainLocation(_LEGACY_KEYCHAIN_SERVICE, "DEEPSEEK_API_KEY"),
        ),
        environment_aliases=(
            "CHEMSMART_DEEPSEEK_API_KEY",
            "DEEPSEEK_API_KEY",
        ),
    ),
    ApiProvider.ELSEVIER: CredentialLocator(
        provider=ApiProvider.ELSEVIER,
        endpoint_class=ApiEndpointClass.LITERATURE,
        canonical_keychain=KeychainLocation(
            CANONICAL_KEYCHAIN_SERVICE, "elsevier_api_key"
        ),
        legacy_keychain=(
            KeychainLocation(_LEGACY_KEYCHAIN_SERVICE, "ELSEVIER_API_KEY"),
            KeychainLocation(_LEGACY_KEYCHAIN_SERVICE, "Elsivier_api_key"),
        ),
        environment_aliases=(
            "CHEMSMART_ELSEVIER_API_KEY",
            "ELSEVIER_API_KEY",
            "Elsivier_api_key",
        ),
    ),
    ApiProvider.SERPAPI: CredentialLocator(
        provider=ApiProvider.SERPAPI,
        endpoint_class=ApiEndpointClass.LITERATURE,
        canonical_keychain=KeychainLocation(
            CANONICAL_KEYCHAIN_SERVICE, "serpapi_api_key"
        ),
        legacy_keychain=(
            KeychainLocation(_LEGACY_KEYCHAIN_SERVICE, "SERPAPI_API_KEY"),
        ),
        environment_aliases=(
            "CHEMSMART_SERPAPI_API_KEY",
            "SERPAPI_API_KEY",
        ),
    ),
    ApiProvider.TAVILY: CredentialLocator(
        provider=ApiProvider.TAVILY,
        endpoint_class=ApiEndpointClass.LITERATURE,
        canonical_keychain=KeychainLocation(
            CANONICAL_KEYCHAIN_SERVICE, "tavily_api_key"
        ),
        legacy_keychain=(
            KeychainLocation(_LEGACY_KEYCHAIN_SERVICE, "TAVILY_API_KEY"),
        ),
        environment_aliases=(
            "CHEMSMART_TAVILY_API_KEY",
            "TAVILY_API_KEY",
        ),
    ),
})


class CredentialAccessError(RuntimeError):
    """Base error whose messages never include credential material."""


class CredentialUnavailableError(CredentialAccessError):
    """Raised when a caller requests a probe without a local credential."""


class UsageBudgetError(CredentialAccessError):
    """Raised when a finite caller-owned network budget is exhausted."""


class CredentialProbeError(CredentialAccessError):
    """Raised when an explicit probe fails to yield an allowed status."""


KeychainReader = Callable[[str, str], str | None]


def read_macos_keychain(service: str, account: str) -> str | None:
    """Read one generic-password item without logging its value or errors.

    This is a local Keychain lookup, not a network operation.  It is kept as a
    small injectable adapter so tests and non-macOS callers never have to
    invoke ``security``.
    """

    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                service,
                "-a",
                account,
                "-w",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    secret = result.stdout.rstrip("\r\n")
    return secret or None


@dataclass(frozen=True, slots=True)
class CredentialStatusReceipt:
    """A safe-to-persist observation with no secret-derived fields."""

    provider: ApiProvider
    status: CredentialStatus
    source: CredentialSource
    credential_locator: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, CredentialStatus):
            raise TypeError("status must be a CredentialStatus")
        if not isinstance(self.provider, ApiProvider):
            raise TypeError("provider must be an ApiProvider")
        if not isinstance(self.source, CredentialSource):
            raise TypeError("source must be a CredentialSource")

    def to_public_dict(self) -> dict[str, str]:
        """Return the deliberately small, safe evidence representation."""

        return {
            "provider": self.provider.value,
            "status": self.status.value,
            "source": self.source.value,
            "credential_locator": self.credential_locator,
        }


@dataclass(frozen=True, slots=True)
class CredentialProbeObservation:
    """A caller-supplied, non-secret conclusion from one authorized probe."""

    status: CredentialStatus

    def __post_init__(self) -> None:
        if not isinstance(self.status, CredentialStatus):
            raise TypeError("status must be a CredentialStatus")
        if self.status not in {
            CredentialStatus.VALID,
            CredentialStatus.INVALID_ENTITLEMENT,
        }:
            raise ValueError(
                "A credential probe may conclude only valid or "
                "invalid-entitlement."
            )


class ApiUsageBudget:
    """A finite, caller-owned request budget with no top-up operation."""

    def __init__(self, max_network_requests: int) -> None:
        if (
            not isinstance(max_network_requests, int)
            or isinstance(max_network_requests, bool)
            or max_network_requests <= 0
        ):
            raise ValueError("max_network_requests must be a positive integer")
        self._max_network_requests = max_network_requests
        self._reserved_requests = 0
        self._lock = threading.Lock()

    @property
    def max_network_requests(self) -> int:
        """Return the fixed maximum supplied by the caller."""

        return self._max_network_requests

    @property
    def remaining_network_requests(self) -> int:
        """Return the unreserved portion without exposing credential data."""

        with self._lock:
            return self._max_network_requests - self._reserved_requests

    def _reserve_one(self) -> None:
        with self._lock:
            if self._reserved_requests >= self._max_network_requests:
                raise UsageBudgetError("The caller-owned network budget is exhausted.")
            self._reserved_requests += 1


@dataclass(frozen=True, slots=True)
class CredentialProbePermit:
    """One non-transferable-looking, single-use authorization handle.

    The permit contains no key and reserves exactly one request from the
    explicit ``ApiUsageBudget`` that created it.
    """

    permit_id: str
    provider: ApiProvider
    endpoint_class: ApiEndpointClass
    caller: str
    purpose: str
    reserved_requests: int = 1


@dataclass(frozen=True, slots=True)
class _CredentialLease:
    """Private one-permit credential state; never serialized or logged."""

    secret: str = field(repr=False)
    source: CredentialSource
    locator: str


class CredentialAccessController:
    """Resolve local credentials and authorize bounded, caller-owned probes.

    ``invoke_authorized_probe`` is intentionally transport-agnostic: it only
    passes a secret to an explicitly supplied operation after checking a
    caller-labelled, one-shot permit.  The operation is responsible for any
    HTTP client and must return a ``CredentialProbeObservation``.  No method
    here constructs a request, selects an endpoint, or alters billing/quota.
    """

    def __init__(
        self,
        *,
        keychain_reader: KeychainReader = read_macos_keychain,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self._keychain_reader = keychain_reader
        self._environment = os.environ if environment is None else environment
        self._permits: dict[
            str, tuple[CredentialProbePermit, _CredentialLease]
        ] = {}
        self._used_permits: set[str] = set()
        self._lock = threading.Lock()

    def credential_locator(self, provider: ApiProvider) -> CredentialLocator:
        """Return public setup metadata for a supported provider."""

        return CREDENTIAL_LOCATORS[provider]

    def credential_status(self, provider: ApiProvider) -> CredentialStatusReceipt:
        """Report local availability only; this method never probes a provider."""

        resolved = self._resolve(provider)
        if resolved is None:
            return CredentialStatusReceipt(
                provider=provider,
                status=CredentialStatus.MISSING,
                source=CredentialSource.NONE,
                credential_locator=CREDENTIAL_LOCATORS[
                    provider
                ].canonical_keychain.account,
            )
        return CredentialStatusReceipt(
            provider=provider,
            status=CredentialStatus.AVAILABLE,
            source=resolved.source,
            credential_locator=resolved.locator,
        )

    def prepare_status_probe(
        self,
        provider: ApiProvider,
        *,
        caller: str,
        purpose: str,
        budget: ApiUsageBudget,
    ) -> CredentialProbePermit:
        """Reserve one explicit network request without making it.

        A real probe remains impossible until the caller subsequently invokes
        the returned permit with its own transport callback.
        """

        caller = _require_label(caller, "caller")
        purpose = _require_label(purpose, "purpose")
        resolved = self._resolve(provider)
        if resolved is None:
            raise CredentialUnavailableError(
                f"No local credential is available for {provider.value}."
            )
        budget._reserve_one()
        locator = CREDENTIAL_LOCATORS[provider]
        permit = CredentialProbePermit(
            permit_id=uuid.uuid4().hex,
            provider=provider,
            endpoint_class=locator.endpoint_class,
            caller=caller,
            purpose=purpose,
        )
        with self._lock:
            self._permits[permit.permit_id] = (permit, resolved)
        return permit

    def invoke_authorized_probe(
        self,
        permit: CredentialProbePermit,
        operation: Callable[[str], CredentialProbeObservation],
    ) -> CredentialStatusReceipt:
        """Invoke a caller-owned probe once and return only a safe receipt.

        The callback is the sole place a network client may be used.  It gets
        the secret only in process and must return a typed status rather than
        a response body, exception text, or secret.
        """

        if not callable(operation):
            raise TypeError("operation must be a callable credential probe")
        with self._lock:
            if permit.reserved_requests != 1:
                raise CredentialProbeError("A probe permit must reserve one request.")
            if permit.permit_id in self._used_permits:
                raise CredentialProbeError("A credential probe permit is single-use.")
            stored = self._permits.pop(permit.permit_id, None)
            if stored is None:
                raise CredentialProbeError("Unknown credential probe permit.")
            stored_permit, resolved = stored
            if permit != stored_permit:
                raise CredentialProbeError("Credential probe permit was altered.")
            self._used_permits.add(permit.permit_id)

        try:
            observation = operation(resolved.secret)
        except Exception:
            raise CredentialProbeError(
                "The credential probe did not return an allowed status."
            ) from None
        if not isinstance(observation, CredentialProbeObservation):
            raise CredentialProbeError(
                "The credential probe must return CredentialProbeObservation."
            )
        return CredentialStatusReceipt(
            provider=permit.provider,
            status=observation.status,
            source=resolved.source,
            credential_locator=resolved.locator,
        )

    def _resolve(self, provider: ApiProvider) -> _CredentialLease | None:
        locator = CREDENTIAL_LOCATORS[provider]
        for location in locator.keychain_locations:
            secret = self._keychain_reader(location.service, location.account)
            if secret:
                return _CredentialLease(
                    secret=secret,
                    source=CredentialSource.KEYCHAIN,
                    locator=location.account,
                )
        for alias in locator.environment_aliases:
            secret = self._environment.get(alias, "")
            if secret:
                return _CredentialLease(
                    secret=secret,
                    source=CredentialSource.ENVIRONMENT,
                    locator=alias,
                )
        return None


def _require_label(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty text label")
    return value.strip()
