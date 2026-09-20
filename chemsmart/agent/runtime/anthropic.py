"""The Anthropic Messages adapter, and the reference tool-search backend.

One consumer of the catalogue, not an authority over it.  Everything
CHEMSMART means by a capability -- what exists, which family it belongs
to, whether it is an act or reference, what may be called -- is decided
in ``catalogue.py`` and ``exposure.py``, which know no wire format.  This
module knows one wire format and nothing else, and it translates in both
directions at its own boundary so the tool loop never learns it:

* out: the host's OpenAI-shaped definitions become Anthropic tool
  objects, the non-callable ones carrying ``defer_loading: true``, with
  the server-side BM25 search tool prepended and never deferred;
* back: the native assistant content is kept verbatim in the wire
  history -- thinking blocks, ``server_tool_use`` and
  ``tool_search_tool_result`` echoed byte-identical, as the API
  requires -- while the loop is handed the same OpenAI-shaped public
  response every other adapter returns.

Two things are deliberately *not* mirrored from the provider. The host's
own search backend and this one write the **same** discovery event, so a
recorded stream reads identically whichever searched. And a
``tool_reference`` the provider returns is checked against the catalogue
before it is adopted: a provider may not add a capability to this host.

Wire facts verified against the live documentation on 2026-09-20:
every definition rides on every request and deferred ones are excluded
from the rendered prefix, so discovery does not invalidate the prompt
cache; at least one tool must be non-deferred; a deferred tool may not
carry ``cache_control``, so the breakpoint goes on the last non-deferred
one; an ``srvtoolu_`` id must never be answered with a ``tool_result``;
a client tool's ``tool_result`` may carry ``tool_reference`` blocks and
the API expands them, provided the name is in ``tools``.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping

from chemsmart.agent._contracts import ContractError, canonical_sha256
from chemsmart.agent.runtime.deepseek import (
    DeepSeekHttpsTransport,
    DeepSeekProtocolError,
    DeepSeekTransportError,
    DeepSeekV4ToolSession,
    ProviderCapabilitiesV1,
    ProviderTurnReceiptV1,
    _require_explicit_model_id,
    _validate_token_limits,
)
from chemsmart.agent.runtime.transport import ProviderTurnDeadlinesV1

ANTHROPIC_OFFICIAL_ENDPOINT = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_WIRE_PROTOCOL = "anthropic-messages"

#: The server-side BM25 search tool. Never deferred -- a request with
#: every tool deferred is a 400, and this is the one that finds the rest.
TOOL_SEARCH_TOOL = {
    "type": "tool_search_tool_bm25_20251119",
    "name": "tool_search_tool_bm25",
}

#: Effort vocabulary this adapter admits. Current models take
#: ``output_config.effort``; ``budget_tokens`` is rejected on them, so the
#: profile never states one.
_EFFORT_VOCABULARY = {"", "low", "medium", "high"}

#: Blocks whose content is provider-private reasoning. ``redacted_thinking``
#: joins ``thinking`` here: it is encrypted reasoning, and the rule the
#: repository enforces is about the channel, not the readability.
PRIVATE_BLOCK_TYPES = frozenset({"thinking", "redacted_thinking"})

#: How many times one turn may be resumed after ``pause_turn``. Bounded,
#: because an unbounded resume is an unbilled loop nobody decided on.
_PAUSE_RESUMES = 3


@dataclass(frozen=True)
class AnthropicMessagesConfigV1:
    """Anthropic adapter configuration bound to an explicit model."""

    model: str
    context_tokens: int
    max_output_tokens: int
    provider: str = "anthropic"
    endpoint: str = ANTHROPIC_OFFICIAL_ENDPOINT
    reasoning_effort: str = ""
    #: Adaptive thinking is the current models' mode; the profile turns
    #: it off explicitly rather than the source assuming either way.
    adaptive_thinking: bool = True
    sdk_max_retries: int = 0
    turn_deadlines: ProviderTurnDeadlinesV1 = field(
        default_factory=ProviderTurnDeadlinesV1
    )
    record_reasoning: bool = False

    def __post_init__(self) -> None:
        if self.provider != "anthropic":
            raise ContractError("Anthropic provider identity is immutable")
        _require_explicit_model_id(self.model, provider="Anthropic")
        _validate_token_limits(
            context_tokens=self.context_tokens,
            max_output_tokens=self.max_output_tokens,
        )
        if self.endpoint.rstrip("/") != ANTHROPIC_OFFICIAL_ENDPOINT:
            raise ContractError(
                "the Anthropic adapter requires the official endpoint"
            )
        if self.reasoning_effort not in _EFFORT_VOCABULARY:
            raise ContractError(
                "Anthropic reasoning effort must be low, medium, high, or "
                "omitted"
            )
        if self.sdk_max_retries != 0:
            raise ContractError(
                "provider retries require a separately authorized attempt"
            )


class AnthropicHttpsTransport(DeepSeekHttpsTransport):
    """The shared bounded HTTPS transport, on the Messages endpoint.

    Only the path and the headers differ, and both are class-level hooks
    on the base transport, so the deadline discipline and the sanitized
    failure ladder stay in the one place that owns them.
    """

    _ENDPOINT_ERROR = "the Anthropic transport requires the official endpoint"

    @staticmethod
    def _endpoint_is_registered(endpoint: str) -> bool:
        return endpoint.rstrip("/") == ANTHROPIC_OFFICIAL_ENDPOINT

    def _request_path(self) -> str:
        return "/v1/messages"

    def _request_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
            "Accept": self._ACCEPT,
            "User-Agent": "chemsmart-agent/1",
        }


def _anthropic_tool(definition: Mapping[str, Any]) -> dict[str, Any]:
    """One OpenAI-shaped definition as an Anthropic tool object."""

    function = definition["function"]
    tool: dict[str, Any] = {
        "name": function["name"],
        "description": str(function.get("description") or ""),
        "input_schema": deepcopy(function.get("parameters") or {}),
    }
    return tool


class AnthropicMessagesToolSession(DeepSeekV4ToolSession):
    """One Anthropic Messages conversation with native continuation.

    The wire history holds native content blocks verbatim -- that is what
    the API requires and what keeps thinking and search blocks valid on
    the next request -- while ``public_history`` and the response handed
    to the loop carry no reasoning text at all.
    """

    def __init__(
        self,
        *,
        transport: Any,
        messages: list[dict[str, Any]],
        config: AnthropicMessagesConfigV1,
        reasoning_sink: Any = None,
        exposure: Any = None,
    ) -> None:
        # The Messages API takes the system prompt as a top-level block,
        # not as a message, so it is lifted here and nowhere else: every
        # caller still builds the one message list every adapter takes.
        system = [
            str(item.get("content") or "")
            for item in messages
            if str(item.get("role") or "") == "system"
        ]
        rest = [
            dict(item)
            for item in messages
            if str(item.get("role") or "") != "system"
        ]
        super().__init__(
            transport=transport,
            messages=rest,
            config=config,
            reasoning_sink=reasoning_sink,
        )
        self._system = "\n\n".join(part for part in system if part)
        self._exposure = exposure
        self._discovered: tuple[str, ...] = ()
        self._last_cache: dict[str, int] = {}

    # -- capabilities --------------------------------------------------

    @property
    def capabilities(self) -> ProviderCapabilitiesV1:
        return ProviderCapabilitiesV1(
            provider=self.config.provider,
            model=self.config.model,
            context_tokens=self.config.context_tokens,
            max_output_tokens=self.config.max_output_tokens,
            wire_protocol=ANTHROPIC_WIRE_PROTOCOL,
            continuation_mode="native_content_blocks",
            exposure_mode="native_tool_search",
            private_reasoning_persisted=self._reasoning_sink is not None,
        )

    def discovered_capabilities(self) -> tuple[str, ...]:
        """Names the provider's own search returned on the last turn."""

        return self._discovered

    # -- the request ---------------------------------------------------

    def _wire_tools(
        self, tools: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]]:
        """The search tool, the callable definitions, then the deferred.

        The order matters twice: the cache breakpoint goes on the last
        non-deferred tool, because a deferred tool may not carry one; and
        the non-deferred prefix must be stable for the session, which is
        why typed promotion happens before the first request and never
        after.
        """

        if not tools:
            return [dict(TOOL_SEARCH_TOOL)]
        withheld = set(
            self._exposure.withheld_names() if self._exposure else ()
        )
        callable_tools = [
            _anthropic_tool(item)
            for item in tools
            if item["function"]["name"] not in withheld
        ]
        deferred = [
            {**_anthropic_tool(item), "defer_loading": True}
            for item in tools
            if item["function"]["name"] in withheld
        ]
        wire = [dict(TOOL_SEARCH_TOOL), *callable_tools]
        if wire:
            wire[-1] = {
                **wire[-1],
                "cache_control": {"type": "ephemeral"},
            }
        return [*wire, *deferred]

    def request_payload(
        self, *, tools: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_output_tokens,
            "messages": deepcopy(self._history),
        }
        if self._system:
            payload["system"] = [
                {
                    "type": "text",
                    "text": self._system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        if self.config.adaptive_thinking:
            payload["thinking"] = {"type": "adaptive"}
        if self.config.reasoning_effort:
            payload["output_config"] = {"effort": self.config.reasoning_effort}
        payload["tools"] = self._wire_tools(tools)
        return payload

    # -- the turn ------------------------------------------------------

    def turn(
        self, *, tools: list[dict[str, Any]] | None = None
    ) -> tuple[dict[str, Any], ProviderTurnReceiptV1]:
        if self._outstanding_tool_call_ids:
            raise DeepSeekProtocolError(
                "all tool results must be appended before the next "
                "provider turn"
            )
        payload = self._exchange(tools)
        request = self.request_payload(tools=tools)
        content = payload.get("content")
        if not isinstance(content, list):
            raise DeepSeekProtocolError(
                "provider response has no content blocks",
                failing_field="content",
            ).with_public_response(_public_payload(payload))
        tool_call_ids = tuple(
            str(block.get("id") or "")
            for block in content
            if isinstance(block, Mapping) and block.get("type") == "tool_use"
        )
        if "" in tool_call_ids:
            raise DeepSeekProtocolError(
                "a tool_use block has no id", failing_field="content"
            ).with_public_response(_public_payload(payload))
        if self._seen_tool_call_ids.intersection(tool_call_ids):
            raise DeepSeekProtocolError(
                "provider reused a tool-call ID within one session",
                failing_field="content",
            ).with_public_response(_public_payload(payload))
        # The assistant turn is replayed byte-identical. Thinking blocks
        # and the server's own search blocks are echoed back exactly as
        # they arrived, which is what the API requires; trimming either
        # invalidates the turn.
        self._history.append(
            {"role": "assistant", "content": deepcopy(content)}
        )
        self._discovered = _discovered_names(content)
        persisted = self._persist_thinking(request=request, content=content)
        receipt = self._receipt(
            request=request,
            payload=payload,
            tools=tools or [],
            tool_calls_present=bool(tool_call_ids),
            private_reasoning_persisted=persisted,
        )
        self._receipts.append(receipt)
        self._outstanding_tool_call_ids = tool_call_ids
        self._seen_tool_call_ids.update(tool_call_ids)
        return _as_openai_response(payload, model=self.config.model), receipt

    def _exchange(self, tools: list[dict[str, Any]] | None) -> dict[str, Any]:
        """One call, resuming a paused turn without a new decision.

        ``pause_turn`` means the model stopped mid-turn and the same
        conversation should be re-sent; it is not an outcome, so it never
        reaches the loop as one. The resume is bounded, because an
        unbounded one is an unbilled loop.
        """

        for _ in range(_PAUSE_RESUMES + 1):
            response = self._transport(
                deepcopy(self.request_payload(tools=tools))
            )
            if not isinstance(response, Mapping):
                raise DeepSeekProtocolError(
                    "provider response must be a mapping"
                )
            payload = deepcopy(dict(response))
            self._validate_model(payload)
            if payload.get("type") == "error":
                raise DeepSeekTransportError("provider_error")
            usage = payload.get("usage")
            self._last_cache = (
                {
                    "cache_read_input_tokens": int(
                        usage.get("cache_read_input_tokens") or 0
                    ),
                    "cache_creation_input_tokens": int(
                        usage.get("cache_creation_input_tokens") or 0
                    ),
                }
                if isinstance(usage, Mapping)
                else {}
            )
            if payload.get("stop_reason") != "pause_turn":
                return payload
            content = payload.get("content")
            if not isinstance(content, list):
                return payload
            self._history.append(
                {"role": "assistant", "content": deepcopy(content)}
            )
        raise DeepSeekProtocolError(
            "provider paused the turn more times than the adapter resumes",
            failing_field="stop_reason",
        )

    def _validate_model(self, payload: Mapping[str, Any]) -> None:
        """Refuse an unbound response, tolerating an alias resolution.

        A requested alias may be echoed as the dated id it resolved to,
        which the base check -- exact equality -- would read as another
        model answering. The tolerance is an override used by this
        session alone: the base check is never relaxed, because on a wire
        that does not resolve aliases an inexact echo means exactly what
        the base check says it means.
        """

        observed = payload.get("model")
        if not isinstance(observed, str) or not observed:
            raise DeepSeekProtocolError(
                "provider response does not identify its model",
                failing_field="model",
            )
        requested = self.config.model
        if observed == requested:
            return
        if observed.startswith(requested) or requested.startswith(observed):
            return
        raise DeepSeekProtocolError(
            "provider response model differs from the requested model",
            failing_field="model",
        )

    def _persist_thinking(
        self, *, request: Mapping[str, Any], content: list
    ) -> bool:
        if self._reasoning_sink is None:
            return False
        text = "\n".join(
            str(block.get("thinking") or "")
            for block in content
            if isinstance(block, Mapping) and block.get("type") == "thinking"
        ).strip()
        if not text:
            return False
        self._reasoning_sink(
            ordinal=len(self._receipts) + 1,
            request_sha256=canonical_sha256(_public_payload(request)),
            reasoning_content=text,
        )
        return True

    def _receipt(
        self,
        *,
        request: Mapping[str, Any],
        payload: Mapping[str, Any],
        tools: list[dict[str, Any]],
        tool_calls_present: bool,
        private_reasoning_persisted: bool,
    ) -> ProviderTurnReceiptV1:
        usage = payload.get("usage")
        usage = usage if isinstance(usage, Mapping) else {}
        content = payload.get("content") or []
        thinking_present = any(
            isinstance(block, Mapping)
            and str(block.get("type")) in PRIVATE_BLOCK_TYPES
            for block in content
        )
        body = {
            "schema_version": "chemsmart.provider-turn-receipt.v1",
            "provider": str(self.config.provider),
            "requested_model": str(self.config.model),
            "observed_model": str(payload.get("model") or ""),
            "request_sha256": canonical_sha256(_public_payload(request)),
            "tool_schema_sha256": canonical_sha256(tools),
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
            # The wire reports no separate reasoning count; the receipt
            # says zero rather than inventing one, and
            # reasoning_continuation_present carries what is known.
            "reasoning_tokens": 0,
            "finish_reason": str(payload.get("stop_reason") or ""),
            "tool_calls_present": bool(tool_calls_present),
            "reasoning_continuation_present": bool(thinking_present),
            "private_reasoning_persisted": bool(private_reasoning_persisted),
        }
        return ProviderTurnReceiptV1(
            **body, receipt_sha256=canonical_sha256(body)
        )

    def cache_observation(self) -> dict[str, int]:
        """What the provider reported about its own prefix cache."""

        return dict(self._last_cache)

    # -- tool results --------------------------------------------------

    def append_tool_results(self, results: list[dict[str, Any]]) -> None:
        """One user message of ``tool_result`` blocks, in call order.

        A host reply that says definitions should now be readable becomes
        ``tool_reference`` blocks the API expands -- which is how
        load-then-re-issue works on this wire. The names are the host's;
        this only changes their shape.
        """

        observed = tuple(
            str(item.get("tool_call_id") or "") for item in results
        )
        if tuple(sorted(observed)) != tuple(
            sorted(self._outstanding_tool_call_ids)
        ):
            raise ContractError(
                "tool results must exactly match outstanding calls"
            )
        if len(observed) != len(set(observed)):
            raise ContractError("tool results contain duplicate call IDs")
        blocks = []
        for result in results:
            if result.get("role") != "tool" or not result.get("tool_call_id"):
                raise ContractError(
                    "tool results require role and tool_call_id"
                )
            text = result.get("content")
            if not isinstance(text, str):
                raise ContractError(
                    "tool result content must be a JSON string"
                )
            content: list[dict[str, Any]] = [{"type": "text", "text": text}]
            for name in _requested_loads(text):
                content.append({"type": "tool_reference", "tool_name": name})
            blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": str(result["tool_call_id"]),
                    "content": content,
                }
            )
        self._history.append({"role": "user", "content": blocks})
        self._outstanding_tool_call_ids = ()

    def append_host_user_message(self, content: str) -> None:
        if self._outstanding_tool_call_ids:
            raise ContractError(
                "host messages may not interleave outstanding tool results"
            )
        if not isinstance(content, str) or not content.strip():
            raise ContractError("a host user message requires text content")
        self._history.append(
            {"role": "user", "content": [{"type": "text", "text": content}]}
        )

    # -- the public plane ----------------------------------------------

    def public_history(self) -> list[dict[str, Any]]:
        return [_public_payload(message) for message in self._history]


