"""Additive, content-addressed scientific-setting registry contracts.

The registry proves only that a setting literal has a reviewed, frozen entry
for a specific ChemSmart source snapshot.  It does not prove that a setting
combination is chemically suitable, that safe preview passed, or that an
engine accepted or executed the generated input.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCIENTIFIC_SETTINGS_REGISTRY_SCHEMA_VERSION = (
    "chemsmart.scientific-settings-registry.v1"
)
SCIENTIFIC_SETTINGS_OVERLAY_SCHEMA_VERSION = (
    "chemsmart.scientific-settings-overlay.v1"
)
SETTING_RESOLUTION_SCHEMA_VERSION = (
    "chemsmart.scientific-setting-resolution.v1"
)
SCIENTIFIC_SETTINGS_VALIDATION_RECEIPT_SCHEMA_VERSION = (
    "chemsmart.scientific-settings-validation-receipt.v1"
)
EVIDENCE_CEILING_SCHEMA_VERSION = (
    "chemsmart.scientific-settings-evidence-ceiling.v1"
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_SETTING_PATH = r"^[a-z][a-z0-9_.-]{0,191}$"
_RULE_ID = r"^scientific_settings\.[a-z0-9_.-]+$"
_SHA1 = r"^[0-9a-f]{40}$"
_SHA256 = r"^[0-9a-f]{64}$"
_SEMVER = (
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z.-]+)?$"
)
_SAFE_TEXT = re.compile(r"^[^\x00-\x1f\x7f]+$")
_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class ScientificProgram(str, Enum):
    GAUSSIAN = "gaussian"
    ORCA = "orca"
    XTB = "xtb"


class SettingResolutionStatus(str, Enum):
    EXACT_REGISTERED = "exact_registered"
    CANDIDATE_ONLY = "candidate_only"
    UNKNOWN_UNVERIFIED = "unknown_unverified"
    INCOMPATIBLE = "incompatible"


class SettingMatchKind(str, Enum):
    CANONICAL_LITERAL = "canonical_literal"
    REGISTERED_ALIAS = "registered_alias"
    FUZZY_CANDIDATE = "fuzzy_candidate"
    REGISTERED_ELSEWHERE = "registered_elsewhere"
    JOB_SCOPE_MISMATCH = "job_scope_mismatch"
    NONE = "none"


class LoaderObservation(str, Enum):
    ACCEPTED = "accepted"
    NOT_OBSERVED = "not_observed"


class RendererObservation(str, Enum):
    PRESERVED = "preserved"
    NOT_PRESERVED = "not_preserved"
    NOT_OBSERVED = "not_observed"


class EvidenceCeilingV1(_Contract):
    """Maximum claim permitted by this registry milestone."""

    schema_version: Literal[EVIDENCE_CEILING_SCHEMA_VERSION] = (
        EVIDENCE_CEILING_SCHEMA_VERSION
    )
    maximum_claim: Literal["loader_renderer_verification_only"] = (
        "loader_renderer_verification_only"
    )
    safe_preview_executed: Literal[False] = False
    engine_executed: Literal[False] = False
    scientific_adequacy_verified: Literal[False] = False
    setting_combination_verified: Literal[False] = False


class SettingEvidenceSourceV1(_Contract):
    source_id: str = Field(pattern=_IDENTIFIER)
    source_kind: Literal[
        "basis_set_exchange_catalog",
        "checked_in_reference",
        "checked_in_loader_renderer",
        "generated_cli_schema",
    ]
    locator: str = Field(min_length=1, max_length=512)
    artifact_sha256: str = Field(pattern=_SHA256)
    source_revision: str = Field(min_length=1, max_length=80)

    @field_validator("locator", "source_revision")
    @classmethod
    def _safe_text(cls, value: str) -> str:
        if not _SAFE_TEXT.fullmatch(value):
            raise ValueError("source text must not contain control characters")
        return value


class SettingCapabilityV1(_Contract):
    """One separately reviewable setting literal and its observed boundary."""

    capability_id: str = Field(pattern=_IDENTIFIER)
    program: ScientificProgram
    setting_path: str = Field(pattern=_SETTING_PATH)
    canonical_value: str = Field(min_length=1, max_length=160)
    aliases: tuple[str, ...] = ()
    applicable_job_kinds: tuple[str, ...] = ("*",)
    source_ids: tuple[str, ...] = Field(min_length=1)
    loader_observation: LoaderObservation
    renderer_observation: RendererObservation
    observation_note: str = Field(min_length=1, max_length=500)
    engine_executed: Literal[False] = False
    combination_verified: Literal[False] = False

    @field_validator("aliases", "applicable_job_kinds", "source_ids")
    @classmethod
    def _canonical_strings(
        cls, value: tuple[str, ...], info: Any
    ) -> tuple[str, ...]:
        if any(not item for item in value):
            raise ValueError(f"{info.field_name} must not contain empty values")
        if len(value) != len(set(value)):
            raise ValueError(f"{info.field_name} must be unique")
        if tuple(sorted(value, key=str.casefold)) != value:
            raise ValueError(f"{info.field_name} must be canonically sorted")
        return value

    @field_validator("canonical_value", "observation_note")
    @classmethod
    def _safe_capability_text(cls, value: str) -> str:
        if not _SAFE_TEXT.fullmatch(value):
            raise ValueError("capability text must not contain controls")
        return value

    @model_validator(mode="after")
    def _observation_is_coherent(self) -> "SettingCapabilityV1":
        if (
            self.loader_observation is LoaderObservation.NOT_OBSERVED
            and self.renderer_observation is RendererObservation.PRESERVED
        ):
            raise ValueError(
                "renderer preservation cannot be asserted without a loader "
                "observation"
            )
        return self


class ScientificSettingsOverlayV1(_Contract):
    schema_version: Literal[SCIENTIFIC_SETTINGS_OVERLAY_SCHEMA_VERSION] = (
        SCIENTIFIC_SETTINGS_OVERLAY_SCHEMA_VERSION
    )
    overlay_id: str = Field(pattern=_IDENTIFIER)
    overlay_version: str = Field(pattern=_SEMVER)
    overlay_sha256: str = Field(pattern=_SHA256)
    program: ScientificProgram
    source_ids: tuple[str, ...] = Field(min_length=1)
    capabilities: tuple[SettingCapabilityV1, ...] = Field(min_length=1)
    evidence_ceiling: EvidenceCeilingV1

    @field_validator("source_ids")
    @classmethod
    def _canonical_source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("overlay source IDs must be unique")
        if tuple(sorted(value)) != value:
            raise ValueError("overlay source IDs must be sorted")
        return value

    @field_validator("capabilities")
    @classmethod
    def _canonical_capabilities(
        cls, value: tuple[SettingCapabilityV1, ...]
    ) -> tuple[SettingCapabilityV1, ...]:
        ids = tuple(item.capability_id for item in value)
        if len(ids) != len(set(ids)):
            raise ValueError("overlay capability IDs must be unique")
        if tuple(sorted(ids)) != ids:
            raise ValueError("overlay capabilities must be sorted by ID")
        return value

    @model_validator(mode="after")
    def _overlay_is_consistent(self) -> "ScientificSettingsOverlayV1":
        if any(item.program is not self.program for item in self.capabilities):
            raise ValueError("overlay capabilities must match overlay program")
        if any(
            not set(item.source_ids).issubset(self.source_ids)
            for item in self.capabilities
        ):
            raise ValueError("capability source IDs must be declared by overlay")
        if self.overlay_sha256 != scientific_settings_overlay_sha256(self):
            raise ValueError("overlay SHA-256 does not match frozen content")
        return self


class ScientificSettingsRegistryV1(_Contract):
    schema_version: Literal[SCIENTIFIC_SETTINGS_REGISTRY_SCHEMA_VERSION] = (
        SCIENTIFIC_SETTINGS_REGISTRY_SCHEMA_VERSION
    )
    registry_id: str = Field(pattern=_IDENTIFIER)
    registry_version: str = Field(pattern=_SEMVER)
    registry_sha256: str = Field(pattern=_SHA256)
    chemsmart_version: str = Field(pattern=_SEMVER)
    source_revision: str = Field(pattern=_SHA1)
    cli_schema_sha256: str = Field(pattern=_SHA256)
    basis_catalog_sha256: str = Field(pattern=_SHA256)
    sources: tuple[SettingEvidenceSourceV1, ...] = Field(min_length=1)
    overlays: tuple[ScientificSettingsOverlayV1, ...] = Field(min_length=1)
    evidence_ceiling: EvidenceCeilingV1

    @field_validator("sources")
    @classmethod
    def _canonical_sources(
        cls, value: tuple[SettingEvidenceSourceV1, ...]
    ) -> tuple[SettingEvidenceSourceV1, ...]:
        ids = tuple(item.source_id for item in value)
        if len(ids) != len(set(ids)):
            raise ValueError("registry source IDs must be unique")
        if tuple(sorted(ids)) != ids:
            raise ValueError("registry sources must be sorted by ID")
        return value

    @field_validator("overlays")
    @classmethod
    def _canonical_overlays(
        cls, value: tuple[ScientificSettingsOverlayV1, ...]
    ) -> tuple[ScientificSettingsOverlayV1, ...]:
        ids = tuple(item.overlay_id for item in value)
        if len(ids) != len(set(ids)):
            raise ValueError("registry overlay IDs must be unique")
        if tuple(sorted(ids)) != ids:
            raise ValueError("registry overlays must be sorted by ID")
        return value

    @model_validator(mode="after")
    def _registry_is_consistent(self) -> "ScientificSettingsRegistryV1":
        source_by_id = {item.source_id: item for item in self.sources}
        known_source_ids = set(source_by_id)
        for overlay in self.overlays:
            if not set(overlay.source_ids).issubset(known_source_ids):
                raise ValueError("overlay references an unknown source ID")
            if overlay.evidence_ceiling != self.evidence_ceiling:
                raise ValueError("overlay evidence ceiling must match registry")

        cli_sources = [
            item
            for item in self.sources
            if item.source_kind == "generated_cli_schema"
        ]
        basis_sources = [
            item
            for item in self.sources
            if item.source_kind == "basis_set_exchange_catalog"
        ]
        if len(cli_sources) != 1:
            raise ValueError("registry requires exactly one CLI-schema source")
        if cli_sources[0].artifact_sha256 != self.cli_schema_sha256:
            raise ValueError("CLI-schema source digest does not match manifest")
        if len(basis_sources) != 1:
            raise ValueError("registry requires exactly one BSE catalog source")
        if basis_sources[0].artifact_sha256 != self.basis_catalog_sha256:
            raise ValueError("BSE source digest does not match manifest")

        aliases: dict[tuple[ScientificProgram, str, str], str] = {}
        for overlay in self.overlays:
            for capability in overlay.capabilities:
                for literal in (
                    capability.canonical_value,
                    *capability.aliases,
                ):
                    key = (
                        capability.program,
                        capability.setting_path,
                        normalize_setting_literal(literal),
                    )
                    previous = aliases.get(key)
                    if previous not in {None, capability.capability_id}:
                        raise ValueError(
                            "normalized setting alias maps to two capabilities"
                        )
                    aliases[key] = capability.capability_id

        if self.registry_sha256 != scientific_settings_registry_sha256(self):
            raise ValueError("registry SHA-256 does not match frozen content")
        return self


class SettingResolutionV1(_Contract):
    schema_version: Literal[SETTING_RESOLUTION_SCHEMA_VERSION] = (
        SETTING_RESOLUTION_SCHEMA_VERSION
    )
    resolution_sha256: str = Field(pattern=_SHA256)
    registry_sha256: str = Field(pattern=_SHA256)
    program: ScientificProgram
    setting_path: str = Field(pattern=_SETTING_PATH)
    requested_value: str = Field(min_length=1, max_length=300)
    normalized_requested_value: str = Field(min_length=1, max_length=300)
    job_kind: str | None = Field(default=None, min_length=1, max_length=80)
    status: SettingResolutionStatus
    matched_by: SettingMatchKind
    canonical_value: str | None = Field(default=None, max_length=160)
    capability_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    candidate_values: tuple[str, ...] = ()
    loader_observation: LoaderObservation = LoaderObservation.NOT_OBSERVED
    renderer_observation: RendererObservation = (
        RendererObservation.NOT_OBSERVED
    )
    loader_renderer_eligible: bool
    reason_rule_id: str = Field(pattern=_RULE_ID)
    evidence_ceiling: EvidenceCeilingV1

    @field_validator("candidate_values")
    @classmethod
    def _canonical_candidates(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("candidate values must be unique")
        if tuple(sorted(value, key=str.casefold)) != value:
            raise ValueError("candidate values must be sorted")
        return value

    @field_validator("job_kind")
    @classmethod
    def _normalize_job_kind(cls, value: str | None) -> str | None:
        return value.casefold() if value is not None else None

    @model_validator(mode="after")
    def _resolution_is_consistent(self) -> "SettingResolutionV1":
        if self.normalized_requested_value != normalize_setting_literal(
            self.requested_value
        ):
            raise ValueError("normalized requested value is not canonical")

        exact = self.status is SettingResolutionStatus.EXACT_REGISTERED
        has_match = self.capability_id is not None and self.canonical_value is not None
        if exact and not has_match:
            raise ValueError("exact resolution requires a capability match")
        if exact and self.matched_by not in {
            SettingMatchKind.CANONICAL_LITERAL,
            SettingMatchKind.REGISTERED_ALIAS,
        }:
            raise ValueError("exact resolution has an invalid match kind")
        if exact and self.candidate_values:
            raise ValueError("exact resolution must not contain candidates")

        if self.status is SettingResolutionStatus.CANDIDATE_ONLY:
            if not self.candidate_values:
                raise ValueError("candidate-only resolution needs candidates")
            if self.matched_by is not SettingMatchKind.FUZZY_CANDIDATE:
                raise ValueError("candidate-only resolution has invalid match kind")
            if has_match:
                raise ValueError("candidate-only resolution is not an exact match")

        if self.status is SettingResolutionStatus.UNKNOWN_UNVERIFIED:
            if has_match or self.candidate_values:
                raise ValueError("unknown resolution cannot assert matches")
            if self.matched_by is not SettingMatchKind.NONE:
                raise ValueError("unknown resolution has invalid match kind")

        if self.status is SettingResolutionStatus.INCOMPATIBLE:
            if not has_match:
                raise ValueError("incompatible resolution needs the conflicting match")
            if self.matched_by not in {
                SettingMatchKind.REGISTERED_ELSEWHERE,
                SettingMatchKind.JOB_SCOPE_MISMATCH,
            }:
                raise ValueError("incompatible resolution has invalid match kind")

        expected_eligible = bool(
            exact
            and self.loader_observation is LoaderObservation.ACCEPTED
            and self.renderer_observation is RendererObservation.PRESERVED
        )
        if self.loader_renderer_eligible != expected_eligible:
            raise ValueError("loader/renderer eligibility is inconsistent")
        if self.resolution_sha256 != scientific_setting_resolution_sha256(self):
            raise ValueError("resolution SHA-256 does not match content")
        return self


class ScientificSettingsValidationReceiptV1(_Contract):
    """Sidecar bound to exact project bytes without changing paper v1 types."""

    schema_version: Literal[
        SCIENTIFIC_SETTINGS_VALIDATION_RECEIPT_SCHEMA_VERSION
    ] = SCIENTIFIC_SETTINGS_VALIDATION_RECEIPT_SCHEMA_VERSION
    receipt_sha256: str = Field(pattern=_SHA256)
    project_yaml_sha256: str = Field(pattern=_SHA256)
    project_config_sha256: str | None = Field(default=None, pattern=_SHA256)
    registry_sha256: str = Field(pattern=_SHA256)
    resolutions: tuple[SettingResolutionV1, ...] = Field(min_length=1)
    all_settings_exact_registered: bool
    all_loader_renderer_observations_preserved: bool
    status: Literal[
        "registered_only",
        "blocked_resolution",
        "blocked_capability_observation",
    ]
    blocking_rule_ids: tuple[str, ...]
    evidence_ceiling: EvidenceCeilingV1
    safe_preview_executed: Literal[False] = False
    engine_executed: Literal[False] = False

    @field_validator("resolutions")
    @classmethod
    def _canonical_resolutions(
        cls, value: tuple[SettingResolutionV1, ...]
    ) -> tuple[SettingResolutionV1, ...]:
        keys = tuple(_resolution_sort_key(item) for item in value)
        if len(keys) != len(set(keys)):
            raise ValueError("sidecar resolutions must be unique")
        if tuple(sorted(keys)) != keys:
            raise ValueError("sidecar resolutions must be canonically sorted")
        return value

    @field_validator("blocking_rule_ids")
    @classmethod
    def _canonical_rule_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("blocking rule IDs must be unique")
        if tuple(sorted(value)) != value:
            raise ValueError("blocking rule IDs must be sorted")
        if any(re.fullmatch(_RULE_ID, item) is None for item in value):
            raise ValueError("blocking rule ID is invalid")
        return value

    @model_validator(mode="after")
    def _receipt_is_consistent(self) -> "ScientificSettingsValidationReceiptV1":
        if any(
            item.registry_sha256 != self.registry_sha256
            for item in self.resolutions
        ):
            raise ValueError("resolution registry digest does not match sidecar")
        if any(
            item.evidence_ceiling != self.evidence_ceiling
            for item in self.resolutions
        ):
            raise ValueError("resolution evidence ceiling does not match sidecar")

        all_exact = all(
            item.status is SettingResolutionStatus.EXACT_REGISTERED
            for item in self.resolutions
        )
        all_preserved = all(
            item.loader_renderer_eligible for item in self.resolutions
        )
        if self.all_settings_exact_registered != all_exact:
            raise ValueError("sidecar exact-registration summary is inconsistent")
        if self.all_loader_renderer_observations_preserved != all_preserved:
            raise ValueError("sidecar loader/renderer summary is inconsistent")

        expected_status: str
        expected_rule_ids: tuple[str, ...]
        if not all_exact:
            expected_status = "blocked_resolution"
            expected_rule_ids = tuple(
                sorted(
                    {
                        item.reason_rule_id
                        for item in self.resolutions
                        if item.status
                        is not SettingResolutionStatus.EXACT_REGISTERED
                    }
                )
            )
        elif not all_preserved:
            expected_status = "blocked_capability_observation"
            expected_rule_ids = (
                "scientific_settings.loader_renderer_not_ready",
            )
        else:
            expected_status = "registered_only"
            expected_rule_ids = ()
        if self.status != expected_status:
            raise ValueError("sidecar status is inconsistent")
        if self.blocking_rule_ids != expected_rule_ids:
            raise ValueError("sidecar blocking rules are inconsistent")
        if self.receipt_sha256 != scientific_settings_receipt_sha256(self):
            raise ValueError("sidecar receipt SHA-256 does not match content")
        return self


def normalize_setting_literal(value: str) -> str:
    """Normalize only for matching registered literals and aliases."""

    text = str(value or "").strip().casefold().replace("ζ", "zeta")
    return _NORMALIZE_RE.sub("", text)


def canonical_contract_json(contract: BaseModel) -> str:
    validated = type(contract).model_validate(
        contract.model_dump(mode="python")
    )
    return _canonical_json(validated.model_dump(mode="json"))


def scientific_settings_overlay_sha256(
    value: ScientificSettingsOverlayV1 | Mapping[str, object],
) -> str:
    return _identity_sha256(value, "overlay_sha256")


def scientific_settings_registry_sha256(
    value: ScientificSettingsRegistryV1 | Mapping[str, object],
) -> str:
    return _identity_sha256(value, "registry_sha256")


def scientific_setting_resolution_sha256(
    value: SettingResolutionV1 | Mapping[str, object],
) -> str:
    return _identity_sha256(value, "resolution_sha256")


def scientific_settings_receipt_sha256(
    value: ScientificSettingsValidationReceiptV1 | Mapping[str, object],
) -> str:
    return _identity_sha256(value, "receipt_sha256")


def content_sha256(value: str | bytes) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()


def _resolution_sort_key(
    resolution: SettingResolutionV1,
) -> tuple[str, str, str, str]:
    return (
        resolution.program.value,
        resolution.setting_path,
        resolution.job_kind or "",
        resolution.normalized_requested_value,
    )


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
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


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
    "EVIDENCE_CEILING_SCHEMA_VERSION",
    "SCIENTIFIC_SETTINGS_OVERLAY_SCHEMA_VERSION",
    "SCIENTIFIC_SETTINGS_REGISTRY_SCHEMA_VERSION",
    "SCIENTIFIC_SETTINGS_VALIDATION_RECEIPT_SCHEMA_VERSION",
    "SETTING_RESOLUTION_SCHEMA_VERSION",
    "EvidenceCeilingV1",
    "LoaderObservation",
    "RendererObservation",
    "ScientificProgram",
    "ScientificSettingsOverlayV1",
    "ScientificSettingsRegistryV1",
    "ScientificSettingsValidationReceiptV1",
    "SettingCapabilityV1",
    "SettingEvidenceSourceV1",
    "SettingMatchKind",
    "SettingResolutionStatus",
    "SettingResolutionV1",
    "canonical_contract_json",
    "content_sha256",
    "normalize_setting_literal",
    "scientific_setting_resolution_sha256",
    "scientific_settings_overlay_sha256",
    "scientific_settings_receipt_sha256",
    "scientific_settings_registry_sha256",
]
