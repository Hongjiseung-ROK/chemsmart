"""Typed additive event payloads for paper-derived research planning.

Legacy Runtime V2 events intentionally retain their original payload contract.
Only the event kinds registered here are validated against these path-free v1
models.  Payloads contain observable identifiers, digests, findings, budgets,
and outcomes; hidden reasoning and raw provider state are never accepted.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from chemsmart.agent.paper_research import (
    PaperResearchPlan,
    PaperResearchPlanValidation,
    PaperResearchValidationContext,
    PlanState,
    contract_sha256,
    validate_paper_research_plan,
)
from chemsmart.agent.runtime.delegation_contracts import (
    ResourceBudget,
    ResourceUsage,
    ReviewFinding,
    ReviewGateReceipt,
    ReviewPacket,
    SpecialistMergeReceipt,
    SpecialistResultPacket,
    SpecialistTaskPacket,
    budget_rule_ids,
    resource_budget_sha256,
    resource_usage_sha256,
    review_finding_sha256,
    review_gate_receipt_sha256,
    review_packet_sha256,
    specialist_merge_receipt_sha256,
    specialist_result_packet_sha256,
    specialist_task_packet_sha256,
)
from chemsmart.agent.runtime.events import EventKind


RESEARCH_EVENT_SCHEMA_VERSION = "chemsmart.runtime-research-event.v1"

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
_SHA256 = r"^[0-9a-f]{64}$"


def _canonical_identifiers(
    values: tuple[str, ...],
    *,
    label: str,
) -> tuple[str, ...]:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")
    if any(re.fullmatch(_IDENTIFIER, value) is None for value in values):
        raise ValueError(f"{label} contain an invalid identifier")
    return tuple(sorted(values))


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[RESEARCH_EVENT_SCHEMA_VERSION] = (
        RESEARCH_EVENT_SCHEMA_VERSION
    )
    plan_id: str = Field(pattern=_IDENTIFIER)
    plan_sha256: str = Field(pattern=_SHA256)


class ResearchStage(str, Enum):
    NOT_STARTED = "not_started"
    SOURCE_COLLECTION = "source_collection"
    CLAIM_EXTRACTION = "claim_extraction"
    SCIENTIFIC_SPECIFICATION = "scientific_specification"
    PROJECT_CONFIGURATION = "project_configuration"
    COMMAND_PLANNING = "command_planning"
    PREFLIGHT = "preflight"
    INDEPENDENT_REVIEW = "independent_review"
    REPORTING = "reporting"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTION = "execution"
    VALIDATION = "validation"
    REPLANNING = "replanning"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    FAILED = "failed"


_GENERIC_STAGES = frozenset(
    {
        ResearchStage.SOURCE_COLLECTION,
        ResearchStage.CLAIM_EXTRACTION,
        ResearchStage.SCIENTIFIC_SPECIFICATION,
        ResearchStage.PROJECT_CONFIGURATION,
        ResearchStage.COMMAND_PLANNING,
        ResearchStage.PREFLIGHT,
        ResearchStage.INDEPENDENT_REVIEW,
        ResearchStage.REPORTING,
        ResearchStage.REPLANNING,
    }
)


class ResearchStageChangedPayload(_Payload):
    stage: ResearchStage
    reason_rule_ids: tuple[str, ...] = ()

    @field_validator("reason_rule_ids")
    @classmethod
    def _canonical_reason_rule_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_identifiers(values, label="reason_rule_ids")

    @model_validator(mode="after")
    def _stage_is_non_authoritative(self) -> "ResearchStageChangedPayload":
        if self.stage not in _GENERIC_STAGES:
            raise ValueError(
                "generic research stage events cannot assert approval, execution, "
                "validation, or terminal state"
            )
        return self


class PlanRevisionAdoptedPayload(BaseModel):
    """Explicitly replace one immutable plan revision with another."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[RESEARCH_EVENT_SCHEMA_VERSION] = (
        RESEARCH_EVENT_SCHEMA_VERSION
    )
    previous_plan_id: str = Field(pattern=_IDENTIFIER)
    previous_plan_sha256: str = Field(pattern=_SHA256)
    new_plan_id: str = Field(pattern=_IDENTIFIER)
    new_plan_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _revision_has_a_new_identity(self) -> "PlanRevisionAdoptedPayload":
        if self.previous_plan_id == self.new_plan_id:
            raise ValueError("a plan revision requires a new immutable plan ID")
        if self.previous_plan_sha256 == self.new_plan_sha256:
            raise ValueError("a plan revision requires a new plan digest")
        return self


