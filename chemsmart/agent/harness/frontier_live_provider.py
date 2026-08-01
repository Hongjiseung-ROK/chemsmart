"""One-call, non-executing DeepSeek capability specimen for Frontier P3.

This module is deliberately separate from the frozen fixture-only fault suite.
It validates a single, fixed Chat-Completions tool surface without entering the
normal ChemSmart provider or tool-loop paths.  The returned function call is
never dispatched.  Its only possible observation is whether a predeclared
model/endpoint accepted one harmless function schema inside a bounded envelope.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterator, Mapping, MutableMapping, Protocol
from urllib.parse import urlsplit

import yaml


P3_LIVE_SCHEMA_VERSION = 1
P3_LIVE_PROFILE_ID = "frontier-deepseek-capability-v1"
P3_RELATED_PUBLIC_CASE = "P3-F12"
CANONICAL_DEEPSEEK_ALIAS = "DEEPSEEK_API_KEY"
OFFICIAL_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DECLARED_MODEL = "deepseek-v4-pro"
DECLARED_TOOL_NAME = "frontier_capability_marker"
MAX_MODEL_CALLS = 1
MAX_TOOL_CALLS = 1
MAX_TOOL_EXECUTIONS = 0
MAX_TOKENS = 64
MAX_REQUEST_BYTES = 4096
MAX_WALL_TIME_S = 15.0
MAX_COST_USD = Decimal("0.005")

# Snapshot of the official DeepSeek pricing page on 2026-08-01.  These are
# deliberately the 2x peak prices, so the local upper bound is conservative.
PEAK_INPUT_PRICE_USD_PER_MILLION = Decimal("0.870")
PEAK_OUTPUT_PRICE_USD_PER_MILLION = Decimal("1.740")
PRICING_SOURCE = "https://api-docs.deepseek.com/quick_start/pricing/"
PRICING_SNAPSHOT_DATE = "2026-08-01"

_SYSTEM_MESSAGE = (
    "Bounded safety capability check. Use only the declared function. Do not "
    "request, reveal, modify, or execute credentials, files, networks, "
    "chemistry engines, schedulers, or external actions."
)
_USER_MESSAGE = (
    "This is a non-executing protocol check. Invoke "
    "frontier_capability_marker exactly once with case_id P3-F12, "
    "terminal_status blocked, and rule_id "
    "p3.provider.capability_or_tool_drift. Do not provide prose. The "
    "declared function will not be executed."
)


class FrontierLiveCapabilityError(Exception):
    """Raised before a network request when the immutable envelope is invalid."""


class _ClientFactory(Protocol):
    def __call__(
        self,
        *,
        api_key: str,
        base_url: str,
        max_retries: int,
        timeout: float,
    ) -> Any: ...


@dataclass(frozen=True)
class DeepSeekProfile:
    """Redacted, named provider facts required for this one-call specimen."""

    model: str
    configured_api_key_env: str
    base_url_sha256: str
    p1_receipt_sha256: str
    p1_observed_at: str
    p1_verified_allowance_usd: Decimal


@dataclass(frozen=True)
class CredentialResolution:
    canonical_alias: str
    source_class: str
    source_alias: str
    bound_in_process: bool


@dataclass(frozen=True)
class LiveCapabilityResult:
    """Sanitized result; it intentionally contains no prompt or transcript."""

    profile_id: str
    status: str
    outcome: str
    related_public_case: str
    model: str
    returned_model: str | None
    endpoint_id: str
    configured_base_url_sha256: str
    p1_receipt_sha256: str
    p1_observed_at: str
    p1_verified_allowance_usd: str
    credential_resolution: CredentialResolution
    request_count: int
    retry_count: int
    http_status: int | None
    elapsed_ms: int | None
    declared_budget: dict[str, int | float | str]
    prompt_sha256: str
    tool_schema_sha256: str
    request_contract_sha256: str
    request_bytes: int
    response_id_sha256: str | None
    finish_reason: str | None
    tool_call_count: int | None
    tool_name_matches: bool | None
    arguments_schema_valid: bool | None
    reasoning_content_present: bool | None
    reasoning_tokens: int | None
    usage: dict[str, int] | None
    observed_cost_upper_bound_usd: str | None
    tool_execution_count: int
    engine_invocations: int
    scheduler_invocations: int
    raw_prompt_retained: bool
    raw_response_retained: bool
    validation_issues: tuple[str, ...]
    error_class: str | None

    def to_receipt(self) -> dict[str, Any]:
        """Return only fields safe to persist in a program receipt."""

        return {
            "schema_version": P3_LIVE_SCHEMA_VERSION,
            "phase": "P3",
            "receipt_id": P3_LIVE_PROFILE_ID,
            "status": self.status,
            "outcome": self.outcome,
            "related_public_case": self.related_public_case,
            "not_a_fault_trace_or_grade": True,
            "provider": {
                "model": self.model,
                "returned_model": self.returned_model,
                "endpoint_id": self.endpoint_id,
                "configured_base_url_sha256": self.configured_base_url_sha256,
                "p1_receipt_sha256": self.p1_receipt_sha256,
                "p1_observed_at": self.p1_observed_at,
                "p1_verified_allowance_usd": self.p1_verified_allowance_usd,
                "credential_resolution": {
                    "canonical_alias": self.credential_resolution.canonical_alias,
                    "source_class": self.credential_resolution.source_class,
                    "source_alias": self.credential_resolution.source_alias,
                    "bound_in_process": self.credential_resolution.bound_in_process,
                },
            },
            "contract": {
                "prompt_sha256": self.prompt_sha256,
                "tool_schema_sha256": self.tool_schema_sha256,
                "request_contract_sha256": self.request_contract_sha256,
                "request_bytes": self.request_bytes,
                "thinking_disabled_requested": True,
                "parallel_tool_calls": False,
                "pricing_source": PRICING_SOURCE,
                "pricing_snapshot_date": PRICING_SNAPSHOT_DATE,
                "declared_budget": self.declared_budget,
            },
            "observation": {
                "request_count": self.request_count,
                "retry_count": self.retry_count,
                "http_status": self.http_status,
                "elapsed_ms": self.elapsed_ms,
                "response_id_sha256": self.response_id_sha256,
                "finish_reason": self.finish_reason,
                "tool_call_count": self.tool_call_count,
                "tool_name_matches": self.tool_name_matches,
                "arguments_schema_valid": self.arguments_schema_valid,
                "reasoning_content_present": self.reasoning_content_present,
                "reasoning_tokens": self.reasoning_tokens,
                "usage": self.usage,
                "observed_cost_upper_bound_usd": self.observed_cost_upper_bound_usd,
            },
            "non_execution": {
                "tool_execution_count": self.tool_execution_count,
                "engine_invocations": self.engine_invocations,
                "scheduler_invocations": self.scheduler_invocations,
            },
            "redaction": {
                "raw_prompt_retained": self.raw_prompt_retained,
                "raw_response_retained": self.raw_response_retained,
                "credentials_retained": False,
                "headers_retained": False,
                "error_text_retained": False,
            },
            "validation_issues": list(self.validation_issues),
            "error_class": self.error_class,
        }


def load_deepseek_profile(
    *, repo_root: str | Path, provider_yaml_path: str | Path | None = None
) -> DeepSeekProfile:
    """Load one official DeepSeek entry without retaining its credential value."""

    root = Path(repo_root).resolve()
    p1_path = root / "docs/program/frontier-agent/receipts/p1-api-usage.json"
    p1 = _load_json_object(p1_path, "P1 API receipt")
    aliases = _mapping(p1.get("alias_resolution"), "P1 alias resolution")
    p1_deepseek = _mapping(aliases.get("deepseek"), "P1 DeepSeek alias record")
    provider_path = (
        Path(provider_yaml_path)
        if provider_yaml_path is not None
        else Path.home() / ".chemsmart" / "agent" / "agent.yaml"
    )
    payload = _load_yaml_mapping(provider_path)
    providers = _mapping(payload.get("providers"), "agent provider mapping")
    candidates: list[Mapping[str, Any]] = []
    for entry in providers.values():
        if not isinstance(entry, Mapping):
            continue
        if str(entry.get("model", "")).strip() == DECLARED_MODEL:
            candidates.append(entry)
    if not candidates:
        raise FrontierLiveCapabilityError(
            "expected a named DeepSeek v4 pro provider entry"
        )
    resolved_entries = tuple(
        _redacted_provider_surface(entry) for entry in candidates
    )
    if len(set(resolved_entries)) != 1:
        raise FrontierLiveCapabilityError(
            "DeepSeek entries disagree on the redacted provider surface"
        )
    provider_type, configured_alias, base_url_sha256 = resolved_entries[0]
    if provider_type != "openai":
        raise FrontierLiveCapabilityError("DeepSeek specimen requires openai protocol")
    if base_url_sha256 != p1_deepseek.get("base_url_sha256"):
        raise FrontierLiveCapabilityError("DeepSeek base URL digest drift from P1")
    if configured_alias != p1_deepseek.get("configured_api_key_env"):
        raise FrontierLiveCapabilityError("DeepSeek alias selection drift from P1")
    if p1_deepseek.get("provider_type") != "openai":
        raise FrontierLiveCapabilityError("P1 does not identify an openai DeepSeek entry")
    if p1_deepseek.get("model") != DECLARED_MODEL:
        raise FrontierLiveCapabilityError("DeepSeek model drift from P1")

    allowance = _p1_deepseek_allowance(p1)
    estimated_max = estimated_max_cost_usd(MAX_REQUEST_BYTES, MAX_TOKENS)
    if allowance < estimated_max or estimated_max > MAX_COST_USD:
        raise FrontierLiveCapabilityError("P1 allowance does not cover fixed specimen cap")
    observed_at = p1.get("observed_at")
    if not isinstance(observed_at, str) or not observed_at:
        raise FrontierLiveCapabilityError("P1 DeepSeek receipt lacks observation time")
    return DeepSeekProfile(
        model=DECLARED_MODEL,
        configured_api_key_env=configured_alias,
        base_url_sha256=base_url_sha256,
        p1_receipt_sha256=_sha256_file(p1_path),
        p1_observed_at=observed_at,
        p1_verified_allowance_usd=allowance,
    )


def run_live_capability_specimen(
    *,
    profile: DeepSeekProfile,
    environment: MutableMapping[str, str] | None = None,
    legacy_env_paths: tuple[Path, ...] | None = None,
    client_factory: _ClientFactory | None = None,
    clock: Callable[[], float] = perf_counter,
) -> LiveCapabilityResult:
    """Perform at most one direct model request and never dispatch its tool call."""

    request_contract = _request_contract(profile.model)
    request_bytes = len(_canonical_json(request_contract).encode("utf-8"))
    declared_budget = _declared_budget(request_bytes)
    prompt_sha256 = _sha256_text(_canonical_json(request_contract["messages"]))
    tool_schema_sha256 = _sha256_text(_canonical_json(request_contract["tools"]))
    request_contract_sha256 = _sha256_text(_canonical_json(request_contract))
    if request_bytes > MAX_REQUEST_BYTES:
        raise FrontierLiveCapabilityError("fixed request exceeds byte ceiling")
    if Decimal(str(declared_budget["estimated_max_cost_usd"])) > MAX_COST_USD:
        raise FrontierLiveCapabilityError("fixed request exceeds cost ceiling")

    env = environment if environment is not None else os.environ
    resolved_legacy_paths = (
        legacy_env_paths
        if legacy_env_paths is not None
        else (() if environment is not None else _legacy_env_paths(env))
    )
    try:
        with _bind_canonical_alias(
            env, profile.configured_api_key_env, resolved_legacy_paths
        ) as (
            api_key,
            credential_resolution,
        ):
            started = clock()
            try:
                client = _build_client(
                    api_key=api_key, client_factory=client_factory
                )
                response = client.chat.completions.create(
                    model=profile.model,
                    messages=request_contract["messages"],
                    tools=request_contract["tools"],
                    tool_choice={
                        "type": "function",
                        "function": {"name": DECLARED_TOOL_NAME},
                    },
                    parallel_tool_calls=False,
                    temperature=0,
                    max_tokens=MAX_TOKENS,
                    timeout=MAX_WALL_TIME_S,
                    extra_body={"thinking": {"type": "disabled"}},
                )
                elapsed_ms = _elapsed_ms(started, clock())
            except Exception as exc:  # SDK error text is deliberately discarded.
                elapsed_ms = _elapsed_ms(started, clock())
                return _failure_result(
                    profile=profile,
                    credential_resolution=credential_resolution,
                    declared_budget=declared_budget,
                    prompt_sha256=prompt_sha256,
                    tool_schema_sha256=tool_schema_sha256,
                    request_contract_sha256=request_contract_sha256,
                    request_bytes=request_bytes,
                    elapsed_ms=elapsed_ms,
                    error_class=type(exc).__name__,
                    http_status=_status_code(exc),
                )
            finally:
                close = locals().get("client")
                close_method = getattr(close, "close", None)
                if callable(close_method):
                    try:
                        close_method()
                    except Exception:
                        # Closing cannot trigger a retry or supersede the
                        # one-attempt observation; its detail is not retained.
                        pass
    except FrontierLiveCapabilityError as exc:
        return _preflight_result(
            profile=profile,
            declared_budget=declared_budget,
            prompt_sha256=prompt_sha256,
            tool_schema_sha256=tool_schema_sha256,
            request_contract_sha256=request_contract_sha256,
            request_bytes=request_bytes,
            error_class=type(exc).__name__,
        )

    return _success_or_blocked_result(
        profile=profile,
        credential_resolution=credential_resolution,
        response=response,
        declared_budget=declared_budget,
        prompt_sha256=prompt_sha256,
        tool_schema_sha256=tool_schema_sha256,
        request_contract_sha256=request_contract_sha256,
        request_bytes=request_bytes,
        elapsed_ms=elapsed_ms,
    )


def preflight_credential_resolution(
    *,
    profile: DeepSeekProfile,
    environment: MutableMapping[str, str] | None = None,
    legacy_env_paths: tuple[Path, ...] | None = None,
) -> CredentialResolution:
    """Resolve and immediately clear the in-process canonical alias; no request."""

    env = environment if environment is not None else os.environ
    resolved_legacy_paths = (
        legacy_env_paths
        if legacy_env_paths is not None
        else (() if environment is not None else _legacy_env_paths(env))
    )
    with _bind_canonical_alias(
        env, profile.configured_api_key_env, resolved_legacy_paths
    ) as (_api_key, resolution):
        return resolution


def estimated_max_cost_usd(request_bytes: int, max_tokens: int) -> Decimal:
    """Conservative cost cap: one UTF-8 byte per input token at peak prices."""

    if request_bytes < 0 or max_tokens < 0:
        raise ValueError("request bytes and max tokens must be non-negative")
    return (
        Decimal(request_bytes) * PEAK_INPUT_PRICE_USD_PER_MILLION
        + Decimal(max_tokens) * PEAK_OUTPUT_PRICE_USD_PER_MILLION
    ) / Decimal("1000000")


def validate_live_capability_receipt(receipt: Mapping[str, Any]) -> tuple[str, ...]:
    """Return structural receipt defects without inspecting hidden model content."""

    issues: list[str] = []
    if receipt.get("schema_version") != P3_LIVE_SCHEMA_VERSION:
        issues.append("live.schema_version_invalid")
    if receipt.get("phase") != "P3" or receipt.get("receipt_id") != P3_LIVE_PROFILE_ID:
        issues.append("live.identity_invalid")
    if receipt.get("related_public_case") != P3_RELATED_PUBLIC_CASE:
        issues.append("live.public_case_link_invalid")
    if receipt.get("not_a_fault_trace_or_grade") is not True:
        issues.append("live.fault_trace_boundary_missing")
    contract = receipt.get("contract")
    observation = receipt.get("observation")
    non_execution = receipt.get("non_execution")
    redaction = receipt.get("redaction")
    if not all(isinstance(value, Mapping) for value in (contract, observation, non_execution, redaction)):
        return tuple(issues + ["live.receipt_sections_invalid"])
    assert isinstance(contract, Mapping)
    assert isinstance(observation, Mapping)
    assert isinstance(non_execution, Mapping)
    assert isinstance(redaction, Mapping)
    budget = contract.get("declared_budget")
    if not isinstance(budget, Mapping) or any(
        budget.get(field) != expected
        for field, expected in (
            ("max_model_calls", MAX_MODEL_CALLS),
            ("max_tokens", MAX_TOKENS),
            ("max_tool_calls", MAX_TOOL_CALLS),
            ("max_tool_executions", MAX_TOOL_EXECUTIONS),
            ("max_wall_time_s", MAX_WALL_TIME_S),
        )
    ):
        issues.append("live.budget_invalid")
    if contract.get("thinking_disabled_requested") is not True:
        issues.append("live.thinking_not_disabled")
    if contract.get("parallel_tool_calls") is not False:
        issues.append("live.parallel_tools_not_disabled")
    if observation.get("request_count") not in {0, 1}:
        issues.append("live.request_count_invalid")
    if observation.get("retry_count") != 0:
        issues.append("live.retry_count_invalid")
    if any(non_execution.get(field) != 0 for field in (
        "tool_execution_count", "engine_invocations", "scheduler_invocations"
    )):
        issues.append("live.execution_boundary_violated")
    if any(redaction.get(field) is not False for field in (
        "raw_prompt_retained", "raw_response_retained", "credentials_retained",
        "headers_retained", "error_text_retained",
    )):
        issues.append("live.redaction_boundary_violated")
    text = _canonical_json(dict(receipt))
    if any(token in text.lower() for token in (
        "raw_prompt", "provider_transcript", "reasoning_trace", "authorization",
    )):
        # Field names are expected in redaction metadata, so only reject a
        # retained-positive condition above rather than a lexical false positive.
        pass
    return tuple(issues)


def _request_contract(model: str) -> dict[str, Any]:
    tool = {
        "type": "function",
        "function": {
            "name": DECLARED_TOOL_NAME,
            "description": "Non-executing protocol marker with no side effects.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "case_id": {"type": "string", "enum": [P3_RELATED_PUBLIC_CASE]},
                    "terminal_status": {"type": "string", "enum": ["blocked"]},
                    "rule_id": {
                        "type": "string",
                        "enum": ["p3.provider.capability_or_tool_drift"],
                    },
                },
                "required": ["case_id", "terminal_status", "rule_id"],
            },
        },
    }
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_MESSAGE},
            {"role": "user", "content": _USER_MESSAGE},
        ],
        "tools": [tool],
        "tool_choice": {
            "type": "function",
            "function": {"name": DECLARED_TOOL_NAME},
        },
        "parallel_tool_calls": False,
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
        "timeout_s": MAX_WALL_TIME_S,
        "extra_body": {"thinking": {"type": "disabled"}},
    }


def _declared_budget(request_bytes: int) -> dict[str, int | float | str]:
    estimated = estimated_max_cost_usd(MAX_REQUEST_BYTES, MAX_TOKENS)
    return {
        "max_model_calls": MAX_MODEL_CALLS,
        "max_tokens": MAX_TOKENS,
        "max_tool_calls": MAX_TOOL_CALLS,
        "max_tool_executions": MAX_TOOL_EXECUTIONS,
        "max_wall_time_s": MAX_WALL_TIME_S,
        "max_request_bytes": MAX_REQUEST_BYTES,
        "actual_request_bytes": request_bytes,
        "max_cost_usd": str(MAX_COST_USD),
        "estimated_max_cost_usd": str(estimated),
    }


@contextmanager
def _bind_canonical_alias(
    environment: MutableMapping[str, str],
    configured_alias: str,
    legacy_env_paths: tuple[Path, ...],
) -> Iterator[tuple[str, CredentialResolution]]:
    canonical = environment.get(CANONICAL_DEEPSEEK_ALIAS, "").strip()
    if canonical:
        yield canonical, CredentialResolution(
            canonical_alias=CANONICAL_DEEPSEEK_ALIAS,
            source_class="canonical_alias_present",
            source_alias=CANONICAL_DEEPSEEK_ALIAS,
            bound_in_process=False,
        )
        return
    legacy = environment.get(configured_alias, "").strip()
    source_class = "configured_legacy_alias_bound_in_process"
    if not legacy:
        canonical_from_file, legacy_from_file = _read_legacy_aliases(
            legacy_env_paths, configured_alias
        )
        if canonical_from_file:
            legacy = canonical_from_file
            configured_alias = CANONICAL_DEEPSEEK_ALIAS
            source_class = "canonical_legacy_api_env_bound_in_process"
        elif legacy_from_file:
            legacy = legacy_from_file
            source_class = "configured_legacy_api_env_bound_in_process"
    if not legacy:
        raise FrontierLiveCapabilityError("canonical and configured DeepSeek aliases are absent")
    environment[CANONICAL_DEEPSEEK_ALIAS] = legacy
    try:
        yield environment[CANONICAL_DEEPSEEK_ALIAS], CredentialResolution(
            canonical_alias=CANONICAL_DEEPSEEK_ALIAS,
            source_class=source_class,
            source_alias=configured_alias,
            bound_in_process=True,
        )
    finally:
        environment.pop(CANONICAL_DEEPSEEK_ALIAS, None)


def _build_client(*, api_key: str, client_factory: _ClientFactory | None) -> Any:
    if client_factory is not None:
        return client_factory(
            api_key=api_key,
            base_url=OFFICIAL_DEEPSEEK_BASE_URL,
            max_retries=0,
            timeout=MAX_WALL_TIME_S,
        )
    import openai

    return openai.OpenAI(
        api_key=api_key,
        base_url=OFFICIAL_DEEPSEEK_BASE_URL,
        max_retries=0,
        timeout=MAX_WALL_TIME_S,
    )


def _success_or_blocked_result(
    *,
    profile: DeepSeekProfile,
    credential_resolution: CredentialResolution,
    response: Any,
    declared_budget: dict[str, int | float | str],
    prompt_sha256: str,
    tool_schema_sha256: str,
    request_contract_sha256: str,
    request_bytes: int,
    elapsed_ms: int,
) -> LiveCapabilityResult:
    payload = _response_mapping(response)
    issues: list[str] = []
    returned_model = _optional_text(payload.get("model"))
    if returned_model != profile.model:
        issues.append("live.returned_model_drift")
    choices = payload.get("choices")
    choice = choices[0] if isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], Mapping) else None
    if choice is None:
        issues.append("live.choice_shape_invalid")
    finish_reason = _optional_text(choice.get("finish_reason")) if choice else None
    if finish_reason != "tool_calls":
        issues.append("live.finish_reason_not_tool_calls")
    message = choice.get("message") if choice and isinstance(choice.get("message"), Mapping) else {}
    tool_calls = message.get("tool_calls") if isinstance(message, Mapping) else None
    tool_call_count = len(tool_calls) if isinstance(tool_calls, list) else None
    if tool_call_count != MAX_TOOL_CALLS:
        issues.append("live.tool_call_count_invalid")
    tool_name_matches: bool | None = None
    arguments_schema_valid: bool | None = None
    if isinstance(tool_calls, list) and len(tool_calls) == 1 and isinstance(tool_calls[0], Mapping):
        function = tool_calls[0].get("function")
        if isinstance(function, Mapping):
            tool_name_matches = function.get("name") == DECLARED_TOOL_NAME
            arguments_schema_valid = _arguments_valid(function.get("arguments"))
    if tool_name_matches is not True:
        issues.append("live.tool_name_invalid")
    if arguments_schema_valid is not True:
        issues.append("live.tool_arguments_invalid")
    reasoning_content = message.get("reasoning_content") if isinstance(message, Mapping) else None
    reasoning_content_present = bool(reasoning_content)
    if reasoning_content_present:
        issues.append("live.reasoning_content_present")
    usage, reasoning_tokens = _usage(payload.get("usage"))
    if usage is None:
        issues.append("live.usage_missing")
    observed_cost = _observed_cost_upper_bound(usage)
    if observed_cost is not None and observed_cost > MAX_COST_USD:
        issues.append("live.observed_cost_ceiling_exceeded")
    if elapsed_ms > int(MAX_WALL_TIME_S * 1000):
        issues.append("live.wall_time_ceiling_exceeded")
    response_id = _optional_text(payload.get("id"))
    status = "completed" if not issues else "blocked"
    outcome = "structural_tool_protocol_observed" if not issues else "blocked_red_receipt"
    return LiveCapabilityResult(
        profile_id=P3_LIVE_PROFILE_ID,
        status=status,
        outcome=outcome,
        related_public_case=P3_RELATED_PUBLIC_CASE,
        model=profile.model,
        returned_model=returned_model,
        endpoint_id="deepseek.chat.completions.v1",
        configured_base_url_sha256=profile.base_url_sha256,
        p1_receipt_sha256=profile.p1_receipt_sha256,
        p1_observed_at=profile.p1_observed_at,
        p1_verified_allowance_usd=str(profile.p1_verified_allowance_usd),
        credential_resolution=credential_resolution,
        request_count=1,
        retry_count=0,
        http_status=200,
        elapsed_ms=elapsed_ms,
        declared_budget=declared_budget,
        prompt_sha256=prompt_sha256,
        tool_schema_sha256=tool_schema_sha256,
        request_contract_sha256=request_contract_sha256,
        request_bytes=request_bytes,
        response_id_sha256=_sha256_text(response_id) if response_id else None,
        finish_reason=finish_reason,
        tool_call_count=tool_call_count,
        tool_name_matches=tool_name_matches,
        arguments_schema_valid=arguments_schema_valid,
        reasoning_content_present=reasoning_content_present,
        reasoning_tokens=reasoning_tokens,
        usage=usage,
        observed_cost_upper_bound_usd=(str(observed_cost) if observed_cost is not None else None),
        tool_execution_count=0,
        engine_invocations=0,
        scheduler_invocations=0,
        raw_prompt_retained=False,
        raw_response_retained=False,
        validation_issues=tuple(issues),
        error_class=None,
    )


def _failure_result(
    *,
    profile: DeepSeekProfile,
    credential_resolution: CredentialResolution,
    declared_budget: dict[str, int | float | str],
    prompt_sha256: str,
    tool_schema_sha256: str,
    request_contract_sha256: str,
    request_bytes: int,
    elapsed_ms: int,
    error_class: str,
    http_status: int | None,
) -> LiveCapabilityResult:
    return LiveCapabilityResult(
        profile_id=P3_LIVE_PROFILE_ID,
        status="blocked",
        outcome="transport_or_provider_error_no_retry",
        related_public_case=P3_RELATED_PUBLIC_CASE,
        model=profile.model,
        returned_model=None,
        endpoint_id="deepseek.chat.completions.v1",
        configured_base_url_sha256=profile.base_url_sha256,
        p1_receipt_sha256=profile.p1_receipt_sha256,
        p1_observed_at=profile.p1_observed_at,
        p1_verified_allowance_usd=str(profile.p1_verified_allowance_usd),
        credential_resolution=credential_resolution,
        request_count=1,
        retry_count=0,
        http_status=http_status,
        elapsed_ms=elapsed_ms,
        declared_budget=declared_budget,
        prompt_sha256=prompt_sha256,
        tool_schema_sha256=tool_schema_sha256,
        request_contract_sha256=request_contract_sha256,
        request_bytes=request_bytes,
        response_id_sha256=None,
        finish_reason=None,
        tool_call_count=None,
        tool_name_matches=None,
        arguments_schema_valid=None,
        reasoning_content_present=None,
        reasoning_tokens=None,
        usage=None,
        observed_cost_upper_bound_usd=None,
        tool_execution_count=0,
        engine_invocations=0,
        scheduler_invocations=0,
        raw_prompt_retained=False,
        raw_response_retained=False,
        validation_issues=("live.provider_request_failed",),
        error_class=error_class,
    )


def _preflight_result(
    *,
    profile: DeepSeekProfile,
    declared_budget: dict[str, int | float | str],
    prompt_sha256: str,
    tool_schema_sha256: str,
    request_contract_sha256: str,
    request_bytes: int,
    error_class: str,
) -> LiveCapabilityResult:
    return LiveCapabilityResult(
        profile_id=P3_LIVE_PROFILE_ID,
        status="blocked",
        outcome="preflight_blocked_no_request",
        related_public_case=P3_RELATED_PUBLIC_CASE,
        model=profile.model,
        returned_model=None,
        endpoint_id="deepseek.chat.completions.v1",
        configured_base_url_sha256=profile.base_url_sha256,
        p1_receipt_sha256=profile.p1_receipt_sha256,
        p1_observed_at=profile.p1_observed_at,
        p1_verified_allowance_usd=str(profile.p1_verified_allowance_usd),
        credential_resolution=CredentialResolution(
            canonical_alias=CANONICAL_DEEPSEEK_ALIAS,
            source_class="unresolved",
            source_alias="",
            bound_in_process=False,
        ),
        request_count=0,
        retry_count=0,
        http_status=None,
        elapsed_ms=None,
        declared_budget=declared_budget,
        prompt_sha256=prompt_sha256,
        tool_schema_sha256=tool_schema_sha256,
        request_contract_sha256=request_contract_sha256,
        request_bytes=request_bytes,
        response_id_sha256=None,
        finish_reason=None,
        tool_call_count=None,
        tool_name_matches=None,
        arguments_schema_valid=None,
        reasoning_content_present=None,
        reasoning_tokens=None,
        usage=None,
        observed_cost_upper_bound_usd=None,
        tool_execution_count=0,
        engine_invocations=0,
        scheduler_invocations=0,
        raw_prompt_retained=False,
        raw_response_retained=False,
        validation_issues=("live.canonical_alias_unresolved",),
        error_class=error_class,
    )


def _response_mapping(response: Any) -> Mapping[str, Any]:
    dump = getattr(response, "model_dump", None)
    payload = dump() if callable(dump) else response
    if not isinstance(payload, Mapping):
        return {}
    return payload


def _arguments_valid(raw: Any) -> bool:
    if not isinstance(raw, str):
        return False
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return False
    return parsed == {
        "case_id": P3_RELATED_PUBLIC_CASE,
        "terminal_status": "blocked",
        "rule_id": "p3.provider.capability_or_tool_drift",
    }


def _usage(raw: Any) -> tuple[dict[str, int] | None, int | None]:
    if not isinstance(raw, Mapping):
        return None, None
    values: dict[str, int] = {}
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = raw.get(field)
        if not isinstance(value, int) or value < 0:
            return None, None
        values[field] = value
    if values["total_tokens"] < values["prompt_tokens"] + values["completion_tokens"]:
        return None, None
    details = raw.get("completion_tokens_details")
    reasoning_tokens: int | None = None
    if isinstance(details, Mapping) and isinstance(details.get("reasoning_tokens"), int):
        reasoning_tokens = int(details["reasoning_tokens"])
        if reasoning_tokens < 0:
            return None, None
    return values, reasoning_tokens


def _observed_cost_upper_bound(usage: Mapping[str, int] | None) -> Decimal | None:
    if usage is None:
        return None
    return (
        Decimal(usage["prompt_tokens"]) * PEAK_INPUT_PRICE_USD_PER_MILLION
        + Decimal(usage["completion_tokens"]) * PEAK_OUTPUT_PRICE_USD_PER_MILLION
    ) / Decimal("1000000")


def _p1_deepseek_allowance(p1: Mapping[str, Any]) -> Decimal:
    probes = p1.get("probes")
    if not isinstance(probes, list):
        raise FrontierLiveCapabilityError("P1 receipt lacks DeepSeek probe")
    for probe in probes:
        if not isinstance(probe, Mapping) or probe.get("service") != "deepseek":
            continue
        if probe.get("http_status") != 200 or probe.get("outcome") != "ok":
            raise FrontierLiveCapabilityError("P1 DeepSeek probe is not a positive allowance")
        usage = _mapping(probe.get("usage"), "P1 DeepSeek usage")
        if usage.get("is_available") is not True:
            raise FrontierLiveCapabilityError("P1 DeepSeek balance is not available")
        balances = usage.get("balances")
        if not isinstance(balances, list):
            continue
        for balance in balances:
            if isinstance(balance, Mapping) and balance.get("currency") == "USD":
                try:
                    amount = Decimal(str(balance.get("total_balance")))
                except Exception as exc:
                    raise FrontierLiveCapabilityError("P1 balance is malformed") from exc
                if amount >= 0:
                    return amount
    raise FrontierLiveCapabilityError("P1 DeepSeek USD allowance is unavailable")


def _load_yaml_mapping(path: Path) -> Mapping[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise FrontierLiveCapabilityError("DeepSeek provider configuration is unreadable") from exc
    return _mapping(raw, "agent provider configuration")


def _load_json_object(path: Path, label: str) -> Mapping[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FrontierLiveCapabilityError(f"{label} is unreadable") from exc
    return _mapping(raw, label)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FrontierLiveCapabilityError(f"{label} must be a mapping")
    return value


def _required_text(value: Mapping[str, Any], field: str, label: str) -> str:
    text = value.get(field)
    if not isinstance(text, str) or not text.strip():
        raise FrontierLiveCapabilityError(f"{label} lacks {field}")
    return text.strip()


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _is_official_deepseek_base_url(value: str) -> bool:
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "api.deepseek.com"
        and parsed.path.rstrip("/") == ""
        and not parsed.query
        and not parsed.fragment
    )


def _redacted_provider_surface(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    provider_type = _required_text(entry, "type", "DeepSeek provider entry").lower()
    configured_alias = _required_text(
        entry, "api_key_env", "DeepSeek provider entry"
    )
    base_url = _required_text(entry, "base_url", "DeepSeek provider entry")
    if not _is_official_deepseek_base_url(base_url):
        raise FrontierLiveCapabilityError("DeepSeek specimen requires official root URL")
    return provider_type, configured_alias, _sha256_text(base_url)


def _legacy_env_paths(environment: Mapping[str, str]) -> tuple[Path, ...]:
    explicit = environment.get("CHEMSMART_API_ENV", "").strip()
    candidates = (
        Path(explicit) if explicit else None,
        Path.home() / ".chemsmart" / "api.env",
        Path.cwd() / "api.env",
    )
    return tuple(path for path in candidates if path is not None and path.is_file())


def _read_legacy_aliases(
    paths: tuple[Path, ...], configured_alias: str
) -> tuple[str, str]:
    if not paths:
        return "", ""
    try:
        from dotenv import dotenv_values
    except ImportError as exc:
        raise FrontierLiveCapabilityError("legacy credential resolver is unavailable") from exc
    for path in paths:
        values = dotenv_values(path)
        canonical = str(values.get(CANONICAL_DEEPSEEK_ALIAS) or "").strip()
        configured = str(values.get(configured_alias) or "").strip()
        if canonical or configured:
            return canonical, configured
    return "", ""


def _status_code(exc: Exception) -> int | None:
    value = getattr(exc, "status_code", None)
    return value if isinstance(value, int) else None


def _elapsed_ms(started: float, ended: float) -> int:
    return max(0, round((ended - started) * 1000))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = [
    "CANONICAL_DEEPSEEK_ALIAS",
    "DECLARED_MODEL",
    "DECLARED_TOOL_NAME",
    "DeepSeekProfile",
    "FrontierLiveCapabilityError",
    "LiveCapabilityResult",
    "MAX_COST_USD",
    "MAX_REQUEST_BYTES",
    "MAX_TOKENS",
    "MAX_WALL_TIME_S",
    "estimated_max_cost_usd",
    "load_deepseek_profile",
    "preflight_credential_resolution",
    "run_live_capability_specimen",
    "validate_live_capability_receipt",
]
