"""Additive v2 contracts for the settings-by-knowledge exposure experiment.

The two factors control only what the model can inspect.  Scientific settings,
project loaders, deterministic validators, permissions, artifact hashing, and
the native-input/engine/HPC prohibitions remain active in every arm.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SETTINGS_KNOWLEDGE_CONFIG_SCHEMA_VERSION = (
    "chemsmart.settings-knowledge-ablation-config.v2"
)
SETTINGS_KNOWLEDGE_RUN_SCHEMA_VERSION = (
    "chemsmart.settings-knowledge-ablation-run.v2"
)
SETTINGS_KNOWLEDGE_OUTCOME_SCHEMA_VERSION = (
    "chemsmart.settings-knowledge-ablation-outcome.v2"
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_SHA256 = r"^[0-9a-f]{64}$"
_HTTPS_ORIGIN = r"^https://[^/?#]+$"


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class SettingsKnowledgeArm(str, Enum):
    S0K0 = "S0K0"
    S1K0 = "S1K0"
    S0K1 = "S0K1"
    S1K1 = "S1K1"


class SettingsKnowledgeExposureV2(_Contract):
    """Model-visible exposure; deterministic host controls are not switches."""

    schema_version: Literal[SETTINGS_KNOWLEDGE_CONFIG_SCHEMA_VERSION] = (
        SETTINGS_KNOWLEDGE_CONFIG_SCHEMA_VERSION
    )
    scientific_settings_registry: bool = False
    domain_knowledge_packs: bool = False

    @property
    def arm(self) -> SettingsKnowledgeArm:
        return SettingsKnowledgeArm(
            f"S{int(self.scientific_settings_registry)}"
            f"K{int(self.domain_knowledge_packs)}"
        )

    def switch_values(self) -> dict[str, bool]:
        return {
            "scientific_settings_registry": self.scientific_settings_registry,
            "domain_knowledge_packs": self.domain_knowledge_packs,
        }


class SettingsKnowledgeSafetyPlaneV2(_Contract):
    """Controls which an exposure experiment is never allowed to remove."""

    permission_enforcement: Literal[True] = True
    cli_schema_validation: Literal[True] = True
    project_loader_validation: Literal[True] = True
    scientific_settings_validation: Literal[True] = True
    artifact_hash_validation: Literal[True] = True
    deterministic_safety_oracle: Literal[True] = True
    native_input_authoring_allowed: Literal[False] = False
    chemistry_engine_execution_allowed: Literal[False] = False
    hpc_execution_allowed: Literal[False] = False
    secret_persistence_allowed: Literal[False] = False


class SettingsKnowledgeFixedContextV2(_Contract):
    """Inputs held constant across all four arms for one scientific case."""

    case_id: str = Field(pattern=_IDENTIFIER)
    source_bundle_sha256: str = Field(pattern=_SHA256)
    coordinate_receipt_sha256: str | None = Field(default=None, pattern=_SHA256)
    base_prompt_template_sha256: str = Field(pattern=_SHA256)
    host_tool_catalog_sha256: str = Field(pattern=_SHA256)
    scientific_settings_registry_sha256: str = Field(pattern=_SHA256)
    domain_knowledge_catalog_sha256: str = Field(pattern=_SHA256)
    project_schema_sha256: str = Field(pattern=_SHA256)
    cli_schema_sha256: str = Field(pattern=_SHA256)
    validator_registry_sha256: str = Field(pattern=_SHA256)
    task_order_sha256: str = Field(pattern=_SHA256)
    network_budget_sha256: str = Field(pattern=_SHA256)
    provider: Literal["deepseek"] = "deepseek"
    model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    endpoint_origin: Literal["https://api.deepseek.com"] = (
        "https://api.deepseek.com"
    )
    thinking_mode: Literal["enabled"] = "enabled"
    prompt_version: str = Field(pattern=_IDENTIFIER)


class SettingsKnowledgeRunSpecV2(_Contract):
    schema_version: Literal[SETTINGS_KNOWLEDGE_RUN_SCHEMA_VERSION] = (
        SETTINGS_KNOWLEDGE_RUN_SCHEMA_VERSION
    )
    run_id: str = Field(pattern=_IDENTIFIER)
    hypothesis_id: str = Field(pattern=_IDENTIFIER)
    hypothesis: str = Field(min_length=1, max_length=1000)
    comparator: str = Field(min_length=1, max_length=1000)
    changed_factor: Literal[
        "reference",
        "scientific_settings_registry",
        "domain_knowledge_packs",
        "joint_exposure",
    ]
    expected_outcome: str = Field(min_length=1, max_length=1000)
    deterministic_oracle_ids: tuple[str, ...] = Field(min_length=1)
    novelty_rationale: str = Field(min_length=1, max_length=1000)
    order_ordinal: int = Field(ge=1, le=4)
    exposure: SettingsKnowledgeExposureV2
    safety_plane: SettingsKnowledgeSafetyPlaneV2 = Field(
        default_factory=SettingsKnowledgeSafetyPlaneV2
    )
    fixed_context: SettingsKnowledgeFixedContextV2
    rendered_prompt_sha256: str = Field(pattern=_SHA256)
    exposed_tool_schema_sha256: str = Field(pattern=_SHA256)
    exposure_sha256: str = Field(pattern=_SHA256)
    run_spec_sha256: str = Field(pattern=_SHA256)

    @field_validator("deterministic_oracle_ids")
    @classmethod
    def _canonical_oracle_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(values))) != values:
            raise ValueError("deterministic oracle IDs must be unique and sorted")
        return values

    @model_validator(mode="after")
    def _digests_are_bound(self) -> "SettingsKnowledgeRunSpecV2":
        if self.exposure_sha256 != settings_knowledge_exposure_sha256(
            self.exposure
        ):
            raise ValueError("settings/knowledge exposure digest mismatch")
        if self.run_spec_sha256 != settings_knowledge_run_spec_sha256(self):
            raise ValueError("settings/knowledge run-spec digest mismatch")
        return self


class SettingsKnowledgeRunOutcomeV2(_Contract):
    """Public, content-addressed observation over one sanitized English run."""

    schema_version: Literal[SETTINGS_KNOWLEDGE_OUTCOME_SCHEMA_VERSION] = (
        SETTINGS_KNOWLEDGE_OUTCOME_SCHEMA_VERSION
    )
    run_id: str = Field(pattern=_IDENTIFIER)
    run_spec_sha256: str = Field(pattern=_SHA256)
    observed_model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    response_language: Literal["en"] = "en"
    sanitized_response_path: str = Field(min_length=1, max_length=1024)
    sanitized_response_sha256: str = Field(pattern=_SHA256)
    public_tool_trace_sha256: str = Field(pattern=_SHA256)
    transport_attempts: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    wall_time_ms: int = Field(ge=0)
    terminal_state: Literal["complete", "blocked", "failed"]
    passed_oracle_ids: tuple[str, ...] = ()
    failed_oracle_ids: tuple[str, ...] = ()
    safety_rule_ids: tuple[str, ...] = ()
    engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0
    native_input_authored: Literal[False] = False
    secret_material_persisted: Literal[False] = False
    private_reasoning_persisted: Literal[False] = False
    receipt_sha256: str = Field(pattern=_SHA256)

    @field_validator(
        "passed_oracle_ids",
        "failed_oracle_ids",
        "safety_rule_ids",
    )
    @classmethod
    def _canonical_rule_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(values))) != values:
            raise ValueError("outcome rule IDs must be unique and sorted")
        return values

    @model_validator(mode="after")
    def _outcome_is_consistent(self) -> "SettingsKnowledgeRunOutcomeV2":
        if set(self.passed_oracle_ids).intersection(self.failed_oracle_ids):
            raise ValueError("an oracle cannot both pass and fail")
        if self.receipt_sha256 != settings_knowledge_outcome_sha256(self):
            raise ValueError("settings/knowledge outcome digest mismatch")
        return self


def build_settings_knowledge_run_spec(
    *,
    run_id: str,
    hypothesis_id: str,
    hypothesis: str,
    comparator: str,
    changed_factor: Literal[
        "reference",
        "scientific_settings_registry",
        "domain_knowledge_packs",
        "joint_exposure",
    ],
    expected_outcome: str,
    deterministic_oracle_ids: tuple[str, ...],
    novelty_rationale: str,
    order_ordinal: int,
    exposure: SettingsKnowledgeExposureV2,
    fixed_context: SettingsKnowledgeFixedContextV2,
    rendered_prompt_sha256: str,
    exposed_tool_schema_sha256: str,
) -> SettingsKnowledgeRunSpecV2:
    body: dict[str, Any] = {
        "schema_version": SETTINGS_KNOWLEDGE_RUN_SCHEMA_VERSION,
        "run_id": run_id,
        "hypothesis_id": hypothesis_id,
        "hypothesis": hypothesis,
        "comparator": comparator,
        "changed_factor": changed_factor,
        "expected_outcome": expected_outcome,
        "deterministic_oracle_ids": deterministic_oracle_ids,
        "novelty_rationale": novelty_rationale,
        "order_ordinal": order_ordinal,
        "exposure": exposure,
        "safety_plane": SettingsKnowledgeSafetyPlaneV2(),
        "fixed_context": fixed_context,
        "rendered_prompt_sha256": rendered_prompt_sha256,
        "exposed_tool_schema_sha256": exposed_tool_schema_sha256,
        "exposure_sha256": settings_knowledge_exposure_sha256(exposure),
    }
    body["run_spec_sha256"] = settings_knowledge_run_spec_sha256(body)
    return SettingsKnowledgeRunSpecV2.model_validate(body)


def validate_complete_settings_knowledge_block(
    runs: tuple[SettingsKnowledgeRunSpecV2, ...],
) -> tuple[str, ...]:
    """Check one counterbalanced four-arm block before provider calls."""

    findings: list[str] = []
    if len(runs) != 4:
        findings.append("ablation.v2.four_arms_required")
        return tuple(findings)
    arms = tuple(run.exposure.arm for run in runs)
    if set(arms) != set(SettingsKnowledgeArm):
        findings.append("ablation.v2.arm_coverage_mismatch")
    if len({run.run_id for run in runs}) != len(runs):
        findings.append("ablation.v2.run_id_duplicate")
    if len({run.order_ordinal for run in runs}) != 4:
        findings.append("ablation.v2.order_ordinal_mismatch")
    if len({run.fixed_context for run in runs}) != 1:
        findings.append("ablation.v2.fixed_context_drift")
    if len({run.safety_plane for run in runs}) != 1:
        findings.append("ablation.v2.safety_plane_drift")
    return tuple(sorted(set(findings)))


def settings_knowledge_exposure_sha256(
    exposure: SettingsKnowledgeExposureV2,
) -> str:
    return _sha256_json(exposure.model_dump(mode="json"))


def settings_knowledge_run_spec_sha256(
    value: SettingsKnowledgeRunSpecV2 | dict[str, Any],
) -> str:
    return _contract_sha256(value, "run_spec_sha256")


def settings_knowledge_outcome_sha256(
    value: SettingsKnowledgeRunOutcomeV2 | dict[str, Any],
) -> str:
    return _contract_sha256(value, "receipt_sha256")


def _contract_sha256(value: BaseModel | dict[str, Any], digest_field: str) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude={digest_field})
    else:
        payload = {
            key: _jsonable(item)
            for key, item in value.items()
            if key != digest_field
        }
    return _sha256_json(payload)


def _jsonable(value: object) -> object:
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


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            _jsonable(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "SETTINGS_KNOWLEDGE_CONFIG_SCHEMA_VERSION",
    "SETTINGS_KNOWLEDGE_OUTCOME_SCHEMA_VERSION",
    "SETTINGS_KNOWLEDGE_RUN_SCHEMA_VERSION",
    "SettingsKnowledgeArm",
    "SettingsKnowledgeExposureV2",
    "SettingsKnowledgeFixedContextV2",
    "SettingsKnowledgeRunOutcomeV2",
    "SettingsKnowledgeRunSpecV2",
    "SettingsKnowledgeSafetyPlaneV2",
    "build_settings_knowledge_run_spec",
    "settings_knowledge_exposure_sha256",
    "settings_knowledge_outcome_sha256",
    "settings_knowledge_run_spec_sha256",
    "validate_complete_settings_knowledge_block",
]
