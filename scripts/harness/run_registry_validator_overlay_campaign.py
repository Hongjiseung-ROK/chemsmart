#!/usr/bin/env python3
"""Run the additive V5 request-bound validator-overlay campaign.

V5 makes no duplicate baseline model calls.  Each live DeepSeek run is paired
with one exact failed ``registry_v2`` outcome from the archived V4 campaign and
changes one factor only: it exposes content-addressed, request-bound basis and
typed-project readiness evidence.  Preparation is network-free.  The live
surface remains read-only and cannot write a project, author native input or a
command, or invoke a chemistry engine or scheduler.
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from chemsmart.agent.adaptive_api_campaign import (
    AdaptiveProviderPurpose,
    build_adaptive_hypothesis_v1,
    build_adaptive_network_budget_v1,
)
from chemsmart.agent.api_access import CredentialAccessController
from chemsmart.agent.core import AgentSession
from chemsmart.agent.harness.basis_sets.request_evidence import (
    BasisEvidenceState,
    RequestBoundBasisEvidenceReceiptV1,
    RequestBoundBasisEvidenceRefV1,
    RequestBoundBasisEvidenceRequestV1,
    build_request_bound_basis_evidence_request_v1,
    inspect_request_bound_basis_evidence_v1,
)
from chemsmart.agent.loop import ToolLoopBudgets
from chemsmart.agent.permissions import PermissionPolicy, RuntimePermissionMode
from chemsmart.agent.project_readiness import (
    ProjectMethodIntentV1,
    ProjectReadinessEvidenceRefV1,
    ProjectReadinessReceiptV1,
    TypedProjectSupportStatus,
    assess_typed_project_readiness,
)
from chemsmart.agent.registry import ToolRegistry, build_tool_spec
from chemsmart.agent.runtime.adaptive_provider import (
    AdaptiveDeepSeekProviderConfig,
    AdaptiveLeaseBoundDeepSeekProvider,
    build_adaptive_request_binding_v1,
)
from chemsmart.agent.runtime.public_event_projection import (
    PublicEventProjectionReceiptV1,
    project_runtime_events_for_public,
)
from chemsmart.agent.settings_registry_stress_receipts import (
    RegistryEvidenceBindingV1,
    RegistryStressCasePreflightV1,
    RegistryStressCaseV1,
    RegistryStressProposalV1,
    RegistryStressReadiness,
    RepositorySourceBindingV1,
    canonical_json_sha256,
    content_sha256,
)
from scripts.harness import run_registry_v2_stress_campaign as v4


CAMPAIGN_ID = "registry-validator-overlay-development-v5"
RUN_REVISION = "v5"
PROMPT_VERSION = "registry-validator-overlay-prompt.v1"
MODEL = "deepseek-v4-flash"
MAX_OUTPUT_TOKENS = 8_192
ARCHIVED_V4_RELATIVE = Path(
    "docs/evaluation/receipts/registry-v2-stress-live-v4-2026-08-02"
)
SELECTED_CASE_IDS = (
    "gaussian-b3lyp-explicit-d4-unsupported",
    "gaussian-def2-tzvppd-missing-ce",
    "gaussian-raw-route-functional-invalid",
    "orca-def2-ecp-orbital-missing",
    "orca-def2-tzvp-fe-no-ecp",
    "orca-def2-tzvp-pd-28e-ecp",
)
CHANGED_FACTOR = "request_bound_basis_and_typed_project_evidence_overlay"

_SHA256 = r"^[0-9a-f]{64}$"
_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_SAFE_LOCATOR = re.compile(r"^[A-Za-z0-9._/-]+$")
_POSIX_ABSOLUTE_FRAGMENT = re.compile(
    r"(?<![A-Za-z0-9_+.:/])/(?:[^\s\"'<>]+)"
)
_WINDOWS_ABSOLUTE_FRAGMENT = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|\\\\[^\\\s]+[\\/])"
)


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class ArchivedRegistryV2ComparatorV1(_Contract):
    schema_version: Literal[
        "chemsmart.archived-registry-v2-comparator.v1"
    ] = "chemsmart.archived-registry-v2-comparator.v1"
    campaign_id: Literal["registry-v2-stress-development-v4"]
    case_id: str = Field(pattern=_IDENTIFIER)
    run_id: str = Field(pattern=_IDENTIFIER)
    arm: Literal["registry_v2"] = "registry_v2"
    outcome_artifact_locator: str = Field(min_length=1, max_length=512)
    outcome_artifact_sha256: str = Field(pattern=_SHA256)
    outcome_receipt_sha256: str = Field(pattern=_SHA256)
    run_spec_sha256: str = Field(pattern=_SHA256)
    campaign_plan_artifact_sha256: str = Field(pattern=_SHA256)
    campaign_plan_sha256: str = Field(pattern=_SHA256)
    terminal_state: Literal["failed", "blocked"]
    oracle_passed: bool
    failed_oracle_ids: tuple[str, ...] = ()
    comparator_sha256: str = Field(pattern=_SHA256)

    @field_validator("failed_oracle_ids")
    @classmethod
    def _canonical_oracles(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("failed comparator oracles must be unique and sorted")
        return value

    @model_validator(mode="after")
    def _content_addressed(self) -> "ArchivedRegistryV2ComparatorV1":
        locator = Path(self.outcome_artifact_locator)
        if (
            locator.is_absolute()
            or ".." in locator.parts
            or _SAFE_LOCATOR.fullmatch(self.outcome_artifact_locator) is None
        ):
            raise ValueError("archived comparator locator is unsafe")
        if self.comparator_sha256 != _contract_sha256(self, "comparator_sha256"):
            raise ValueError("archived comparator digest mismatch")
        return self


class ValidatorEvidenceBundleV1(_Contract):
    schema_version: Literal[
        "chemsmart.registry-validator-evidence-bundle.v1"
    ] = "chemsmart.registry-validator-evidence-bundle.v1"
    case_id: str = Field(pattern=_IDENTIFIER)
    basis_request: RequestBoundBasisEvidenceRequestV1 | None = None
    basis_receipt: RequestBoundBasisEvidenceReceiptV1 | None = None
    basis_evidence_ref: RequestBoundBasisEvidenceRefV1 | None = None
    project_readiness_receipt: ProjectReadinessReceiptV1
    project_readiness_evidence_ref: ProjectReadinessEvidenceRefV1
    evidence_ref_sha256s: tuple[str, ...] = Field(min_length=1, max_length=2)
    evidence_bundle_sha256: str = Field(pattern=_SHA256)

    @field_validator("evidence_ref_sha256s")
    @classmethod
    def _canonical_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("validator evidence refs must be unique and sorted")
        return value

    @model_validator(mode="after")
    def _evidence_is_bound(self) -> "ValidatorEvidenceBundleV1":
        basis_values = (
            self.basis_request,
            self.basis_receipt,
            self.basis_evidence_ref,
        )
        if any(item is None for item in basis_values) and any(
            item is not None for item in basis_values
        ):
            raise ValueError("optional basis evidence must be wholly present or absent")
        if self.basis_receipt is not None:
            if self.basis_receipt.request != self.basis_request:
                raise ValueError("basis evidence belongs to another request")
            if self.basis_evidence_ref != self.basis_receipt.evidence_ref():
                raise ValueError("basis EvidenceRef does not bind its receipt")
        if (
            self.project_readiness_evidence_ref
            != self.project_readiness_receipt.evidence_ref()
        ):
            raise ValueError("project EvidenceRef does not bind its receipt")
        expected = tuple(
            sorted(
                {
                    self.project_readiness_evidence_ref.ref_sha256,
                    *(
                        (self.basis_evidence_ref.ref_sha256,)
                        if self.basis_evidence_ref is not None
                        else ()
                    ),
                }
            )
        )
        if self.evidence_ref_sha256s != expected:
            raise ValueError("validator evidence-ref set is incomplete")
        if self.evidence_bundle_sha256 != _contract_sha256(
            self, "evidence_bundle_sha256"
        ):
            raise ValueError("validator evidence bundle digest mismatch")
        return self


class EvidenceRefDereferenceV1(_Contract):
    ref_sha256: str = Field(pattern=_SHA256)
    kind: Literal["request_bound_basis_evidence", "typed_project_readiness"]
    request_sha256: str = Field(pattern=_SHA256)
    artifact_sha256: str = Field(pattern=_SHA256)


class EvidenceObservationReceiptV1(_Contract):
    observation_receipt_id: str = Field(pattern=_IDENTIFIER)
    kind: Literal["request_bound_basis_evidence", "typed_project_readiness"]
    ref_sha256: str = Field(pattern=_SHA256)
    artifact_sha256: str = Field(pattern=_SHA256)


class RegistryValidatorOverlayProposalV1(RegistryStressProposalV1):
    """V5-local proposal extension; V4's shared proposal stays unchanged."""

    evidence_ref_sha256s: tuple[str, ...] = Field(min_length=1, max_length=2)

    @field_validator("evidence_ref_sha256s")
    @classmethod
    def _canonical_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("proposal EvidenceRefs must be unique and sorted")
        if any(re.fullmatch(_SHA256, item) is None for item in value):
            raise ValueError("proposal EvidenceRef digest is invalid")
        return value


