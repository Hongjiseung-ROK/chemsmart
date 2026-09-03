"""Provider reasoning is kept privately, per campaign, and the receipt says so.

Hidden model reasoning is never scientific evidence and never reaches the
public plane; a research campaign may still need to read it. A profile
that states ``record_reasoning: true`` makes the host install a sink that
keeps each turn's reasoning beside the event stream, in the private run
directory, at 0600; the turn receipt's ``private_reasoning_persisted`` is
then a true word, and the public transcript is byte-identical either way.
"""

from __future__ import annotations

import json
import stat

from chemsmart.agent.provider_config import load_agent_provider_selection
from chemsmart.agent.runtime.deepseek import (
    DeepSeekV4FlashConfigV1,
    DeepSeekV4ToolSession,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.services.unified_session import _private_reasoning_sink

_CONFIG = DeepSeekV4FlashConfigV1(
    model="deepseek-v4-flash", context_tokens=131072, max_output_tokens=8192
)
_PRIVATE = "the model weighed the gauche effect here"


def _transport(_payload):
    return {
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "Done.",
                    "reasoning_content": _PRIVATE,
                },
            }
        ],
        "usage": {"prompt_tokens": 40, "completion_tokens": 5},
    }


def _session(sink=None):
    return DeepSeekV4ToolSession(
        transport=_transport,
        messages=[{"role": "user", "content": "Plan the workflow."}],
        config=_CONFIG,
        reasoning_sink=sink,
    )


def test_a_sink_keeps_the_reasoning_beside_the_stream_and_the_receipt_says_so(
    tmp_path,
):
    store = RuntimeEventStore(
        tmp_path / "run" / "events.jsonl", session_id="campaign-session"
    )
    kept = _session(_private_reasoning_sink(store, turn_id="t1"))
    plain = _session()
    assert kept.capabilities.private_reasoning_persisted is True
    assert plain.capabilities.private_reasoning_persisted is False

    _, kept_receipt = kept.turn()
    _, plain_receipt = plain.turn()
    assert kept_receipt.private_reasoning_persisted is True
    assert plain_receipt.private_reasoning_persisted is False

    (path,) = list((tmp_path / "run").glob("private-reasoning-*.json"))
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["reasoning_content"] == _PRIVATE
    assert record["request_sha256"] == kept_receipt.request_sha256
    (artifact,) = [
        event
        for event in store.read_events()
        if event.kind == EventKind.ARTIFACT_RECORDED.value
    ]
    assert artifact.payload["kind"] == "private_reasoning"
    assert _PRIVATE not in json.dumps(artifact.payload)

    # The public plane is identical with and without the sink.
    assert kept.public_history() == plain.public_history()
    assert _PRIVATE not in json.dumps(kept.public_history())


def test_the_profile_key_is_opt_in_and_digests_only_when_stated(tmp_path):
    base = """
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
""".lstrip()
    path = tmp_path / "agent.yaml"
    path.write_text(base, encoding="utf-8")
    silent = load_agent_provider_selection(path).active_profile
    assert silent.record_reasoning is None
    assert silent.runtime_config().record_reasoning is False

    path.write_text(base + "    record_reasoning: true\n", encoding="utf-8")
    asked = load_agent_provider_selection(path).active_profile
    assert asked.record_reasoning is True
    assert asked.runtime_config().record_reasoning is True
    # Stating the key changes the profile digest; leaving it unstated
    # keeps every profile minted before the key existed verifying.
    assert asked.profile_sha256 != silent.profile_sha256
