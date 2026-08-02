"""Public bibliographic evidence and fail-closed concordance contracts.

Crossref is a public metadata endpoint, not a credentialed ChemSmart provider.
The contracts in this module therefore bind every request to an adaptive
hypothesis while explicitly forbidding a credential lease.  Response bodies
remain ephemeral: public receipts retain exact-byte hashes and normalized
bibliographic observations only.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from enum import Enum
from typing import Any, Literal, Mapping, Sequence
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CROSSREF_ORIGIN = "https://api.crossref.org"
CROSSREF_METADATA_REQUEST_SCHEMA_VERSION = (
    "chemsmart.crossref-metadata-request.v1"
)
CROSSREF_RESPONSE_RECEIPT_SCHEMA_VERSION = (
    "chemsmart.crossref-response-receipt.v1"
)
BIBLIOGRAPHIC_OBSERVATION_SCHEMA_VERSION = (
    "chemsmart.bibliographic-observation.v1"
)
BIBLIOGRAPHIC_CONCORDANCE_SCHEMA_VERSION = (
    "chemsmart.bibliographic-concordance-receipt.v1"
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_SHA256 = r"^[0-9a-f]{64}$"
_RULE_ID = r"^[a-z][a-z0-9_.-]{0,191}$"
_DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
_RELATION_TYPE = re.compile(r"^[a-z][a-z0-9-]{0,95}$")
_CORRECTION_RELATION_TYPES = frozenset(
    {
        "is-corrected-by",
        "is-correction-of",
        "is-retracted-by",
        "is-retraction-of",
        "is-updated-by",
        "is-update-of",
        "updated-by",
        "updates",
    }
)


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class CrossrefRepresentation(str, Enum):
    JSON = "json"
    BIBTEX = "bibtex"


class CrossrefResponseStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"


class BibliographicConcordanceStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


class BibliographicAuthorV1(_Contract):
    given: str = Field(default="", max_length=256)
    family: str = Field(min_length=1, max_length=256)


class BibliographicCorrectionRelationV1(_Contract):
    relation_type: str = Field(pattern=r"^[a-z][a-z0-9-]{0,95}$")
    identifier_type: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    identifier: str = Field(min_length=1, max_length=2048)

    @model_validator(mode="after")
    def _relation_is_canonical(self) -> "BibliographicCorrectionRelationV1":
        if self.relation_type not in _CORRECTION_RELATION_TYPES:
            raise ValueError("relation is not correction- or retraction-sensitive")
        expected = (
            normalize_doi(self.identifier)
            if self.identifier_type == "doi"
            else _normalize_free_identifier(self.identifier)
        )
        if self.identifier != expected:
            raise ValueError("correction relation identifier is not canonical")
        return self


class BibliographicObservationV1(_Contract):
    schema_version: Literal[
        "chemsmart.bibliographic-observation.v1"
    ] = BIBLIOGRAPHIC_OBSERVATION_SCHEMA_VERSION
    observation_id: str = Field(pattern=_IDENTIFIER)
    observation_sha256: str = Field(pattern=_SHA256)
    source_provider: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    source_artifact_sha256: str = Field(pattern=_SHA256)
    doi: str = Field(min_length=1, max_length=2048)
    title: str = Field(min_length=1, max_length=4096)
    authors: tuple[BibliographicAuthorV1, ...] = Field(min_length=1)
    publication_year: int = Field(ge=1000, le=9999)
    license_reported: bool
    license_urls: tuple[str, ...] = ()
    correction_relations_checked: bool
    correction_relations: tuple[BibliographicCorrectionRelationV1, ...] = ()

    @field_validator("doi")
    @classmethod
    def _doi_is_canonical(cls, value: str) -> str:
        if value != normalize_doi(value):
            raise ValueError("bibliographic DOI is not canonical")
        return value

    @field_validator("license_urls")
    @classmethod
    def _licenses_are_canonical(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values != tuple(sorted(set(values))):
            raise ValueError("license URLs must be unique and sorted")
        if any(value != normalize_license_url(value) for value in values):
            raise ValueError("license URL is not canonical")
        return values

    @field_validator("correction_relations")
    @classmethod
    def _relations_are_canonical(
        cls,
        values: tuple[BibliographicCorrectionRelationV1, ...],
    ) -> tuple[BibliographicCorrectionRelationV1, ...]:
        keys = tuple(_relation_key(value) for value in values)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("correction relations must be unique and sorted")
        return values

    @model_validator(mode="after")
    def _observation_is_exact(self) -> "BibliographicObservationV1":
        if not self.license_reported and self.license_urls:
            raise ValueError("unreported license cannot carry license URLs")
        if not self.correction_relations_checked and self.correction_relations:
            raise ValueError("unchecked correction state cannot carry relations")
        if self.observation_sha256 != bibliographic_observation_sha256(self):
            raise ValueError("bibliographic observation digest mismatch")
        return self


class CrossrefMetadataRequestV1(_Contract):
    """One public Crossref representation request bound to one hypothesis."""

    schema_version: Literal[
        "chemsmart.crossref-metadata-request.v1"
    ] = CROSSREF_METADATA_REQUEST_SCHEMA_VERSION
    request_id: str = Field(pattern=_IDENTIFIER)
    request_sha256: str = Field(pattern=_SHA256)
    adaptive_hypothesis_sha256: str = Field(pattern=_SHA256)
    provider: Literal["crossref"] = "crossref"
    origin: Literal["https://api.crossref.org"] = CROSSREF_ORIGIN
    purpose: Literal["article_metadata"] = "article_metadata"
    representation: CrossrefRepresentation
    doi: str = Field(min_length=1, max_length=2048)
    method: Literal["GET"] = "GET"
    path: str = Field(min_length=1, max_length=4096)
    accept_media_type: str = Field(min_length=1, max_length=128)
    credential_lease_required: Literal[False] = False

    @model_validator(mode="after")
    def _request_is_exact(self) -> "CrossrefMetadataRequestV1":
        if self.doi != normalize_doi(self.doi):
            raise ValueError("Crossref request DOI is not canonical")
        if self.path != crossref_request_path(self.doi, self.representation):
            raise ValueError("Crossref request path is not canonical")
        if self.accept_media_type != _representation_media_type(
            self.representation
        ):
            raise ValueError("Crossref request media type is not canonical")
        if self.request_sha256 != crossref_request_sha256(self):
            raise ValueError("Crossref request digest mismatch")
        return self

    @property
    def endpoint_url(self) -> str:
        return f"{self.origin}{self.path}"


class CrossrefResponseReceiptV1(_Contract):
    schema_version: Literal[
        "chemsmart.crossref-response-receipt.v1"
    ] = CROSSREF_RESPONSE_RECEIPT_SCHEMA_VERSION
    response_receipt_id: str = Field(pattern=_IDENTIFIER)
    response_receipt_sha256: str = Field(pattern=_SHA256)
    request_id: str = Field(pattern=_IDENTIFIER)
    request_sha256: str = Field(pattern=_SHA256)
    adaptive_hypothesis_sha256: str = Field(pattern=_SHA256)
    provider: Literal["crossref"] = "crossref"
    origin: Literal["https://api.crossref.org"] = CROSSREF_ORIGIN
    representation: CrossrefRepresentation
    doi: str
    credential_lease_used: Literal[False] = False
    http_status: int = Field(ge=100, le=599)
    status: CrossrefResponseStatus
    body_sha256: str = Field(pattern=_SHA256)
    body_size_bytes: int = Field(ge=0)
    body_media_type: str = Field(min_length=1, max_length=128)
    observation: BibliographicObservationV1 | None = None
    rule_ids: tuple[str, ...] = ()

    @field_validator("rule_ids")
    @classmethod
    def _rules_are_canonical(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values != tuple(sorted(set(values))):
            raise ValueError("Crossref rule IDs must be unique and sorted")
        if any(re.fullmatch(_RULE_ID, value) is None for value in values):
            raise ValueError("Crossref rule ID is invalid")
        return values

    @model_validator(mode="after")
    def _receipt_is_exact(self) -> "CrossrefResponseReceiptV1":
        if self.doi != normalize_doi(self.doi):
            raise ValueError("Crossref response DOI is not canonical")
        if self.status is CrossrefResponseStatus.VALID:
            if (
                self.observation is None
                or self.rule_ids
                or not 200 <= self.http_status < 300
                or self.body_size_bytes == 0
            ):
                raise ValueError("valid Crossref receipt requires one observation")
            if self.observation.source_artifact_sha256 != self.body_sha256:
                raise ValueError("Crossref observation does not bind response bytes")
            if self.observation.doi != self.doi:
                raise ValueError("Crossref observation DOI differs from request")
        elif self.observation is not None or not self.rule_ids:
            raise ValueError("non-valid Crossref receipt forbids observations")
        exact = {
            CrossrefResponseStatus.NOT_FOUND: 404,
            CrossrefResponseStatus.RATE_LIMITED: 429,
        }.get(self.status)
        if exact is not None and self.http_status != exact:
            raise ValueError("Crossref response status disagrees with HTTP status")
        if self.http_status == 404 and self.status is not CrossrefResponseStatus.NOT_FOUND:
            raise ValueError("HTTP 404 requires not_found")
        if self.http_status == 429 and self.status is not CrossrefResponseStatus.RATE_LIMITED:
            raise ValueError("HTTP 429 requires rate_limited")
        if self.response_receipt_sha256 != crossref_response_receipt_sha256(self):
            raise ValueError("Crossref response receipt digest mismatch")
        return self


class NormalizedBibliographicRecordV1(_Contract):
    doi: str
    title: str
    authors: tuple[str, ...] = Field(min_length=1)
    publication_year: int = Field(ge=1000, le=9999)
    license_urls: tuple[str, ...] = Field(min_length=1)
    correction_relations: tuple[str, ...] = ()


class BibliographicConcordanceReceiptV1(_Contract):
    schema_version: Literal[
        "chemsmart.bibliographic-concordance-receipt.v1"
    ] = BIBLIOGRAPHIC_CONCORDANCE_SCHEMA_VERSION
    concordance_id: str = Field(pattern=_IDENTIFIER)
    concordance_sha256: str = Field(pattern=_SHA256)
    observations: tuple[BibliographicObservationV1, ...] = Field(min_length=2)
    status: BibliographicConcordanceStatus
    canonical_record: NormalizedBibliographicRecordV1 | None = None
    rule_ids: tuple[str, ...] = ()

    @field_validator("observations")
    @classmethod
    def _observations_are_canonical(
        cls,
        values: tuple[BibliographicObservationV1, ...],
    ) -> tuple[BibliographicObservationV1, ...]:
        hashes = tuple(value.observation_sha256 for value in values)
        if hashes != tuple(sorted(set(hashes))):
            raise ValueError("concordance observations must be unique and sorted")
        return values

    @field_validator("rule_ids")
    @classmethod
    def _concordance_rules_are_canonical(
        cls, values: tuple[str, ...]
    ) -> tuple[str, ...]:
        if values != tuple(sorted(set(values))):
            raise ValueError("concordance rule IDs must be unique and sorted")
        if any(re.fullmatch(_RULE_ID, value) is None for value in values):
            raise ValueError("concordance rule ID is invalid")
        return values

    @model_validator(mode="after")
    def _concordance_is_replayable(self) -> "BibliographicConcordanceReceiptV1":
        expected_record, expected_rules = _evaluate_concordance(self.observations)
        expected_status = (
            BibliographicConcordanceStatus.INVALID
            if expected_rules
            else BibliographicConcordanceStatus.VALID
        )
        if (
            self.status is not expected_status
            or self.rule_ids != expected_rules
            or self.canonical_record != expected_record
        ):
            raise ValueError("bibliographic concordance outcome is not replayable")
        if self.concordance_sha256 != bibliographic_concordance_sha256(self):
            raise ValueError("bibliographic concordance receipt digest mismatch")
        return self


def normalize_doi(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("DOI must be text")
    normalized = unicodedata.normalize("NFKC", unquote(value.strip()))
    lowered = normalized.casefold()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if lowered.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
            break
    normalized = normalized.casefold()
    if not _DOI.fullmatch(normalized) or any(
        character.isspace() for character in normalized
    ):
        raise ValueError("DOI is invalid")
    return normalized


def normalize_license_url(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("license URL must be text")
    parsed = urlsplit(unicodedata.normalize("NFKC", value.strip()))
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("license must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None or parsed.port not in {
        None,
        80,
        443,
    }:
        raise ValueError("license URL authority is invalid")
    path = re.sub(r"/+", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(("https", parsed.hostname.casefold(), path, "", ""))


def crossref_request_path(
    doi: str,
    representation: CrossrefRepresentation,
) -> str:
    normalized_doi = normalize_doi(doi)
    encoded_doi = quote(normalized_doi, safe="")
    if representation is CrossrefRepresentation.JSON:
        return f"/works/{encoded_doi}"
    if representation is CrossrefRepresentation.BIBTEX:
        return f"/works/{encoded_doi}/transform/application/x-bibtex"
    raise TypeError("Crossref representation must be typed")


def build_crossref_metadata_request_v1(
    *,
    request_id: str,
    adaptive_hypothesis_sha256: str,
    doi: str,
    representation: CrossrefRepresentation,
) -> CrossrefMetadataRequestV1:
    representation = CrossrefRepresentation(representation)
    body: dict[str, Any] = {
        "schema_version": CROSSREF_METADATA_REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "adaptive_hypothesis_sha256": adaptive_hypothesis_sha256,
        "provider": "crossref",
        "origin": CROSSREF_ORIGIN,
        "purpose": "article_metadata",
        "representation": representation.value,
        "doi": normalize_doi(doi),
        "method": "GET",
        "path": crossref_request_path(doi, representation),
        "accept_media_type": _representation_media_type(representation),
        "credential_lease_required": False,
    }
    return CrossrefMetadataRequestV1.model_validate(
        {**body, "request_sha256": crossref_request_sha256(body)}
    )


def build_crossref_response_receipt_v1(
    request: CrossrefMetadataRequestV1,
    *,
    http_status: int,
    body: bytes,
    media_type: str,
) -> CrossrefResponseReceiptV1:
    """Normalize one ephemeral Crossref body into a public receipt."""

    request = CrossrefMetadataRequestV1.model_validate(
        request.model_dump(mode="json")
    )
    if not isinstance(body, bytes):
        raise TypeError("Crossref response body must be exact bytes")
    normalized_media_type = media_type.split(";", 1)[0].strip().casefold()
    body_sha256 = hashlib.sha256(body).hexdigest()
    status = CrossrefResponseStatus.INVALID
    rules: set[str] = set()
    observation: BibliographicObservationV1 | None = None
    if http_status == 404:
        status = CrossrefResponseStatus.NOT_FOUND
        rules.add("bibliography.crossref.not_found")
    elif http_status == 429:
        status = CrossrefResponseStatus.RATE_LIMITED
        rules.add("bibliography.crossref.rate_limited")
    elif not 200 <= http_status < 300:
        rules.add("bibliography.crossref.http_invalid")
    elif normalized_media_type != request.accept_media_type:
        rules.add("bibliography.crossref.media_type_mismatch")
    elif not body:
        rules.add("bibliography.crossref.body_missing")
    else:
        try:
            observation = _parse_crossref_observation(
                request,
                body,
                body_sha256=body_sha256,
            )
        except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            rules.add("bibliography.crossref.parse_invalid")
        else:
            if observation.doi != request.doi:
                observation = None
                rules.add("bibliography.crossref.doi_mismatch")
            else:
                status = CrossrefResponseStatus.VALID
    receipt_id_digest = hashlib.sha256(
        f"{request.request_sha256}\x00{body_sha256}".encode("utf-8")
    ).hexdigest()[:32]
    receipt_body: dict[str, Any] = {
        "schema_version": CROSSREF_RESPONSE_RECEIPT_SCHEMA_VERSION,
        "response_receipt_id": f"crossref-response:{receipt_id_digest}",
        "request_id": request.request_id,
        "request_sha256": request.request_sha256,
        "adaptive_hypothesis_sha256": request.adaptive_hypothesis_sha256,
        "provider": "crossref",
        "origin": CROSSREF_ORIGIN,
        "representation": request.representation.value,
        "doi": request.doi,
        "credential_lease_used": False,
        "http_status": http_status,
        "status": status.value,
        "body_sha256": body_sha256,
        "body_size_bytes": len(body),
        "body_media_type": normalized_media_type,
        "observation": (
            observation.model_dump(mode="json") if observation is not None else None
        ),
        "rule_ids": sorted(rules),
    }
    return CrossrefResponseReceiptV1.model_validate(
        {
            **receipt_body,
            "response_receipt_sha256": crossref_response_receipt_sha256(
                receipt_body
            ),
        }
    )


def build_bibliographic_observation_v1(
    *,
    observation_id: str,
    source_provider: str,
    source_artifact_sha256: str,
    doi: str,
    title: str,
    authors: Sequence[BibliographicAuthorV1],
    publication_year: int,
    license_reported: bool,
    license_urls: Sequence[str] = (),
    correction_relations_checked: bool,
    correction_relations: Sequence[BibliographicCorrectionRelationV1] = (),
) -> BibliographicObservationV1:
    canonical_authors = tuple(
        BibliographicAuthorV1.model_validate(author) for author in authors
    )
    canonical_licenses = tuple(
        sorted({normalize_license_url(value) for value in license_urls})
    )
    canonical_relations = tuple(
        sorted(
            (
                BibliographicCorrectionRelationV1.model_validate(value)
                for value in correction_relations
            ),
            key=_relation_key,
        )
    )
    body: dict[str, Any] = {
        "schema_version": BIBLIOGRAPHIC_OBSERVATION_SCHEMA_VERSION,
        "observation_id": observation_id,
        "source_provider": source_provider,
        "source_artifact_sha256": source_artifact_sha256,
        "doi": normalize_doi(doi),
        "title": title,
        "authors": [author.model_dump(mode="json") for author in canonical_authors],
        "publication_year": publication_year,
        "license_reported": license_reported,
        "license_urls": list(canonical_licenses),
        "correction_relations_checked": correction_relations_checked,
        "correction_relations": [
            relation.model_dump(mode="json") for relation in canonical_relations
        ],
    }
    return BibliographicObservationV1.model_validate(
        {**body, "observation_sha256": bibliographic_observation_sha256(body)}
    )


def build_bibliographic_concordance_receipt_v1(
    observations: Sequence[BibliographicObservationV1],
    *,
    concordance_id: str,
) -> BibliographicConcordanceReceiptV1:
    validated = tuple(
        sorted(
            (
                BibliographicObservationV1.model_validate(
                    observation.model_dump(mode="json")
                )
                for observation in observations
            ),
            key=lambda observation: observation.observation_sha256,
        )
    )
    if len(validated) < 2:
        raise ValueError("bibliographic concordance requires at least two sources")
    record, rules = _evaluate_concordance(validated)
    body: dict[str, Any] = {
        "schema_version": BIBLIOGRAPHIC_CONCORDANCE_SCHEMA_VERSION,
        "concordance_id": concordance_id,
        "observations": [value.model_dump(mode="json") for value in validated],
        "status": (
            BibliographicConcordanceStatus.INVALID.value
            if rules
            else BibliographicConcordanceStatus.VALID.value
        ),
        "canonical_record": (
            record.model_dump(mode="json") if record is not None else None
        ),
        "rule_ids": list(rules),
    }
    return BibliographicConcordanceReceiptV1.model_validate(
        {**body, "concordance_sha256": bibliographic_concordance_sha256(body)}
    )


def crossref_request_sha256(
    value: CrossrefMetadataRequestV1 | Mapping[str, Any],
) -> str:
    return _contract_sha256(value, "request_sha256")


def crossref_response_receipt_sha256(
    value: CrossrefResponseReceiptV1 | Mapping[str, Any],
) -> str:
    return _contract_sha256(value, "response_receipt_sha256")


def bibliographic_observation_sha256(
    value: BibliographicObservationV1 | Mapping[str, Any],
) -> str:
    return _contract_sha256(value, "observation_sha256")


def bibliographic_concordance_sha256(
    value: BibliographicConcordanceReceiptV1 | Mapping[str, Any],
) -> str:
    return _contract_sha256(value, "concordance_sha256")


def _parse_crossref_observation(
    request: CrossrefMetadataRequestV1,
    body: bytes,
    *,
    body_sha256: str,
) -> BibliographicObservationV1:
    if request.representation is CrossrefRepresentation.JSON:
        parsed = json.loads(body.decode("utf-8", errors="strict"))
        if not isinstance(parsed, Mapping) or parsed.get("status") != "ok":
            raise ValueError("Crossref JSON envelope is invalid")
        message = parsed.get("message")
        if not isinstance(message, Mapping):
            raise ValueError("Crossref JSON work record is missing")
        doi = _required_text(message.get("DOI"), "DOI")
        title = _first_text(message.get("title"), "title")
        authors_value = message.get("author")
        if not isinstance(authors_value, list) or not authors_value:
            raise ValueError("Crossref authors are missing")
        authors = tuple(
            BibliographicAuthorV1(
                given=str(author.get("given", "")),
                family=_required_text(author.get("family"), "author family"),
            )
            for author in authors_value
            if isinstance(author, Mapping)
        )
        if len(authors) != len(authors_value):
            raise ValueError("Crossref author record is invalid")
        year = _crossref_publication_year(message)
        license_present = "license" in message
        license_value = message.get("license", [])
        if not isinstance(license_value, list):
            raise ValueError("Crossref license field is invalid")
        licenses = []
        for item in license_value:
            if not isinstance(item, Mapping):
                raise ValueError("Crossref license record is invalid")
            licenses.append(_required_text(item.get("URL"), "license URL"))
        relations = _crossref_correction_relations(message.get("relation", {}))
        return build_bibliographic_observation_v1(
            observation_id=f"crossref-json:{body_sha256[:32]}",
            source_provider="crossref-json",
            source_artifact_sha256=body_sha256,
            doi=doi,
            title=title,
            authors=authors,
            publication_year=year,
            license_reported=license_present,
            license_urls=licenses,
            correction_relations_checked=True,
            correction_relations=relations,
        )

    text = body.decode("utf-8", errors="strict")
    fields = _parse_bibtex_fields(text)
    author_text = _required_text(fields.get("author"), "BibTeX author")
    authors = _parse_bibtex_authors(author_text)
    year_match = re.search(r"\d{4}", _required_text(fields.get("year"), "year"))
    if year_match is None:
        raise ValueError("BibTeX year is invalid")
    license_value = fields.get("license")
    return build_bibliographic_observation_v1(
        observation_id=f"crossref-bibtex:{body_sha256[:32]}",
        source_provider="crossref-bibtex",
        source_artifact_sha256=body_sha256,
        doi=_required_text(fields.get("doi"), "BibTeX DOI"),
        title=_required_text(fields.get("title"), "BibTeX title"),
        authors=authors,
        publication_year=int(year_match.group(0)),
        license_reported=license_value is not None,
        license_urls=(() if license_value is None else (license_value,)),
        correction_relations_checked=False,
    )


def _crossref_publication_year(message: Mapping[str, Any]) -> int:
    for field_name in ("published-print", "published-online", "issued"):
        value = message.get(field_name)
        if not isinstance(value, Mapping):
            continue
        parts = value.get("date-parts")
        if (
            isinstance(parts, list)
            and parts
            and isinstance(parts[0], list)
            and parts[0]
            and isinstance(parts[0][0], int)
            and not isinstance(parts[0][0], bool)
        ):
            return parts[0][0]
    raise ValueError("Crossref publication year is missing")


def _crossref_correction_relations(
    relation_value: object,
) -> tuple[BibliographicCorrectionRelationV1, ...]:
    if not isinstance(relation_value, Mapping):
        raise ValueError("Crossref relation field is invalid")
    relations: list[BibliographicCorrectionRelationV1] = []
    for raw_type, raw_items in relation_value.items():
        relation_type = str(raw_type).casefold()
        if relation_type not in _CORRECTION_RELATION_TYPES:
            continue
        if not isinstance(raw_items, list):
            raise ValueError("Crossref correction relation is invalid")
        for raw_item in raw_items:
            if not isinstance(raw_item, Mapping):
                raise ValueError("Crossref correction relation item is invalid")
            identifier_type = _required_text(
                raw_item.get("id-type"), "relation identifier type"
            ).casefold()
            identifier = _required_text(raw_item.get("id"), "relation identifier")
            if identifier_type == "doi":
                identifier = normalize_doi(identifier)
            else:
                identifier = _normalize_free_identifier(identifier)
            relations.append(
                BibliographicCorrectionRelationV1(
                    relation_type=relation_type,
                    identifier_type=identifier_type,
                    identifier=identifier,
                )
            )
    return tuple(sorted(relations, key=_relation_key))


def _parse_bibtex_fields(text: str) -> dict[str, str]:
    start = text.find("{")
    if not text.lstrip().startswith("@") or start < 0:
        raise ValueError("BibTeX entry is invalid")
    comma = text.find(",", start + 1)
    if comma < 0:
        raise ValueError("BibTeX citation key is missing")
    index = comma + 1
    fields: dict[str, str] = {}
    while index < len(text):
        while index < len(text) and (text[index].isspace() or text[index] == ","):
            index += 1
        if index >= len(text) or text[index] == "}":
            break
        name_match = re.match(r"[A-Za-z][A-Za-z0-9_-]*", text[index:])
        if name_match is None:
            raise ValueError("BibTeX field name is invalid")
        name = name_match.group(0).casefold()
        index += len(name_match.group(0))
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text) or text[index] != "=":
            raise ValueError("BibTeX field assignment is invalid")
        index += 1
        while index < len(text) and text[index].isspace():
            index += 1
        value, index = _parse_bibtex_value(text, index)
        if name in fields:
            raise ValueError("BibTeX field is duplicated")
        fields[name] = value.strip()
    return fields


def _parse_bibtex_value(text: str, index: int) -> tuple[str, int]:
    if index >= len(text):
        raise ValueError("BibTeX field value is missing")
    opener = text[index]
    if opener == "{":
        depth = 1
        index += 1
        start = index
        while index < len(text) and depth:
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
            index += 1
        if depth:
            raise ValueError("BibTeX braced value is unterminated")
        return text[start : index - 1], index
    if opener == '"':
        index += 1
        start = index
        escaped = False
        while index < len(text):
            character = text[index]
            if character == '"' and not escaped:
                return text[start:index], index + 1
            escaped = character == "\\" and not escaped
            if character != "\\":
                escaped = False
            index += 1
        raise ValueError("BibTeX quoted value is unterminated")
    end = index
    while end < len(text) and text[end] not in ",}\n\r":
        end += 1
    return text[index:end], end


def _parse_bibtex_authors(value: str) -> tuple[BibliographicAuthorV1, ...]:
    authors: list[BibliographicAuthorV1] = []
    for raw_author in re.split(r"\s+and\s+", value, flags=re.IGNORECASE):
        author = raw_author.strip()
        if not author:
            raise ValueError("BibTeX author is empty")
        if "," in author:
            family, given = (part.strip() for part in author.split(",", 1))
        else:
            parts = author.split()
            if len(parts) < 2:
                raise ValueError("BibTeX author requires given and family names")
            given, family = " ".join(parts[:-1]), parts[-1]
        authors.append(BibliographicAuthorV1(given=given, family=family))
    return tuple(authors)


def _evaluate_concordance(
    observations: Sequence[BibliographicObservationV1],
) -> tuple[NormalizedBibliographicRecordV1 | None, tuple[str, ...]]:
    rules: set[str] = set()
    dois = {normalize_doi(value.doi) for value in observations}
    titles = {_normalize_title(value.title) for value in observations}
    authors = {_normalized_authors(value.authors) for value in observations}
    years = {value.publication_year for value in observations}
    license_sets = {value.license_urls for value in observations}
    relation_sets = {
        tuple(_render_relation(value) for value in observation.correction_relations)
        for observation in observations
    }
    if len(dois) != 1:
        rules.add("bibliography.concordance.doi_mismatch")
    if len(titles) != 1:
        rules.add("bibliography.concordance.title_mismatch")
    if len(authors) != 1:
        rules.add("bibliography.concordance.authors_mismatch")
    if len(years) != 1:
        rules.add("bibliography.concordance.year_mismatch")
    if any(not value.license_reported or not value.license_urls for value in observations):
        rules.add("bibliography.concordance.license_missing")
    elif len(license_sets) != 1:
        rules.add("bibliography.concordance.license_mismatch")
    if any(not value.correction_relations_checked for value in observations):
        rules.add("bibliography.concordance.correction_relation_unchecked")
    elif len(relation_sets) != 1:
        rules.add("bibliography.concordance.correction_relation_mismatch")
    elif next(iter(relation_sets), ()):
        rules.add("bibliography.concordance.correction_relation_present")
    canonical_rules = tuple(sorted(rules))
    if canonical_rules:
        return None, canonical_rules
    return (
        NormalizedBibliographicRecordV1(
            doi=next(iter(dois)),
            title=next(iter(titles)),
            authors=next(iter(authors)),
            publication_year=next(iter(years)),
            license_urls=next(iter(license_sets)),
            correction_relations=next(iter(relation_sets)),
        ),
        (),
    )


def _normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.replace("{", "").replace("}", "")
    return " ".join(
        "".join(character if character.isalnum() else " " for character in normalized)
        .split()
    )


def _normalized_authors(
    authors: Sequence[BibliographicAuthorV1],
) -> tuple[str, ...]:
    normalized: list[str] = []
    for author in authors:
        family = _normalize_name_part(author.family)
        given_tokens = re.findall(
            r"[^\W_]+", unicodedata.normalize("NFKC", author.given).casefold()
        )
        initials = "".join(token[0] for token in given_tokens)
        normalized.append(f"{family}|{initials}")
    return tuple(normalized)


def _normalize_name_part(value: str) -> str:
    return " ".join(
        "".join(
            character if character.isalnum() else " "
            for character in unicodedata.normalize("NFKC", value).casefold()
        ).split()
    )


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is missing")
    return value.strip()


def _first_text(value: object, field_name: str) -> str:
    if isinstance(value, str):
        return _required_text(value, field_name)
    if isinstance(value, list) and value:
        return _required_text(value[0], field_name)
    raise ValueError(f"{field_name} is missing")


def _normalize_free_identifier(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if not normalized:
        raise ValueError("relation identifier is empty")
    return normalized


def _relation_key(value: BibliographicCorrectionRelationV1) -> tuple[str, str, str]:
    return (value.relation_type, value.identifier_type, value.identifier)


def _render_relation(value: BibliographicCorrectionRelationV1) -> str:
    return ":".join(_relation_key(value))


def _representation_media_type(representation: CrossrefRepresentation) -> str:
    return {
        CrossrefRepresentation.JSON: "application/json",
        CrossrefRepresentation.BIBTEX: "application/x-bibtex",
    }[representation]


def _contract_sha256(
    value: BaseModel | Mapping[str, Any],
    identity_field: str,
) -> str:
    if isinstance(value, BaseModel):
        body = value.model_dump(mode="json", exclude={identity_field})
    else:
        body = dict(value)
        body.pop(identity_field, None)
    return hashlib.sha256(
        json.dumps(
            body,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "BIBLIOGRAPHIC_CONCORDANCE_SCHEMA_VERSION",
    "BIBLIOGRAPHIC_OBSERVATION_SCHEMA_VERSION",
    "CROSSREF_METADATA_REQUEST_SCHEMA_VERSION",
    "CROSSREF_ORIGIN",
    "CROSSREF_RESPONSE_RECEIPT_SCHEMA_VERSION",
    "BibliographicAuthorV1",
    "BibliographicConcordanceReceiptV1",
    "BibliographicConcordanceStatus",
    "BibliographicCorrectionRelationV1",
    "BibliographicObservationV1",
    "CrossrefMetadataRequestV1",
    "CrossrefRepresentation",
    "CrossrefResponseReceiptV1",
    "CrossrefResponseStatus",
    "NormalizedBibliographicRecordV1",
    "bibliographic_concordance_sha256",
    "bibliographic_observation_sha256",
    "build_bibliographic_concordance_receipt_v1",
    "build_bibliographic_observation_v1",
    "build_crossref_metadata_request_v1",
    "build_crossref_response_receipt_v1",
    "crossref_request_path",
    "crossref_request_sha256",
    "crossref_response_receipt_sha256",
    "normalize_doi",
    "normalize_license_url",
]
