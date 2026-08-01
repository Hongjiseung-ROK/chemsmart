"""Bounded DeepSeek H0 conformance probe over the production tool loop.

The probe deliberately exercises only ``inspect_command_schema``.  It does not
expose command execution, native-engine input builders, project writes, HPC,
or arbitrary shell access.  A credential is leased independently for each of
at most two provider requests and is never retained by the provider bridge.

Only a sanitized :class:`ProviderConformanceReceipt` leaves this module.  Raw
provider responses and private reasoning remain in the uninterrupted in-memory
turn long enough to satisfy the provider's tool-continuation protocol, then
are discarded.  Training capture and raw provider-turn logging are disabled.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from chemsmart.agent.api_access import (
    ApiProvider,
    ApiUsageBudget,
    CredentialAccessController,
    CredentialProbeError,
    CredentialProbeObservation,
    CredentialStatus,
    CredentialUnavailableError,
    UsageBudgetError,
)
from chemsmart.agent.command_workflow_tools import inspect_command_schema
from chemsmart.agent.core import AgentSession
from chemsmart.agent.loop import (
    ToolLoopBudgets,
    registry_tool_defs_for_provider,
)
from chemsmart.agent.permissions import (
    PermissionPolicy,
    RuntimePermissionMode,
)
from chemsmart.agent.providers import OpenAIProvider
from chemsmart.agent.registry import ToolRegistry
from chemsmart.agent.runtime.contracts import TaskPhase
from chemsmart.agent.runtime.harness_profiles import (
    CapabilityEvidenceBasis,
    ConformanceCheck,
    ConformanceStatus,
    ContinuationMode,
    DEEPSEEK_H0_REQUEST_SHA256,
    DEEPSEEK_H0_TARGET_ORIGIN,
    DEEPSEEK_H0_TOOL_ARGUMENTS_SHA256,
    HarnessProfile,
    PROVIDER_CONFORMANCE_SCHEMA_VERSION,
    ProviderCapabilities,
    ProviderConformanceReceipt,
    ProviderProbeObservation,
    ProbeToolOutcomeObservation,
    ProbeToolRequestObservation,
    provider_conformance_receipt_id,
    validate_provider_conformance_receipt_identity,
)
from chemsmart.agent.runtime.tool_catalog import PhaseToolProfile


_SHA256 = r"^[0-9a-f]{64}$"
_SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
_OFFICIAL_ENDPOINT = "https://api.deepseek.com"
_REGISTERED_TOOL = "inspect_command_schema"
_VIRTUAL_TOOL = "ask_user"
_PROBE_CONTEXT = "Gaussian optimization command schema"
_PROBE_REQUEST = (
    "Call inspect_command_schema exactly once with request_context set to "
    f"{_PROBE_CONTEXT!r}. After its result, answer only that the schema was "
    "inspected. Do not call ask_user and do not propose or execute chemistry."
)
_PRIVATE_REASONING_KEYS = frozenset({"reasoning_content", "thinking"})

if hashlib.sha256(_PROBE_REQUEST.encode("utf-8")).hexdigest() != (
    DEEPSEEK_H0_REQUEST_SHA256
):  # pragma: no cover - import-time frozen-contract invariant
    raise RuntimeError("DeepSeek H0 request text drifted from its frozen digest")
if hashlib.sha256(
    json.dumps(
        {"request_context": _PROBE_CONTEXT},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest() != DEEPSEEK_H0_TOOL_ARGUMENTS_SHA256:  # pragma: no cover
    raise RuntimeError("DeepSeek H0 tool arguments drifted from their digest")


class DeepSeekH0ProbeConfig(BaseModel):
    """Immutable limits for the sole live-model conformance slice."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    endpoint: Literal["https://api.deepseek.com"] = _OFFICIAL_ENDPOINT
    thinking_mode: Literal["enabled"] = "enabled"
    reasoning_effort: Literal["high", "max"] = "high"
    max_output_tokens: int = Field(default=512, ge=128, le=512)
    max_network_requests: Literal[2] = 2
    max_model_steps: Literal[2] = 2
    max_tool_calls: Literal[1] = 1
    raw_provider_turn_logging: Literal[False] = False
    training_capture: Literal[False] = False
    engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0


