"""Typed, content-addressed contracts for explicit V2 setting lookup."""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from chemsmart.agent.harness.scientific_settings.contracts import (
    EvidenceCeilingV1,
    LoaderObservation,
    RendererObservation,
    ScientificProgram,
    normalize_setting_literal,
)
from chemsmart.agent.harness.scientific_settings.contracts_v2 import (
    SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION,
    SCIENTIFIC_SETTING_NORMALIZATION_VERSION,
    normalize_setting_literal_for_version,
    normalize_setting_literal_v2,
)


SETTING_RESOLUTION_V2_SCHEMA_VERSION = (
    "chemsmart.scientific-setting-resolution.v2"
)
SCIENTIFIC_SETTINGS_LIST_V2_SCHEMA_VERSION = (
    "chemsmart.scientific-settings-list.v2"
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_SETTING_PATH = r"^[a-z][a-z0-9_.-]{0,191}$"
_RULE_ID = r"^[a-z][a-z0-9_.-]+$"
_JOB_KIND = r"^[a-z][a-z0-9_-]{0,79}$"
_SHA256 = r"^[0-9a-f]{64}$"
_SAFE_TEXT = re.compile(r"^[^\x00-\x1f\x7f]+$")


class _LookupContractV2(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class SettingResolutionStatusV2(str, Enum):
    EXACT_REGISTERED = "exact_registered"
    BLOCKED_VALIDATION_COVERAGE = "blocked_validation_coverage"
    CANDIDATE_ONLY = "candidate_only"
    UNKNOWN_UNVERIFIED = "unknown_unverified"
    INCOMPATIBLE = "incompatible"
    NOT_APPLICABLE = "not_applicable"


class SettingMatchKindV2(str, Enum):
    CANONICAL_LITERAL = "canonical_literal"
    REGISTERED_ALIAS = "registered_alias"
    FUZZY_CANDIDATE = "fuzzy_candidate"
    REGISTERED_ELSEWHERE = "registered_elsewhere"
    JOB_SCOPE_MISMATCH = "job_scope_mismatch"
    NOT_APPLICABLE = "not_applicable"
    NONE = "none"


class ScientificSettingsListStatusV2(str, Enum):
    OK = "ok"
    NOT_APPLICABLE = "not_applicable"


class SettingCandidateV2(_LookupContractV2):
    """A ranked registered entry that still requires explicit selection."""

    rank: int = Field(ge=1, le=10)
    entry_id: str = Field(pattern=_IDENTIFIER)
    canonical_value: str = Field(min_length=1, max_length=160)
    matched_literal: str = Field(min_length=1, max_length=160)
    similarity_basis_points: int = Field(ge=1, le=9999)
    source_registered: Literal[True] = True
    loader_observation: LoaderObservation
    loader_accepted: bool
    renderer_observation: RendererObservation
    renderer_preserved: bool
    applicability_rule_ids: tuple[str, ...] = ()
    applicability_rules_present: bool
    deterministic_validator_enforced: bool
    job_scope_compatible: bool
    project_candidate_eligible_after_selection: bool

    @field_validator("canonical_value", "matched_literal")
    @classmethod
    def _safe_literals(cls, value: str) -> str:
        if not _SAFE_TEXT.fullmatch(value):
            raise ValueError("candidate literal contains control characters")
        if not (
            normalize_setting_literal(value) or normalize_setting_literal_v2(value)
        ):
            raise ValueError("candidate literal must normalize to a value")
        return value

    @field_validator("applicability_rule_ids")
    @classmethod
    def _canonical_rules(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_rule_ids(value)

    @model_validator(mode="after")
    def _candidate_is_consistent(self) -> "SettingCandidateV2":
        _validate_observations(
            source_registered=self.source_registered,
            loader_observation=self.loader_observation,
            loader_accepted=self.loader_accepted,
            renderer_observation=self.renderer_observation,
            renderer_preserved=self.renderer_preserved,
            applicability_rule_ids=self.applicability_rule_ids,
            applicability_rules_present=self.applicability_rules_present,
            deterministic_validator_enforced=(
                self.deterministic_validator_enforced
            ),
        )
        expected_eligible = bool(
            self.loader_accepted
            and self.renderer_preserved
            and self.job_scope_compatible
            and (
                not self.applicability_rules_present
                or self.deterministic_validator_enforced
            )
        )
        if self.project_candidate_eligible_after_selection != expected_eligible:
            raise ValueError("candidate eligibility is inconsistent")
        return self


class SettingResolutionV2(_LookupContractV2):
    """One conservative V2 resolution against explicitly supplied evidence."""

    schema_version: Literal[SETTING_RESOLUTION_V2_SCHEMA_VERSION] = (
        SETTING_RESOLUTION_V2_SCHEMA_VERSION
    )
    resolution_sha256: str = Field(pattern=_SHA256)
    registry_sha256: str = Field(pattern=_SHA256)
    inventory_sha256s: tuple[str, ...] = Field(min_length=1)
    normalization_version: Literal[
        SCIENTIFIC_SETTING_NORMALIZATION_VERSION,
        SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION,
    ]
    program: ScientificProgram
    setting_path: str = Field(pattern=_SETTING_PATH)
    requested_value: str = Field(min_length=1, max_length=300)
    normalized_requested_value: str = Field(min_length=1, max_length=300)
    job_kind: str = Field(pattern=_JOB_KIND)
    status: SettingResolutionStatusV2
    matched_by: SettingMatchKindV2
    entry_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    canonical_value: str | None = Field(default=None, max_length=160)
    candidates: tuple[SettingCandidateV2, ...] = ()
    source_registered: bool
    loader_observation: LoaderObservation
    loader_accepted: bool
    renderer_observation: RendererObservation
    renderer_preserved: bool
    applicability_rule_ids: tuple[str, ...] = ()
    applicability_rules_present: bool
    deterministic_validator_enforced: bool
    job_scope_compatible: bool | None
    project_candidate_eligible: bool
    reason_rule_id: str = Field(pattern=_RULE_ID)
    evidence_ceiling: EvidenceCeilingV1

    @field_validator("inventory_sha256s")
    @classmethod
    def _canonical_inventory_hashes(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if len(value) != len(set(value)) or tuple(sorted(value)) != value:
            raise ValueError("inventory SHA-256 values must be unique and sorted")
        if any(re.fullmatch(_SHA256, item) is None for item in value):
            raise ValueError("inventory SHA-256 is invalid")
        return value

    @field_validator("applicability_rule_ids")
    @classmethod
    def _canonical_rules(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_rule_ids(value)

    @field_validator("requested_value", "canonical_value")
    @classmethod
    def _safe_resolution_literals(cls, value: str | None) -> str | None:
        if value is not None and (
            not _SAFE_TEXT.fullmatch(value)
            or not (
                normalize_setting_literal(value)
                or normalize_setting_literal_v2(value)
            )
        ):
            raise ValueError("resolution literal is invalid")
        return value

    @field_validator("candidates")
    @classmethod
    def _canonical_candidates(
        cls, value: tuple[SettingCandidateV2, ...]
    ) -> tuple[SettingCandidateV2, ...]:
        ranks = tuple(item.rank for item in value)
        if ranks != tuple(range(1, len(value) + 1)):
            raise ValueError("candidate ranks must be contiguous")
        ids = tuple(item.entry_id for item in value)
        if len(ids) != len(set(ids)):
            raise ValueError("candidate entries must be unique")
        keys = tuple(
            (
                -item.similarity_basis_points,
                item.canonical_value.casefold(),
                item.entry_id,
            )
            for item in value
        )
        if tuple(sorted(keys)) != keys:
            raise ValueError("candidates must use deterministic score ordering")
        return value

    @model_validator(mode="after")
    def _resolution_is_consistent(self) -> "SettingResolutionV2":
        expected_normalization = normalize_setting_literal_for_version(
            self.requested_value,
            self.normalization_version,
        )
        if self.normalized_requested_value != expected_normalization:
            raise ValueError("normalized requested value is not canonical")
        _validate_observations(
            source_registered=self.source_registered,
            loader_observation=self.loader_observation,
            loader_accepted=self.loader_accepted,
            renderer_observation=self.renderer_observation,
            renderer_preserved=self.renderer_preserved,
            applicability_rule_ids=self.applicability_rule_ids,
            applicability_rules_present=self.applicability_rules_present,
            deterministic_validator_enforced=(
                self.deterministic_validator_enforced
            ),
        )
        expected_project_eligible = bool(
            self.source_registered
            and self.loader_accepted
            and self.renderer_preserved
            and self.job_scope_compatible is True
            and (
                not self.applicability_rules_present
                or self.deterministic_validator_enforced
            )
            and self.status is SettingResolutionStatusV2.EXACT_REGISTERED
        )
        if self.project_candidate_eligible != expected_project_eligible:
            raise ValueError("project-candidate eligibility is inconsistent")

        has_exact = self.entry_id is not None and self.canonical_value is not None
        exact_match_kinds = {
            SettingMatchKindV2.CANONICAL_LITERAL,
            SettingMatchKindV2.REGISTERED_ALIAS,
        }
        if self.status is SettingResolutionStatusV2.EXACT_REGISTERED:
            if not has_exact or self.matched_by not in exact_match_kinds:
                raise ValueError("exact resolution requires a registered entry")
            if self.candidates or not self.source_registered:
                raise ValueError("exact resolution cannot contain candidates")
            if self.job_scope_compatible is not True:
                raise ValueError("exact resolution requires compatible job scope")
            if self.applicability_rules_present and not (
                self.deterministic_validator_enforced
            ):
                raise ValueError("exact resolution has an applicability gap")
            if not self.project_candidate_eligible:
                raise ValueError("exact resolution must be project eligible")
        elif (
            self.status
            is SettingResolutionStatusV2.BLOCKED_VALIDATION_COVERAGE
        ):
            if not has_exact or self.matched_by not in exact_match_kinds:
                raise ValueError("coverage block requires a registered entry")
            if self.candidates or not self.source_registered:
                raise ValueError("coverage block cannot contain candidates")
            if self.job_scope_compatible is not True:
                raise ValueError("coverage block requires compatible job scope")
            if not self.applicability_rules_present:
                raise ValueError("coverage block requires applicability rules")
            if self.deterministic_validator_enforced:
                raise ValueError("coverage block cannot claim validator enforcement")
            if self.project_candidate_eligible:
                raise ValueError("coverage block cannot be project eligible")
        elif self.status is SettingResolutionStatusV2.CANDIDATE_ONLY:
            if not self.candidates or self.matched_by is not (
                SettingMatchKindV2.FUZZY_CANDIDATE
            ):
                raise ValueError("candidate-only result requires fuzzy candidates")
            if has_exact or self.source_registered:
                raise ValueError("fuzzy result cannot assert exact registration")
            _require_unobserved_noneligible(self)
        elif self.status is SettingResolutionStatusV2.UNKNOWN_UNVERIFIED:
            if self.candidates or has_exact:
                raise ValueError("unknown result cannot assert a match")
            if self.matched_by is not SettingMatchKindV2.NONE:
                raise ValueError("unknown result has an invalid match kind")
            _require_unobserved_noneligible(self)
        elif self.status is SettingResolutionStatusV2.NOT_APPLICABLE:
            if self.candidates or has_exact:
                raise ValueError("not-applicable result cannot assert a match")
            if self.matched_by is not SettingMatchKindV2.NOT_APPLICABLE:
                raise ValueError("not-applicable result has an invalid match kind")
            _require_unobserved_noneligible(self)
        elif self.status is SettingResolutionStatusV2.INCOMPATIBLE:
            if not has_exact or not self.source_registered or self.candidates:
                raise ValueError("incompatible result requires a registered entry")
            if self.matched_by is SettingMatchKindV2.JOB_SCOPE_MISMATCH:
                if self.job_scope_compatible is not False:
                    raise ValueError("job mismatch requires incompatible job scope")
            elif self.matched_by is SettingMatchKindV2.REGISTERED_ELSEWHERE:
                if self.job_scope_compatible is not None:
                    raise ValueError("elsewhere match has no requested job scope")
            else:
                raise ValueError("incompatible result has an invalid match kind")
            if self.project_candidate_eligible:
                raise ValueError("incompatible result cannot be project eligible")

        if self.resolution_sha256 != scientific_setting_resolution_v2_sha256(
            self
        ):
            raise ValueError("V2 resolution SHA-256 does not match content")
        return self


class ScientificSettingsListItemV2(_LookupContractV2):
    rank: int = Field(ge=1, le=50)
    entry_id: str = Field(pattern=_IDENTIFIER)
    canonical_value: str = Field(min_length=1, max_length=160)
    matched_literal: str | None = Field(default=None, max_length=160)
    similarity_basis_points: int | None = Field(default=None, ge=1, le=10000)
    source_registered: Literal[True] = True
    loader_observation: LoaderObservation
    loader_accepted: bool
    renderer_observation: RendererObservation
    renderer_preserved: bool
    applicability_rule_ids: tuple[str, ...] = ()
    applicability_rules_present: bool
    deterministic_validator_enforced: bool
    job_scope_compatible: bool
    project_candidate_eligible: bool

    @field_validator("canonical_value", "matched_literal")
    @classmethod
    def _safe_item_literals(cls, value: str | None) -> str | None:
        if value is not None and (
            not _SAFE_TEXT.fullmatch(value)
            or not (
                normalize_setting_literal(value)
                or normalize_setting_literal_v2(value)
            )
        ):
            raise ValueError("list-item literal is invalid")
        return value

    @field_validator("applicability_rule_ids")
    @classmethod
    def _canonical_rules(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_rule_ids(value)

    @model_validator(mode="after")
    def _item_is_consistent(self) -> "ScientificSettingsListItemV2":
        _validate_observations(
            source_registered=self.source_registered,
            loader_observation=self.loader_observation,
            loader_accepted=self.loader_accepted,
            renderer_observation=self.renderer_observation,
            renderer_preserved=self.renderer_preserved,
            applicability_rule_ids=self.applicability_rule_ids,
            applicability_rules_present=self.applicability_rules_present,
            deterministic_validator_enforced=(
                self.deterministic_validator_enforced
            ),
        )
        expected_eligible = bool(
            self.loader_accepted
            and self.renderer_preserved
            and self.job_scope_compatible
            and (
                not self.applicability_rules_present
                or self.deterministic_validator_enforced
            )
        )
        if self.project_candidate_eligible != expected_eligible:
            raise ValueError("list-item eligibility is inconsistent")
        if (self.matched_literal is None) != (
            self.similarity_basis_points is None
        ):
            raise ValueError("list-item similarity fields must appear together")
        return self


class ScientificSettingsListV2(_LookupContractV2):
    """A bounded, typed view over an explicit populated V2 registry."""

    schema_version: Literal[SCIENTIFIC_SETTINGS_LIST_V2_SCHEMA_VERSION] = (
        SCIENTIFIC_SETTINGS_LIST_V2_SCHEMA_VERSION
    )
    listing_sha256: str = Field(pattern=_SHA256)
    registry_sha256: str = Field(pattern=_SHA256)
    inventory_sha256s: tuple[str, ...] = Field(min_length=1)
    normalization_version: Literal[
        SCIENTIFIC_SETTING_NORMALIZATION_VERSION,
        SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION,
    ]
    program: ScientificProgram
    setting_path: str = Field(pattern=_SETTING_PATH)
    query: str = Field(max_length=300)
    normalized_query: str = Field(max_length=300)
    job_kind: str = Field(pattern=_JOB_KIND)
    limit: int = Field(ge=1, le=50)
    status: ScientificSettingsListStatusV2
    inventory_count: int = Field(ge=0)
    matched_count: int = Field(ge=0)
    returned_count: int = Field(ge=0, le=50)
    truncated: bool
    items: tuple[ScientificSettingsListItemV2, ...]
    reason_rule_ids: tuple[str, ...]
    token_policy: Literal["bounded_view_only"] = "bounded_view_only"
    evidence_ceiling: EvidenceCeilingV1

    @field_validator("query")
    @classmethod
    def _safe_query(cls, value: str) -> str:
        if value and not _SAFE_TEXT.fullmatch(value):
            raise ValueError("list query contains control characters")
        return value

    @field_validator("inventory_sha256s")
    @classmethod
    def _canonical_inventory_hashes(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if len(value) != len(set(value)) or tuple(sorted(value)) != value:
            raise ValueError("inventory SHA-256 values must be unique and sorted")
        if any(re.fullmatch(_SHA256, item) is None for item in value):
            raise ValueError("inventory SHA-256 is invalid")
        return value

    @field_validator("reason_rule_ids")
    @classmethod
    def _canonical_rules(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_rule_ids(value)

    @field_validator("items")
    @classmethod
    def _canonical_items(
        cls, value: tuple[ScientificSettingsListItemV2, ...]
    ) -> tuple[ScientificSettingsListItemV2, ...]:
        ranks = tuple(item.rank for item in value)
        if ranks != tuple(range(1, len(value) + 1)):
            raise ValueError("list ranks must be contiguous")
        ids = tuple(item.entry_id for item in value)
        if len(ids) != len(set(ids)):
            raise ValueError("list entries must be unique")
        return value

    @model_validator(mode="after")
    def _listing_is_consistent(self) -> "ScientificSettingsListV2":
        expected_normalization = normalize_setting_literal_for_version(
            self.query,
            self.normalization_version,
        )
        if self.normalized_query != expected_normalization:
            raise ValueError("normalized list query is not canonical")
        if self.returned_count != len(self.items):
            raise ValueError("returned_count does not match list items")
        if not (
            self.inventory_count >= self.matched_count >= self.returned_count
        ):
            raise ValueError("list counts are inconsistent")
        if self.truncated != (self.matched_count > self.returned_count):
            raise ValueError("list truncation flag is inconsistent")
        if self.normalized_query:
            if any(
                item.similarity_basis_points is None
                or item.matched_literal is None
                for item in self.items
            ):
                raise ValueError("searched list items require similarity evidence")
            keys = tuple(
                (
                    -int(item.similarity_basis_points or 0),
                    item.canonical_value.casefold(),
                    item.entry_id,
                )
                for item in self.items
            )
        else:
            if any(
                item.similarity_basis_points is not None
                or item.matched_literal is not None
                for item in self.items
            ):
                raise ValueError("unfiltered list items cannot claim similarity")
            keys = tuple(
                (item.canonical_value.casefold(), item.entry_id)
                for item in self.items
            )
        if tuple(sorted(keys)) != keys:
            raise ValueError("list items must use deterministic ordering")
        if self.status is ScientificSettingsListStatusV2.NOT_APPLICABLE:
            if any(
                (
                    self.inventory_count,
                    self.matched_count,
                    self.returned_count,
                    len(self.items),
                )
            ):
                raise ValueError("not-applicable list must be empty")
            if self.reason_rule_ids != (
                "scientific_settings.v2.xtb_basis_not_applicable",
            ):
                raise ValueError("not-applicable list needs its rule ID")
        elif self.reason_rule_ids:
            raise ValueError("successful list must not contain reason rules")
        if self.listing_sha256 != scientific_settings_list_v2_sha256(self):
            raise ValueError("V2 listing SHA-256 does not match content")
        return self


def scientific_setting_resolution_v2_sha256(
    value: SettingResolutionV2 | Mapping[str, object],
) -> str:
    return _identity_sha256(value, "resolution_sha256")


def scientific_settings_list_v2_sha256(
    value: ScientificSettingsListV2 | Mapping[str, object],
) -> str:
    return _identity_sha256(value, "listing_sha256")


def _validate_rule_ids(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(value) != len(set(value)) or tuple(sorted(value)) != value:
        raise ValueError("applicability rule IDs must be unique and sorted")
    if any(re.fullmatch(_RULE_ID, item) is None for item in value):
        raise ValueError("applicability rule ID is invalid")
    return value


def _validate_observations(
    *,
    source_registered: bool,
    loader_observation: LoaderObservation,
    loader_accepted: bool,
    renderer_observation: RendererObservation,
    renderer_preserved: bool,
    applicability_rule_ids: tuple[str, ...],
    applicability_rules_present: bool,
    deterministic_validator_enforced: bool,
) -> None:
    if loader_accepted != (loader_observation is LoaderObservation.ACCEPTED):
        raise ValueError("loader acceptance observation is inconsistent")
    if renderer_preserved != (
        renderer_observation is RendererObservation.PRESERVED
    ):
        raise ValueError("renderer preservation observation is inconsistent")
    if applicability_rules_present != bool(applicability_rule_ids):
        raise ValueError("applicability-rule observation is inconsistent")
    if deterministic_validator_enforced and not applicability_rules_present:
        raise ValueError("validator enforcement requires an applicability rule")
    if not source_registered and any(
        (
            loader_accepted,
            renderer_preserved,
            applicability_rules_present,
            deterministic_validator_enforced,
        )
    ):
        raise ValueError("unregistered literal cannot assert entry observations")


def _require_unobserved_noneligible(resolution: SettingResolutionV2) -> None:
    if resolution.source_registered:
        raise ValueError("non-exact resolution cannot assert registration")
    if resolution.loader_observation is not LoaderObservation.NOT_OBSERVED:
        raise ValueError("non-exact resolution cannot assert loader observation")
    if resolution.renderer_observation is not RendererObservation.NOT_OBSERVED:
        raise ValueError("non-exact resolution cannot assert renderer observation")
    if resolution.job_scope_compatible is not None:
        raise ValueError("non-exact resolution has no registered job scope")
    if resolution.project_candidate_eligible:
        raise ValueError("non-exact resolution cannot be project eligible")


def _identity_sha256(
    value: BaseModel | Mapping[str, object], identity_field: str
) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude={identity_field})
    else:
        payload = {
            str(key): _jsonable(item)
            for key, item in value.items()
            if key != identity_field
        }
    encoded = json.dumps(
        _jsonable(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


__all__ = [
    "SCIENTIFIC_SETTINGS_LIST_V2_SCHEMA_VERSION",
    "SETTING_RESOLUTION_V2_SCHEMA_VERSION",
    "ScientificSettingsListItemV2",
    "ScientificSettingsListStatusV2",
    "ScientificSettingsListV2",
    "SettingCandidateV2",
    "SettingMatchKindV2",
    "SettingResolutionStatusV2",
    "SettingResolutionV2",
    "scientific_setting_resolution_v2_sha256",
    "scientific_settings_list_v2_sha256",
]
