"""The Anthropic Messages wire, driven provider-free on literal envelopes.

The envelopes below are the shapes the published wire contract states,
copied rather than paraphrased.  What these witness is the boundary: the
adapter translates in both directions and nothing about what CHEMSMART
means by a capability depends on the wire.  A provider searches
server-side and its discovery is recorded with the *same* event the
host's own backend writes; a provider may not name a capability this
host does not have; a thinking block is echoed back byte-identical and
never reaches the public plane; and no ``tool_result`` is ever sent for
an ``srvtoolu_`` id.
"""

from __future__ import annotations

import json

import pytest

from chemsmart.agent._contracts import ContractError, canonical_sha256
from chemsmart.agent.exposure import build_exposure
from chemsmart.agent.runtime.anthropic import (
    ANTHROPIC_OFFICIAL_ENDPOINT,
    ANTHROPIC_WIRE_PROTOCOL,
    TOOL_SEARCH_TOOL,
    AnthropicMessagesConfigV1,
    AnthropicMessagesToolSession,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.tool_runtime import (
    CapabilityNotInCatalogueError,
    CommandCompiledToolHostV1,
)

pytestmark = pytest.mark.capability("tool:*")

_MODEL = "claude-sonnet-4-6"

#: A turn in which the server searched, found one tool, and called it.
#: Thinking, server_tool_use and tool_search_tool_result are exactly the
#: block shapes the wire contract publishes.
_SEARCHED_AND_CALLED = {
    "id": "msg_01ABC",
    "type": "message",
    "role": "assistant",
    "model": _MODEL,
    "content": [
        {
            "type": "thinking",
            "thinking": "PRIVATE REASONING THAT MUST NEVER BE PUBLISHED",
            "signature": "sig_abc",
        },
        {
            "type": "text",
            "text": "I will look for the operation that owns this.",
        },
        {
            "type": "server_tool_use",
            "id": "srvtoolu_01ABC123",
            "name": "tool_search_tool_bm25",
            "input": {"query": "centre of mass of a molecule", "limit": 5},
        },
        {
            "type": "tool_search_tool_result",
            "tool_use_id": "srvtoolu_01ABC123",
            "content": {
                "type": "tool_search_tool_search_result",
                "tool_references": [
                    {
                        "type": "tool_reference",
                        "tool_name": "about_operations_geometry",
                    }
                ],
            },
        },
        {
            "type": "tool_use",
            "id": "toolu_01XYZ789",
            "name": "about_operations_geometry",
            "input": {},
        },
    ],
    "stop_reason": "tool_use",
    "usage": {
        "input_tokens": 1200,
        "output_tokens": 80,
        "cache_read_input_tokens": 1100,
        "cache_creation_input_tokens": 0,
    },
}


def _turn(ordinal: int) -> dict:
    """The same envelope with fresh ids; a reused id is a real refusal."""

    import copy

    envelope = copy.deepcopy(_SEARCHED_AND_CALLED)
    envelope["id"] = f"msg_{ordinal:02d}"
    for block in envelope["content"]:
        if block.get("type") == "tool_use":
            block["id"] = f"toolu_{ordinal:02d}"
    return envelope


def _config() -> AnthropicMessagesConfigV1:
    return AnthropicMessagesConfigV1(
        model=_MODEL,
        context_tokens=200_000,
        max_output_tokens=4096,
        endpoint=ANTHROPIC_OFFICIAL_ENDPOINT,
    )


def _session(responses, *, exposure=None, sink=None):
    sent = []

    def transport(payload):
        sent.append(payload)
        return responses.pop(0)

    session = AnthropicMessagesToolSession(
        transport=transport,
        messages=[
            {"role": "system", "content": "THE SYSTEM PROMPT"},
            {"role": "user", "content": "Answer the question."},
        ],
        config=_config(),
        reasoning_sink=sink,
        exposure=exposure or build_exposure("native_tool_search"),
    )
    return session, sent


def _tools(exposure):
    return list(exposure.tool_definitions())


def test_the_request_defers_everything_the_host_withholds(tmp_path):
    """One breakpoint, on the last non-deferred tool, and never on a
    deferred one -- the API rejects that combination."""

    exposure = build_exposure("native_tool_search")
    session, sent = _session([_SEARCHED_AND_CALLED], exposure=exposure)
    session.turn(tools=_tools(exposure))
    payload = sent[0]

    tools = payload["tools"]
    assert tools[0] == TOOL_SEARCH_TOOL
    assert "defer_loading" not in tools[0]
    deferred = [item for item in tools if item.get("defer_loading")]
    assert {item["name"] for item in deferred} == set(
        exposure.withheld_names()
    )
    assert len(deferred) + len(exposure.available_names()) + 1 == len(tools)
    breakpoints = [item for item in tools if "cache_control" in item]
    assert len(breakpoints) == 1
    assert not breakpoints[0].get("defer_loading")
    assert breakpoints[0] is not tools[0] or len(tools) == 1
    # The system prompt is a top-level block, cached, not a message.
    assert payload["system"][0]["text"] == "THE SYSTEM PROMPT"
    assert payload["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert all(item["role"] != "system" for item in payload["messages"])
    assert payload["thinking"] == {"type": "adaptive"}
    assert "budget_tokens" not in json.dumps(payload)


def test_native_blocks_are_echoed_back_byte_identical(tmp_path):
    """The API requires the assistant turn back unchanged, and a trimmed
    thinking or search block invalidates it."""

    exposure = build_exposure("native_tool_search")
    session, sent = _session([_turn(1), _turn(2)], exposure=exposure)
    session.turn(tools=_tools(exposure))
    session.append_tool_results(
        [
            {
                "role": "tool",
                "tool_call_id": "toolu_01",
                "content": json.dumps({"status": "ok"}),
            }
        ]
    )
    session.turn(tools=_tools(exposure))

    echoed = sent[1]["messages"][1]
    assert echoed["role"] == "assistant"
    assert echoed["content"] == _turn(1)["content"]

    # And no tool_result is ever sent for the server tool's own id.
    wire = json.dumps(sent[1])
    assert "srvtoolu_01ABC123" in wire
    for message in sent[1]["messages"]:
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                assert not str(block["tool_use_id"]).startswith("srvtoolu_")


def test_thinking_never_reaches_the_public_plane(tmp_path):
    """The wire history keeps the blocks; nothing else ever sees them."""

    exposure = build_exposure("native_tool_search")
    session, _ = _session([_SEARCHED_AND_CALLED], exposure=exposure)
    response, receipt = session.turn(tools=_tools(exposure))

    secret = "PRIVATE REASONING THAT MUST NEVER BE PUBLISHED"
    assert secret not in json.dumps(response)
    assert secret not in json.dumps(session.public_history())
    assert secret in json.dumps(session._history)
    assert receipt.reasoning_continuation_present is True
    # Redacted thinking is the same channel, so it is refused the same way.
    from chemsmart.agent.runtime.anthropic import _public_payload

    redacted = _public_payload(
        {"content": [{"type": "redacted_thinking", "data": "OPAQUE"}]}
    )
    assert redacted == {"content": []}


def test_the_loop_reads_one_envelope_shape(tmp_path):
    """The wire format does not leak into what the product means."""

    exposure = build_exposure("native_tool_search")
    session, _ = _session([_SEARCHED_AND_CALLED], exposure=exposure)
    response, receipt = session.turn(tools=_tools(exposure))

    from chemsmart.agent.loop import _decode_tool_call

    message = response["choices"][0]["message"]
    assert response["choices"][0]["finish_reason"] == "tool_calls"
    (call,) = message["tool_calls"]
    call_id, name, arguments = _decode_tool_call(call)
    assert (name, arguments) == ("about_operations_geometry", {})
    assert call_id == "toolu_01XYZ789"
    # The one number that says whether deferral bought what it claims to.
    assert response["usage"]["cache_read_input_tokens"] == 1100
    assert session.cache_observation()["cache_read_input_tokens"] == 1100
    assert receipt.provider == "anthropic"
    assert session.capabilities.wire_protocol == ANTHROPIC_WIRE_PROTOCOL
    assert session.capabilities.exposure_mode == "native_tool_search"


def test_a_server_search_writes_the_hosts_own_discovery_event(tmp_path):
    """One stream shape, whichever backend searched."""

    store = RuntimeEventStore(
        tmp_path / "events.jsonl", session_id="anthropic-session"
    )
    host = CommandCompiledToolHostV1(
        event_store=store,
        exposure=build_exposure("native_tool_search"),
        task_spec_sha256s=(canonical_sha256("synthetic task"),),
    )
    session, _ = _session(
        [_SEARCHED_AND_CALLED], exposure=host.surface.exposure
    )
    session.turn(tools=_tools(host.surface.exposure))

    assert session.discovered_capabilities() == ("about_operations_geometry",)
    host.record_provider_discovery(
        "anthropic-session.turn-1", session.discovered_capabilities()
    )

    loaded = [
        event
        for event in store.read_events()
        if event.kind == EventKind.CAPABILITY_LOADED.value
    ]
    assert [event.payload["signal"] for event in loaded] == ["provider_search"]
    assert loaded[0].payload["loaded"] == ["about_operations_geometry"]
    assert host.exposure.is_available("about_operations_geometry")


def test_a_provider_cannot_name_a_capability_this_host_lacks(tmp_path):
    """Discovery is not permission, and a provider is not an authority."""

    store = RuntimeEventStore(
        tmp_path / "events.jsonl", session_id="anthropic-session"
    )
    host = CommandCompiledToolHostV1(
        event_store=store, exposure=build_exposure("native_tool_search")
    )
    with pytest.raises(CapabilityNotInCatalogueError):
        host.record_provider_discovery(
            "anthropic-session.turn-1", ("run_the_experiment",)
        )


def test_load_then_reissue_rides_a_tool_reference_on_this_wire(tmp_path):
    """The host says which definitions should be readable; the adapter
    turns that into the blocks this API expands, and nothing else does."""

    exposure = build_exposure("native_tool_search")
    session, sent = _session([_turn(1), _turn(2)], exposure=exposure)
    session.turn(tools=_tools(exposure))
    session.append_tool_results(
        [
            {
                "role": "tool",
                "tool_call_id": "toolu_01",
                "content": json.dumps(
                    {
                        "status": "schema_loaded",
                        "load_capabilities": ["extract_result_quantities"],
                        "result": {
                            "callable_now": "extract_result_quantities"
                        },
                    }
                ),
            }
        ]
    )
    block = session._history[-1]["content"][0]
    assert block["type"] == "tool_result"
    assert block["content"][0]["type"] == "text"
    assert block["content"][1] == {
        "type": "tool_reference",
        "tool_name": "extract_result_quantities",
    }
    # And the name it references is in the tools array, or the API 400s.
    session.turn(tools=_tools(exposure))
    names = {item["name"] for item in sent[1]["tools"]}
    assert "extract_result_quantities" in names


def test_an_alias_echo_is_tolerated_only_on_this_wire(tmp_path):
    """A requested alias may be answered by the dated id it resolved to.

    The base check -- exact equality -- stays exactly as strict: on a
    wire that does not resolve aliases, an inexact echo means another
    model answered, which is what that check exists to catch.
    """

    resolved = {
        **_SEARCHED_AND_CALLED,
        "model": _MODEL + "-20260214",
    }
    exposure = build_exposure("native_tool_search")
    session, _ = _session([resolved], exposure=exposure)
    session.turn(tools=_tools(exposure))

    from chemsmart.agent.runtime.deepseek import _validate_response_model

    with pytest.raises(Exception):
        _validate_response_model(resolved, expected_model=_MODEL)

    other = {**_SEARCHED_AND_CALLED, "model": "some-other-model"}
    session2, _ = _session([other], exposure=exposure)
    with pytest.raises(Exception):
        session2.turn(tools=_tools(exposure))


def test_a_paused_turn_is_resumed_and_is_not_an_outcome(tmp_path):
    """``pause_turn`` means re-send, not a terminal state."""

    paused = {
        "id": "msg_paused",
        "type": "message",
        "role": "assistant",
        "model": _MODEL,
        "content": [{"type": "text", "text": "still working"}],
        "stop_reason": "pause_turn",
        "usage": {"input_tokens": 10, "output_tokens": 2},
    }
    exposure = build_exposure("native_tool_search")
    session, sent = _session([paused, _SEARCHED_AND_CALLED], exposure=exposure)
    response, _ = session.turn(tools=_tools(exposure))
    assert len(sent) == 2
    assert response["choices"][0]["finish_reason"] == "tool_calls"


def test_every_existing_provider_profile_digest_is_unchanged():
    """Admitting a second wire protocol changed no archived arithmetic.

    ``wire_protocol`` is inside the digest body, so a profile minted as
    ``openai`` has to keep the exact body it always had. The value is
    derived from the declared type rather than hard-coded, and the
    openai branch resolves to the same literal it did before.
    """

    from chemsmart.agent.provider_config import _build_profile

    entry = {
        "type": "openai",
        "model": "a-model",
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "context_tokens": 128000,
        "max_output_tokens": 8192,
        "reasoning_effort": "max",
    }
    profile = _build_profile("frozen", entry)
    assert profile.wire_protocol == "openai-chat-completions"
    assert profile.profile_sha256 == canonical_sha256(
        {
            "schema_version": "chemsmart.agent-provider-profile.v1",
            "profile_name": "frozen",
            "provider": "deepseek",
            "wire_protocol": "openai-chat-completions",
            "api_key_env": "DEEPSEEK_API_KEY",
            "model": "a-model",
            "endpoint": "https://api.deepseek.com",
            "reasoning_effort": "max",
            "preserve_thinking": True,
            "context_tokens": 128000,
            "max_output_tokens": 8192,
        }
    )

    anthropic = _build_profile(
        "anthropic",
        {
            "type": "anthropic",
            "model": _MODEL,
            "api_key_env": "ANTHROPIC_API_KEY",
            "context_tokens": 200000,
            "max_output_tokens": 8192,
        },
    )
    assert anthropic.wire_protocol == ANTHROPIC_WIRE_PROTOCOL
    assert anthropic.endpoint == ANTHROPIC_OFFICIAL_ENDPOINT
    assert anthropic.profile_sha256 != profile.profile_sha256
    with pytest.raises(ContractError):
        _build_profile("local", {"type": "local", "model": "x"})