class PaperSourceFrozenPayload(_Payload):
    source_bundle_id: str = Field(pattern=_IDENTIFIER)
    source_bundle_sha256: str = Field(pattern=_SHA256)


class ProtocolClaimRecordedPayload(_Payload):
    claim_id: str = Field(pattern=_IDENTIFIER)
    claim_sha256: str = Field(pattern=_SHA256)
    epistemic_status: Literal[
        "explicit",
        "derived",
        "inferred",
        "unknown",
        "conflict",
        "not_applicable",
    ]
    criticality: Literal["critical", "important", "context"]


class MolecularSystemSpecifiedPayload(_Payload):
    system_id: str = Field(pattern=_IDENTIFIER)
    system_sha256: str = Field(pattern=_SHA256)
    geometry_sha256: str = Field(pattern=_SHA256)


class ProjectConfigSpecifiedPayload(_Payload):
    project_id: str = Field(pattern=_IDENTIFIER)
    project_config_sha256: str = Field(pattern=_SHA256)
    project_yaml_sha256: str | None = Field(default=None, pattern=_SHA256)
    loader_receipt_sha256: str | None = Field(default=None, pattern=_SHA256)

    @model_validator(mode="after")
    def _render_receipts_are_paired(self) -> "ProjectConfigSpecifiedPayload":
        if (self.project_yaml_sha256 is None) != (
            self.loader_receipt_sha256 is None
        ):
            raise ValueError("project YAML and loader receipt digests must be paired")
        return self


class DomainKnowledgeBoundPayload(_Payload):
    pack_id: str = Field(pattern=_IDENTIFIER)
    pack_sha256: str = Field(pattern=_SHA256)
    validator_registry_sha256: str = Field(pattern=_SHA256)
    domains: tuple[
        Literal[
            "general",
            "reaction_mechanism",
            "transition_metal",
            "excited_state",
            "conformer_ensemble",
            "thermochemistry",
            "multiscale_qmmm",
        ],
        ...,
    ] = Field(min_length=1)
    programs: tuple[Literal["gaussian", "orca", "xtb"], ...] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def _scopes_are_canonical(self) -> "DomainKnowledgeBoundPayload":
        if tuple(sorted(set(self.domains))) != self.domains:
            raise ValueError("domain knowledge domains must be unique and sorted")
        if tuple(sorted(set(self.programs))) != self.programs:
            raise ValueError("domain knowledge programs must be unique and sorted")
        return self


class ReviewGateRefPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["domain", "command_evidence", "adversarial"]
    review_gate_id: str = Field(pattern=_IDENTIFIER)
    review_gate_sha256: str = Field(pattern=_SHA256)


def _validate_complete_review_set(
    refs: tuple[ReviewGateRefPayload, ...],
) -> None:
    roles = tuple(item.role for item in refs)
    required = ("adversarial", "command_evidence", "domain")
    if tuple(sorted(roles)) != required:
        raise ValueError(
            "a valid paper plan requires exactly one domain, command_evidence, "
            "and adversarial review gate"
        )
    gate_ids = tuple(item.review_gate_id for item in refs)
    if len(gate_ids) != len(set(gate_ids)):
        raise ValueError("independent review roles require distinct gate IDs")


