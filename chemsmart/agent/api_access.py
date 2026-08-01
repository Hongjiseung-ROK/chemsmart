"""Bounded, no-network API credential access for ChemSmart agents.

This module deliberately does not contain HTTP clients or provider adapters.
It is the narrow boundary future harness and literature integrations use before
they make an explicitly requested network call.  A caller must provide its own
single-use permit, caller label, purpose, and finite request budget; this
module never tops up a quota or starts a network request itself.

When a caller reserves a probe, only its public source locator is retained.
The secret is reacquired from that exact locator immediately before the
single authorized callback and is never stored in the pending-permit table.

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

import math
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping
from urllib.parse import urlsplit


CANONICAL_KEYCHAIN_SERVICE = "com.chemsmart.agent.credentials"


class ApiProvider(str, Enum):
    """Providers allowed by this credential contract."""

    DEEPSEEK = "deepseek"
    ELSEVIER = "elsevier"
    SERPAPI = "serpapi"
    TAVILY = "tavily"


CANONICAL_API_ORIGINS = MappingProxyType({
    ApiProvider.DEEPSEEK: "https://api.deepseek.com",
    ApiProvider.ELSEVIER: "https://api.elsevier.com",
    ApiProvider.SERPAPI: "https://serpapi.com",
    ApiProvider.TAVILY: "https://api.tavily.com",
})


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
            "DEEPSEEK-api-key",
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
            "SerpApi_api_key",
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
            "Tavily_api_key",
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
    target_origin: str
    caller: str
    purpose: str
    expires_at_monotonic: float
    reserved_requests: int = 1


@dataclass(frozen=True, slots=True)
class _CredentialReference:
    """Secret-free source reference retained by one pending permit."""

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
        permit_ttl_seconds: float = 60.0,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if (
            not isinstance(permit_ttl_seconds, (int, float))
            or isinstance(permit_ttl_seconds, bool)
            or not math.isfinite(permit_ttl_seconds)
            or permit_ttl_seconds <= 0
            or permit_ttl_seconds > 300
        ):
            raise ValueError(
                "permit_ttl_seconds must be finite and in the range (0, 300]"
            )
        if not callable(monotonic_clock):
            raise TypeError("monotonic_clock must be callable")
        self._keychain_reader = keychain_reader
        self._environment = os.environ if environment is None else environment
        self._permit_ttl_seconds = float(permit_ttl_seconds)
        self._monotonic_clock = monotonic_clock
        self._permits: dict[
            str, tuple[CredentialProbePermit, _CredentialReference]
        ] = {}
        self._used_permits: set[str] = set()
        self._lock = threading.Lock()

    def credential_locator(self, provider: ApiProvider) -> CredentialLocator:
        """Return public setup metadata for a supported provider."""

        return CREDENTIAL_LOCATORS[provider]

    def credential_status(self, provider: ApiProvider) -> CredentialStatusReceipt:
        """Report local availability only; this method never probes a provider."""

        resolved = self._resolve_reference(provider)
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
        target_origin: str | None = None,
    ) -> CredentialProbePermit:
        """Reserve one explicit network request without making it.

        A real probe remains impossible until the caller subsequently invokes
        the returned permit with its own transport callback.
        """

        caller = _require_label(caller, "caller")
        purpose = _require_label(purpose, "purpose")
        origin = _require_provider_origin(provider, target_origin)
        reference = self._resolve_reference(provider)
        if reference is None:
            raise CredentialUnavailableError(
                f"No local credential is available for {provider.value}."
            )
        budget._reserve_one()
        locator = CREDENTIAL_LOCATORS[provider]
        permit = CredentialProbePermit(
            permit_id=uuid.uuid4().hex,
            provider=provider,
            endpoint_class=locator.endpoint_class,
            target_origin=origin,
            caller=caller,
            purpose=purpose,
            expires_at_monotonic=(
                self._monotonic_clock() + self._permit_ttl_seconds
            ),
        )
        with self._lock:
            self._permits[permit.permit_id] = (permit, reference)
        return permit

    def invoke_authorized_probe(
        self,
        permit: CredentialProbePermit,
        operation: Callable[[str, str], CredentialProbeObservation],
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
            stored_permit, reference = stored
            if permit != stored_permit:
                self._used_permits.add(permit.permit_id)
                raise CredentialProbeError("Credential probe permit was altered.")
            self._used_permits.add(permit.permit_id)
            if self._monotonic_clock() >= permit.expires_at_monotonic:
                raise CredentialProbeError("Credential probe permit expired.")

        try:
            secret = self._read_reference(permit.provider, reference)
            if not secret:
                raise CredentialUnavailableError
            observation = operation(secret, permit.target_origin)
        except Exception:
            raise CredentialProbeError(
                "The credential probe did not return an allowed status."
            ) from None
        finally:
            secret = None
        if not isinstance(observation, CredentialProbeObservation):
            raise CredentialProbeError(
                "The credential probe must return CredentialProbeObservation."
            )
        return CredentialStatusReceipt(
            provider=permit.provider,
            status=observation.status,
            source=reference.source,
            credential_locator=reference.locator,
        )

    def cancel_probe(self, permit: CredentialProbePermit) -> bool:
        """Cancel an exact pending permit without refunding its budget."""

        with self._lock:
            if permit.permit_id in self._used_permits:
                return False
            stored = self._permits.pop(permit.permit_id, None)
            if stored is None:
                return False
            stored_permit, _ = stored
            self._used_permits.add(permit.permit_id)
            if permit != stored_permit:
                raise CredentialProbeError("Credential probe permit was altered.")
            return True

    def cleanup_expired(self) -> int:
        """Invalidate expired pending permits and return the removal count."""

        now = self._monotonic_clock()
        with self._lock:
            expired = [
                permit_id
                for permit_id, (permit, _) in self._permits.items()
                if now >= permit.expires_at_monotonic
            ]
            for permit_id in expired:
                self._permits.pop(permit_id, None)
                self._used_permits.add(permit_id)
        return len(expired)

    def _resolve_reference(
        self, provider: ApiProvider
    ) -> _CredentialReference | None:
        locator = CREDENTIAL_LOCATORS[provider]
        for location in locator.keychain_locations:
            secret = self._keychain_reader(location.service, location.account)
            if secret:
                return _CredentialReference(
                    source=CredentialSource.KEYCHAIN,
                    locator=location.account,
                )
        for alias in locator.environment_aliases:
            secret = self._environment.get(alias, "")
            if secret:
                return _CredentialReference(
                    source=CredentialSource.ENVIRONMENT,
                    locator=alias,
                )
        return None

    def _read_reference(
        self,
        provider: ApiProvider,
        reference: _CredentialReference,
    ) -> str | None:
        locator = CREDENTIAL_LOCATORS[provider]
        if reference.source is CredentialSource.KEYCHAIN:
            for location in locator.keychain_locations:
                if location.account == reference.locator:
                    return self._keychain_reader(
                        location.service, location.account
                    )
            return None
        if (
            reference.source is CredentialSource.ENVIRONMENT
            and reference.locator in locator.environment_aliases
        ):
            return self._environment.get(reference.locator) or None
        return None


def _require_label(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty text label")
    return value.strip()


def _require_provider_origin(
    provider: ApiProvider,
    value: str | None,
) -> str:
    expected = CANONICAL_API_ORIGINS[provider]
    candidate = expected if value is None else value
    if not isinstance(candidate, str) or not candidate.strip():
        raise ValueError("target_origin must be a non-empty HTTPS origin")
    try:
        parsed = urlsplit(candidate.strip())
        port = parsed.port
    except ValueError as exc:
        raise ValueError("target_origin must be a valid HTTPS origin") from exc
    if (
        parsed.scheme.lower() != "https"
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.hostname
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("target_origin must be an exact HTTPS origin")
    host = parsed.hostname.lower()
    normalized = f"https://{host}"
    if port not in {None, 443}:
        normalized = f"{normalized}:{port}"
    if normalized != expected:
        raise ValueError(
            f"target_origin is not authorized for {provider.value}"
        )
    return normalized
