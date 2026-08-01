"""Bounded specialist delegation and read-only review contracts.

The coordinator may use these envelopes to delegate independently verifiable
work without sharing mutable state.  Workers return immutable, content-
addressed artifacts.  The deterministic gates in this module validate scope,
budget, ownership, and merge keys; they do not execute tools, approve actions,
or let a critic repair its own finding.

This is an additive Runtime V2 contract module.  It does not change the legacy
event registry or reducer, preserving replay of existing event streams.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from enum import Enum
from typing import Any, Iterable, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from chemsmart.agent.runtime.contracts import OpaqueArtifactRef
from chemsmart.agent.runtime.harness_profiles import (
    HarnessProfile,
    resolve_harness_profile,
)


DELEGATION_SCHEMA_VERSION = "chemsmart.specialist-task.v1"
SPECIALIST_RESULT_SCHEMA_VERSION = "chemsmart.specialist-result.v1"
MERGE_RECEIPT_SCHEMA_VERSION = "chemsmart.specialist-merge-receipt.v1"
OUTPUT_SCHEMA_VALIDATION_SCHEMA_VERSION = (
    "chemsmart.output-schema-validation-receipt.v1"
)
RUNTIME_USAGE_RECEIPT_SCHEMA_VERSION = "chemsmart.runtime-usage-receipt.v1"
REVIEW_SCHEMA_VERSION = "chemsmart.review-packet.v1"
REVIEW_FINDING_SCHEMA_VERSION = "chemsmart.review-finding.v1"
REVIEW_GATE_SCHEMA_VERSION = "chemsmart.review-gate-receipt.v1"

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
_KIND = r"^[a-z][a-z0-9_.-]{0,63}$"
_SCHEMA_ID = r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$"
_SHA256 = r"^[0-9a-f]{64}$"
_TOOL_NAME = r"^[a-z][a-z0-9_]{0,127}$"
_SAFE_TEXT = r"^[^\r\n\x00]+$"

_FRONTIER_FORBIDDEN_TOOLS = frozenset(
    {
        "approve",
        "build_gaussian_settings",
        "build_job",
        "build_molecule",
        "build_orca_settings",
        "build_xtb_settings",
        "dry_run_input",
        "execute_chemsmart_command",
        "run_local",
        "submit_hpc",
        "update_project_yaml",
        "validate_runtime",
        "write_project_yaml",
    }
)

_PROPOSAL_TOOLS = frozenset(
    {
        "extract_project_protocol",
        "render_project_yaml",
        "repair_command",
        "synthesize_command",
    }
)
_FIXTURE_ONLY_TOOLS = frozenset(
    {
        "inspect_command_schema",
        "inspect_command_workflow",
        "list_workspace",
        "read_evidence",
        "validate_project_yaml",
    }
)
_NETWORK_TOOLS = frozenset({"search_literature", "retrieve_literature"})


def tool_scope_sha256(tools: Iterable[str]) -> str:
    """Bind a tool allowlist to one canonical, order-independent digest."""

    canonical = tuple(sorted(str(item) for item in tools))
    return _sha256_json({"allowed_tools": canonical})


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResourceBudget(_Contract):
    """Finite hard ceilings for one specialist or reviewer invocation."""

    max_model_tokens: int = Field(ge=0)
    max_tool_calls: int = Field(ge=0)
    max_wall_time_ms: int = Field(ge=1)
    max_compute_time_ms: int = Field(ge=0)
    max_cost_microusd: int = Field(ge=0)
    max_child_tasks: int = Field(ge=0)
    max_network_requests: int = Field(default=0, ge=0)


class ResourceUsage(_Contract):
    """Observable usage in the same integer units as ``ResourceBudget``."""

    model_tokens: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    wall_time_ms: int = Field(ge=0)
    compute_time_ms: int = Field(ge=0)
    cost_microusd: int = Field(ge=0)
    child_tasks: int = Field(ge=0)
    network_requests: int = Field(default=0, ge=0)


_BUDGET_FIELDS = (
    ("model_tokens", "max_model_tokens"),
    ("tool_calls", "max_tool_calls"),
    ("wall_time_ms", "max_wall_time_ms"),
    ("compute_time_ms", "max_compute_time_ms"),
    ("cost_microusd", "max_cost_microusd"),
    ("child_tasks", "max_child_tasks"),
    ("network_requests", "max_network_requests"),
)


def budget_rule_ids(
    usage: ResourceUsage,
    budget: ResourceBudget,
) -> tuple[str, ...]:
    """Return deterministic rules for every exceeded budget dimension."""

    return tuple(
        f"delegation.budget.{usage_field}_exceeded"
        for usage_field, budget_field in _BUDGET_FIELDS
        if getattr(usage, usage_field) > getattr(budget, budget_field)
    )


def resource_budget_sha256(budget: ResourceBudget) -> str:
    """Return the canonical public digest for a finite resource budget."""

    return _sha256_json(budget.model_dump(mode="json"))


def resource_usage_sha256(usage: ResourceUsage) -> str:
    """Return the canonical public digest for observable resource usage."""

    return _sha256_json(usage.model_dump(mode="json"))


class SpecialistRole(str, Enum):
    SOURCE_CURATOR = "source_curator"
    PROTOCOL_EXTRACTOR = "protocol_extractor"
    MOLECULAR_SYSTEM_SPECIALIST = "molecular_system_specialist"
    INDEPENDENT_SPECIES_SPECIALIST = "independent_species_specialist"
    WORKFLOW_PLANNER = "workflow_planner"
    PROJECT_COMMAND_COMPILER = "project_command_compiler"
    COMMAND_COUNTEREXAMPLE_SPECIALIST = "command_counterexample_specialist"
    CLAIM_ARTIFACT_AUDITOR = "claim_artifact_auditor"


_READ_TOOLS = frozenset({"list_workspace", "read_evidence"})
_COMMAND_INSPECTION_TOOLS = frozenset(
    {"inspect_command_schema", "inspect_command_workflow"}
)
_SPECIALIST_ROLE_TOOLS: dict[SpecialistRole, frozenset[str]] = {
    SpecialistRole.SOURCE_CURATOR: _READ_TOOLS
    | {"search_literature", "retrieve_literature"},
    SpecialistRole.PROTOCOL_EXTRACTOR: _READ_TOOLS,
    SpecialistRole.MOLECULAR_SYSTEM_SPECIALIST: _READ_TOOLS,
    SpecialistRole.INDEPENDENT_SPECIES_SPECIALIST: (
        _READ_TOOLS | _COMMAND_INSPECTION_TOOLS
    ),
    SpecialistRole.WORKFLOW_PLANNER: _READ_TOOLS | _COMMAND_INSPECTION_TOOLS,
    SpecialistRole.PROJECT_COMMAND_COMPILER: _READ_TOOLS
    | _COMMAND_INSPECTION_TOOLS
    | {
        "extract_project_protocol",
        "render_project_yaml",
        "repair_command",
        "synthesize_command",
        "validate_project_yaml",
    },
    SpecialistRole.COMMAND_COUNTEREXAMPLE_SPECIALIST: (
        _READ_TOOLS | _COMMAND_INSPECTION_TOOLS
    ),
    SpecialistRole.CLAIM_ARTIFACT_AUDITOR: (
        _READ_TOOLS | _COMMAND_INSPECTION_TOOLS | {"validate_project_yaml"}
    ),
}

_SPECIALIST_ROLE_OUTPUTS: dict[SpecialistRole, frozenset[str]] = {
    SpecialistRole.SOURCE_CURATOR: frozenset(
        {"paper.source", "paper.source_bundle", "source.receipt"}
    ),
    SpecialistRole.PROTOCOL_EXTRACTOR: frozenset(
        {"protocol.claims", "capability.gap"}
    ),
    SpecialistRole.MOLECULAR_SYSTEM_SPECIALIST: frozenset(
        {"molecular.system", "protocol.claims", "capability.gap"}
    ),
    SpecialistRole.INDEPENDENT_SPECIES_SPECIALIST: frozenset(
        {
            "molecular.system",
            "project.config",
            "command.workflow",
            "capability.gap",
        }
    ),
    SpecialistRole.WORKFLOW_PLANNER: frozenset(
        {"command.workflow", "research.graph", "capability.gap"}
    ),
    SpecialistRole.PROJECT_COMMAND_COMPILER: frozenset(
        {
            "project.config",
            "project.yaml_candidate",
            "command.workflow",
            "command.preflight",
            "capability.gap",
        }
    ),
    SpecialistRole.COMMAND_COUNTEREXAMPLE_SPECIALIST: frozenset(
        {"command.counterexample", "review.findings", "capability.gap"}
    ),
    SpecialistRole.CLAIM_ARTIFACT_AUDITOR: frozenset(
        {"claim.audit", "review.findings", "capability.gap"}
    ),
}


class ImmutableTaskInput(_Contract):
    input_id: str = Field(pattern=_IDENTIFIER)
    kind: str = Field(pattern=_KIND)
    sha256: str = Field(pattern=_SHA256)


class ExpectedOutput(_Contract):
    output_id: str = Field(pattern=_IDENTIFIER)
    artifact_kind: str = Field(pattern=_KIND)
    schema_id: str = Field(pattern=_SCHEMA_ID)
    validator_id: str = Field(pattern=_IDENTIFIER)
    validator_version: str = Field(min_length=1, max_length=80, pattern=_SAFE_TEXT)
    validator_registry_sha256: str = Field(pattern=_SHA256)
    mutable: Literal[False] = False


class CompletionPredicate(_Contract):
    """Deterministic success condition for one specialist packet."""

    predicate_id: str = Field(pattern=_IDENTIFIER)
    required_output_ids: tuple[str, ...] = Field(min_length=1)
    require_schema_validation: Literal[True] = True
    require_no_unresolved_rule_ids: Literal[True] = True

    @field_validator("required_output_ids")
    @classmethod
    def _canonical_output_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _require_unique(list(value), "completion required_output_ids")
        _require_pattern(
            list(value),
            _IDENTIFIER,
            "completion required_output_ids",
        )
        return tuple(sorted(value))


class SpecialistTaskPacket(_Contract):
    """Immutable coordinator-to-specialist work envelope."""

    schema_version: Literal[DELEGATION_SCHEMA_VERSION] = DELEGATION_SCHEMA_VERSION
    task_id: str = Field(pattern=_IDENTIFIER)
    parent_task_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    parent_task_packet_sha256: str | None = Field(default=None, pattern=_SHA256)
    coordinator_id: str = Field(pattern=_IDENTIFIER)
    specialist_id: str = Field(pattern=_IDENTIFIER)
    role: SpecialistRole
    objective: str = Field(min_length=1, max_length=1000, pattern=_SAFE_TEXT)
    harness_profile: HarnessProfile
    delegation_depth: Literal[1, 2] = 1
    immutable_inputs: tuple[ImmutableTaskInput, ...] = Field(min_length=1)
    source_scope_ids: tuple[str, ...] = Field(min_length=1)
    dependencies: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    tool_scope_sha256: str = Field(pattern=_SHA256)
    permission_scope: Literal["read_only", "proposal_only", "fixture_only"]
    budget: ResourceBudget
    usage_observer_id: str = Field(pattern=_IDENTIFIER)
    usage_observer_version: str = Field(
        min_length=1,
        max_length=80,
        pattern=_SAFE_TEXT,
    )
    usage_observer_registry_sha256: str = Field(pattern=_SHA256)
    expected_outputs: tuple[ExpectedOutput, ...] = Field(min_length=1)
    completion_predicate: CompletionPredicate
    write_owner: str = Field(pattern=_IDENTIFIER)
    merge_key: str = Field(pattern=_IDENTIFIER)
    merge_order: int = Field(ge=0)
    max_repairs: int = Field(default=0, ge=0, le=2)
    can_approve: Literal[False] = False
    can_execute: Literal[False] = False

    @field_validator("immutable_inputs")
    @classmethod
    def _canonical_inputs(
        cls, value: tuple[ImmutableTaskInput, ...]
    ) -> tuple[ImmutableTaskInput, ...]:
        _require_unique(
            [item.input_id for item in value],
            "immutable input_id values",
        )
        return tuple(sorted(value, key=lambda item: item.input_id))

    @field_validator("source_scope_ids", "dependencies")
    @classmethod
    def _canonical_identifiers(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _require_unique(list(value), "specialist identifiers")
        _require_pattern(list(value), _IDENTIFIER, "specialist identifiers")
        return tuple(sorted(value))

    @field_validator("allowed_tools")
    @classmethod
    def _canonical_tools(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _require_unique(list(value), "allowed_tools")
        _require_pattern(list(value), _TOOL_NAME, "allowed_tools")
        return tuple(sorted(value))

    @field_validator("expected_outputs")
    @classmethod
    def _canonical_outputs(
        cls, value: tuple[ExpectedOutput, ...]
    ) -> tuple[ExpectedOutput, ...]:
        _require_unique(
            [item.output_id for item in value],
            "expected output_id values",
        )
        return tuple(sorted(value, key=lambda item: item.output_id))

    @model_validator(mode="after")
    def _packet_is_independent_and_bounded(self) -> "SpecialistTaskPacket":
        if self.coordinator_id == self.specialist_id:
            raise ValueError("specialist must be independent from the coordinator")
        if self.write_owner != self.specialist_id:
            raise ValueError("the assigned specialist must own its proposed outputs")
        input_ids = {item.input_id for item in self.immutable_inputs}
        unknown_scope = sorted(set(self.source_scope_ids).difference(input_ids))
        if unknown_scope:
            raise ValueError(
                "source_scope_ids must reference immutable input IDs: "
                + ", ".join(unknown_scope)
            )
        if self.tool_scope_sha256 != tool_scope_sha256(self.allowed_tools):
            raise ValueError("tool_scope_sha256 does not bind allowed_tools")
        expected_output_ids = {
            item.output_id for item in self.expected_outputs
        }
        if set(self.completion_predicate.required_output_ids) != expected_output_ids:
            raise ValueError(
                "completion predicate must require every expected output exactly once"
            )
        forbidden = sorted(_FRONTIER_FORBIDDEN_TOOLS.intersection(self.allowed_tools))
        if forbidden:
            raise ValueError(
                "specialist packet exposes forbidden frontier tools: "
                + ", ".join(forbidden)
            )
        role_tools = _SPECIALIST_ROLE_TOOLS[self.role]
        unknown_tools = sorted(set(self.allowed_tools).difference(role_tools))
        if unknown_tools:
            raise ValueError(
                f"{self.role.value} exposes tools outside its allowlist: "
                + ", ".join(unknown_tools)
            )
        if self.permission_scope == "read_only":
            scope_tools = role_tools.difference(_PROPOSAL_TOOLS)
        elif self.permission_scope == "fixture_only":
            scope_tools = role_tools.intersection(_FIXTURE_ONLY_TOOLS)
        else:
            scope_tools = role_tools
        scope_violations = sorted(set(self.allowed_tools).difference(scope_tools))
        if scope_violations:
            raise ValueError(
                f"{self.permission_scope} permission exposes tools outside its scope: "
                + ", ".join(scope_violations)
            )
        if (
            _NETWORK_TOOLS.intersection(self.allowed_tools)
            and self.budget.max_network_requests == 0
        ):
            raise ValueError(
                "literature tools require a finite positive network-request budget"
            )
        role_outputs = _SPECIALIST_ROLE_OUTPUTS[self.role]
        invalid_outputs = sorted(
            {
                item.artifact_kind
                for item in self.expected_outputs
                if item.artifact_kind not in role_outputs
            }
        )
        if invalid_outputs:
            raise ValueError(
                f"{self.role.value} cannot own these output kinds: "
                + ", ".join(invalid_outputs)
            )
        expected_depth = 2 if self.parent_task_id is not None else 1
        if self.delegation_depth != expected_depth:
            raise ValueError(
                "delegation_depth must match the presence of parent_task_id"
            )
        if self.parent_task_id is None and self.parent_task_packet_sha256 is not None:
            raise ValueError("depth-1 task forbids parent_task_packet_sha256")
        if self.parent_task_id is not None and self.parent_task_packet_sha256 is None:
            raise ValueError("depth-2 task requires parent_task_packet_sha256")
        if self.parent_task_id == self.task_id:
            raise ValueError("specialist task cannot be its own parent")
        profile = resolve_harness_profile(self.harness_profile)
        if self.delegation_depth > profile.max_delegation_depth:
            raise ValueError(
                f"{self.harness_profile.value} does not permit this delegation depth"
            )
        if (
            self.delegation_depth >= profile.max_delegation_depth
            and self.budget.max_child_tasks
        ):
            raise ValueError("a leaf specialist budget cannot permit child tasks")
        return self


def specialist_task_packet_sha256(packet: SpecialistTaskPacket) -> str:
    return _sha256_json(packet.model_dump(mode="json"))


class OwnedArtifactRef(_Contract):
    """Path-free specialist output with a single declared owner."""

    output_id: str = Field(pattern=_IDENTIFIER)
    artifact_id: str = Field(pattern=_IDENTIFIER)
    kind: str = Field(pattern=_KIND)
    schema_id: str = Field(pattern=_SCHEMA_ID)
    sha256: str = Field(pattern=_SHA256)
    size_bytes: int = Field(ge=0)
    owner_id: str = Field(pattern=_IDENTIFIER)
    mutable: Literal[False] = False


class OutputSchemaValidationReceipt(_Contract):
    """Full content-addressed observation of one output-schema validation."""

    schema_version: Literal[OUTPUT_SCHEMA_VALIDATION_SCHEMA_VERSION] = (
        OUTPUT_SCHEMA_VALIDATION_SCHEMA_VERSION
    )
    output_id: str = Field(pattern=_IDENTIFIER)
    artifact_id: str = Field(pattern=_IDENTIFIER)
    artifact_sha256: str = Field(pattern=_SHA256)
    schema_id: str = Field(pattern=_SCHEMA_ID)
    validator_id: str = Field(pattern=_IDENTIFIER)
    validator_version: str = Field(min_length=1, max_length=80, pattern=_SAFE_TEXT)
    validator_registry_sha256: str = Field(pattern=_SHA256)
    validation_receipt_id: str = Field(pattern=_IDENTIFIER)
    validation_receipt_sha256: str = Field(pattern=_SHA256)
    status: Literal["valid", "invalid"]
    rule_ids: tuple[str, ...] = ()

    @field_validator("rule_ids")
    @classmethod
    def _canonical_rule_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _require_unique(list(value), "schema-validation rule_ids")
        _require_pattern(list(value), _IDENTIFIER, "schema-validation rule_ids")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def _receipt_is_content_addressed(self) -> "OutputSchemaValidationReceipt":
        if self.status == "valid" and self.rule_ids:
            raise ValueError("valid schema validation cannot retain rule_ids")
        if self.status == "invalid" and not self.rule_ids:
            raise ValueError("invalid schema validation requires rule_ids")
        if self.validation_receipt_sha256 != output_schema_validation_receipt_sha256(
            self
        ):
            raise ValueError("schema-validation receipt digest mismatch")
        return self


# Backward-compatible import name; the v1 value is now a full receipt, not a ref.
OutputSchemaValidationRef = OutputSchemaValidationReceipt


class RuntimeObservedUsageReceipt(_Contract):
    """Content-addressed usage emitted by the runtime observer, not a worker."""

    schema_version: Literal[RUNTIME_USAGE_RECEIPT_SCHEMA_VERSION] = (
        RUNTIME_USAGE_RECEIPT_SCHEMA_VERSION
    )
    usage_receipt_id: str = Field(pattern=_IDENTIFIER)
    usage_receipt_sha256: str = Field(pattern=_SHA256)
    observer_id: str = Field(pattern=_IDENTIFIER)
    observer_version: str = Field(min_length=1, max_length=80, pattern=_SAFE_TEXT)
    observer_registry_sha256: str = Field(pattern=_SHA256)
    task_id: str = Field(pattern=_IDENTIFIER)
    task_packet_sha256: str = Field(pattern=_SHA256)
    result_id: str = Field(pattern=_IDENTIFIER)
    provider_request_ids: tuple[str, ...] = Field(min_length=1)
    tool_call_ids: tuple[str, ...] = ()
    network_request_ids: tuple[str, ...] = ()
    tools_used: tuple[str, ...] = ()
    usage: ResourceUsage
    repair_count: int = Field(ge=0)

    @field_validator(
        "provider_request_ids",
        "tool_call_ids",
        "network_request_ids",
    )
    @classmethod
    def _canonical_observation_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _require_unique(list(value), "runtime usage observation IDs")
        _require_pattern(list(value), _IDENTIFIER, "runtime usage observation IDs")
        return tuple(sorted(value))

    @field_validator("tools_used")
    @classmethod
    def _canonical_observed_tools(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _require_unique(list(value), "runtime usage tools")
        _require_pattern(list(value), _TOOL_NAME, "runtime usage tools")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def _counts_and_digest_are_observed(self) -> "RuntimeObservedUsageReceipt":
        if len(self.tool_call_ids) != self.usage.tool_calls:
            raise ValueError("tool_call_ids do not match observed tool-call usage")
        if len(self.network_request_ids) != self.usage.network_requests:
            raise ValueError(
                "network_request_ids do not match observed network-request usage"
            )
        if self.usage_receipt_sha256 != runtime_usage_receipt_sha256(self):
            raise ValueError("runtime usage receipt digest mismatch")
        return self


def output_schema_validation_receipt_sha256(
    receipt: OutputSchemaValidationReceipt | dict[str, Any],
) -> str:
    """Hash every schema-validation field except the digest itself."""

    if isinstance(receipt, BaseModel):
        body = receipt.model_dump(
            mode="json",
            exclude={"validation_receipt_sha256"},
        )
    else:
        body = dict(receipt)
        body.pop("validation_receipt_sha256", None)
        body.setdefault(
            "schema_version",
            OUTPUT_SCHEMA_VALIDATION_SCHEMA_VERSION,
        )
    return _sha256_json(body)


def runtime_usage_receipt_sha256(
    receipt: RuntimeObservedUsageReceipt | dict[str, Any],
) -> str:
    """Hash every runtime-observed usage field except the digest itself."""

    if isinstance(receipt, BaseModel):
        body = receipt.model_dump(
            mode="json",
            exclude={"usage_receipt_sha256"},
        )
    else:
        body = dict(receipt)
        body.pop("usage_receipt_sha256", None)
        body.setdefault("schema_version", RUNTIME_USAGE_RECEIPT_SCHEMA_VERSION)
    return _sha256_json(body)


class SpecialistResultStatus(str, Enum):
    COMPLETE = "complete"
    BLOCKED = "blocked"
    FAILED = "failed"


class SpecialistResultPacket(_Contract):
    """Observable specialist output; persuasive hidden rationale is excluded."""

    schema_version: Literal[SPECIALIST_RESULT_SCHEMA_VERSION] = (
        SPECIALIST_RESULT_SCHEMA_VERSION
    )
    result_id: str = Field(pattern=_IDENTIFIER)
    task_id: str = Field(pattern=_IDENTIFIER)
    task_packet_sha256: str = Field(pattern=_SHA256)
    specialist_id: str = Field(pattern=_IDENTIFIER)
    status: SpecialistResultStatus
    merge_key: str = Field(pattern=_IDENTIFIER)
    usage: ResourceUsage
    usage_receipt: RuntimeObservedUsageReceipt
    repair_count: int = Field(default=0, ge=0)
    tools_used: tuple[str, ...] = ()
    output_artifacts: tuple[OwnedArtifactRef, ...] = ()
    output_schema_validations: tuple[OutputSchemaValidationRef, ...] = ()
    unresolved_rule_ids: tuple[str, ...] = ()
    public_summary: str = Field(min_length=1, max_length=1000, pattern=_SAFE_TEXT)
    can_approve: Literal[False] = False
    can_execute: Literal[False] = False

    @field_validator("tools_used", "unresolved_rule_ids")
    @classmethod
    def _canonical_string_sets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _require_unique(list(value), "specialist result identifiers")
        return tuple(sorted(value))

    @field_validator("output_artifacts")
    @classmethod
    def _canonical_artifacts(
        cls, value: tuple[OwnedArtifactRef, ...]
    ) -> tuple[OwnedArtifactRef, ...]:
        return tuple(
            sorted(value, key=lambda item: (item.output_id, item.artifact_id))
        )

    @field_validator("output_schema_validations")
    @classmethod
    def _canonical_schema_validations(
        cls,
        value: tuple[OutputSchemaValidationRef, ...],
    ) -> tuple[OutputSchemaValidationRef, ...]:
        _require_unique(
            [item.output_id for item in value],
            "schema-validation output_id values",
        )
        _require_unique(
            [item.validation_receipt_id for item in value],
            "schema-validation receipt IDs",
        )
        _require_unique(
            [item.validation_receipt_sha256 for item in value],
            "schema-validation receipt digests",
        )
        return tuple(
            sorted(
                value,
                key=lambda item: (
                    item.output_id,
                    item.artifact_id,
                    item.validation_receipt_id,
                ),
            )
        )

    @model_validator(mode="after")
    def _terminal_status_has_evidence(self) -> "SpecialistResultPacket":
        _require_unique(list(self.tools_used), "tools_used")
        _require_pattern(list(self.tools_used), _TOOL_NAME, "tools_used")
        _require_unique(
            [item.artifact_id for item in self.output_artifacts],
            "output artifact_id values",
        )
        _require_unique(
            [item.output_id for item in self.output_artifacts],
            "output output_id values",
        )
        _require_unique(list(self.unresolved_rule_ids), "unresolved_rule_ids")
        _require_pattern(
            list(self.unresolved_rule_ids), _IDENTIFIER, "unresolved_rule_ids"
        )
        usage_receipt = self.usage_receipt
        if (
            usage_receipt.task_id != self.task_id
            or usage_receipt.task_packet_sha256 != self.task_packet_sha256
            or usage_receipt.result_id != self.result_id
            or usage_receipt.usage != self.usage
            or usage_receipt.repair_count != self.repair_count
            or usage_receipt.tools_used != self.tools_used
        ):
            raise ValueError(
                "runtime usage receipt must bind the exact specialist result"
            )
        if self.status is SpecialistResultStatus.COMPLETE:
            if not self.output_artifacts:
                raise ValueError("complete specialist result requires artifacts")
            if self.unresolved_rule_ids:
                raise ValueError("complete specialist result cannot be unresolved")
            artifacts = {item.output_id: item for item in self.output_artifacts}
            validations = {
                item.output_id: item for item in self.output_schema_validations
            }
            if set(validations) != set(artifacts):
                raise ValueError(
                    "complete specialist result requires exactly one "
                    "schema-validation ref per output artifact"
                )
            for output_id in sorted(artifacts):
                artifact = artifacts[output_id]
                validation = validations[output_id]
                if (
                    validation.artifact_id != artifact.artifact_id
                    or validation.artifact_sha256 != artifact.sha256
                    or validation.schema_id != artifact.schema_id
                    or validation.status != "valid"
                ):
                    raise ValueError(
                        "schema-validation ref must bind its output artifact"
                    )
        elif not self.unresolved_rule_ids:
            raise ValueError("blocked or failed result requires a stable rule_id")
        return self


def specialist_result_packet_sha256(packet: SpecialistResultPacket) -> str:
    """Return the full public result-packet digest used by merge receipts."""

    return _sha256_json(packet.model_dump(mode="json"))


class MergeFinding(_Contract):
    rule_id: str = Field(pattern=_IDENTIFIER)
    task_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    field: str = Field(pattern=_IDENTIFIER)
    expected: str = Field(min_length=1, max_length=500, pattern=_SAFE_TEXT)
    observed: str = Field(min_length=1, max_length=500, pattern=_SAFE_TEXT)


class SpecialistMergeReceipt(_Contract):
    """All-or-nothing deterministic join receipt."""

    schema_version: Literal[MERGE_RECEIPT_SCHEMA_VERSION] = (
        MERGE_RECEIPT_SCHEMA_VERSION
    )
    status: Literal["accepted", "rejected"]
    ordered_task_ids: tuple[str, ...]
    task_packet_sha256s: tuple[str, ...]
    result_packet_sha256s: tuple[str, ...]
    merged_artifacts: tuple[OwnedArtifactRef, ...]
    findings: tuple[MergeFinding, ...]
    merge_sha256: str = Field(pattern=_SHA256)
    approval_eligible: Literal[False] = False

    @field_validator("merged_artifacts")
    @classmethod
    def _canonical_merged_artifacts(
        cls,
        value: tuple[OwnedArtifactRef, ...],
    ) -> tuple[OwnedArtifactRef, ...]:
        _require_unique(
            [item.artifact_id for item in value],
            "merged artifact IDs",
        )
        return tuple(
            sorted(
                value,
                key=lambda item: (
                    item.output_id,
                    item.artifact_id,
                    item.sha256,
                ),
            )
        )

    @field_validator("findings")
    @classmethod
    def _canonical_findings(
        cls,
        value: tuple[MergeFinding, ...],
    ) -> tuple[MergeFinding, ...]:
        return tuple(sorted(value, key=_merge_finding_sort_key))

    @field_validator("task_packet_sha256s", "result_packet_sha256s")
    @classmethod
    def _valid_packet_digests(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _require_pattern(list(value), _SHA256, "merge packet digests")
        return value

    @model_validator(mode="after")
    def _status_matches_merge_surface(self) -> "SpecialistMergeReceipt":
        if self.status == "accepted":
            _require_unique(list(self.ordered_task_ids), "ordered_task_ids")
            if self.findings:
                raise ValueError("accepted specialist merge cannot retain findings")
            if not self.ordered_task_ids or not self.merged_artifacts:
                raise ValueError(
                    "accepted specialist merge requires tasks and artifacts"
                )
            if len(self.result_packet_sha256s) != len(self.ordered_task_ids):
                raise ValueError(
                    "accepted specialist merge requires one result per task"
                )
        if self.status == "rejected" and self.merged_artifacts:
            raise ValueError("rejected specialist merge cannot expose artifacts")
        if len(self.ordered_task_ids) != len(self.task_packet_sha256s):
            raise ValueError("every ordered task requires its task-packet digest")
        expected_sha256 = _merge_receipt_surface_sha256(
            status=self.status,
            ordered_task_ids=self.ordered_task_ids,
            task_packet_sha256s=self.task_packet_sha256s,
            result_packet_sha256s=self.result_packet_sha256s,
            merged_artifacts=self.merged_artifacts,
            findings=self.findings,
        )
        if self.merge_sha256 != expected_sha256:
            raise ValueError("merge_sha256 does not bind the full receipt surface")
        return self


def specialist_merge_receipt_sha256(receipt: SpecialistMergeReceipt) -> str:
    """Return a content address for the complete immutable merge receipt."""

    return _sha256_json(receipt.model_dump(mode="json"))


def deterministic_merge_gate(
    task_packets: Sequence[SpecialistTaskPacket],
    result_packets: Sequence[SpecialistResultPacket],
) -> SpecialistMergeReceipt:
    """Validate and deterministically order specialist outputs.

    The gate is deliberately all-or-nothing.  A rejected join exposes no
    merged artifact list, preventing a coordinator from silently consuming a
    partial or over-budget result.
    """

    tasks = sorted(
        task_packets,
        key=lambda item: (
            item.merge_order,
            item.task_id,
            specialist_task_packet_sha256(item),
        ),
    )
    results = sorted(
        result_packets,
        key=lambda item: (
            item.task_id,
            item.result_id,
            specialist_result_packet_sha256(item),
        ),
    )
    findings: list[MergeFinding] = []

    if not tasks:
        findings.append(
            _merge_finding(
                "delegation.merge.task_missing",
                None,
                "task_id",
                "at least one dispatched task",
                "missing",
            )
        )

    task_counts = Counter(item.task_id for item in tasks)
    result_counts = Counter(item.task_id for item in results)
    for task_id in sorted(key for key, count in task_counts.items() if count > 1):
        findings.append(
            _merge_finding(
                "delegation.merge.duplicate_task",
                task_id,
                "task_id",
                "one immutable task packet; retries require a new task_id",
                str(task_counts[task_id]),
            )
        )
    for task_id in sorted(key for key, count in result_counts.items() if count > 1):
        findings.append(
            _merge_finding(
                "delegation.merge.duplicate_result",
                task_id,
                "task_id",
                "one result packet",
                str(result_counts[task_id]),
            )
        )

    task_by_id = {item.task_id: item for item in tasks}
    result_by_id = {item.task_id: item for item in results}
    for task_id in sorted(set(result_by_id).difference(task_by_id)):
        findings.append(
            _merge_finding(
                "delegation.merge.unexpected_result",
                task_id,
                "task_id",
                "a dispatched task_id",
                task_id,
            )
        )

    child_tasks_by_parent: dict[str, list[SpecialistTaskPacket]] = {}
    for task in tasks:
        if task.parent_task_id is not None:
            child_tasks_by_parent.setdefault(task.parent_task_id, []).append(task)
            parent = task_by_id.get(task.parent_task_id)
            if parent is None:
                findings.append(
                    _merge_finding(
                        "delegation.merge.parent_task_missing",
                        task.task_id,
                        "parent_task_id",
                        "a depth-1 parent in the same immutable merge batch",
                        task.parent_task_id,
                    )
                )
            else:
                if parent.delegation_depth != 1:
                    findings.append(
                        _merge_finding(
                            "delegation.merge.parent_depth_invalid",
                            task.task_id,
                            "parent_task_id",
                            "a depth-1 parent task",
                            f"depth-{parent.delegation_depth}",
                        )
                    )
                if task.coordinator_id != parent.specialist_id:
                    findings.append(
                        _merge_finding(
                            "delegation.merge.parent_coordinator_mismatch",
                            task.task_id,
                            "coordinator_id",
                            parent.specialist_id,
                            task.coordinator_id,
                        )
                    )
                parent_sha256 = specialist_task_packet_sha256(parent)
                if task.parent_task_packet_sha256 != parent_sha256:
                    findings.append(
                        _merge_finding(
                            "delegation.merge.parent_digest_mismatch",
                            task.task_id,
                            "parent_task_packet_sha256",
                            parent_sha256,
                            str(task.parent_task_packet_sha256),
                        )
                    )
                if parent.merge_order >= task.merge_order:
                    findings.append(
                        _merge_finding(
                            "delegation.merge.parent_order_invalid",
                            task.task_id,
                            "merge_order",
                            f"greater than parent {parent.task_id}",
                            str(task.merge_order),
                        )
                    )

        if task.task_id in task.dependencies:
            findings.append(
                _merge_finding(
                    "delegation.merge.self_dependency",
                    task.task_id,
                    "dependencies",
                    "no self dependency",
                    task.task_id,
                )
            )
        for dependency in sorted(task.dependencies):
            upstream = task_by_id.get(dependency)
            if upstream is None:
                findings.append(
                    _merge_finding(
                        "delegation.merge.dependency_unknown",
                        task.task_id,
                        "dependencies",
                        "a task in the same immutable merge batch",
                        dependency,
                    )
                )
            elif upstream.merge_order >= task.merge_order:
                findings.append(
                    _merge_finding(
                        "delegation.merge.dependency_order_invalid",
                        task.task_id,
                        "merge_order",
                        f"greater than dependency {dependency}",
                        str(task.merge_order),
                    )
                )

    for task_id in _cyclic_task_ids(tasks):
        findings.append(
            _merge_finding(
                "delegation.merge.task_graph_cycle",
                task_id,
                "dependencies",
                "an acyclic dependency and parent graph",
                "cycle detected",
            )
        )

    parent_ids = {
        item.task_id for item in tasks if item.delegation_depth == 1
    }.union(child_tasks_by_parent)
    for parent_id in sorted(parent_ids):
        parent = task_by_id.get(parent_id)
        if parent is None:
            continue
        children = sorted(
            child_tasks_by_parent.get(parent_id, []),
            key=lambda item: (item.merge_order, item.task_id),
        )
        if len(children) > parent.budget.max_child_tasks:
            findings.append(
                _merge_finding(
                    "delegation.merge.parent_child_limit_exceeded",
                    parent.task_id,
                    "budget.max_child_tasks",
                    str(parent.budget.max_child_tasks),
                    str(len(children)),
                )
            )

        family_results: list[SpecialistResultPacket] = []
        for family_task in (parent, *children):
            family_result = result_by_id.get(family_task.task_id)
            if (
                family_result is not None
                and task_counts[family_task.task_id] == 1
                and result_counts[family_task.task_id] == 1
            ):
                family_results.append(family_result)
        if len(family_results) != len(children) + 1:
            continue
        parent_result = result_by_id[parent.task_id]
        if parent_result.usage.child_tasks != len(children):
            findings.append(
                _merge_finding(
                    "delegation.merge.parent_child_usage_mismatch",
                    parent.task_id,
                    "usage.child_tasks",
                    str(len(children)),
                    str(parent_result.usage.child_tasks),
                )
            )
        aggregate = _aggregate_resource_usage(
            item.usage for item in family_results
        )
        for usage_field, budget_field in _BUDGET_FIELDS:
            if getattr(aggregate, usage_field) > getattr(
                parent.budget,
                budget_field,
            ):
                findings.append(
                    _merge_finding(
                        f"delegation.parent_budget.{usage_field}_exceeded",
                        parent.task_id,
                        budget_field,
                        str(getattr(parent.budget, budget_field)),
                        str(getattr(aggregate, usage_field)),
                    )
                )

    accepted_artifacts: list[OwnedArtifactRef] = []
    artifact_owners: dict[str, tuple[str, str]] = {}
    output_owners: dict[str, str] = {}
    validation_receipt_owners: dict[str, str] = {}
    merge_keys: dict[str, str] = {}
    for task in tasks:
        if task_counts[task.task_id] != 1:
            continue
        result = result_by_id.get(task.task_id)
        if result is None:
            findings.append(
                _merge_finding(
                    "delegation.merge.result_missing",
                    task.task_id,
                    "task_id",
                    "one result packet",
                    "missing",
                )
            )
            continue
        if result_counts[result.task_id] != 1:
            continue
        _validate_result_for_task(task, result, findings)

        previous_task = merge_keys.get(task.merge_key)
        if previous_task is not None:
            findings.append(
                _merge_finding(
                    "delegation.merge.merge_key_collision",
                    task.task_id,
                    "merge_key",
                    "a unique merge key",
                    f"shared with {previous_task}",
                )
            )
        else:
            merge_keys[task.merge_key] = task.task_id

        for artifact in result.output_artifacts:
            previous = artifact_owners.get(artifact.artifact_id)
            if previous is not None:
                findings.append(
                    _merge_finding(
                        "delegation.merge.artifact_owner_collision",
                        task.task_id,
                        "artifact_id",
                        "one artifact owner and digest",
                        f"already owned by {previous[0]}",
                    )
                )
            else:
                artifact_owners[artifact.artifact_id] = (
                    artifact.owner_id,
                    artifact.sha256,
                )
            previous_output_owner = output_owners.get(artifact.output_id)
            if previous_output_owner is not None:
                findings.append(
                    _merge_finding(
                        "delegation.merge.output_id_collision",
                        task.task_id,
                        "output_id",
                        "one output binding in the merge batch",
                        f"already returned by {previous_output_owner}",
                    )
                )
            else:
                output_owners[artifact.output_id] = task.task_id
            accepted_artifacts.append(artifact)
        for validation in result.output_schema_validations:
            previous_receipt_owner = validation_receipt_owners.get(
                validation.validation_receipt_id
            )
            if previous_receipt_owner is not None:
                findings.append(
                    _merge_finding(
                        "delegation.merge.schema_validation_receipt_collision",
                        task.task_id,
                        "validation_receipt_id",
                        "one validation receipt ID in the merge batch",
                        f"already returned by {previous_receipt_owner}",
                    )
                )
            else:
                validation_receipt_owners[
                    validation.validation_receipt_id
                ] = task.task_id

    ordered_task_ids = tuple(item.task_id for item in tasks)
    task_packet_sha256s = tuple(
        specialist_task_packet_sha256(item) for item in tasks
    )
    result_packet_sha256s = tuple(
        specialist_result_packet_sha256(item) for item in results
    )
    canonical_findings = tuple(sorted(findings, key=_merge_finding_sort_key))
    if findings:
        merge_sha256 = _merge_receipt_surface_sha256(
            status="rejected",
            ordered_task_ids=ordered_task_ids,
            task_packet_sha256s=task_packet_sha256s,
            result_packet_sha256s=result_packet_sha256s,
            merged_artifacts=(),
            findings=canonical_findings,
        )
        return SpecialistMergeReceipt(
            status="rejected",
            ordered_task_ids=ordered_task_ids,
            task_packet_sha256s=task_packet_sha256s,
            result_packet_sha256s=result_packet_sha256s,
            merged_artifacts=(),
            findings=canonical_findings,
            merge_sha256=merge_sha256,
        )
    canonical_artifacts = tuple(
        sorted(
            accepted_artifacts,
            key=lambda item: (item.output_id, item.artifact_id, item.sha256),
        )
    )
    merge_sha256 = _merge_receipt_surface_sha256(
        status="accepted",
        ordered_task_ids=ordered_task_ids,
        task_packet_sha256s=task_packet_sha256s,
        result_packet_sha256s=result_packet_sha256s,
        merged_artifacts=canonical_artifacts,
        findings=(),
    )
    return SpecialistMergeReceipt(
        status="accepted",
        ordered_task_ids=ordered_task_ids,
        task_packet_sha256s=task_packet_sha256s,
        result_packet_sha256s=result_packet_sha256s,
        merged_artifacts=canonical_artifacts,
        findings=(),
        merge_sha256=merge_sha256,
    )


def _validate_result_for_task(
    task: SpecialistTaskPacket,
    result: SpecialistResultPacket,
    findings: list[MergeFinding],
) -> None:
    comparisons = (
        (
            "delegation.merge.packet_digest_mismatch",
            "task_packet_sha256",
            specialist_task_packet_sha256(task),
            result.task_packet_sha256,
        ),
        (
            "delegation.merge.specialist_mismatch",
            "specialist_id",
            task.specialist_id,
            result.specialist_id,
        ),
        (
            "delegation.merge.merge_key_mismatch",
            "merge_key",
            task.merge_key,
            result.merge_key,
        ),
        (
            "delegation.merge.usage_observer_mismatch",
            "usage_receipt.observer_id",
            task.usage_observer_id,
            result.usage_receipt.observer_id,
        ),
        (
            "delegation.merge.usage_observer_version_mismatch",
            "usage_receipt.observer_version",
            task.usage_observer_version,
            result.usage_receipt.observer_version,
        ),
        (
            "delegation.merge.usage_observer_registry_mismatch",
            "usage_receipt.observer_registry_sha256",
            task.usage_observer_registry_sha256,
            result.usage_receipt.observer_registry_sha256,
        ),
    )
    for rule_id, field, expected, observed in comparisons:
        if expected != observed:
            findings.append(
                _merge_finding(rule_id, task.task_id, field, expected, observed)
            )
    if result.status is not SpecialistResultStatus.COMPLETE:
        findings.append(
            _merge_finding(
                "delegation.merge.result_not_complete",
                task.task_id,
                "status",
                SpecialistResultStatus.COMPLETE.value,
                result.status.value,
            )
        )
    for rule_id in budget_rule_ids(result.usage, task.budget):
        findings.append(
            _merge_finding(
                rule_id,
                task.task_id,
                "budget",
                "usage within every finite ceiling",
                "exceeded",
            )
        )
    if result.repair_count > task.max_repairs:
        findings.append(
            _merge_finding(
                "delegation.merge.repair_budget_exceeded",
                task.task_id,
                "repair_count",
                f"at most {task.max_repairs}",
                str(result.repair_count),
            )
        )
    unexpected_tools = sorted(set(result.tools_used).difference(task.allowed_tools))
    if unexpected_tools:
        findings.append(
            _merge_finding(
                "delegation.merge.tool_scope_exceeded",
                task.task_id,
                "tools_used",
                "subset of allowed_tools",
                ", ".join(unexpected_tools),
            )
        )

    expected_outputs = {item.output_id: item for item in task.expected_outputs}
    observed_outputs = {item.output_id: item for item in result.output_artifacts}
    observed_validations = {
        item.output_id: item for item in result.output_schema_validations
    }
    for output_id in sorted(set(expected_outputs).difference(observed_outputs)):
        findings.append(
            _merge_finding(
                "delegation.merge.output_missing",
                task.task_id,
                "output_id",
                output_id,
                "missing",
            )
        )
    for output_id in sorted(set(observed_outputs).difference(expected_outputs)):
        findings.append(
            _merge_finding(
                "delegation.merge.output_unexpected",
                task.task_id,
                "output_id",
                "a declared output_id",
                output_id,
            )
        )
    for output_id in sorted(set(expected_outputs).difference(observed_validations)):
        findings.append(
            _merge_finding(
                "delegation.merge.schema_validation_missing",
                task.task_id,
                "output_schema_validations",
                output_id,
                "missing",
            )
        )
    for output_id in sorted(set(observed_validations).difference(expected_outputs)):
        findings.append(
            _merge_finding(
                "delegation.merge.schema_validation_unexpected",
                task.task_id,
                "output_schema_validations",
                "a declared output_id",
                output_id,
            )
        )
    for output_id in sorted(set(expected_outputs).intersection(observed_outputs)):
        expected = expected_outputs[output_id]
        observed = observed_outputs[output_id]
        output_comparisons: tuple[tuple[str, str, Any, Any], ...] = (
            (
                "delegation.merge.output_kind_mismatch",
                "kind",
                expected.artifact_kind,
                observed.kind,
            ),
            (
                "delegation.merge.output_schema_mismatch",
                "schema_id",
                expected.schema_id,
                observed.schema_id,
            ),
            (
                "delegation.merge.output_mutability_mismatch",
                "mutable",
                expected.mutable,
                observed.mutable,
            ),
            (
                "delegation.merge.output_owner_mismatch",
                "owner_id",
                task.write_owner,
                observed.owner_id,
            ),
        )
        for rule_id, field, expected_value, observed_value in output_comparisons:
            if expected_value != observed_value:
                findings.append(
                    _merge_finding(
                        rule_id,
                        task.task_id,
                        field,
                        str(expected_value),
                        str(observed_value),
                    )
                )
        validation = observed_validations.get(output_id)
        if validation is None:
            continue
        validation_comparisons: tuple[tuple[str, str, Any, Any], ...] = (
            (
                "delegation.merge.schema_validation_artifact_id_mismatch",
                "artifact_id",
                observed.artifact_id,
                validation.artifact_id,
            ),
            (
                "delegation.merge.schema_validation_artifact_digest_mismatch",
                "artifact_sha256",
                observed.sha256,
                validation.artifact_sha256,
            ),
            (
                "delegation.merge.schema_validation_schema_mismatch",
                "schema_id",
                expected.schema_id,
                validation.schema_id,
            ),
            (
                "delegation.merge.schema_validation_status_invalid",
                "status",
                "valid",
                validation.status,
            ),
            (
                "delegation.merge.schema_validation_validator_mismatch",
                "validator_id",
                expected.validator_id,
                validation.validator_id,
            ),
            (
                "delegation.merge.schema_validation_validator_version_mismatch",
                "validator_version",
                expected.validator_version,
                validation.validator_version,
            ),
            (
                "delegation.merge.schema_validation_registry_mismatch",
                "validator_registry_sha256",
                expected.validator_registry_sha256,
                validation.validator_registry_sha256,
            ),
        )
        for rule_id, field, expected_value, observed_value in validation_comparisons:
            if expected_value != observed_value:
                findings.append(
                    _merge_finding(
                        rule_id,
                        task.task_id,
                        field,
                        str(expected_value),
                        str(observed_value),
                    )
                )


class ReviewRole(str, Enum):
    DOMAIN = "domain"
    COMMAND_EVIDENCE = "command_evidence"
    ADVERSARIAL = "adversarial"


_REVIEW_ROLE_TOOLS: dict[ReviewRole, frozenset[str]] = {
    ReviewRole.DOMAIN: _READ_TOOLS | {"validate_project_yaml"},
    ReviewRole.COMMAND_EVIDENCE: (
        _READ_TOOLS | _COMMAND_INSPECTION_TOOLS | {"validate_project_yaml"}
    ),
    ReviewRole.ADVERSARIAL: (
        _READ_TOOLS | _COMMAND_INSPECTION_TOOLS | {"validate_project_yaml"}
    ),
}


class ReviewPacket(_Contract):
    """Read-only candidate and evidence scope for an independent critic."""

    schema_version: Literal[REVIEW_SCHEMA_VERSION] = REVIEW_SCHEMA_VERSION
    review_id: str = Field(pattern=_IDENTIFIER)
    reviewer_id: str = Field(pattern=_IDENTIFIER)
    role: ReviewRole
    producer_ids: tuple[str, ...] = Field(min_length=1)
    source_artifacts: tuple[OpaqueArtifactRef, ...] = Field(min_length=1)
    candidate_artifacts: tuple[OpaqueArtifactRef, ...] = Field(min_length=1)
    declared_assumptions: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    tool_scope_sha256: str = Field(pattern=_SHA256)
    budget: ResourceBudget
    read_only: Literal[True] = True
    can_approve: Literal[False] = False
    can_execute: Literal[False] = False
    can_repair: Literal[False] = False

    @field_validator("producer_ids", "declared_assumptions")
    @classmethod
    def _canonical_text_sets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _require_unique(list(value), "review packet identifiers")
        return tuple(sorted(value))

    @field_validator("allowed_tools")
    @classmethod
    def _canonical_tools(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _require_unique(list(value), "allowed_tools")
        _require_pattern(list(value), _TOOL_NAME, "allowed_tools")
        return tuple(sorted(value))

    @field_validator("source_artifacts", "candidate_artifacts")
    @classmethod
    def _canonical_artifacts(
        cls, value: tuple[OpaqueArtifactRef, ...]
    ) -> tuple[OpaqueArtifactRef, ...]:
        return tuple(sorted(value, key=lambda item: item.artifact_id))

    @model_validator(mode="after")
    def _critic_is_independent_and_read_only(self) -> "ReviewPacket":
        _require_unique(list(self.producer_ids), "producer_ids")
        _require_pattern(list(self.producer_ids), _IDENTIFIER, "producer_ids")
        if self.reviewer_id in self.producer_ids:
            raise ValueError("reviewer must be independent from artifact producers")
        if self.budget.max_child_tasks:
            raise ValueError("a read-only reviewer cannot receive a child-task budget")
        _require_unique(
            [item.artifact_id for item in self.source_artifacts],
            "source artifact_id values",
        )
        _require_unique(
            [item.artifact_id for item in self.candidate_artifacts],
            "candidate artifact_id values",
        )
        overlap = set(item.artifact_id for item in self.source_artifacts).intersection(
            item.artifact_id for item in self.candidate_artifacts
        )
        if overlap:
            raise ValueError("source and candidate artifact scopes must be disjoint")
        if self.tool_scope_sha256 != tool_scope_sha256(self.allowed_tools):
            raise ValueError("tool_scope_sha256 does not bind allowed_tools")
        forbidden = sorted(_FRONTIER_FORBIDDEN_TOOLS.intersection(self.allowed_tools))
        if forbidden:
            raise ValueError(
                "review packet exposes mutating or execution tools: "
                + ", ".join(forbidden)
            )
        unknown_tools = sorted(
            set(self.allowed_tools).difference(_REVIEW_ROLE_TOOLS[self.role])
        )
        if unknown_tools:
            raise ValueError(
                f"{self.role.value} review exposes tools outside its allowlist: "
                + ", ".join(unknown_tools)
            )
        return self


def review_packet_sha256(packet: ReviewPacket) -> str:
    return _sha256_json(packet.model_dump(mode="json"))


class ReviewSeverity(str, Enum):
    INFORMATIONAL = "informational"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ReviewFinding(_Contract):
    """Typed, open finding without approval or repair authority."""

    schema_version: Literal[REVIEW_FINDING_SCHEMA_VERSION] = (
        REVIEW_FINDING_SCHEMA_VERSION
    )
    finding_id: str = Field(pattern=_IDENTIFIER)
    review_id: str = Field(pattern=_IDENTIFIER)
    reviewer_id: str = Field(pattern=_IDENTIFIER)
    role: ReviewRole
    rule_id: str = Field(pattern=_IDENTIFIER)
    severity: ReviewSeverity
    target_artifact_id: str = Field(pattern=_IDENTIFIER)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    field: str = Field(pattern=_IDENTIFIER)
    expected: str = Field(min_length=1, max_length=1000, pattern=_SAFE_TEXT)
    observed: str = Field(min_length=1, max_length=1000, pattern=_SAFE_TEXT)
    public_summary: str = Field(min_length=1, max_length=1000, pattern=_SAFE_TEXT)
    disposition: Literal["open"] = "open"
    can_approve: Literal[False] = False
    can_execute: Literal[False] = False
    can_repair: Literal[False] = False

    @field_validator("evidence_refs")
    @classmethod
    def _canonical_evidence_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _require_unique(list(value), "evidence_refs")
        _require_pattern(list(value), _IDENTIFIER, "evidence_refs")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def _evidence_refs_are_unique(self) -> "ReviewFinding":
        return self


def review_finding_sha256(finding: ReviewFinding) -> str:
    """Return the canonical public digest for one immutable review finding."""

    return _sha256_json(finding.model_dump(mode="json"))


class ReviewFindingRef(_Contract):
    finding_id: str = Field(pattern=_IDENTIFIER)
    finding_sha256: str = Field(pattern=_SHA256)


class ReviewGateReceipt(_Contract):
    """Validation result for critic output; explicitly non-authoritative."""

    schema_version: Literal[REVIEW_GATE_SCHEMA_VERSION] = REVIEW_GATE_SCHEMA_VERSION
    review_id: str = Field(pattern=_IDENTIFIER)
    review_packet_sha256: str = Field(pattern=_SHA256)
    verdict: Literal[
        "invalid_review",
        "critical_findings_open",
        "no_critical_findings_observed",
    ]
    finding_refs: tuple[ReviewFindingRef, ...]
    validation_rule_ids: tuple[str, ...]
    usage: ResourceUsage
    tools_used: tuple[str, ...]
    authoritative: Literal[False] = False
    approval_eligible: Literal[False] = False

    @field_validator("finding_refs")
    @classmethod
    def _canonical_finding_refs(
        cls, value: tuple[ReviewFindingRef, ...]
    ) -> tuple[ReviewFindingRef, ...]:
        _require_unique([item.finding_id for item in value], "finding_refs")
        return tuple(sorted(value, key=lambda item: item.finding_id))

    @field_validator("validation_rule_ids", "tools_used")
    @classmethod
    def _canonical_identifiers(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _require_unique(list(value), "review receipt identifiers")
        return tuple(sorted(value))


def review_gate_receipt_sha256(receipt: ReviewGateReceipt) -> str:
    """Return the digest bound by the runtime review-gate event."""

    return _sha256_json(receipt.model_dump(mode="json"))


def validate_review_findings(
    packet: ReviewPacket,
    findings: Iterable[ReviewFinding],
    *,
    usage: ResourceUsage,
    tools_used: Iterable[str] = (),
) -> ReviewGateReceipt:
    """Validate scope and budget for independent critic findings."""

    ordered = sorted(findings, key=lambda item: item.finding_id)
    used_tools = tuple(sorted(tools_used))
    rules: list[str] = list(budget_rule_ids(usage, packet.budget))
    if len(used_tools) != len(set(used_tools)):
        rules.append("review.tools_used.duplicate")
    if set(used_tools).difference(packet.allowed_tools):
        rules.append("review.tool_scope.exceeded")
    finding_counts = Counter(item.finding_id for item in ordered)
    if any(count > 1 for count in finding_counts.values()):
        rules.append("review.finding_id.duplicate")

    candidate_ids = {item.artifact_id for item in packet.candidate_artifacts}
    evidence_ids = candidate_ids.union(
        item.artifact_id for item in packet.source_artifacts
    )
    for finding in ordered:
        if finding.review_id != packet.review_id:
            rules.append("review.review_id.mismatch")
        if finding.reviewer_id != packet.reviewer_id:
            rules.append("review.reviewer_id.mismatch")
        if finding.role is not packet.role:
            rules.append("review.role.mismatch")
        if finding.target_artifact_id not in candidate_ids:
            rules.append("review.target.out_of_scope")
        if set(finding.evidence_refs).difference(evidence_ids):
            rules.append("review.evidence_ref.out_of_scope")

    unique_rules = tuple(dict.fromkeys(rules))
    if unique_rules:
        verdict = "invalid_review"
    elif any(item.severity is ReviewSeverity.CRITICAL for item in ordered):
        verdict = "critical_findings_open"
    else:
        verdict = "no_critical_findings_observed"
    return ReviewGateReceipt(
        review_id=packet.review_id,
        review_packet_sha256=review_packet_sha256(packet),
        verdict=verdict,
        finding_refs=tuple(
            ReviewFindingRef(
                finding_id=item.finding_id,
                finding_sha256=review_finding_sha256(item),
            )
            for item in ordered
        ),
        validation_rule_ids=unique_rules,
        usage=usage,
        tools_used=used_tools,
    )


def _require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def _require_pattern(values: list[str], pattern: str, label: str) -> None:
    if any(re.fullmatch(pattern, value) is None for value in values):
        raise ValueError(f"{label} contain an invalid identifier")


def _merge_finding(
    rule_id: str,
    task_id: str | None,
    field: str,
    expected: str,
    observed: str,
) -> MergeFinding:
    return MergeFinding(
        rule_id=rule_id,
        task_id=task_id,
        field=field,
        expected=expected,
        observed=observed,
    )


def _merge_finding_sort_key(
    finding: MergeFinding,
) -> tuple[str, str, str, str, str]:
    return (
        finding.task_id or "",
        finding.rule_id,
        finding.field,
        finding.expected,
        finding.observed,
    )


def _merge_receipt_surface_sha256(
    *,
    status: Literal["accepted", "rejected"],
    ordered_task_ids: tuple[str, ...],
    task_packet_sha256s: tuple[str, ...],
    result_packet_sha256s: tuple[str, ...],
    merged_artifacts: tuple[OwnedArtifactRef, ...],
    findings: tuple[MergeFinding, ...],
) -> str:
    """Bind every non-self-referential field of a merge receipt."""

    return _sha256_json(
        {
            "schema_version": MERGE_RECEIPT_SCHEMA_VERSION,
            "status": status,
            "ordered_task_ids": ordered_task_ids,
            "task_packet_sha256s": task_packet_sha256s,
            "result_packet_sha256s": result_packet_sha256s,
            "merged_artifacts": [
                item.model_dump(mode="json") for item in merged_artifacts
            ],
            "findings": [item.model_dump(mode="json") for item in findings],
            "approval_eligible": False,
        }
    )


def _aggregate_resource_usage(usages: Iterable[ResourceUsage]) -> ResourceUsage:
    totals = {usage_field: 0 for usage_field, _ in _BUDGET_FIELDS}
    for usage in usages:
        for usage_field, _ in _BUDGET_FIELDS:
            totals[usage_field] += getattr(usage, usage_field)
    return ResourceUsage(**totals)


def _cyclic_task_ids(
    tasks: Sequence[SpecialistTaskPacket],
) -> tuple[str, ...]:
    """Return deterministic cycle-affected IDs from dependency and parent edges."""

    task_ids = {item.task_id for item in tasks}
    outgoing = {task_id: set() for task_id in task_ids}
    indegree = {task_id: 0 for task_id in task_ids}
    for task in tasks:
        predecessors = set(task.dependencies)
        if task.parent_task_id is not None:
            predecessors.add(task.parent_task_id)
        for predecessor in sorted(predecessors.intersection(task_ids)):
            if task.task_id not in outgoing[predecessor]:
                outgoing[predecessor].add(task.task_id)
                indegree[task.task_id] += 1

    ready = sorted(task_id for task_id, count in indegree.items() if count == 0)
    visited: set[str] = set()
    while ready:
        task_id = ready.pop(0)
        visited.add(task_id)
        for dependent in sorted(outgoing[task_id]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
                ready.sort()
    return tuple(sorted(task_ids.difference(visited)))


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


__all__ = [
    "CompletionPredicate",
    "ExpectedOutput",
    "ImmutableTaskInput",
    "MergeFinding",
    "OwnedArtifactRef",
    "OutputSchemaValidationReceipt",
    "OutputSchemaValidationRef",
    "ResourceBudget",
    "ResourceUsage",
    "RuntimeObservedUsageReceipt",
    "ReviewFinding",
    "ReviewFindingRef",
    "ReviewGateReceipt",
    "ReviewPacket",
    "ReviewRole",
    "ReviewSeverity",
    "SpecialistMergeReceipt",
    "SpecialistResultPacket",
    "SpecialistResultStatus",
    "SpecialistRole",
    "SpecialistTaskPacket",
    "budget_rule_ids",
    "deterministic_merge_gate",
    "resource_budget_sha256",
    "resource_usage_sha256",
    "runtime_usage_receipt_sha256",
    "review_finding_sha256",
    "review_gate_receipt_sha256",
    "review_packet_sha256",
    "specialist_merge_receipt_sha256",
    "specialist_result_packet_sha256",
    "specialist_task_packet_sha256",
    "tool_scope_sha256",
    "output_schema_validation_receipt_sha256",
    "validate_review_findings",
]