class ProbeErrorClass(str, Enum):
    """Persistable error taxonomy; no provider exception text is retained."""

    MISSING_CREDENTIAL = "missing_credential"
    REQUEST_BUDGET_EXHAUSTED = "request_budget_exhausted"
    AUTHENTICATION = "authentication"
    ENTITLEMENT = "entitlement"
    QUOTA_OR_RATE_LIMIT = "quota_or_rate_limit"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    REQUEST_REJECTED = "request_rejected"
    PROVIDER_ERROR = "provider_error"
    PROVIDER_PROTOCOL = "provider_protocol"
    UNSAFE_PERSISTENCE = "unsafe_persistence"


class ProviderConformanceProbeError(RuntimeError):
    """Fail-closed conformance error carrying only a safe class label."""

    def __init__(self, error_class: ProbeErrorClass) -> None:
        self.error_class = error_class
        super().__init__(error_class.value)


ProviderFactory = Callable[..., Any]


def compute_source_snapshot_sha256(repo_root: str | Path) -> str:
    """Hash the sorted H0 implementation, prompt, and dependency declarations.

    Generated receipts, docs, test artifacts, user behavior rules, and bytecode
    caches stay outside the digest. The H0 probe explicitly disables dynamic
    behavior-rule text; its stage prompt and dependency declarations are
    included here. Length-prefix framing keeps boundaries unambiguous.
    """

    root = Path(repo_root).resolve()
    source_root = root / "chemsmart"
    if not source_root.is_dir():
        raise ValueError("repo_root must contain a chemsmart source directory")
    python_sources = [
        path
        for path in source_root.rglob("*.py")
        if path.is_file()
        and "__pycache__" not in path.relative_to(source_root).parts
    ]
    declared_inputs = [
        root / "chemsmart/agent/prompts/tool_loop.md",
        root / "pyproject.toml",
        root / "environment.yml",
    ]
    sources = sorted(
        [*python_sources, *(path for path in declared_inputs if path.is_file())],
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if not python_sources:
        raise ValueError("chemsmart source tree contains no Python files")

    digest = hashlib.sha256(b"chemsmart.h0-source-bundle.v2\x00")
    for path in sources:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        contents = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return digest.hexdigest()


class _LeaseBoundDeepSeekProvider:
    """OpenAI-wire provider which reacquires a one-request credential lease."""

    name = "deepseek"
    wire_protocol = "openai"

    def __init__(
        self,
        *,
        controller: CredentialAccessController,
        budget: ApiUsageBudget,
        config: DeepSeekH0ProbeConfig,
        provider_factory: ProviderFactory | None = None,
    ) -> None:
        self.default_model = config.model
        self._controller = controller
        self._budget = budget
        self._config = config
        self._provider_factory = provider_factory or OpenAIProvider
        self._requests_used = 0
        self._transport_attempts = 0
        self._credential_receipts: list[dict[str, str]] = []
        self._observed_model_id = ""
        self._instruction_bundle_sha256 = ""
        self._instruction_message_count = 0
        self._tool_schema_sha256 = ""
        self._registered_tool_names: tuple[str, ...] = ()
        self._virtual_tool_names: tuple[str, ...] = ()
        self._public_history_replay_observed = False
        self._reasoning_continuation_observed = False
        self._safe_error_class: ProbeErrorClass | None = None

    @property
    def requests_used(self) -> int:
        return self._requests_used

    @property
    def observed_model_id(self) -> str:
        return self._observed_model_id

    @property
    def transport_attempts(self) -> int:
        return self._transport_attempts

    @property
    def instruction_bundle_sha256(self) -> str:
        return self._instruction_bundle_sha256

    @property
    def instruction_message_count(self) -> int:
        return self._instruction_message_count

    @property
    def tool_schema_sha256(self) -> str:
        return self._tool_schema_sha256

    @property
    def registered_tool_names(self) -> tuple[str, ...]:
        return self._registered_tool_names

    @property
    def virtual_tool_names(self) -> tuple[str, ...]:
        return self._virtual_tool_names

    @property
    def public_history_replay_observed(self) -> bool:
        return self._public_history_replay_observed

    @property
    def reasoning_continuation_observed(self) -> bool:
        return self._reasoning_continuation_observed

    @property
    def safe_error_class(self) -> ProbeErrorClass | None:
        return self._safe_error_class

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        timeout_s: float = 30,
    ) -> dict[str, Any]:
        if self._requests_used >= self._config.max_network_requests:
            self._raise_safe(ProbeErrorClass.REQUEST_BUDGET_EXHAUSTED)
        self._observe_instruction_bundle(messages)
        self._observe_public_continuation(messages)
        self._observe_tool_schema(tools or [])
        try:
            permit = self._controller.prepare_status_probe(
                ApiProvider.DEEPSEEK,
                caller="chemsmart-provider-conformance",
                purpose=f"h0-v4-flash-request-{self._requests_used + 1}",
                budget=self._budget,
                target_origin=self._config.endpoint,
            )
        except CredentialUnavailableError:
            self._raise_safe(ProbeErrorClass.MISSING_CREDENTIAL)
        except UsageBudgetError:
            self._raise_safe(ProbeErrorClass.REQUEST_BUDGET_EXHAUSTED)

        captured: dict[str, Any] = {}

        def operation(
            secret: str,
            target_origin: str,
        ) -> CredentialProbeObservation:
            try:
                if target_origin != self._config.endpoint:
                    self._raise_safe(ProbeErrorClass.PROVIDER_PROTOCOL)
                provider = self._provider_factory(
                    api_key=secret,
                    model=self._config.model,
                    base_url=target_origin,
                    provider_name="deepseek",
                    thinking_mode=self._config.thinking_mode,
                    reasoning_effort=self._config.reasoning_effort,
                    max_output_tokens=self._config.max_output_tokens,
                    max_retries=0,
                )
                self._transport_attempts += 1
                captured["response"] = provider.chat(
                    messages,
                    tools=tools,
                    timeout_s=timeout_s,
                )
            except Exception as exc:
                self._safe_error_class = _classify_provider_error(exc)
                raise _SanitizedLeaseFailure from None
            return CredentialProbeObservation(CredentialStatus.VALID)

        try:
            status = self._controller.invoke_authorized_probe(
                permit, operation
            )
        except CredentialProbeError:
            self._raise_safe(
                self._safe_error_class or ProbeErrorClass.PROVIDER_ERROR
            )
        self._requests_used += 1
        self._credential_receipts.append(status.to_public_dict())
        response = captured.get("response")
        if not isinstance(response, dict):
            self._raise_safe(ProbeErrorClass.PROVIDER_PROTOCOL)
        model = response.get("model")
        if not isinstance(model, str) or not _SAFE_MODEL.fullmatch(model):
            self._raise_safe(ProbeErrorClass.PROVIDER_PROTOCOL)
        if self._observed_model_id and model != self._observed_model_id:
            self._raise_safe(ProbeErrorClass.PROVIDER_PROTOCOL)
        self._observed_model_id = model
        return response

    def _observe_instruction_bundle(
        self, messages: list[dict[str, Any]]
    ) -> None:
        if not self._instruction_bundle_sha256:
            self._instruction_message_count = len(messages)
            self._instruction_bundle_sha256 = _sha256_json(messages)
            return
        prefix = messages[: self._instruction_message_count]
        if _sha256_json(prefix) != self._instruction_bundle_sha256:
            self._raise_safe(ProbeErrorClass.PROVIDER_PROTOCOL)

    def _observe_public_continuation(
        self, messages: list[dict[str, Any]]
    ) -> None:
        roles = [
            str(message.get("role") or "")
            for message in messages
            if isinstance(message, dict)
        ]
        if "assistant" in roles and "tool" in roles:
            self._public_history_replay_observed = True
        for message in messages:
            if not isinstance(message, dict) or message.get("role") != "assistant":
                continue
            if any(key in message for key in _PRIVATE_REASONING_KEYS):
                self._reasoning_continuation_observed = True

    def _observe_tool_schema(self, tools: list[dict[str, Any]]) -> None:
        digest = _sha256_json(tools)
        if self._tool_schema_sha256 and digest != self._tool_schema_sha256:
            self._raise_safe(ProbeErrorClass.PROVIDER_PROTOCOL)
        self._tool_schema_sha256 = digest
        names = tuple(
            name
            for name in (_tool_name(definition) for definition in tools)
            if name
        )
        self._registered_tool_names = tuple(
            name for name in names if name != _VIRTUAL_TOOL
        )
        self._virtual_tool_names = tuple(
            name for name in names if name == _VIRTUAL_TOOL
        )

    def _raise_safe(self, error_class: ProbeErrorClass) -> None:
        self._safe_error_class = error_class
        raise ProviderConformanceProbeError(error_class) from None


