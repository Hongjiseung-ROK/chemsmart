from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import chemsmart.agent.tools_command as tools_command
from chemsmart.agent.core import AgentSession
from chemsmart.agent.public_visibility import sanitize_public_text
from chemsmart.agent.registry import ToolRegistry

from ._agent_session_helpers import FakeProvider
from ._loop_helpers import ScriptedRegistry, openai_final_response


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


def test_bound_command_session_runs_inside_the_embedder_owned_directory(
    monkeypatch,
    tmp_path,
):
    provider = object()
    original_cwd = Path.cwd()
    observed: list[Path] = []
    monkeypatch.setattr(
        tools_command, "SynthesisSession", _FakeSynthesisSession
    )
    monkeypatch.setattr(tools_command, "_command_schema", lambda: {})
    monkeypatch.setattr(
        tools_command,
        "_synthesize_command_with_session",
        lambda _session, _request: (
            observed.append(Path.cwd()) or {"status": "ready"}
        ),
    )
    session = tools_command.CommandSynthesisSession(
        provider,
        default_project="",
        working_directory=tmp_path,
    )

    session.synthesize_command("prepare a dry-run command")

    assert observed == [tmp_path.resolve()]
    assert Path.cwd() == original_cwd


def test_bound_command_execution_uses_the_same_embedder_owned_directory(
    monkeypatch,
    tmp_path,
):
    observed: list[tuple[Path, str, bool, int]] = []
    monkeypatch.setattr(tools_command, "SynthesisSession", _FakeSynthesisSession)
    monkeypatch.setattr(tools_command, "_command_schema", lambda: {})
    monkeypatch.setattr(
        tools_command,
        "execute_chemsmart_command",
        lambda command, test, timeout_s: observed.append(
            (Path.cwd(), command, test, timeout_s)
        )
        or {"ok": True},
    )
    session = tools_command.CommandSynthesisSession(
        object(),
        default_project="",
        working_directory=tmp_path,
    )

    assert session.execute_command("chemsmart run xtb -f water.xyz sp", timeout_s=90) == {"ok": True}
    assert observed == [(tmp_path.resolve(), "chemsmart run xtb -f water.xyz sp", False, 90)]


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
            "preflight": {
                "receipt_id": "sha256:abc123",
                "input": {
                    "basename": "water.xyz",
                    "digest": "sha256:def456",
                },
                "workspace_path": "/Users/researcher/private",
            },
        }
    )

    assert "workflow_state" not in result
    assert "raw_response" not in result
    assert result["preflight"]["receipt_id"] == "sha256:abc123"
    assert result["preflight"]["input"]["basename"] == "water.xyz"
    assert "/Users/researcher" not in repr(result)
    assert "[opaque-path]" in repr(result)


def test_public_text_redacts_root_level_absolute_paths():
    assert sanitize_public_text("Use /tmp, then inspect /etc.") == (
        "Use [opaque-path], then inspect [opaque-path]."
    )


def test_agent_session_rebinds_only_to_an_explicit_provider(tmp_path):
    first = object()
    second = object()
    session = AgentSession(provider=first, session_root=tmp_path)

    session.bind_provider(second)

    assert session._provider_instance() is second
    with pytest.raises(ValueError, match="provider is required"):
        session.bind_provider(None)
    assert session._provider_instance() is second


def test_session_created_callback_runs_after_request_persistence_before_provider(
    tmp_path,
):
    provider = FakeProvider(
        [{"__raw_response__": openai_final_response("Ready.")}]
    )
    session = AgentSession(
        provider=provider,
        registry=ScriptedRegistry({}),
        session_root=tmp_path,
    )
    observed: list[str] = []

    def observe_created_session(session_id: str) -> None:
        session_directory = tmp_path / session_id
        assert (session_directory / "session.json").is_file()
        assert '"kind": "request"' in (
            session_directory / "decision_log.jsonl"
        ).read_text()
        assert provider.calls == []
        observed.append(session_id)

    result = session.run_loop(
        "Inspect the current molecule.",
        on_session_created=observe_created_session,
    )

    assert observed == [result["session_id"]]
    assert len(provider.calls) == 1


def test_session_created_callback_failure_prevents_provider_call(tmp_path):
    provider = FakeProvider(
        [{"__raw_response__": openai_final_response("Must not run.")}]
    )
    session = AgentSession(
        provider=provider,
        registry=ScriptedRegistry({}),
        session_root=tmp_path,
    )

    def reject_binding(session_id: str) -> None:
        assert (tmp_path / session_id / "session.json").is_file()
        raise RuntimeError("host binding failed")

    with pytest.raises(RuntimeError, match="host binding failed"):
        session.run_loop(
            "Inspect the current molecule.",
            on_session_created=reject_binding,
        )

    assert provider.calls == []
