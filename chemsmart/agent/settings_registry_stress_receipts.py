"""Typed preregistration and receipt contracts for Registry V2 stress runs.

These contracts bind a future DeepSeek transport to the exact repository,
registry inventories, prompt, tools, case, and deterministic oracle set.  They
do not authorize a provider request, project write, native input, or chemistry
execution.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SOURCE_BINDING_SCHEMA_VERSION = (
    "chemsmart.registry-stress-source-binding.v1"
)
REGISTRY_BINDING_SCHEMA_VERSION = (
    "chemsmart.registry-stress-registry-binding.v1"
)
STRESS_CASE_SCHEMA_VERSION = "chemsmart.registry-stress-case.v1"
STRESS_PREFLIGHT_SCHEMA_VERSION = "chemsmart.registry-stress-preflight.v1"
STRESS_RUN_SCHEMA_VERSION = "chemsmart.registry-stress-run.v1"
STRESS_OUTCOME_SCHEMA_VERSION = "chemsmart.registry-stress-outcome.v1"
STRESS_CAMPAIGN_SCHEMA_VERSION = "chemsmart.registry-stress-campaign.v1"

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_SETTING_PATH = r"^[a-z][a-z0-9_.-]{0,191}$"
_RULE_ID = r"^[a-z][a-z0-9_.-]+$"
_GIT_REF = r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$"
_SHA1 = r"^[0-9a-f]{40}$"
_SHA256 = r"^[0-9a-f]{64}$"


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class RegistryStressArm(str, Enum):
    MINIMAL = "minimal"
    REGISTRY_V1 = "registry_v1"
    REGISTRY_V2 = "registry_v2"
    REGISTRY_V2_VALIDATED = "registry_v2_validated"
    REGISTRY_V2_ADVISORY = "registry_v2_advisory"


class RegistryStressReadiness(str, Enum):
    PROJECT_CANDIDATE = "project_candidate"
    BLOCKED_UNVERIFIED_SETTING = "blocked_unverified_setting"
    BLOCKED_VALIDATION_COVERAGE = "blocked_validation_coverage"
    BLOCKED_MISSING_EVIDENCE = "blocked_missing_evidence"
    BLOCKED_INVALID_SPECIFICATION = "blocked_invalid_specification"
    BLOCKED_UNSUPPORTED_SETTING = "blocked_unsupported_setting"
    INFEASIBLE = "infeasible"


class RepositorySourceBindingV1(_Contract):
    """Exact Git worktree observation captured before credential access."""

    schema_version: Literal[SOURCE_BINDING_SCHEMA_VERSION] = (
        SOURCE_BINDING_SCHEMA_VERSION
    )
    repository_id: Literal["chemsmart"] = "chemsmart"
    branch: str = Field(pattern=_GIT_REF)
    required_remote: str = Field(pattern=_IDENTIFIER)
    required_remote_branch: str = Field(pattern=_GIT_REF)
    required_remote_url: str = Field(min_length=1, max_length=512)
    observed_remote_url: str = Field(min_length=1, max_length=512)
    base_checkpoint_sha: str = Field(pattern=_SHA1)
    head_sha: str = Field(pattern=_SHA1)
    remote_tracking_sha: str | None = Field(default=None, pattern=_SHA1)
    base_is_ancestor: Literal[True] = True
    head_matches_remote_tracking: bool
    tracked_file_count: int = Field(ge=1)
    untracked_file_count: int = Field(ge=0)
    tracked_files_sha256: str = Field(pattern=_SHA256)
    tracked_diff_sha256: str = Field(pattern=_SHA256)
    untracked_manifest_sha256: str = Field(pattern=_SHA256)
    worktree_diff_sha256: str = Field(pattern=_SHA256)
    source_tree_sha256: str = Field(pattern=_SHA256)
    dirty: bool
    transport_eligible: bool
    binding_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _digest_is_bound(self) -> "RepositorySourceBindingV1":
        if self.branch != self.required_remote_branch:
            raise ValueError("stress campaign is bound to the wrong branch")
        if self.observed_remote_url != self.required_remote_url:
            raise ValueError("stress campaign is bound to the wrong remote URL")
        matches = (
            self.remote_tracking_sha is not None
            and self.remote_tracking_sha == self.head_sha
        )
        if self.head_matches_remote_tracking != matches:
            raise ValueError("remote-tracking observation is inconsistent")
        expected_eligibility = not self.dirty and matches
        if self.transport_eligible != expected_eligibility:
            raise ValueError("transport eligibility is inconsistent")
        if self.binding_sha256 != repository_source_binding_sha256(self):
            raise ValueError("repository source-binding digest mismatch")
        return self


class InventoryEvidenceBindingV1(_Contract):
    inventory_id: str = Field(pattern=_IDENTIFIER)
    inventory_version: str = Field(min_length=1, max_length=80)
    inventory_sha256: str = Field(pattern=_SHA256)
    artifact_locator: str = Field(min_length=1, max_length=512)
    artifact_sha256: str = Field(pattern=_SHA256)
    entry_count: int = Field(ge=1)


class RegistryEvidenceBindingV1(_Contract):
    """Populated V2 inventory evidence; V2 may never fall back to V1."""

    schema_version: Literal[REGISTRY_BINDING_SCHEMA_VERSION] = (
        REGISTRY_BINDING_SCHEMA_VERSION
    )
    v1_registry_sha256: str = Field(pattern=_SHA256)
    v2_registry_sha256: str = Field(pattern=_SHA256)
    v2_population_state: Literal["populated"] = "populated"
    inventories: tuple[InventoryEvidenceBindingV1, ...] = Field(
        min_length=1
    )
    v2_fallback_to_v1_allowed: Literal[False] = False
    binding_sha256: str = Field(pattern=_SHA256)

    @field_validator("inventories")
    @classmethod
    def _inventories_are_canonical(
        cls,
        value: tuple[InventoryEvidenceBindingV1, ...],
    ) -> tuple[InventoryEvidenceBindingV1, ...]:
        keys = tuple(
            (item.inventory_id, item.inventory_version) for item in value
        )
        if len(keys) != len(set(keys)):
            raise ValueError("inventory evidence bindings must be unique")
        if keys != tuple(sorted(keys)):
            raise ValueError("inventory evidence bindings must be sorted")
        semantic = tuple(item.inventory_sha256 for item in value)
        artifacts = tuple(item.artifact_sha256 for item in value)
        if len(semantic) != len(set(semantic)):
            raise ValueError("inventory semantic digests must be unique")
        if len(artifacts) != len(set(artifacts)):
            raise ValueError("inventory artifact digests must be unique")
        return value

    @model_validator(mode="after")
    def _digest_is_bound(self) -> "RegistryEvidenceBindingV1":
        if self.binding_sha256 != registry_evidence_binding_sha256(self):
            raise ValueError("registry evidence-binding digest mismatch")
        return self


class StressLookupExpectationV1(_Contract):
    lookup_id: str = Field(pattern=_IDENTIFIER)
    program: Literal["gaussian", "orca", "xtb"]
    setting_path: str = Field(pattern=_SETTING_PATH)
    requested_value: str = Field(min_length=1, max_length=300)
    job_kind: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,79}$")
    expected_v2_status: Literal[
        "exact_registered",
        "blocked_validation_coverage",
        "candidate_only",
        "unknown_unverified",
        "incompatible",
        "not_applicable",
    ]
    expected_canonical_value: str | None = Field(
        default=None,
        max_length=160,
    )
    allow_fuzzy_candidates: bool = True


class ElementFindingV1(_Contract):
    symbol: str = Field(pattern=r"^[A-Z][a-z]?$", max_length=2)
    covered: bool
    orbital_present: bool
    ecp_present: bool
    ecp_electrons: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _ecp_is_coherent(self) -> "ElementFindingV1":
        if self.ecp_present != (self.ecp_electrons is not None):
            raise ValueError("ECP presence and electron count disagree")
        if not self.covered and (self.orbital_present or self.ecp_present):
            raise ValueError("an uncovered element cannot contain basis data")
        return self


class BasisElementExpectationV1(_Contract):
    basis: str = Field(min_length=1, max_length=160)
    program: Literal["gaussian", "orca"]
    elements: tuple[str, ...] = Field(min_length=1)
    expected_verdict: Literal["ok", "reject"]
    expected_status: str = Field(pattern=_IDENTIFIER)
    expected_findings: tuple[ElementFindingV1, ...] = Field(min_length=1)
    expected_rule_ids: tuple[str, ...] = ()

    @field_validator("elements", "expected_rule_ids")
    @classmethod
    def _ordered_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("basis element expectation values must be unique")
        return value


class StressProjectSettingsV1(_Contract):
    functional: str | None = Field(default=None, max_length=300)
    basis: str | None = Field(default=None, max_length=300)
    dispersion: str | None = Field(default=None, max_length=160)
    integration_grid: str | None = Field(default=None, max_length=160)
    heavy_elements: tuple[str, ...] = ()
    heavy_elements_basis: str | None = Field(default=None, max_length=300)
    light_elements_basis: str | None = Field(default=None, max_length=300)
    solvent_model: str | None = Field(default=None, max_length=160)
    solvent_id: str | None = Field(default=None, max_length=160)
    gfn_version: str | None = Field(default=None, max_length=160)
    optimization_level: str | None = Field(default=None, max_length=160)
    freq: bool | None = None
    solv_freq: bool | None = None
    ecp_intent: Literal["not_applicable", "required"] | None = None
    ecp_elements: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _ecp_intent_is_typed(self) -> "StressProjectSettingsV1":
        if self.ecp_elements != tuple(sorted(set(self.ecp_elements))):
            raise ValueError("ECP elements must be unique and sorted")
        if any(re.fullmatch(r"[A-Z][a-z]?", item) is None for item in self.ecp_elements):
            raise ValueError("ECP element symbol is invalid")
        if self.ecp_intent == "required" and not self.ecp_elements:
            raise ValueError("required ECP intent needs explicit elements")
        if self.ecp_intent != "required" and self.ecp_elements:
            raise ValueError("ECP elements require a required ECP intent")
        return self


class RegistryStressCaseV1(_Contract):
    schema_version: Literal[STRESS_CASE_SCHEMA_VERSION] = (
        STRESS_CASE_SCHEMA_VERSION
    )
    case_id: str = Field(pattern=_IDENTIFIER)
    hypothesis_family_id: str = Field(pattern=_IDENTIFIER)
    program: Literal["gaussian", "orca", "xtb"]
    engine_version: str = Field(min_length=1, max_length=80)
    task_kind: Literal["freq", "hess", "opt", "sp"]
    project_accessor_job_kind: Literal["hess", "opt", "sp"]
    request_text: str = Field(min_length=1, max_length=4000)
    lookup_expectations: tuple[StressLookupExpectationV1, ...] = ()
    basis_element_expectation: BasisElementExpectationV1 | None = None
    expected_readiness: RegistryStressReadiness
    expected_settings: StressProjectSettingsV1
    expected_blocking_rule_ids: tuple[str, ...] = ()
    rule_discharge_mode: Literal["none", "orca_native_basis_elements"] = "none"
    request_bound_validation_eligible: bool = False
    expected_render_status: Literal[
        "project_candidate_valid",
        "blocked_invalid_specification",
        "blocked_unsupported_setting",
        "not_evaluated",
    ] = "not_evaluated"
    knowledge_advisory_eligible: bool = False
    deterministic_oracle_ids: tuple[str, ...] = Field(min_length=1)
    case_sha256: str = Field(pattern=_SHA256)

    @field_validator(
        "expected_blocking_rule_ids",
        "deterministic_oracle_ids",
    )
    @classmethod
    def _rule_ids_are_canonical(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("case rule IDs must be unique and sorted")
        return value

    @model_validator(mode="after")
    def _case_is_bound(self) -> "RegistryStressCaseV1":
        lookup_ids = tuple(item.lookup_id for item in self.lookup_expectations)
        if len(lookup_ids) != len(set(lookup_ids)):
            raise ValueError("case lookup IDs must be unique")
        if self.rule_discharge_mode == "orca_native_basis_elements":
            expectation = self.basis_element_expectation
            if (
                self.program != "orca"
                or expectation is None
                or expectation.expected_verdict != "ok"
            ):
                raise ValueError("ORCA basis discharge needs passing elements")
            if not self.request_bound_validation_eligible:
                raise ValueError("rule discharge requires a validated arm")
        if self.case_sha256 != registry_stress_case_sha256(self):
            raise ValueError("registry stress-case digest mismatch")
        return self


class RegistryStressProposalV1(_Contract):
    case_id: str = Field(pattern=_IDENTIFIER)
    program: Literal["gaussian", "orca", "xtb"]
    project_name: str = Field(pattern=_IDENTIFIER)
    readiness: RegistryStressReadiness
    settings: StressProjectSettingsV1
    blocking_rule_ids: tuple[str, ...] = ()
    element_findings: tuple[ElementFindingV1, ...] = ()
    analysis_summary: str = Field(min_length=1, max_length=3000)
    native_input_authored: Literal[False] = False
    command_authored: Literal[False] = False
    project_written: Literal[False] = False
    execution_requested: Literal[False] = False

    @field_validator("blocking_rule_ids")
    @classmethod
    def _blocking_rules_are_canonical(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("proposal blocking rules must be unique and sorted")
        return value


class RegistryStressCasePreflightV1(_Contract):
    schema_version: Literal[STRESS_PREFLIGHT_SCHEMA_VERSION] = (
        STRESS_PREFLIGHT_SCHEMA_VERSION
    )
    case_id: str = Field(pattern=_IDENTIFIER)
    case_sha256: str = Field(pattern=_SHA256)
    raw_v2_resolutions: tuple[dict[str, Any], ...] = ()
    basis_element_receipt: dict[str, Any] | None = None
    project_render_observation: dict[str, Any]
    receipt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _preflight_is_bound(self) -> "RegistryStressCasePreflightV1":
        if self.receipt_sha256 != registry_stress_preflight_sha256(self):
            raise ValueError("registry stress preflight digest mismatch")
        return self


class RegistryStressSafetyPlaneV1(_Contract):
    runtime_v2_active: Literal[True] = True
    read_only_permission: Literal[True] = True
    deterministic_oracles_active: Literal[True] = True
    v2_fallback_to_v1_allowed: Literal[False] = False
    project_writes_allowed: Literal[False] = False
    native_input_authoring_allowed: Literal[False] = False
    chemistry_engine_execution_allowed: Literal[False] = False
    hpc_execution_allowed: Literal[False] = False
    secret_persistence_allowed: Literal[False] = False


class RegistryStressRunSpecV1(_Contract):
    schema_version: Literal[STRESS_RUN_SCHEMA_VERSION] = STRESS_RUN_SCHEMA_VERSION
    run_id: str = Field(pattern=_IDENTIFIER)
    hypothesis_id: str = Field(pattern=_IDENTIFIER)
    case_id: str = Field(pattern=_IDENTIFIER)
    case_sha256: str = Field(pattern=_SHA256)
    arm: RegistryStressArm
    comparator_arm: RegistryStressArm | None = None
    changed_factor: Literal[
        "reference",
        "v1_registry_surface",
        "v2_registry_surface",
        "request_bound_validator",
        "knowledge_advisory",
    ]
    hypothesis: str = Field(min_length=1, max_length=1000)
    expected_outcome: str = Field(min_length=1, max_length=1000)
    novelty_rationale: str = Field(min_length=1, max_length=1000)
    deterministic_oracle_ids: tuple[str, ...] = Field(min_length=1)
    source_binding_sha256: str = Field(pattern=_SHA256)
    registry_binding_sha256: str = Field(pattern=_SHA256)
    prompt_sha256: str = Field(pattern=_SHA256)
    tool_schema_sha256: str = Field(pattern=_SHA256)
    configuration_sha256: str = Field(pattern=_SHA256)
    network_budget_sha256: str = Field(pattern=_SHA256)
    request_bound_validation_exposed: bool = False
    knowledge_advisory_exposed: bool = False
    safety_plane: RegistryStressSafetyPlaneV1 = Field(
        default_factory=RegistryStressSafetyPlaneV1
    )
    run_spec_sha256: str = Field(pattern=_SHA256)

    @field_validator("deterministic_oracle_ids")
    @classmethod
    def _oracles_are_canonical(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("run oracle IDs must be unique and sorted")
        return value

    @model_validator(mode="after")
    def _run_is_consistent(self) -> "RegistryStressRunSpecV1":
        expected_validator = self.arm is RegistryStressArm.REGISTRY_V2_VALIDATED
        if self.request_bound_validation_exposed != expected_validator:
            raise ValueError("validated-arm tool exposure is inconsistent")
        if self.arm is RegistryStressArm.REGISTRY_V2_ADVISORY:
            if not self.knowledge_advisory_exposed:
                raise ValueError("advisory arm must expose an advisory pack")
        elif self.knowledge_advisory_exposed:
            raise ValueError("knowledge exposure is limited to the advisory arm")
        if self.run_spec_sha256 != registry_stress_run_spec_sha256(self):
            raise ValueError("registry stress run-spec digest mismatch")
        return self


class RegistryStressDeterministicGradeV1(_Contract):
    oracle_passed: bool
    passed_oracle_ids: tuple[str, ...] = ()
    failed_oracle_ids: tuple[str, ...] = ()
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("passed_oracle_ids", "failed_oracle_ids")
    @classmethod
    def _grade_oracles_are_canonical(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("grade oracle IDs must be unique and sorted")
        return value

    @model_validator(mode="after")
    def _grade_is_consistent(self) -> "RegistryStressDeterministicGradeV1":
        if set(self.passed_oracle_ids).intersection(self.failed_oracle_ids):
            raise ValueError("a deterministic oracle cannot pass and fail")
        if self.oracle_passed != (not self.failed_oracle_ids):
            raise ValueError("deterministic grade verdict is inconsistent")
        return self


class RegistryStressRunOutcomeV1(_Contract):
    """Schema for a future public outcome; construction requires transport."""

    schema_version: Literal[STRESS_OUTCOME_SCHEMA_VERSION] = (
        STRESS_OUTCOME_SCHEMA_VERSION
    )
    run_id: str = Field(pattern=_IDENTIFIER)
    run_spec_sha256: str = Field(pattern=_SHA256)
    observed_model: str | None = Field(default=None, max_length=160)
    raw_public_english_response: str = Field(max_length=32_000)
    raw_public_english_response_sha256: str = Field(pattern=_SHA256)
    response_artifact_locator: str = Field(min_length=1, max_length=512)
    sanitized_response_sha256: str = Field(pattern=_SHA256)
    deterministic_grade: "RegistryStressDeterministicGradeV1"
    public_tool_trace_locator: str = Field(min_length=1, max_length=512)
    public_tool_trace_sha256: str = Field(pattern=_SHA256)
    runtime_event_log_locator: str = Field(min_length=1, max_length=512)
    runtime_event_log_sha256: str = Field(pattern=_SHA256)
    runtime_replay_verified: bool
    runtime_replay_state_sha256: str = Field(pattern=_SHA256)
    runtime_terminal_state: Literal["complete", "blocked", "failed"]
    terminal_state: Literal["complete", "blocked", "failed"]
    passed_oracle_ids: tuple[str, ...] = ()
    failed_oracle_ids: tuple[str, ...] = ()
    transport_attempts: int = Field(ge=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    wall_time_ms: int = Field(ge=0)
    engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0
    project_writes: Literal[0] = 0
    secret_material_persisted: Literal[False] = False
    private_reasoning_persisted: Literal[False] = False
    receipt_sha256: str = Field(pattern=_SHA256)

    @field_validator("passed_oracle_ids", "failed_oracle_ids")
    @classmethod
    def _outcome_oracles_are_canonical(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("outcome oracle IDs must be unique and sorted")
        return value

    @model_validator(mode="after")
    def _outcome_is_consistent(self) -> "RegistryStressRunOutcomeV1":
        if set(self.passed_oracle_ids).intersection(self.failed_oracle_ids):
            raise ValueError("an oracle cannot both pass and fail")
        if self.raw_public_english_response_sha256 != content_sha256(
            self.raw_public_english_response.encode("utf-8")
        ):
            raise ValueError("raw public response digest mismatch")
        if self.passed_oracle_ids != self.deterministic_grade.passed_oracle_ids:
            raise ValueError("outcome and deterministic grade passes disagree")
        if self.failed_oracle_ids != self.deterministic_grade.failed_oracle_ids:
            raise ValueError("outcome and deterministic grade failures disagree")
        if self.terminal_state == "complete" and (
            self.runtime_terminal_state != "complete"
            or not self.deterministic_grade.oracle_passed
        ):
            raise ValueError("a complete outcome requires green runtime and grade")
        if self.receipt_sha256 != registry_stress_outcome_sha256(self):
            raise ValueError("registry stress outcome digest mismatch")
        return self


class RegistryStressCampaignPlanV1(_Contract):
    schema_version: Literal[STRESS_CAMPAIGN_SCHEMA_VERSION] = (
        STRESS_CAMPAIGN_SCHEMA_VERSION
    )
    campaign_id: str = Field(pattern=_IDENTIFIER)
    source_binding: RepositorySourceBindingV1
    registry_binding: RegistryEvidenceBindingV1
    cases: tuple[RegistryStressCaseV1, ...] = Field(min_length=1)
    preflight_receipts: tuple[RegistryStressCasePreflightV1, ...] = Field(
        min_length=1
    )
    runs: tuple[RegistryStressRunSpecV1, ...] = Field(min_length=1)
    transport_attempt_limit: None = None
    attempt_count_is_observational: Literal[True] = True
    final_receipts_generated: Literal[False] = False
    campaign_plan_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _campaign_is_complete(self) -> "RegistryStressCampaignPlanV1":
        case_ids = tuple(case.case_id for case in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("campaign case IDs must be unique")
        hypothesis_families = tuple(
            case.hypothesis_family_id for case in self.cases
        )
        if len(hypothesis_families) != len(set(hypothesis_families)):
            raise ValueError("campaign hypothesis families must be unique")
        run_ids = tuple(run.run_id for run in self.runs)
        hypothesis_ids = tuple(run.hypothesis_id for run in self.runs)
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("campaign run IDs must be unique")
        if len(hypothesis_ids) != len(set(hypothesis_ids)):
            raise ValueError("campaign hypothesis IDs must be unique")

        cases = {case.case_id: case for case in self.cases}
        preflights = {item.case_id: item for item in self.preflight_receipts}
        if len(preflights) != len(self.preflight_receipts):
            raise ValueError("campaign preflight case IDs must be unique")
        if set(preflights) != set(cases):
            raise ValueError("campaign requires one preflight per case")
        if any(
            preflights[case_id].case_sha256 != case.case_sha256
            for case_id, case in cases.items()
        ):
            raise ValueError("campaign preflight is bound to a stale case")
        required_arms = {
            RegistryStressArm.MINIMAL,
            RegistryStressArm.REGISTRY_V1,
            RegistryStressArm.REGISTRY_V2,
        }
        for case_id, case in cases.items():
            selected = [run for run in self.runs if run.case_id == case_id]
            arms = {run.arm for run in selected}
            if not required_arms.issubset(arms):
                raise ValueError("every case requires minimal, V1, and V2 arms")
            has_advisory = RegistryStressArm.REGISTRY_V2_ADVISORY in arms
            if has_advisory != case.knowledge_advisory_eligible:
                raise ValueError("advisory-arm coverage disagrees with the case")
            has_validated = RegistryStressArm.REGISTRY_V2_VALIDATED in arms
            if has_validated != case.request_bound_validation_eligible:
                raise ValueError("validated-arm coverage disagrees with the case")
            if any(run.case_sha256 != case.case_sha256 for run in selected):
                raise ValueError("run is bound to a stale case digest")
            if any(
                run.source_binding_sha256
                != self.source_binding.binding_sha256
                for run in selected
            ):
                raise ValueError("run is bound to a stale source tree")
            if any(
                run.registry_binding_sha256
                != self.registry_binding.binding_sha256
                for run in selected
            ):
                raise ValueError("run is bound to stale registry evidence")
        if any(run.case_id not in cases for run in self.runs):
            raise ValueError("run references an unknown case")
        if self.campaign_plan_sha256 != registry_stress_campaign_sha256(self):
            raise ValueError("registry stress campaign digest mismatch")
        return self


def repository_source_binding_sha256(
    value: RepositorySourceBindingV1 | dict[str, Any],
) -> str:
    return _contract_sha256(value, "binding_sha256")


def registry_evidence_binding_sha256(
    value: RegistryEvidenceBindingV1 | dict[str, Any],
) -> str:
    return _contract_sha256(value, "binding_sha256")


def registry_stress_case_sha256(
    value: RegistryStressCaseV1 | dict[str, Any],
) -> str:
    return _contract_sha256(value, "case_sha256")


def registry_stress_preflight_sha256(
    value: RegistryStressCasePreflightV1 | dict[str, Any],
) -> str:
    return _contract_sha256(value, "receipt_sha256")


def registry_stress_run_spec_sha256(
    value: RegistryStressRunSpecV1 | dict[str, Any],
) -> str:
    return _contract_sha256(value, "run_spec_sha256")


def registry_stress_outcome_sha256(
    value: RegistryStressRunOutcomeV1 | dict[str, Any],
) -> str:
    return _contract_sha256(value, "receipt_sha256")


def registry_stress_campaign_sha256(
    value: RegistryStressCampaignPlanV1 | dict[str, Any],
) -> str:
    return _contract_sha256(value, "campaign_plan_sha256")


def content_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    return content_sha256(_canonical_json_bytes(value))


def _contract_sha256(
    value: BaseModel | dict[str, Any],
    digest_field: str,
) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude={digest_field})
    else:
        payload = {
            key: _jsonable(item)
            for key, item in value.items()
            if key != digest_field
        }
    return canonical_json_sha256(payload)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


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
    "BasisElementExpectationV1",
    "ElementFindingV1",
    "InventoryEvidenceBindingV1",
    "RegistryEvidenceBindingV1",
    "RegistryStressArm",
    "RegistryStressCampaignPlanV1",
    "RegistryStressCasePreflightV1",
    "RegistryStressCaseV1",
    "RegistryStressDeterministicGradeV1",
    "RegistryStressProposalV1",
    "RegistryStressReadiness",
    "RegistryStressRunOutcomeV1",
    "RegistryStressRunSpecV1",
    "RegistryStressSafetyPlaneV1",
    "RepositorySourceBindingV1",
    "StressLookupExpectationV1",
    "StressProjectSettingsV1",
    "canonical_json_sha256",
    "content_sha256",
    "registry_evidence_binding_sha256",
    "registry_stress_campaign_sha256",
    "registry_stress_case_sha256",
    "registry_stress_outcome_sha256",
    "registry_stress_preflight_sha256",
    "registry_stress_run_spec_sha256",
    "repository_source_binding_sha256",
]