class _SanitizedLeaseFailure(RuntimeError):
    """Internal sentinel whose text never contains a provider exception."""


def run_deepseek_h0_conformance_probe(
    *,
    credential_controller: CredentialAccessController,
    session_root: str | Path,
    source_snapshot_sha256: str | None = None,
    repo_root: str | Path | None = None,
    config: DeepSeekH0ProbeConfig | None = None,
    provider_factory: ProviderFactory | None = None,
) -> ProviderConformanceReceipt:
    """Run one bounded H0 turn and return only a sanitized receipt.

    The caller owns ``session_root``.  The source snapshot is recomputed from
    the current H0 source/prompt/dependency bundle; an optional supplied digest
    acts only as a stale-source assertion. No live chemistry engine or scheduler
    path is reachable from the one-tool registry.  Provider failures are
    re-raised only as :class:`ProbeErrorClass` labels.
    """

    resolved = config or DeepSeekH0ProbeConfig()
    resolved_repo_root = (
        Path(repo_root)
        if repo_root is not None
        else Path(__file__).resolve().parents[3]
    )
    current_source_snapshot_sha256 = compute_source_snapshot_sha256(
        resolved_repo_root
    )
    if source_snapshot_sha256 is not None:
        if not re.fullmatch(_SHA256, source_snapshot_sha256):
            raise ValueError("source_snapshot_sha256 must be lowercase SHA-256")
        if source_snapshot_sha256 != current_source_snapshot_sha256:
            raise ValueError(
                "source_snapshot_sha256 does not match the current H0 "
                "source bundle"
            )
    source_snapshot_sha256 = current_source_snapshot_sha256
    sdk_version = importlib.metadata.version("openai")
    budget = ApiUsageBudget(resolved.max_network_requests)
    provider = _LeaseBoundDeepSeekProvider(
        controller=credential_controller,
        budget=budget,
        config=resolved,
        provider_factory=provider_factory,
    )
    registry = _inspect_only_registry()
    session = AgentSession(
        provider=provider,
        registry=registry,
        session_root=session_root,
        runtime_v2="active",
        tool_profile=_inspect_only_profile(),
        training_capture=False,
        behavior_rules_text="",
    )
    started = time.perf_counter()
    result = session.run_loop(
        _PROBE_REQUEST,
        budgets=ToolLoopBudgets(
            max_model_steps_per_turn=resolved.max_model_steps,
            max_total_tool_calls_per_turn=resolved.max_tool_calls,
            max_consecutive_tool_errors=1,
            max_same_signature_retries=1,
            max_provider_errors_per_turn=1,
            log_provider_turn_raw=False,
        ),
        log_raw_provider_turns=False,
        policy=PermissionPolicy(mode=RuntimePermissionMode.READ_ONLY),
    )
    wall_time_ms = max(0, int((time.perf_counter() - started) * 1000))
    if provider.safe_error_class is not None:
        raise ProviderConformanceProbeError(provider.safe_error_class)
    if session.session_dir is None:
        raise ProviderConformanceProbeError(ProbeErrorClass.PROVIDER_PROTOCOL)
    if _unsafe_persistence_found(session.session_dir):
        raise ProviderConformanceProbeError(ProbeErrorClass.UNSAFE_PERSISTENCE)
    public_history = result.get("messages")
    if (
        not isinstance(public_history, list)
        or any(not isinstance(message, dict) for message in public_history)
        or _contains_private_reasoning(public_history)
    ):
        raise ProviderConformanceProbeError(ProbeErrorClass.UNSAFE_PERSISTENCE)
    public_history_message_sha256s = tuple(
        _sha256_json(message) for message in public_history
    )
    public_history_sha256 = _sha256_json(
        public_history_message_sha256s
    )

    tool_requests = list(result.get("tool_requests") or [])
    tool_outcomes = list(result.get("tool_outcomes") or [])
    exact_request = (
        len(tool_requests) == 1
        and tool_requests[0].name == _REGISTERED_TOOL
        and tool_requests[0].arguments == {"request_context": _PROBE_CONTEXT}
    )
    exact_outcome = (
        len(tool_outcomes) == 1
        and tool_outcomes[0].name == _REGISTERED_TOOL
        and tool_outcomes[0].status == "ok"
        and isinstance(tool_outcomes[0].raw_result, dict)
    )
    direct_observation = inspect_command_schema(_PROBE_CONTEXT)
    deterministic_gate = bool(
        exact_outcome
        and tool_outcomes[0].raw_result.get("cli_schema_digest")
        == direct_observation.get("cli_schema_digest")
        and tool_outcomes[0].raw_result.get("schema_variant")
        == direct_observation.get("schema_variant")
        and result.get("runtime_v2", {}).get("mode") == "active"
        and not result.get("runtime_v2", {}).get("shadow_violations")
    )
    typed_round_trip = bool(
        exact_request
        and exact_outcome
        and result.get("loop_state", {}).get("tool_calls") == 1
        and provider.requests_used == 2
        and provider.public_history_replay_observed
        and provider.registered_tool_names == (_REGISTERED_TOOL,)
        and provider.virtual_tool_names == (_VIRTUAL_TOOL,)
        and not result.get("ask_user_question")
    )
    provider_response_count = len(result.get("provider_responses") or ())
    usage_response_count = _usage_response_count(result)
    usage_complete = (
        provider_response_count > 0
        and usage_response_count == provider_response_count
    )
    bounded_transport_accounting = bool(
        provider.transport_attempts == provider.requests_used
        and provider.requests_used == provider_response_count
        and usage_complete
    )

    checks = (
        _check(
            "typed_tool_call_round_trip",
            typed_round_trip,
            "One typed schema inspection completed across the tool continuation.",
            "provider.h0.typed_round_trip_failed",
        ),
        _check(
            "public_history_sanitized",
            True,
            "No raw provider turn or private reasoning key was persisted.",
            "provider.h0.unsafe_persistence",
        ),
        _check(
            "deterministic_validator_gate",
            deterministic_gate,
            "The tool receipt matched an independent live-schema observation.",
            "provider.h0.schema_observation_mismatch",
        ),
        _check(
            "bounded_transport_accounting",
            bounded_transport_accounting,
            "Each zero-retry request has one response with complete usage.",
            "provider.h0.transport_or_usage_incomplete",
        ),
    )
    verdict = (
        "incompatible"
        if any(check.status is ConformanceStatus.FAIL for check in checks)
        else "compatible"
    )
    observed_model = provider.observed_model_id
    if not observed_model:
        raise ProviderConformanceProbeError(ProbeErrorClass.PROVIDER_PROTOCOL)

    usage = {
        "requests_used": provider.requests_used,
        "transport_attempts": provider.transport_attempts,
        "model_steps": int(result.get("loop_state", {}).get("model_steps") or 0),
        "tool_calls": int(result.get("loop_state", {}).get("tool_calls") or 0),
        "input_tokens": _sum_usage(result, "input_tokens"),
        "output_tokens": _sum_usage(result, "output_tokens"),
        "usage_complete": usage_complete,
        "wall_time_ms": wall_time_ms,
        "engine_calls": 0,
        "hpc_calls": 0,
    }
    resources = {
        "max_network_requests": resolved.max_network_requests,
        "max_model_steps": resolved.max_model_steps,
        "max_tool_calls": resolved.max_tool_calls,
        "max_output_tokens": resolved.max_output_tokens,
        "engine_call_budget": 0,
        "hpc_call_budget": 0,
        "raw_provider_turn_logging": False,
        "sdk_max_retries": 0,
        "thinking_mode": resolved.thinking_mode,
        "training_capture": False,
    }
    transcript = ProviderProbeObservation(
        request_sha256=DEEPSEEK_H0_REQUEST_SHA256,
        source_snapshot_sha256=source_snapshot_sha256,
        target_origin=resolved.endpoint,
        instruction_bundle_sha256=provider.instruction_bundle_sha256,
        instruction_message_count=provider.instruction_message_count,
        tool_schema_sha256=provider.tool_schema_sha256,
        tool_schema_entry_count=(
            len(provider.registered_tool_names)
            + len(provider.virtual_tool_names)
        ),
        public_history_message_sha256s=public_history_message_sha256s,
        model=observed_model,
        tool_requests=tuple(
            ProbeToolRequestObservation(
                name=request.name,
                arguments_sha256=_sha256_json(request.arguments),
            )
            for request in tool_requests
        ),
        tool_outcomes=tuple(
            ProbeToolOutcomeObservation(
                name=outcome.name,
                status=outcome.status,
                result_sha256=_sha256_json(outcome.raw_result),
            )
            for outcome in tool_outcomes
        ),
        stop_reason=result.get("loop_state", {}).get("stop_reason"),
        runtime_mode=str(result.get("runtime_v2", {}).get("mode") or ""),
        runtime_phase=str(result.get("runtime_v2", {}).get("phase") or ""),
        runtime_shadow_violations=tuple(
            str(value)
            for value in result.get("runtime_v2", {}).get(
                "shadow_violations", ()
            )
        ),
        permission_mode=str(result.get("approval_mode") or ""),
        sdk_name="openai",
        sdk_version=sdk_version,
        sdk_max_retries=0,
        provider_response_count=provider_response_count,
        usage_response_count=usage_response_count,
    )
    capabilities = _observed_capabilities(
        provider,
        observed_model,
        structured_tool_calls=bool(tool_requests),
    )
    receipt_payload: dict[str, Any] = {
        "schema_version": PROVIDER_CONFORMANCE_SCHEMA_VERSION,
        "profile": HarnessProfile.H0,
        "capabilities": capabilities,
        "requested_model_id": resolved.model,
        "observed_model_id": observed_model,
        "target_origin": resolved.endpoint,
        "request_sha256": DEEPSEEK_H0_REQUEST_SHA256,
        "source_snapshot_sha256": source_snapshot_sha256,
        "instruction_bundle_sha256": provider.instruction_bundle_sha256,
        "tool_schema_sha256": provider.tool_schema_sha256,
        "public_history_sha256": public_history_sha256,
        "resource_budget_sha256": _sha256_json(resources),
        "observed_usage_sha256": _sha256_json(usage),
        "probe_transcript_sha256": _sha256_json(
            transcript.model_dump(mode="json")
        ),
        "probe_observation": transcript,
        "sdk_name": "openai",
        "sdk_version": sdk_version,
        "sdk_max_retries": 0,
        "thinking_mode": resolved.thinking_mode,
        "max_output_tokens": resolved.max_output_tokens,
        "request_budget": resolved.max_network_requests,
        "model_step_budget": resolved.max_model_steps,
        "tool_call_budget": resolved.max_tool_calls,
        "engine_call_budget": 0,
        "hpc_call_budget": 0,
        "requests_used": provider.requests_used,
        "transport_attempts": provider.transport_attempts,
        "model_steps": usage["model_steps"],
        "tool_calls": usage["tool_calls"],
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "usage_complete": usage_complete,
        "wall_time_ms": usage["wall_time_ms"],
        "registered_tool_names": provider.registered_tool_names,
        "virtual_tool_names": provider.virtual_tool_names,
        "engine_calls": 0,
        "hpc_calls": 0,
        "credential_status": "valid",
        "quota_sufficient_for_probe": (
            provider.requests_used == resolved.max_network_requests
        ),
        "checks": checks,
        "verdict": verdict,
        "raw_provider_turns_persisted": False,
        "training_data_persisted": False,
        "private_reasoning_persisted": False,
        "secret_material_persisted": False,
    }
    return ProviderConformanceReceipt(
        receipt_id=provider_conformance_receipt_id(receipt_payload),
        **receipt_payload,
    )


