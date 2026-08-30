"""The goal recency restatement must reach the provider, not the helper.

``_coordinator_base_messages`` appends a third message restating a
goal's terms in the recency slot -- budgets, authority, deliverables,
and the refusal affordance -- because alphabetical canonical JSON lands
the goal block mid-context, in the attention trough. The production
call site then rebuilt the message list by hand from index 0, so the
restatement never reached a provider while the helper-direct test
asserted three messages and passed: a test that fabricates the
surrounding truth cannot catch a call-site drop.

These tests run the PRODUCTION assembly. The real
``run_live_agent_session`` binds the workspace, schema, previews, and
budget, builds its message list, and hands it to the runner; a
capturing stand-in for the runner records exactly what a provider
would have been sent. Only the wire is asserted.
"""

from __future__ import annotations

import pytest

from chemsmart.agent import live_session
from chemsmart.agent.goal_loop import _goal_terms_context

_WATER_XYZ = """3
water
O 0.000000 0.000000 0.117300
H 0.000000 0.757200 -0.469200
H 0.000000 -0.757200 -0.469200
"""


class _MessagesCaptured(Exception):
    """Carries the exact message list the session would have sent."""

    def __init__(self, messages):
        super().__init__("messages captured before any provider request")
        self.messages = messages


class _CapturingRunner:
    """Stands where UnifiedSessionRunner stands; sends nothing."""

    def __init__(self, **_kwargs):
        pass

    def run(self, *, messages, **_kwargs):
        raise _MessagesCaptured(messages)


@pytest.fixture
def provider_config(tmp_path):
    path = tmp_path / "agent.yaml"
    path.write_text(
        """
active: deepseek
fallback: []
providers:
  deepseek:
    type: openai
    api_key_env: DEEPSEEK-api-key
    model: deepseek-v4-flash
    context_tokens: 1000000
    max_output_tokens: 384000
    base_url: https://api.deepseek.com
    reasoning_effort: max
    preserve_thinking: true
""".lstrip(),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def secret_file(tmp_path):
    path = tmp_path / "api.env"
    path.write_text("DEEPSEEK-api-key=test-value\n", encoding="utf-8")
    return path


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "water.xyz").write_text(_WATER_XYZ, encoding="utf-8")
    return root


def _captured_messages(
    monkeypatch, *, provider_config, secret_file, workspace, goal_context
):
    monkeypatch.setattr(live_session, "UnifiedSessionRunner", _CapturingRunner)
    with pytest.raises(_MessagesCaptured) as excinfo:
        live_session.run_live_agent_session(
            task=(
                "Report the electronic energy of the water molecule at "
                "charge 0 and multiplicity 1."
            ),
            provider="deepseek",
            provider_config_file=provider_config,
            secret_file=secret_file,
            workspace=workspace,
            execution_enabled=False,
            approval_file=None,
            goal_context=goal_context,
        )
    return excinfo.value.messages


def test_a_goal_cycle_sends_the_recency_restatement(
    monkeypatch, provider_config, secret_file, workspace
):
    """The message the trough rationale exists for must be on the wire."""

    goal_context = _goal_terms_context(
        goal_id="GOAL-RECENCY-WIRE",
        granted_by="claude-owner-delegated-reviewer",
        envelope_record={
            "max_engine_calls": 4,
            "episode_wall_time_seconds": 1200.0,
        },
        max_revisions=2,
    )
    messages = _captured_messages(
        monkeypatch,
        provider_config=provider_config,
        secret_file=secret_file,
        workspace=workspace,
        goal_context=goal_context,
    )
    assert [item["role"] for item in messages] == ["system", "user", "user"]
    context_message, recency_message = messages[1], messages[2]
    # Duplication, not movement: the goal block stays in the canonical
    # context and the restatement repeats it at the tail.
    assert '"goal":' in context_message["content"]
    assert "GOAL-RECENCY-WIRE" in context_message["content"]
    assert recency_message["content"].startswith(
        "goal terms, restated for recency"
    )
    assert "GOAL-RECENCY-WIRE" in recency_message["content"]
    assert "engine_calls_remaining" in recency_message["content"]


def test_a_plain_session_sends_exactly_two_messages(
    monkeypatch, provider_config, secret_file, workspace
):
    """Without a goal there is nothing to restate; the shape is fixed."""

    messages = _captured_messages(
        monkeypatch,
        provider_config=provider_config,
        secret_file=secret_file,
        workspace=workspace,
        goal_context=None,
    )
    assert [item["role"] for item in messages] == ["system", "user"]