def paper_plan_validation_rule_ids(
    validation: PaperResearchPlanValidation,
) -> tuple[str, ...]:
    """Return deterministic terminal reasons, including non-finding blockers."""

    rules = {item.rule_id for item in validation.findings}
    status_rule = {
        "blocked_missing_evidence": "paper.plan.blocked_missing_evidence",
        "blocked_capability_gap": "paper.plan.blocked_capability_gap",
        "invalid": "paper.plan.invalid",
    }.get(validation.status.value)
    if status_rule is not None:
        rules.add(status_rule)
    return tuple(sorted(rules))


class PaperPlanValidationReceiptBody(_Payload):
    """Full deterministic paper-plan validation surface except its own digest."""

    validation_receipt_id: str = Field(pattern=_IDENTIFIER)
    status: Literal[
        "valid",
        "blocked_missing_evidence",
        "blocked_capability_gap",
        "invalid",
    ]
    review_gate_refs: tuple[ReviewGateRefPayload, ...] = ()
    report_graph_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    report_graph_sha256: str | None = Field(default=None, pattern=_SHA256)
    rule_ids: tuple[str, ...] = ()
    paper_plan: PaperResearchPlan
    validation_context: PaperResearchValidationContext
    validation: PaperResearchPlanValidation

    @field_validator("rule_ids")
    @classmethod
    def _canonical_rule_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_identifiers(values, label="plan-validation rule_ids")

    @field_validator("review_gate_refs")
    @classmethod
    def _canonical_review_order(
        cls, refs: tuple[ReviewGateRefPayload, ...]
    ) -> tuple[ReviewGateRefPayload, ...]:
        return tuple(sorted(refs, key=lambda item: item.role))

    @model_validator(mode="after")
    def _validation_is_deterministically_derived(
        self,
    ) -> "PaperPlanValidationReceiptBody":
        if self.plan_id != self.paper_plan.plan_id:
            raise ValueError("plan_id does not match embedded paper plan")
        if self.plan_sha256 != contract_sha256(self.paper_plan):
            raise ValueError("plan_sha256 does not bind embedded paper plan")
        derived = validate_paper_research_plan(
            self.paper_plan,
            context=self.validation_context,
        )
        if derived.model_dump(mode="json") != self.validation.model_dump(
            mode="json"
        ):
            raise ValueError(
                "paper plan validation body is not deterministically derived"
            )
        if self.status != derived.status.value:
            raise ValueError("plan validation status does not match derived status")
        derived_rules = paper_plan_validation_rule_ids(derived)
        if self.rule_ids != derived_rules:
            raise ValueError(
                "plan validation rule_ids do not match the derived outcome"
            )
        report_paired = (self.report_graph_id is None) == (
            self.report_graph_sha256 is None
        )
        if not report_paired:
            raise ValueError("plan validation report ID and digest must pair")
        if self.status == "valid":
            if self.paper_plan.plan_state is not PlanState.VALIDATED:
                raise ValueError(
                    "valid runtime plan receipt requires plan_state=validated"
                )
            _validate_complete_review_set(self.review_gate_refs)
            if self.report_graph_id is None:
                raise ValueError("valid plan validation requires a report graph")
            if self.rule_ids:
                raise ValueError("valid plan validation cannot retain rule_ids")
        elif self.review_gate_refs or self.report_graph_id is not None:
            raise ValueError(
                "non-valid plan validation cannot claim final review/report gates"
            )
        elif not self.rule_ids:
            raise ValueError("blocked or invalid plan validation requires rule_ids")
        return self


class PaperPlanValidatedPayload(PaperPlanValidationReceiptBody):
    """Content-addressed event payload for one deterministic validation run."""

    validation_receipt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _receipt_digest_binds_the_full_body(self) -> "PaperPlanValidatedPayload":
        expected = paper_plan_validation_receipt_sha256(self)
        if self.validation_receipt_sha256 != expected:
            raise ValueError(
                "validation_receipt_sha256 does not bind the full validation payload"
            )
        return self