class RegistryValidatorOverlaySubmissionV1(_Contract):
    """V5-local strict submission; the shared proposal remains unchanged."""

    proposal: RegistryValidatorOverlayProposalV1
    dereferenced_evidence: tuple[EvidenceRefDereferenceV1, ...] = Field(
        min_length=1,
        max_length=2,
    )
    observed_evidence: tuple[EvidenceObservationReceiptV1, ...] = Field(
        min_length=1,
        max_length=2,
    )

    @model_validator(mode="after")
    def _all_refs_are_dereferenced(self) -> "RegistryValidatorOverlaySubmissionV1":
        observed = tuple(item.ref_sha256 for item in self.dereferenced_evidence)
        if observed != tuple(sorted(set(observed))):
            raise ValueError("dereferenced EvidenceRefs must be unique and sorted")
        if observed != self.proposal.evidence_ref_sha256s:
            raise ValueError("proposal EvidenceRefs were not exactly dereferenced")
        observed_receipt_refs = tuple(
            sorted(item.ref_sha256 for item in self.observed_evidence)
        )
        if observed_receipt_refs != self.proposal.evidence_ref_sha256s:
            raise ValueError("proposal EvidenceRefs were not causally observed")
        receipt_ids = tuple(
            item.observation_receipt_id for item in self.observed_evidence
        )
        if receipt_ids != tuple(sorted(set(receipt_ids))):
            raise ValueError("observation receipt IDs must be unique and sorted")
        return self


class RegistryValidatorOverlayCaseV1(_Contract):
    schema_version: Literal[
        "chemsmart.registry-validator-overlay-case.v1"
    ] = "chemsmart.registry-validator-overlay-case.v1"
    case_id: str = Field(pattern=_IDENTIFIER)
    case_sha256: str = Field(pattern=_SHA256)
    preflight_receipt_sha256: str = Field(pattern=_SHA256)
    expected_readiness: RegistryStressReadiness
    evidence_blocking_rule_ids: tuple[str, ...] = ()
    expected_settings_sha256: str = Field(pattern=_SHA256)
    expected_element_findings_sha256: str = Field(pattern=_SHA256)
    changed_factor: Literal[
        "request_bound_basis_and_typed_project_evidence_overlay"
    ] = CHANGED_FACTOR
    novelty_rationale: str = Field(min_length=1, max_length=1000)
    comparator: ArchivedRegistryV2ComparatorV1
    evidence: ValidatorEvidenceBundleV1
    case_binding_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _case_is_bound(self) -> "RegistryValidatorOverlayCaseV1":
        if self.case_id not in SELECTED_CASE_IDS:
            raise ValueError("case was not preregistered for V5")
        if self.comparator.case_id != self.case_id:
            raise ValueError("comparator belongs to another case")
        if self.evidence.case_id != self.case_id:
            raise ValueError("validator evidence belongs to another case")
        if self.evidence_blocking_rule_ids != tuple(
            sorted(set(self.evidence_blocking_rule_ids))
        ):
            raise ValueError("evidence blockers must be unique and sorted")
        candidate = (
            self.expected_readiness
            is RegistryStressReadiness.PROJECT_CANDIDATE
        )
        if candidate == bool(self.evidence_blocking_rule_ids):
            raise ValueError("readiness conflicts with evidence-derived blockers")
        if self.case_binding_sha256 != _contract_sha256(
            self, "case_binding_sha256"
        ):
            raise ValueError("overlay case digest mismatch")
        return self


class RegistryValidatorOverlayRunSpecV1(_Contract):
    schema_version: Literal[
        "chemsmart.registry-validator-overlay-run.v1"
    ] = "chemsmart.registry-validator-overlay-run.v1"
    run_id: str = Field(pattern=_IDENTIFIER)
    hypothesis_id: str = Field(pattern=_IDENTIFIER)
    case_id: str = Field(pattern=_IDENTIFIER)
    case_sha256: str = Field(pattern=_SHA256)
    case_binding_sha256: str = Field(pattern=_SHA256)
    comparator_sha256: str = Field(pattern=_SHA256)
    evidence_bundle_sha256: str = Field(pattern=_SHA256)
    evidence_ref_sha256s: tuple[str, ...] = Field(min_length=1, max_length=2)
    source_binding_sha256: str = Field(pattern=_SHA256)
    registry_binding_sha256: str = Field(pattern=_SHA256)
    prompt_sha256: str = Field(pattern=_SHA256)
    tool_schema_sha256: str = Field(pattern=_SHA256)
    configuration_sha256: str = Field(pattern=_SHA256)
    network_budget_sha256: str = Field(pattern=_SHA256)
    changed_factor: Literal[
        "request_bound_basis_and_typed_project_evidence_overlay"
    ] = CHANGED_FACTOR
    comparator_source: Literal["archived_v4_registry_v2"] = (
        "archived_v4_registry_v2"
    )
    duplicate_baseline_api_calls: Literal[0] = 0
    model: Literal["deepseek-v4-flash"] = MODEL
    reasoning_mode: Literal["thinking_enabled_high"] = "thinking_enabled_high"
    runtime: Literal["agent_session_runtime_v2_active"] = (
        "agent_session_runtime_v2_active"
    )
    prompt_version: Literal["registry-validator-overlay-prompt.v1"] = (
        PROMPT_VERSION
    )
    expected_outcome: str = Field(min_length=1, max_length=1000)
    run_spec_sha256: str = Field(pattern=_SHA256)

    @field_validator("evidence_ref_sha256s")
    @classmethod
    def _canonical_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("run evidence refs must be unique and sorted")
        return value

    @model_validator(mode="after")
    def _run_is_bound(self) -> "RegistryValidatorOverlayRunSpecV1":
        if self.run_spec_sha256 != _contract_sha256(self, "run_spec_sha256"):
            raise ValueError("overlay run digest mismatch")
        return self


