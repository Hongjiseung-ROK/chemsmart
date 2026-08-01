"""Offline contracts for the separately frozen P3 v2 provider specimen."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from chemsmart.agent.harness.frontier_live_provider import (
    FrontierLiveCapabilityError,
)
from chemsmart.agent.harness.frontier_live_provider_v2 import (
    MAX_TOKENS,
    load_v2_profile,
    preflight_credential_resolution_v2,
    run_live_capability_specimen_v2,
    validate_live_capability_v2_receipt,
)
from chemsmart.agent.harness.frontier_live_provider import (
    _request_contract as _v1_request_contract,
)
from chemsmart.agent.harness.frontier_live_provider_v2 import (
    _request_contract as _v2_request_contract,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_inputs(tmp_path: Path) -> Path:
    receipt_dir = tmp_path / "docs/program/frontier-agent/receipts"
    receipt_dir.mkdir(parents=True)
    base_url = "https://api.deepseek.com"
    (receipt_dir / "p1-api-usage.json").write_text(
        json.dumps({
            "schema_version": 1,
            "phase": "P1",
            "observed_at": "2026-08-01T00:00:00Z",
            "alias_resolution": {"deepseek": {
                "configured_api_key_env": "DEEPSEEK-api-key",
                "provider_type": "openai",
                "model": "deepseek-v4-pro",
                "base_url_sha256": hashlib.sha256(base_url.encode()).hexdigest(),
            }},
            "probes": [{"service": "deepseek", "http_status": 200, "outcome": "ok", "usage": {
                "is_available": True,
                "balances": [{"currency": "USD", "total_balance": "0.82"}],
            }}],
        }),
        encoding="utf-8",
    )
    frozen_receipt_path = (
        _REPO_ROOT / "docs/program/frontier-agent/receipts/"
        "p3-live-provider-capability-v1.json"
    )
    frozen_receipt = json.loads(frozen_receipt_path.read_text(encoding="utf-8"))
    (receipt_dir / "p3-live-provider-capability-v1.json").write_bytes(
        frozen_receipt_path.read_bytes()
    )
    for artifact in frozen_receipt["source_artifacts"]:
        destination = tmp_path / artifact["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((_REPO_ROOT / artifact["path"]).read_bytes())
    provider_path = tmp_path / "agent.yaml"
    provider_path.write_text(
        """providers:
  deepseek:
    type: openai
    api_key_env: DEEPSEEK-api-key
    model: deepseek-v4-pro
    base_url: https://api.deepseek.com