def paper_plan_validation_receipt_sha256(
    value: PaperPlanValidationReceiptBody | dict[str, Any],
) -> str:
    """Hash every canonical validation-event field except the digest itself."""

    if isinstance(value, BaseModel):
        body = value.model_dump(
            mode="json",
            exclude={"validation_receipt_sha256"},
        )
    else:
        raw = dict(value)
        raw.pop("validation_receipt_sha256", None)
        body = PaperPlanValidationReceiptBody.model_validate(raw).model_dump(
            mode="json"
        )
    encoded = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class SpecialistTaskDispatchedPayload(_Payload):
    task_id: str = Field(pattern=_IDENTIFIER)
    task_packet_sha256: str = Field(pattern=_SHA256)
    role: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")
    task_packet: SpecialistTaskPacket

    @model_validator(mode="after")
    def _task_labels_bind_exact_packet(self) -> "SpecialistTaskDispatchedPayload":
        if self.task_id != self.task_packet.task_id:
            raise ValueError("task_id does not match embedded specialist packet")
        if self.role != self.task_packet.role.value:
            raise ValueError("role does not match embedded specialist packet")
        if self.task_packet_sha256 != specialist_task_packet_sha256(
            self.task_packet
        ):
            raise ValueError("task_packet_sha256 does not bind embedded packet")
        return self


class SpecialistTasksJoinedPayload(_Payload):
    merge_receipt_id: str = Field(pattern=_IDENTIFIER)
    merge_receipt_sha256: str = Field(pattern=_SHA256)
    task_ids: tuple[str, ...] = Field(min_length=1)
    result_packet_sha256s: tuple[str, ...] = ()
    status: Literal["accepted", "rejected"]
    rule_ids: tuple[str, ...] = ()
    result_packets: tuple[SpecialistResultPacket, ...] = ()
    merge_receipt: SpecialistMergeReceipt

    @field_validator("task_ids", "rule_ids")
    @classmethod
    def _canonical_join_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("specialist join identifiers must be unique")
        if any(re.fullmatch(_IDENTIFIER, value) is None for value in values):
            raise ValueError("specialist join identifiers are invalid")
        return values

    @field_validator("result_packet_sha256s")
    @classmethod
    def _result_digests_are_valid(
        cls, values: tuple[str, ...]
    ) -> tuple[str, ...]:
        if any(re.fullmatch(_SHA256, value) is None for value in values):
            raise ValueError("result packet digests must be SHA-256 values")
        return values

    @field_validator("result_packets")
    @classmethod
    def _canonical_result_packets(
        cls,
        values: tuple[SpecialistResultPacket, ...],
    ) -> tuple[SpecialistResultPacket, ...]:
        result_ids = [item.result_id for item in values]
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("specialist result packet IDs must be unique")
        return tuple(
            sorted(
                values,
                key=lambda item: (
                    item.task_id,
                    item.result_id,
                    specialist_result_packet_sha256(item),
                ),
            )
        )

    @model_validator(mode="after")
    def _join_labels_are_receipt_derived(self) -> "SpecialistTasksJoinedPayload":
        if self.merge_receipt_sha256 != specialist_merge_receipt_sha256(
            self.merge_receipt
        ):
            raise ValueError("merge_receipt_sha256 does not bind embedded receipt")
        if self.task_ids != self.merge_receipt.ordered_task_ids:
            raise ValueError("task_ids do not match merge receipt ordering")
        if self.result_packet_sha256s != self.merge_receipt.result_packet_sha256s:
            raise ValueError("result packet digests do not match merge receipt")
        embedded_result_digests = tuple(
            specialist_result_packet_sha256(item) for item in self.result_packets
        )
        if self.result_packet_sha256s != embedded_result_digests:
            raise ValueError(
                "result packet digests do not bind embedded result packets"
            )
        if self.status != self.merge_receipt.status:
            raise ValueError("join status does not match merge receipt")
        derived_rules = tuple(
            sorted({finding.rule_id for finding in self.merge_receipt.findings})
        )
        if self.rule_ids != derived_rules:
            raise ValueError("join rule_ids do not match merge receipt findings")
        return self


class CommandWorkflowPreviewedPayload(_Payload):
    workflow_id: str = Field(pattern=_IDENTIFIER)
    command_workflow_sha256: str = Field(pattern=_SHA256)
    preflight_receipt_sha256: str = Field(pattern=_SHA256)
    status: Literal["previewed"] = "previewed"