def _requested_loads(text: str) -> tuple[str, ...]:
    """The host's ``load_capabilities``, if this reply carries any."""

    try:
        decoded = json.loads(text)
    except (TypeError, ValueError):
        return ()
    if not isinstance(decoded, Mapping):
        return ()
    names = decoded.get("load_capabilities")
    if isinstance(names, Mapping):
        return ()
    if not isinstance(names, (list, tuple)):
        names = (decoded.get("result") or {}).get("load_capabilities")
    if not isinstance(names, (list, tuple)):
        return ()
    return tuple(str(name) for name in names if str(name))


def _discovered_names(content: list) -> tuple[str, ...]:
    """Names the server's search returned, in the order it returned them."""

    out: list[str] = []
    for block in content:
        if (
            not isinstance(block, Mapping)
            or block.get("type") != "tool_search_tool_result"
        ):
            continue
        inner = block.get("content")
        if not isinstance(inner, Mapping):
            continue
        for reference in inner.get("tool_references") or ():
            if (
                isinstance(reference, Mapping)
                and reference.get("type") == "tool_reference"
            ):
                name = str(reference.get("tool_name") or "")
                if name and name not in out:
                    out.append(name)
    return tuple(out)


def _public_payload(value: Any) -> Any:
    """Strip provider-private reasoning, keeping every other block.

    A ``thinking`` or ``redacted_thinking`` block is removed whole. The
    wire history keeps them -- the API requires the echo -- and this is
    the only projection any event, transcript or digest ever sees.
    """

    if isinstance(value, Mapping):
        if str(value.get("type") or "") in PRIVATE_BLOCK_TYPES:
            return None
        out = {}
        for key, item in value.items():
            if key in PRIVATE_BLOCK_TYPES:
                continue
            public = _public_payload(item)
            if public is not None:
                out[key] = public
        return out
    if isinstance(value, list):
        return [
            item
            for item in (_public_payload(entry) for entry in value)
            if item is not None
        ]
    return value


