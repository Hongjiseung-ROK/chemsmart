"""The recorded tool exposure follows the surface the wire actually carries.

A guide opened mid-session extends the tool schema the next request is
built from, and the exposure record fired once at session start, so the
recorded digest went stale the moment a leaf opened (audit, 2026-09-03).
An exposure is appended whenever the surface's digest changes, keyed on
the digest, so an unchanged surface records nothing new.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from chemsmart.agent._contracts import canonical_sha256
from chemsmart.agent.loop import ToolLoopRunner
from chemsmart.agent.runtime.alibaba import (
    Qwen38MaxConfigV1,
    Qwen38MaxToolSession,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from tests.agent.provider_fakes import _DispatchSpyHost, _run_contracts

pytestmark = pytest.mark.capability("guide:*")


def _tool(name: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"{name}.",
            "parameters": {
                "type": "object",
                "properties": {"program": {"type": "string"}},
                "required": ["program"],
            },
        },
    }


class _SurfaceGrowsOnDispatch(_DispatchSpyHost):
    """A host whose first dispatch opens a leaf, as a guide would."""

    def dispatch(self, *, tool_name: str, arguments: dict, **kwargs):
        reply = super().dispatch(
            tool_name=tool_name, arguments=arguments, **kwargs
        )
        if len(self.surface.tool_definitions) == 1:
            grown = self.surface.tool_definitions + (_tool("leaf_tool"),)
            self.surface = SimpleNamespace(
                tool_definitions=grown,
                tool_schema_sha256=canonical_sha256(grown),
                profile=self.surface.profile,
            )
        return reply


def _response(identifier: str, *, tool_call: bool) -> dict:
    message: dict = {"role": "assistant", "reasoning_content": ""}
    if tool_call:
        message["content"] = ""
        message["tool_calls"] = [
            {
                "id": identifier,
                "type": "function",
                "function": {
                    "name": "inspect_program_capability",
                    "arguments": '{"program": "orca"}',
                },
            }
        ]
    else:
        message["content"] = "Done."
    return {
        "id": identifier,
        "model": "qwen3.8-max",
        "choices": [
            {
                "finish_reason": "tool_calls" if tool_call else "stop",
                "message": message,
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def test_a_surface_change_records_a_new_exposure_and_nothing_else_does(
    tmp_path,
):
    responses = iter(
        (
            _response("first", tool_call=True),
            _response("second", tool_call=True),
            _response("third", tool_call=False),
        )
    )
    config = Qwen38MaxConfigV1()
    session = Qwen38MaxToolSession(
        transport=lambda _payload: next(responses),
        messages=[{"role": "user", "content": "Plan the workflow."}],
        config=config,
    )
    store = RuntimeEventStore(
        tmp_path / "events" / "runtime.jsonl", session_id="protocol-session"
    )
    host = _SurfaceGrowsOnDispatch()
    first_digest = host.surface.tool_schema_sha256
    envelope, request_context, network = _run_contracts(host, config)

    result = ToolLoopRunner(host=host, event_store=store).run(
        session=session,
        envelope=envelope,
        request_context=request_context,
        provider_budget=network,
    )
    assert result.final_text == "Done."
    assert len(host.dispatched) == 2

    exposures = [
        event
        for event in store.read_events()
        if event.kind == EventKind.EXPOSURE_PLANNED.value
    ]
    # One at session start, one when the leaf opened; the third request
    # saw the same surface as the second and recorded nothing.
    assert [e.payload["tool_schema_sha256"] for e in exposures] == [
        first_digest,
        host.surface.tool_schema_sha256,
    ]
    assert list(exposures[-1].payload["tools"]) == [
        "inspect_program_capability",
        "leaf_tool",
    ]
