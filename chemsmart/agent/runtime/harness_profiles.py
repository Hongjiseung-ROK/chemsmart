"""Provider-neutral harness profiles and conformance contracts.

The contracts in this module describe observable provider capabilities and
the four preregistered harness profiles.  They do not contain credentials,
provider reasoning, or a provider's raw continuation token.  In particular,
``ProviderStateRef`` is only a host-generated reference bound to public
digests; it is never scientific evidence.

This module is additive to Runtime V2.  It intentionally does not add event
kinds or reducer state, so existing hash-chained event logs replay unchanged.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


HARNESS_PROFILE_SCHEMA_VERSION = "chemsmart.harness-profile.v1"
PROVIDER_CAPABILITIES_SCHEMA_VERSION = "chemsmart.provider-capabilities.v1"
PROVIDER_CONFORMANCE_SCHEMA_VERSION = "chemsmart.provider-conformance.v1"
PROVIDER_STATE_REF_SCHEMA_VERSION = "chemsmart.provider-state-ref.v1"
DEEPSEEK_H0_REQUEST_SHA256 = (
    "f501aa5ee17e2662c12a6d2c9bb16b37cad14ce435e209834364d019e09e8bad"
)
DEEPSEEK_H0_TOOL_ARGUMENTS_SHA256 = (
    "5d67805494f3066b2aa4fe88544a90973f6da4eed05b0136609954e39dd1bb0c"
)
DEEPSEEK_H0_TARGET_ORIGIN = "https://api.deepseek.com"

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
_PROTOCOL = r"^[a-z][a-z0-9_.-]{0,63}$"
_SHA256 = r"^[0-9a-f]{64}$"
_SAFE_TEXT = r"^[^\r\n\x00]+$"


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HarnessProfile(str, Enum):
    """Preregistered harness configurations used by crossover studies."""

    H0 = "H0"
    HC = "HC"
    HA = "HA"
    HK = "HK"


class ContinuationMode(str, Enum):
    """Observable continuation mechanism; never the continuation payload."""

    NONE = "none"
    PUBLIC_HISTORY = "public_history"
    EPHEMERAL_PRIVATE_TURN = "ephemeral_private_turn"
    OPAQUE_PROVIDER_REFERENCE = "opaque_provider_reference"


class CapabilityEvidenceBasis(str, Enum):
    """How one capability value was established at this boundary."""

    OBSERVED_PROBE = "observed_probe"
    OFFICIAL_DOCUMENTATION = "official_documentation"
    HARNESS_LIMIT = "harness_limit"
    HARNESS_IMPLEMENTATION = "harness_implementation"
    NOT_EVALUATED = "not_evaluated"


class HarnessProfileSpec(_Contract):
    """Deterministic feature declaration for one evaluation profile.

    A profile enables harness behavior, not autonomous chemistry execution.
    Scientific validators and approval pauses stay enabled for every profile.
    """

    schema_version: Literal[HARNESS_PROFILE_SCHEMA_VERSION] = (
        HARNESS_PROFILE_SCHEMA_VERSION
    )
    profile: HarnessProfile
    public_event_prefix_replay: bool
    sandboxed_tools: bool = True
    approval_pause: bool = True
    deterministic_validator_feedback: bool = True
    progressive_skill_loading: bool
    fresh_specialist_contexts: bool
    deterministic_hooks: bool
    structured_handoffs: bool
    context_compaction: bool
    persistent_goal_state: bool
    checkpoint_fork_resume: bool
    max_delegation_depth: int = Field(ge=0, le=2)


_PROFILE_SPECS = {
    HarnessProfile.H0: HarnessProfileSpec(
        profile=HarnessProfile.H0,
        public_event_prefix_replay=False,
        progressive_skill_loading=False,
        fresh_specialist_contexts=False,
        deterministic_hooks=False,
        structured_handoffs=False,
        context_compaction=False,
        persistent_goal_state=False,
        checkpoint_fork_resume=False,
        max_delegation_depth=0,
    ),
    HarnessProfile.HC: HarnessProfileSpec(
        profile=HarnessProfile.HC,
        public_event_prefix_replay=True,
        progressive_skill_loading=False,
        fresh_specialist_contexts=False,
        deterministic_hooks=False,
        structured_handoffs=False,
        context_compaction=False,
        persistent_goal_state=False,
        checkpoint_fork_resume=False,
        max_delegation_depth=0,
    ),
    HarnessProfile.HA: HarnessProfileSpec(
        profile=HarnessProfile.HA,
        public_event_prefix_replay=True,
        progressive_skill_loading=True,
        fresh_specialist_contexts=True,
        deterministic_hooks=True,
        structured_handoffs=True,
        context_compaction=True,
        persistent_goal_state=False,
        checkpoint_fork_resume=False,
        max_delegation_depth=1,
    ),
    HarnessProfile.HK: HarnessProfileSpec(
        profile=HarnessProfile.HK,
        public_event_prefix_replay=True,
        progressive_skill_loading=True,
        fresh_specialist_contexts=True,
        deterministic_hooks=True,
        structured_handoffs=True,
        context_compaction=True,
        persistent_goal_state=True,
        checkpoint_fork_resume=True,
        max_delegation_depth=2,
    ),
}


def resolve_harness_profile(profile: HarnessProfile | str) -> HarnessProfileSpec:
    """Return an immutable copy of the canonical profile declaration."""

    selected = HarnessProfile(profile)
    return _PROFILE_SPECS[selected].model_copy(deep=True)


class ProviderCapabilities(_Contract):
    """Capabilities declared at one provider/model/protocol boundary.

    Every positive or numeric claim carries an evidence basis.  This prevents
    a bounded one-tool probe from presenting vendor documentation or a harness
    limit as if the value had been empirically measured.  A provider is not
    admitted merely because its configuration claims support; a
    ``ProviderConformanceReceipt`` must record the corresponding deterministic
    probes.
    """

    schema_version: Literal[PROVIDER_CAPABILITIES_SCHEMA_VERSION] = (
        PROVIDER_CAPABILITIES_SCHEMA_VERSION
    )
    provider_id: str = Field(pattern=_IDENTIFIER)
    endpoint_class: str = Field(pattern=_PROTOCOL)
    wire_protocol: str = Field(pattern=_PROTOCOL)
    resolved_model: str = Field(min_length=1, max_length=200, pattern=_SAFE_TEXT)
    structured_tool_calls: bool
    structured_tool_calls_basis: CapabilityEvidenceBasis = (
        CapabilityEvidenceBasis.NOT_EVALUATED
    )
    structured_output: bool
    structured_output_basis: CapabilityEvidenceBasis = (
        CapabilityEvidenceBasis.NOT_EVALUATED
    )
    tool_continuation: ContinuationMode
    tool_continuation_basis: CapabilityEvidenceBasis = (
        CapabilityEvidenceBasis.NOT_EVALUATED
    )
    reasoning_continuation: ContinuationMode = ContinuationMode.NONE
    reasoning_continuation_basis: CapabilityEvidenceBasis = (
        CapabilityEvidenceBasis.NOT_EVALUATED
    )
    public_history_replay: bool
    public_history_replay_basis: CapabilityEvidenceBasis = (
        CapabilityEvidenceBasis.NOT_EVALUATED
    )
    max_context_tokens: int = Field(ge=1)
    max_context_tokens_basis: CapabilityEvidenceBasis = (
        CapabilityEvidenceBasis.NOT_EVALUATED
    )
    max_parallel_tool_calls: int = Field(ge=1)
    max_parallel_tool_calls_basis: CapabilityEvidenceBasis = (
        CapabilityEvidenceBasis.NOT_EVALUATED
    )
    supports_compaction: bool = False
    supports_compaction_basis: CapabilityEvidenceBasis = (
        CapabilityEvidenceBasis.NOT_EVALUATED
    )
    supports_checkpoint: bool = False
    supports_checkpoint_basis: CapabilityEvidenceBasis = (
        CapabilityEvidenceBasis.NOT_EVALUATED
    )
    supports_fork_resume: bool = False
    supports_fork_resume_basis: CapabilityEvidenceBasis = (
        CapabilityEvidenceBasis.NOT_EVALUATED
    )

    @model_validator(mode="after")
    def _capability_combinations_are_coherent(self) -> "ProviderCapabilities":
        claimed = {
            "structured_tool_calls": self.structured_tool_calls,
            "structured_output": self.structured_output,
            "tool_continuation": self.tool_continuation
            is not ContinuationMode.NONE,
            "reasoning_continuation": self.reasoning_continuation
            is not ContinuationMode.NONE,
            "public_history_replay": self.public_history_replay,
            "max_context_tokens": True,
            "max_parallel_tool_calls": True,
            "supports_compaction": self.supports_compaction,
            "supports_checkpoint": self.supports_checkpoint,
            "supports_fork_resume": self.supports_fork_resume,
        }
        ungrounded = [
            name
            for name, is_claimed in claimed.items()
            if is_claimed
            and getattr(self, f"{name}_basis")
            is CapabilityEvidenceBasis.NOT_EVALUATED
        ]
        if ungrounded:
            raise ValueError(
                "positive provider capability claims require an evidence "
                "basis: " + ", ".join(sorted(ungrounded))
            )
        if (
            self.tool_continuation is ContinuationMode.PUBLIC_HISTORY
            and not self.public_history_replay
        ):
            raise ValueError(
                "public-history tool continuation requires public_history_replay"
            )
        if self.supports_fork_resume and not self.supports_checkpoint:
            raise ValueError("fork/resume support requires checkpoint support")
        if self.reasoning_continuation is ContinuationMode.PUBLIC_HISTORY:
            raise ValueError(
                "private reasoning must not be replayed through public history"
            )
        return self


class ProviderStateRef(_Contract):
    """Opaque, scope-bound reference to adapter-owned continuation state.

    No raw response identifier, reasoning text, path, or serialized provider
    state is accepted here.  Hosts must invalidate this reference whenever a
    bound digest changes.  The explicit false literals prevent callers from
    accidentally presenting the reference as evidence or approval.
    """

    schema_version: Literal[PROVIDER_STATE_REF_SCHEMA_VERSION] = (
        PROVIDER_STATE_REF_SCHEMA_VERSION
    )
    state_ref: str = Field(pattern=_IDENTIFIER)
    session_id: str = Field(pattern=_IDENTIFIER)
    turn_id: str = Field(pattern=_IDENTIFIER)
    provider_id: str = Field(pattern=_IDENTIFIER)
    endpoint_class: str = Field(pattern=_PROTOCOL)
    wire_protocol: str = Field(pattern=_PROTOCOL)
    resolved_model: str = Field(min_length=1, max_length=200, pattern=_SAFE_TEXT)
    continuation_mode: Literal[
        "uninterrupted_turn", "public_recap_checkpoint"
    ]
    tool_schema_sha256: str = Field(pattern=_SHA256)
    public_history_sha256: str = Field(pattern=_SHA256)
    resource_envelope_sha256: str = Field(pattern=_SHA256)
    scope_sha256: str = Field(pattern=_SHA256)
    contains_raw_provider_state: Literal[False] = False
    private_reasoning_replay_allowed: Literal[False] = False
    evidence_eligible: Literal[False] = False
    approval_eligible: Literal[False] = False


class ProviderStateScope(_Contract):
    """Public inputs that must still match before an opaque ref is reused."""

    session_id: str = Field(pattern=_IDENTIFIER)
    turn_id: str = Field(pattern=_IDENTIFIER)
    provider_id: str = Field(pattern=_IDENTIFIER)
    endpoint_class: str = Field(pattern=_PROTOCOL)
    wire_protocol: str = Field(pattern=_PROTOCOL)
    resolved_model: str = Field(min_length=1, max_length=200, pattern=_SAFE_TEXT)
    tool_schema_sha256: str = Field(pattern=_SHA256)
    public_history_sha256: str = Field(pattern=_SHA256)
    resource_envelope_sha256: str = Field(pattern=_SHA256)


def provider_state_scope_sha256(scope: ProviderStateScope) -> str:
    """Return the canonical public binding digest for provider state."""

    return _sha256_json(scope.model_dump(mode="json"))


def validate_provider_state_ref(
    state_ref: ProviderStateRef,
    scope: ProviderStateScope,
) -> tuple[str, ...]:
    """Return stable invalidation rules for an opaque continuation ref."""

    findings: list[str] = []
    for field_name in (
        "session_id",
        "turn_id",
        "provider_id",
        "endpoint_class",
        "wire_protocol",
        "resolved_model",
        "tool_schema_sha256",
        "public_history_sha256",
        "resource_envelope_sha256",
    ):
        if getattr(state_ref, field_name) != getattr(scope, field_name):
            findings.append(f"provider.state_ref.{field_name}_mismatch")
    if state_ref.scope_sha256 != provider_state_scope_sha256(scope):
        findings.append("provider.state_ref.scope_digest_mismatch")
    return tuple(findings)


class ConformanceStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_SUPPORTED = "not_supported"
    NOT_RUN = "not_run"


class ConformanceCheck(_Contract):
    check_id: str = Field(pattern=_IDENTIFIER)
    status: ConformanceStatus
    required: bool = True
    rule_ids: tuple[str, ...] = ()
    public_summary: str = Field(min_length=1, max_length=500, pattern=_SAFE_TEXT)


class ProbeToolRequestObservation(_Contract):
    """Content-only observation of one model-requested tool call."""

    name: str = Field(pattern=_IDENTIFIER)
    arguments_sha256: str = Field(pattern=_SHA256)


class ProbeToolOutcomeObservation(_Contract):
    """Content-only observation of one deterministic tool outcome."""

    name: str = Field(pattern=_IDENTIFIER)
    status: str = Field(min_length=1, max_length=64, pattern=_SAFE_TEXT)
    result_sha256: str = Field(pattern=_SHA256)


class ProviderProbeObservation(_Contract):
    """Sanitized body from which conformance transcript hashes are derived."""

    request_sha256: str = Field(pattern=_SHA256)
    source_snapshot_sha256: str = Field(pattern=_SHA256)
    target_origin: str = Field(min_length=1, max_length=200, pattern=_SAFE_TEXT)
    instruction_bundle_sha256: str = Field(pattern=_SHA256)
    instruction_message_count: int = Field(ge=1)
    tool_schema_sha256: str = Field(pattern=_SHA256)
    tool_schema_entry_count: int = Field(ge=1)
    public_history_message_sha256s: tuple[str, ...] = Field(min_length=1)
    model: str = Field(min_length=1, max_length=200, pattern=_SAFE_TEXT)
    tool_requests: tuple[ProbeToolRequestObservation, ...] = ()
    tool_outcomes: tuple[ProbeToolOutcomeObservation, ...] = ()
    stop_reason: str | None = Field(
        default=None, max_length=120, pattern=_SAFE_TEXT
    )
    runtime_mode: str = Field(min_length=1, max_length=64, pattern=_SAFE_TEXT)
    runtime_phase: str = Field(min_length=1, max_length=120, pattern=_SAFE_TEXT)
    runtime_shadow_violations: tuple[str, ...] = ()
    permission_mode: str = Field(
        min_length=1, max_length=64, pattern=_SAFE_TEXT
    )
    sdk_name: str = Field(min_length=1, max_length=80, pattern=_SAFE_TEXT)
    sdk_version: str = Field(min_length=1, max_length=80, pattern=_SAFE_TEXT)
    sdk_max_retries: int = Field(ge=0)
    provider_response_count: int = Field(ge=0)
    usage_response_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _history_hashes_are_valid(self) -> "ProviderProbeObservation":
        if any(
            re.fullmatch(_SHA256, digest) is None
            for digest in self.public_history_message_sha256s
        ):
            raise ValueError(
                "public history observations must be lowercase SHA-256"
            )
        if self.usage_response_count > self.provider_response_count:
            raise ValueError(
                "usage_response_count exceeds provider_response_count"
            )
        if any(
            not isinstance(rule_id, str)
            or re.fullmatch(_IDENTIFIER, rule_id) is None
            for rule_id in self.runtime_shadow_violations
        ):
            raise ValueError(
                "runtime shadow violations must be stable identifiers"
            )
        return self


_COMMON_PROFILE_CHECKS = (
    "typed_tool_call_round_trip",
    "public_history_sanitized",
    "deterministic_validator_gate",
    "bounded_transport_accounting",
)
_ADDITIONAL_PROFILE_CHECKS = {
    HarnessProfile.H0: (),
    HarnessProfile.HC: (
        "event_prefix_replay",
        "approval_pause_resume",
    ),
    HarnessProfile.HA: (
        "event_prefix_replay",
        "approval_pause_resume",
        "fresh_specialist_context",
        "compaction_public_recap",
    ),
    HarnessProfile.HK: (
        "event_prefix_replay",
        "approval_pause_resume",
        "fresh_specialist_context",
        "compaction_public_recap",
        "checkpoint_scope_invalidation",
        "fork_resume_budget_binding",
    ),
}


def required_profile_checks(profile: HarnessProfile | str) -> tuple[str, ...]:
    selected = HarnessProfile(profile)
    return _COMMON_PROFILE_CHECKS + _ADDITIONAL_PROFILE_CHECKS[selected]


class ProviderConformanceReceipt(_Contract):
    """Sanitized result of probing one model under one harness profile."""

    schema_version: Literal[PROVIDER_CONFORMANCE_SCHEMA_VERSION] = (
        PROVIDER_CONFORMANCE_SCHEMA_VERSION
    )
    receipt_id: str = Field(pattern=_SHA256)
    profile: HarnessProfile
    capabilities: ProviderCapabilities
    requested_model_id: str = Field(
        min_length=1, max_length=200, pattern=_SAFE_TEXT
    )
    observed_model_id: str = Field(
        min_length=1, max_length=200, pattern=_SAFE_TEXT
    )
    target_origin: str = Field(min_length=1, max_length=200, pattern=_SAFE_TEXT)
    request_sha256: str = Field(pattern=_SHA256)
    source_snapshot_sha256: str = Field(pattern=_SHA256)
    instruction_bundle_sha256: str = Field(pattern=_SHA256)
    tool_schema_sha256: str = Field(pattern=_SHA256)
    public_history_sha256: str = Field(pattern=_SHA256)
    resource_budget_sha256: str = Field(pattern=_SHA256)
    observed_usage_sha256: str = Field(pattern=_SHA256)
    probe_transcript_sha256: str = Field(pattern=_SHA256)
    probe_observation: ProviderProbeObservation
    sdk_name: Literal["openai"] = "openai"
    sdk_version: str = Field(min_length=1, max_length=80, pattern=_SAFE_TEXT)
    sdk_max_retries: Literal[0] = 0
    thinking_mode: Literal["enabled", "disabled"]
    max_output_tokens: int = Field(ge=1)
    request_budget: int = Field(ge=1)
    model_step_budget: int = Field(ge=1)
    tool_call_budget: int = Field(ge=0)
    engine_call_budget: Literal[0] = 0
    hpc_call_budget: Literal[0] = 0
    requests_used: int = Field(ge=0)
    transport_attempts: int = Field(ge=0)
    model_steps: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    usage_complete: bool
    wall_time_ms: int = Field(ge=0)
    registered_tool_names: tuple[str, ...]
    virtual_tool_names: tuple[str, ...] = ()
    engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0
    credential_status: Literal["valid"]
    quota_sufficient_for_probe: bool
    checks: tuple[ConformanceCheck, ...] = Field(min_length=1)
    verdict: Literal["compatible", "partial", "incompatible"]
    raw_provider_turns_persisted: Literal[False] = False
    training_data_persisted: Literal[False] = False
    private_reasoning_persisted: Literal[False] = False
    secret_material_persisted: Literal[False] = False

    @model_validator(mode="after")
    def _verdict_follows_required_checks(self) -> "ProviderConformanceReceipt":
        check_ids = [check.check_id for check in self.checks]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("conformance check_id values must be unique")
        required = set(required_profile_checks(self.profile))
        supplied = {
            check.check_id for check in self.checks if check.required
        }
        missing = sorted(required.difference(supplied))
        if missing:
            raise ValueError(
                "required profile conformance checks are missing: "
                + ", ".join(missing)
            )
        required_checks = [check for check in self.checks if check.required]
        if self.observed_model_id != self.capabilities.resolved_model:
            raise ValueError(
                "observed_model_id must match the resolved capability model"
            )
        if self.requests_used > self.request_budget:
            raise ValueError("requests_used exceeds the immutable request budget")
        if self.model_steps != self.requests_used:
            raise ValueError(
                "each conformance model step must consume exactly one request"
            )
        if self.model_steps > self.model_step_budget:
            raise ValueError("model_steps exceeds the immutable model-step budget")
        if self.tool_calls > self.tool_call_budget:
            raise ValueError("tool_calls exceeds the immutable tool-call budget")
        if self.transport_attempts != self.requests_used:
            raise ValueError(
                "zero-retry probe requires one transport attempt per request"
            )
        if len(self.registered_tool_names) != len(
            set(self.registered_tool_names)
        ):
            raise ValueError("registered_tool_names must be unique")
        if len(self.virtual_tool_names) != len(set(self.virtual_tool_names)):
            raise ValueError("virtual_tool_names must be unique")
        if set(self.registered_tool_names).intersection(self.virtual_tool_names):
            raise ValueError("registered and virtual tool names must be disjoint")
        invalid_tool_names = [
            name
            for name in (*self.registered_tool_names, *self.virtual_tool_names)
            if not isinstance(name, str)
            or re.fullmatch(_IDENTIFIER, name) is None
        ]
        if invalid_tool_names:
            raise ValueError("conformance tool names must be safe identifiers")
        if self.verdict == "compatible" and not self.quota_sufficient_for_probe:
            raise ValueError(
                "a compatible receipt requires quota sufficient for this probe"
            )
        observation = self.probe_observation
        if self.request_sha256 != observation.request_sha256:
            raise ValueError("request_sha256 does not bind probe observation")
        if self.source_snapshot_sha256 != observation.source_snapshot_sha256:
            raise ValueError(
                "source_snapshot_sha256 does not bind probe observation"
            )
        if self.target_origin != observation.target_origin:
            raise ValueError("target_origin does not bind probe observation")
        if self.instruction_bundle_sha256 != observation.instruction_bundle_sha256:
            raise ValueError(
                "instruction_bundle_sha256 does not bind probe observation"
            )
        if self.tool_schema_sha256 != observation.tool_schema_sha256:
            raise ValueError("tool_schema_sha256 does not bind probe observation")
        expected_public_history = _sha256_json(
            observation.public_history_message_sha256s
        )
        if self.public_history_sha256 != expected_public_history:
            raise ValueError(
                "public_history_sha256 does not bind message observations"
            )
        if self.probe_transcript_sha256 != _sha256_json(
            observation.model_dump(mode="json")
        ):
            raise ValueError(
                "probe_transcript_sha256 does not bind observation body"
            )
        if observation.model != self.observed_model_id:
            raise ValueError("probe observation model does not match receipt")
        if observation.sdk_name != self.sdk_name:
            raise ValueError("SDK name does not bind probe observation")
        if observation.sdk_version != self.sdk_version:
            raise ValueError("SDK version does not bind probe observation")
        if observation.sdk_max_retries != self.sdk_max_retries:
            raise ValueError("SDK retry policy does not bind probe observation")
        if observation.tool_schema_entry_count != len(
            self.registered_tool_names + self.virtual_tool_names
        ):
            raise ValueError(
                "tool schema entry count does not match exposed tool names"
            )
        if observation.provider_response_count != self.requests_used:
            raise ValueError(
                "provider response count does not match requests_used"
            )
        expected_usage_complete = (
            observation.provider_response_count > 0
            and observation.usage_response_count
            == observation.provider_response_count
        )
        if self.usage_complete != expected_usage_complete:
            raise ValueError("usage_complete does not match observed responses")
        if self.verdict == "compatible" and not self.usage_complete:
            raise ValueError("a compatible receipt requires complete token usage")
        expected_resource_digest = _sha256_json(
            {
                "engine_call_budget": self.engine_call_budget,
                "hpc_call_budget": self.hpc_call_budget,
                "max_model_steps": self.model_step_budget,
                "max_network_requests": self.request_budget,
                "max_output_tokens": self.max_output_tokens,
                "max_tool_calls": self.tool_call_budget,
                "raw_provider_turn_logging": False,
                "sdk_max_retries": self.sdk_max_retries,
                "thinking_mode": self.thinking_mode,
                "training_capture": False,
            }
        )
        if self.resource_budget_sha256 != expected_resource_digest:
            raise ValueError("resource_budget_sha256 does not bind receipt limits")
        expected_usage_digest = _sha256_json(
            {
                "engine_calls": self.engine_calls,
                "hpc_calls": self.hpc_calls,
                "input_tokens": self.input_tokens,
                "model_steps": self.model_steps,
                "output_tokens": self.output_tokens,
                "requests_used": self.requests_used,
                "transport_attempts": self.transport_attempts,
                "tool_calls": self.tool_calls,
                "usage_complete": self.usage_complete,
                "wall_time_ms": self.wall_time_ms,
            }
        )
        if self.observed_usage_sha256 != expected_usage_digest:
            raise ValueError("observed_usage_sha256 does not bind observed usage")
        checks_by_id = {check.check_id: check for check in required_checks}
        if (
            checks_by_id["typed_tool_call_round_trip"].status
            is ConformanceStatus.PASS
            and (
                not self.capabilities.structured_tool_calls
                or self.capabilities.structured_tool_calls_basis
                is not CapabilityEvidenceBasis.OBSERVED_PROBE
                or not self.registered_tool_names
                or self.tool_calls < 1
                or self.requests_used < 2
            )
        ):
            raise ValueError(
                "typed tool-call conformance cannot pass without observed "
                "capability support"
            )
        if (
            checks_by_id["bounded_transport_accounting"].status
            is ConformanceStatus.PASS
            and (
                not self.usage_complete
                or self.transport_attempts != self.requests_used
            )
        ):
            raise ValueError(
                "bounded transport accounting cannot pass without exact "
                "attempt and complete usage observations"
            )
        if (
            "event_prefix_replay" in checks_by_id
            and checks_by_id["event_prefix_replay"].status
            is ConformanceStatus.PASS
            and not self.capabilities.public_history_replay
        ):
            raise ValueError(
                "event-prefix replay cannot pass without public-history support"
            )
        if self.profile is HarnessProfile.H0:
            expected_h0_limits = (
                self.requested_model_id == "deepseek-v4-flash"
                and self.target_origin == DEEPSEEK_H0_TARGET_ORIGIN
                and self.request_sha256 == DEEPSEEK_H0_REQUEST_SHA256
                and self.thinking_mode == "enabled"
                and self.max_output_tokens == 512
                and self.request_budget == 2
                and self.model_step_budget == 2
                and self.tool_call_budget == 1
                and self.sdk_max_retries == 0
                and self.registered_tool_names == ("inspect_command_schema",)
                and self.virtual_tool_names == ("ask_user",)
            )
            if not expected_h0_limits:
                raise ValueError("H0 receipt does not match its frozen envelope")
            if self.verdict == "compatible" and (
                self.requests_used != 2
                or self.model_steps != 2
                or self.tool_calls != 1
                or len(observation.tool_requests) != 1
                or len(observation.tool_outcomes) != 1
                or observation.tool_requests[0].name
                != "inspect_command_schema"
                or observation.tool_requests[0].arguments_sha256
                != DEEPSEEK_H0_TOOL_ARGUMENTS_SHA256
                or observation.tool_outcomes[0].name
                != "inspect_command_schema"
                or observation.tool_outcomes[0].status != "ok"
                or observation.runtime_mode != "active"
                or observation.runtime_phase != "complete"
                or observation.runtime_shadow_violations
                or observation.permission_mode != "read_only"
                or observation.sdk_name != "openai"
                or observation.sdk_max_retries != 0
            ):
                raise ValueError(
                    "compatible H0 receipt requires the exact observed envelope"
                )
        if any(check.status is ConformanceStatus.FAIL for check in required_checks):
            expected = "incompatible"
        elif all(
            check.status is ConformanceStatus.PASS for check in required_checks
        ):
            expected = "compatible"
        else:
            expected = "partial"
        if self.profile is not HarnessProfile.H0 and expected == "compatible":
            raise ValueError(
                "non-H0 compatibility requires typed profile-specific "
                "observation receipts that are not implemented"
            )
        if self.verdict != expected:
            raise ValueError(
                f"conformance verdict must be {expected!r} for required checks"
            )
        if validate_provider_conformance_receipt_identity(self):
            raise ValueError(
                "receipt_id must be the SHA-256 content address of the "
                "complete conformance receipt payload"
            )
        return self


def provider_conformance_receipt_id(
    receipt: ProviderConformanceReceipt | Mapping[str, object],
) -> str:
    """Return the full content address for a complete receipt payload.

    The canonical identity covers every modeled field except ``receipt_id``.
    Mapping inputs must therefore contain the complete payload, including
    schema version and fields whose model defaults are false or zero.
    """

    payload = _provider_conformance_identity_payload(receipt)
    return _sha256_json(payload)


def validate_provider_conformance_receipt_identity(
    receipt: ProviderConformanceReceipt | Mapping[str, object],
) -> tuple[str, ...]:
    """Return a stable finding when a receipt content address is stale."""

    receipt_id = (
        receipt.receipt_id
        if isinstance(receipt, ProviderConformanceReceipt)
        else receipt.get("receipt_id")
    )
    if receipt_id != provider_conformance_receipt_id(receipt):
        return ("provider.conformance.receipt_id_mismatch",)
    return ()


def _provider_conformance_identity_payload(
    receipt: ProviderConformanceReceipt | Mapping[str, object],
) -> dict[str, object]:
    if isinstance(receipt, ProviderConformanceReceipt):
        return receipt.model_dump(mode="json", exclude={"receipt_id"})
    if not isinstance(receipt, Mapping):
        raise TypeError("receipt must be a ProviderConformanceReceipt or mapping")

    payload = {
        key: value for key, value in receipt.items() if key != "receipt_id"
    }
    expected_fields = set(ProviderConformanceReceipt.model_fields).difference(
        {"receipt_id"}
    )
    missing = sorted(expected_fields.difference(payload))
    unexpected = sorted(set(payload).difference(expected_fields))
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unexpected:
            details.append("unexpected=" + ",".join(unexpected))
        raise ValueError(
            "receipt identity requires the complete modeled payload: "
            + "; ".join(details)
        )
    return {
        key: _receipt_json_value(value) for key, value in payload.items()
    }


def _receipt_json_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _receipt_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_receipt_json_value(item) for item in value]
    return value


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


__all__ = [
    "ConformanceCheck",
    "ConformanceStatus",
    "CapabilityEvidenceBasis",
    "ContinuationMode",
    "DEEPSEEK_H0_REQUEST_SHA256",
    "DEEPSEEK_H0_TARGET_ORIGIN",
    "DEEPSEEK_H0_TOOL_ARGUMENTS_SHA256",
    "HarnessProfile",
    "HarnessProfileSpec",
    "ProviderCapabilities",
    "ProviderConformanceReceipt",
    "ProviderProbeObservation",
    "ProviderStateRef",
    "ProviderStateScope",
    "ProbeToolOutcomeObservation",
    "ProbeToolRequestObservation",
    "provider_conformance_receipt_id",
    "provider_state_scope_sha256",
    "required_profile_checks",
    "resolve_harness_profile",
    "validate_provider_conformance_receipt_identity",
    "validate_provider_state_ref",
]
