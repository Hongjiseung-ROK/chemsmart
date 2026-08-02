#!/usr/bin/env python3
"""Run the V5r2 compact validator engineering-recovery campaign.

The campaign reuses five exact failed V5r1 outcomes but is deliberately not a
one-factor causal ablation.  It evaluates a composite recovery bundle: compact
host decisions, trusted routing, green completion receipts, provider completion
shape checks, and stronger provenance.  Full replayable receipts remain
host-side while the model acknowledges and explains their compiled decision.
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import time
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
from chemsmart.agent.evidence_artifact_manifest import (
    EvidenceArtifactManifestV1,
    EvidenceArtifactManifestV2,
    build_evidence_artifact_manifest_v2,
    manifest_v2_json_bytes,
    verify_evidence_artifact_manifest,
    verify_evidence_artifact_manifest_v2,
)
from chemsmart.agent.harness.basis_sets.request_evidence import BasisEvidenceState
from chemsmart.agent.loop import ToolLoopBudgets
from chemsmart.agent.permissions import PermissionPolicy, RuntimePermissionMode
from chemsmart.agent.project_readiness import TypedProjectSupportStatus
from chemsmart.agent.registry import ToolRegistry, build_tool_spec
from chemsmart.agent.runtime.adaptive_provider import (
    AdaptiveDeepSeekProviderConfig,
    AdaptiveLeaseBoundDeepSeekProvider,
    build_adaptive_request_binding_v1,
)
from chemsmart.agent.runtime.contracts import TaskPhase
from chemsmart.agent.runtime.public_event_projection import (
    PublicEventProjectionReceiptV1,
    project_runtime_events_for_public,
)
from chemsmart.agent.runtime.tool_catalog import PhaseToolProfile
from chemsmart.agent.settings_registry_stress_receipts import (
    ElementFindingV1,
    RegistryStressCaseV1,
    RegistryStressReadiness,
    StressProjectSettingsV1,
    canonical_json_sha256,
    content_sha256,
)
from scripts.harness import run_registry_validator_overlay_campaign as v5


CAMPAIGN_ID = "registry-validator-decision-development-v5r2"
RUN_REVISION = "v5r2"
PROMPT_VERSION = "registry-validator-decision-prompt.v2"
MODEL = "deepseek-v4-flash"
MAX_OUTPUT_TOKENS = 8_192
MAX_REPAIRS = 2
CHANGED_FACTOR = "compact_validator_runtime_provenance_recovery_bundle"
REQUIRED_EVIDENCE_CEILING_SENTENCE = (
    "Evidence ceiling: scientific suitability, safe preview, engine "
    "acceptance, and execution are not verified."
)
ARCHIVED_V5R1_RELATIVE = Path(
    "docs/evaluation/receipts/registry-validator-overlay-live-v5r1-2026-08-02"
)
ARCHIVED_V5R1_AUDIT_RELATIVE = Path(
    "docs/evaluation/receipts/"
    "registry-validator-overlay-live-v5r1-2026-08-02-audit-reconciliation.json"
)
SELECTED_CASE_IDS = (
    "gaussian-def2-tzvppd-missing-ce",
    "gaussian-raw-route-functional-invalid",
    "orca-def2-ecp-orbital-missing",
    "orca-def2-tzvp-fe-no-ecp",
    "orca-def2-tzvp-pd-28e-ecp",
)

_SHA256 = r"^[0-9a-f]{64}$"
_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_SAFE_LOCATOR = re.compile(r"^[A-Za-z0-9._/-]+$")
_UNSUPPORTED_POSITIVE_CLAIM = re.compile(
    r"\b(?:scientifically\s+suitable|safe\s+preview\s+(?:passed|completed?)|"
    r"engine\s+(?:accepted|validated)|execution\s+(?:completed?|succeeded)|"
    r"reproduc(?:ed|tion\s+completed?)|ready\s+for\s+(?:execution|production))\b",
    re.IGNORECASE,
)


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class ArchivedV5r1ComparatorV1(_Contract):
    schema_version: Literal[
        "chemsmart.archived-validator-overlay-comparator.v1"
    ] = "chemsmart.archived-validator-overlay-comparator.v1"
    campaign_id: Literal["registry-validator-overlay-development-v5"]
    case_id: str = Field(pattern=_IDENTIFIER)
    run_id: str = Field(pattern=_IDENTIFIER)
    outcome_artifact_locator: str
    outcome_artifact_sha256: str = Field(pattern=_SHA256)
    outcome_receipt_sha256: str = Field(pattern=_SHA256)
    run_spec_sha256: str = Field(pattern=_SHA256)
    campaign_plan_artifact_sha256: str = Field(pattern=_SHA256)
    campaign_plan_sha256: str = Field(pattern=_SHA256)
    archive_manifest_sha256: str = Field(pattern=_SHA256)
    archive_manifest_artifact_sha256: str = Field(pattern=_SHA256)
    audit_reconciliation_receipt_sha256: str = Field(pattern=_SHA256)
    terminal_state: Literal["failed", "blocked"]
    failed_oracle_ids: tuple[str, ...] = ()
    comparator_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _comparator_is_bound(self) -> "ArchivedV5r1ComparatorV1":
        locator = Path(self.outcome_artifact_locator)
        if (
            locator.is_absolute()
            or ".." in locator.parts
            or _SAFE_LOCATOR.fullmatch(self.outcome_artifact_locator) is None
        ):
            raise ValueError("archived comparator locator is unsafe")
        if self.failed_oracle_ids != tuple(sorted(set(self.failed_oracle_ids))):
            raise ValueError("archived failed oracles must be canonical")
        if self.comparator_sha256 != _contract_sha256(
            self, "comparator_sha256"
        ):
            raise ValueError("archived V5r1 comparator digest mismatch")
        return self


class OverlayReadinessDecisionV1(_Contract):
    schema_version: Literal[
        "chemsmart.overlay-readiness-decision.v1"
    ] = "chemsmart.overlay-readiness-decision.v1"
    authority_id: Literal["chemsmart.validator-evidence-readiness"] = (
        "chemsmart.validator-evidence-readiness"
    )
    authority_version: Literal["1.0.0"] = "1.0.0"
    case_id: str = Field(pattern=_IDENTIFIER)
    case_sha256: str = Field(pattern=_SHA256)
    immutable_settings_sha256: str = Field(pattern=_SHA256)
    project_receipt_sha256: str = Field(pattern=_SHA256)
    basis_receipt_sha256: str | None = Field(default=None, pattern=_SHA256)
    evidence_ref_sha256s: tuple[str, ...] = Field(min_length=1, max_length=2)
    readiness: RegistryStressReadiness
    blocking_rule_ids: tuple[str, ...] = ()
    derivation_rule_ids: tuple[str, ...] = Field(min_length=1)
    scope: Literal[
        "project_candidate_only_no_suitability_or_execution"
    ] = "project_candidate_only_no_suitability_or_execution"
    decision_sha256: str = Field(pattern=_SHA256)

    @field_validator(
        "evidence_ref_sha256s", "blocking_rule_ids", "derivation_rule_ids"
    )
    @classmethod
    def _canonical_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("decision values must be unique and sorted")
        return value

    @model_validator(mode="after")
    def _decision_is_consistent(self) -> "OverlayReadinessDecisionV1":
        candidate = self.readiness is RegistryStressReadiness.PROJECT_CANDIDATE
        if candidate == bool(self.blocking_rule_ids):
            raise ValueError("decision readiness conflicts with blockers")
        if self.decision_sha256 != _contract_sha256(
            self, "decision_sha256"
        ):
            raise ValueError("validator decision digest mismatch")
        return self


class CompactBasisElementV1(_Contract):
    atomic_number: int = Field(ge=1, le=118)
    symbol: str = Field(pattern=r"^[A-Z][a-z]?$", max_length=2)
    state: BasisEvidenceState
    covered: bool | None
    orbital_present: bool | None
    ecp_present: bool | None
    ecp_electrons: int | None = Field(default=None, ge=1)
    reason_rule_ids: tuple[str, ...] = Field(min_length=1)


class CompactBasisEvidenceV1(_Contract):
    request_sha256: str = Field(pattern=_SHA256)
    receipt_sha256: str = Field(pattern=_SHA256)
    evidence_ref_sha256: str = Field(pattern=_SHA256)
    program: Literal["gaussian", "orca", "xtb"]
    basis_literal: str
    role: Literal["orbital", "ecp"]
    atomic_numbers: tuple[int, ...] = Field(min_length=1)
    state: BasisEvidenceState
    canonical_basis_name: str | None = None
    inspection_status: str | None = None
    reason_rule_ids: tuple[str, ...] = Field(min_length=1)
    elements: tuple[CompactBasisElementV1, ...] = Field(min_length=1)
    evidence_scope: str
    source_package: str | None = None
    source_version: str | None = None
    scientific_suitability_verified: Literal[False] = False
    native_engine_verified: Literal[False] = False


class CompactProjectEvidenceV1(_Contract):
    request_sha256: str = Field(pattern=_SHA256)
    receipt_sha256: str = Field(pattern=_SHA256)
    evidence_ref_sha256: str = Field(pattern=_SHA256)
    authority_id: str
    authority_version: str
    program: Literal["gaussian", "orca", "xtb"]
    required_job: str
    status: TypedProjectSupportStatus
    blocking_rule_ids: tuple[str, ...] = ()
    finding_rule_ids: tuple[str, ...] = ()
    renderer_status: str
    validation_verdict: str
    project_yaml_sha256: str | None = Field(default=None, pattern=_SHA256)
    support_scope: str
    engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0
    project_writes: Literal[0] = 0
    native_input_previews: Literal[0] = 0


class ValidatorDecisionProjectionV1(_Contract):
    schema_version: Literal[
        "chemsmart.validator-decision-projection.v1"
    ] = "chemsmart.validator-decision-projection.v1"
    case_id: str = Field(pattern=_IDENTIFIER)
    immutable_settings: StressProjectSettingsV1
    basis_evidence: CompactBasisEvidenceV1 | None = None
    project_evidence: CompactProjectEvidenceV1
    decision: OverlayReadinessDecisionV1
    evidence_ref_sha256s: tuple[str, ...] = Field(min_length=1, max_length=2)
    projection_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _projection_is_bound(self) -> "ValidatorDecisionProjectionV1":
        if self.case_id != self.decision.case_id:
            raise ValueError("projection decision belongs to another case")
        if self.evidence_ref_sha256s != self.decision.evidence_ref_sha256s:
            raise ValueError("projection EvidenceRefs differ from decision")
        if self.projection_sha256 != _contract_sha256(
            self, "projection_sha256"
        ):
            raise ValueError("validator projection digest mismatch")
        return self


class ValidatorDecisionObservationReceiptV1(_Contract):
    schema_version: Literal[
        "chemsmart.validator-decision-observation.v1"
    ] = "chemsmart.validator-decision-observation.v1"
    observation_receipt_id: str = Field(pattern=_IDENTIFIER)
    projection_sha256: str = Field(pattern=_SHA256)
    decision_sha256: str = Field(pattern=_SHA256)
    evidence_ref_sha256s: tuple[str, ...] = Field(min_length=1, max_length=2)
    observation_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _observation_is_bound(self) -> "ValidatorDecisionObservationReceiptV1":
        if self.observation_sha256 != _contract_sha256(
            self, "observation_sha256"
        ):
            raise ValueError("decision observation digest mismatch")
        return self


class ValidatorDecisionDraftV1(_Contract):
    readiness: RegistryStressReadiness
    element_findings: tuple[ElementFindingV1, ...] = ()
    decision_sha256: str = Field(pattern=_SHA256)
    analysis_summary: str = Field(min_length=1, max_length=3000)


class ProposalCounterexampleV1(_Contract):
    schema_version: Literal[
        "chemsmart.validator-proposal-counterexample.v1"
    ] = "chemsmart.validator-proposal-counterexample.v1"
    rule_id: str = Field(pattern=_IDENTIFIER)
    failed_field: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,159}$")
    expected: Any
    observed: Any
    evidence_id: str = Field(pattern=_IDENTIFIER)
    counterexample_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _counterexample_is_bound(self) -> "ProposalCounterexampleV1":
        if self.counterexample_sha256 != _contract_sha256(
            self, "counterexample_sha256"
        ):
            raise ValueError("proposal counterexample digest mismatch")
        return self


class ValidatorDecisionSubmitResultV1(_Contract):
    schema_version: Literal[
        "chemsmart.validator-decision-submit-result.v1"
    ] = "chemsmart.validator-decision-submit-result.v1"
    accepted: bool
    status: Literal[
        "accepted", "observation_required", "repair_required", "blocked"
    ]
    verdict: Literal["ok", "reject"]
    proposal: v5.RegistryValidatorOverlayProposalV1 | None = None
    counterexamples: tuple[ProposalCounterexampleV1, ...] = ()
    repairs_used: int = Field(ge=0, le=MAX_REPAIRS)
    repairs_remaining: int = Field(ge=0, le=MAX_REPAIRS)
    decision_sha256: str = Field(pattern=_SHA256)
    observation_sha256: str | None = Field(default=None, pattern=_SHA256)
    result_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _result_is_consistent(self) -> "ValidatorDecisionSubmitResultV1":
        if self.accepted != (self.status == "accepted"):
            raise ValueError("submit acceptance conflicts with status")
        if self.accepted != (self.verdict == "ok"):
            raise ValueError("submit acceptance conflicts with verdict")
        if self.accepted != (self.proposal is not None):
            raise ValueError("accepted submit requires exactly one proposal")
        if self.accepted and self.counterexamples:
            raise ValueError("accepted submit cannot retain counterexamples")
        if self.result_sha256 != _contract_sha256(self, "result_sha256"):
            raise ValueError("submit-result digest mismatch")
        return self


class ValidatorDecisionCaseV1(_Contract):
    schema_version: Literal[
        "chemsmart.validator-decision-case.v1"
    ] = "chemsmart.validator-decision-case.v1"
    case_id: str = Field(pattern=_IDENTIFIER)
    case_sha256: str = Field(pattern=_SHA256)
    comparator: ArchivedV5r1ComparatorV1
    evidence: v5.ValidatorEvidenceBundleV1
    decision: OverlayReadinessDecisionV1
    projection: ValidatorDecisionProjectionV1
    changed_factor: Literal[
        "compact_validator_runtime_provenance_recovery_bundle"
    ] = CHANGED_FACTOR
    case_binding_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _case_is_bound(self) -> "ValidatorDecisionCaseV1":
        if self.case_id not in SELECTED_CASE_IDS:
            raise ValueError("case is not preregistered for V5r2")
        if any(
            item.case_id != self.case_id
            for item in (self.comparator, self.decision, self.projection)
        ):
            raise ValueError("V5r2 case components have different identities")
        if self.evidence.case_id != self.case_id:
            raise ValueError("V5r2 evidence belongs to another case")
        replayed = derive_overlay_readiness_decision(
            _case(self.case_id), self.evidence
        )
        if replayed != self.decision:
            raise ValueError("V5r2 readiness decision does not replay")
        replayed_projection = build_validator_decision_projection(
            _case(self.case_id), self.evidence, replayed
        )
        if replayed_projection != self.projection:
            raise ValueError("V5r2 compact projection does not replay")
        if self.case_binding_sha256 != _contract_sha256(
            self, "case_binding_sha256"
        ):
            raise ValueError("V5r2 case digest mismatch")
        return self


class ValidatorDecisionRunSpecV1(_Contract):
    schema_version: Literal[
        "chemsmart.validator-decision-run.v1"
    ] = "chemsmart.validator-decision-run.v1"
    run_id: str = Field(pattern=_IDENTIFIER)
    hypothesis_id: str = Field(pattern=_IDENTIFIER)
    case_id: str = Field(pattern=_IDENTIFIER)
    case_sha256: str = Field(pattern=_SHA256)
    case_binding_sha256: str = Field(pattern=_SHA256)
    comparator_sha256: str = Field(pattern=_SHA256)
    evidence_bundle_sha256: str = Field(pattern=_SHA256)
    decision_sha256: str = Field(pattern=_SHA256)
    projection_sha256: str = Field(pattern=_SHA256)
    source_binding_sha256: str = Field(pattern=_SHA256)
    registry_binding_sha256: str = Field(pattern=_SHA256)
    prompt_sha256: str = Field(pattern=_SHA256)
    tool_schema_sha256: str = Field(pattern=_SHA256)
    configuration_sha256: str = Field(pattern=_SHA256)
    network_budget_sha256: str = Field(pattern=_SHA256)
    changed_factor: Literal[
        "compact_validator_runtime_provenance_recovery_bundle"
    ] = CHANGED_FACTOR
    comparator_source: Literal["archived_v5r1_failed_outcome"] = (
        "archived_v5r1_failed_outcome"
    )
    duplicate_comparator_api_calls: Literal[0] = 0
    model: Literal["deepseek-v4-flash"] = MODEL
    reasoning_mode: Literal["thinking_enabled_high"] = (
        "thinking_enabled_high"
    )
    runtime: Literal["agent_session_runtime_v2_active"] = (
        "agent_session_runtime_v2_active"
    )
    prompt_version: Literal["registry-validator-decision-prompt.v2"] = (
        PROMPT_VERSION
    )
    expected_outcome: str = Field(min_length=1, max_length=1000)
    run_spec_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _run_is_bound(self) -> "ValidatorDecisionRunSpecV1":
        if self.run_spec_sha256 != _contract_sha256(
            self, "run_spec_sha256"
        ):
            raise ValueError("validator-decision run digest mismatch")
        return self


class ValidatorDecisionCampaignPlanV1(_Contract):
    schema_version: Literal[
        "chemsmart.validator-decision-campaign.v1"
    ] = "chemsmart.validator-decision-campaign.v1"
    campaign_id: Literal[
        "registry-validator-decision-development-v5r2"
    ] = CAMPAIGN_ID
    source_binding: v5.RepositorySourceBindingV1
    registry_binding: v5.RegistryEvidenceBindingV1
    network_budget_sha256: str = Field(pattern=_SHA256)
    cases: tuple[ValidatorDecisionCaseV1, ...] = Field(min_length=1)
    runs: tuple[ValidatorDecisionRunSpecV1, ...] = Field(min_length=1)
    live_run_count: int = Field(ge=1)
    duplicate_comparator_api_calls: Literal[0] = 0
    chemistry_engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0
    project_writes: Literal[0] = 0
    native_inputs_authored: Literal[0] = 0
    campaign_plan_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _plan_is_bound(self) -> "ValidatorDecisionCampaignPlanV1":
        case_ids = tuple(item.case_id for item in self.cases)
        run_ids = tuple(item.run_id for item in self.runs)
        if case_ids != tuple(sorted(set(case_ids))):
            raise ValueError("validator-decision cases must be canonical")
        if len(run_ids) != len(set(run_ids)) or len(self.runs) != len(
            self.cases
        ):
            raise ValueError("V5r2 requires one unique run per case")
        if self.live_run_count != len(self.runs):
            raise ValueError("V5r2 live-run count is inconsistent")
        by_case = {item.case_id: item for item in self.cases}
        for run in self.runs:
            case = by_case.get(run.case_id)
            if case is None or (
                run.case_sha256 != case.case_sha256
                or run.case_binding_sha256 != case.case_binding_sha256
                or run.comparator_sha256
                != case.comparator.comparator_sha256
                or run.evidence_bundle_sha256
                != case.evidence.evidence_bundle_sha256
                or run.decision_sha256 != case.decision.decision_sha256
                or run.projection_sha256
                != case.projection.projection_sha256
                or run.source_binding_sha256
                != self.source_binding.binding_sha256
                or run.registry_binding_sha256
                != self.registry_binding.binding_sha256
                or run.network_budget_sha256 != self.network_budget_sha256
            ):
                raise ValueError("V5r2 run is not bound to its plan inputs")
        if self.campaign_plan_sha256 != _contract_sha256(
            self, "campaign_plan_sha256"
        ):
            raise ValueError("validator-decision plan digest mismatch")
        return self


class ValidatorDecisionGradeV1(_Contract):
    oracle_passed: bool
    passed_oracle_ids: tuple[str, ...]
    failed_oracle_ids: tuple[str, ...]
    successful_submit_count: int = Field(ge=0)
    rejected_submit_count: int = Field(ge=0)
    details: dict[str, Any]
    grade_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _grade_is_bound(self) -> "ValidatorDecisionGradeV1":
        for values in (self.passed_oracle_ids, self.failed_oracle_ids):
            if values != tuple(sorted(set(values))):
                raise ValueError("grade oracle IDs must be canonical")
        if self.oracle_passed != (not self.failed_oracle_ids):
            raise ValueError("grade verdict conflicts with failed oracles")
        if self.grade_sha256 != _contract_sha256(self, "grade_sha256"):
            raise ValueError("validator-decision grade digest mismatch")
        return self


class ProviderObservationBindingV1(_Contract):
    artifact_locator: str = Field(min_length=1, max_length=1000)
    artifact_sha256: str = Field(pattern=_SHA256)
    observation_count: int = Field(ge=0)
    observations_sha256: str = Field(pattern=_SHA256)

    @field_validator("artifact_locator")
    @classmethod
    def _safe_locator(cls, value: str) -> str:
        path = Path(value)
        if (
            path.is_absolute()
            or ".." in path.parts
            or path.as_posix() != value
            or _SAFE_LOCATOR.fullmatch(value) is None
        ):
            raise ValueError("provider-observation locator is unsafe")
        return value


class CegisAttemptReceiptV1(_Contract):
    ordinal: int = Field(ge=1)
    request_id: str = Field(pattern=_IDENTIFIER)
    arguments_sha256: str = Field(pattern=_SHA256)
    accepted: bool
    status: Literal[
        "accepted", "observation_required", "repair_required", "blocked"
    ]
    verdict: Literal["ok", "reject"]
    result_sha256: str = Field(pattern=_SHA256)
    counterexample_sha256s: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _attempt_is_coherent(self) -> "CegisAttemptReceiptV1":
        if self.accepted != (self.status == "accepted"):
            raise ValueError("CEGIS attempt acceptance is inconsistent")
        if self.accepted != (self.verdict == "ok"):
            raise ValueError("CEGIS attempt verdict is inconsistent")
        if self.counterexample_sha256s != tuple(
            sorted(set(self.counterexample_sha256s))
        ):
            raise ValueError("CEGIS counterexamples must be canonical")
        return self


class ValidatorDecisionOutcomeV1(_Contract):
    schema_version: Literal[
        "chemsmart.validator-decision-outcome.v1"
    ] = "chemsmart.validator-decision-outcome.v1"
    run_id: str = Field(pattern=_IDENTIFIER)
    run_spec_sha256: str = Field(pattern=_SHA256)
    comparator_sha256: str = Field(pattern=_SHA256)
    comparator_outcome_receipt_sha256: str = Field(pattern=_SHA256)
    decision_sha256: str = Field(pattern=_SHA256)
    projection_sha256: str = Field(pattern=_SHA256)
    observed_model: str | None = Field(default=None, max_length=160)
    canonical_public_english_report: str
    canonical_public_english_report_sha256: str = Field(pattern=_SHA256)
    model_public_english_response: str
    model_public_english_response_sha256: str = Field(pattern=_SHA256)
    model_output_authoritative: Literal[False] = False
    response_artifact_locator: str
    response_artifact_sha256: str = Field(pattern=_SHA256)
    tool_trace_artifact_locator: str
    tool_trace_artifact_sha256: str = Field(pattern=_SHA256)
    provider_observations: ProviderObservationBindingV1
    cegis_attempts: tuple[CegisAttemptReceiptV1, ...]
    cegis_lineage_sha256: str = Field(pattern=_SHA256)
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
    deterministic_grade: ValidatorDecisionGradeV1
    accepted_proposal_sha256: str | None = Field(
        default=None, pattern=_SHA256
    )
    transport_attempts: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)
    wall_time_ms: int = Field(ge=0)
    successful_submit_count: int = Field(ge=0)
    rejected_submit_count: int = Field(ge=0)
    duplicate_comparator_api_calls: Literal[0] = 0
    engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0
    project_writes: Literal[0] = 0
    native_inputs_authored: Literal[0] = 0
    private_reasoning_persisted: Literal[False] = False
    secret_material_persisted: Literal[False] = False
    receipt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _outcome_is_bound(self) -> "ValidatorDecisionOutcomeV1":
        if self.canonical_public_english_report_sha256 != content_sha256(
            self.canonical_public_english_report.encode("utf-8")
        ):
            raise ValueError("canonical public-report digest mismatch")
        if self.model_public_english_response_sha256 != content_sha256(
            self.model_public_english_response.encode("utf-8")
        ):
            raise ValueError("model public-response digest mismatch")
        if (
            self.successful_submit_count
            != self.deterministic_grade.successful_submit_count
            or self.rejected_submit_count
            != self.deterministic_grade.rejected_submit_count
        ):
            raise ValueError("outcome submit counts conflict with grade")
        ordinals = tuple(item.ordinal for item in self.cegis_attempts)
        if ordinals != tuple(range(1, len(ordinals) + 1)):
            raise ValueError("CEGIS attempt ordinals are not contiguous")
        if self.cegis_lineage_sha256 != canonical_json_sha256(
            [item.model_dump(mode="json") for item in self.cegis_attempts]
        ):
            raise ValueError("CEGIS lineage digest mismatch")
        if (
            sum(item.accepted for item in self.cegis_attempts)
            != self.successful_submit_count
            or sum(not item.accepted for item in self.cegis_attempts)
            != self.rejected_submit_count
        ):
            raise ValueError("CEGIS lineage submit counts disagree")
        projection = self.runtime_event_projection_receipt
        if (
            projection.projected_jsonl_sha256
            != self.runtime_event_log_sha256
            or projection.private_exact_jsonl_sha256
            != self.private_runtime_event_log_sha256
            or projection.projected_state_sha256
            != self.runtime_replay_state_sha256
        ):
            raise ValueError("Runtime V2 projection binding is incomplete")
        expected_terminal = (
            self.runtime_terminal_state
            if self.deterministic_grade.oracle_passed
            else "failed"
        )
        if self.terminal_state != expected_terminal:
            raise ValueError("outcome terminal conflicts with runtime/grade")
        if (
            self.deterministic_grade.oracle_passed
            and self.observed_model != MODEL
        ):
            raise ValueError("strict pass requires the preregistered model")
        if self.receipt_sha256 != _contract_sha256(
            self, "receipt_sha256"
        ):
            raise ValueError("validator-decision outcome digest mismatch")
        return self


class ValidatorDecisionRunReceiptV1(_Contract):
    schema_version: Literal[
        "chemsmart.validator-decision-run-receipt.v1"
    ] = "chemsmart.validator-decision-run-receipt.v1"
    campaign_id: Literal[
        "registry-validator-decision-development-v5r2"
    ] = CAMPAIGN_ID
    campaign_plan_sha256: str = Field(pattern=_SHA256)
    campaign_plan_artifact_sha256: str = Field(pattern=_SHA256)
    outcome_artifacts: tuple[dict[str, Any], ...]
    outcome_receipt_sha256s: tuple[str, ...]
    live_run_count: int = Field(ge=0)
    strict_pass_count: int = Field(ge=0)
    duplicate_comparator_api_calls: Literal[0] = 0
    engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0
    project_writes: Literal[0] = 0
    native_inputs_authored: Literal[0] = 0
    receipt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _receipt_is_bound(self) -> "ValidatorDecisionRunReceiptV1":
        locators = tuple(str(item.get("locator")) for item in self.outcome_artifacts)
        if locators != tuple(sorted(set(locators))):
            raise ValueError("outcome artifacts must be unique and sorted")
        if len(self.outcome_artifacts) != self.live_run_count:
            raise ValueError("campaign outcome count is inconsistent")
        if len(self.outcome_receipt_sha256s) != self.live_run_count:
            raise ValueError("campaign receipt count is inconsistent")
        if self.outcome_receipt_sha256s != tuple(
            sorted(set(self.outcome_receipt_sha256s))
        ):
            raise ValueError("outcome receipt digests must be canonical")
        for item in self.outcome_artifacts:
            if set(item) != {"artifact_sha256", "locator", "size_bytes"}:
                raise ValueError("outcome artifact binding is malformed")
            ProviderObservationBindingV1._safe_locator(str(item["locator"]))
            if re.fullmatch(_SHA256, str(item["artifact_sha256"])) is None:
                raise ValueError("outcome artifact digest is invalid")
            if not isinstance(item["size_bytes"], int) or item["size_bytes"] < 1:
                raise ValueError("outcome artifact size is invalid")
        if self.receipt_sha256 != _contract_sha256(
            self, "receipt_sha256"
        ):
            raise ValueError("campaign run-receipt digest mismatch")
        return self


class ValidatorDecisionCampaignReceiptV1(_Contract):
    """Final non-circular envelope binding run receipt and manifest bytes."""

    schema_version: Literal[
        "chemsmart.validator-decision-campaign-receipt.v1"
    ] = "chemsmart.validator-decision-campaign-receipt.v1"
    campaign_id: Literal[
        "registry-validator-decision-development-v5r2"
    ] = CAMPAIGN_ID
    campaign_plan_sha256: str = Field(pattern=_SHA256)
    campaign_plan_artifact_sha256: str = Field(pattern=_SHA256)
    run_receipt_locator: Literal["campaign-run-receipt.json"] = (
        "campaign-run-receipt.json"
    )
    run_receipt_sha256: str = Field(pattern=_SHA256)
    run_receipt_artifact_sha256: str = Field(pattern=_SHA256)
    public_manifest_locator: Literal["artifact-manifest.json"] = (
        "artifact-manifest.json"
    )
    public_manifest_sha256: str = Field(pattern=_SHA256)
    public_manifest_artifact_sha256: str = Field(pattern=_SHA256)
    private_manifest_sha256: str = Field(pattern=_SHA256)
    private_manifest_artifact_sha256: str = Field(pattern=_SHA256)
    private_receipt_sha256: str = Field(pattern=_SHA256)
    private_receipt_artifact_sha256: str = Field(pattern=_SHA256)
    private_artifact_count: int = Field(ge=1)
    semantic_replay_verified: Literal[True] = True
    replayed_outcome_count: int = Field(ge=0)
    replayed_response_count: int = Field(ge=0)
    replayed_tool_trace_count: int = Field(ge=0)
    replayed_provider_observation_count: int = Field(ge=0)
    replayed_runtime_event_count: int = Field(ge=0)
    strict_pass_count: int = Field(ge=0)
    receipt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _envelope_is_bound(self) -> "ValidatorDecisionCampaignReceiptV1":
        counts = {
            self.replayed_outcome_count,
            self.replayed_response_count,
            self.replayed_tool_trace_count,
            self.replayed_provider_observation_count,
            self.replayed_runtime_event_count,
        }
        if len(counts) != 1:
            raise ValueError("campaign replay counts disagree")
        if self.strict_pass_count > self.replayed_outcome_count:
            raise ValueError("strict-pass count exceeds replayed outcomes")
        if self.receipt_sha256 != _contract_sha256(
            self, "receipt_sha256"
        ):
            raise ValueError("final campaign receipt digest mismatch")
        return self


class ValidatorDecisionPrivateReceiptV1(_Contract):
    schema_version: Literal[
        "chemsmart.validator-decision-private-receipt.v1"
    ] = "chemsmart.validator-decision-private-receipt.v1"
    campaign_id: Literal[
        "registry-validator-decision-development-v5r2"
    ] = CAMPAIGN_ID
    campaign_plan_sha256: str = Field(pattern=_SHA256)
    source_binding_sha256: str = Field(pattern=_SHA256)
    private_manifest_sha256: str = Field(pattern=_SHA256)
    private_manifest_artifact_sha256: str = Field(pattern=_SHA256)
    private_artifact_count: int = Field(ge=1)
    private_total_bytes: int = Field(ge=1)
    secret_material_persisted: Literal[False] = False
    private_reasoning_persisted: Literal[False] = False
    receipt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _private_receipt_is_bound(
        self,
    ) -> "ValidatorDecisionPrivateReceiptV1":
        if self.receipt_sha256 != _contract_sha256(
            self, "receipt_sha256"
        ):
            raise ValueError("private campaign receipt digest mismatch")
        return self


def _contract_sha256(value: BaseModel | Mapping[str, Any], field: str) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude={field})
    else:
        payload = {str(key): item for key, item in value.items() if key != field}
    return canonical_json_sha256(payload)


def _case(case_id: str) -> RegistryStressCaseV1:
    matches = tuple(item for item in v5.v4.CASES if item.case_id == case_id)
    if len(matches) != 1:
        raise ValueError(f"registry case is not unique: {case_id}")
    return matches[0]


def _json_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path.name}")
    return value


def _audit_receipt_sha256(value: Mapping[str, Any]) -> str:
    return canonical_json_sha256(
        {key: item for key, item in value.items() if key != "receipt_sha256"}
    )


def load_archived_v5r1_comparator(
    repository_root: Path,
    case_id: str,
) -> ArchivedV5r1ComparatorV1:
    archive_root = repository_root / ARCHIVED_V5R1_RELATIVE
    manifest_path = archive_root / "artifact-manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = EvidenceArtifactManifestV1.model_validate(
        json.loads(manifest_bytes)
    )
    verify_evidence_artifact_manifest(archive_root, manifest)
    plan_path = archive_root / "campaign-plan.json"
    plan = _json_file(plan_path)
    relative = Path("outcomes") / (
        f"run_{case_id}_registry_validator_overlay_v5r1.json"
    )
    outcome_path = archive_root / relative
    outcome_bytes = outcome_path.read_bytes()
    manifest_by_locator = {
        item.locator: item for item in manifest.artifacts
    }
    bound = manifest_by_locator.get(relative.as_posix())
    if bound is None or bound.artifact_sha256 != content_sha256(outcome_bytes):
        raise ValueError("archived V5r1 outcome is not manifest-bound")
    parsed = json.loads(outcome_bytes)
    run = parsed.get("run_spec") or {}
    outcome = parsed.get("outcome") or {}
    grade = outcome.get("deterministic_grade") or {}
    if (
        run.get("case_id") != case_id
        or outcome.get("terminal_state") not in {"failed", "blocked"}
        or grade.get("oracle_passed") is not False
        or plan.get("campaign_id") != "registry-validator-overlay-development-v5"
    ):
        raise ValueError("V5r2 comparator is not an exact failed V5r1 run")
    audit = _json_file(repository_root / ARCHIVED_V5R1_AUDIT_RELATIVE)
    if audit.get("receipt_sha256") != _audit_receipt_sha256(audit):
        raise ValueError("V5r1 audit reconciliation digest mismatch")
    if audit.get("public_artifact_manifest_sha256") != manifest.manifest_sha256:
        raise ValueError("V5r1 audit does not bind the archive manifest")
    body: dict[str, Any] = {
        "schema_version": "chemsmart.archived-validator-overlay-comparator.v1",
        "campaign_id": "registry-validator-overlay-development-v5",
        "case_id": case_id,
        "run_id": run["run_id"],
        "outcome_artifact_locator": (
            ARCHIVED_V5R1_RELATIVE / relative
        ).as_posix(),
        "outcome_artifact_sha256": content_sha256(outcome_bytes),
        "outcome_receipt_sha256": outcome["receipt_sha256"],
        "run_spec_sha256": run["run_spec_sha256"],
        "campaign_plan_artifact_sha256": content_sha256(
            plan_path.read_bytes()
        ),
        "campaign_plan_sha256": plan["campaign_plan_sha256"],
        "archive_manifest_sha256": manifest.manifest_sha256,
        "archive_manifest_artifact_sha256": content_sha256(manifest_bytes),
        "audit_reconciliation_receipt_sha256": audit["receipt_sha256"],
        "terminal_state": outcome["terminal_state"],
        "failed_oracle_ids": tuple(sorted(grade["failed_oracle_ids"])),
        "comparator_sha256": "0" * 64,
    }
    body["comparator_sha256"] = _contract_sha256(
        body, "comparator_sha256"
    )
    return ArchivedV5r1ComparatorV1.model_validate(body)


def _element_findings_from_evidence(
    evidence: v5.ValidatorEvidenceBundleV1,
) -> tuple[ElementFindingV1, ...]:
    receipt = evidence.basis_receipt
    if receipt is None:
        return ()
    if any(
        value is None
        for item in receipt.elements
        for value in (
            item.covered,
            item.orbital_present,
            item.ecp_present,
        )
    ):
        raise ValueError(
            "typed proposal cannot coerce unobserved element facts to false"
        )
    return tuple(
        ElementFindingV1(
            symbol=item.symbol,
            covered=item.covered,
            orbital_present=item.orbital_present,
            ecp_present=item.ecp_present,
            ecp_electrons=item.ecp_electrons,
        )
        for item in receipt.elements
    )


def derive_overlay_readiness_decision(
    case: RegistryStressCaseV1,
    evidence: v5.ValidatorEvidenceBundleV1,
) -> OverlayReadinessDecisionV1:
    """Derive readiness exclusively from replayed validator evidence.

    ``case.expected_readiness`` is deliberately not consulted.  The case owns
    immutable source settings only; the project and request-bound basis
    receipts own readiness and blockers.
    """

    project = evidence.project_readiness_receipt.typed_project_support
    project_map = {
        TypedProjectSupportStatus.BLOCKED_MISSING_EVIDENCE: (
            RegistryStressReadiness.BLOCKED_MISSING_EVIDENCE,
            "validator.decision.project.blocked_missing_evidence",
        ),
        TypedProjectSupportStatus.BLOCKED_UNSUPPORTED_SETTING: (
            RegistryStressReadiness.BLOCKED_UNSUPPORTED_SETTING,
            "validator.decision.project.blocked_unsupported_setting",
        ),
        TypedProjectSupportStatus.BLOCKED_INVALID_SPECIFICATION: (
            RegistryStressReadiness.BLOCKED_INVALID_SPECIFICATION,
            "validator.decision.project.blocked_invalid_specification",
        ),
        TypedProjectSupportStatus.BLOCKED_REQUIRED_JOB_VALIDATION: (
            RegistryStressReadiness.BLOCKED_VALIDATION_COVERAGE,
            "validator.decision.project.blocked_required_job_validation",
        ),
        TypedProjectSupportStatus.BLOCKED_SEMANTIC_DRIFT: (
            RegistryStressReadiness.BLOCKED_INVALID_SPECIFICATION,
            "validator.decision.project.blocked_semantic_drift",
        ),
        TypedProjectSupportStatus.BLOCKED_ECP_BINDING: (
            RegistryStressReadiness.BLOCKED_VALIDATION_COVERAGE,
            "validator.decision.project.blocked_ecp_binding",
        ),
    }
    blockers: set[str] = set(project.blocking_rule_ids)
    derivation: set[str] = set()
    if project.status is not TypedProjectSupportStatus.TYPED_PROJECT_SUPPORTED:
        readiness, rule = project_map[project.status]
        derivation.add(rule)
    else:
        derivation.add("validator.decision.project.typed_supported")
        basis = evidence.basis_receipt
        if basis is None:
            readiness = RegistryStressReadiness.PROJECT_CANDIDATE
            derivation.add("validator.decision.basis.not_requested")
        elif basis.state is BasisEvidenceState.VERIFIED:
            readiness = RegistryStressReadiness.PROJECT_CANDIDATE
            derivation.add("validator.decision.basis.verified")
        elif basis.state is BasisEvidenceState.UNKNOWN:
            readiness = RegistryStressReadiness.BLOCKED_UNVERIFIED_SETTING
            blockers.update(basis.reason_rule_ids)
            derivation.add("validator.decision.basis.unknown")
        elif basis.state is BasisEvidenceState.CONFLICT:
            blockers.update(basis.reason_rule_ids)
            if any(item.covered is False for item in basis.elements):
                readiness = RegistryStressReadiness.BLOCKED_MISSING_EVIDENCE
                derivation.add(
                    "validator.decision.basis.element_coverage_conflict"
                )
            else:
                readiness = RegistryStressReadiness.BLOCKED_VALIDATION_COVERAGE
                derivation.add(
                    "validator.decision.basis.definition_conflict"
                )
        elif (
            basis.state is BasisEvidenceState.NOT_APPLICABLE
            and case.program == "xtb"
        ):
            readiness = RegistryStressReadiness.PROJECT_CANDIDATE
            derivation.add("validator.decision.basis.xtb_not_applicable")
        else:
            readiness = RegistryStressReadiness.BLOCKED_VALIDATION_COVERAGE
            blockers.update(basis.reason_rule_ids)
            derivation.add(
                "validator.decision.basis.non_xtb_not_applicable"
            )
    if readiness is RegistryStressReadiness.PROJECT_CANDIDATE:
        blockers.clear()
    body: dict[str, Any] = {
        "schema_version": "chemsmart.overlay-readiness-decision.v1",
        "authority_id": "chemsmart.validator-evidence-readiness",
        "authority_version": "1.0.0",
        "case_id": case.case_id,
        "case_sha256": case.case_sha256,
        "immutable_settings_sha256": canonical_json_sha256(
            case.expected_settings.model_dump(mode="json")
        ),
        "project_receipt_sha256": (
            evidence.project_readiness_receipt.receipt_sha256
        ),
        "basis_receipt_sha256": (
            evidence.basis_receipt.receipt_sha256
            if evidence.basis_receipt is not None
            else None
        ),
        "evidence_ref_sha256s": evidence.evidence_ref_sha256s,
        "readiness": readiness,
        "blocking_rule_ids": tuple(sorted(blockers)),
        "derivation_rule_ids": tuple(sorted(derivation)),
        "scope": "project_candidate_only_no_suitability_or_execution",
        "decision_sha256": "0" * 64,
    }
    body["decision_sha256"] = _contract_sha256(
        body, "decision_sha256"
    )
    return OverlayReadinessDecisionV1.model_validate(body)


def _compact_basis_evidence(
    evidence: v5.ValidatorEvidenceBundleV1,
) -> CompactBasisEvidenceV1 | None:
    receipt = evidence.basis_receipt
    request = evidence.basis_request
    ref = evidence.basis_evidence_ref
    if receipt is None or request is None or ref is None:
        return None
    return CompactBasisEvidenceV1(
        request_sha256=request.request_sha256,
        receipt_sha256=receipt.receipt_sha256,
        evidence_ref_sha256=ref.ref_sha256,
        program=request.program.value,
        basis_literal=request.basis_literal,
        role=request.role.value,
        atomic_numbers=request.atomic_numbers,
        state=receipt.state,
        canonical_basis_name=receipt.canonical_basis_name,
        inspection_status=receipt.inspection_status,
        reason_rule_ids=receipt.reason_rule_ids,
        elements=tuple(
            CompactBasisElementV1(
                atomic_number=item.atomic_number,
                symbol=item.symbol,
                state=item.state,
                covered=item.covered,
                orbital_present=item.orbital_present,
                ecp_present=item.ecp_present,
                ecp_electrons=item.ecp_electrons,
                reason_rule_ids=item.reason_rule_ids,
            )
            for item in receipt.elements
        ),
        evidence_scope=receipt.evidence_scope,
        source_package=receipt.source_package,
        source_version=receipt.source_version,
        scientific_suitability_verified=False,
        native_engine_verified=False,
    )


def _compact_project_evidence(
    evidence: v5.ValidatorEvidenceBundleV1,
) -> CompactProjectEvidenceV1:
    receipt = evidence.project_readiness_receipt
    support = receipt.typed_project_support
    ref = evidence.project_readiness_evidence_ref
    return CompactProjectEvidenceV1(
        request_sha256=receipt.request.request_sha256,
        receipt_sha256=receipt.receipt_sha256,
        evidence_ref_sha256=ref.ref_sha256,
        authority_id=receipt.authority_id,
        authority_version=receipt.authority_version,
        program=receipt.request.program,
        required_job=support.required_job,
        status=support.status,
        blocking_rule_ids=support.blocking_rule_ids,
        finding_rule_ids=support.finding_rule_ids,
        renderer_status=support.renderer_status,
        validation_verdict=support.validation_verdict,
        project_yaml_sha256=support.project_yaml_sha256,
        support_scope=support.support_scope,
        engine_calls=0,
        hpc_calls=0,
        project_writes=0,
        native_input_previews=0,
    )


def build_validator_decision_projection(
    case: RegistryStressCaseV1,
    evidence: v5.ValidatorEvidenceBundleV1,
    decision: OverlayReadinessDecisionV1,
) -> ValidatorDecisionProjectionV1:
    body: dict[str, Any] = {
        "schema_version": "chemsmart.validator-decision-projection.v1",
        "case_id": case.case_id,
        "immutable_settings": case.expected_settings,
        "basis_evidence": _compact_basis_evidence(evidence),
        "project_evidence": _compact_project_evidence(evidence),
        "decision": decision,
        "evidence_ref_sha256s": evidence.evidence_ref_sha256s,
        "projection_sha256": "0" * 64,
    }
    body["projection_sha256"] = _contract_sha256(
        body, "projection_sha256"
    )
    return ValidatorDecisionProjectionV1.model_validate(body)


def build_validator_decision_case(
    repository_root: Path,
    case: RegistryStressCaseV1,
    bundle: v5.v4.LoadedRegistryV2Bundle,
) -> ValidatorDecisionCaseV1:
    preflight = v5.v4.build_case_preflight(case, bundle)
    evidence = v5.build_validator_evidence_bundle(case, preflight)
    decision = derive_overlay_readiness_decision(case, evidence)
    projection = build_validator_decision_projection(
        case, evidence, decision
    )
    body: dict[str, Any] = {
        "schema_version": "chemsmart.validator-decision-case.v1",
        "case_id": case.case_id,
        "case_sha256": case.case_sha256,
        "comparator": load_archived_v5r1_comparator(
            repository_root, case.case_id
        ),
        "evidence": evidence,
        "decision": decision,
        "projection": projection,
        "changed_factor": CHANGED_FACTOR,
        "case_binding_sha256": "0" * 64,
    }
    body["case_binding_sha256"] = _contract_sha256(
        body, "case_binding_sha256"
    )
    return ValidatorDecisionCaseV1.model_validate(body)


def _no_argument_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {},
    }


def _counterexample(
    *,
    rule_id: str,
    failed_field: str,
    expected: Any,
    observed: Any,
    evidence_id: str,
) -> ProposalCounterexampleV1:
    body: dict[str, Any] = {
        "schema_version": "chemsmart.validator-proposal-counterexample.v1",
        "rule_id": rule_id,
        "failed_field": failed_field,
        "expected": expected,
        "observed": observed,
        "evidence_id": evidence_id,
        "counterexample_sha256": "0" * 64,
    }
    body["counterexample_sha256"] = _contract_sha256(
        body, "counterexample_sha256"
    )
    return ProposalCounterexampleV1.model_validate(body)


def _summary_claim_violations(summary: str) -> tuple[str, ...]:
    violations: list[str] = []
    if REQUIRED_EVIDENCE_CEILING_SENTENCE not in summary:
        violations.append("claim.evidence_ceiling.missing")
    if _UNSUPPORTED_POSITIVE_CLAIM.search(summary):
        violations.append("claim.evidence_ceiling.contradicted")
    return tuple(sorted(violations))


def render_authoritative_public_report(
    binding: ValidatorDecisionCaseV1,
) -> str:
    """Render the only claim-bearing English view from typed host facts."""

    findings = _element_findings_from_evidence(binding.evidence)
    element_text = "; ".join(
        (
            f"{item.symbol}: covered={str(item.covered).lower()}, "
            f"orbital_present={str(item.orbital_present).lower()}, "
            f"ecp_present={str(item.ecp_present).lower()}, "
            f"ecp_electrons={item.ecp_electrons if item.ecp_electrons is not None else 'null'}"
        )
        for item in findings
    ) or "not requested"
    blockers = ", ".join(binding.decision.blocking_rule_ids) or "none"
    return (
        f"Case {binding.case_id}. Host-derived readiness: "
        f"{binding.decision.readiness.value}. Blocking rule IDs: {blockers}. "
        f"Request-bound element facts: {element_text}. This is a "
        "non-executing typed-project readiness record. "
        f"{REQUIRED_EVIDENCE_CEILING_SENTENCE}"
    )


def _submit_result(
    *,
    accepted: bool,
    status: Literal[
        "accepted", "observation_required", "repair_required", "blocked"
    ],
    decision_sha256: str,
    observation_sha256: str | None,
    counterexamples: Sequence[ProposalCounterexampleV1] = (),
    proposal: v5.RegistryValidatorOverlayProposalV1 | None = None,
    repairs_used: int = 0,
    repairs_remaining: int = MAX_REPAIRS,
) -> ValidatorDecisionSubmitResultV1:
    body: dict[str, Any] = {
        "schema_version": "chemsmart.validator-decision-submit-result.v1",
        "accepted": accepted,
        "status": status,
        "verdict": "ok" if accepted else "reject",
        "proposal": proposal,
        "counterexamples": tuple(counterexamples),
        "repairs_used": repairs_used,
        "repairs_remaining": repairs_remaining,
        "decision_sha256": decision_sha256,
        "observation_sha256": observation_sha256,
        "result_sha256": "0" * 64,
    }
    body["result_sha256"] = _contract_sha256(body, "result_sha256")
    return ValidatorDecisionSubmitResultV1.model_validate(body)


def build_validator_decision_registry(
    case_binding: ValidatorDecisionCaseV1,
) -> ToolRegistry:
    """Build a two-tool, compact, case-bound CEGIS surface."""

    projection = case_binding.projection
    decision = case_binding.decision
    observation_body: dict[str, Any] = {
        "schema_version": "chemsmart.validator-decision-observation.v1",
        "observation_receipt_id": (
            f"observation:validator-decision:{secrets.token_hex(16)}"
        ),
        "projection_sha256": projection.projection_sha256,
        "decision_sha256": decision.decision_sha256,
        "evidence_ref_sha256s": decision.evidence_ref_sha256s,
        "observation_sha256": "0" * 64,
    }
    observation_body["observation_sha256"] = _contract_sha256(
        observation_body, "observation_sha256"
    )
    observation = ValidatorDecisionObservationReceiptV1.model_validate(
        observation_body
    )
    observed = False
    invalid_drafts: list[ValidatorDecisionDraftV1] = []
    invalid_digests: set[str] = set()
    prior_failed_fields: set[str] = set()

    def inspect_case_validator_decision() -> dict[str, Any]:
        nonlocal observed
        observed = True
        return {
            "projection": projection.model_dump(mode="json"),
            "observation_receipt": observation.model_dump(mode="json"),
            "evidence_ceiling": {
                "scientific_suitability_verified": False,
                "safe_preview_executed": False,
                "engine_acceptance_verified": False,
                "execution_authorized": False,
            },
        }

    expected_findings = _element_findings_from_evidence(
        case_binding.evidence
    )

    def submit_validator_decision_plan(
        readiness: str,
        element_findings: list[dict[str, Any]],
        decision_sha256: str,
        analysis_summary: str,
    ) -> dict[str, Any]:
        draft = ValidatorDecisionDraftV1.model_validate(
            {
                "readiness": readiness,
                "element_findings": element_findings,
                "decision_sha256": decision_sha256,
                "analysis_summary": analysis_summary,
            }
        )
        if not observed:
            return _submit_result(
                accepted=False,
                status="observation_required",
                decision_sha256=decision.decision_sha256,
                observation_sha256=None,
            ).model_dump(mode="json")
        draft_digest = canonical_json_sha256(draft.model_dump(mode="json"))
        if draft_digest in invalid_digests:
            repeated = _counterexample(
                rule_id="validator.repair.repeated_candidate",
                failed_field="draft",
                expected="a field-local revision",
                observed="identical rejected candidate",
                evidence_id=observation.observation_receipt_id,
            )
            return _submit_result(
                accepted=False,
                status="blocked",
                decision_sha256=decision.decision_sha256,
                observation_sha256=observation.observation_sha256,
                counterexamples=(repeated,),
                repairs_used=min(len(invalid_drafts), MAX_REPAIRS),
                repairs_remaining=0,
            ).model_dump(mode="json")
        current = draft.model_dump(mode="json")
        if invalid_drafts:
            previous = invalid_drafts[-1].model_dump(mode="json")
            changed = {
                field
                for field in ("readiness", "element_findings", "decision_sha256")
                if previous[field] != current[field]
            }
            unrelated = changed - prior_failed_fields
            if unrelated:
                finding = _counterexample(
                    rule_id="validator.repair.unrelated_field_mutation",
                    failed_field="repair",
                    expected=sorted(prior_failed_fields),
                    observed=sorted(unrelated),
                    evidence_id=observation.observation_receipt_id,
                )
                return _submit_result(
                    accepted=False,
                    status="blocked",
                    decision_sha256=decision.decision_sha256,
                    observation_sha256=observation.observation_sha256,
                    counterexamples=(finding,),
                    repairs_used=min(len(invalid_drafts), MAX_REPAIRS),
                    repairs_remaining=0,
                ).model_dump(mode="json")
        findings: list[ProposalCounterexampleV1] = []
        if draft.readiness is not decision.readiness:
            findings.append(
                _counterexample(
                    rule_id="validator.proposal.readiness_mismatch",
                    failed_field="readiness",
                    expected=decision.readiness.value,
                    observed=draft.readiness.value,
                    evidence_id=decision.decision_sha256,
                )
            )
        if draft.element_findings != expected_findings:
            findings.append(
                _counterexample(
                    rule_id="validator.proposal.element_findings_mismatch",
                    failed_field="element_findings",
                    expected=[
                        item.model_dump(mode="json")
                        for item in expected_findings
                    ],
                    observed=[
                        item.model_dump(mode="json")
                        for item in draft.element_findings
                    ],
                    evidence_id=decision.decision_sha256,
                )
            )
        if draft.decision_sha256 != decision.decision_sha256:
            findings.append(
                _counterexample(
                    rule_id="validator.proposal.decision_binding_mismatch",
                    failed_field="decision_sha256",
                    expected=decision.decision_sha256,
                    observed=draft.decision_sha256,
                    evidence_id=observation.observation_receipt_id,
                )
            )
        summary_violations = _summary_claim_violations(
            draft.analysis_summary
        )
        if summary_violations:
            findings.append(
                _counterexample(
                    rule_id="validator.proposal.analysis_claim_unsupported",
                    failed_field="analysis_summary",
                    expected=REQUIRED_EVIDENCE_CEILING_SENTENCE,
                    observed=list(summary_violations),
                    evidence_id=decision.decision_sha256,
                )
            )
        if findings:
            invalid_drafts.append(draft)
            invalid_digests.add(draft_digest)
            prior_failed_fields.clear()
            prior_failed_fields.update(item.failed_field for item in findings)
            invalid_count = len(invalid_drafts)
            repairs_used = max(invalid_count - 1, 0)
            blocked = invalid_count > MAX_REPAIRS
            return _submit_result(
                accepted=False,
                status="blocked" if blocked else "repair_required",
                decision_sha256=decision.decision_sha256,
                observation_sha256=observation.observation_sha256,
                counterexamples=findings,
                repairs_used=min(repairs_used, MAX_REPAIRS),
                repairs_remaining=(
                    0 if blocked else MAX_REPAIRS - repairs_used
                ),
            ).model_dump(mode="json")
        proposal = v5.RegistryValidatorOverlayProposalV1(
            case_id=case_binding.case_id,
            program=_case(case_binding.case_id).program,
            project_name=f"validator-{case_binding.case_id}",
            readiness=decision.readiness,
            settings=projection.immutable_settings,
            blocking_rule_ids=decision.blocking_rule_ids,
            element_findings=expected_findings,
            analysis_summary=render_authoritative_public_report(case_binding),
            native_input_authored=False,
            command_authored=False,
            project_written=False,
            execution_requested=False,
            evidence_ref_sha256s=decision.evidence_ref_sha256s,
        )
        return _submit_result(
            accepted=True,
            status="accepted",
            decision_sha256=decision.decision_sha256,
            observation_sha256=observation.observation_sha256,
            proposal=proposal,
            repairs_used=min(len(invalid_drafts), MAX_REPAIRS),
            repairs_remaining=max(MAX_REPAIRS - len(invalid_drafts), 0),
        ).model_dump(mode="json")

    draft_schema = ValidatorDecisionDraftV1.model_json_schema()
    specs = (
        build_tool_spec(
            inspect_case_validator_decision,
            registered_name="inspect_case_validator_decision",
            description=(
                "Return one compact host-derived validator decision and one "
                "unpredictable causal observation receipt. No arguments."
            ),
            input_json_schema=_no_argument_schema(),
            metadata=v5.v4._read_only_metadata(
                "Inspect compact validator decision"
            ),
        ),
        build_tool_spec(
            submit_validator_decision_plan,
            registered_name="submit_validator_decision_plan",
            description=(
                "Acknowledge the exact decision and element facts. Rejected "
                "fields may be repaired from structured counterexamples."
            ),
            input_json_schema=draft_schema,
            metadata=v5.v4._read_only_metadata(
                "Submit validator decision acknowledgement"
            ),
        ),
    )
    return ToolRegistry(specs)


def _tool_profile(registry: ToolRegistry) -> PhaseToolProfile:
    names = tuple(tool.name for tool in registry.list_tools())
    return PhaseToolProfile(
        {TaskPhase.SYNTHESIS: names},
        specialist_tools=names,
        required_completion_tools={
            TaskPhase.SYNTHESIS: ("submit_validator_decision_plan",),
        },
        trusted_initial_phase=TaskPhase.SYNTHESIS,
    )


def render_prompt(case: RegistryStressCaseV1) -> str:
    return f"""You are the scientific acknowledgement agent in a controlled
