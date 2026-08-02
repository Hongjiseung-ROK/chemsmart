"""Bounded, provider-scoped literature acquisition with public receipts.

The client in this module is transport- and credential-source agnostic.  It
constructs requests only for the exact Elsevier, SerpAPI, and Tavily HTTPS
origins, consumes a finite per-provider request budget, and accepts injected
transports for offline tests or future wire adapters.  Credentials and source
content are passed ephemerally and are never retained in a receipt.

Retrieved full text is written through an injected private evidence store.
Public receipts retain only canonical locators, hashes, byte sizes, content
classes, and opaque ``private-store:`` references.  Search discoveries remain
explicitly metadata-only and cannot satisfy a full-text evidence requirement.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from chemsmart.agent.api_access import ApiProvider
from chemsmart.agent.bibliographic_evidence import (
    CROSSREF_ORIGIN,
    BibliographicAuthorV1,
    BibliographicConcordanceReceiptV1,
    BibliographicConcordanceStatus,
    BibliographicCorrectionRelationV1,
    BibliographicObservationV1,
    CrossrefMetadataRequestV1,
    CrossrefRepresentation,
    CrossrefResponseReceiptV1,
    CrossrefResponseStatus,
    NormalizedBibliographicRecordV1,
    build_bibliographic_concordance_receipt_v1,
    build_bibliographic_observation_v1,
    build_crossref_metadata_request_v1,
    build_crossref_response_receipt_v1,
    crossref_request_path,
)


LITERATURE_REQUEST_SCHEMA_VERSION = "chemsmart.literature-request.v1"
LITERATURE_REQUEST_RECEIPT_SCHEMA_VERSION = (
    "chemsmart.literature-request-receipt.v1"
)
LITERATURE_RESPONSE_RECEIPT_SCHEMA_VERSION = (
    "chemsmart.literature-response-receipt.v1"
)
LITERATURE_SOURCE_RECEIPT_SCHEMA_VERSION = (
    "chemsmart.literature-source-receipt.v1"
)
LITERATURE_MERGE_RECEIPT_SCHEMA_VERSION = (
    "chemsmart.literature-merge-receipt.v1"
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
_SHA256 = r"^[0-9a-f]{64}$"
_RULE_ID = r"^[a-z][a-z0-9_.-]{0,191}$"
_MEDIA_TYPE = r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+/-]{0,126}$"
_PRIVATE_STORE_REF = r"^private-store:[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
_NO_CONTROL = re.compile(r"^[^\x00-\x1f\x7f]+$")
_SENSITIVE_LOCATOR_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "key",
        "secret",
        "sig",
        "signature",
        "token",
        "x-amz-credential",
        "x-amz-signature",
        "x-goog-credential",
        "x-goog-signature",
    }
)


LITERATURE_PROVIDERS = (
    ApiProvider.ELSEVIER,
    ApiProvider.SERPAPI,
    ApiProvider.TAVILY,
)

LITERATURE_PROVIDER_ORIGINS: Mapping[ApiProvider, str] = MappingProxyType(
    {
        ApiProvider.ELSEVIER: "https://api.elsevier.com",
        ApiProvider.SERPAPI: "https://serpapi.com",
        ApiProvider.TAVILY: "https://api.tavily.com",
    }
)


class LiteratureAcquisitionAction(str, Enum):
    METADATA = "metadata"
    FULL_TEXT = "full_text"
    DISCOVER = "discover"


class LiteratureContentClass(str, Enum):
    ARTICLE_METADATA = "article_metadata"
    ARTICLE_FULL_TEXT = "article_full_text"
    SUPPORTING_INFORMATION = "supporting_information"
    DATASET = "dataset"
    CODE = "code"
    CITED_PROTOCOL = "cited_protocol"


class LiteratureContentState(str, Enum):
    METADATA_ONLY = "metadata_only"
    RETRIEVED = "retrieved"
    DISCOVERED = "discovered"


class LiteratureDigestBasis(str, Enum):
    CONTENT_BYTES = "content_bytes"
    CANONICAL_LOCATOR = "canonical_locator"


class LiteratureResponseStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    INVALID_ENTITLEMENT = "invalid_entitlement"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"


class LiteratureAcquisitionError(RuntimeError):
    """Base public error whose message contains no secret or response body."""


class LiteratureBudgetExhaustedError(LiteratureAcquisitionError):
    pass


class LiteratureRequestConflictError(LiteratureAcquisitionError):
    pass


class LiteratureCredentialUnavailableError(LiteratureAcquisitionError):
    pass


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class LiteratureAcquisitionRequest(_Contract):
    """Ephemeral acquisition intent; its raw query is hashed in receipts."""

    schema_version: str = Field(
        default=LITERATURE_REQUEST_SCHEMA_VERSION,
        pattern=r"^chemsmart\.literature-request\.v1$",
    )
    request_id: str = Field(pattern=_IDENTIFIER)
    provider: ApiProvider
    action: LiteratureAcquisitionAction
    query: str = Field(min_length=1, max_length=1024, repr=False)
    requested_content_classes: tuple[LiteratureContentClass, ...] = Field(
        min_length=1
    )
    max_results: int = Field(default=10, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def _query_is_safe_ephemeral_text(cls, value: str) -> str:
        if not _NO_CONTROL.fullmatch(value):
            raise ValueError("literature query contains control characters")
        return value

    @field_validator("requested_content_classes")
    @classmethod
    def _content_classes_are_canonical(
        cls,
        values: tuple[LiteratureContentClass, ...],
    ) -> tuple[LiteratureContentClass, ...]:
        if len(values) != len(set(values)):
            raise ValueError("requested content classes must be unique")
        return tuple(sorted(values, key=lambda item: item.value))

    @model_validator(mode="after")
    def _provider_action_surface_is_exact(self) -> "LiteratureAcquisitionRequest":
        classes = set(self.requested_content_classes)
        if self.provider is ApiProvider.ELSEVIER:
            expected = {
                LiteratureAcquisitionAction.METADATA: {
                    LiteratureContentClass.ARTICLE_METADATA
                },
                LiteratureAcquisitionAction.FULL_TEXT: {
                    LiteratureContentClass.ARTICLE_FULL_TEXT
                },
            }
            if self.action not in expected or classes != expected[self.action]:
                raise ValueError(
                    "Elsevier accepts exactly article metadata or article full text"
                )
        elif self.provider is ApiProvider.SERPAPI:
            discovery_classes = {
                LiteratureContentClass.SUPPORTING_INFORMATION,
                LiteratureContentClass.DATASET,
                LiteratureContentClass.CODE,
                LiteratureContentClass.CITED_PROTOCOL,
            }
            if (
                self.action is not LiteratureAcquisitionAction.DISCOVER
                or not classes.issubset(discovery_classes)
            ):
                raise ValueError(
                    "SerpAPI is restricted to literature discovery"
                )
        elif self.provider is ApiProvider.TAVILY:
            discovery_classes = {
                LiteratureContentClass.SUPPORTING_INFORMATION,
                LiteratureContentClass.DATASET,
                LiteratureContentClass.CODE,
                LiteratureContentClass.CITED_PROTOCOL,
            }
            if self.action is LiteratureAcquisitionAction.FULL_TEXT:
                if classes != {LiteratureContentClass.ARTICLE_FULL_TEXT}:
                    raise ValueError(
                        "Tavily full-text extraction requires article_full_text"
                    )
            elif (
                self.action is not LiteratureAcquisitionAction.DISCOVER
                or not classes.issubset(discovery_classes)
            ):
                raise ValueError(
                    "Tavily accepts literature discovery or private full-text "
                    "extraction"
                )
        else:
            raise ValueError("provider is not a literature acquisition provider")
        return self


class LiteratureRequestReceipt(_Contract):
    schema_version: str = Field(
        default=LITERATURE_REQUEST_RECEIPT_SCHEMA_VERSION,
        pattern=r"^chemsmart\.literature-request-receipt\.v1$",
    )
    request_receipt_id: str = Field(pattern=_IDENTIFIER)
    request_id: str = Field(pattern=_IDENTIFIER)
    provider: ApiProvider
    origin: str
    action: LiteratureAcquisitionAction
    query_sha256: str = Field(pattern=_SHA256)
    requested_content_classes: tuple[LiteratureContentClass, ...]
    max_results: int = Field(ge=1, le=50)
    budget_id: str = Field(pattern=_IDENTIFIER)
    provider_request_ordinal: int = Field(ge=1)
    provider_request_limit: int = Field(ge=1)
    request_receipt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _receipt_is_exact_and_content_addressed(self) -> "LiteratureRequestReceipt":
        if self.provider not in LITERATURE_PROVIDER_ORIGINS:
            raise ValueError("request receipt provider is not literature-scoped")
        if self.origin != LITERATURE_PROVIDER_ORIGINS[self.provider]:
            raise ValueError("request receipt origin is not the exact provider origin")
        if self.provider_request_ordinal > self.provider_request_limit:
            raise ValueError("request receipt exceeds its finite provider budget")
        if self.request_receipt_sha256 != literature_request_receipt_sha256(self):
            raise ValueError("literature request receipt digest mismatch")
        return self


class PrivateStoreWriteReceipt(_Contract):
    """Opaque result from an injected private evidence store."""

    private_store_ref: str = Field(pattern=_PRIVATE_STORE_REF)
    sha256: str = Field(pattern=_SHA256)
    size_bytes: int = Field(gt=0)
    media_type: str = Field(pattern=_MEDIA_TYPE)


class LiteratureSourceReceipt(_Contract):
    schema_version: str = Field(
        default=LITERATURE_SOURCE_RECEIPT_SCHEMA_VERSION,
        pattern=r"^chemsmart\.literature-source-receipt\.v1$",
    )
    source_id: str = Field(pattern=_IDENTIFIER)
    source_locator: str = Field(min_length=1, max_length=2048)
    sha256: str = Field(pattern=_SHA256)
    size_bytes: int = Field(gt=0)
    media_type: str = Field(pattern=_MEDIA_TYPE)
    content_class: LiteratureContentClass
    content_state: LiteratureContentState
    digest_basis: LiteratureDigestBasis
    private_store_ref: str | None = Field(
        default=None,
        pattern=_PRIVATE_STORE_REF,
    )

    @field_validator("source_locator")
    @classmethod
    def _locator_is_canonical(cls, value: str) -> str:
        canonical = canonicalize_source_locator(value)
        if canonical != value:
            raise ValueError("source locator must already be canonical")
        return value

    @model_validator(mode="after")
    def _content_state_cannot_overclaim(self) -> "LiteratureSourceReceipt":
        expected_state = {
            LiteratureContentClass.ARTICLE_METADATA: (
                LiteratureContentState.METADATA_ONLY,
                LiteratureDigestBasis.CONTENT_BYTES,
            ),
            LiteratureContentClass.ARTICLE_FULL_TEXT: (
                LiteratureContentState.RETRIEVED,
                LiteratureDigestBasis.CONTENT_BYTES,
            ),
            LiteratureContentClass.SUPPORTING_INFORMATION: (
                LiteratureContentState.DISCOVERED,
                LiteratureDigestBasis.CANONICAL_LOCATOR,
            ),
            LiteratureContentClass.DATASET: (
                LiteratureContentState.DISCOVERED,
                LiteratureDigestBasis.CANONICAL_LOCATOR,
            ),
            LiteratureContentClass.CODE: (
                LiteratureContentState.DISCOVERED,
                LiteratureDigestBasis.CANONICAL_LOCATOR,
            ),
            LiteratureContentClass.CITED_PROTOCOL: (
                LiteratureContentState.DISCOVERED,
                LiteratureDigestBasis.CANONICAL_LOCATOR,
            ),
        }[self.content_class]
        if (self.content_state, self.digest_basis) != expected_state:
            raise ValueError("content class, state, and digest basis disagree")
        if self.content_state is LiteratureContentState.RETRIEVED:
            if self.private_store_ref is None:
                raise ValueError("retrieved source requires a private-store reference")
        elif self.private_store_ref is not None:
            raise ValueError("metadata and discoveries cannot claim private content")
        return self


class LiteratureResponseReceipt(_Contract):
    schema_version: str = Field(
        default=LITERATURE_RESPONSE_RECEIPT_SCHEMA_VERSION,
        pattern=r"^chemsmart\.literature-response-receipt\.v1$",
    )
    response_receipt_id: str = Field(pattern=_IDENTIFIER)
    request_receipt_id: str = Field(pattern=_IDENTIFIER)
    request_receipt_sha256: str = Field(pattern=_SHA256)
    provider: ApiProvider
    origin: str
    http_status: int = Field(ge=0, le=599)
    status: LiteratureResponseStatus
    transport_response_sha256: str = Field(pattern=_SHA256)
    source_receipts: tuple[LiteratureSourceReceipt, ...] = ()
    rule_ids: tuple[str, ...] = ()
    response_receipt_sha256: str = Field(pattern=_SHA256)

    @field_validator("source_receipts")
    @classmethod
    def _sources_are_canonical(
        cls,
        values: tuple[LiteratureSourceReceipt, ...],
    ) -> tuple[LiteratureSourceReceipt, ...]:
        source_ids = [item.source_id for item in values]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("response source IDs must be unique")
        return tuple(
            sorted(
                values,
                key=lambda item: (
                    item.content_class.value,
                    item.source_locator,
                    item.source_id,
                ),
            )
        )

    @field_validator("rule_ids")
    @classmethod
    def _rules_are_canonical(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("response rule IDs must be unique")
        if any(re.fullmatch(_RULE_ID, item) is None for item in values):
            raise ValueError("response rule ID is invalid")
        return tuple(sorted(values))

    @model_validator(mode="after")
    def _status_and_receipt_are_exact(self) -> "LiteratureResponseReceipt":
        if self.provider not in LITERATURE_PROVIDER_ORIGINS:
            raise ValueError("response provider is not literature-scoped")
        if self.origin != LITERATURE_PROVIDER_ORIGINS[self.provider]:
            raise ValueError("response origin is not the exact provider origin")
        if self.status is LiteratureResponseStatus.VALID:
            if not self.source_receipts or self.rule_ids:
                raise ValueError("valid response requires sources and no rule IDs")
        elif self.source_receipts or not self.rule_ids:
            raise ValueError("non-valid response requires rules and forbids sources")
        exact_http_statuses = {
            LiteratureResponseStatus.INVALID_ENTITLEMENT: 403,
            LiteratureResponseStatus.RATE_LIMITED: 429,
        }
        exact = exact_http_statuses.get(self.status)
        if exact is not None and self.http_status != exact:
            raise ValueError("response status disagrees with HTTP status")
        required_status = {
            401: LiteratureResponseStatus.INVALID,
            403: LiteratureResponseStatus.INVALID_ENTITLEMENT,
            404: LiteratureResponseStatus.NOT_FOUND,
            429: LiteratureResponseStatus.RATE_LIMITED,
        }.get(self.http_status)
        if required_status is not None and self.status is not required_status:
            raise ValueError("HTTP status requires a distinct response status")
        if self.response_receipt_sha256 != literature_response_receipt_sha256(
            self
        ):
            raise ValueError("literature response receipt digest mismatch")
        return self


class LiteratureAcquisitionResult(_Contract):
    request_receipt: LiteratureRequestReceipt
    response_receipt: LiteratureResponseReceipt

    @model_validator(mode="after")
    def _response_binds_request(self) -> "LiteratureAcquisitionResult":
        response = self.response_receipt
        request = self.request_receipt
        if (
            response.request_receipt_id != request.request_receipt_id
            or response.request_receipt_sha256 != request.request_receipt_sha256
            or response.provider is not request.provider
            or response.origin != request.origin
        ):
            raise ValueError("literature response does not bind its request receipt")
        return self


class LiteratureMergeReceipt(_Contract):
    schema_version: str = Field(
        default=LITERATURE_MERGE_RECEIPT_SCHEMA_VERSION,
        pattern=r"^chemsmart\.literature-merge-receipt\.v1$",
    )
    merge_id: str = Field(pattern=_IDENTIFIER)
    input_response_receipt_sha256s: tuple[str, ...] = Field(min_length=1)
    status: LiteratureResponseStatus
    source_receipts: tuple[LiteratureSourceReceipt, ...] = ()
    rule_ids: tuple[str, ...] = ()
    merge_receipt_sha256: str = Field(pattern=_SHA256)

    @field_validator("input_response_receipt_sha256s")
    @classmethod
    def _inputs_are_canonical(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("merge input receipts must be unique")
        if any(re.fullmatch(_SHA256, item) is None for item in values):
            raise ValueError("merge input receipt digest is invalid")
        return tuple(sorted(values))

    @field_validator("source_receipts")
    @classmethod
    def _merged_sources_are_canonical(
        cls,
        values: tuple[LiteratureSourceReceipt, ...],
    ) -> tuple[LiteratureSourceReceipt, ...]:
        source_ids = [item.source_id for item in values]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("merged source IDs must be unique")
        return tuple(
            sorted(
                values,
                key=lambda item: (
                    item.content_class.value,
                    item.source_locator,
                    item.source_id,
                ),
            )
        )

    @field_validator("rule_ids")
    @classmethod
    def _merged_rules_are_canonical(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("merge rule IDs must be unique")
        if any(re.fullmatch(_RULE_ID, item) is None for item in values):
            raise ValueError("merge rule ID is invalid")
        return tuple(sorted(values))

    @model_validator(mode="after")
    def _merge_is_content_addressed(self) -> "LiteratureMergeReceipt":
        if self.status is LiteratureResponseStatus.VALID:
            if not self.source_receipts or self.rule_ids:
                raise ValueError("valid merge requires sources and no rules")
        elif self.status is not LiteratureResponseStatus.INVALID:
            raise ValueError("merge status must be valid or invalid")
        elif self.source_receipts or not self.rule_ids:
            raise ValueError("invalid merge requires rules and forbids sources")
        if self.merge_receipt_sha256 != literature_merge_receipt_sha256(self):
            raise ValueError("literature merge receipt digest mismatch")
        return self


@dataclass(frozen=True, slots=True)
class LiteratureTransportRequest:
    """Ephemeral provider request; credentials are deliberately absent."""

    request_id: str
    provider: ApiProvider
    origin: str
    method: str
    path: str
    parameters: tuple[tuple[str, str], ...]
    requested_content_classes: tuple[LiteratureContentClass, ...]

    def __post_init__(self) -> None:
        if self.origin != LITERATURE_PROVIDER_ORIGINS.get(self.provider):
            raise ValueError("transport request origin is not provider-exact")
        if self.method not in {"GET", "POST"}:
            raise ValueError("literature transport method is invalid")
        if not self.path.startswith("/") or "//" in self.path:
            raise ValueError("literature transport path is invalid")
        if tuple(sorted(self.parameters)) != self.parameters:
            raise ValueError("literature transport parameters must be canonical")

    @property
    def endpoint_url(self) -> str:
        return f"{self.origin}{self.path}"


@dataclass(frozen=True, slots=True)
class TransportSourceObservation:
    """Normalized transport output; ``content`` is never serialized."""

    source_locator: str
    content_class: LiteratureContentClass
    content_state: LiteratureContentState
    media_type: str
    content: bytes | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_locator, str):
            raise TypeError("transport source locator must be text")
        if not isinstance(self.content_class, LiteratureContentClass):
            raise TypeError("transport content_class must be typed")
        if not isinstance(self.content_state, LiteratureContentState):
            raise TypeError("transport content_state must be typed")
        if not isinstance(self.media_type, str):
            raise TypeError("transport media_type must be text")
        if self.content is not None and not isinstance(self.content, bytes):
            raise TypeError("transport source content must be bytes")


@dataclass(frozen=True, slots=True)
class LiteratureTransportResponse:
    origin: str
    status_code: int
    sources: tuple[TransportSourceObservation, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status_code, int) or isinstance(
            self.status_code, bool
        ):
            raise TypeError("transport status_code must be an integer")
        if self.status_code < 100 or self.status_code > 599:
            raise ValueError("transport status_code is outside HTTP range")


class LiteratureTransport(Protocol):
    def send(
        self,
        request: LiteratureTransportRequest,
        *,
        credential: str,
    ) -> LiteratureTransportResponse: ...


class PrivateEvidenceStore(Protocol):
    def put(
        self,
        *,
        source_id: str,
        content: bytes,
        media_type: str,
    ) -> PrivateStoreWriteReceipt: ...


class LiteratureTransportBudget:
    """Finite immutable provider limits with no refill or top-up operation."""

    def __init__(
        self,
        *,
        budget_id: str,
        provider_limits: Mapping[ApiProvider, int],
    ) -> None:
        if re.fullmatch(_IDENTIFIER, budget_id) is None:
            raise ValueError("literature budget_id is invalid")
        normalized = {ApiProvider(key): value for key, value in provider_limits.items()}
        if set(normalized) != set(LITERATURE_PROVIDERS):
            raise ValueError("finite limits are required for all literature providers")
        for provider, value in normalized.items():
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value <= 0
            ):
                raise ValueError(
                    f"provider limit must be a positive integer: {provider.value}"
                )
        self._budget_id = budget_id
        self._limits = MappingProxyType(dict(normalized))
        self._used = {provider: 0 for provider in LITERATURE_PROVIDERS}
        self._lock = threading.Lock()

    @property
    def budget_id(self) -> str:
        return self._budget_id

    @property
    def provider_limits(self) -> Mapping[ApiProvider, int]:
        return self._limits

    def remaining(self, provider: ApiProvider) -> int:
        with self._lock:
            return self._limits[provider] - self._used[provider]

    def reserve(self, provider: ApiProvider) -> tuple[int, int]:
        with self._lock:
            limit = self._limits[provider]
            if self._used[provider] >= limit:
                raise LiteratureBudgetExhaustedError(
                    f"finite literature budget exhausted for {provider.value}"
                )
            self._used[provider] += 1
            return self._used[provider], limit


@dataclass(frozen=True, slots=True)
class _CandidateSource:
    source_id: str
    source_locator: str
    sha256: str
    size_bytes: int
    media_type: str
    content_class: LiteratureContentClass
    content_state: LiteratureContentState
    digest_basis: LiteratureDigestBasis
    content: bytes | None = field(default=None, repr=False)


class LiteratureAcquisitionClient:
    """One bounded client over exact provider origins and injected transports."""

    def __init__(
        self,
        *,
        transports: Mapping[ApiProvider, LiteratureTransport],
        budget: LiteratureTransportBudget,
        private_store: PrivateEvidenceStore | None = None,
    ) -> None:
        normalized = {ApiProvider(key): value for key, value in transports.items()}
        if set(normalized) != set(LITERATURE_PROVIDERS):
            raise ValueError("one injected transport is required for each provider")
        self._transports = MappingProxyType(dict(normalized))
        self._budget = budget
        self._private_store = private_store
        self._request_fingerprints: dict[str, str] = {}
        self._results: dict[str, LiteratureAcquisitionResult] = {}
        self._lock = threading.Lock()

    def acquire(
        self,
        request: LiteratureAcquisitionRequest,
        *,
        credential: str,
    ) -> LiteratureAcquisitionResult:
        request = LiteratureAcquisitionRequest.model_validate(
            request.model_dump(mode="json")
        )
        fingerprint = _sha256_json(request.model_dump(mode="json"))
        with self._lock:
            existing_fingerprint = self._request_fingerprints.get(request.request_id)
            if existing_fingerprint is not None:
                if existing_fingerprint != fingerprint:
                    raise LiteratureRequestConflictError(
                        "literature request_id is bound to different immutable intent"
                    )
                return self._results[request.request_id]
            if not isinstance(credential, str) or not credential:
                raise LiteratureCredentialUnavailableError(
                    "a short-lived provider credential lease is required"
                )
            ordinal, limit = self._budget.reserve(request.provider)
            request_receipt = _build_request_receipt(
                request,
                budget_id=self._budget.budget_id,
                provider_request_ordinal=ordinal,
                provider_request_limit=limit,
            )
            transport_request = _build_transport_request(request)
            try:
                observation = self._transports[request.provider].send(
                    transport_request,
                    credential=credential,
                )
                if not isinstance(observation, LiteratureTransportResponse):
                    raise TypeError("transport returned an invalid response type")
                response_receipt = self._normalize_response(
                    request,
                    request_receipt,
                    observation,
                )
            except Exception:
                response_receipt = _build_nonvalid_response(
                    request_receipt,
                    http_status=0,
                    status=LiteratureResponseStatus.INVALID,
                    transport_response_sha256=_sha256_json(
                        {
                            "provider": request.provider.value,
                            "origin": LITERATURE_PROVIDER_ORIGINS[request.provider],
                            "request_id": request.request_id,
                            "outcome": "transport_failure",
                        }
                    ),
                    rule_ids=("literature.transport.failure",),
                )
            result = LiteratureAcquisitionResult(
                request_receipt=request_receipt,
                response_receipt=response_receipt,
            )
            self._request_fingerprints[request.request_id] = fingerprint
            self._results[request.request_id] = result
            return result

    def _normalize_response(
        self,
        request: LiteratureAcquisitionRequest,
        request_receipt: LiteratureRequestReceipt,
        observation: LiteratureTransportResponse,
    ) -> LiteratureResponseReceipt:
        transport_digest = _transport_response_sha256(observation)
        exact_origin = LITERATURE_PROVIDER_ORIGINS[request.provider]
        if observation.origin != exact_origin:
            return _build_nonvalid_response(
                request_receipt,
                http_status=observation.status_code,
                status=LiteratureResponseStatus.INVALID,
                transport_response_sha256=transport_digest,
                rule_ids=("literature.transport.origin_mismatch",),
            )
        mapped = _http_status_outcome(observation.status_code)
        if mapped is not None:
            status, rule_id = mapped
            return _build_nonvalid_response(
                request_receipt,
                http_status=observation.status_code,
                status=status,
                transport_response_sha256=transport_digest,
                rule_ids=(rule_id,),
            )
        if not 200 <= observation.status_code < 300:
            return _build_nonvalid_response(
                request_receipt,
                http_status=observation.status_code,
                status=LiteratureResponseStatus.INVALID,
                transport_response_sha256=transport_digest,
                rule_ids=("literature.transport.http_invalid",),
            )
        if not observation.sources:
            return _build_nonvalid_response(
                request_receipt,
                http_status=observation.status_code,
                status=LiteratureResponseStatus.NOT_FOUND,
                transport_response_sha256=transport_digest,
                rule_ids=("literature.source.not_found",),
            )

        candidates, rules = _normalize_source_candidates(request, observation.sources)
        if len(observation.sources) > request.max_results:
            rules.add("literature.source.result_limit_exceeded")
        if rules:
            return _build_nonvalid_response(
                request_receipt,
                http_status=observation.status_code,
                status=LiteratureResponseStatus.INVALID,
                transport_response_sha256=transport_digest,
                rule_ids=tuple(sorted(rules)),
            )

        source_receipts: list[LiteratureSourceReceipt] = []
        for candidate in candidates[: request.max_results]:
            private_store_ref: str | None = None
            if candidate.content_state is LiteratureContentState.RETRIEVED:
                if self._private_store is None:
                    return _build_nonvalid_response(
                        request_receipt,
                        http_status=observation.status_code,
                        status=LiteratureResponseStatus.INVALID,
                        transport_response_sha256=transport_digest,
                        rule_ids=("literature.private_store.unavailable",),
                    )
                try:
                    write_receipt = PrivateStoreWriteReceipt.model_validate(
                        self._private_store.put(
                            source_id=candidate.source_id,
                            content=candidate.content or b"",
                            media_type=candidate.media_type,
                        )
                    )
                except Exception:
                    return _build_nonvalid_response(
                        request_receipt,
                        http_status=observation.status_code,
                        status=LiteratureResponseStatus.INVALID,
                        transport_response_sha256=transport_digest,
                        rule_ids=("literature.private_store.write_failed",),
                    )
                if (
                    write_receipt.sha256 != candidate.sha256
                    or write_receipt.size_bytes != candidate.size_bytes
                    or write_receipt.media_type != candidate.media_type
                ):
                    return _build_nonvalid_response(
                        request_receipt,
                        http_status=observation.status_code,
                        status=LiteratureResponseStatus.INVALID,
                        transport_response_sha256=transport_digest,
                        rule_ids=("literature.private_store.receipt_mismatch",),
                    )
                private_store_ref = write_receipt.private_store_ref
            source_receipts.append(
                LiteratureSourceReceipt(
                    source_id=candidate.source_id,
                    source_locator=candidate.source_locator,
                    sha256=candidate.sha256,
                    size_bytes=candidate.size_bytes,
                    media_type=candidate.media_type,
                    content_class=candidate.content_class,
                    content_state=candidate.content_state,
                    digest_basis=candidate.digest_basis,
                    private_store_ref=private_store_ref,
                )
            )
        return _build_valid_response(
            request_receipt,
            http_status=observation.status_code,
            transport_response_sha256=transport_digest,
            source_receipts=tuple(source_receipts),
        )


def _build_request_receipt(
    request: LiteratureAcquisitionRequest,
    *,
    budget_id: str,
    provider_request_ordinal: int,
    provider_request_limit: int,
) -> LiteratureRequestReceipt:
    receipt_suffix = hashlib.sha256(request.request_id.encode()).hexdigest()[:32]
    body: dict[str, Any] = {
        "request_receipt_id": f"request-receipt:{receipt_suffix}",
        "request_id": request.request_id,
        "provider": request.provider.value,
        "origin": LITERATURE_PROVIDER_ORIGINS[request.provider],
        "action": request.action.value,
        "query_sha256": hashlib.sha256(request.query.encode()).hexdigest(),
        "requested_content_classes": [
            item.value for item in request.requested_content_classes
        ],
        "max_results": request.max_results,
        "budget_id": budget_id,
        "provider_request_ordinal": provider_request_ordinal,
        "provider_request_limit": provider_request_limit,
    }
    return LiteratureRequestReceipt(
        **body,
        request_receipt_sha256=literature_request_receipt_sha256(body),
    )


def _build_transport_request(
    request: LiteratureAcquisitionRequest,
) -> LiteratureTransportRequest:
    if request.provider is ApiProvider.ELSEVIER:
        identifier = (
            request.query[4:]
            if request.query.lower().startswith("doi:")
            else request.query
        )
        path = f"/content/article/doi/{quote(identifier, safe='')}"
        parameters = (
            (
                "view",
                "FULL"
                if request.action is LiteratureAcquisitionAction.FULL_TEXT
                else "META_ABS",
            ),
        )
        method = "GET"
    elif request.provider is ApiProvider.SERPAPI:
        path = "/search"
        parameters = (
            ("engine", "google_scholar"),
            ("num", str(request.max_results)),
            ("q", request.query),
        )
        method = "GET"
    elif request.action is LiteratureAcquisitionAction.FULL_TEXT:
        path = "/extract"
        parameters = (("url", request.query),)
        method = "POST"
    else:
        path = "/search"
        parameters = (
            ("max_results", str(request.max_results)),
            ("query", request.query),
            ("search_depth", "advanced"),
        )
        method = "POST"
    return LiteratureTransportRequest(
        request_id=request.request_id,
        provider=request.provider,
        origin=LITERATURE_PROVIDER_ORIGINS[request.provider],
        method=method,
        path=path,
        parameters=tuple(sorted(parameters)),
        requested_content_classes=request.requested_content_classes,
    )


def _normalize_source_candidates(
    request: LiteratureAcquisitionRequest,
    observations: Sequence[TransportSourceObservation],
) -> tuple[tuple[_CandidateSource, ...], set[str]]:
    rules: set[str] = set()
    candidates: dict[
        tuple[LiteratureContentClass, str], _CandidateSource
    ] = {}
    requested = set(request.requested_content_classes)
    expected_state = {
        LiteratureAcquisitionAction.METADATA: LiteratureContentState.METADATA_ONLY,
        LiteratureAcquisitionAction.FULL_TEXT: LiteratureContentState.RETRIEVED,
        LiteratureAcquisitionAction.DISCOVER: LiteratureContentState.DISCOVERED,
    }[request.action]
    for observation in observations:
        try:
            locator = canonicalize_source_locator(observation.source_locator)
        except (TypeError, ValueError):
            rules.add("literature.source.invalid_locator")
            continue
        if observation.content_class not in requested:
            rules.add("literature.source.content_class_unrequested")
            continue
        if observation.content_state is not expected_state:
            rules.add("literature.source.content_state_mismatch")
            continue
        if re.fullmatch(_MEDIA_TYPE, observation.media_type) is None:
            rules.add("literature.source.media_type_invalid")
            continue
        if expected_state is LiteratureContentState.DISCOVERED:
            if observation.content is not None:
                rules.add("literature.source.discovery_content_forbidden")
                continue
            descriptor = _canonical_json_bytes(
                {
                    "content_class": observation.content_class.value,
                    "locator": locator,
                    "media_type": observation.media_type,
                }
            )
            digest_basis = LiteratureDigestBasis.CANONICAL_LOCATOR
            content = None
        else:
            if not observation.content:
                rules.add("literature.source.content_missing")
                continue
            descriptor = observation.content
            digest_basis = LiteratureDigestBasis.CONTENT_BYTES
            content = observation.content
        source_id = _source_id(observation.content_class, locator)
        candidate = _CandidateSource(
            source_id=source_id,
            source_locator=locator,
            sha256=hashlib.sha256(descriptor).hexdigest(),
            size_bytes=len(descriptor),
            media_type=observation.media_type,
            content_class=observation.content_class,
            content_state=observation.content_state,
            digest_basis=digest_basis,
            content=content,
        )
        key = (candidate.content_class, candidate.source_locator)
        existing = candidates.get(key)
        if existing is None:
            candidates[key] = candidate
        elif _candidate_public_identity(existing) != _candidate_public_identity(
            candidate
        ):
            rules.add("literature.source.conflict")
    return (
        tuple(
            sorted(
                candidates.values(),
                key=lambda item: (
                    item.content_class.value,
                    item.source_locator,
                    item.source_id,
                ),
            )
        ),
        rules,
    )


def _candidate_public_identity(candidate: _CandidateSource) -> tuple[Any, ...]:
    return (
        candidate.source_id,
        candidate.sha256,
        candidate.size_bytes,
        candidate.media_type,
        candidate.content_state,
        candidate.digest_basis,
    )


def _http_status_outcome(
    status_code: int,
) -> tuple[LiteratureResponseStatus, str] | None:
    return {
        401: (
            LiteratureResponseStatus.INVALID,
            "literature.transport.credential_invalid",
        ),
        403: (
            LiteratureResponseStatus.INVALID_ENTITLEMENT,
            "literature.transport.entitlement_invalid",
        ),
        404: (
            LiteratureResponseStatus.NOT_FOUND,
            "literature.source.not_found",
        ),
        429: (
            LiteratureResponseStatus.RATE_LIMITED,
            "literature.transport.rate_limited",
        ),
    }.get(status_code)


def _build_valid_response(
    request: LiteratureRequestReceipt,
    *,
    http_status: int,
    transport_response_sha256: str,
    source_receipts: tuple[LiteratureSourceReceipt, ...],
) -> LiteratureResponseReceipt:
    receipt_suffix = hashlib.sha256(request.request_id.encode()).hexdigest()[:32]
    body: dict[str, Any] = {
        "response_receipt_id": f"response-receipt:{receipt_suffix}",
        "request_receipt_id": request.request_receipt_id,
        "request_receipt_sha256": request.request_receipt_sha256,
        "provider": request.provider.value,
        "origin": request.origin,
        "http_status": http_status,
        "status": LiteratureResponseStatus.VALID.value,
        "transport_response_sha256": transport_response_sha256,
        "source_receipts": [item.model_dump(mode="json") for item in source_receipts],
        "rule_ids": [],
    }
    return LiteratureResponseReceipt(
        **body,
        response_receipt_sha256=literature_response_receipt_sha256(body),
    )


def _build_nonvalid_response(
    request: LiteratureRequestReceipt,
    *,
    http_status: int,
    status: LiteratureResponseStatus,
    transport_response_sha256: str,
    rule_ids: tuple[str, ...],
) -> LiteratureResponseReceipt:
    receipt_suffix = hashlib.sha256(request.request_id.encode()).hexdigest()[:32]
    body: dict[str, Any] = {
        "response_receipt_id": f"response-receipt:{receipt_suffix}",
        "request_receipt_id": request.request_receipt_id,
        "request_receipt_sha256": request.request_receipt_sha256,
        "provider": request.provider.value,
        "origin": request.origin,
        "http_status": http_status,
        "status": status.value,
        "transport_response_sha256": transport_response_sha256,
        "source_receipts": [],
        "rule_ids": list(sorted(set(rule_ids))),
    }
    return LiteratureResponseReceipt(
        **body,
        response_receipt_sha256=literature_response_receipt_sha256(body),
    )


def canonicalize_source_locator(value: str) -> str:
    """Canonicalize an evidence locator without allowing local host paths."""

    if not isinstance(value, str):
        raise TypeError("source locator must be text")
    value = value.strip()
    if not value or not _NO_CONTROL.fullmatch(value):
        raise ValueError("source locator is empty or contains control characters")
    if value.lower().startswith("doi:"):
        doi = value[4:].strip().lower()
        if not doi.startswith("10.") or "/" not in doi or any(
            character.isspace() for character in doi
        ):
            raise ValueError("DOI locator is invalid")
        return f"doi:{doi}"
    parsed = urlsplit(value)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("source locator must be a DOI or absolute HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("source locator must not contain user information")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("source locator has an invalid port") from exc
    if port not in {None, 443} or parsed.fragment:
        raise ValueError("source locator must not contain a custom port or fragment")
    host = parsed.hostname.lower()
    netloc = host
    if ":" in host and not host.startswith("["):
        netloc = f"[{host}]"
    path = parsed.path or "/"
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    if any(
        key.casefold() in _SENSITIVE_LOCATOR_QUERY_KEYS
        for key, _ in query_items
    ):
        raise ValueError("source locator must not contain credential parameters")
    query = urlencode(sorted(query_items))
    return urlunsplit(("https", netloc, path, query, ""))


def merge_literature_response_receipts(
    receipts: Sequence[LiteratureResponseReceipt],
    *,
    merge_id: str,
) -> LiteratureMergeReceipt:
    """Deduplicate identical sources and fail closed on locator conflicts."""

    if not receipts:
        raise ValueError("at least one literature response receipt is required")
    validated = tuple(
        LiteratureResponseReceipt.model_validate(item.model_dump(mode="json"))
        for item in receipts
    )
    input_digests = tuple(
        sorted({item.response_receipt_sha256 for item in validated})
    )
    rules: set[str] = set()
    sources: dict[
        tuple[LiteratureContentClass, str], LiteratureSourceReceipt
    ] = {}
    for receipt in validated:
        if receipt.status is not LiteratureResponseStatus.VALID:
            rules.add("literature.merge.response_not_valid")
            continue
        for source in receipt.source_receipts:
            key = (source.content_class, source.source_locator)
            existing = sources.get(key)
            if existing is None:
                sources[key] = source
            elif existing.model_dump(mode="json") != source.model_dump(mode="json"):
                rules.add("literature.source.conflict")
    if rules:
        body: dict[str, Any] = {
            "merge_id": merge_id,
            "input_response_receipt_sha256s": list(input_digests),
            "status": LiteratureResponseStatus.INVALID.value,
            "source_receipts": [],
            "rule_ids": list(sorted(rules)),
        }
    else:
        body = {
            "merge_id": merge_id,
            "input_response_receipt_sha256s": list(input_digests),
            "status": LiteratureResponseStatus.VALID.value,
            "source_receipts": [
                item.model_dump(mode="json")
                for item in sorted(
                    sources.values(),
                    key=lambda item: (
                        item.content_class.value,
                        item.source_locator,
                        item.source_id,
                    ),
                )
            ],
            "rule_ids": [],
        }
    return LiteratureMergeReceipt(
        **body,
        merge_receipt_sha256=literature_merge_receipt_sha256(body),
    )


def literature_request_receipt_sha256(
    value: LiteratureRequestReceipt | Mapping[str, Any],
) -> str:
    return _receipt_sha256(
        value,
        digest_field="request_receipt_sha256",
        schema_version=LITERATURE_REQUEST_RECEIPT_SCHEMA_VERSION,
    )


def literature_response_receipt_sha256(
    value: LiteratureResponseReceipt | Mapping[str, Any],
) -> str:
    return _receipt_sha256(
        value,
        digest_field="response_receipt_sha256",
        schema_version=LITERATURE_RESPONSE_RECEIPT_SCHEMA_VERSION,
    )


def literature_merge_receipt_sha256(
    value: LiteratureMergeReceipt | Mapping[str, Any],
) -> str:
    return _receipt_sha256(
        value,
        digest_field="merge_receipt_sha256",
        schema_version=LITERATURE_MERGE_RECEIPT_SCHEMA_VERSION,
    )


def _receipt_sha256(
    value: BaseModel | Mapping[str, Any],
    *,
    digest_field: str,
    schema_version: str,
) -> str:
    if isinstance(value, BaseModel):
        body = value.model_dump(mode="json", exclude={digest_field})
    else:
        body = dict(value)
        body.pop(digest_field, None)
        body.setdefault("schema_version", schema_version)
    return _sha256_json(body)


def _transport_response_sha256(response: LiteratureTransportResponse) -> str:
    return _sha256_json(
        {
            "origin": response.origin,
            "status_code": response.status_code,
            "sources": [
                {
                    "source_locator": item.source_locator,
                    "content_class": item.content_class.value,
                    "content_state": item.content_state.value,
                    "media_type": item.media_type,
                    "content_sha256": (
                        hashlib.sha256(item.content).hexdigest()
                        if item.content is not None
                        else None
                    ),
                    "content_size_bytes": (
                        len(item.content) if item.content is not None else None
                    ),
                }
                for item in response.sources
            ],
        }
    )


def _source_id(content_class: LiteratureContentClass, locator: str) -> str:
    digest = hashlib.sha256(
        f"{content_class.value}\x00{locator}".encode()
    ).hexdigest()
    return f"source:{digest[:32]}"


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


__all__ = [
    "CROSSREF_ORIGIN",
    "LITERATURE_PROVIDER_ORIGINS",
    "LITERATURE_PROVIDERS",
    "BibliographicAuthorV1",
    "BibliographicConcordanceReceiptV1",
    "BibliographicConcordanceStatus",
    "BibliographicCorrectionRelationV1",
    "BibliographicObservationV1",
    "CrossrefMetadataRequestV1",
    "CrossrefRepresentation",
    "CrossrefResponseReceiptV1",
    "CrossrefResponseStatus",
    "LiteratureAcquisitionAction",
    "LiteratureAcquisitionClient",
    "LiteratureAcquisitionError",
    "LiteratureAcquisitionRequest",
    "LiteratureAcquisitionResult",
    "LiteratureBudgetExhaustedError",
    "LiteratureContentClass",
    "LiteratureContentState",
    "LiteratureCredentialUnavailableError",
    "LiteratureDigestBasis",
    "LiteratureMergeReceipt",
    "LiteratureRequestConflictError",
    "LiteratureRequestReceipt",
    "LiteratureResponseReceipt",
    "LiteratureResponseStatus",
    "LiteratureSourceReceipt",
    "LiteratureTransport",
    "LiteratureTransportBudget",
    "LiteratureTransportRequest",
    "LiteratureTransportResponse",
    "NormalizedBibliographicRecordV1",
    "PrivateEvidenceStore",
    "PrivateStoreWriteReceipt",
    "TransportSourceObservation",
    "build_bibliographic_concordance_receipt_v1",
    "build_bibliographic_observation_v1",
    "build_crossref_metadata_request_v1",
    "build_crossref_response_receipt_v1",
    "canonicalize_source_locator",
    "crossref_request_path",
    "literature_merge_receipt_sha256",
    "literature_request_receipt_sha256",
    "literature_response_receipt_sha256",
    "merge_literature_response_receipts",
]
