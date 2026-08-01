"""Additive, versioned scientific and evidence contracts for Runtime V2.

These models are intentionally declarative.  They do not invoke an engine,
change Click semantics, grant approval, or turn a model response into a
scientific pass.  Runtime events carry the payload envelopes defined here so
older event records remain independent from this opt-in contract surface.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from chemsmart.agent.runtime.contracts import (
    ExecutionMode,
    OpaqueArtifactRef,
    RuntimeContract,
)


_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SCIENTIFIC_V1_RECORD_FIELDS = (
    "provider_capabilities",
    "task_spec",
    "task_graph",
    "resource_budget",
    "approval_request",
    "approval_resolution",
    "approval_invalidation",
    "evidence",
    "validation",
    "claim",
    "review_finding",
    "report_manifest",
    "budget_exhaustion",
    "phase_close",
)


class ScientificTaskKind(str, Enum):
    PLAN = "plan"
    SINGLE_POINT = "single_point"
    OPTIMIZATION = "optimization"
    FREQUENCY = "frequency"
    TRANSITION_STATE = "transition_state"
    PATHWAY = "pathway"
    COMPARISON = "comparison"
    ANALYSIS = "analysis"


class ValidationStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"


class ClaimType(str, Enum):
    OBSERVATION = "observation"
    COMPUTED_RESULT = "computed_result"
    INFERENCE = "inference"
    LITERATURE_STATEMENT = "literature_statement"
    UNRESOLVED_UNCERTAINTY = "unresolved_uncertainty"


class ClaimStatus(str, Enum):
    SUPPORTED = "supported"
    QUALIFIED = "qualified"
    UNRESOLVED = "unresolved"
    REJECTED = "rejected"


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"


class ReviewSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class GeometryFrameRef(RuntimeContract):
    """Stable, model-safe geometry identity rather than a filename guess."""

    molecule_id: str = Field(min_length=1, max_length=128)
    geometry_frame_id: str = Field(min_length=1, max_length=128)
    artifact: OpaqueArtifactRef
    coordinate_units: Literal["angstrom", "bohr"]
    atom_count: int = Field(ge=1)
    atom_order_sha256: str = Field(pattern=_SHA256_PATTERN)


class EvidenceRequirement(RuntimeContract):
    requirement_id: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=500)
    required: bool = True


class ScientificTaskSpec(RuntimeContract):
    """A typed chemistry task declaration for shadow/runtime evidence paths."""

    contract_version: Literal[1] = 1
    task_spec_id: str = Field(min_length=1, max_length=128)
    geometry: GeometryFrameRef
    charge: int
    multiplicity: int = Field(ge=1)
    fragments: tuple[str, ...] = ()
    stereochemistry: str = ""
    constraints: tuple[str, ...] = ()
    requested_observable: str = Field(min_length=1, max_length=500)
    task_kind: ScientificTaskKind
    execution_mode: ExecutionMode = ExecutionMode.NONE
    program: str = Field(min_length=1, max_length=64)
    job_kind: str = Field(min_length=1, max_length=128)
    method: str = ""
    basis_or_ecp: str = ""
    dispersion: str = ""
    solvent: str = ""
    temperature_kelvin: float | None = Field(default=None, ge=0.0)
    standard_state: str = ""
    resource_target: str = ""
    assumptions: tuple[str, ...] = ()
    expected_evidence: tuple[EvidenceRequirement, ...] = ()
    unresolved_facts: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _requires_explicit_missing_facts(self) -> "ScientificTaskSpec":
        required_values = {
            "method": self.method,
            "basis_or_ecp": self.basis_or_ecp,
            "dispersion": self.dispersion,
            "solvent": self.solvent,
            "standard_state": self.standard_state,
            "resource_target": self.resource_target,
        }
        missing = {name for name, value in required_values.items() if not value}
        if self.temperature_kelvin is None:
            missing.add("temperature_kelvin")
        declared = set(self.unresolved_facts)
        undeclared = missing - declared
        if undeclared:
            joined = ", ".join(sorted(undeclared))
            raise ValueError(f"unresolved_facts must declare missing facts: {joined}")
        if not self.expected_evidence:
            raise ValueError("expected_evidence must contain at least one requirement")
        return self

    @property
    def execution_ready(self) -> bool:
        """Whether the declared task has no acknowledged consequential gaps."""

        return not self.unresolved_facts


class ProviderCapabilities(RuntimeContract):
    """Observable provider capability snapshot; no secret or hidden reasoning."""

    contract_version: Literal[1] = 1
    provider_id: str = Field(min_length=1, max_length=128)
    wire_protocol: str = Field(min_length=1, max_length=128)
    resolved_model: str = Field(min_length=1, max_length=256)
    supports_structured_output: bool
    continuation_mode: Literal["none", "adapter_owned_checkpoint"]
    max_context_tokens: int = Field(ge=0)
    max_tool_calls: int = Field(ge=0)
    max_parallel_tasks: int = Field(ge=0)
    configuration_sha256: str = Field(pattern=_SHA256_PATTERN)
    observed_at: str = Field(min_length=1, max_length=64)


class ResourceBudget(RuntimeContract):
    """Explicit ceilings; zero is a valid explicit no-use ceiling."""

    contract_version: Literal[1] = 1
    budget_id: str = Field(min_length=1, max_length=128)
    max_model_calls: int = Field(ge=0)
    max_tokens: int = Field(ge=0)
    max_tool_calls: int = Field(ge=0)
    max_cost_usd: float = Field(ge=0.0)
    max_wall_time_s: int = Field(ge=0)
    max_compute_seconds: int = Field(ge=0)
    max_retries: int = Field(ge=0)


class TaskNode(RuntimeContract):
    """Declarative node only; this contract does not dispatch a worker."""

    node_id: str = Field(min_length=1, max_length=128)
    task_spec_id: str = Field(min_length=1, max_length=128)
    dependencies: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    budget_id: str = Field(min_length=1, max_length=128)
    approval_scope_sha256: str = Field(pattern=_SHA256_PATTERN)
    expected_evidence_ids: tuple[str, ...] = ()
    verifier_id: str = Field(min_length=1, max_length=128)
    role: Literal["single_agent", "worker", "critic"] = "single_agent"


class TaskGraph(RuntimeContract):
    contract_version: Literal[1] = 1
    task_graph_id: str = Field(min_length=1, max_length=128)
    nodes: tuple[TaskNode, ...] = ()
    deterministic_join_id: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _requires_acyclic_known_dependencies(self) -> "TaskGraph":
        node_ids = [node.node_id for node in self.nodes]
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("task graph node identifiers must be unique")
        known = set(node_ids)
        dependencies = {node.node_id: set(node.dependencies) for node in self.nodes}
        for node_id, values in dependencies.items():
            if node_id in values:
                raise ValueError(f"task graph node {node_id!r} depends on itself")
            unknown = values - known
            if unknown:
                raise ValueError(
                    f"task graph node {node_id!r} has unknown dependencies: "
                    f"{sorted(unknown)}"
                )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise ValueError("task graph dependencies must be acyclic")
            if node_id in visited:
                return
            visiting.add(node_id)
            for dependency in dependencies[node_id]:
                visit(dependency)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in dependencies:
            visit(node_id)
        return self


class ApprovalRequest(RuntimeContract):
    """One exact approval envelope; its digest is the approval binding."""

    contract_version: Literal[1] = 1
    approval_id: str = Field(min_length=1, max_length=128)
    task_spec_id: str = Field(min_length=1, max_length=128)
    tool_name: str = Field(min_length=1, max_length=128)
    action_kind: str = Field(min_length=1, max_length=128)
    policy_version: str = Field(min_length=1, max_length=128)
    origin_event_hash: str = Field(pattern=_SHA256_PATTERN)
    command_sha256: str = Field(pattern=_SHA256_PATTERN)
    input_sha256s: tuple[str, ...] = ()
    project_sha256: str = Field(pattern=_SHA256_PATTERN)
    executable_sha256: str = Field(pattern=_SHA256_PATTERN)
    environment_sha256: str = Field(pattern=_SHA256_PATTERN)
    resource_budget_sha256: str = Field(pattern=_SHA256_PATTERN)
    preflight_receipt_sha256s: tuple[str, ...] = ()
    execution_target: str = Field(min_length=1, max_length=128)
    overwrite_intent: bool = False
    provider_configuration_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    requested_at: str = Field(min_length=1, max_length=64)
    expires_at: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _requires_input_hashes(self) -> "ApprovalRequest":
        if not self.input_sha256s:
            raise ValueError("approval request requires at least one input hash")
        if any(not _is_sha256(item) for item in self.input_sha256s):
            raise ValueError("approval request input hashes must be SHA-256")
        if tuple(sorted(set(self.input_sha256s))) != self.input_sha256s:
            raise ValueError("approval request input hashes must be sorted and unique")
        if any(
            not _is_sha256(item) for item in self.preflight_receipt_sha256s
        ):
            raise ValueError("approval request preflight hashes must be SHA-256")
        if (
            tuple(sorted(set(self.preflight_receipt_sha256s)))
            != self.preflight_receipt_sha256s
        ):
            raise ValueError(
                "approval request preflight hashes must be sorted and unique"
            )
        return self

    @property
    def binding_sha256(self) -> str:
        body = self.model_dump(mode="json")
        return hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


class ApprovalResolution(RuntimeContract):
    contract_version: Literal[1] = 1
    resolution_id: str = Field(min_length=1, max_length=128)
    approval_id: str = Field(min_length=1, max_length=128)
    request_binding_sha256: str = Field(pattern=_SHA256_PATTERN)
    decision: ApprovalDecision
    reason_code: str = Field(min_length=1, max_length=128)
    actor_role: Literal["user", "policy", "system"]
    resolved_at: str = Field(min_length=1, max_length=64)


class ApprovalInvalidation(RuntimeContract):
    contract_version: Literal[1] = 1
    approval_id: str = Field(min_length=1, max_length=128)
    previous_binding_sha256: str = Field(pattern=_SHA256_PATTERN)
    current_binding_sha256: str = Field(pattern=_SHA256_PATTERN)
    reason: str = Field(min_length=1, max_length=500)
    invalidated_at: str = Field(min_length=1, max_length=64)


def approval_resolution_matches(
    request: ApprovalRequest,
    resolution: ApprovalResolution,
) -> bool:
    """Return true only for the exact approved request binding."""

    return (
        resolution.decision is ApprovalDecision.APPROVED
        and resolution.approval_id == request.approval_id
        and resolution.request_binding_sha256 == request.binding_sha256
    )


class EvidenceRef(RuntimeContract):
    contract_version: Literal[1] = 1
    evidence_id: str = Field(min_length=1, max_length=128)
    evidence_kind: Literal[
        "artifact",
        "native_input",
        "native_output",
        "receipt",
        "citation",
        "provider_usage",
    ]
    subject_id: str = Field(min_length=1, max_length=128)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    reference: str = Field(min_length=1, max_length=1_000)
    captured_at: str = Field(min_length=1, max_length=64)


class ParsedMeasurement(RuntimeContract):
    name: str = Field(min_length=1, max_length=128)
    value: float
    unit: str = Field(min_length=1, max_length=64)
    convention: str = Field(min_length=1, max_length=500)


class ValidationReceipt(RuntimeContract):
    contract_version: Literal[1] = 1
    receipt_id: str = Field(min_length=1, max_length=128)
    validator_id: str = Field(min_length=1, max_length=128)
    validator_version: str = Field(min_length=1, max_length=128)
    subject_ids: tuple[str, ...]
    status: ValidationStatus
    rule_ids: tuple[str, ...] = ()
    measurements: tuple[ParsedMeasurement, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    checked_at: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _requires_subject(self) -> "ValidationReceipt":
        if not self.subject_ids:
            raise ValueError("validation receipt requires at least one subject")
        return self


class ClaimRecord(RuntimeContract):
    contract_version: Literal[1] = 1
    claim_id: str = Field(min_length=1, max_length=128)
    claim_type: ClaimType
    statement: str = Field(min_length=1, max_length=2_000)
    status: ClaimStatus
    evidence_ids: tuple[str, ...] = ()
    validation_receipt_ids: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _requires_support_for_supported_claim(self) -> "ClaimRecord":
        if self.status in {ClaimStatus.SUPPORTED, ClaimStatus.QUALIFIED} and not (
            self.evidence_ids or self.validation_receipt_ids
        ):
            raise ValueError("supported or qualified claim requires evidence")
        return self


class ReviewFinding(RuntimeContract):
    contract_version: Literal[1] = 1
    finding_id: str = Field(min_length=1, max_length=128)
    reviewer_role: Literal["chemistry", "statistics", "harness", "citation", "red_team"]
    severity: ReviewSeverity
    statement: str = Field(min_length=1, max_length=2_000)
    claim_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    arbitration_path: Literal[
        "deterministic_validation",
        "independent_recomputation",
        "human_decision",
        "unresolved",
    ]

    @model_validator(mode="after")
    def _requires_cited_evidence(self) -> "ReviewFinding":
        if not self.evidence_ids:
            raise ValueError("review finding requires at least one evidence id")
        return self


class ReportManifest(RuntimeContract):
    contract_version: Literal[1] = 1
    manifest_id: str = Field(min_length=1, max_length=128)
    task_spec_id: str = Field(min_length=1, max_length=128)
    evidence_ids: tuple[str, ...]
    validation_receipt_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    citation_ids: tuple[str, ...] = ()
    rendered_output_ids: tuple[str, ...] = ()


class BudgetExhaustion(RuntimeContract):
    contract_version: Literal[1] = 1
    budget_id: str = Field(min_length=1, max_length=128)
    dimension: Literal[
        "model_calls",
        "tokens",
        "tool_calls",
        "cost_usd",
        "wall_time_s",
        "compute_seconds",
        "retries",
    ]
    consumed: float = Field(ge=0.0)
    limit: float = Field(ge=0.0)
    observed_at: str = Field(min_length=1, max_length=64)


class PhaseCloseReceipt(RuntimeContract):
    """An explicit gate result; a red gate cannot be represented as passed."""

    contract_version: Literal[1] = 1
    phase_close_id: str = Field(min_length=1, max_length=128)
    outcome: Literal["passed", "blocked"]
    gate_status: Literal["green", "red"]
    rule_ids: tuple[str, ...] = ()
    claim_ids: tuple[str, ...] = ()
    checked_at: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _requires_consistent_gate_outcome(self) -> "PhaseCloseReceipt":
        if self.outcome == "passed" and self.gate_status != "green":
            raise ValueError("a passed phase close must have a green gate")
        if self.outcome == "blocked":
            if self.gate_status != "red":
                raise ValueError("a blocked phase close must have a red gate")
            if not self.rule_ids:
                raise ValueError("a blocked phase close requires at least one rule")
        return self


class ScientificV1Extension(RuntimeContract):
    """Optional, typed namespace carried inside an unchanged v1 event.

    The event registry validates this model without replacing the raw payload.
    That distinction preserves the v1 hash chain exactly as serialized.
    """

    version: Literal[1] = 1
    provider_capabilities: ProviderCapabilities | None = None
    task_spec: ScientificTaskSpec | None = None
    task_graph: TaskGraph | None = None
    resource_budget: ResourceBudget | None = None
    approval_request: ApprovalRequest | None = None
    approval_resolution: ApprovalResolution | None = None
    approval_invalidation: ApprovalInvalidation | None = None
    evidence: EvidenceRef | None = None
    validation: ValidationReceipt | None = None
    claim: ClaimRecord | None = None
    review_finding: ReviewFinding | None = None
    report_manifest: ReportManifest | None = None
    budget_exhaustion: BudgetExhaustion | None = None
    phase_close: PhaseCloseReceipt | None = None

    @model_validator(mode="after")
    def _requires_a_typed_record(self) -> "ScientificV1Extension":
        if not any(
            getattr(self, field_name) is not None
            for field_name in _SCIENTIFIC_V1_RECORD_FIELDS
        ):
            raise ValueError("scientific_v1 requires at least one typed record")
        return self


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


__all__ = [
    "ApprovalDecision",
    "ApprovalInvalidation",
    "ApprovalRequest",
    "ApprovalResolution",
    "BudgetExhaustion",
    "ClaimRecord",
    "ClaimStatus",
    "ClaimType",
    "EvidenceRef",
    "EvidenceRequirement",
    "GeometryFrameRef",
    "ParsedMeasurement",
    "PhaseCloseReceipt",
    "ProviderCapabilities",
    "ReportManifest",
    "ResourceBudget",
    "ReviewFinding",
    "ReviewSeverity",
    "ScientificTaskKind",
    "ScientificTaskSpec",
    "ScientificV1Extension",
    "TaskGraph",
    "TaskNode",
    "ValidationReceipt",
    "ValidationStatus",
    "approval_resolution_matches",
]
