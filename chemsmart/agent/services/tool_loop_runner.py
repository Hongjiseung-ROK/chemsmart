"""Bounded provider/tool state machine used by :class:`ToolLoop`."""

from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Protocol

from chemsmart.agent.provider_adapter import (
    ToolOutcome,
    ToolRequest,
    build_tool_result_messages,
    normalize_response,
    response_payload,
)
from chemsmart.agent.providers import (
    DEFAULT_TIMEOUT_S,
    extract_response_metadata,
    extract_response_usage,
)
from chemsmart.agent.public_visibility import sanitize_public_text

ASK_USER_TOOL_NAME = "ask_user"
STUDIO_RESULT_TOOL_NAME = "report_studio_result"
_STUDIO_RESULT_REMINDER = (
    "This Studio turn used tools and must now finish by calling "
    "report_studio_result. Do not answer with plain text."
)
_PRIVATE_REASONING_KEYS = frozenset(
    {"reasoning_content", "thinking", "analysis", "<think>"}
)
_THINK_BLOCK = re.compile(
    r"<think\b[^>]*>.*?</think>",
    flags=re.DOTALL | re.IGNORECASE,
)
_UNCLOSED_THINK = re.compile(r"<think\b", flags=re.IGNORECASE)


class LoopHost(Protocol):
    provider: Any
    decision_log: Any
    budgets: Any

    def _tool_defs_for_mode(self, provider_name: str, mode: Any) -> list: ...
    def _tool_defs_for_provider(self, provider_name: str) -> list: ...
    def _filter_tool_defs(
        self,
        provider_name: str,
        tool_defs: list[dict[str, Any]],
        allowed_tool_names: set[str],
    ) -> list[dict[str, Any]]: ...
    def _normalized_args(self, request: ToolRequest) -> dict[str, Any]: ...
    def _tool_description(self, tool_name: str) -> str: ...
    def _run_one_request(
        self, step: int, request: ToolRequest
    ) -> tuple[ToolOutcome, bool]: ...
    def _tool_is_terminal(self, tool_name: str) -> bool: ...
    def _skipped_outcome(
        self, step: int, request: ToolRequest, *, reason: str
    ) -> ToolOutcome: ...


@dataclass
class TurnState:
    history: list[dict[str, Any]]
    assistant_text: str = ""
    stop_reason: str | None = None
    limit_reason: str | None = None
    model_steps: int = 0
    tool_calls: int = 0
    consecutive_tool_errors: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    signature_counts: Counter[tuple[str, str]] = field(default_factory=Counter)
    tool_requests: list[ToolRequest] = field(default_factory=list)
    tool_outcomes: list[ToolOutcome] = field(default_factory=list)
    approvals_count: int = 0
    denials_count: int = 0
    ask_user_outcome: dict[str, Any] | None = None
    provider_errors: int = 0
    provider_responses: list[dict[str, Any]] = field(default_factory=list)
    studio_result_reminders: int = 0