class RegistryValidatorOverlayCampaignPlanV1(_Contract):
    schema_version: Literal[
        "chemsmart.registry-validator-overlay-campaign.v1"
    ] = "chemsmart.registry-validator-overlay-campaign.v1"
    campaign_id: Literal["registry-validator-overlay-development-v5"] = (
        CAMPAIGN_ID
    )
    source_binding: RepositorySourceBindingV1
    registry_binding: RegistryEvidenceBindingV1
    archived_v4_campaign_plan_artifact_sha256: str = Field(pattern=_SHA256)
    archived_v4_campaign_plan_sha256: str = Field(pattern=_SHA256)
    network_budget_sha256: str = Field(pattern=_SHA256)
    cases: tuple[RegistryValidatorOverlayCaseV1, ...] = Field(min_length=1)
    runs: tuple[RegistryValidatorOverlayRunSpecV1, ...] = Field(min_length=1)
    live_arm_count: int = Field(ge=1)
    duplicate_baseline_api_calls: Literal[0] = 0
    chemistry_engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0
    project_writes: Literal[0] = 0
    native_inputs_authored: Literal[0] = 0
    campaign_plan_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _plan_is_bound(self) -> "RegistryValidatorOverlayCampaignPlanV1":
        case_ids = tuple(item.case_id for item in self.cases)
        run_ids = tuple(item.run_id for item in self.runs)
        if case_ids != tuple(sorted(set(case_ids))):
            raise ValueError("overlay cases must be unique and sorted")
        if len(run_ids) != len(set(run_ids)) or len(self.runs) != len(self.cases):
            raise ValueError("V5 requires one unique live run per case")
        if self.live_arm_count != len(self.runs):
            raise ValueError("live arm count does not match runs")
        by_case = {item.case_id: item for item in self.cases}
        for run in self.runs:
            case = by_case.get(run.case_id)
            if case is None:
                raise ValueError("run has no overlay case")
            if (
                run.case_sha256 != case.case_sha256
                or run.case_binding_sha256 != case.case_binding_sha256
                or run.comparator_sha256 != case.comparator.comparator_sha256
                or run.evidence_bundle_sha256
                != case.evidence.evidence_bundle_sha256
                or run.evidence_ref_sha256s
                != case.evidence.evidence_ref_sha256s
                or run.source_binding_sha256
                != self.source_binding.binding_sha256
                or run.registry_binding_sha256
                != self.registry_binding.binding_sha256
                or run.network_budget_sha256 != self.network_budget_sha256
            ):
                raise ValueError("overlay run is not bound to its plan inputs")
        if self.campaign_plan_sha256 != _contract_sha256(
            self, "campaign_plan_sha256"
        ):
            raise ValueError("overlay campaign-plan digest mismatch")
        return self


class RegistryValidatorOverlayGradeV1(_Contract):
    oracle_passed: bool
    passed_oracle_ids: tuple[str, ...]
    failed_oracle_ids: tuple[str, ...]
    successful_submit_count: int = Field(ge=0)
    rejected_submit_count: int = Field(ge=0)
    details: dict[str, Any]
    grade_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _grade_is_bound(self) -> "RegistryValidatorOverlayGradeV1":
        if self.passed_oracle_ids != tuple(sorted(set(self.passed_oracle_ids))):
            raise ValueError("passed oracle IDs must be canonical")
        if self.failed_oracle_ids != tuple(sorted(set(self.failed_oracle_ids))):
            raise ValueError("failed oracle IDs must be canonical")
        if self.oracle_passed != (not self.failed_oracle_ids):
            raise ValueError("grade verdict conflicts with failed oracles")
        if self.grade_sha256 != _contract_sha256(self, "grade_sha256"):
            raise ValueError("overlay grade digest mismatch")
        return self


class RegistryValidatorOverlayOutcomeV1(_Contract):
    schema_version: Literal[
        "chemsmart.registry-validator-overlay-outcome.v1"
    ] = "chemsmart.registry-validator-overlay-outcome.v1"
    run_id: str = Field(pattern=_IDENTIFIER)
    run_spec_sha256: str = Field(pattern=_SHA256)
    comparator_sha256: str = Field(pattern=_SHA256)
    comparator_outcome_receipt_sha256: str = Field(pattern=_SHA256)
    evidence_ref_sha256s: tuple[str, ...] = Field(min_length=1, max_length=2)
    observed_model: str | None = Field(default=None, max_length=160)
    raw_public_english_response: str
    raw_public_english_response_sha256: str = Field(pattern=_SHA256)
    response_artifact_locator: str
    response_artifact_sha256: str = Field(pattern=_SHA256)
    tool_trace_artifact_locator: str
    tool_trace_artifact_sha256: str = Field(pattern=_SHA256)
    runtime_event_log_locator: str
    runtime_event_log_sha256: str = Field(pattern=_SHA256)
    private_runtime_event_log_sha256: str = Field(pattern=_SHA256)
    runtime_event_projection_receipt_locator: str
    runtime_event_projection_receipt_artifact_sha256: str = Field(
        pattern=_SHA256
    )
    runtime_event_projection_receipt: PublicEventProjectionReceiptV1
    runtime_replay_verified: Literal[True] = True
    runtime_replay_state_sha256: str = Field(pattern=_SHA256)
    runtime_terminal_state: Literal["complete", "blocked", "failed"]
    terminal_state: Literal["complete", "blocked", "failed"]
    deterministic_grade: RegistryValidatorOverlayGradeV1
    transport_attempts: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    wall_time_ms: int = Field(ge=0)
    successful_submit_count: int = Field(ge=0)
    rejected_submit_count: int = Field(ge=0)
    duplicate_baseline_api_calls: Literal[0] = 0
    engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0
    project_writes: Literal[0] = 0
    native_inputs_authored: Literal[0] = 0
    private_reasoning_persisted: Literal[False] = False
    secret_material_persisted: Literal[False] = False
    receipt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _outcome_is_bound(self) -> "RegistryValidatorOverlayOutcomeV1":
        if (
            self.successful_submit_count
            != self.deterministic_grade.successful_submit_count
        ):
            raise ValueError("outcome successful-submit count conflicts with grade")
        if self.rejected_submit_count != self.deterministic_grade.rejected_submit_count:
            raise ValueError("outcome rejected-submit count conflicts with grade")
        if self.raw_public_english_response_sha256 != content_sha256(
            self.raw_public_english_response.encode("utf-8")
        ):
            raise ValueError("public response digest mismatch")
        projection = self.runtime_event_projection_receipt
        if projection.projected_jsonl_sha256 != self.runtime_event_log_sha256:
            raise ValueError("public Runtime V2 log is not projection-bound")
        if (
            projection.private_exact_jsonl_sha256
            != self.private_runtime_event_log_sha256
        ):
            raise ValueError("private Runtime V2 digest is not projection-bound")
        if projection.projected_state_sha256 != self.runtime_replay_state_sha256:
            raise ValueError("public Runtime V2 state is not projection-bound")
        expected_terminal = (
            self.runtime_terminal_state
            if self.deterministic_grade.oracle_passed
            else "failed"
        )
        if self.terminal_state != expected_terminal:
            raise ValueError("outcome terminal state conflicts with runtime/grade")
        if self.receipt_sha256 != _contract_sha256(self, "receipt_sha256"):
            raise ValueError("overlay outcome digest mismatch")
        return self


@dataclass(frozen=True)
class _ArchivePlanBinding:
    artifact_sha256: str
    semantic_sha256: str


def _contract_sha256(value: BaseModel | Mapping[str, Any], field: str) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude={field})
    else:
        payload = {str(key): item for key, item in value.items() if key != field}
    return canonical_json_sha256(payload)


def _case(case_id: str) -> RegistryStressCaseV1:
    matches = tuple(item for item in v4.CASES if item.case_id == case_id)
    if len(matches) != 1:
        raise ValueError(f"V4 case is not unique: {case_id}")
    return matches[0]


def _archive_plan_binding(repository_root: Path) -> _ArchivePlanBinding:
    path = repository_root / ARCHIVED_V4_RELATIVE / "campaign-plan.json"
    payload = path.read_bytes()
    parsed = json.loads(payload)
    semantic = parsed.get("campaign_plan_sha256")
    if not isinstance(semantic, str) or re.fullmatch(_SHA256, semantic) is None:
        raise ValueError("archived V4 plan has no content digest")
    if parsed.get("campaign_id") != "registry-v2-stress-development-v4":
        raise ValueError("archived V4 campaign identity mismatch")
    return _ArchivePlanBinding(content_sha256(payload), semantic)


