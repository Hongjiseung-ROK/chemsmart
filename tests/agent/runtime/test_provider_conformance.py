"""No-network tests for the bounded DeepSeek H0 conformance bridge."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from chemsmart.agent.api_access import CredentialAccessController
from chemsmart.agent.runtime.harness_profiles import (
    CapabilityEvidenceBasis,
    ContinuationMode,
)
from chemsmart.agent.runtime.provider_conformance import (
    ProbeErrorClass,
    ProviderConformanceProbeError,
    compute_source_snapshot_sha256,
    run_deepseek_h0_conformance_probe,
    validate_deepseek_h0_receipt_bindings,
)
from chemsmart.agent.services.tool_loop_runner import public_message_history


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SOURCE = compute_source_snapshot_sha256(_REPO_ROOT)
_SECRET = "synthetic-deepseek-secret-must-not-persist"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _controller() -> CredentialAccessController:
    return CredentialAccessController(
        keychain_reader=lambda service, account: None,
        environment={"DEEPSEEK_API_KEY": _SECRET},
    )


def _tool_response(*, parallel: bool = False) -> dict[str, Any]:
    calls = [
        {
            "id": "call-schema-1",
            "type": "function",
            "function": {
                "name": "inspect_command_schema",
                "arguments": json.dumps(
                    {"request_context": "Gaussian optimization command schema"}
                ),
            },
        }
    ]
    if parallel:
        calls.append(
            {
                "id": "call-schema-2",
                "type": "function",
                "function": {
                    "name": "inspect_command_schema",
                    "arguments": json.dumps(
                        {"request_context": "ORCA frequency command schema"}
                    ),
                },
            }
        )
    return {
        "id": "response-tool",
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "reasoning_content": "private probe reasoning",
                    "tool_calls": calls,
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {
            "prompt_tokens": 40,
            "completion_tokens": 12,
            "total_tokens": 52,
        },
    }


def _final_response() -> dict[str, Any]:
    return {
        "id": "response-final",
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Schema inspected.",
                    "reasoning_content": "private final reasoning",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 90,
            "completion_tokens": 8,
            "total_tokens": 98,
        },
    }


class _ScriptedFactory:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls = 0
        self.constructor_observations: list[dict[str, Any]] = []
        self.message_observations: list[list[dict[str, Any]]] = []
        self.reasoning_replayed = False
        self.tool_history_replayed = False

    def __call__(self, **kwargs: Any) -> "_ScriptedFactory":
        assert kwargs.pop("api_key") == _SECRET
        self.constructor_observations.append(kwargs)
        return self

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        timeout_s: float = 30,
    ) -> dict[str, Any]:
        assert timeout_s == 30
        assert tools is not None
        self.message_observations.append(deepcopy(messages))
        if self.calls == 1:
            self.reasoning_replayed = any(
                message.get("role") == "assistant"
                and "reasoning_content" in message
                for message in messages
            )
            self.tool_history_replayed = any(
                message.get("role") == "tool" for message in messages
            )
        response = self.responses[self.calls]
        self.calls += 1
        return response


def _persisted_text(root: Path) -> str:
    chunks: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
    return "\n".join(chunks)


def test_source_snapshot_binds_code_prompt_and_dependency_inputs(tmp_path) -> None:
    root = tmp_path / "checkout"
    source = root / "chemsmart"
    nested = source / "agent" / "runtime"
    nested.mkdir(parents=True)
    (source / "__init__.py").write_bytes(b'"""package"""\n')
    provider_path = nested / "provider.py"
    provider_bytes = b"VALUE = 1\n"
    provider_path.write_bytes(provider_bytes)
    prompt = source / "agent" / "prompts" / "tool_loop.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_bytes(b"deterministic probe prompt\n")
    (root / "pyproject.toml").write_bytes(b"[project]\nname='probe'\n")
    cache = nested / "__pycache__"
    cache.mkdir()
    (cache / "ignored.py").write_bytes(b"CACHE = 1\n")
    docs = root / "docs" / "evaluation" / "receipts"
    docs.mkdir(parents=True)
    receipt_path = docs / "receipt.json"
    receipt_path.write_text('{"receipt": 1}\n', encoding="utf-8")

    baseline = compute_source_snapshot_sha256(root)
    assert len(baseline) == 64

    mirror_root = tmp_path / "mirror-checkout"
    mirror_source = mirror_root / "chemsmart"
    mirror_nested = mirror_source / "agent" / "runtime"
    mirror_nested.mkdir(parents=True)
    (mirror_nested / "provider.py").write_bytes(provider_bytes)
    (mirror_source / "__init__.py").write_bytes(b'"""package"""\n')
    mirror_prompt = mirror_source / "agent" / "prompts" / "tool_loop.md"
    mirror_prompt.parent.mkdir(parents=True)
    mirror_prompt.write_bytes(b"deterministic probe prompt\n")
    (mirror_root / "pyproject.toml").write_bytes(
        b"[project]\nname='probe'\n"
    )
    assert compute_source_snapshot_sha256(mirror_root) == baseline

    receipt_path.write_text('{"receipt": 2}\n', encoding="utf-8")
    (cache / "ignored.py").write_bytes(b"CACHE = 2\n")
    assert compute_source_snapshot_sha256(root) == baseline

    prompt.write_bytes(b"changed probe prompt\n")
    assert compute_source_snapshot_sha256(root) != baseline
    prompt.write_bytes(b"deterministic probe prompt\n")

    provider_path.write_bytes(b"VALUE = 2\n")
    assert compute_source_snapshot_sha256(root) != baseline
    provider_path.write_bytes(provider_bytes)
    provider_path.rename(nested / "renamed.py")
    assert compute_source_snapshot_sha256(root) != baseline


def test_h0_probe_uses_two_leases_and_persists_only_public_evidence(
    tmp_path,
) -> None:
    factory = _ScriptedFactory([_tool_response(), _final_response()])

    receipt = run_deepseek_h0_conformance_probe(
        credential_controller=_controller(),
        session_root=tmp_path / "sessions",
        repo_root=_REPO_ROOT,
        provider_factory=factory,
    )

    assert receipt.verdict == "compatible"
    assert receipt.request_budget == 2
    assert receipt.model_step_budget == 2
    assert receipt.tool_call_budget == 1
    assert receipt.requests_used == 2
    assert receipt.transport_attempts == 2
    assert receipt.model_steps == 2
    assert receipt.tool_calls == 1
    assert receipt.input_tokens == 130
    assert receipt.output_tokens == 20
    assert receipt.usage_complete is True
    assert receipt.wall_time_ms >= 0
    assert receipt.max_output_tokens == 512
    assert receipt.thinking_mode == "enabled"
    assert receipt.registered_tool_names == ("inspect_command_schema",)
    assert receipt.virtual_tool_names == ("ask_user",)
    assert receipt.engine_calls == 0
    assert receipt.hpc_calls == 0
    assert receipt.credential_status == "valid"
    assert receipt.quota_sufficient_for_probe is True
    assert receipt.source_snapshot_sha256 == _SOURCE
    assert receipt.probe_observation.source_snapshot_sha256 == _SOURCE
    assert receipt.target_origin == "https://api.deepseek.com"
    assert receipt.probe_observation.target_origin == receipt.target_origin
    assert receipt.sdk_name == "openai"
    assert receipt.sdk_max_retries == 0
    assert receipt.probe_observation.sdk_version == receipt.sdk_version
    assert receipt.probe_observation.sdk_max_retries == 0
    assert receipt.probe_observation.runtime_mode == "active"
    assert receipt.probe_observation.runtime_phase == "complete"
    assert receipt.probe_observation.runtime_shadow_violations == ()
    assert receipt.probe_observation.permission_mode == "read_only"
    assert receipt.instruction_bundle_sha256
    assert receipt.probe_observation.instruction_message_count >= 1
    expected_public_history = public_message_history(
        [
            *factory.message_observations[-1],
            _final_response()["choices"][0]["message"],
        ]
    )
    assert receipt.public_history_sha256 == _digest(
        tuple(_digest(message) for message in expected_public_history)
    )
    assert receipt.capabilities.structured_tool_calls_basis is (
        CapabilityEvidenceBasis.OBSERVED_PROBE
    )
    assert receipt.capabilities.max_context_tokens_basis is (
        CapabilityEvidenceBasis.OFFICIAL_DOCUMENTATION
    )
    assert receipt.capabilities.max_context_tokens == 1_000_000
    assert receipt.capabilities.max_parallel_tool_calls == 1
    assert receipt.capabilities.max_parallel_tool_calls_basis is (
        CapabilityEvidenceBasis.HARNESS_LIMIT
    )
    assert receipt.capabilities.tool_continuation is (
        ContinuationMode.PUBLIC_HISTORY
    )
    assert receipt.capabilities.reasoning_continuation is (
        ContinuationMode.EPHEMERAL_PRIVATE_TURN
    )
    assert factory.calls == 2
    assert factory.reasoning_replayed is True
    assert factory.tool_history_replayed is True
    assert all(
        observation == {
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "provider_name": "deepseek",
            "thinking_mode": "enabled",
            "reasoning_effort": "high",
            "max_output_tokens": 512,
            "max_retries": 0,
        }
        for observation in factory.constructor_observations
    )
    persisted = _persisted_text(tmp_path)
    assert _SECRET not in persisted
    assert "private probe reasoning" not in persisted
    assert "private final reasoning" not in persisted
    assert '"kind": "provider_turn_raw"' not in persisted
    assert validate_deepseek_h0_receipt_bindings(
        receipt,
        repo_root=_REPO_ROOT,
    ) == ()


class _FailingFactory:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, **kwargs: Any) -> "_FailingFactory":
        assert kwargs.pop("api_key") == _SECRET
        return self

    def chat(self, messages, tools=None, timeout_s=30):
        del messages, tools, timeout_s
        self.calls += 1
        raise RuntimeError(f"remote failure containing {_SECRET}")


def test_h0_probe_does_not_retry_or_persist_provider_error_text(
    tmp_path,
) -> None:
    factory = _FailingFactory()

    with pytest.raises(ProviderConformanceProbeError) as captured:
        run_deepseek_h0_conformance_probe(
            credential_controller=_controller(),
            session_root=tmp_path / "sessions",
            repo_root=_REPO_ROOT,
            provider_factory=factory,
        )

    assert captured.value.error_class is ProbeErrorClass.PROVIDER_ERROR
    assert str(captured.value) == "provider_error"
    assert factory.calls == 1
    persisted = _persisted_text(tmp_path)
    assert _SECRET not in persisted
    assert "remote failure" not in persisted


def test_h0_probe_rejects_parallel_tool_attempt_without_second_request(
    tmp_path,
) -> None:
    factory = _ScriptedFactory([_tool_response(parallel=True)])

    receipt = run_deepseek_h0_conformance_probe(
        credential_controller=_controller(),
        session_root=tmp_path / "sessions",
        repo_root=_REPO_ROOT,
        provider_factory=factory,
    )

    assert receipt.verdict == "incompatible"
    assert receipt.requests_used == 1
    assert receipt.tool_calls == 1
    assert receipt.quota_sufficient_for_probe is False
    assert factory.calls == 1
    checks = {check.check_id: check for check in receipt.checks}
    assert checks["typed_tool_call_round_trip"].status.value == "fail"
    assert checks["deterministic_validator_gate"].status.value == "fail"


def test_h0_probe_rejects_stale_or_arbitrary_source_snapshot(tmp_path) -> None:
    factory = _ScriptedFactory([])
    stale_source = ("0" if _SOURCE[0] != "0" else "1") + _SOURCE[1:]

    with pytest.raises(ValueError, match="current H0 source bundle"):
        run_deepseek_h0_conformance_probe(
            credential_controller=_controller(),
            session_root=tmp_path / "sessions",
            repo_root=_REPO_ROOT,
            source_snapshot_sha256=stale_source,
            provider_factory=factory,
        )

    assert factory.calls == 0


def test_h0_binding_validator_rejects_stale_source_and_sdk(tmp_path) -> None:
    factory = _ScriptedFactory([_tool_response(), _final_response()])
    receipt = run_deepseek_h0_conformance_probe(
        credential_controller=_controller(),
        session_root=tmp_path / "sessions",
        repo_root=_REPO_ROOT,
        provider_factory=factory,
    )

    stale = receipt.model_copy(
        update={
            "source_snapshot_sha256": "0" * 64,
            "sdk_version": "0.0.0",
        }
    )

    assert validate_deepseek_h0_receipt_bindings(
        stale,
        repo_root=_REPO_ROOT,
    ) == (
        "provider.conformance.receipt_id_mismatch",
        "provider.h0.source_snapshot_stale",
        "provider.h0.sdk_binding_mismatch",
    )


def test_h0_missing_usage_is_an_incompatible_observation(tmp_path) -> None:
    tool_response = _tool_response()
    final_response = _final_response()
    final_response.pop("usage")

    receipt = run_deepseek_h0_conformance_probe(
        credential_controller=_controller(),
        session_root=tmp_path / "sessions",
        repo_root=_REPO_ROOT,
        provider_factory=_ScriptedFactory([tool_response, final_response]),
    )

    assert receipt.verdict == "incompatible"
    assert receipt.usage_complete is False
    checks = {check.check_id: check for check in receipt.checks}
    assert checks["bounded_transport_accounting"].status.value == "fail"