def _inspect_only_registry() -> ToolRegistry:
    source = ToolRegistry.default(groups=["synthesis"])
    tool = source.get_tool(_REGISTERED_TOOL)
    if tool is None:  # pragma: no cover - checked repository invariant
        raise ProviderConformanceProbeError(ProbeErrorClass.PROVIDER_PROTOCOL)
    return ToolRegistry([tool])


def validate_deepseek_h0_receipt_bindings(
    receipt: ProviderConformanceReceipt,
    *,
    repo_root: str | Path,
) -> tuple[str, ...]:
    """Recompute local H0 source, tool, SDK, and runtime bindings.

    Pydantic establishes internal receipt coherence.  This independent gate
    additionally compares the receipt with the validator's current checkout
    and installed SDK, so a self-consistent stale or fabricated body cannot be
    treated as current compatible evidence.
    """

    findings = list(validate_provider_conformance_receipt_identity(receipt))
    observation = receipt.probe_observation
    if receipt.profile is not HarnessProfile.H0:
        findings.append("provider.h0.profile_mismatch")
    if receipt.request_sha256 != DEEPSEEK_H0_REQUEST_SHA256:
        findings.append("provider.h0.request_digest_mismatch")
    if receipt.target_origin != DEEPSEEK_H0_TARGET_ORIGIN:
        findings.append("provider.h0.target_origin_mismatch")
    if receipt.source_snapshot_sha256 != compute_source_snapshot_sha256(
        repo_root
    ):
        findings.append("provider.h0.source_snapshot_stale")
    installed_sdk = importlib.metadata.version("openai")
    if receipt.sdk_name != "openai" or receipt.sdk_version != installed_sdk:
        findings.append("provider.h0.sdk_binding_mismatch")
    expected_tools = registry_tool_defs_for_provider(
        _inspect_only_registry(), "deepseek"
    )
    if receipt.tool_schema_sha256 != _sha256_json(expected_tools):
        findings.append("provider.h0.tool_schema_stale")
    expected_names = tuple(
        name
        for name in (_tool_name(definition) for definition in expected_tools)
        if name
    )
    if expected_names != (
        *receipt.registered_tool_names,
        *receipt.virtual_tool_names,
    ):
        findings.append("provider.h0.tool_surface_mismatch")
    if (
        len(observation.tool_requests) != 1
        or observation.tool_requests[0].arguments_sha256
        != DEEPSEEK_H0_TOOL_ARGUMENTS_SHA256
    ):
        findings.append("provider.h0.tool_arguments_mismatch")
    if (
        observation.runtime_mode != "active"
        or observation.runtime_phase != "complete"
        or observation.runtime_shadow_violations
        or observation.permission_mode != "read_only"
    ):
        findings.append("provider.h0.runtime_binding_mismatch")
    if (
        receipt.sdk_max_retries != 0
        or receipt.transport_attempts != receipt.requests_used
    ):
        findings.append("provider.h0.transport_budget_mismatch")
    if not receipt.usage_complete:
        findings.append("provider.h0.usage_incomplete")
    return tuple(dict.fromkeys(findings))