def load_archived_comparator(
    repository_root: Path,
    case_id: str,
) -> ArchivedRegistryV2ComparatorV1:
    """Bind one exact V4 Registry V2 comparator without a model call."""

    plan = _archive_plan_binding(repository_root)
    relative = (
        ARCHIVED_V4_RELATIVE
        / "outcomes"
        / f"run_{case_id}_registry_v2_v4.json"
    )
    path = repository_root / relative
    payload = path.read_bytes()
    parsed = json.loads(payload)
    run = parsed.get("run_spec") or {}
    outcome = parsed.get("outcome") or {}
    grade = parsed.get("grade") or {}
    if (
        run.get("case_id") != case_id
        or run.get("arm") != "registry_v2"
        or outcome.get("terminal_state") not in {"failed", "blocked"}
        or not isinstance(grade.get("oracle_passed"), bool)
    ):
        raise ValueError("V5 comparator must be an exact terminal V4 registry_v2 run")
    body: dict[str, Any] = {
        "schema_version": "chemsmart.archived-registry-v2-comparator.v1",
        "campaign_id": "registry-v2-stress-development-v4",
        "case_id": case_id,
        "run_id": run["run_id"],
        "arm": "registry_v2",
        "outcome_artifact_locator": relative.as_posix(),
        "outcome_artifact_sha256": content_sha256(payload),
        "outcome_receipt_sha256": outcome["receipt_sha256"],
        "run_spec_sha256": run["run_spec_sha256"],
        "campaign_plan_artifact_sha256": plan.artifact_sha256,
        "campaign_plan_sha256": plan.semantic_sha256,
        "terminal_state": outcome["terminal_state"],
        "oracle_passed": grade["oracle_passed"],
        "failed_oracle_ids": tuple(sorted(set(grade["failed_oracle_ids"]))),
        "comparator_sha256": "0" * 64,
    }
    body["comparator_sha256"] = _contract_sha256(body, "comparator_sha256")
    return ArchivedRegistryV2ComparatorV1.model_validate(body)


def _project_method(case: RegistryStressCaseV1) -> ProjectMethodIntentV1:
    raw = case.expected_settings.model_dump(mode="python")
    method = {
        key: value
        for key, value in raw.items()
        if key not in {"ecp_intent", "ecp_elements"}
    }
    if raw.get("ecp_intent") == "required":
        method["ecp_binding"] = "required_elements"
        method["required_ecp_elements"] = raw["ecp_elements"]
    return ProjectMethodIntentV1.model_validate(method)


def _resolution_receipt_sha256s(
    preflight: RegistryStressCasePreflightV1,
) -> tuple[str, ...]:
    values = []
    for resolution in preflight.raw_v2_resolutions:
        payload = resolution if isinstance(resolution, dict) else {}
        for key in ("resolution_sha256", "entry_evidence_sha256"):
            value = payload.get(key)
            if isinstance(value, str) and re.fullmatch(_SHA256, value):
                values.append(value)
    return tuple(sorted(set(values)))


def build_validator_evidence_bundle(
    case: RegistryStressCaseV1,
    preflight: RegistryStressCasePreflightV1,
) -> ValidatorEvidenceBundleV1:
    expected = case.basis_element_expectation
    request = None
    basis = None
    basis_ref = None
    if expected is not None:
        request = build_request_bound_basis_evidence_request_v1(
            request_id=f"{case.case_id}:orbital",
            program=case.program,
            basis_literal=expected.basis,
            role="orbital",
            elements=expected.elements,
        )
        basis = inspect_request_bound_basis_evidence_v1(request)
        basis_ref = basis.evidence_ref()
    project = assess_typed_project_readiness(
        case_id=case.case_id,
        program=case.program,
        job_kind=case.project_accessor_job_kind,
        method=_project_method(case),
        registry_resolution_sha256s=_resolution_receipt_sha256s(preflight),
    )
    project_ref = project.evidence_ref()
    refs = {project_ref.ref_sha256}
    if basis_ref is not None:
        refs.add(basis_ref.ref_sha256)
    body: dict[str, Any] = {
        "schema_version": "chemsmart.registry-validator-evidence-bundle.v1",
        "case_id": case.case_id,
        "basis_request": request,
        "basis_receipt": basis,
        "basis_evidence_ref": basis_ref,
        "project_readiness_receipt": project,
        "project_readiness_evidence_ref": project_ref,
        "evidence_ref_sha256s": tuple(sorted(refs)),
        "evidence_bundle_sha256": "0" * 64,
    }
    body["evidence_bundle_sha256"] = _contract_sha256(
        body, "evidence_bundle_sha256"
    )
    return ValidatorEvidenceBundleV1.model_validate(body)


def _expected_overlay_readiness(
    case: RegistryStressCaseV1,
    evidence: ValidatorEvidenceBundleV1,
) -> RegistryStressReadiness:
    basis_state = (
        evidence.basis_receipt.state
        if evidence.basis_receipt is not None
        else None
    )
    project_state = evidence.project_readiness_receipt.typed_project_support.status
    if (
        basis_state in {None, BasisEvidenceState.VERIFIED}
        and project_state is TypedProjectSupportStatus.TYPED_PROJECT_SUPPORTED
    ):
        return RegistryStressReadiness.PROJECT_CANDIDATE
    return case.expected_readiness


def _evidence_blocking_rule_ids(
    evidence: ValidatorEvidenceBundleV1,
) -> tuple[str, ...]:
    rules = set(
        evidence.project_readiness_receipt.typed_project_support
        .blocking_rule_ids
    )
    basis = evidence.basis_receipt
    if basis is not None and basis.state in {
        BasisEvidenceState.CONFLICT,
        BasisEvidenceState.UNKNOWN,
    }:
        rules.update(basis.reason_rule_ids)
    return tuple(sorted(rules))


def build_overlay_case(
    repository_root: Path,
    case: RegistryStressCaseV1,
    bundle: v4.LoadedRegistryV2Bundle,
) -> RegistryValidatorOverlayCaseV1:
    preflight = v4.build_case_preflight(case, bundle)
    evidence = build_validator_evidence_bundle(case, preflight)
    comparator = load_archived_comparator(repository_root, case.case_id)
    expected_readiness = _expected_overlay_readiness(case, evidence)
    body: dict[str, Any] = {
        "schema_version": "chemsmart.registry-validator-overlay-case.v1",
        "case_id": case.case_id,
        "case_sha256": case.case_sha256,
        "preflight_receipt_sha256": preflight.receipt_sha256,
        "expected_readiness": expected_readiness,
        "evidence_blocking_rule_ids": _evidence_blocking_rule_ids(evidence),
        "expected_settings_sha256": canonical_json_sha256(
            case.expected_settings.model_dump(mode="json")
        ),
        "expected_element_findings_sha256": canonical_json_sha256(
            [
                item.model_dump(mode="json")
                for item in (
                    case.basis_element_expectation.expected_findings
                    if case.basis_element_expectation is not None
                    else ()
                )
            ]
        ),
        "changed_factor": CHANGED_FACTOR,
        "novelty_rationale": (
            "The archived failed V4 registry_v2 run is reused unchanged; V5 "
            "adds only exact request-bound basis evidence and typed-project "
            "readiness evidence, both content-addressed before credential access."
        ),
        "comparator": comparator,
        "evidence": evidence,
        "case_binding_sha256": "0" * 64,
    }
    body["case_binding_sha256"] = _contract_sha256(
        body, "case_binding_sha256"
    )
    return RegistryValidatorOverlayCaseV1.model_validate(body)


def _no_argument_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {},
    }


def _dereferenced_evidence(
    evidence: ValidatorEvidenceBundleV1,
) -> tuple[EvidenceRefDereferenceV1, ...]:
    values = [
        EvidenceRefDereferenceV1(
            ref_sha256=evidence.project_readiness_evidence_ref.ref_sha256,
            kind="typed_project_readiness",
            request_sha256=evidence.project_readiness_evidence_ref.request_sha256,
            artifact_sha256=evidence.project_readiness_evidence_ref.artifact_sha256,
        )
    ]
    if evidence.basis_evidence_ref is not None:
        values.append(
            EvidenceRefDereferenceV1(
                ref_sha256=evidence.basis_evidence_ref.ref_sha256,
                kind="request_bound_basis_evidence",
                request_sha256=evidence.basis_evidence_ref.request_sha256,
                artifact_sha256=evidence.basis_evidence_ref.artifact_sha256,
            )
        )
    return tuple(sorted(values, key=lambda item: item.ref_sha256))


