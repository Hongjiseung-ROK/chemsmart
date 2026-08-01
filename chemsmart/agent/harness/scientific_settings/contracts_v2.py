"""Experimental V2 contracts for digest-addressed scientific settings.

V2 is deliberately parallel to, rather than a mutation of, the frozen V1
registry.  Its empty initial registry establishes lineage and artifact shapes
without making a comprehensive inventory authoritative before that artifact is
generated, reviewed, and content-addressed.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from chemsmart.agent.harness.scientific_settings.contracts import (
    SCIENTIFIC_SETTINGS_REGISTRY_SCHEMA_VERSION,
    EvidenceCeilingV1,
    LoaderObservation,
    RendererObservation,
    ScientificProgram,
)


SCIENTIFIC_SETTINGS_REGISTRY_V2_SCHEMA_VERSION = (
    "chemsmart.scientific-settings-registry.v2"
)
SCIENTIFIC_SETTINGS_REGISTRY_REF_V2_SCHEMA_VERSION = (
    "chemsmart.scientific-settings-registry-ref.v2"
)
SCIENTIFIC_SETTINGS_INVENTORY_V2_SCHEMA_VERSION = (
    "chemsmart.scientific-settings-inventory.v2"
)
SCIENTIFIC_SETTINGS_INVENTORY_DESCRIPTOR_V2_SCHEMA_VERSION = (
    "chemsmart.scientific-settings-inventory-descriptor.v2"
)
SCIENTIFIC_SETTING_NORMALIZATION_VERSION = (
    "chemsmart.scientific-setting-literal.v1"
)
SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION = (
    "chemsmart.scientific-setting-literal.v2"
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_SETTING_PATH = r"^[a-z][a-z0-9_.-]{0,191}$"
_RULE_ID = r"^[a-z][a-z0-9_.-]+$"
_JOB_KIND = r"^(?:\*|[a-z][a-z0-9_-]{0,79})$"
_SHA1 = r"^[0-9a-f]{40}$"
_SHA256 = r"^[0-9a-f]{64}$"
_SEMVER = (
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z.-]+)?$"
)
_SAFE_TEXT = re.compile(r"^[^\x00-\x1f\x7f]+$")
_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")
_POPULATED_NORMALIZE_RE = re.compile(r"[^a-z0-9+*(),/!]+")


class _ContractV2(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class SettingEvidenceSourceKindV2(str, Enum):
    BASIS_SET_EXCHANGE_CATALOG = "basis_set_exchange_catalog"
    CHECKED_IN_REFERENCE = "checked_in_reference"
    CHECKED_IN_LOADER_RENDERER = "checked_in_loader_renderer"
    GENERATED_CLI_SCHEMA = "generated_cli_schema"
    ENGINE_DOCUMENTATION_SNAPSHOT = "engine_documentation_snapshot"
    CURATED_REFERENCE_SNAPSHOT = "curated_reference_snapshot"


class ScientificSettingsRegistryRefV2(_ContractV2):
    """An immutable reference to a registry from another schema generation."""

    schema_version: Literal[
        SCIENTIFIC_SETTINGS_REGISTRY_REF_V2_SCHEMA_VERSION
    ] = SCIENTIFIC_SETTINGS_REGISTRY_REF_V2_SCHEMA_VERSION
    target_schema_version: str = Field(min_length=1, max_length=160)
    registry_id: str = Field(pattern=_IDENTIFIER)
    registry_version: str = Field(pattern=_SEMVER)
    registry_sha256: str = Field(pattern=_SHA256)

    @field_validator("target_schema_version")
    @classmethod
    def _safe_schema_version(cls, value: str) -> str:
        if not _SAFE_TEXT.fullmatch(value):
            raise ValueError("target schema version contains control characters")
        return value


class SettingEvidenceSourceV2(_ContractV2):
    source_id: str = Field(pattern=_IDENTIFIER)
    source_kind: SettingEvidenceSourceKindV2
    locator: str = Field(min_length=1, max_length=512)
    artifact_sha256: str = Field(pattern=_SHA256)
    source_revision: str = Field(min_length=1, max_length=160)

    @field_validator("locator", "source_revision")
    @classmethod
    def _safe_source_text(cls, value: str) -> str:
        if not _SAFE_TEXT.fullmatch(value):
            raise ValueError("source text contains control characters")
        return value


class SettingInventoryEntryV2(_ContractV2):
    """One typed-project-exposed, loader/renderer-observed literal."""

    entry_id: str = Field(pattern=_IDENTIFIER)
    program: ScientificProgram
    setting_path: str = Field(pattern=_SETTING_PATH)
    canonical_value: str = Field(min_length=1, max_length=160)
    aliases: tuple[str, ...] = ()
    applicable_job_kinds: tuple[str, ...] = Field(
        default=("*",), min_length=1
    )
    applicability_rule_ids: tuple[str, ...] = ()
    validator_enforced: bool = False
    source_ids: tuple[str, ...] = Field(min_length=1)
    loader_observation: LoaderObservation
    renderer_observation: RendererObservation
    observation_note: str = Field(min_length=1, max_length=500)
    engine_executed: Literal[False] = False
    combination_verified: Literal[False] = False

    @field_validator(
        "aliases",
        "applicable_job_kinds",
        "applicability_rule_ids",
        "source_ids",
    )
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
        if info.field_name == "aliases":
            if any(len(item) > 160 for item in value):
                raise ValueError("inventory aliases must not exceed 160 characters")
            if any(not _SAFE_TEXT.fullmatch(item) for item in value):
                raise ValueError("inventory aliases contain control characters")
            if any(not normalize_setting_literal_v2(item) for item in value):
                raise ValueError("inventory aliases must normalize to a literal")
        elif info.field_name == "applicable_job_kinds":
            if any(re.fullmatch(_JOB_KIND, item) is None for item in value):
                raise ValueError("applicable job kind is invalid")
        elif info.field_name == "applicability_rule_ids":
            if any(re.fullmatch(_RULE_ID, item) is None for item in value):
                raise ValueError("applicability rule ID is invalid")
        elif any(re.fullmatch(_IDENTIFIER, item) is None for item in value):
            raise ValueError("inventory source ID is invalid")
        return value

    @field_validator("canonical_value", "observation_note")
    @classmethod
    def _safe_entry_text(cls, value: str) -> str:
        if not _SAFE_TEXT.fullmatch(value):
            raise ValueError("inventory text contains control characters")
        return value

    @model_validator(mode="after")
    def _entry_is_observed_and_coherent(self) -> "SettingInventoryEntryV2":
        if self.loader_observation is not LoaderObservation.ACCEPTED:
            raise ValueError("V2 inventory entries require loader acceptance")
        if self.renderer_observation is not RendererObservation.PRESERVED:
            raise ValueError("V2 inventory entries require renderer preservation")
        if not normalize_setting_literal_v2(self.canonical_value):
            raise ValueError("canonical value must normalize to a literal")
        if self.validator_enforced and not self.applicability_rule_ids:
            raise ValueError(
                "validator enforcement requires an applicability rule ID"
            )
        return self


class ScientificSettingsInventoryV2(_ContractV2):
    """Content-addressed comprehensive inventory artifact contract."""

    schema_version: Literal[
        SCIENTIFIC_SETTINGS_INVENTORY_V2_SCHEMA_VERSION
    ] = SCIENTIFIC_SETTINGS_INVENTORY_V2_SCHEMA_VERSION
    inventory_id: str = Field(pattern=_IDENTIFIER)
    inventory_version: str = Field(pattern=_SEMVER)
    inventory_sha256: str = Field(pattern=_SHA256)
    normalization_version: Literal[
        SCIENTIFIC_SETTING_NORMALIZATION_VERSION,
        SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION,
    ] = SCIENTIFIC_SETTING_NORMALIZATION_VERSION
    sources: tuple[SettingEvidenceSourceV2, ...] = Field(min_length=1)
    entries: tuple[SettingInventoryEntryV2, ...] = Field(min_length=1)
    evidence_ceiling: EvidenceCeilingV1

    @field_validator("sources")
    @classmethod
    def _canonical_sources(
        cls, value: tuple[SettingEvidenceSourceV2, ...]
    ) -> tuple[SettingEvidenceSourceV2, ...]:
        ids = tuple(item.source_id for item in value)
        if len(ids) != len(set(ids)):
            raise ValueError("inventory source IDs must be unique")
        if tuple(sorted(ids)) != ids:
            raise ValueError("inventory sources must be sorted by ID")
        return value

    @field_validator("entries")
    @classmethod
    def _canonical_entries(
        cls, value: tuple[SettingInventoryEntryV2, ...]
    ) -> tuple[SettingInventoryEntryV2, ...]:
        ids = tuple(item.entry_id for item in value)
        if len(ids) != len(set(ids)):
            raise ValueError("inventory entry IDs must be unique")
        if tuple(sorted(ids)) != ids:
            raise ValueError("inventory entries must be sorted by ID")
        return value

    @model_validator(mode="after")
    def _inventory_is_consistent(self) -> "ScientificSettingsInventoryV2":
        source_ids = {item.source_id for item in self.sources}
        semantic_keys: dict[
            tuple[ScientificProgram, str, str], str
        ] = {}
        for entry in self.entries:
            if not set(entry.source_ids).issubset(source_ids):
                raise ValueError("inventory entry references an unknown source ID")
            for literal in (entry.canonical_value, *entry.aliases):
                key = (
                    entry.program,
                    entry.setting_path,
                    normalize_setting_literal_for_version(
                        literal,
                        self.normalization_version,
                    ),
                )
                previous = semantic_keys.get(key)
                if previous not in {None, entry.entry_id}:
                    raise ValueError(
                        "inventory contains an ambiguous normalized literal"
                    )
                semantic_keys[key] = entry.entry_id
        if self.inventory_sha256 != scientific_settings_inventory_v2_sha256(
            self
        ):
            raise ValueError("inventory SHA-256 does not match frozen content")
        return self


class ScientificSettingsInventoryScopeV2(_ContractV2):
    """One exact program/path partition and its inventory cardinality."""

    program: ScientificProgram
    setting_path: str = Field(pattern=_SETTING_PATH)
    entry_count: int = Field(ge=1)


class ScientificSettingsInventoryDescriptorV2(_ContractV2):
    """Exact-byte and semantic binding for one external inventory artifact."""

    schema_version: Literal[
        SCIENTIFIC_SETTINGS_INVENTORY_DESCRIPTOR_V2_SCHEMA_VERSION
    ] = SCIENTIFIC_SETTINGS_INVENTORY_DESCRIPTOR_V2_SCHEMA_VERSION
    inventory_schema_version: Literal[
        SCIENTIFIC_SETTINGS_INVENTORY_V2_SCHEMA_VERSION
    ] = SCIENTIFIC_SETTINGS_INVENTORY_V2_SCHEMA_VERSION
    normalization_version: Literal[
        SCIENTIFIC_SETTING_NORMALIZATION_VERSION,
        SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION,
    ] = SCIENTIFIC_SETTING_NORMALIZATION_VERSION
    inventory_id: str = Field(pattern=_IDENTIFIER)
    inventory_version: str = Field(pattern=_SEMVER)
    inventory_sha256: str = Field(pattern=_SHA256)
    artifact_locator: str = Field(min_length=1, max_length=512)
    artifact_sha256: str = Field(pattern=_SHA256)
    entry_count: int = Field(ge=1)
    scopes: tuple[ScientificSettingsInventoryScopeV2, ...] = Field(
        min_length=1
    )

    @field_validator("artifact_locator")
    @classmethod
    def _safe_locator(cls, value: str) -> str:
        if not _SAFE_TEXT.fullmatch(value):
            raise ValueError("artifact locator contains control characters")
        locator = PurePosixPath(value)
        if (
            locator.is_absolute()
            or any(part in {"", ".", ".."} for part in locator.parts)
            or locator.as_posix() != value
            or locator.suffix != ".json"
        ):
            raise ValueError(
                "artifact locator must be a normalized repository-relative JSON path"
            )
        return value

    @field_validator("scopes")
    @classmethod
    def _canonical_scopes(
        cls, value: tuple[ScientificSettingsInventoryScopeV2, ...]
    ) -> tuple[ScientificSettingsInventoryScopeV2, ...]:
        keys = tuple((item.program.value, item.setting_path) for item in value)
        if len(keys) != len(set(keys)):
            raise ValueError("descriptor inventory scopes must be unique")
        if tuple(sorted(keys)) != keys:
            raise ValueError("descriptor inventory scopes must be sorted")
        return value

    @model_validator(mode="after")
    def _scope_counts_are_consistent(
        self,
    ) -> "ScientificSettingsInventoryDescriptorV2":
        if sum(item.entry_count for item in self.scopes) != self.entry_count:
            raise ValueError("descriptor scope counts must equal entry_count")
        return self


class ScientificSettingsRegistryV2(_ContractV2):
    """Experimental V2 registry that preserves an exact V1 predecessor."""

    schema_version: Literal[
        SCIENTIFIC_SETTINGS_REGISTRY_V2_SCHEMA_VERSION
    ] = SCIENTIFIC_SETTINGS_REGISTRY_V2_SCHEMA_VERSION
    registry_id: str = Field(pattern=_IDENTIFIER)
    registry_version: str = Field(pattern=_SEMVER)
    registry_sha256: str = Field(pattern=_SHA256)
    chemsmart_version: str = Field(pattern=_SEMVER)
    source_revision: str = Field(pattern=_SHA1)
    cli_schema_sha256: str = Field(pattern=_SHA256)
    predecessor: ScientificSettingsRegistryRefV2
    inventories: tuple[ScientificSettingsInventoryDescriptorV2, ...]
    inventory_population_state: Literal["empty_skeleton", "populated"]
    evidence_ceiling: EvidenceCeilingV1
    experimental: Literal[True] = True
    default_runtime_authority: Literal[False] = False

    @field_validator("inventories")
    @classmethod
    def _canonical_inventories(
        cls, value: tuple[ScientificSettingsInventoryDescriptorV2, ...]
    ) -> tuple[ScientificSettingsInventoryDescriptorV2, ...]:
        ids = tuple(item.inventory_id for item in value)
        if len(ids) != len(set(ids)):
            raise ValueError("registry inventory IDs must be unique")
        if tuple(sorted(ids)) != ids:
            raise ValueError("registry inventories must be sorted by ID")
        return value

    @model_validator(mode="after")
    def _registry_is_consistent(self) -> "ScientificSettingsRegistryV2":
        if (
            self.predecessor.target_schema_version
            != SCIENTIFIC_SETTINGS_REGISTRY_SCHEMA_VERSION
        ):
            raise ValueError("V2 predecessor must reference the V1 schema")
        populated = bool(self.inventories)
        if (self.inventory_population_state == "populated") != populated:
            raise ValueError("registry inventory population state is inconsistent")
        if self.registry_sha256 != scientific_settings_registry_v2_sha256(self):
            raise ValueError("registry SHA-256 does not match frozen V2 content")
        return self


def scientific_settings_inventory_v2_sha256(
    value: ScientificSettingsInventoryV2 | Mapping[str, object],
) -> str:
    return _identity_sha256_v2(value, "inventory_sha256")


def scientific_settings_registry_v2_sha256(
    value: ScientificSettingsRegistryV2 | Mapping[str, object],
) -> str:
    return _identity_sha256_v2(value, "registry_sha256")


def normalize_setting_literal_for_version(value: str, version: str) -> str:
    """Normalize one literal with the profile bound by its inventory.

    The frozen V1 profile removes all punctuation.  That is unsafe for a
    populated basis inventory because ``6-31G``, ``6-31+G``, and ``6-31G*``
    would become the same key.  The populated profile keeps punctuation that
    carries established basis/method semantics while still folding cosmetic
    whitespace, hyphens, and underscores.
    """

    if version == SCIENTIFIC_SETTING_NORMALIZATION_VERSION:
        text = str(value or "").strip().casefold().replace("ζ", "zeta")
        return _NORMALIZE_RE.sub("", text)
    if version != SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION:
        raise ValueError(f"unknown scientific-setting normalization: {version}")
    text = (
        str(value or "")
        .strip()
        .casefold()
        .replace("ζ", "zeta")
        .replace("ω", "omega")
    )
    text = re.sub(r"[-_\s]+", "", text)
    return _POPULATED_NORMALIZE_RE.sub("", text)


def normalize_setting_literal_v2(value: str) -> str:
    """Normalize with the punctuation-safe populated inventory profile."""

    return normalize_setting_literal_for_version(
        value,
        SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION,
    )


def _identity_sha256_v2(
    value: BaseModel | Mapping[str, object], identity_field: str
) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude={identity_field})
    else:
        payload = {
            str(key): _jsonable_v2(item)
            for key, item in value.items()
            if key != identity_field
        }
    encoded = json.dumps(
        _jsonable_v2(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _jsonable_v2(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable_v2(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable_v2(item) for item in value]
    return value


__all__ = [
    "SCIENTIFIC_SETTING_NORMALIZATION_VERSION",
    "SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION",
    "SCIENTIFIC_SETTINGS_INVENTORY_DESCRIPTOR_V2_SCHEMA_VERSION",
    "SCIENTIFIC_SETTINGS_INVENTORY_V2_SCHEMA_VERSION",
    "SCIENTIFIC_SETTINGS_REGISTRY_REF_V2_SCHEMA_VERSION",
    "SCIENTIFIC_SETTINGS_REGISTRY_V2_SCHEMA_VERSION",
    "ScientificSettingsInventoryDescriptorV2",
    "ScientificSettingsInventoryScopeV2",
    "ScientificSettingsInventoryV2",
    "ScientificSettingsRegistryRefV2",
    "ScientificSettingsRegistryV2",
    "SettingEvidenceSourceKindV2",
    "SettingEvidenceSourceV2",
    "SettingInventoryEntryV2",
    "normalize_setting_literal_for_version",
    "normalize_setting_literal_v2",
    "scientific_settings_inventory_v2_sha256",
    "scientific_settings_registry_v2_sha256",
]