""",
        encoding="utf-8",
    )
    return provider_path


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def model_dump(self) -> dict[str, Any]:
        return self.payload


class _Client:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.kwargs: dict[str, Any] | None = None
        self.closed = False
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **kwargs: Any) -> _Response:
        self.kwargs = kwargs
        return self.response

    def close(self) -> None:
        self.closed = True


class _ProviderError(Exception):
    status_code = 429


class _FailingClient:
    def __init__(self) -> None:
        self.closed = False
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **_kwargs: Any) -> _Response:
        raise _ProviderError()

    def close(self) -> None:
        self.closed = True


def _valid_response() -> _Response:
    return _Response({
        "id": "response-not-retained",
        "model": "deepseek-v4-pro",
        "choices": [{
            "finish_reason": "tool_calls",
            "message": {"tool_calls": [{"type": "function", "function": {
                "name": "frontier_capability_marker",
                "arguments": json.dumps({
                    "case_id": "P3-F12",
                    "terminal_status": "blocked",
                    "rule_id": "p3.provider.capability_or_tool_drift",
                }),
            }}]},
        }],
        "usage": {
            "prompt_tokens": 111,
            "completion_tokens": 9,
            "total_tokens": 120,
            "completion_tokens_details": {"reasoning_tokens": 0},
        },
    })


def test_v2_changes_only_the_output_ceiling_and_never_dispatches(tmp_path: Path) -> None:
    provider_path = _write_inputs(tmp_path)
    profile = load_v2_profile(repo_root=tmp_path, provider_yaml_path=provider_path)
    client = _Client(_valid_response())
    environment = {"DEEPSEEK-api-key": "fixture-only-key"}
    ticks = iter((1.0, 1.125))

    receipt = run_live_capability_specimen_v2(
        profile=profile,
        environment=environment,
        client_factory=lambda **_: client,
        clock=lambda: next(ticks),
    )

    assert receipt["status"] == "completed"
    assert receipt["contract"]["v1_to_v2_change"] == "max_tokens_64_to_256_only"
    assert client.kwargs is not None
    assert client.kwargs["max_tokens"] == MAX_TOKENS == 256
    assert client.kwargs["parallel_tool_calls"] is False
    assert client.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    assert receipt["non_execution"] == {
        "tool_execution_count": 0,
        "engine_invocations": 0,
        "scheduler_invocations": 0,
    }
    assert validate_live_capability_v2_receipt(receipt) == ()
    assert "fixture-only-key" not in json.dumps(receipt)
    assert "response-not-retained" not in json.dumps(receipt)
    assert "DEEPSEEK_API_KEY" not in environment
    assert client.closed is True


def test_v2_request_contract_changes_only_max_tokens_from_frozen_v1() -> None:
    v1_contract = _v1_request_contract("deepseek-v4-pro")
    v2_contract = _v2_request_contract("deepseek-v4-pro")

    assert v1_contract["max_tokens"] == 64
    assert v2_contract["max_tokens"] == 256
    v1_contract["max_tokens"] = v2_contract["max_tokens"]
    assert v2_contract == v1_contract


def test_v2_invalid_arguments_block_without_a_retry(tmp_path: Path) -> None:
    provider_path = _write_inputs(tmp_path)
    profile = load_v2_profile(repo_root=tmp_path, provider_yaml_path=provider_path)
    invalid = _valid_response().model_dump()
    invalid["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = "{}"
    receipt = run_live_capability_specimen_v2(
        profile=profile,
        environment={"DEEPSEEK-api-key": "fixture-only-key"},
        client_factory=lambda **_: _Client(_Response(invalid)),
        clock=lambda: 1.0,
    )

    assert receipt["status"] == "blocked"
    assert receipt["observation"]["request_count"] == 1
    assert receipt["observation"]["retry_count"] == 0
    assert "v2.tool_arguments_invalid" in receipt["validation_issues"]
    assert receipt["non_execution"]["tool_execution_count"] == 0


def test_v2_rejects_completion_token_ceiling_before_any_dispatch(tmp_path: Path) -> None:
    provider_path = _write_inputs(tmp_path)
    profile = load_v2_profile(repo_root=tmp_path, provider_yaml_path=provider_path)
    over_cap = _valid_response().model_dump()
    over_cap["usage"]["completion_tokens"] = 257
    over_cap["usage"]["total_tokens"] = 368
    receipt = run_live_capability_specimen_v2(
        profile=profile,
        environment={"DEEPSEEK-api-key": "fixture-only-key"},
        client_factory=lambda **_: _Client(_Response(over_cap)),
        clock=lambda: 1.0,
    )

    assert receipt["status"] == "blocked"
    assert "v2.completion_token_ceiling_exceeded" in receipt["validation_issues"]
    assert receipt["non_execution"]["tool_execution_count"] == 0


def test_v2_credential_preflight_is_in_process_only(tmp_path: Path) -> None:
    provider_path = _write_inputs(tmp_path)
    profile = load_v2_profile(repo_root=tmp_path, provider_yaml_path=provider_path)
    environment = {"DEEPSEEK-api-key": "fixture-only-key"}

    resolution = preflight_credential_resolution_v2(
        profile=profile,
        environment=environment,
    )

    assert resolution.bound_in_process is True
    assert "DEEPSEEK_API_KEY" not in environment


def test_v2_receipt_validator_rejects_execution_boundary_violation(tmp_path: Path) -> None:
    provider_path = _write_inputs(tmp_path)
    profile = load_v2_profile(repo_root=tmp_path, provider_yaml_path=provider_path)
    receipt = run_live_capability_specimen_v2(
        profile=profile,
        environment={"DEEPSEEK-api-key": "fixture-only-key"},
        client_factory=lambda **_: _Client(_valid_response()),
        clock=lambda: 1.0,
    )
    receipt["non_execution"]["tool_execution_count"] = 1

    assert "v2.execution_boundary_violated" in validate_live_capability_v2_receipt(receipt)


def test_v2_receipt_validator_rejects_tampered_green_result(tmp_path: Path) -> None:
    provider_path = _write_inputs(tmp_path)
    profile = load_v2_profile(repo_root=tmp_path, provider_yaml_path=provider_path)
    receipt = run_live_capability_specimen_v2(
        profile=profile,
        environment={"DEEPSEEK-api-key": "fixture-only-key"},
        client_factory=lambda **_: _Client(_valid_response()),
        clock=lambda: 1.0,
    )
    receipt["observation"]["finish_reason"] = "length"
    receipt["observation"]["arguments_schema_valid"] = False
    receipt["observation"]["request_count"] = 0
    receipt["validation_issues"] = ["v2.tool_arguments_invalid"]

    issues = validate_live_capability_v2_receipt(receipt)

    assert "v2.completed_observation_invalid" in issues
    assert "v2.completed_validation_issues_present" in issues


def test_v2_rejects_any_frozen_v1_receipt_drift(tmp_path: Path) -> None:
    provider_path = _write_inputs(tmp_path)
    v1_receipt_path = (
        tmp_path / "docs/program/frontier-agent/receipts/"
        "p3-live-provider-capability-v1.json"
    )
    v1_receipt_path.write_bytes(v1_receipt_path.read_bytes() + b"\n")

    with pytest.raises(FrontierLiveCapabilityError, match="P3 v1 receipt hash drift"):
        load_v2_profile(repo_root=tmp_path, provider_yaml_path=provider_path)


def test_v2_rejects_any_frozen_v1_source_artifact_drift(tmp_path: Path) -> None:
    provider_path = _write_inputs(tmp_path)
    source_path = tmp_path / "chemsmart/agent/harness/frontier_live_provider.py"
    source_path.write_bytes(source_path.read_bytes() + b"\n")

    with pytest.raises(FrontierLiveCapabilityError, match="P3 v1 source artifact drift"):
        load_v2_profile(repo_root=tmp_path, provider_yaml_path=provider_path)


def test_v2_preserves_direct_provider_error_status_without_retry(tmp_path: Path) -> None:
    provider_path = _write_inputs(tmp_path)
    profile = load_v2_profile(repo_root=tmp_path, provider_yaml_path=provider_path)
    client = _FailingClient()
    receipt = run_live_capability_specimen_v2(
        profile=profile,
        environment={"DEEPSEEK-api-key": "fixture-only-key"},
        client_factory=lambda **_: client,
        clock=lambda: 1.0,
    )

    assert receipt["status"] == "blocked"
    assert receipt["outcome"] == "transport_or_provider_error_no_retry"
    assert receipt["observation"]["http_status"] == 429
    assert receipt["observation"]["retry_count"] == 0
    assert client.closed is True