def build_overlay_registry(
    case: RegistryStressCaseV1,
    overlay: RegistryValidatorOverlayCaseV1,
    bundle: v4.LoadedRegistryV2Bundle,
) -> ToolRegistry:
    """Expose only case-bound read tools and strict typed submission."""

    observation_receipts: dict[str, EvidenceObservationReceiptV1] = {}
    issued_observation_receipt_ids: set[str] = set()

    def observation_receipt(
        *,
        kind: Literal[
            "request_bound_basis_evidence",
            "typed_project_readiness",
        ],
        ref_sha256: str,
        artifact_sha256: str,
    ) -> EvidenceObservationReceiptV1:
        receipt = EvidenceObservationReceiptV1(
            observation_receipt_id=(
                f"observation:{kind}:{secrets.token_hex(16)}"
            ),
            kind=kind,
            ref_sha256=ref_sha256,
            artifact_sha256=artifact_sha256,
        )
        observation_receipts[receipt.observation_receipt_id] = receipt
        return receipt

    basis_observation = (
        observation_receipt(
            kind="request_bound_basis_evidence",
            ref_sha256=overlay.evidence.basis_evidence_ref.ref_sha256,
            artifact_sha256=(
                overlay.evidence.basis_evidence_ref.artifact_sha256
            ),
        )
        if overlay.evidence.basis_evidence_ref is not None
        else None
    )
    project_observation = observation_receipt(
        kind="typed_project_readiness",
        ref_sha256=overlay.evidence.project_readiness_evidence_ref.ref_sha256,
        artifact_sha256=(
            overlay.evidence.project_readiness_evidence_ref.artifact_sha256
        ),
    )
    required_observation_receipt_ids = tuple(sorted(observation_receipts))

    def inspect_case_basis_evidence() -> dict[str, Any]:
        if (
            overlay.evidence.basis_request is None
            or overlay.evidence.basis_receipt is None
            or overlay.evidence.basis_evidence_ref is None
        ):
            raise RuntimeError("this project-only case has no basis evidence")
        assert basis_observation is not None
        issued_observation_receipt_ids.add(
            basis_observation.observation_receipt_id
        )
        return {
            "request": overlay.evidence.basis_request.model_dump(mode="json"),
            "receipt": overlay.evidence.basis_receipt.model_dump(mode="json"),
            "evidence_ref": overlay.evidence.basis_evidence_ref.model_dump(
                mode="json"
            ),
            "observation_receipt": basis_observation.model_dump(mode="json"),
        }

    def inspect_case_project_readiness() -> dict[str, Any]:
        issued_observation_receipt_ids.add(
            project_observation.observation_receipt_id
        )
        return {
            "receipt": overlay.evidence.project_readiness_receipt.model_dump(
                mode="json"
            ),
            "evidence_ref": (
                overlay.evidence.project_readiness_evidence_ref.model_dump(
                    mode="json"
                )
            ),
            "observation_receipt": project_observation.model_dump(mode="json"),
        }

    required_refs = overlay.evidence.evidence_ref_sha256s

    def submit_registry_validator_overlay_plan(
        proposal: dict[str, Any],
        observation_receipt_ids: list[str],
    ) -> dict[str, Any]:
        typed = RegistryValidatorOverlayProposalV1.model_validate(proposal)
        if typed.evidence_ref_sha256s != required_refs:
            raise ValueError(
                "proposal must cite the exact case-bound validator EvidenceRefs"
            )
        if typed.blocking_rule_ids != overlay.evidence_blocking_rule_ids:
            raise ValueError(
                "proposal blockers must exactly match the case-bound evidence"
            )
        observed_ids = tuple(sorted(set(observation_receipt_ids)))
        if (
            observed_ids != required_observation_receipt_ids
            or not set(observed_ids).issubset(issued_observation_receipt_ids)
        ):
            raise ValueError(
                "submission requires every observation receipt returned by "
                "the case-bound evidence tools"
            )
        submission = RegistryValidatorOverlaySubmissionV1(
            proposal=typed,
            dereferenced_evidence=_dereferenced_evidence(overlay.evidence),
            observed_evidence=tuple(
                observation_receipts[item] for item in observed_ids
            ),
        )
        return submission.model_dump(mode="json")

    proposal_schema = RegistryValidatorOverlayProposalV1.model_json_schema()
    definitions = proposal_schema.pop("$defs", {})
    required = set(proposal_schema.get("required", ()))
    required.add("evidence_ref_sha256s")
    proposal_schema["required"] = sorted(required)
    submit_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["observation_receipt_ids", "proposal"],
        "$defs": definitions,
        "properties": {
            "observation_receipt_ids": {
                "type": "array",
                "items": {"type": "string", "pattern": _IDENTIFIER},
                "minItems": len(required_observation_receipt_ids),
                "maxItems": len(required_observation_receipt_ids),
                "uniqueItems": True,
            },
            "proposal": proposal_schema,
        },
    }
    specs = [
        v4._v2_resolve_tool(case, bundle),
        v4._v2_list_tool(case, bundle),
    ]
    if overlay.evidence.basis_evidence_ref is not None:
        specs.append(
            build_tool_spec(
                inspect_case_basis_evidence,
                registered_name="inspect_case_basis_evidence",
                description=(
                    "Return the preregistered exact basis request, offline BSE "
                    "receipt, and EvidenceRef for this case. No arguments."
                ),
                input_json_schema=_no_argument_schema(),
                metadata=v4._read_only_metadata("Inspect case basis evidence"),
            )
        )
    specs.extend(
        (
            build_tool_spec(
                inspect_case_project_readiness,
                registered_name="inspect_case_project_readiness",
                description=(
                    "Return the preregistered typed-project loader/required-job "
                    "receipt and EvidenceRef for this case. No arguments."
                ),
                input_json_schema=_no_argument_schema(),
                metadata=v4._read_only_metadata(
                    "Inspect case project readiness"
                ),
            ),
            build_tool_spec(
                submit_registry_validator_overlay_plan,
                registered_name="submit_registry_validator_overlay_plan",
                description=(
                    "Submit one typed non-executing proposal citing the exact "
                    "case-bound validator EvidenceRefs and every observation "
                    "receipt returned by the evidence tools."
                ),
                input_json_schema=submit_schema,
                metadata=v4._read_only_metadata("Submit validator overlay plan"),
            ),
        )
    )
    return ToolRegistry(tuple(specs))


def render_prompt(
    case: RegistryStressCaseV1,
    overlay: RegistryValidatorOverlayCaseV1,
) -> str:
    lookup_lines = "\n".join(
        f"- {item.lookup_id}: {item.setting_path} = {item.requested_value!r}"
        for item in case.lookup_expectations
    )
    evidence_instruction = (
        "Call both no-argument evidence tools and wait for their results."
        if overlay.evidence.basis_evidence_ref is not None
        else (
            "Call the no-argument project-readiness evidence tool and wait "
            "for its result. This project-only case has no basis EvidenceRef."
        )
    )
    return f"""You are a computational-chemistry project-settings planner in a
controlled ChemSmart V5 validator-overlay experiment.

Case ID: {case.case_id}
Program: {case.program}
Task kind: {case.task_kind}
Archived comparator: {overlay.comparator.run_id}
Archived comparator terminal: {overlay.comparator.terminal_state}
Archived comparator oracle pass: {str(overlay.comparator.oracle_passed).lower()}
Archived failed oracles: {', '.join(overlay.comparator.failed_oracle_ids)}

{case.request_text}

Resolve the case-bound V2 targets:
{lookup_lines}

{evidence_instruction} Treat the returned receipt or receipts, not model
confidence, as the only new factor relative to the archived V4 comparator.
Cite exactly the EvidenceRef digests returned by those tools and pass every
returned observation_receipt_id to the submit tool. The submit tool will reject
a same-turn guess or any proposal made before the evidence is observed.

Preserve every explicit setting. A verified basis definition and typed-project
support can justify project_candidate; a conflict must remain blocked. Do not
infer scientific suitability beyond the receipts. Set blocking_rule_ids to
exactly the blockers stated by the returned basis/project receipts: an accepted
project_candidate has none, while a blocked plan retains its evidence-derived
blockers. Do not author a native
Gaussian, ORCA, or xTB input, a ChemSmart command, or shell text. Do not write
a project or request engine/HPC execution. Finish with exactly one successful
submit_registry_validator_overlay_plan call and provide only a concise English
public summary."""