class ReviewFindingRecordedPayload(_Payload):
    review_id: str = Field(pattern=_IDENTIFIER)
    review_packet_sha256: str = Field(pattern=_SHA256)
    finding_id: str = Field(pattern=_IDENTIFIER)
    finding_sha256: str = Field(pattern=_SHA256)
    role: Literal["domain", "command_evidence", "adversarial"]
    severity: Literal["informational", "warning", "error", "critical"]
    disposition: Literal["open"] = "open"
    finding: ReviewFinding

    @model_validator(mode="after")
    def _finding_labels_bind_exact_finding(self) -> "ReviewFindingRecordedPayload":
        finding = self.finding
        comparisons = (
            ("review_id", self.review_id, finding.review_id),
            ("finding_id", self.finding_id, finding.finding_id),
            ("role", self.role, finding.role.value),
            ("severity", self.severity, finding.severity.value),
            ("disposition", self.disposition, finding.disposition),
        )
        for label, observed, expected in comparisons:
            if observed != expected:
                raise ValueError(f"{label} does not match embedded review finding")
        if self.finding_sha256 != review_finding_sha256(finding):
            raise ValueError("finding_sha256 does not bind embedded review finding")
        return self


class ReviewFindingRefPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(pattern=_IDENTIFIER)
    finding_sha256: str = Field(pattern=_SHA256)


class ReviewGateRecordedPayload(_Payload):
    review_id: str = Field(pattern=_IDENTIFIER)
    review_packet_sha256: str = Field(pattern=_SHA256)
    role: Literal["domain", "command_evidence", "adversarial"]
    review_gate_id: str = Field(pattern=_IDENTIFIER)
    review_gate_sha256: str = Field(pattern=_SHA256)
    finding_refs: tuple[ReviewFindingRefPayload, ...] = ()
    status: Literal[
        "invalid_review",
        "critical_findings_open",
        "no_critical_findings_observed",
    ]
    review_packet: ReviewPacket
    review_gate_receipt: ReviewGateReceipt

    @field_validator("finding_refs")
    @classmethod
    def _canonical_finding_refs(
        cls, refs: tuple[ReviewFindingRefPayload, ...]
    ) -> tuple[ReviewFindingRefPayload, ...]:
        finding_ids = [item.finding_id for item in refs]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("review gate finding references must be unique")
        return tuple(sorted(refs, key=lambda item: item.finding_id))

    @model_validator(mode="after")
    def _gate_labels_bind_exact_contracts(self) -> "ReviewGateRecordedPayload":
        packet = self.review_packet
        receipt = self.review_gate_receipt
        if self.review_id != packet.review_id or self.review_id != receipt.review_id:
            raise ValueError("review_id does not match embedded review contracts")
        if self.role != packet.role.value:
            raise ValueError("role does not match embedded review packet")
        if self.review_packet_sha256 != review_packet_sha256(packet):
            raise ValueError("review_packet_sha256 does not bind embedded packet")
        if receipt.review_packet_sha256 != self.review_packet_sha256:
            raise ValueError("review receipt does not bind embedded review packet")
        if self.review_gate_sha256 != review_gate_receipt_sha256(receipt):
            raise ValueError("review_gate_sha256 does not bind embedded receipt")
        receipt_refs = tuple(
            ReviewFindingRefPayload.model_validate(item.model_dump(mode="json"))
            for item in receipt.finding_refs
        )
        if self.finding_refs != receipt_refs:
            raise ValueError("finding_refs do not match embedded review receipt")
        if self.status != receipt.verdict:
            raise ValueError("review status does not match embedded review receipt")
        derived_budget_rules = budget_rule_ids(receipt.usage, packet.budget)
        unexpected_tools = set(receipt.tools_used).difference(packet.allowed_tools)
        if (
            self.status == "no_critical_findings_observed"
            and (derived_budget_rules or unexpected_tools)
        ):
            raise ValueError("invalid or over-budget review cannot be green")
        return self