ChemSmart V5r2 composite engineering-recovery experiment.

Case ID: {case.case_id}
Program: {case.program}
Original task text (immutable):
{case.request_text}

Call inspect_case_validator_decision with no arguments. Treat its compact,
host-derived projection as authoritative for this experiment. Then call
submit_validator_decision_plan with exactly the returned readiness, element
facts, and decision_sha256 plus a concise English evidence-bounded summary.
If the submit result is repair_required, change only the failed fields named by
its counterexamples and retry. Do not sort or normalize scientific literals,
infer an absent ECP intent, select readiness, author native input or commands,
write projects, or request chemistry-engine/HPC execution. Finish only after
one submit result has accepted=true and verdict=ok. Include this exact sentence
in the submitted analysis_summary and final answer:
{REQUIRED_EVIDENCE_CEILING_SENTENCE}"""


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
            "trusted_initial_phase": TaskPhase.SYNTHESIS.value,
            "required_completion_tool": "submit_validator_decision_plan",
            "max_repairs": MAX_REPAIRS,
            "native_input_authoring": False,
            "chemistry_engine_execution": False,
            "hpc_execution": False,
        }
    )


def prepare_campaign(
    *,
    repository_root: Path,
    bundle: v5.v4.LoadedRegistryV2Bundle,
    source_binding: v5.RepositorySourceBindingV1,
    network_budget_sha256: str,
    case_ids: Sequence[str] = SELECTED_CASE_IDS,
) -> ValidatorDecisionCampaignPlanV1:
    """Preregister V5r2 without network or credential access."""

    selected = tuple(case_ids)
    if selected != tuple(sorted(set(selected))):
        raise ValueError("V5r2 case IDs must be unique and sorted")
    registry_binding = v5.v4.build_registry_evidence_binding(bundle)
    cases = tuple(
        build_validator_decision_case(
            repository_root, _case(case_id), bundle
        )
        for case_id in selected
    )
    runs: list[ValidatorDecisionRunSpecV1] = []
    for binding in cases:
        case = _case(binding.case_id)
        registry = build_validator_decision_registry(binding)
        prompt = render_prompt(case)
        body: dict[str, Any] = {
            "schema_version": "chemsmart.validator-decision-run.v1",
            "run_id": f"run:{case.case_id}:validator_decision:{RUN_REVISION}",
            "hypothesis_id": (
                f"hypothesis:{case.case_id}:validator_decision:{RUN_REVISION}"
            ),
            "case_id": case.case_id,
            "case_sha256": case.case_sha256,
            "case_binding_sha256": binding.case_binding_sha256,
            "comparator_sha256": binding.comparator.comparator_sha256,
            "evidence_bundle_sha256": (
                binding.evidence.evidence_bundle_sha256
            ),
            "decision_sha256": binding.decision.decision_sha256,
            "projection_sha256": binding.projection.projection_sha256,
            "source_binding_sha256": source_binding.binding_sha256,
            "registry_binding_sha256": registry_binding.binding_sha256,
            "prompt_sha256": content_sha256(prompt.encode("utf-8")),
            "tool_schema_sha256": canonical_json_sha256(
                v5.v4.model_visible_tool_defs(registry)
            ),
            "configuration_sha256": _configuration_sha256(),
            "network_budget_sha256": network_budget_sha256,
            "changed_factor": CHANGED_FACTOR,
            "comparator_source": "archived_v5r1_failed_outcome",
            "duplicate_comparator_api_calls": 0,
            "model": MODEL,
            "reasoning_mode": "thinking_enabled_high",
            "runtime": "agent_session_runtime_v2_active",
            "prompt_version": PROMPT_VERSION,
            "expected_outcome": (
                "The compact decision is causally inspected, exactly one "
                "accepted acknowledgement preserves its receipt-derived "
                "readiness and element facts, and Runtime V2 completes only "
                "on the green submit receipt."
            ),
            "run_spec_sha256": "0" * 64,
        }
        body["run_spec_sha256"] = _contract_sha256(
            body, "run_spec_sha256"
        )
        runs.append(ValidatorDecisionRunSpecV1.model_validate(body))
    plan_body: dict[str, Any] = {
        "schema_version": "chemsmart.validator-decision-campaign.v1",
        "campaign_id": CAMPAIGN_ID,
        "source_binding": source_binding,
        "registry_binding": registry_binding,
        "network_budget_sha256": network_budget_sha256,
        "cases": cases,
        "runs": tuple(runs),
        "live_run_count": len(runs),
        "duplicate_comparator_api_calls": 0,
        "chemistry_engine_calls": 0,
        "hpc_calls": 0,
        "project_writes": 0,
        "native_inputs_authored": 0,
        "campaign_plan_sha256": "0" * 64,
    }
    plan_body["campaign_plan_sha256"] = _contract_sha256(
        plan_body, "campaign_plan_sha256"
    )
    return ValidatorDecisionCampaignPlanV1.model_validate(plan_body)


def submitted_proposal_from_outcomes(
    outcomes: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any] | None, int, int, str | None]:
    submissions = [
        item
        for item in outcomes
        if item.get("name") == "submit_validator_decision_plan"
        and isinstance(item.get("result"), Mapping)
    ]
    accepted = [
        item
        for item in submissions
        if item["result"].get("accepted") is True
        and item["result"].get("status") == "accepted"
        and item["result"].get("verdict") == "ok"
        and isinstance(item["result"].get("proposal"), Mapping)
    ]
    rejected = len(submissions) - len(accepted)
    if len(accepted) != 1:
        return None, len(accepted), rejected, None
    result = accepted[0]["result"]
    observation_sha256 = result.get("observation_sha256")
    return (
        dict(result["proposal"]),
        1,
        rejected,
        str(observation_sha256) if observation_sha256 else None,
    )


def cegis_attempt_receipts(
    requests: Sequence[Mapping[str, Any]],
    outcomes: Sequence[Mapping[str, Any]],
) -> tuple[CegisAttemptReceiptV1, ...]:
    by_request = {
        str(item.get("request_id")): item
        for item in requests
        if item.get("name") == "submit_validator_decision_plan"
    }
    attempts: list[CegisAttemptReceiptV1] = []
    for outcome in outcomes:
        if outcome.get("name") != "submit_validator_decision_plan":
            continue
        result = outcome.get("result")
        request_id = str(outcome.get("request_id") or "")
        request = by_request.get(request_id)
        if not isinstance(result, Mapping) or request is None:
            continue
        counterexamples = result.get("counterexamples")
        if not isinstance(counterexamples, list):
            counterexamples = []
        attempts.append(
            CegisAttemptReceiptV1(
                ordinal=len(attempts) + 1,
                request_id=request_id,
                arguments_sha256=str(request["arguments_sha256"]),
                accepted=result.get("accepted") is True,
                status=str(result["status"]),
                verdict=str(result["verdict"]),
                result_sha256=str(result["result_sha256"]),
                counterexample_sha256s=tuple(
                    sorted(
                        str(item["counterexample_sha256"])
                        for item in counterexamples
                        if isinstance(item, Mapping)
                    )
                ),
            )
        )
    return tuple(attempts)


def grade_validator_decision_proposal(
    binding: ValidatorDecisionCaseV1,
    proposal_payload: dict[str, Any] | None,
    *,
    canonical_public_text: str,
    model_public_text: str,
    observed_model: str | None,
    successful_submit_count: int,
    rejected_submit_count: int,
    accepted_observation_sha256: str | None,
    tool_outcomes: Sequence[Mapping[str, Any]],
) -> ValidatorDecisionGradeV1:
    passed: set[str] = set()
    failed: set[str] = set()

    def check(name: str, observed: Any, expected: Any) -> None:
        (passed if observed == expected else failed).add(name)

    check(
        "oracle.typed-proposal-exactly-one",
        successful_submit_count,
        1,
    )
    proposal = None
    if proposal_payload is not None:
        try:
            proposal = v5.RegistryValidatorOverlayProposalV1.model_validate(
                proposal_payload
            )
            passed.add("oracle.typed-proposal-valid")
        except Exception:
            failed.add("oracle.typed-proposal-valid")
    else:
        failed.add("oracle.typed-proposal-valid")
    expected_findings = _element_findings_from_evidence(binding.evidence)
    expected_report = render_authoritative_public_report(binding)
    if proposal is not None:
        check("oracle.case-identity", proposal.case_id, binding.case_id)
        check(
            "oracle.program-identity",
            proposal.program,
            _case(binding.case_id).program,
        )
        check(
            "oracle.host-setting-preservation",
            proposal.settings,
            binding.projection.immutable_settings,
        )
        check(
            "oracle.receipt-derived-readiness",
            proposal.readiness,
            binding.decision.readiness,
        )
        check(
            "oracle.receipt-derived-blockers",
            proposal.blocking_rule_ids,
            binding.decision.blocking_rule_ids,
        )
        check(
            "oracle.receipt-derived-element-findings",
            proposal.element_findings,
            expected_findings,
        )
        check(
            "oracle.evidence-ref-binding",
            proposal.evidence_ref_sha256s,
            binding.decision.evidence_ref_sha256s,
        )
        check(
            "oracle.execution-prohibited",
            (
                proposal.native_input_authored,
                proposal.command_authored,
                proposal.project_written,
                proposal.execution_requested,
            ),
            (False, False, False, False),
        )
        check(
            "oracle.typed-summary-evidence-bounded",
            proposal.analysis_summary,
            expected_report,
        )
    native_or_shell = any(
        bool(v5.v4._NATIVE_TEXT.search(text))
        or bool(v5.v4._SHELL_TEXT.search(text))
        for text in (canonical_public_text, model_public_text)
    )
    check("oracle.public-output-safe", native_or_shell, False)
    check(
        "oracle.public-claim-evidence-bounded",
        canonical_public_text,
        expected_report,
    )
    check("oracle.observed-model-identity", observed_model, MODEL)

    inspect_indices: list[int] = []
    observed_receipts: list[str] = []
    accepted_indices: list[int] = []
    latest_submit_verdict = None
    for index, item in enumerate(tool_outcomes):
        name = item.get("name")
        result = item.get("result")
        if name == "inspect_case_validator_decision" and isinstance(
            result, Mapping
        ):
            receipt = result.get("observation_receipt")
            if isinstance(receipt, Mapping) and isinstance(
                receipt.get("observation_sha256"), str
            ):
                inspect_indices.append(index)
                observed_receipts.append(str(receipt["observation_sha256"]))
        if name == "submit_validator_decision_plan" and isinstance(
            result, Mapping
        ):
            latest_submit_verdict = result.get("verdict")
            if result.get("accepted") is True:
                accepted_indices.append(index)
    causal = (
        len(observed_receipts) == 1
        and len(accepted_indices) == 1
        and inspect_indices[0] < accepted_indices[0]
        and accepted_observation_sha256 == observed_receipts[0]
    )
    check("oracle.causal-decision-observation", causal, True)
    check("oracle.required-green-submit", latest_submit_verdict, "ok")

    details = {
        "receipt_derived_readiness": binding.decision.readiness.value,
        "receipt_derived_blocking_rule_ids": list(
            binding.decision.blocking_rule_ids
        ),
        "decision_sha256": binding.decision.decision_sha256,
        "projection_sha256": binding.projection.projection_sha256,
        "comparator_terminal_state": binding.comparator.terminal_state,
        "comparator_failed_oracle_ids": list(
            binding.comparator.failed_oracle_ids
        ),
        "rejected_submit_count": rejected_submit_count,
        "model_output_authoritative": False,
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
    return ValidatorDecisionGradeV1.model_validate(body)


def _provider_observation_binding(
    *,
    locator: str,
    observations: Sequence[Mapping[str, Any]],
    artifact_bytes: bytes,
) -> ProviderObservationBindingV1:
    return ProviderObservationBindingV1(
        artifact_locator=locator,
        artifact_sha256=content_sha256(artifact_bytes),
        observation_count=len(observations),
        observations_sha256=canonical_json_sha256(list(observations)),
    )


def _read_bound_artifact(root: Path, locator: str) -> bytes:
    relative = Path(locator)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.as_posix() != locator
        or _SAFE_LOCATOR.fullmatch(locator) is None
    ):
        raise ValueError("campaign artifact locator is unsafe")
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError("campaign artifact is absent or symbolic")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("campaign artifact escapes its evidence root")
    return path.read_bytes()


def seal_private_campaign_evidence(
    *,
    run_root: Path,
    campaign_plan_sha256: str,
    source_binding_sha256: str,
    secret_values: Sequence[str],
) -> tuple[
    ValidatorDecisionPrivateReceiptV1,
    EvidenceArtifactManifestV2,
    bytes,
    bytes,
]:
    """Scan and exact-byte seal non-public Runtime V2 session artifacts."""

    for path in sorted(run_root.rglob("*")):
        if path.is_symlink():
            raise ValueError("private campaign evidence contains a symlink")
        if not path.is_file():
            continue
        payload = path.read_bytes()
        if any(secret.encode("utf-8") in payload for secret in secret_values):
            raise RuntimeError("secret material entered private campaign evidence")
        try:
            text = payload.decode("utf-8", "strict")
        except UnicodeDecodeError:
            continue
        lowered = text.casefold()
        if any(
            marker in lowered
            for marker in ('"reasoning_content"', "<think", "</think>")
        ):
            raise RuntimeError("private reasoning marker entered evidence")
        values: list[Any] = []
        try:
            if path.suffix == ".jsonl":
                values.extend(
                    json.loads(line)
                    for line in text.splitlines()
                    if line.strip()
                )
            elif path.suffix == ".json":
                values.append(json.loads(text))
        except json.JSONDecodeError as exc:
            raise ValueError("private JSON evidence is malformed") from exc
        if v5.v4._contains_private_reasoning(values):
            raise RuntimeError("private reasoning entered persisted evidence")
    manifest = build_evidence_artifact_manifest_v2(
        run_root,
        manifest_id=f"{CAMPAIGN_ID}:private",
        scope="private",
        excluded_locators=(
            "artifact-manifest.json",
            "campaign-receipt.json",
        ),
    )
    manifest_bytes = manifest_v2_json_bytes(manifest)
    v5.v4._write_atomic(run_root / "artifact-manifest.json", manifest_bytes)
    body: dict[str, Any] = {
        "schema_version": (
            "chemsmart.validator-decision-private-receipt.v1"
        ),
        "campaign_id": CAMPAIGN_ID,
        "campaign_plan_sha256": campaign_plan_sha256,
        "source_binding_sha256": source_binding_sha256,
        "private_manifest_sha256": manifest.manifest_sha256,
        "private_manifest_artifact_sha256": content_sha256(manifest_bytes),
        "private_artifact_count": manifest.artifact_count,
        "private_total_bytes": manifest.total_bytes,
        "secret_material_persisted": False,
        "private_reasoning_persisted": False,
        "receipt_sha256": "0" * 64,
    }
    body["receipt_sha256"] = _contract_sha256(body, "receipt_sha256")
    receipt = ValidatorDecisionPrivateReceiptV1.model_validate(body)
    receipt_bytes = v5.v4._json_bytes(receipt.model_dump(mode="json"))
    v5.v4._write_atomic(run_root / "campaign-receipt.json", receipt_bytes)
    persisted = ValidatorDecisionPrivateReceiptV1.model_validate(
        _json_file(run_root / "campaign-receipt.json")
    )
    if persisted != receipt:
        raise ValueError("private campaign receipt does not replay")
    verify_evidence_artifact_manifest_v2(run_root, manifest)
    return receipt, manifest, receipt_bytes, manifest_bytes


def verify_persisted_campaign_artifacts(
    *,
    output_dir: Path,
    expected_plan: ValidatorDecisionCampaignPlanV1,
    expected_run_receipt: ValidatorDecisionRunReceiptV1,
    manifest: EvidenceArtifactManifestV2,
) -> dict[str, int | bool]:
    """Replay exact bytes and semantic links before sealing the envelope."""

    if manifest.excluded_locators != (
        "artifact-manifest.json",
        "campaign-receipt.json",
    ):
        raise ValueError("public manifest has an unexpected exclusion set")
    verify_evidence_artifact_manifest_v2(output_dir, manifest)
    manifest_by_locator = {
        item.locator: item for item in manifest.artifacts
    }
    plan_bytes = _read_bound_artifact(output_dir, "campaign-plan.json")
    plan_record = ValidatorDecisionCampaignPlanV1.model_validate(
        json.loads(plan_bytes)
    )
    if plan_record != expected_plan:
        raise ValueError("persisted campaign plan does not replay")
    run_receipt_bytes = _read_bound_artifact(
        output_dir, "campaign-run-receipt.json"
    )
    run_receipt = ValidatorDecisionRunReceiptV1.model_validate(
        json.loads(run_receipt_bytes)
    )
    if run_receipt != expected_run_receipt:
        raise ValueError("persisted run receipt does not replay")
    if (
        run_receipt.campaign_plan_artifact_sha256
        != content_sha256(plan_bytes)
    ):
        raise ValueError("run receipt lost campaign-plan byte binding")
    planned_runs = {item.run_id: item for item in plan_record.runs}
    planned_cases = {item.case_id: item for item in plan_record.cases}
    replayed = 0
    strict_passes = 0
    for artifact in run_receipt.outcome_artifacts:
        locator = str(artifact["locator"])
        outcome_bytes = _read_bound_artifact(output_dir, locator)
        if (
            content_sha256(outcome_bytes) != artifact["artifact_sha256"]
            or len(outcome_bytes) != artifact["size_bytes"]
        ):
            raise ValueError("outer outcome exact-byte binding failed")
        manifested = manifest_by_locator.get(locator)
        if (
            manifested is None
            or manifested.artifact_sha256 != artifact["artifact_sha256"]
            or manifested.size_bytes != artifact["size_bytes"]
        ):
            raise ValueError("outer outcome is not manifest-bound")
        outer = json.loads(outcome_bytes)
        run = ValidatorDecisionRunSpecV1.model_validate(outer["run_spec"])
        comparator = ArchivedV5r1ComparatorV1.model_validate(
            outer["comparator"]
        )
        outcome = ValidatorDecisionOutcomeV1.model_validate(outer["outcome"])
        if planned_runs.get(run.run_id) != run:
            raise ValueError("outer outcome run differs from campaign plan")
        binding = planned_cases.get(run.case_id)
        if binding is None or binding.comparator != comparator:
            raise ValueError("outer outcome comparator differs from plan")
        if (
            outcome.run_spec_sha256 != run.run_spec_sha256
            or outcome.comparator_sha256 != comparator.comparator_sha256
            or outcome.decision_sha256 != binding.decision.decision_sha256
            or outcome.projection_sha256
            != binding.projection.projection_sha256
        ):
            raise ValueError("outer outcome lost preregistration binding")

        response_bytes = _read_bound_artifact(
            output_dir, outcome.response_artifact_locator
        )
        trace_bytes = _read_bound_artifact(
            output_dir, outcome.tool_trace_artifact_locator
        )
        provider_bytes = _read_bound_artifact(
            output_dir, outcome.provider_observations.artifact_locator
        )
        event_bytes = _read_bound_artifact(
            output_dir, outcome.runtime_event_log_locator
        )
        projection_bytes = _read_bound_artifact(
            output_dir,
            outcome.runtime_event_projection_receipt_locator,
        )
        if content_sha256(response_bytes) != outcome.response_artifact_sha256:
            raise ValueError("response artifact digest mismatch")
        if content_sha256(trace_bytes) != outcome.tool_trace_artifact_sha256:
            raise ValueError("tool-trace artifact digest mismatch")
        if (
            content_sha256(provider_bytes)
            != outcome.provider_observations.artifact_sha256
        ):
            raise ValueError("provider-observation artifact digest mismatch")
        if content_sha256(event_bytes) != outcome.runtime_event_log_sha256:
            raise ValueError("public Runtime V2 artifact digest mismatch")
        if (
            content_sha256(projection_bytes)
            != outcome.runtime_event_projection_receipt_artifact_sha256
        ):
            raise ValueError("projection-receipt artifact digest mismatch")

        response_record = json.loads(response_bytes)
        trace_record = json.loads(trace_bytes)
        observations = json.loads(provider_bytes)
        projection_receipt = PublicEventProjectionReceiptV1.model_validate(
            json.loads(projection_bytes)
        )
        if (
            response_record.get("run_id") != run.run_id
            or trace_record.get("run_id") != run.run_id
            or response_record.get("canonical_public_english_report")
            != outcome.canonical_public_english_report
            or response_record.get("model_public_english_response")
            != outcome.model_public_english_response
            or response_record.get("model_output_authoritative") is not False
            or response_record.get("deterministic_grade")
            != outcome.deterministic_grade.model_dump(mode="json")
            or projection_receipt != outcome.runtime_event_projection_receipt
        ):
            raise ValueError("referenced artifact semantics differ from outcome")
        if not isinstance(observations, list) or any(
            not isinstance(item, dict) for item in observations
        ):
            raise ValueError("provider observations are not a JSON-object list")
        ordinals = tuple(item.get("attempt_ordinal") for item in observations)
        if ordinals and ordinals != tuple(range(1, len(ordinals) + 1)):
            raise ValueError("provider observation ordinals are not canonical")
        if (
            len(observations)
            != outcome.provider_observations.observation_count
            or canonical_json_sha256(observations)
            != outcome.provider_observations.observations_sha256
        ):
            raise ValueError("provider observation semantics do not replay")

        event_path = output_dir / outcome.runtime_event_log_locator
        events = v5.v4.RuntimeEventStore(event_path).load()
        state = v5.v4.reduce_events(events)
        if canonical_json_sha256(state.model_dump(mode="json")) != (
            outcome.runtime_replay_state_sha256
        ):
            raise ValueError("public Runtime V2 state does not replay")
        terminal_events = [
            event
            for event in events
            if event.kind.value
            in {"turn_completed", "turn_blocked", "turn_failed"}
        ]
        if len(terminal_events) != 1:
            raise ValueError("public Runtime V2 terminal is not unique")
        replayed_terminal = {
            "turn_completed": "complete",
            "turn_blocked": "blocked",
            "turn_failed": "failed",
        }[terminal_events[0].kind.value]
        if replayed_terminal != outcome.runtime_terminal_state:
            raise ValueError("public Runtime V2 terminal does not replay")

        tool_outcomes = trace_record.get("tool_outcomes")
        tool_requests = trace_record.get("tool_requests")
        if not isinstance(tool_outcomes, list) or not isinstance(
            tool_requests, list
        ):
            raise ValueError("tool-trace outcomes are absent")
        if cegis_attempt_receipts(tool_requests, tool_outcomes) != (
            outcome.cegis_attempts
        ):
            raise ValueError("CEGIS lineage does not replay from tool trace")
        proposal, successful, rejected, observation_sha256 = (
            submitted_proposal_from_outcomes(tool_outcomes)
        )
        replayed_grade = grade_validator_decision_proposal(
            binding,
            proposal,
            canonical_public_text=outcome.canonical_public_english_report,
            model_public_text=outcome.model_public_english_response,
            observed_model=outcome.observed_model,
            successful_submit_count=successful,
            rejected_submit_count=rejected,
            accepted_observation_sha256=observation_sha256,
            tool_outcomes=tool_outcomes,
        )
        if replayed_grade != outcome.deterministic_grade:
            raise ValueError("deterministic grade does not replay")
        replayed += 1
        strict_passes += int(
            replayed_grade.oracle_passed
            and outcome.runtime_terminal_state == "complete"
        )
    if replayed != run_receipt.live_run_count:
        raise ValueError("not every run receipt outcome replayed")
    if strict_passes != run_receipt.strict_pass_count:
        raise ValueError("strict-pass count does not replay")
    return {
        "semantic_replay_verified": True,
        "replayed_outcome_count": replayed,
        "replayed_response_count": replayed,
        "replayed_tool_trace_count": replayed,
        "replayed_provider_observation_count": replayed,
        "replayed_runtime_event_count": replayed,
        "strict_pass_count": strict_passes,
    }


def run_campaign(
    *,
    repository_root: Path,
    api_env: Path,
    run_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Run five active V5r2 arms without rerunning their comparators."""

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
    source = v5.v4.capture_repository_binding(repository_root)
    bundle = v5.v4.load_registry_v2_bundle(repository_root)
    plan = prepare_campaign(
        repository_root=repository_root,
        bundle=bundle,
        source_binding=source,
        network_budget_sha256=network_budget.budget_sha256,
    )
    v5.v4.assert_repository_binding_current(repository_root, source)
    v5.v4.assert_transport_source_ready(repository_root, source)
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
                        run.decision_sha256,
                        run.projection_sha256,
                        run.prompt_sha256,
                        run.tool_schema_sha256,
                        run.configuration_sha256,
                        run.network_budget_sha256,
                    }
                )
            ),
        )
        for run in plan.runs
    }
    run_root.mkdir(mode=0o700, parents=True)
    output_dir.mkdir(parents=True)
    for name in (
        "responses",
        "tool-traces",
        "provider-observations",
        "runtime-events",
        "outcomes",
    ):
        (output_dir / name).mkdir()
    plan_bytes = v5.v4._json_bytes(plan.model_dump(mode="json"))
    v5.v4._write_atomic(output_dir / "campaign-plan.json", plan_bytes)

    environment = v5.v4._credential_environment(api_env)
    secret_values = tuple(environment.values())
    controller = CredentialAccessController(
        keychain_reader=lambda _service, _account: None,
        environment=environment,
        permit_ttl_seconds=120,
    )
    outcomes: list[dict[str, Any]] = []
    outer_artifacts: list[dict[str, Any]] = []
    try:
        for run in plan.runs:
            v5.v4.assert_repository_binding_current(repository_root, source)
            binding = case_bindings[run.case_id]
            case = _case(run.case_id)
            registry = build_validator_decision_registry(binding)
            prompt = render_prompt(case)
            if content_sha256(prompt.encode("utf-8")) != run.prompt_sha256:
                raise RuntimeError("prompt changed after preregistration")
            tool_schema = v5.v4.model_visible_tool_defs(registry)
            if canonical_json_sha256(tool_schema) != run.tool_schema_sha256:
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
                tool_profile=_tool_profile(registry),
                training_capture=False,
                behavior_rules_text=(
                    "Read-only V5r2 compact validator-decision experiment. "
                    "No projects, native inputs, commands, engines, or HPC."
                ),
            )
            started = time.perf_counter()
            result = session.run_loop(
                prompt,
                budgets=ToolLoopBudgets(
                    max_model_steps_per_turn=None,
                    max_total_tool_calls_per_turn=8,
                    max_consecutive_tool_errors=3,
                    max_same_signature_retries=1,
                    max_provider_errors_per_turn=1,
                    provider_timeout_s=180,
                    max_wall_time_s=420,
                    max_request_input_tokens=32_000,
                    max_request_output_tokens=MAX_OUTPUT_TOKENS,
                    log_provider_turn_raw=False,
                ),
                log_raw_provider_turns=False,
                policy=PermissionPolicy(mode=RuntimePermissionMode.READ_ONLY),
            )
            wall_time_ms = int((time.perf_counter() - started) * 1000)
            requests, tool_outcomes = v5.v4._tool_observations(result)
            cegis_attempts = cegis_attempt_receipts(requests, tool_outcomes)
            proposal, successful_count, rejected_count, observation_sha256 = (
                submitted_proposal_from_outcomes(tool_outcomes)
            )
            _, assistant_text, _ = v5.v4._public_english_response(
                result=result,
                proposal_payload=None,
            )
            model_public_text = assistant_text
            canonical_public_text = render_authoritative_public_report(binding)
            proposal_summary = (
                str(proposal.get("analysis_summary") or "")
                if proposal is not None
                else ""
            )
            grade = grade_validator_decision_proposal(
                binding,
                proposal,
                canonical_public_text=canonical_public_text,
                model_public_text=model_public_text,
                observed_model=provider.observed_model_id or None,
                successful_submit_count=successful_count,
                rejected_submit_count=rejected_count,
                accepted_observation_sha256=observation_sha256,
                tool_outcomes=tool_outcomes,
            )
            response_record = {
                "run_id": run.run_id,
                "canonical_public_english_report": canonical_public_text,
                "model_public_english_response": model_public_text,
                "model_output_authoritative": False,
                "typed_analysis_summary": proposal_summary,
                "typed_proposal": proposal,
                "deterministic_grade": grade.model_dump(mode="json"),
                "private_reasoning_included": False,
            }
            trace_record = {
                "run_id": run.run_id,
                "tool_requests": requests,
                "tool_outcomes": tool_outcomes,
                "public_messages": v5.v4.json_safe(
                    v5.v4.public_message_history(result.get("messages") or [])
                ),
                "tool_error_receipt": v5.v4._tool_error_receipt(
                    requests, tool_outcomes
                ),
            }
            observations = [dict(item) for item in provider.request_observations]
            if any(
                v5.v4._contains_private_reasoning(value)
                for value in (response_record, trace_record, observations)
            ):
                raise RuntimeError("private reasoning entered public evidence")
            v5._reject_absolute_paths(response_record, location="response")
            v5._reject_absolute_paths(trace_record, location="tool_trace")
            v5._reject_absolute_paths(
                observations, location="provider_observations"
            )
            response_bytes = v5.v4._json_bytes(response_record)
            trace_bytes = v5.v4._json_bytes(trace_record)
            observation_bytes = v5.v4._json_bytes(observations)
            public_bytes = response_bytes + trace_bytes + observation_bytes
            if any(
                secret.encode("utf-8") in public_bytes
                for secret in secret_values
            ):
                raise RuntimeError("secret material entered public evidence")
            terminal = v5.v4._authoritative_terminal(
                session_root, secret_values=secret_values
            )
            private_event_paths = sorted(
                session_root.glob("*/runtime_events.jsonl")
            )
            if len(private_event_paths) != 1:
                raise RuntimeError("private Runtime V2 event log is not unique")
            private_events = v5.v4.RuntimeEventStore(
                private_event_paths[0]
            ).load()
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
            observation_locator = f"provider-observations/{stem}.json"
            event_locator = f"runtime-events/{stem}.jsonl"
            projection_locator = (
                f"runtime-events/{stem}.projection-receipt.json"
            )
            projection_bytes = v5.v4._json_bytes(
                public_projection.receipt.model_dump(mode="json")
            )
            for locator, payload in (
                (response_locator, response_bytes),
                (trace_locator, trace_bytes),
                (observation_locator, observation_bytes),
                (event_locator, public_projection.projected_jsonl_bytes),
                (projection_locator, projection_bytes),
            ):
                v5.v4._write_atomic(output_dir / locator, payload)
            observation_binding = _provider_observation_binding(
                locator=observation_locator,
                observations=observations,
                artifact_bytes=observation_bytes,
            )
            terminal_state = (
                terminal["terminal_state"]
                if grade.oracle_passed
                else "failed"
            )
            outcome_body: dict[str, Any] = {
                "schema_version": "chemsmart.validator-decision-outcome.v1",
                "run_id": run.run_id,
                "run_spec_sha256": run.run_spec_sha256,
                "comparator_sha256": binding.comparator.comparator_sha256,
                "comparator_outcome_receipt_sha256": (
                    binding.comparator.outcome_receipt_sha256
                ),
                "decision_sha256": binding.decision.decision_sha256,
                "projection_sha256": binding.projection.projection_sha256,
                "observed_model": provider.observed_model_id or None,
                "canonical_public_english_report": canonical_public_text,
                "canonical_public_english_report_sha256": content_sha256(
                    canonical_public_text.encode("utf-8")
                ),
                "model_public_english_response": model_public_text,
                "model_public_english_response_sha256": content_sha256(
                    model_public_text.encode("utf-8")
                ),
                "model_output_authoritative": False,
                "response_artifact_locator": response_locator,
                "response_artifact_sha256": content_sha256(response_bytes),
                "tool_trace_artifact_locator": trace_locator,
                "tool_trace_artifact_sha256": content_sha256(trace_bytes),
                "provider_observations": observation_binding,
                "cegis_attempts": cegis_attempts,
                "cegis_lineage_sha256": canonical_json_sha256(
                    [
                        item.model_dump(mode="json")
                        for item in cegis_attempts
                    ]
                ),
                "runtime_event_log_locator": event_locator,
                "runtime_event_log_sha256": (
                    public_projection.receipt.projected_jsonl_sha256
                ),
                "private_runtime_event_log_sha256": (
                    public_projection.receipt.private_exact_jsonl_sha256
                ),
                "runtime_event_projection_receipt_locator": projection_locator,
                "runtime_event_projection_receipt_artifact_sha256": (
                    content_sha256(projection_bytes)
                ),
                "runtime_event_projection_receipt": public_projection.receipt,
                "runtime_replay_verified": True,
                "runtime_replay_state_sha256": (
                    public_projection.receipt.projected_state_sha256
                ),
                "runtime_terminal_state": terminal["terminal_state"],
                "terminal_state": terminal_state,
                "deterministic_grade": grade,
                "accepted_proposal_sha256": (
                    canonical_json_sha256(proposal)
                    if proposal is not None
                    else None
                ),
                "transport_attempts": provider.transport_attempts,
                "input_tokens": sum(
                    int(item.get("input_tokens", 0) or 0)
                    for item in observations
                ),
                "output_tokens": sum(
                    int(item.get("output_tokens", 0) or 0)
                    for item in observations
                ),
                "reasoning_tokens": sum(
                    int(item.get("reasoning_tokens", 0) or 0)
                    for item in observations
                ),
                "wall_time_ms": wall_time_ms,
                "successful_submit_count": successful_count,
                "rejected_submit_count": rejected_count,
                "duplicate_comparator_api_calls": 0,
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
            outcome = ValidatorDecisionOutcomeV1.model_validate(outcome_body)
            outcome_record = {
                "run_spec": run.model_dump(mode="json"),
                "comparator": binding.comparator.model_dump(mode="json"),
                "outcome": outcome.model_dump(mode="json"),
            }
            outcome_locator = f"outcomes/{stem}.json"
            outcome_bytes = v5.v4._json_bytes(outcome_record)
            v5.v4._write_atomic(output_dir / outcome_locator, outcome_bytes)
            outer_artifacts.append(
                {
                    "locator": outcome_locator,
                    "artifact_sha256": content_sha256(outcome_bytes),
                    "size_bytes": len(outcome_bytes),
                }
            )
            outcomes.append(outcome_record)
    finally:
        environment.clear()

    (
        private_receipt,
        private_manifest,
        private_receipt_bytes,
        private_manifest_bytes,
    ) = seal_private_campaign_evidence(
        run_root=run_root,
        campaign_plan_sha256=plan.campaign_plan_sha256,
        source_binding_sha256=source.binding_sha256,
        secret_values=secret_values,
    )

    run_receipt_body: dict[str, Any] = {
        "schema_version": "chemsmart.validator-decision-run-receipt.v1",
        "campaign_id": CAMPAIGN_ID,
        "campaign_plan_sha256": plan.campaign_plan_sha256,
        "campaign_plan_artifact_sha256": content_sha256(plan_bytes),
        "outcome_artifacts": tuple(
            sorted(outer_artifacts, key=lambda item: item["locator"])
        ),
        "outcome_receipt_sha256s": tuple(
            sorted(item["outcome"]["receipt_sha256"] for item in outcomes)
        ),
        "live_run_count": len(outcomes),
        "strict_pass_count": sum(
            item["outcome"]["deterministic_grade"]["oracle_passed"] is True
            and item["outcome"]["runtime_terminal_state"] == "complete"
            for item in outcomes
        ),
        "duplicate_comparator_api_calls": 0,
        "engine_calls": 0,
        "hpc_calls": 0,
        "project_writes": 0,
        "native_inputs_authored": 0,
        "receipt_sha256": "0" * 64,
    }
    run_receipt_body["receipt_sha256"] = _contract_sha256(
        run_receipt_body, "receipt_sha256"
    )
    run_receipt = ValidatorDecisionRunReceiptV1.model_validate(
        run_receipt_body
    )
    run_receipt_bytes = v5.v4._json_bytes(
        run_receipt.model_dump(mode="json")
    )
    v5.v4._write_atomic(
        output_dir / "campaign-run-receipt.json",
        run_receipt_bytes,
    )
    manifest = build_evidence_artifact_manifest_v2(
        output_dir,
        manifest_id=f"{CAMPAIGN_ID}:public",
        scope="public",
        excluded_locators=(
            "artifact-manifest.json",
            "campaign-receipt.json",
        ),
    )
    manifest_bytes = manifest_v2_json_bytes(manifest)
    v5.v4._write_atomic(
        output_dir / "artifact-manifest.json",
        manifest_bytes,
    )
    replay = verify_persisted_campaign_artifacts(
        output_dir=output_dir,
        expected_plan=plan,
        expected_run_receipt=run_receipt,
        manifest=manifest,
    )
    final_body: dict[str, Any] = {
        "schema_version": (
            "chemsmart.validator-decision-campaign-receipt.v1"
        ),
        "campaign_id": CAMPAIGN_ID,
        "campaign_plan_sha256": plan.campaign_plan_sha256,
        "campaign_plan_artifact_sha256": content_sha256(plan_bytes),
        "run_receipt_locator": "campaign-run-receipt.json",
        "run_receipt_sha256": run_receipt.receipt_sha256,
        "run_receipt_artifact_sha256": content_sha256(run_receipt_bytes),
        "public_manifest_locator": "artifact-manifest.json",
        "public_manifest_sha256": manifest.manifest_sha256,
        "public_manifest_artifact_sha256": content_sha256(manifest_bytes),
        "private_manifest_sha256": private_manifest.manifest_sha256,
        "private_manifest_artifact_sha256": content_sha256(
            private_manifest_bytes
        ),
        "private_receipt_sha256": private_receipt.receipt_sha256,
        "private_receipt_artifact_sha256": content_sha256(
            private_receipt_bytes
        ),
        "private_artifact_count": private_manifest.artifact_count,
        **replay,
        "receipt_sha256": "0" * 64,
    }
    final_body["receipt_sha256"] = _contract_sha256(
        final_body, "receipt_sha256"
    )
    final_receipt = ValidatorDecisionCampaignReceiptV1.model_validate(
        final_body
    )
    v5.v4._write_atomic(
        output_dir / "campaign-receipt.json",
        v5.v4._json_bytes(final_receipt.model_dump(mode="json")),
    )
    persisted_final = ValidatorDecisionCampaignReceiptV1.model_validate(
        _json_file(output_dir / "campaign-receipt.json")
    )
    if persisted_final != final_receipt:
        raise ValueError("final campaign receipt does not replay")
    verify_evidence_artifact_manifest_v2(output_dir, manifest)
    return {
        **final_receipt.model_dump(mode="json"),
        "live_run_count": run_receipt.live_run_count,
        "outcomes": outcomes,
    }


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
        source = v5.v4.capture_repository_binding(repository_root)
        bundle = v5.v4.load_registry_v2_bundle(repository_root)
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
                    "live_run_count": len(plan.runs),
                    "transport_attempts": 0,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.api_env is None or args.run_root is None or args.output_dir is None:
        parser.error(
            "live mode requires --api-env, --run-root, and --output-dir"
        )
    receipt = run_campaign(
        repository_root=repository_root,
        api_env=args.api_env,
        run_root=args.run_root,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "campaign_id": receipt["campaign_id"],
                "receipt_sha256": receipt["receipt_sha256"],
                "public_manifest_sha256": receipt[
                    "public_manifest_sha256"
                ],
                "live_run_count": receipt["live_run_count"],
                "strict_pass_count": receipt["strict_pass_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