class ToolLoopRunner:
    def __init__(self, loop: LoopHost) -> None:
        self.loop = loop

    def run(
        self,
        messages: list[dict[str, Any]],
        tool_defs: list[dict[str, Any]] | None,
        mode: Any | None,
        allowed_tool_names: set[str] | None,
    ) -> dict[str, Any]:
        protocol = self._wire_protocol()
        definitions = self._tool_defs(
            protocol, tool_defs, mode, allowed_tool_names
        )
        state = TurnState(history=[deepcopy(item) for item in messages])
        while state.model_steps < self.loop.budgets.max_model_steps_per_turn:
            response = self._provider_turn(state, definitions)
            if response is None:
                if state.limit_reason is not None:
                    break
                continue
            requests = self._record_assistant_turn(state, protocol, response)
            if not requests:
                if self._studio_result_is_required(state, definitions):
                    if state.studio_result_reminders >= 1:
                        state.limit_reason = "studio_result_required"
                        break
                    state.studio_result_reminders += 1
                    state.history.append(
                        {
                            "role": "system",
                            "content": _STUDIO_RESULT_REMINDER,
                        }
                    )
                    continue
                break
            should_stop, asked_user = self._process_requests(
                state, protocol, requests
            )
            if should_stop or asked_user:
                break
        else:
            state.limit_reason = "max_model_steps"
        self._log_limit(state)
        return _result(state)

    def _studio_result_is_required(
        self,
        state: TurnState,
        definitions: list[dict[str, Any]],
    ) -> bool:
        if not state.tool_requests:
            return False
        if any(
            outcome.name == STUDIO_RESULT_TOOL_NAME and outcome.status == "ok"
            for outcome in state.tool_outcomes
        ):
            return False
        return any(
            _tool_definition_name(definition) == STUDIO_RESULT_TOOL_NAME
            for definition in definitions
        )

    def _wire_protocol(self) -> str:
        provider = self.loop.provider
        name = getattr(provider, "name", None) or "openai"
        return getattr(provider, "wire_protocol", None) or name

    def _tool_defs(
        self,
        protocol: str,
        tool_defs: list[dict[str, Any]] | None,
        mode: Any | None,
        allowed: set[str] | None,
    ) -> list[dict[str, Any]]:
        if mode is not None:
            definitions = self.loop._tool_defs_for_mode(protocol, mode)
        elif tool_defs is None:
            definitions = self.loop._tool_defs_for_provider(protocol)
        else:
            definitions = tool_defs
        if allowed is None:
            return definitions
        return self.loop._filter_tool_defs(protocol, definitions, allowed)

    def _provider_turn(
        self, state: TurnState, tool_defs: list[dict[str, Any]]
    ) -> Any | None:
        state.model_steps += 1
        try:
            response = self.loop.provider.chat(
                state.history,
                tools=tool_defs,
                timeout_s=DEFAULT_TIMEOUT_S,
            )
        except Exception as exc:
            state.provider_errors += 1
            self.loop.decision_log.write(
                "provider_turn_error",
                {
                    "step": state.model_steps,
                    "error_type": exc.__class__.__name__,
                    "message": str(exc)[:500],
                    "attempt": state.provider_errors,
                },
            )
            if state.provider_errors >= (
                self.loop.budgets.max_provider_errors_per_turn
            ):
                state.limit_reason = "provider_errors"
            return None
        payload = response_payload(response)
        if self.loop.budgets.log_provider_turn_raw:
            self.loop.decision_log.write(
                "provider_turn_raw",
                {
                    "step": state.model_steps,
                    "response_dict": public_provider_response(payload),
                },
            )
        return payload

    def _record_assistant_turn(
        self,
        state: TurnState,
        protocol: str,
        response: dict[str, Any],
    ) -> list[ToolRequest]:
        message = assistant_message(protocol, response)
        text, requests, stop_reason = normalize_response(protocol, response)
        text = public_assistant_text(text)
        usage = extract_response_usage(response)
        provider_response = {
            "provider": _provider_name(self.loop.provider, protocol),
            "wire_protocol": protocol,
            **extract_response_metadata(response),
        }
        state.provider_responses.append(provider_response)
        state.assistant_text = text
        state.stop_reason = stop_reason
        state.total_input_tokens += int(usage["input_tokens"] or 0)
        state.total_output_tokens += int(usage["output_tokens"] or 0)
        self.loop.decision_log.write(
            "assistant_turn",
            {
                "step": state.model_steps,
                "assistant_text": text,
                "stop_reason": stop_reason,
                "usage": usage,
                "provider_response": provider_response,
            },
        )
        state.history.append(message)
        return requests

    def _process_requests(
        self,
        state: TurnState,
        protocol: str,
        requests: list[ToolRequest],
    ) -> tuple[bool, bool]:
        outcomes: list[ToolOutcome] = []
        stop_index: int | None = None
        asked_user = False
        for index, request in enumerate(requests):
            self._log_request(state, request, index, len(requests))
            if request.name == ASK_USER_TOOL_NAME:
                outcome = self._ask_user(state, request)
                outcomes.append(outcome)
                asked_user = True
                break
            outcome, should_stop = self._process_one(state, request)
            outcomes.append(outcome)
            if should_stop:
                stop_index = index
                break
        if stop_index is not None:
            outcomes.extend(self._skip_queued(state, requests, stop_index))
        state.tool_outcomes.extend(outcomes)
        if outcomes:
            state.history.extend(
                build_tool_result_messages(protocol, outcomes)
            )
        return stop_index is not None, asked_user

    def _process_one(
        self, state: TurnState, request: ToolRequest
    ) -> tuple[ToolOutcome, bool]:
        signature = (request.name, canonical_args_json(request))
        state.signature_counts[signature] += 1
        if state.signature_counts[signature] > (
            self.loop.budgets.max_same_signature_retries
        ):
            state.limit_reason = "repeat_signature"
            return self._skip(state, request, "repeat_signature"), True
        if state.tool_calls >= self.loop.budgets.max_total_tool_calls_per_turn:
            state.limit_reason = "max_tool_calls"
            return self._skip(state, request, "max_tool_calls"), True
        outcome, approved = self.loop._run_one_request(
            state.model_steps, request
        )
        if approved:
            state.approvals_count += 1
            state.tool_calls += 1
        elif outcome.status == "denied":
            state.denials_count += 1
            state.stop_reason = "denied"
            return outcome, True
        if outcome.status == "error":
            state.consecutive_tool_errors += 1
        else:
            state.consecutive_tool_errors = 0
        should_stop = state.consecutive_tool_errors >= (
            self.loop.budgets.max_consecutive_tool_errors
        )
        if should_stop:
            state.limit_reason = "max_consecutive_errors"
        elif outcome.status == "ok" and self.loop._tool_is_terminal(
            request.name
        ):
            state.stop_reason = "terminal_tool"
            should_stop = True
        return outcome, should_stop

    def _log_request(
        self,
        state: TurnState,
        request: ToolRequest,
        index: int,
        total: int,
    ) -> None:
        state.tool_requests.append(request)
        self.loop.decision_log.write(
            "tool_use_request",
            {
                "step": state.model_steps,
                "provider_call_id": request.provider_call_id,
                "tool": request.name,
                "args": request.arguments,
                "normalized_args": self.loop._normalized_args(request),
                "description": self.loop._tool_description(request.name),
                "queue_index": index + 1,
                "queue_total": total,
                "raw": request.raw,
            },
        )

    def _ask_user(self, state: TurnState, request: ToolRequest) -> ToolOutcome:
        question = request.arguments.get("question")
        question = question.strip() if isinstance(question, str) else ""
        raw_options = request.arguments.get("options")
        options = (
            [
                item.strip()
                for item in raw_options
                if isinstance(item, str) and item.strip()
            ]
            if isinstance(raw_options, list)
            else []
        )
        payload = {"question": question, "options": options}
        self.loop.decision_log.write(
            "ask_user",
            {
                **payload,
                "step": state.model_steps,
                "provider_call_id": request.provider_call_id,
            },
        )
        outcome = ToolOutcome(
            request_id=request.request_id,
            provider_call_id=request.provider_call_id,
            name=request.name,
            status="ask_user",
            result=payload,
            display_result=payload,
            raw_result=payload,
        )
        self._log_virtual_result(state, request, outcome)
        state.ask_user_outcome = payload
        return outcome

    def _log_virtual_result(
        self, state: TurnState, request: ToolRequest, outcome: ToolOutcome
    ) -> None:
        self.loop.decision_log.write(
            "tool_use_result",
            {
                "step": state.model_steps,
                "provider_call_id": request.provider_call_id,
                "tool": request.name,
                "status": outcome.status,
                "description": self.loop._tool_description(request.name),
                "payload": outcome.display_result,
                "handle_id": None,
            },
        )

    def _skip(
        self, state: TurnState, request: ToolRequest, reason: str
    ) -> ToolOutcome:
        return self.loop._skipped_outcome(
            state.model_steps, request, reason=reason
        )

    def _skip_queued(
        self,
        state: TurnState,
        requests: list[ToolRequest],
        stop_index: int,
    ) -> list[ToolOutcome]:
        outcomes = []
        for index, request in enumerate(
            requests[stop_index + 1 :], start=stop_index + 1
        ):
            self._log_request(state, request, index, len(requests))
            outcomes.append(
                self._skip(
                    state,
                    request,
                    state.limit_reason
                    or (
                        "permission_denied"
                        if state.stop_reason == "denied"
                        else (
                            "terminal_tool_completed"
                            if state.stop_reason == "terminal_tool"
                            else "loop_stopped"
                        )
                    ),
                )
            )
        return outcomes

    def _log_limit(self, state: TurnState) -> None:
        if state.limit_reason is None:
            return
        self.loop.decision_log.write(
            "loop_limit_exceeded",
            {
                "limit_reason": state.limit_reason,
                "model_steps": state.model_steps,
                "tool_calls": state.tool_calls,
            },
        )


