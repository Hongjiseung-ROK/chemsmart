"""Fail-closed composition of Registry V2 and typed-project readiness.

Registry lookup establishes setting-literal and applicability evidence.  The
project-readiness authority independently establishes whether ChemSmart's
typed project renderer, loader, and required-job validator preserve a project.
Neither authority is sufficient alone, so this module binds their complete
receipts into one additive decision without performing a preview or execution.

V1 intentionally has no validation-coverage discharge contract.  A later
version may add a typed, independently validated discharge; an opaque digest or
caller assertion must never discharge ``blocked_validation_coverage``.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from chemsmart.agent.harness.scientific_settings.lookup_contracts_v2 import (
    SettingResolutionStatusV2,
)
from chemsmart.agent.harness.scientific_settings.repair_contracts_v2 import (
    PolicyBoundSettingResolutionV2,
)
from chemsmart.agent.project_readiness import (
    ProjectReadinessReceiptV1,
    TypedProjectSupportStatus,
)


SCIENTIFIC_SETTINGS_READINESS_GATE_V1_SCHEMA_VERSION = (
    "chemsmart.scientific-settings-readiness-gate.v1"
)

_RULE_ID = r"^[a-z][a-z0-9_.-]+$"
_SHA256 = r"^[0-9a-f]{64}$"

_INPUTS_BOUND_RULE = "scientific_settings.readiness.inputs_content_bound"
_REGISTRY_REPLAY_RULE = "scientific_settings.readiness.registry_status_replayed"
_PROJECT_REPLAY_RULE = "scientific_settings.readiness.project_status_replayed"
_NO_RESOLUTION_RULE = "scientific_settings.readiness.no_resolution_binding"
_UNVERIFIED_RULE = "scientific_settings.readiness.unverified_setting"
_COVERAGE_RULE = (
    "scientific_settings.readiness.validation_coverage_undischarged_v1"
)
_UNSUPPORTED_RULE = "scientific_settings.readiness.unsupported_setting"
_ALL_EXACT_RULE = (
    "scientific_settings.readiness.all_resolutions_exact_project_eligible"
)
_PROJECT_SUPPORTED_RULE = (
    "scientific_settings.readiness.typed_project_supported"
)


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class ScientificSettingsReadinessStatusV1(str, Enum):
    """Conservative aggregate state for one typed project candidate."""

    PROJECT_CANDIDATE = "project_candidate"
    BLOCKED_UNVERIFIED_SETTING = "blocked_unverified_setting"
    BLOCKED_VALIDATION_COVERAGE = "blocked_validation_coverage"
    BLOCKED_MISSING_EVIDENCE = "blocked_missing_evidence"
    BLOCKED_UNSUPPORTED_SETTING = "blocked_unsupported_setting"
    BLOCKED_INVALID_SPECIFICATION = "blocked_invalid_specification"
    BLOCKED_REQUIRED_JOB_VALIDATION = "blocked_required_job_validation"
    BLOCKED_SEMANTIC_DRIFT = "blocked_semantic_drift"
    BLOCKED_ECP_BINDING = "blocked_ecp_binding"


_PROJECT_STATUS_MAP = {
    TypedProjectSupportStatus.BLOCKED_MISSING_EVIDENCE: (
        ScientificSettingsReadinessStatusV1.BLOCKED_MISSING_EVIDENCE
    ),
    TypedProjectSupportStatus.BLOCKED_UNSUPPORTED_SETTING: (
        ScientificSettingsReadinessStatusV1.BLOCKED_UNSUPPORTED_SETTING
    ),
    TypedProjectSupportStatus.BLOCKED_INVALID_SPECIFICATION: (
        ScientificSettingsReadinessStatusV1.BLOCKED_INVALID_SPECIFICATION
    ),
    TypedProjectSupportStatus.BLOCKED_REQUIRED_JOB_VALIDATION: (
        ScientificSettingsReadinessStatusV1.BLOCKED_REQUIRED_JOB_VALIDATION
    ),
    TypedProjectSupportStatus.BLOCKED_SEMANTIC_DRIFT: (
        ScientificSettingsReadinessStatusV1.BLOCKED_SEMANTIC_DRIFT
    ),
    TypedProjectSupportStatus.BLOCKED_ECP_BINDING: (
        ScientificSettingsReadinessStatusV1.BLOCKED_ECP_BINDING
    ),
}

# If independent authorities report more than one block, this order selects a
# single terminal label without dropping any of the canonical blocking rules.
_STATUS_PRECEDENCE = (
    ScientificSettingsReadinessStatusV1.BLOCKED_UNSUPPORTED_SETTING,
    ScientificSettingsReadinessStatusV1.BLOCKED_MISSING_EVIDENCE,
    ScientificSettingsReadinessStatusV1.BLOCKED_ECP_BINDING,
    ScientificSettingsReadinessStatusV1.BLOCKED_SEMANTIC_DRIFT,
    ScientificSettingsReadinessStatusV1.BLOCKED_REQUIRED_JOB_VALIDATION,
    ScientificSettingsReadinessStatusV1.BLOCKED_INVALID_SPECIFICATION,
    ScientificSettingsReadinessStatusV1.BLOCKED_UNVERIFIED_SETTING,
    ScientificSettingsReadinessStatusV1.BLOCKED_VALIDATION_COVERAGE,
)


class ScientificSettingsReadinessGateV1(_Contract):
    """Content-addressed aggregate over every supplied resolution and project.

    The nested contracts remain the evidence source.  The redundant digest
    fields make the complete input set directly inspectable and prevent a
    project receipt from silently omitting a registry resolution.
    """

    schema_version: Literal[
        SCIENTIFIC_SETTINGS_READINESS_GATE_V1_SCHEMA_VERSION
    ] = SCIENTIFIC_SETTINGS_READINESS_GATE_V1_SCHEMA_VERSION
    policy_bound_resolutions: tuple[PolicyBoundSettingResolutionV2, ...]
    project_readiness: ProjectReadinessReceiptV1
    resolution_binding_sha256s: tuple[str, ...]
    resolution_sha256s: tuple[str, ...]
    sidecar_sha256s: tuple[str, ...]
    registry_sha256s: tuple[str, ...]
    inventory_sha256s: tuple[str, ...]
    project_request_sha256: str = Field(pattern=_SHA256)
    project_readiness_receipt_sha256: str = Field(pattern=_SHA256)
    input_sha256: str = Field(pattern=_SHA256)
    validation_coverage_discharge_policy: Literal[
        "no_discharge_supported_v1"
    ] = "no_discharge_supported_v1"
    status: ScientificSettingsReadinessStatusV1
    blocking_rule_ids: tuple[str, ...]
    derivation_rule_ids: tuple[str, ...]
    gate_sha256: str = Field(pattern=_SHA256)

    @field_validator(
        "resolution_binding_sha256s",
        "resolution_sha256s",
        "sidecar_sha256s",
        "registry_sha256s",
        "inventory_sha256s",
    )
    @classmethod
    def _hashes_are_canonical(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("readiness input hashes must be unique and sorted")
        if any(re.fullmatch(_SHA256, item) is None for item in value):
            raise ValueError("readiness input hash is invalid")
        return value

    @field_validator("policy_bound_resolutions")
    @classmethod
    def _resolutions_are_canonical(
        cls,
        value: tuple[PolicyBoundSettingResolutionV2, ...],
    ) -> tuple[PolicyBoundSettingResolutionV2, ...]:
        keys = tuple(_resolution_sort_key(item) for item in value)
        if keys != tuple(sorted(keys)):
            raise ValueError("policy-bound resolutions must be canonically sorted")
        bindings = tuple(item.binding_sha256 for item in value)
        if len(bindings) != len(set(bindings)):
            raise ValueError("policy-bound resolutions must be unique")
        return value

    @field_validator("blocking_rule_ids", "derivation_rule_ids")
    @classmethod
    def _rules_are_canonical(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("readiness rule IDs must be unique and sorted")
        if any(re.fullmatch(_RULE_ID, item) is None for item in value):
            raise ValueError("readiness rule ID is invalid")
        return value

    @model_validator(mode="after")
    def _gate_is_reproducible(self) -> "ScientificSettingsReadinessGateV1":
        request = self.project_readiness.request
        for item in self.policy_bound_resolutions:
            resolution = item.resolution
            if resolution.program.value != request.program:
                raise ValueError("setting resolution belongs to another program")
            if resolution.job_kind != request.job_kind:
                raise ValueError("setting resolution belongs to another job")

        expected_refs = _input_references(
            self.policy_bound_resolutions,
            self.project_readiness,
        )
        for field_name, expected in expected_refs.items():
            if getattr(self, field_name) != expected:
                raise ValueError(f"{field_name} does not bind every gate input")

        discovery_hashes = self.project_readiness.registry_discovery.resolution_sha256s
        if discovery_hashes != self.resolution_sha256s:
            raise ValueError(
                "project-readiness discovery does not bind every resolution"
            )
        if self.input_sha256 != scientific_settings_readiness_input_sha256(
            self.policy_bound_resolutions,
            self.project_readiness,
        ):
            raise ValueError("scientific-settings readiness input digest mismatch")

        status, blocking_rules, derivation_rules = _derive_readiness(
            self.policy_bound_resolutions,
            self.project_readiness,
        )
        if self.status is not status:
            raise ValueError("scientific-settings readiness status is not reproducible")
        if self.blocking_rule_ids != blocking_rules:
            raise ValueError("scientific-settings blocking rules are not reproducible")
        if self.derivation_rule_ids != derivation_rules:
            raise ValueError(
                "scientific-settings derivation rules are not reproducible"
            )
        if self.gate_sha256 != scientific_settings_readiness_gate_v1_sha256(self):
            raise ValueError("scientific-settings readiness gate digest mismatch")
        return self


def assess_scientific_settings_readiness(
    *,
    policy_bound_resolutions: Sequence[PolicyBoundSettingResolutionV2],
    project_readiness: ProjectReadinessReceiptV1,
) -> ScientificSettingsReadinessGateV1:
    """Compose registry and project evidence into one deterministic gate."""

    resolutions = tuple(sorted(policy_bound_resolutions, key=_resolution_sort_key))
    references = _input_references(resolutions, project_readiness)
    status, blocking_rules, derivation_rules = _derive_readiness(
        resolutions,
        project_readiness,
    )
    body: dict[str, Any] = {
        "schema_version": SCIENTIFIC_SETTINGS_READINESS_GATE_V1_SCHEMA_VERSION,
        "policy_bound_resolutions": resolutions,
        "project_readiness": project_readiness,
        **references,
        "input_sha256": scientific_settings_readiness_input_sha256(
            resolutions,
            project_readiness,
        ),
        "validation_coverage_discharge_policy": "no_discharge_supported_v1",
        "status": status,
        "blocking_rule_ids": blocking_rules,
        "derivation_rule_ids": derivation_rules,
    }
    body["gate_sha256"] = scientific_settings_readiness_gate_v1_sha256(body)
    return ScientificSettingsReadinessGateV1.model_validate(body)


def scientific_settings_readiness_input_sha256(
    policy_bound_resolutions: Sequence[PolicyBoundSettingResolutionV2],
    project_readiness: ProjectReadinessReceiptV1,
) -> str:
    """Hash the exact nested evidence inputs, independently of the decision."""

    return _sha256_json(
        {
            "policy_bound_resolutions": [
                item.model_dump(mode="json")
                for item in policy_bound_resolutions
            ],
            "project_readiness": project_readiness.model_dump(mode="json"),
        }
    )


def scientific_settings_readiness_gate_v1_sha256(
    value: ScientificSettingsReadinessGateV1 | Mapping[str, Any],
) -> str:
    """Return the canonical identity of a complete readiness decision."""

    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude={"gate_sha256"})
    else:
        payload = {
            str(key): _jsonable(item)
            for key, item in value.items()
            if key != "gate_sha256"
        }
    return _sha256_json(payload)


def _derive_readiness(
    resolutions: Sequence[PolicyBoundSettingResolutionV2],
    project_readiness: ProjectReadinessReceiptV1,
) -> tuple[
    ScientificSettingsReadinessStatusV1,
    tuple[str, ...],
    tuple[str, ...],
]:
    blockers: set[str] = set()
    derivations = {
        _INPUTS_BOUND_RULE,
        _REGISTRY_REPLAY_RULE,
        _PROJECT_REPLAY_RULE,
    }
    candidate_statuses: set[ScientificSettingsReadinessStatusV1] = set()

    if not resolutions:
        blockers.add(_NO_RESOLUTION_RULE)
        candidate_statuses.add(
            ScientificSettingsReadinessStatusV1.BLOCKED_UNVERIFIED_SETTING
        )

    for item in resolutions:
        resolution = item.resolution
        status = resolution.status
        if status is SettingResolutionStatusV2.EXACT_REGISTERED:
            if not resolution.project_candidate_eligible:
                blockers.update((_UNVERIFIED_RULE, resolution.reason_rule_id))
                candidate_statuses.add(
                    ScientificSettingsReadinessStatusV1.BLOCKED_UNVERIFIED_SETTING
                )
            continue
        blockers.add(resolution.reason_rule_id)
        if status in {
            SettingResolutionStatusV2.UNKNOWN_UNVERIFIED,
            SettingResolutionStatusV2.CANDIDATE_ONLY,
        }:
            blockers.add(_UNVERIFIED_RULE)
            candidate_statuses.add(
                ScientificSettingsReadinessStatusV1.BLOCKED_UNVERIFIED_SETTING
            )
        elif status is SettingResolutionStatusV2.BLOCKED_VALIDATION_COVERAGE:
            blockers.add(_COVERAGE_RULE)
            derivations.add(
                "scientific_settings.readiness.v1_has_no_coverage_discharge"
            )
            candidate_statuses.add(
                ScientificSettingsReadinessStatusV1.BLOCKED_VALIDATION_COVERAGE
            )
        elif status in {
            SettingResolutionStatusV2.INCOMPATIBLE,
            SettingResolutionStatusV2.NOT_APPLICABLE,
        }:
            blockers.add(_UNSUPPORTED_RULE)
            candidate_statuses.add(
                ScientificSettingsReadinessStatusV1.BLOCKED_UNSUPPORTED_SETTING
            )
        else:  # pragma: no cover - enum additions must fail closed
            raise ValueError(f"unmapped setting-resolution status: {status.value}")

    project_status = project_readiness.typed_project_support.status
    if project_status is not TypedProjectSupportStatus.TYPED_PROJECT_SUPPORTED:
        try:
            mapped = _PROJECT_STATUS_MAP[project_status]
        except KeyError as exc:  # pragma: no cover - enum additions must fail closed
            raise ValueError(
                f"unmapped typed-project support status: {project_status.value}"
            ) from exc
        candidate_statuses.add(mapped)
        blockers.add(f"scientific_settings.readiness.project.{project_status.value}")
        blockers.update(project_readiness.typed_project_support.blocking_rule_ids)

    if not candidate_statuses:
        if not resolutions or any(
            item.resolution.status is not SettingResolutionStatusV2.EXACT_REGISTERED
            or not item.resolution.project_candidate_eligible
            for item in resolutions
        ):
            raise ValueError("project candidate lacks exact setting evidence")
        derivations.update((_ALL_EXACT_RULE, _PROJECT_SUPPORTED_RULE))
        return (
            ScientificSettingsReadinessStatusV1.PROJECT_CANDIDATE,
            (),
            tuple(sorted(derivations)),
        )

    selected = next(
        status for status in _STATUS_PRECEDENCE if status in candidate_statuses
    )
    return selected, tuple(sorted(blockers)), tuple(sorted(derivations))


def _input_references(
    resolutions: Sequence[PolicyBoundSettingResolutionV2],
    project_readiness: ProjectReadinessReceiptV1,
) -> dict[str, Any]:
    return {
        "resolution_binding_sha256s": tuple(
            sorted(item.binding_sha256 for item in resolutions)
        ),
        "resolution_sha256s": tuple(
            sorted(item.resolution.resolution_sha256 for item in resolutions)
        ),
        "sidecar_sha256s": tuple(
            sorted({item.sidecar_sha256 for item in resolutions})
        ),
        "registry_sha256s": tuple(
            sorted({item.resolution.registry_sha256 for item in resolutions})
        ),
        "inventory_sha256s": tuple(
            sorted(
                {
                    digest
                    for item in resolutions
                    for digest in item.resolution.inventory_sha256s
                }
            )
        ),
        "project_request_sha256": project_readiness.request.request_sha256,
        "project_readiness_receipt_sha256": project_readiness.receipt_sha256,
    }


def _resolution_sort_key(
    value: PolicyBoundSettingResolutionV2,
) -> tuple[str, str, str, str, str]:
    resolution = value.resolution
    return (
        resolution.program.value,
        resolution.setting_path,
        resolution.requested_value,
        resolution.job_kind,
        value.binding_sha256,
    )


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


__all__ = [
    "SCIENTIFIC_SETTINGS_READINESS_GATE_V1_SCHEMA_VERSION",
    "ScientificSettingsReadinessGateV1",
    "ScientificSettingsReadinessStatusV1",
    "assess_scientific_settings_readiness",
    "scientific_settings_readiness_gate_v1_sha256",
    "scientific_settings_readiness_input_sha256",
]
