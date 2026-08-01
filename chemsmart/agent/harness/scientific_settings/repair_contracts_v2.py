"""Additive, content-addressed repair contracts for Registry V2.

The frozen populated V2 registry remains immutable.  These contracts bind a
separate sidecar that can add explicitly probed predecessor capabilities and
declare whether absence from a program/path partition is authoritative.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from chemsmart.agent.harness.scientific_settings.contracts import (
    ScientificProgram,
)
from chemsmart.agent.harness.scientific_settings.contracts_v2 import (
    SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION,
    SCIENTIFIC_SETTING_NORMALIZATION_VERSION,
    SettingEvidenceSourceV2,
    SettingInventoryEntryV2,
    normalize_setting_literal_for_version,
)
from chemsmart.agent.harness.scientific_settings.lookup_contracts_v2 import (
    ScientificSettingsListV2,
    SettingMatchKindV2,
    SettingResolutionStatusV2,
    SettingResolutionV2,
)


SCIENTIFIC_SETTINGS_REPAIR_SIDECAR_V2_SCHEMA_VERSION = (
    "chemsmart.scientific-settings-repair-sidecar.v2"
)
SCIENTIFIC_SETTINGS_CARRY_FORWARD_PROBE_V2_SCHEMA_VERSION = (
    "chemsmart.scientific-settings-carry-forward-probe.v2"
)
POLICY_BOUND_SETTING_RESOLUTION_V2_SCHEMA_VERSION = (
    "chemsmart.policy-bound-setting-resolution.v2"
)
POLICY_BOUND_SCIENTIFIC_SETTINGS_LIST_V2_SCHEMA_VERSION = (
    "chemsmart.policy-bound-scientific-settings-list.v2"
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_SETTING_PATH = r"^[a-z][a-z0-9_.-]{0,191}$"
_RULE_ID = r"^[a-z][a-z0-9_.-]+$"
_SHA256 = r"^[0-9a-f]{64}$"
_SEMVER = (
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z.-]+)?$"
)


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class ScopeCompletenessV2(str, Enum):
    """Whether an absent literal can prove program/path incompatibility."""

    EXHAUSTIVE_TYPED_DOMAIN = "exhaustive_typed_domain"
    ENUMERATED_NON_EXHAUSTIVE = "enumerated_non_exhaustive"


class ScientificSettingsScopePolicyV2(_Contract):
    program: ScientificProgram
    setting_path: str = Field(pattern=_SETTING_PATH)
    completeness: ScopeCompletenessV2
    reason_rule_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("reason_rule_ids")
    @classmethod
    def _canonical_rules(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values != tuple(sorted(set(values))):
            raise ValueError("scope-policy rules must be unique and sorted")
        if any(re.fullmatch(_RULE_ID, value) is None for value in values):
            raise ValueError("scope-policy rule ID is invalid")
        return values


class CarryForwardProbeV2(_Contract):
    schema_version: Literal[
        SCIENTIFIC_SETTINGS_CARRY_FORWARD_PROBE_V2_SCHEMA_VERSION
    ] = SCIENTIFIC_SETTINGS_CARRY_FORWARD_PROBE_V2_SCHEMA_VERSION
    probe_sha256: str = Field(pattern=_SHA256)
    predecessor_capability_id: str = Field(pattern=_IDENTIFIER)
    entry_id: str = Field(pattern=_IDENTIFIER)
    program: ScientificProgram
    setting_path: str = Field(pattern=_SETTING_PATH)
    normalization_version: Literal[
        SCIENTIFIC_SETTING_NORMALIZATION_VERSION,
        SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION,
    ]
    input_literal: str = Field(min_length=1, max_length=160)
    rendered_literals: tuple[str, ...] = Field(min_length=1)
    loaded_literals: tuple[str, ...] = Field(min_length=1)
    carry_forward_canonical_value: str = Field(min_length=1, max_length=160)
    normalized_semantic_literal: str = Field(min_length=1, max_length=300)
    observed_job_kinds: tuple[str, ...] = Field(min_length=1)
    transform_id: str = Field(pattern=_IDENTIFIER)
    loader_accepted: Literal[True] = True
    renderer_preserved: Literal[True] = True
    safe_preview_executed: Literal[False] = False
    engine_executed: Literal[False] = False

    @model_validator(mode="after")
    def _probe_is_consistent(self) -> "CarryForwardProbeV2":
        if self.rendered_literals != self.loaded_literals:
            raise ValueError("carry-forward probe lost renderer/loader semantics")
        semantic_literals = (
            self.input_literal,
            *self.rendered_literals,
            *self.loaded_literals,
            self.carry_forward_canonical_value,
        )
        normalized_literals = tuple(
            normalize_setting_literal_for_version(
                literal,
                self.normalization_version,
            )
            for literal in semantic_literals
        )
        if any(not literal for literal in normalized_literals):
            raise ValueError("carry-forward probe contains an empty semantic literal")
        if set(normalized_literals) != {self.normalized_semantic_literal}:
            raise ValueError("carry-forward probe silently substituted a literal")
        if self.probe_sha256 != carry_forward_probe_v2_sha256(self):
            raise ValueError("carry-forward probe digest mismatch")
        return self


class PredecessorCapabilityDispositionV2(_Contract):
    predecessor_capability_id: str = Field(pattern=_IDENTIFIER)
    disposition: Literal[
        "present_in_bound_inventory",
        "carry_forward_probe",
        "retired",
    ]
    target_entry_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    reason_rule_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("reason_rule_ids")
    @classmethod
    def _canonical_rules(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values != tuple(sorted(set(values))):
            raise ValueError("disposition rules must be unique and sorted")
        if any(re.fullmatch(_RULE_ID, value) is None for value in values):
            raise ValueError("disposition rule ID is invalid")
        return values

    @model_validator(mode="after")
    def _target_matches_disposition(self) -> "PredecessorCapabilityDispositionV2":
        if (self.disposition == "retired") != (self.target_entry_id is None):
            raise ValueError("only retired capabilities may omit a target entry")
        return self


class ScientificSettingsRepairSidecarV2(_Contract):
    schema_version: Literal[
        SCIENTIFIC_SETTINGS_REPAIR_SIDECAR_V2_SCHEMA_VERSION
    ] = SCIENTIFIC_SETTINGS_REPAIR_SIDECAR_V2_SCHEMA_VERSION
    sidecar_id: str = Field(pattern=_IDENTIFIER)
    sidecar_version: str = Field(pattern=_SEMVER)
    sidecar_sha256: str = Field(pattern=_SHA256)
    base_registry_sha256: str = Field(pattern=_SHA256)
    base_inventory_sha256s: tuple[str, ...] = Field(min_length=1)
    predecessor_registry_sha256: str = Field(pattern=_SHA256)
    sources: tuple[SettingEvidenceSourceV2, ...] = Field(min_length=1)
    scopes: tuple[ScientificSettingsScopePolicyV2, ...] = Field(min_length=1)
    carry_forward_entries: tuple[SettingInventoryEntryV2, ...]
    carry_forward_probes: tuple[CarryForwardProbeV2, ...]
    predecessor_dispositions: tuple[
        PredecessorCapabilityDispositionV2, ...
    ] = Field(min_length=1)

    @field_validator("base_inventory_sha256s")
    @classmethod
    def _canonical_inventory_hashes(
        cls, values: tuple[str, ...]
    ) -> tuple[str, ...]:
        if values != tuple(sorted(set(values))):
            raise ValueError("base inventory hashes must be unique and sorted")
        if any(re.fullmatch(_SHA256, value) is None for value in values):
            raise ValueError("base inventory hash is invalid")
        return values

    @field_validator("sources")
    @classmethod
    def _canonical_sources(
        cls, values: tuple[SettingEvidenceSourceV2, ...]
    ) -> tuple[SettingEvidenceSourceV2, ...]:
        ids = tuple(value.source_id for value in values)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("sidecar sources must be unique and sorted")
        return values

    @field_validator("scopes")
    @classmethod
    def _canonical_scopes(
        cls, values: tuple[ScientificSettingsScopePolicyV2, ...]
    ) -> tuple[ScientificSettingsScopePolicyV2, ...]:
        keys = tuple((value.program.value, value.setting_path) for value in values)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("sidecar scopes must be unique and sorted")
        return values

    @field_validator("carry_forward_entries")
    @classmethod
    def _canonical_entries(
        cls, values: tuple[SettingInventoryEntryV2, ...]
    ) -> tuple[SettingInventoryEntryV2, ...]:
        ids = tuple(value.entry_id for value in values)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("carry-forward entries must be unique and sorted")
        return values

    @field_validator("carry_forward_probes")
    @classmethod
    def _canonical_probes(
        cls, values: tuple[CarryForwardProbeV2, ...]
    ) -> tuple[CarryForwardProbeV2, ...]:
        ids = tuple(value.predecessor_capability_id for value in values)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("carry-forward probes must be unique and sorted")
        return values

    @field_validator("predecessor_dispositions")
    @classmethod
    def _canonical_dispositions(
        cls, values: tuple[PredecessorCapabilityDispositionV2, ...]
    ) -> tuple[PredecessorCapabilityDispositionV2, ...]:
        ids = tuple(value.predecessor_capability_id for value in values)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("predecessor dispositions must be unique and sorted")
        return values

    @model_validator(mode="after")
    def _sidecar_is_consistent(self) -> "ScientificSettingsRepairSidecarV2":
        source_ids = {value.source_id for value in self.sources}
        if any(
            not set(entry.source_ids).issubset(source_ids)
            for entry in self.carry_forward_entries
        ):
            raise ValueError("carry-forward entry references an unbound source")
        entry_ids = {value.entry_id for value in self.carry_forward_entries}
        probes_by_entry = {value.entry_id for value in self.carry_forward_probes}
        carry_targets = {
            value.target_entry_id
            for value in self.predecessor_dispositions
            if value.disposition == "carry_forward_probe"
        }
        if probes_by_entry != entry_ids or carry_targets != entry_ids:
            raise ValueError("carry-forward entries, probes, and dispositions differ")
        entries_by_id = {
            value.entry_id: value for value in self.carry_forward_entries
        }
        for probe in self.carry_forward_probes:
            entry = entries_by_id[probe.entry_id]
            if (
                probe.program is not entry.program
                or probe.setting_path != entry.setting_path
            ):
                raise ValueError("carry-forward probe changed program or setting path")
            if probe.carry_forward_canonical_value != entry.canonical_value:
                raise ValueError("carry-forward probe canonical value differs from entry")
            normalized_entry = normalize_setting_literal_for_version(
                entry.canonical_value,
                probe.normalization_version,
            )
            if normalized_entry != probe.normalized_semantic_literal:
                raise ValueError("carry-forward probe and entry semantics differ")
            if "*" not in entry.applicable_job_kinds and not set(
                probe.observed_job_kinds
            ).issubset(entry.applicable_job_kinds):
                raise ValueError("carry-forward probe exceeds the observed job scope")
        if self.sidecar_sha256 != scientific_settings_repair_sidecar_v2_sha256(
            self
        ):
            raise ValueError("scientific-settings repair sidecar digest mismatch")
        return self


class PolicyBoundSettingResolutionV2(_Contract):
    schema_version: Literal[
        POLICY_BOUND_SETTING_RESOLUTION_V2_SCHEMA_VERSION
    ] = POLICY_BOUND_SETTING_RESOLUTION_V2_SCHEMA_VERSION
    binding_sha256: str = Field(pattern=_SHA256)
    sidecar_sha256: str = Field(pattern=_SHA256)
    scope_completeness: ScopeCompletenessV2
    resolution: SettingResolutionV2

    @model_validator(mode="after")
    def _binding_is_consistent(self) -> "PolicyBoundSettingResolutionV2":
        if (
            self.scope_completeness
            is ScopeCompletenessV2.ENUMERATED_NON_EXHAUSTIVE
            and self.resolution.status is SettingResolutionStatusV2.INCOMPATIBLE
            and self.resolution.matched_by is SettingMatchKindV2.REGISTERED_ELSEWHERE
        ):
            raise ValueError(
                "non-exhaustive absence cannot prove cross-program incompatibility"
            )
        if self.binding_sha256 != policy_bound_setting_resolution_v2_sha256(self):
            raise ValueError("policy-bound resolution digest mismatch")
        return self


class PolicyBoundScientificSettingsListV2(_Contract):
    schema_version: Literal[
        POLICY_BOUND_SCIENTIFIC_SETTINGS_LIST_V2_SCHEMA_VERSION
    ] = POLICY_BOUND_SCIENTIFIC_SETTINGS_LIST_V2_SCHEMA_VERSION
    binding_sha256: str = Field(pattern=_SHA256)
    sidecar_sha256: str = Field(pattern=_SHA256)
    scope_completeness: ScopeCompletenessV2
    listing: ScientificSettingsListV2

    @model_validator(mode="after")
    def _binding_is_consistent(self) -> "PolicyBoundScientificSettingsListV2":
        if self.binding_sha256 != policy_bound_scientific_settings_list_v2_sha256(
            self
        ):
            raise ValueError("policy-bound listing digest mismatch")
        return self


def _identity_sha256(value: Any, digest_field: str) -> str:
    if isinstance(value, BaseModel):
        body = value.model_dump(mode="json")
    else:
        body = dict(value)
    body[digest_field] = "0" * 64
    encoded = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def carry_forward_probe_v2_sha256(value: CarryForwardProbeV2 | Any) -> str:
    return _identity_sha256(value, "probe_sha256")


def scientific_settings_repair_sidecar_v2_sha256(
    value: ScientificSettingsRepairSidecarV2 | Any,
) -> str:
    return _identity_sha256(value, "sidecar_sha256")


def policy_bound_setting_resolution_v2_sha256(
    value: PolicyBoundSettingResolutionV2 | Any,
) -> str:
    return _identity_sha256(value, "binding_sha256")


def policy_bound_scientific_settings_list_v2_sha256(
    value: PolicyBoundScientificSettingsListV2 | Any,
) -> str:
    return _identity_sha256(value, "binding_sha256")


__all__ = [
    "CarryForwardProbeV2",
    "PolicyBoundScientificSettingsListV2",
    "PolicyBoundSettingResolutionV2",
    "PredecessorCapabilityDispositionV2",
    "ScopeCompletenessV2",
    "ScientificSettingsRepairSidecarV2",
    "ScientificSettingsScopePolicyV2",
    "carry_forward_probe_v2_sha256",
    "policy_bound_scientific_settings_list_v2_sha256",
    "policy_bound_setting_resolution_v2_sha256",
    "scientific_settings_repair_sidecar_v2_sha256",
]