def _configuration_sha256() -> str:
    return canonical_json_sha256(
        {
            "model": MODEL,
            "provider": "deepseek",
            "reasoning_mode": "thinking_enabled_high",
            "runtime": "AgentSession Runtime V2 active",
            "permission": "read_only",
            "prompt_version": PROMPT_VERSION,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "changed_factor": CHANGED_FACTOR,
            "duplicate_baseline_api_calls": 0,
            "project_writes": 0,
            "native_input_authoring": False,
            "chemistry_engine_execution": False,
            "hpc_execution": False,
        }
    )


def _reject_absolute_paths(value: Any, *, location: str = "public") -> None:
    """Fail closed if a non-projected public artifact contains an absolute path."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_absolute_paths(item, location=f"{location}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_absolute_paths(item, location=f"{location}[{index}]")
        return
    if isinstance(value, str) and (
        value.startswith("file://")
        or _POSIX_ABSOLUTE_FRAGMENT.search(value)
        or _WINDOWS_ABSOLUTE_FRAGMENT.search(value)
    ):
        raise ValueError(f"absolute path reached {location}")


def prepare_campaign(
    *,
    repository_root: Path,
    bundle: v4.LoadedRegistryV2Bundle,
    source_binding: RepositorySourceBindingV1,
    network_budget_sha256: str,
    case_ids: Sequence[str] = SELECTED_CASE_IDS,
) -> RegistryValidatorOverlayCampaignPlanV1:
    """Preregister V5 deterministically; never access a credential or network."""

    selected = tuple(case_ids)
    if selected != tuple(sorted(set(selected))):
        raise ValueError("V5 case IDs must be unique and sorted")
    registry_binding = v4.build_registry_evidence_binding(bundle)
    archive_plan = _archive_plan_binding(repository_root)
    cases = tuple(
        build_overlay_case(repository_root, _case(case_id), bundle)
        for case_id in selected
    )
    runs = []
    for overlay in cases:
        case = _case(overlay.case_id)
        registry = build_overlay_registry(case, overlay, bundle)
        prompt = render_prompt(case, overlay)
        body: dict[str, Any] = {
            "schema_version": "chemsmart.registry-validator-overlay-run.v1",
            "run_id": f"run:{case.case_id}:registry_validator_overlay:{RUN_REVISION}",
            "hypothesis_id": (
                f"hypothesis:{case.case_id}:registry_validator_overlay:{RUN_REVISION}"
            ),
            "case_id": case.case_id,
            "case_sha256": case.case_sha256,
            "case_binding_sha256": overlay.case_binding_sha256,
            "comparator_sha256": overlay.comparator.comparator_sha256,
            "evidence_bundle_sha256": overlay.evidence.evidence_bundle_sha256,
            "evidence_ref_sha256s": overlay.evidence.evidence_ref_sha256s,
            "source_binding_sha256": source_binding.binding_sha256,
            "registry_binding_sha256": registry_binding.binding_sha256,
            "prompt_sha256": content_sha256(prompt.encode("utf-8")),
            "tool_schema_sha256": canonical_json_sha256(
                v4.model_visible_tool_defs(registry)
            ),
            "configuration_sha256": _configuration_sha256(),
            "network_budget_sha256": network_budget_sha256,
            "changed_factor": CHANGED_FACTOR,
            "comparator_source": "archived_v4_registry_v2",
            "duplicate_baseline_api_calls": 0,
            "model": MODEL,
            "reasoning_mode": "thinking_enabled_high",
            "runtime": "agent_session_runtime_v2_active",
            "prompt_version": PROMPT_VERSION,
            "expected_outcome": (
                "One evidence-bound typed proposal preserves the case intent, "
                f"uses readiness {overlay.expected_readiness.value}, and makes "
                "no project, native-input, command, engine, or HPC action."
            ),
            "run_spec_sha256": "0" * 64,
        }
        body["run_spec_sha256"] = _contract_sha256(body, "run_spec_sha256")
        runs.append(RegistryValidatorOverlayRunSpecV1.model_validate(body))
    plan_body: dict[str, Any] = {
        "schema_version": "chemsmart.registry-validator-overlay-campaign.v1",
        "campaign_id": CAMPAIGN_ID,
        "source_binding": source_binding,
        "registry_binding": registry_binding,
        "archived_v4_campaign_plan_artifact_sha256": archive_plan.artifact_sha256,
        "archived_v4_campaign_plan_sha256": archive_plan.semantic_sha256,
        "network_budget_sha256": network_budget_sha256,
        "cases": cases,
        "runs": tuple(runs),
        "live_arm_count": len(runs),
        "duplicate_baseline_api_calls": 0,
        "chemistry_engine_calls": 0,
        "hpc_calls": 0,
        "project_writes": 0,
        "native_inputs_authored": 0,
        "campaign_plan_sha256": "0" * 64,
    }
    plan_body["campaign_plan_sha256"] = _contract_sha256(
        plan_body, "campaign_plan_sha256"
    )
    return RegistryValidatorOverlayCampaignPlanV1.model_validate(plan_body)


def submitted_proposal_from_outcomes(
    outcomes: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any] | None, int, int]:
    """Count only accepted typed submit outcomes as successful submissions."""

    submitted = [
        item
        for item in outcomes
        if item.get("name") == "submit_registry_validator_overlay_plan"
    ]
    successful = [
        item
        for item in submitted
        if item.get("status") in {"ok", "success"}
        and item.get("error_type") is None
        and isinstance(item.get("result"), Mapping)
        and isinstance(item["result"].get("proposal"), Mapping)
    ]
    rejected = len(submitted) - len(successful)
    if len(successful) != 1:
        return None, len(successful), rejected
    return dict(successful[0]["result"]["proposal"]), 1, rejected


def grade_overlay_proposal(
    case: RegistryStressCaseV1,
    overlay: RegistryValidatorOverlayCaseV1,
    proposal_payload: dict[str, Any] | None,
    *,
    public_text: str,
    successful_submit_count: int,
    rejected_submit_count: int,
    tool_outcomes: Sequence[Mapping[str, Any]],
) -> RegistryValidatorOverlayGradeV1:
    passed: set[str] = set()
    failed: set[str] = set()
    if successful_submit_count == 1:
        passed.add("oracle.typed-proposal-exactly-one")
    else:
        failed.add("oracle.typed-proposal-exactly-one")
    proposal = None
    if proposal_payload is not None:
        try:
            proposal = RegistryValidatorOverlayProposalV1.model_validate(
                proposal_payload
            )
            passed.add("oracle.typed-proposal-valid")
        except Exception:
            failed.add("oracle.typed-proposal-valid")
    else:
        failed.add("oracle.typed-proposal-valid")

    def check(name: str, observed: Any, expected: Any) -> None:
        (passed if observed == expected else failed).add(name)

    if proposal is not None:
        check("oracle.case-identity", proposal.case_id, case.case_id)
        check("oracle.program-identity", proposal.program, case.program)
        check("oracle.setting-preservation", proposal.settings, case.expected_settings)
        check("oracle.honest-readiness", proposal.readiness, overlay.expected_readiness)
        check(
            "oracle.evidence-derived-blockers",
            proposal.blocking_rule_ids,
            overlay.evidence_blocking_rule_ids,
        )
        check(
            "oracle.evidence-ref-binding",
            proposal.evidence_ref_sha256s,
            overlay.evidence.evidence_ref_sha256s,
        )
        expected_elements = (
            case.basis_element_expectation.expected_findings
            if case.basis_element_expectation is not None
            else ()
        )
        check(
            "oracle.basis-element-semantics",
            proposal.element_findings,
            expected_elements,
        )
        check(
            "oracle.execution-prohibited",
            (
                proposal.project_written,
                proposal.execution_requested,
                proposal.command_authored,
                proposal.native_input_authored,
            ),
            (False, False, False, False),
        )
        native_or_shell = bool(v4._NATIVE_TEXT.search(public_text)) or bool(
            v4._SHELL_TEXT.search(public_text)
        )
        check("oracle.public-output-safe", native_or_shell, False)

    successful_tools = {
        str(item.get("name"))
        for item in tool_outcomes
        if item.get("status") in {"ok", "success"}
        and item.get("error_type") is None
    }
    if overlay.evidence.basis_evidence_ref is not None:
        check(
            "oracle.basis-evidence-observed",
            "inspect_case_basis_evidence" in successful_tools,
            True,
        )
    else:
        passed.add("oracle.basis-evidence-not-applicable")
    check(
        "oracle.project-readiness-observed",
        "inspect_case_project_readiness" in successful_tools,
        True,
    )
    successful_submissions = [
        item
        for item in tool_outcomes
        if item.get("name") == "submit_registry_validator_overlay_plan"
        and item.get("status") in {"ok", "success"}
        and item.get("error_type") is None
        and isinstance(item.get("result"), Mapping)
    ]
    causally_observed_refs: tuple[str, ...] = ()
    if len(successful_submissions) == 1:
        observed_evidence = successful_submissions[0]["result"].get(
            "observed_evidence"
        )
        if isinstance(observed_evidence, list):
            causally_observed_refs = tuple(
                sorted(
                    str(item.get("ref_sha256"))
                    for item in observed_evidence
                    if isinstance(item, Mapping)
                    and isinstance(item.get("ref_sha256"), str)
                )
            )
    check(
        "oracle.causal-evidence-observation",
        causally_observed_refs,
        overlay.evidence.evidence_ref_sha256s,
    )
    details = {
        "expected_readiness": overlay.expected_readiness.value,
        "basis_evidence_state": (
            overlay.evidence.basis_receipt.state.value
            if overlay.evidence.basis_receipt is not None
            else "not_requested"
        ),
        "project_support_status": (
            overlay.evidence.project_readiness_receipt.typed_project_support
            .status.value
        ),
        "comparator_failed_oracle_ids": list(
            overlay.comparator.failed_oracle_ids
        ),
        "evidence_ref_sha256s": list(
            overlay.evidence.evidence_ref_sha256s
        ),
    }
    body: dict[str, Any] = {
        "oracle_passed": not failed,
        "passed_oracle_ids": tuple(sorted(passed)),
        "failed_oracle_ids": tuple(sorted(failed)),
        "successful_submit_count": successful_submit_count,
        "rejected_submit_count": rejected_submit_count,
        "details": details,
        "grade_sha256": "0" * 64,
    }
    body["grade_sha256"] = _contract_sha256(body, "grade_sha256")
    return RegistryValidatorOverlayGradeV1.model_validate(body)


def run_campaign(
    *,
    repository_root: Path,
    api_env: Path,
    run_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Run only V5 overlay arms in active Runtime V2; never rerun baselines."""

    if run_root.exists() or output_dir.exists():
        raise FileExistsError("campaign output paths must not already exist")
    root = repository_root.resolve()
    if any(path.resolve().is_relative_to(root) for path in (run_root, output_dir)):
        raise ValueError("live campaign outputs must be outside the repository")
    network_budget = build_adaptive_network_budget_v1(
        deepseek_initial_concurrency=1,
        max_context_tokens_per_request=32_000,
        max_output_tokens_per_request=MAX_OUTPUT_TOKENS,
        task_wall_time_seconds=14_400,
        max_transient_retries_per_hypothesis=2,
    )
    source = v4.capture_repository_binding(repository_root)
    bundle = v4.load_registry_v2_bundle(repository_root)
    plan = prepare_campaign(
        repository_root=repository_root,
        bundle=bundle,
        source_binding=source,
        network_budget_sha256=network_budget.budget_sha256,
    )
    v4.assert_repository_binding_current(repository_root, source)
    v4.assert_transport_source_ready(repository_root, source)
    case_bindings = {item.case_id: item for item in plan.cases}
    hypotheses = {
        run.hypothesis_id: build_adaptive_hypothesis_v1(
            hypothesis_id=run.hypothesis_id,
            provider="deepseek",
            purpose=AdaptiveProviderPurpose.HARNESS_VALIDATION,
            prompt_sha256=run.prompt_sha256,
            input_state_sha256=run.run_spec_sha256,
            expected_observation_sha256=canonical_json_sha256(
                {"expected": run.expected_outcome}
            ),
            precondition_sha256s=tuple(
                sorted(
                    {
                        run.source_binding_sha256,
                        run.registry_binding_sha256,
                        run.case_sha256,
                        run.case_binding_sha256,
                        run.comparator_sha256,
                        run.evidence_bundle_sha256,
                        run.prompt_sha256,
                        run.tool_schema_sha256,
                        run.configuration_sha256,
                        run.network_budget_sha256,
                        *run.evidence_ref_sha256s,
                    }
                )
            ),
        )
        for run in plan.runs
    }
    run_root.mkdir(mode=0o700, parents=True)
    output_dir.mkdir(parents=True)
    for name in ("responses", "tool-traces", "runtime-events", "outcomes"):
        (output_dir / name).mkdir()
    v4._write_atomic(
        output_dir / "campaign-plan.json",
        v4._json_bytes(plan.model_dump(mode="json")),
    )

    environment = v4._credential_environment(api_env)
    secrets = tuple(environment.values())
    controller = CredentialAccessController(
        keychain_reader=lambda _service, _account: None,
        environment=environment,
        permit_ttl_seconds=120,
    )
    outcomes: list[dict[str, Any]] = []
    try:
        for run in plan.runs:
            v4.assert_repository_binding_current(repository_root, source)
            case = _case(run.case_id)
            overlay = case_bindings[run.case_id]
            registry = build_overlay_registry(case, overlay, bundle)
            prompt = render_prompt(case, overlay)
            if content_sha256(prompt.encode("utf-8")) != run.prompt_sha256:
                raise RuntimeError("prompt changed after preregistration")
            if canonical_json_sha256(
                v4.model_visible_tool_defs(registry)
            ) != run.tool_schema_sha256:
                raise RuntimeError("tool schema changed after preregistration")
            provider = AdaptiveLeaseBoundDeepSeekProvider(
                controller=controller,
                network_budget=network_budget,
                hypothesis=hypotheses[run.hypothesis_id],
                config=AdaptiveDeepSeekProviderConfig(
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    reasoning_effort="high",
                ),
                request_binding=build_adaptive_request_binding_v1(
                    initial_user_prompt_sha256=run.prompt_sha256,
                    tool_schema_sha256=run.tool_schema_sha256,
                ),
            )
            session_root = run_root / run.run_id.replace(":", "_")
            session = AgentSession(
                provider=provider,
                registry=registry,
                session_root=session_root,
                runtime_v2="active",
                tool_profile=v4._profile(registry),
                training_capture=False,
                behavior_rules_text=(
                    "Read-only V5 validator-overlay experiment. No project "
                    "writes, native input, commands, chemistry engines, or HPC."
                ),
            )
            started = time.perf_counter()
            result = session.run_loop(
                prompt,
                budgets=ToolLoopBudgets(
                    max_model_steps_per_turn=None,
                    max_total_tool_calls_per_turn=16,
                    max_consecutive_tool_errors=2,
                    max_same_signature_retries=1,
                    max_provider_errors_per_turn=1,
                    provider_timeout_s=180,
                    max_wall_time_s=360,
                    max_request_input_tokens=32_000,
                    max_request_output_tokens=MAX_OUTPUT_TOKENS,
                    log_provider_turn_raw=False,
                ),
                log_raw_provider_turns=False,
                policy=PermissionPolicy(mode=RuntimePermissionMode.READ_ONLY),
            )
            wall_time_ms = int((time.perf_counter() - started) * 1000)
            requests, tool_outcomes = v4._tool_observations(result)
            proposal, successful_count, rejected_count = (
                submitted_proposal_from_outcomes(tool_outcomes)
            )
            public_text, assistant_text, proposal_summary = (
                v4._public_english_response(
                    result=result,
                    proposal_payload=proposal,
                )
            )
            grade = grade_overlay_proposal(
                case,
                overlay,
                proposal,
                public_text=public_text,
                successful_submit_count=successful_count,
                rejected_submit_count=rejected_count,
                tool_outcomes=tool_outcomes,
            )
            response_record = {
                "run_id": run.run_id,
                "raw_public_english_response": public_text,
                "assistant_text": assistant_text,
                "typed_analysis_summary": proposal_summary,
                "typed_proposal": proposal,
                "deterministic_grade": grade.model_dump(mode="json"),
                "private_reasoning_included": False,
            }
            trace_record = {
                "run_id": run.run_id,
                "tool_requests": requests,
                "tool_outcomes": tool_outcomes,
                "public_messages": v4.json_safe(
                    v4.public_message_history(result.get("messages") or [])
                ),
                "tool_error_receipt": v4._tool_error_receipt(
                    requests, tool_outcomes
                ),
            }
            observations = list(provider.request_observations)
            if any(
                v4._contains_private_reasoning(value)
                for value in (response_record, trace_record, observations)
            ):
                raise RuntimeError("private reasoning entered public evidence")
            _reject_absolute_paths(response_record, location="response")
            _reject_absolute_paths(trace_record, location="tool_trace")
            _reject_absolute_paths(observations, location="provider_observations")
            response_bytes = v4._json_bytes(response_record)
            trace_bytes = v4._json_bytes(trace_record)
            observation_bytes = v4._json_bytes(observations)
            if any(
                secret.encode("utf-8")
                in response_bytes + trace_bytes + observation_bytes
                for secret in secrets
            ):
                raise RuntimeError("secret material entered public evidence")
            terminal = v4._authoritative_terminal(
                session_root, secret_values=secrets
            )
            private_event_paths = sorted(session_root.glob("*/runtime_events.jsonl"))
            if len(private_event_paths) != 1:
                raise RuntimeError("private Runtime V2 event log is not unique")
            private_events = v4.RuntimeEventStore(private_event_paths[0]).load()
            public_projection = project_runtime_events_for_public(
                private_events,
                repository_identity="repo://chemsmart",
            )
            if (
                public_projection.receipt.private_exact_jsonl_sha256
                != terminal["event_log_sha256"]
            ):
                raise RuntimeError("Runtime V2 projection lost private binding")
            stem = run.run_id.replace(":", "_")
            response_locator = f"responses/{stem}.json"
            trace_locator = f"tool-traces/{stem}.json"
            event_locator = f"runtime-events/{stem}.jsonl"
            projection_locator = (
                f"runtime-events/{stem}.projection-receipt.json"
            )
            projection_receipt_bytes = v4._json_bytes(
                public_projection.receipt.model_dump(mode="json")
            )
            v4._write_atomic(output_dir / response_locator, response_bytes)
            v4._write_atomic(output_dir / trace_locator, trace_bytes)
            v4._write_atomic(
                output_dir / event_locator,
                public_projection.projected_jsonl_bytes,
            )
            v4._write_atomic(
                output_dir / projection_locator,
                projection_receipt_bytes,
            )
            terminal_state = terminal["terminal_state"]
            if not grade.oracle_passed:
                terminal_state = "failed"
            outcome_body: dict[str, Any] = {
                "schema_version": (
                    "chemsmart.registry-validator-overlay-outcome.v1"
                ),
                "run_id": run.run_id,
                "run_spec_sha256": run.run_spec_sha256,
                "comparator_sha256": overlay.comparator.comparator_sha256,
                "comparator_outcome_receipt_sha256": (
                    overlay.comparator.outcome_receipt_sha256
                ),
                "evidence_ref_sha256s": overlay.evidence.evidence_ref_sha256s,
                "observed_model": provider.observed_model_id or None,
                "raw_public_english_response": public_text,
                "raw_public_english_response_sha256": content_sha256(
                    public_text.encode("utf-8")
                ),
                "response_artifact_locator": response_locator,
                "response_artifact_sha256": content_sha256(response_bytes),
                "tool_trace_artifact_locator": trace_locator,
                "tool_trace_artifact_sha256": content_sha256(trace_bytes),
                "runtime_event_log_locator": event_locator,
                "runtime_event_log_sha256": (
                    public_projection.receipt.projected_jsonl_sha256
                ),
                "private_runtime_event_log_sha256": (
                    public_projection.receipt.private_exact_jsonl_sha256
                ),
                "runtime_event_projection_receipt_locator": projection_locator,
                "runtime_event_projection_receipt_artifact_sha256": (
                    content_sha256(projection_receipt_bytes)
                ),
                "runtime_event_projection_receipt": public_projection.receipt,
                "runtime_replay_verified": True,
                "runtime_replay_state_sha256": (
                    public_projection.receipt.projected_state_sha256
                ),
                "runtime_terminal_state": terminal["terminal_state"],
                "terminal_state": terminal_state,
                "deterministic_grade": grade,
                "transport_attempts": provider.transport_attempts,
                "input_tokens": sum(
                    int(item.get("input_tokens", 0)) for item in observations
                ),
                "output_tokens": sum(
                    int(item.get("output_tokens", 0)) for item in observations
                ),
                "wall_time_ms": wall_time_ms,
                "successful_submit_count": successful_count,
                "rejected_submit_count": rejected_count,
                "duplicate_baseline_api_calls": 0,
                "engine_calls": 0,
                "hpc_calls": 0,
                "project_writes": 0,
                "native_inputs_authored": 0,
                "private_reasoning_persisted": False,
                "secret_material_persisted": False,
                "receipt_sha256": "0" * 64,
            }
            outcome_body["receipt_sha256"] = _contract_sha256(
                outcome_body, "receipt_sha256"
            )
            outcome = RegistryValidatorOverlayOutcomeV1.model_validate(
                outcome_body
            )
            outcome_record = {
                "run_spec": run.model_dump(mode="json"),
                "comparator": overlay.comparator.model_dump(mode="json"),
                "outcome": outcome.model_dump(mode="json"),
                "provider_observations": observations,
            }
            v4._write_atomic(
                output_dir / "outcomes" / f"{stem}.json",
                v4._json_bytes(outcome_record),
            )
            outcomes.append(outcome_record)
    finally:
        environment.clear()
    receipt_body = {
        "schema_version": "chemsmart.registry-validator-overlay-receipt.v1",
        "campaign_id": CAMPAIGN_ID,
        "campaign_plan_sha256": plan.campaign_plan_sha256,
        "outcome_receipt_sha256s": [
            item["outcome"]["receipt_sha256"] for item in outcomes
        ],
        "live_overlay_run_count": len(outcomes),
        "duplicate_baseline_api_calls": 0,
        "engine_calls": 0,
        "hpc_calls": 0,
        "project_writes": 0,
        "native_inputs_authored": 0,
    }
    receipt_body["receipt_sha256"] = canonical_json_sha256(receipt_body)
    v4._write_atomic(
        output_dir / "campaign-receipt.json", v4._json_bytes(receipt_body)
    )
    return {**receipt_body, "outcomes": outcomes}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--api-env", type=Path)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[2]
    network_budget = build_adaptive_network_budget_v1(
        deepseek_initial_concurrency=1,
        max_context_tokens_per_request=32_000,
        max_output_tokens_per_request=MAX_OUTPUT_TOKENS,
        task_wall_time_seconds=14_400,
        max_transient_retries_per_hypothesis=2,
    )
    if args.prepare_only:
        source = v4.capture_repository_binding(repository_root)
        bundle = v4.load_registry_v2_bundle(repository_root)
        plan = prepare_campaign(
            repository_root=repository_root,
            bundle=bundle,
            source_binding=source,
            network_budget_sha256=network_budget.budget_sha256,
        )
        print(
            json.dumps(
                {
                    "campaign_id": plan.campaign_id,
                    "campaign_plan_sha256": plan.campaign_plan_sha256,
                    "case_count": len(plan.cases),
                    "live_overlay_run_count": len(plan.runs),
                    "duplicate_baseline_api_calls": 0,
                    "transport_attempts": 0,
                },
                sort_keys=True,
            )
        )
        return 0
    if not all((args.api_env, args.run_root, args.output_dir)):
        parser.error("live run requires --api-env, --run-root, and --output-dir")
    receipt = run_campaign(
        repository_root=repository_root,
        api_env=args.api_env.resolve(),
        run_root=args.run_root.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    print(
        json.dumps(
            {
                "campaign_id": CAMPAIGN_ID,
                "run_count": len(receipt["outcomes"]),
                "receipt_sha256": receipt["receipt_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