def assistant_message(
    provider_name: str, response: dict[str, Any]
) -> dict[str, Any]:
    if provider_name == "anthropic":
        return {
            "role": "assistant",
            "content": deepcopy(response.get("content") or []),
        }
    choice = (response.get("choices") or [{}])[0] or {}
    message = deepcopy(choice.get("message") or {})
    message.setdefault("role", "assistant")
    return message


def canonical_args_json(request: ToolRequest) -> str:
    import json

    return json.dumps(request.arguments, sort_keys=True)


def _tool_definition_name(definition: dict[str, Any]) -> str | None:
    direct = definition.get("name")
    if isinstance(direct, str):
        return direct
    function = definition.get("function")
    if isinstance(function, dict):
        name = function.get("name")
        if isinstance(name, str):
            return name
    return None


def public_assistant_text(text: str) -> str:
    """Remove provider-private reasoning and absolute paths from public text."""

    public = _THINK_BLOCK.sub("", text)
    unclosed = _UNCLOSED_THINK.search(public)
    if unclosed is not None:
        public = public[: unclosed.start()]
    return sanitize_public_text(public).strip()


def public_message_history(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return persistable history without provider-private reasoning."""

    public: list[dict[str, Any]] = []
    for message in messages:
        copied = deepcopy(message)
        if copied.get("role") == "assistant":
            copied = _strip_private_reasoning(copied)
        public.append(copied)
    return public


def public_provider_response(response: dict[str, Any]) -> dict[str, Any]:
    """Return debug evidence with provider-private reasoning removed."""

    public = _strip_private_reasoning(deepcopy(response))
    return public if isinstance(public, dict) else {}


def _strip_private_reasoning(value: Any) -> Any:
    if isinstance(value, dict):
        block_type = value.get("type")
        if (
            isinstance(block_type, str)
            and block_type.lower() in _PRIVATE_REASONING_KEYS
        ):
            return None
        return {
            key: _strip_private_reasoning(item)
            for key, item in value.items()
            if key not in _PRIVATE_REASONING_KEYS
        }
    if isinstance(value, list):
        public_items = []
        for item in value:
            public_item = _strip_private_reasoning(item)
            if public_item is not None:
                public_items.append(public_item)
        return public_items
    if isinstance(value, str):
        return public_assistant_text(value)
    return value


def _provider_name(provider: Any, fallback: str) -> str:
    name = getattr(provider, "name", None)
    return name.strip() if isinstance(name, str) and name.strip() else fallback


def _result(state: TurnState) -> dict[str, Any]:
    terminal_outcome = (
        "needs_user"
        if state.ask_user_outcome
        else (
            "denied"
            if state.denials_count
            else ("failed" if state.limit_reason else "completed")
        )
    )
    return {
        "assistant_text": state.assistant_text,
        "tool_requests": state.tool_requests,
        "tool_outcomes": state.tool_outcomes,
        "stop_reason": state.stop_reason,
        "model_steps": state.model_steps,
        "limit_reason": state.limit_reason,
        "total_input_tokens": state.total_input_tokens,
        "total_output_tokens": state.total_output_tokens,
        "messages": public_message_history(state.history),
        "provider_responses": deepcopy(state.provider_responses),
        "approvals_count": state.approvals_count,
        "denials_count": state.denials_count,
        "ask_user": state.ask_user_outcome,
        "provider_errors": state.provider_errors,
        "terminal_outcome": terminal_outcome,
    }


__all__ = [
    "ToolLoopRunner",
    "assistant_message",
    "canonical_args_json",
    "public_assistant_text",
    "public_message_history",
    "public_provider_response",
]