def _as_openai_response(
    payload: Mapping[str, Any], *, model: str
) -> dict[str, Any]:
    """The turn as the loop reads every provider: one chat completion.

    The translation is the whole point of the adapter boundary. The loop
    decodes one envelope shape and validates one public projection, so a
    wire format cannot leak into what the product means; the native
    blocks stay in this session's own history and nowhere else.
    """

    public = _public_payload(dict(payload))
    text_parts = []
    tool_calls = []
    for block in public.get("content") or []:
        if not isinstance(block, Mapping):
            continue
        kind = str(block.get("type") or "")
        if kind == "text":
            text_parts.append(str(block.get("text") or ""))
        elif kind == "tool_use":
            tool_calls.append(
                {
                    "id": str(block.get("id") or ""),
                    "type": "function",
                    "function": {
                        "name": str(block.get("name") or ""),
                        "arguments": json.dumps(block.get("input") or {}),
                    },
                }
            )
    message: dict[str, Any] = {
        "role": "assistant",
        "content": "\n".join(part for part in text_parts if part),
    }
    if tool_calls:
        message["tool_calls"] = tool_calls
    usage = payload.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    return {
        "id": str(payload.get("id") or ""),
        "model": model,
        "choices": [
            {
                "index": 0,
                "finish_reason": (
                    "tool_calls"
                    if tool_calls
                    else str(payload.get("stop_reason") or "stop")
                ),
                "message": message,
            }
        ],
        "usage": {
            "prompt_tokens": int(usage.get("input_tokens") or 0),
            "completion_tokens": int(usage.get("output_tokens") or 0),
            # Kept under their wire names: a cache read is the one number
            # that says whether deferral bought what it claims to buy, and
            # nothing else in this tree reports it.
            "cache_read_input_tokens": int(
                usage.get("cache_read_input_tokens") or 0
            ),
            "cache_creation_input_tokens": int(
                usage.get("cache_creation_input_tokens") or 0
            ),
        },
    }


__all__ = [
    "ANTHROPIC_OFFICIAL_ENDPOINT",
    "ANTHROPIC_VERSION",
    "ANTHROPIC_WIRE_PROTOCOL",
    "PRIVATE_BLOCK_TYPES",
    "TOOL_SEARCH_TOOL",
    "AnthropicHttpsTransport",
    "AnthropicMessagesConfigV1",
    "AnthropicMessagesToolSession",
]