def _inspect_only_profile() -> PhaseToolProfile:
    phases = {phase: (_REGISTERED_TOOL,) for phase in TaskPhase}
    return PhaseToolProfile(
        phases,
        specialist_tools=(_REGISTERED_TOOL,),
    )


def _observed_capabilities(
    provider: _LeaseBoundDeepSeekProvider,
    observed_model: str,
    *,
    structured_tool_calls: bool,
) -> ProviderCapabilities:
    continued = provider.public_history_replay_observed
    reasoning = provider.reasoning_continuation_observed
    return ProviderCapabilities(
        provider_id="deepseek",
        endpoint_class="official",
        wire_protocol="openai_chat",
        resolved_model=observed_model,
        structured_tool_calls=structured_tool_calls,
        structured_tool_calls_basis=(
            CapabilityEvidenceBasis.OBSERVED_PROBE
            if structured_tool_calls
            else CapabilityEvidenceBasis.NOT_EVALUATED
        ),
        structured_output=False,
        tool_continuation=(
            ContinuationMode.PUBLIC_HISTORY
            if continued
            else ContinuationMode.NONE
        ),
        tool_continuation_basis=(
            CapabilityEvidenceBasis.OBSERVED_PROBE
            if continued
            else CapabilityEvidenceBasis.NOT_EVALUATED
        ),
        reasoning_continuation=(
            ContinuationMode.EPHEMERAL_PRIVATE_TURN
            if reasoning
            else ContinuationMode.NONE
        ),
        reasoning_continuation_basis=(
            CapabilityEvidenceBasis.OBSERVED_PROBE
            if reasoning
            else CapabilityEvidenceBasis.NOT_EVALUATED
        ),
        public_history_replay=continued,
        public_history_replay_basis=(
            CapabilityEvidenceBasis.OBSERVED_PROBE
            if continued
            else CapabilityEvidenceBasis.NOT_EVALUATED
        ),
        max_context_tokens=1_000_000,
        max_context_tokens_basis=(
            CapabilityEvidenceBasis.OFFICIAL_DOCUMENTATION
        ),
        max_parallel_tool_calls=1,
        max_parallel_tool_calls_basis=CapabilityEvidenceBasis.HARNESS_LIMIT,
        supports_compaction=False,
        supports_checkpoint=False,
        supports_fork_resume=False,
    )