class ReportGraphRecordedPayload(_Payload):
    report_graph_id: str = Field(pattern=_IDENTIFIER)
    report_graph_sha256: str = Field(pattern=_SHA256)
    evidence_graph_sha256: str = Field(pattern=_SHA256)
    review_gate_refs: tuple[ReviewGateRefPayload, ...] = Field(min_length=3)

    @field_validator("review_gate_refs")
    @classmethod
    def _canonical_review_order(
        cls, refs: tuple[ReviewGateRefPayload, ...]
    ) -> tuple[ReviewGateRefPayload, ...]:
        ordered = tuple(sorted(refs, key=lambda item: item.role))
        _validate_complete_review_set(ordered)
        return ordered


class ResearchBudgetRecordedPayload(_Payload):
    budget_receipt_id: str = Field(pattern=_IDENTIFIER)
    budget_sha256: str = Field(pattern=_SHA256)
    usage_sha256: str = Field(pattern=_SHA256)
    status: Literal["within_budget", "exceeded"]
    budget: ResourceBudget
    usage: ResourceUsage

    @model_validator(mode="after")
    def _budget_status_is_derived(self) -> "ResearchBudgetRecordedPayload":
        if self.budget_sha256 != resource_budget_sha256(self.budget):
            raise ValueError("budget_sha256 does not bind embedded budget")
        if self.usage_sha256 != resource_usage_sha256(self.usage):
            raise ValueError("usage_sha256 does not bind embedded usage")
        derived_status = (
            "exceeded" if budget_rule_ids(self.usage, self.budget) else "within_budget"
        )
        if self.status != derived_status:
            raise ValueError("research budget status does not match canonical usage")
        return self


class ResearchPausedPayload(_Payload):
    pause_id: str = Field(pattern=_IDENTIFIER)
    reason_rule_ids: tuple[str, ...] = Field(min_length=1)
    public_recap_sha256: str = Field(pattern=_SHA256)

    @field_validator("reason_rule_ids")
    @classmethod
    def _canonical_reason_rule_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_identifiers(values, label="reason_rule_ids")


class ResearchResumedPayload(_Payload):
    pause_id: str = Field(pattern=_IDENTIFIER)
    resume_stage: ResearchStage
    public_recap_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _resume_is_non_authoritative(self) -> "ResearchResumedPayload":
        if self.resume_stage not in _GENERIC_STAGES:
            raise ValueError("resume_stage must be a non-authoritative planning stage")
        return self


class ResearchTerminatedPayload(_Payload):
    terminal_state: Literal["complete", "blocked", "failed"]
    validation_receipt_id: str = Field(pattern=_IDENTIFIER)
    validation_receipt_sha256: str = Field(pattern=_SHA256)
    validation_status: Literal[
        "valid",
        "blocked_missing_evidence",
        "blocked_capability_gap",
        "invalid",
    ]
    review_gate_refs: tuple[ReviewGateRefPayload, ...] = ()
    report_graph_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    report_graph_sha256: str | None = Field(default=None, pattern=_SHA256)
    required_gates_passed: bool = False
    reason_rule_ids: tuple[str, ...] = ()

    @field_validator("reason_rule_ids")
    @classmethod
    def _canonical_reason_rule_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_identifiers(values, label="reason_rule_ids")

    @field_validator("review_gate_refs")
    @classmethod
    def _canonical_review_order(
        cls, refs: tuple[ReviewGateRefPayload, ...]
    ) -> tuple[ReviewGateRefPayload, ...]:
        return tuple(sorted(refs, key=lambda item: item.role))

    @model_validator(mode="after")
    def _terminal_claim_is_evidence_bound(self) -> "ResearchTerminatedPayload":
        allowed_statuses = {
            "complete": {"valid"},
            "blocked": {
                "blocked_missing_evidence",
                "blocked_capability_gap",
            },
            "failed": {"invalid"},
        }
        if self.validation_status not in allowed_statuses[self.terminal_state]:
            raise ValueError(
                "terminal_state does not match the plan validation status"
            )
        report_paired = (self.report_graph_id is None) == (
            self.report_graph_sha256 is None
        )
        if not report_paired:
            raise ValueError("terminal report identifier and digest must pair")
        if self.terminal_state == "complete":
            if self.validation_status != "valid":
                raise ValueError("complete requires a valid plan-validation receipt")
            if not self.required_gates_passed:
                raise ValueError("complete requires every deterministic gate to pass")
            _validate_complete_review_set(self.review_gate_refs)
            if self.report_graph_id is None:
                raise ValueError(
                    "complete requires review-gate and report-graph receipts"
                )
            if self.reason_rule_ids:
                raise ValueError("complete cannot retain unresolved rule_ids")
        else:
            if self.required_gates_passed:
                raise ValueError("blocked or failed cannot claim all gates passed")
            if not self.reason_rule_ids:
                raise ValueError("blocked or failed requires stable reason_rule_ids")
            if self.review_gate_refs:
                raise ValueError("blocked or failed forbids review gate fields")
            if self.report_graph_id is not None:
                raise ValueError("blocked or failed forbids report graph fields")
        return self


