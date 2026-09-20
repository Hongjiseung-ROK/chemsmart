"""An anthropic profile loads, derives its provider, and builds its adapter.

This file used to pin the opposite -- that the profile was valid
configuration which refused at ``runtime_config()`` with "the anthropic
adapter is not registered in this release". The adapter is registered
now, so the refusal is gone and what replaces it is the same three
questions answered the other way: the profile loads, the provider is
derived from its endpoint rather than from its name, and the config it
builds is the Messages one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.provider_config import load_agent_provider_selection

pytestmark = pytest.mark.capability("tool:*")

_YAML = """\
active: anthropic
fallback: []
providers:
  anthropic:
    type: anthropic
    api_key_env: ANTHROPIC_API_KEY
    model: claude-fable-5
    context_tokens: 1000000
    max_output_tokens: 128000
    base_url: https://api.anthropic.com
    reasoning_effort: high
"""


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "agent.yaml"
    path.write_text(_YAML, encoding="utf-8")
    return path


def test_the_profile_loads_and_derives_its_provider(tmp_path):
    profile = load_agent_provider_selection(_config(tmp_path)).active_profile

    assert profile.provider == "anthropic"
    assert profile.model == "claude-fable-5"
    assert profile.api_key_env == "ANTHROPIC_API_KEY"
    assert profile.wire_protocol == "anthropic-messages"


def test_it_builds_the_messages_adapter_configuration(tmp_path):
    from chemsmart.agent.runtime.anthropic import AnthropicMessagesConfigV1

    profile = load_agent_provider_selection(_config(tmp_path)).active_profile
    config = profile.runtime_config()

    assert isinstance(config, AnthropicMessagesConfigV1)
    assert config.model == "claude-fable-5"
    assert config.reasoning_effort == "high"
    assert config.adaptive_thinking is True


def test_a_profile_that_states_no_endpoint_takes_the_declared_one(tmp_path):
    """The shipped sample writes ``base_url: \'\'``; the declaration owns
    the endpoint, so the profile need not restate it."""

    path = tmp_path / "agent.yaml"
    path.write_text(
        _YAML.replace(
            "    base_url: https://api.anthropic.com\n", "    base_url: ''\n"
        ),
        encoding="utf-8",
    )
    profile = load_agent_provider_selection(path).active_profile
    assert profile.endpoint == "https://api.anthropic.com"


def test_a_type_this_runtime_has_no_wire_for_is_refused(tmp_path):
    path = tmp_path / "agent.yaml"
    path.write_text(
        _YAML.replace("type: anthropic", "type: local"), encoding="utf-8"
    )
    with pytest.raises(ContractError, match="type openai or anthropic"):
        load_agent_provider_selection(path)


def test_an_inactive_anthropic_block_never_blocks_the_active_profile(
    tmp_path,
):
    path = tmp_path / "agent.yaml"
    path.write_text(
        _YAML.replace("active: anthropic", "active: openai") + """\
  openai:
    type: openai
    api_key_env: OPENAI_API_KEY
    model: gpt-5.2
    context_tokens: 400000
    max_output_tokens: 64000
    base_url: https://api.openai.com/v1
""",
        encoding="utf-8",
    )

    profile = load_agent_provider_selection(path).active_profile

    assert profile.provider == "openai"
    assert profile.runtime_config().model == "gpt-5.2"
    assert profile.runtime_config().reasoning_effort == ""