def _check(
    check_id: str,
    passed: bool,
    summary: str,
    rule_id: str,
) -> ConformanceCheck:
    return ConformanceCheck(
        check_id=check_id,
        status=(ConformanceStatus.PASS if passed else ConformanceStatus.FAIL),
        rule_ids=(() if passed else (rule_id,)),
        public_summary=summary,
    )


def _sum_usage(result: dict[str, Any], field: str) -> int:
    total = 0
    for response in result.get("provider_responses") or []:
        if not isinstance(response, dict):
            continue
        usage = response.get("usage")
        if not isinstance(usage, dict):
            continue
        value = usage.get(field)
        if isinstance(value, int) and not isinstance(value, bool):
            total += value
    return total


def _usage_response_count(result: dict[str, Any]) -> int:
    complete = 0
    for response in result.get("provider_responses") or []:
        if not isinstance(response, dict):
            continue
        usage = response.get("usage")
        if not isinstance(usage, dict):
            continue
        values = (usage.get("input_tokens"), usage.get("output_tokens"))
        if all(
            isinstance(value, int)
            and not isinstance(value, bool)
            and value >= 0
            for value in values
        ):
            complete += 1
    return complete


def _unsafe_persistence_found(session_dir: Path) -> bool:
    for path in session_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        values: list[Any] = []
        try:
            values.append(json.loads(text))
        except json.JSONDecodeError:
            pass
        if not values:
            for line in text.splitlines():
                try:
                    values.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        for value in values:
            if _contains_private_reasoning(value):
                return True
            if isinstance(value, dict) and value.get("kind") == "provider_turn_raw":
                return True
    return False


