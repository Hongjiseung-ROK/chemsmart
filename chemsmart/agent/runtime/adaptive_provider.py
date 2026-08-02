"""Lease-bound DeepSeek adapter for adaptive, non-count-capped experiments."""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from chemsmart.agent.adaptive_api_campaign import (
    AdaptiveHypothesisV1,
    AdaptiveNetworkBudgetV1,
    AdaptiveProviderPurpose,
)
from chemsmart.agent.api_access import (
    ApiProvider,
    ApiUsageBudget,
    CredentialAccessController,
    CredentialProbeError,
    CredentialProbeObservation,
    CredentialStatus,
    CredentialUnavailableError,
)
from chemsmart.agent.providers import OpenAIProvider


_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
_PRIVATE_REASONING_KEYS = frozenset({"reasoning_content", "thinking"})
_SHA256 = r"^[0-9a-f]{64}$"


class AdaptiveRequestBindingV1(BaseModel):
    """Exact model-visible prompt and tool schema expected by a hypothesis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["chemsmart.adaptive-request-binding.v1"] = (
        "chemsmart.adaptive-request-binding.v1"
    )
    binding_sha256: str = Field(pattern=_SHA256)
    initial_user_prompt_sha256: str = Field(pattern=_SHA256)
    tool_schema_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _binding_is_content_addressed(self) -> "AdaptiveRequestBindingV1":
        body = self.model_dump(mode="json", exclude={"binding_sha256"})
        if self.binding_sha256 != _sha256_json(body):
            raise ValueError("adaptive request binding digest mismatch")
        return self


def build_adaptive_request_binding_v1(
    *,
    initial_user_prompt_sha256: str,
    tool_schema_sha256: str,
) -> AdaptiveRequestBindingV1:
    body = {
        "schema_version": "chemsmart.adaptive-request-binding.v1",
        "initial_user_prompt_sha256": initial_user_prompt_sha256,
        "tool_schema_sha256": tool_schema_sha256,
    }
    return AdaptiveRequestBindingV1.model_validate(
        {**body, "binding_sha256": _sha256_json(body)}
    )


class AdaptiveDeepSeekProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    endpoint: Literal["https://api.deepseek.com"] = "https://api.deepseek.com"
    thinking_mode: Literal["enabled"] = "enabled"
    reasoning_effort: Literal["high", "max"] = "high"
    max_output_tokens: int = Field(default=8_192, ge=1, le=65_536)
    sdk_max_retries: Literal[0] = 0
    raw_provider_turn_logging: Literal[False] = False
    training_capture: Literal[False] = False
    engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0


class AdaptiveProviderTurnError(RuntimeError):
    """Provider failure carrying only a stable public error class."""

    def __init__(self, error_class: str) -> None:
        self.error_class = error_class
        super().__init__(error_class)


class _LeaseFailure(RuntimeError):
    pass


class AdaptiveLeaseBoundDeepSeekProvider:
    """Official DeepSeek provider bounded by time/tokens, never call count.

    Every transport call gets a new one-request credential lease.  The
    aggregate request count is observable but is not consulted to authorize or
    terminate the turn.  The surrounding ToolLoop must use adaptive mode with
    a wall-time bound and per-request input/output token guards.
    """

    name = "deepseek"
    wire_protocol = "openai"

    def __init__(
        self,
        *,
        controller: CredentialAccessController,
        network_budget: AdaptiveNetworkBudgetV1,
        hypothesis: AdaptiveHypothesisV1,
        config: AdaptiveDeepSeekProviderConfig | None = None,
        request_binding: AdaptiveRequestBindingV1 | None = None,
        provider_factory: Callable[..., Any] | None = None,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or AdaptiveDeepSeekProviderConfig()
        if self.config.max_output_tokens > (
            network_budget.max_output_tokens_per_request
        ):
            raise ValueError("provider output bound exceeds adaptive network budget")
        if hypothesis.provider is not ApiProvider.DEEPSEEK:
            raise ValueError("adaptive DeepSeek provider requires a DeepSeek hypothesis")
        if hypothesis.purpose not in {
            AdaptiveProviderPurpose.HARNESS_VALIDATION,
            AdaptiveProviderPurpose.PAPER_PLAN_VALIDATION,
            AdaptiveProviderPurpose.ADVERSARIAL_REVIEW,
        }:
            raise ValueError("hypothesis purpose is not valid for DeepSeek")
        self.default_model = self.config.model
        self._controller = controller
        self._network_budget = network_budget
        self._hypothesis = hypothesis
        if request_binding is not None:
            if (
                request_binding.initial_user_prompt_sha256
                != hypothesis.prompt_sha256
            ):
                raise ValueError("request binding differs from hypothesis prompt")
            if (
                request_binding.tool_schema_sha256
                not in hypothesis.precondition_sha256s
            ):
                raise ValueError(
                    "request binding tool schema is not a hypothesis precondition"
                )
        self._request_binding = request_binding
        self._provider_factory = provider_factory or OpenAIProvider
        self._clock = monotonic_clock
        self._started = self._clock()
        self._requests_used = 0
        self._transport_attempts = 0
        self._observed_model_id = ""
        self._reasoning_continuation_observed = False
        self._request_observations: list[dict[str, Any]] = []

    @property
    def requests_used(self) -> int:
        return self._requests_used

    @property
    def transport_attempts(self) -> int:
        return self._transport_attempts

    @property
    def observed_model_id(self) -> str:
        return self._observed_model_id

    @property
    def reasoning_continuation_observed(self) -> bool:
        return self._reasoning_continuation_observed

    @property
    def request_observations(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(item) for item in self._request_observations)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        timeout_s: float = 30,
    ) -> dict[str, Any]:
        elapsed = self._clock() - self._started
        self._observe_reasoning_continuation(messages)
        request_sha256 = _sha256_json(
            {"messages": messages, "tools": tools or []}
        )
        attempt_ordinal = len(self._request_observations) + 1
        if elapsed >= self._network_budget.task_wall_time_seconds:
            self._request_observations.append(
                {
                    "hypothesis_id": self._hypothesis.hypothesis_id,
                    "hypothesis_sha256": self._hypothesis.hypothesis_sha256,
                    "attempt_ordinal": attempt_ordinal,
                    "request_sha256": request_sha256,
                    "status": "rejected_before_transport",
                    "error_class": "provider.stop.task_wall_time",
                    "latency_ms": 0,
                }
            )
            raise AdaptiveProviderTurnError("provider.stop.task_wall_time")
        binding_error = self._request_binding_error(messages, tools or [])
        if binding_error is not None:
            observed_user_prompt_sha256s = sorted(
                hashlib.sha256(message["content"].encode("utf-8")).hexdigest()
                for message in messages
                if isinstance(message, dict)
                and message.get("role") == "user"
                and isinstance(message.get("content"), str)
            )
            observed_tool_schema_sha256 = _sha256_json(tools or [])
            self._request_observations.append(
                {
                    "hypothesis_id": self._hypothesis.hypothesis_id,
                    "hypothesis_sha256": self._hypothesis.hypothesis_sha256,
                    "attempt_ordinal": attempt_ordinal,
                    "request_sha256": request_sha256,
                    "request_binding_sha256": (
                        self._request_binding.binding_sha256
                        if self._request_binding is not None
                        else None
                    ),
                    "request_binding_verified": False,
                    "expected_initial_user_prompt_sha256": (
                        self._request_binding.initial_user_prompt_sha256
                        if self._request_binding is not None
                        else None
                    ),
                    "observed_user_prompt_sha256s": (
                        observed_user_prompt_sha256s
                    ),
                    "expected_tool_schema_sha256": (
                        self._request_binding.tool_schema_sha256
                        if self._request_binding is not None
                        else None
                    ),
                    "observed_tool_schema_sha256": (
                        observed_tool_schema_sha256
                    ),
                    "status": "rejected_before_transport",
                    "error_class": binding_error,
                    "latency_ms": 0,
                }
            )
            raise AdaptiveProviderTurnError(binding_error)
        try:
            permit = self._controller.prepare_status_probe(
                ApiProvider.DEEPSEEK,
                caller="chemsmart-adaptive-deepseek",
                purpose=(
                    "adaptive-"
                    f"{self._hypothesis.hypothesis_sha256[:16]}-"
                    f"{attempt_ordinal}"
                ),
                budget=ApiUsageBudget(1),
                target_origin=self.config.endpoint,
            )
        except CredentialUnavailableError:
            self._request_observations.append(
                {
                    "hypothesis_id": self._hypothesis.hypothesis_id,
                    "hypothesis_sha256": self._hypothesis.hypothesis_sha256,
                    "attempt_ordinal": attempt_ordinal,
                    "request_sha256": request_sha256,
                    "status": "rejected_before_transport",
                    "error_class": "provider.stop.credential_missing",
                    "latency_ms": 0,
                }
            )
            raise AdaptiveProviderTurnError(
                "provider.stop.credential_missing"
            ) from None

        captured: dict[str, Any] = {}
        started = self._clock()

        def operation(secret: str, target_origin: str) -> CredentialProbeObservation:
            try:
                provider = self._provider_factory(
                    api_key=secret,
                    model=self.config.model,
                    base_url=target_origin,
                    provider_name="deepseek",
                    thinking_mode=self.config.thinking_mode,
                    reasoning_effort=self.config.reasoning_effort,
                    max_output_tokens=self.config.max_output_tokens,
                    max_retries=0,
                )
                self._transport_attempts += 1
                captured["response"] = provider.chat(
                    messages,
                    tools=tools,
                    timeout_s=min(
                        timeout_s,
                        self._network_budget.task_wall_time_seconds - elapsed,
                    ),
                )
            except Exception as exc:
                captured["error_class"] = _safe_error_class(exc)
                raise _LeaseFailure from None
            return CredentialProbeObservation(CredentialStatus.VALID)

        try:
            status = self._controller.invoke_authorized_probe(permit, operation)
        except CredentialProbeError:
            error_class = str(captured.get("error_class") or "provider.fail.unknown")
            self._request_observations.append(
                {
                    "hypothesis_id": self._hypothesis.hypothesis_id,
                    "hypothesis_sha256": self._hypothesis.hypothesis_sha256,
                    "attempt_ordinal": attempt_ordinal,
                    "request_sha256": request_sha256,
                    "status": "failed",
                    "error_class": error_class,
                    "latency_ms": int((self._clock() - started) * 1000),
                }
            )
            raise AdaptiveProviderTurnError(error_class) from None

        response = captured.get("response")
        if not isinstance(response, dict):
            self._record_protocol_failure(
                attempt_ordinal,
                request_sha256,
                "provider.fail.protocol",
                started,
            )
            raise AdaptiveProviderTurnError("provider.fail.protocol")
        model = response.get("model")
        if not isinstance(model, str) or _MODEL.fullmatch(model) is None:
            self._record_protocol_failure(
                attempt_ordinal,
                request_sha256,
                "provider.fail.model_identity",
                started,
            )
            raise AdaptiveProviderTurnError("provider.fail.model_identity")
        if self._observed_model_id and self._observed_model_id != model:
            self._record_protocol_failure(
                attempt_ordinal,
                request_sha256,
                "provider.fail.model_identity_changed",
                started,
            )
            raise AdaptiveProviderTurnError("provider.fail.model_identity_changed")
        self._observed_model_id = model
        self._requests_used += 1
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        finish_reason, content_present, tool_calls_present = (
            _public_completion_observation(response)
        )
        completion_details = usage.get("completion_tokens_details")
        if not isinstance(completion_details, dict):
            completion_details = {}
        reasoning_tokens = int(
            completion_details.get("reasoning_tokens", 0) or 0
        )
        completion_error = None
        if finish_reason == "length":
            completion_error = "provider.stop.output_truncated"
        elif not content_present and not tool_calls_present:
            completion_error = "provider.stop.empty_completion"
        self._request_observations.append(
            {
                "hypothesis_id": self._hypothesis.hypothesis_id,
                "hypothesis_sha256": self._hypothesis.hypothesis_sha256,
                "attempt_ordinal": attempt_ordinal,
                "request_sha256": request_sha256,
                "request_binding_sha256": (
                    self._request_binding.binding_sha256
                    if self._request_binding is not None
                    else None
                ),
                "request_binding_verified": self._request_binding is not None,
                "status": "rejected" if completion_error else "observed",
                "error_class": completion_error,
                "credential_status": status.status.value,
                "observed_model": model,
                "input_tokens": int(
                    usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
                ),
                "output_tokens": int(
                    usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
                ),
                "reasoning_tokens": reasoning_tokens,
                "finish_reason": finish_reason,
                "content_present": content_present,
                "tool_calls_present": tool_calls_present,
                "latency_ms": int((self._clock() - started) * 1000),
            }
        )
        if completion_error is not None:
            raise AdaptiveProviderTurnError(completion_error)
        return response

    def _request_binding_error(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> str | None:
        binding = self._request_binding
        if binding is None:
            return None
        user_prompt_hashes = {
            hashlib.sha256(message["content"].encode("utf-8")).hexdigest()
            for message in messages
            if isinstance(message, dict)
            and message.get("role") == "user"
            and isinstance(message.get("content"), str)
        }
        if binding.initial_user_prompt_sha256 not in user_prompt_hashes:
            return "provider.stop.prompt_binding_mismatch"
        if _sha256_json(tools) != binding.tool_schema_sha256:
            return "provider.stop.tool_schema_binding_mismatch"
        return None

    def _record_protocol_failure(
        self,
        attempt_ordinal: int,
        request_sha256: str,
        error_class: str,
        started: float,
    ) -> None:
        self._request_observations.append(
            {
                "hypothesis_id": self._hypothesis.hypothesis_id,
                "hypothesis_sha256": self._hypothesis.hypothesis_sha256,
                "attempt_ordinal": attempt_ordinal,
                "request_sha256": request_sha256,
                "status": "failed",
                "error_class": error_class,
                "latency_ms": int((self._clock() - started) * 1000),
            }
        )

    def _observe_reasoning_continuation(
        self, messages: list[dict[str, Any]]
    ) -> None:
        for message in messages:
            if not isinstance(message, dict) or message.get("role") != "assistant":
                continue
            if any(key in message for key in _PRIVATE_REASONING_KEYS):
                self._reasoning_continuation_observed = True


def _public_completion_observation(
    response: dict[str, Any],
) -> tuple[str | None, bool, bool]:
    """Expose truncation and output shape without exposing reasoning content."""

    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None, False, False
    choice = choices[0]
    if not isinstance(choice, dict):
        return None, False, False
    finish_reason = choice.get("finish_reason")
    if not isinstance(finish_reason, str):
        finish_reason = None
    message = choice.get("message")
    if not isinstance(message, dict):
        return finish_reason, False, False
    content = message.get("content")
    content_present = isinstance(content, str) and bool(content.strip())
    tool_calls = message.get("tool_calls")
    tool_calls_present = isinstance(tool_calls, list) and bool(tool_calls)
    return finish_reason, content_present, tool_calls_present


def _safe_error_class(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status is None and response is not None:
        status = getattr(response, "status_code", None)
    text = str(exc).lower()
    if "insufficient balance" in text or "quota exceeded" in text:
        return "provider.stop.explicit_quota_exhausted"
    if status == 401:
        return "provider.stop.authentication_401"
    if status == 429:
        return "provider.fail.rate_limited_429"
    if isinstance(status, int) and 500 <= status <= 599:
        return "provider.fail.server_5xx"
    name = exc.__class__.__name__.lower()
    if "timeout" in name or "timeout" in text:
        return "provider.fail.timeout"
    if "connection" in name:
        return "provider.fail.connection"
    return "provider.fail.other"


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "AdaptiveDeepSeekProviderConfig",
    "AdaptiveLeaseBoundDeepSeekProvider",
    "AdaptiveProviderTurnError",
    "AdaptiveRequestBindingV1",
    "build_adaptive_request_binding_v1",
]