RESEARCH_EVENT_PAYLOAD_MODELS: dict[EventKind, type[BaseModel]] = {
    EventKind.RESEARCH_STAGE_CHANGED: ResearchStageChangedPayload,
    EventKind.PLAN_REVISION_ADOPTED: PlanRevisionAdoptedPayload,
    EventKind.PAPER_SOURCE_FROZEN: PaperSourceFrozenPayload,
    EventKind.PROTOCOL_CLAIM_RECORDED: ProtocolClaimRecordedPayload,
    EventKind.MOLECULAR_SYSTEM_SPECIFIED: MolecularSystemSpecifiedPayload,
    EventKind.PROJECT_CONFIG_SPECIFIED: ProjectConfigSpecifiedPayload,
    EventKind.DOMAIN_KNOWLEDGE_BOUND: DomainKnowledgeBoundPayload,
    EventKind.PAPER_PLAN_VALIDATED: PaperPlanValidatedPayload,
    EventKind.SPECIALIST_TASK_DISPATCHED: SpecialistTaskDispatchedPayload,
    EventKind.SPECIALIST_TASKS_JOINED: SpecialistTasksJoinedPayload,
    EventKind.COMMAND_WORKFLOW_PREVIEWED: CommandWorkflowPreviewedPayload,
    EventKind.REVIEW_FINDING_RECORDED: ReviewFindingRecordedPayload,
    EventKind.REVIEW_GATE_RECORDED: ReviewGateRecordedPayload,
    EventKind.REPORT_GRAPH_RECORDED: ReportGraphRecordedPayload,
    EventKind.RESEARCH_BUDGET_RECORDED: ResearchBudgetRecordedPayload,
    EventKind.RESEARCH_PAUSED: ResearchPausedPayload,
    EventKind.RESEARCH_RESUMED: ResearchResumedPayload,
    EventKind.RESEARCH_TERMINATED: ResearchTerminatedPayload,
}


def validate_research_event_payload(
    kind: EventKind,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate and canonically project a research-event payload.

    Returning legacy payloads unchanged is deliberate: old event logs remain
    replayable without retroactive migration or behavior changes.
    """

    model_cls = RESEARCH_EVENT_PAYLOAD_MODELS.get(kind)
    if model_cls is None:
        return dict(payload)
    return model_cls.model_validate(payload).model_dump(mode="json")


def is_research_event_kind(kind: EventKind) -> bool:
    return kind in RESEARCH_EVENT_PAYLOAD_MODELS


__all__ = [
    "RESEARCH_EVENT_PAYLOAD_MODELS",
    "RESEARCH_EVENT_SCHEMA_VERSION",
    "ResearchStage",
    "is_research_event_kind",
    "paper_plan_validation_rule_ids",
    "paper_plan_validation_receipt_sha256",
    "validate_research_event_payload",
]
