from __future__ import annotations

from typing import Any

import pytest

import chemsmart.agent.tools_command as tools_command
from chemsmart.agent.core import AgentSession
from chemsmart.agent.registry import ToolRegistry


class _FakeSynthesisSession:
    def __init__(self, provider: Any, **options: Any) -> None:
        self.provider = provider
        self.options = options
        self.default_project = options.get("default_project") or ""


def test_bound_command_session_never_discovers_a_provider(monkeypatch):
    provider = object()
    seen: list[tuple[_FakeSynthesisSession, str]] = []

    monkeypatch.setattr(tools_command, "SynthesisSession", _FakeSynthesisSession)
    monkeypatch.setattr(tools_command, "_command_schema", lambda: {"schema": True})
    monkeypatch.setattr(
        tools_command,
        "_synthesize_command_with_session",
        lambda session, request: seen.append((session, request))
        or {"status": "ready"},
    )
    monkeypatch.setattr(
        "chemsmart.agent.providers.get_provider",
        lambda: pytest.fail("bound synthesis must not discover user config"),
    )

    session = tools_command.CommandSynthesisSession(
        provider,
        default_project="studio-project",
    )

    assert session.synthesize_command("prepare a dry-run command") == {
        "status": "ready"
    }
    assert seen[0][0].provider is provider
    assert seen[0][0].options["schema"] == {"schema": True}
    assert seen[0][1] == "prepare a dry-run command"


def test_bound_command_specs_dispatch_to_the_injected_session(monkeypatch):
    provider = object()
    seen: list[tuple[Any, str]] = []
    monkeypatch.setattr(tools_command, "SynthesisSession", _FakeSynthesisSession)
    monkeypatch.setattr(tools_command, "_command_schema", lambda: {})
    monkeypatch.setattr(
        tools_command,
        "_synthesize_command_with_session",
        lambda session, request: seen.append((session.provider, request))
        or {"status": "informational", "explanation": "Inspected."},
    )

    session = tools_command.CommandSynthesisSession(provider, default_project="")
    registry = ToolRegistry(session.tool_specs())

    assert registry.call(
        "synthesize_command",
        {"request": "inspect this request"},
    ) == {
        "status": "informational",
        "explanation": "Inspected.",
    }
    assert seen == [(provider, "inspect this request")]


def test_bound_command_session_requires_a_provider():
    with pytest.raises(ValueError, match="provider is required"):
        tools_command.CommandSynthesisSession(None)


def test_host_visible_command_result_omits_private_provider_and_workspace_state():
    result = tools_command._host_visible_command_result(
        {
            "status": "ready",
            "command": "chemsmart run xtb -f /Users/researcher/private/water.xyz opt",
            "explanation": "Prepared /Users/researcher/private/water.xyz.",
            "workflow_state": {"cwd": "/Users/researcher/private"},
            "raw_response": {"provider": "private"},
            "semantic": {"verdict": "ok"},
            "intent": {"verdict": "ok"},
        }
    )

    assert "workflow_state" not in result
    assert "raw_response" not in result
    assert "/Users/researcher" not in repr(result)
    assert "[opaque-path]" in repr(result)


def test_agent_session_rebinds_only_to_an_explicit_provider(tmp_path):
    first = object()
    second = object()
    session = AgentSession(provider=first, session_root=tmp_path)

    session.bind_provider(second)

    assert session._provider_instance() is second
    with pytest.raises(ValueError, match="provider is required"):
        session.bind_provider(None)
    assert session._provider_instance() is second