def _contains_private_reasoning(value: Any) -> bool:
    if isinstance(value, dict):
        if any(key in value for key in _PRIVATE_REASONING_KEYS):
            return True
        return any(_contains_private_reasoning(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_private_reasoning(item) for item in value)
    if isinstance(value, str):
        return "<think" in value.lower()
    return False


def _classify_provider_error(exc: Exception) -> ProbeErrorClass:
    name = exc.__class__.__name__.lower()
    if "authentication" in name or "unauthorized" in name:
        return ProbeErrorClass.AUTHENTICATION
    if "permission" in name or "forbidden" in name:
        return ProbeErrorClass.ENTITLEMENT
    if "ratelimit" in name or "quota" in name:
        return ProbeErrorClass.QUOTA_OR_RATE_LIMIT
    if "timeout" in name:
        return ProbeErrorClass.TIMEOUT
    if "connection" in name:
        return ProbeErrorClass.CONNECTION
    if "badrequest" in name or "unprocessable" in name:
        return ProbeErrorClass.REQUEST_REJECTED
    return ProbeErrorClass.PROVIDER_ERROR


def _tool_name(definition: dict[str, Any]) -> str:
    if not isinstance(definition, dict):
        return ""
    function = definition.get("function")
    if isinstance(function, dict):
        name = function.get("name")
        return name if isinstance(name, str) else ""
    name = definition.get("name")
    return name if isinstance(name, str) else ""


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = [
    "compute_source_snapshot_sha256",
    "DEEPSEEK_H0_REQUEST_SHA256",
    "DeepSeekH0ProbeConfig",
    "ProbeErrorClass",
    "ProviderConformanceProbeError",
    "run_deepseek_h0_conformance_probe",
    "validate_deepseek_h0_receipt_bindings",
]
