"""Offline contract tests for the one-call Frontier provider specimen."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from chemsmart.agent.harness.frontier_live_provider import (
    CANONICAL_DEEPSEEK_ALIAS,
    DECLARED_MODEL,
    DECLARED_TOOL_NAME,
    load_deepseek_profile,
    preflight_credential_resolution,
    run_live_capability_specimen,
    validate_live_capability_receipt,
)


def _write_profile_inputs(tmp_path: Path) -> tuple[Path, Path]:
    receipt_path = tmp_path / "docs/program/frontier-agent/receipts/p1-api-usage.json"
    receipt_path.parent.mkdir(parents=True)
    base_url = "https://api.deepseek.com"
    import hashlib

    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "phase": "P1",
                "observed_at": "2026-08-01T00:00:00Z",
                "alias_resolution": {
                    "deepseek": {
                        "configured_api_key_env": "DEEPSEEK-api-key",
                        "provider_type": "openai",
                        "model": DECLARED_MODEL,
                        "base_url_sha256": hashlib.sha256(
                            base_url.encode("utf-8")
                        ).hexdigest(),
                    }
                },
                "probes": [
                    {
                        "service": "deepseek",
                        "http_status": 200,
                        "outcome": "ok",
                        "usage": {
                            "is_available": True,
                            "balances": [
                                {"currency": "USD", "total_balance": "0.82"}
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
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
    return receipt_path, provider_path


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def model_dump(self) -> dict[str, Any]:
        return self._payload


class _Completions:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.kwargs: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> _Response:
        self.kwargs = kwargs
        return self.response


class _Client:
    def __init__(self, response: _Response) -> None:
        self.completions = _Completions(response)
        self.chat = type("Chat", (), {"completions": self.completions})()
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _valid_response(*, tool_name: str = DECLARED_TOOL_NAME) -> _Response:
    return _Response(
        {
            "id": "cmpl-not-persisted",
            "model": DECLARED_MODEL,
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": json.dumps(
                                        {
                                            "case_id": "P3-F12",
                                            "terminal_status": "blocked",
                                            "rule_id": "p3.provider.capability_or_tool_drift",
                                        }
                                    ),
                                },
                            }
                        ]
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 111,
                "completion_tokens": 9,
                "total_tokens": 120,
                "completion_tokens_details": {"reasoning_tokens": 0},
            },
        }
    )


def test_profile_requires_the_p1_pinned_official_deepseek_entry(tmp_path: Path) -> None:
    _receipt_path, provider_path = _write_profile_inputs(tmp_path)

    profile = load_deepseek_profile(
        repo_root=tmp_path,
        provider_yaml_path=provider_path,
    )

    assert profile.model == DECLARED_MODEL
    assert profile.configured_api_key_env == "DEEPSEEK-api-key"
    assert profile.p1_verified_allowance_usd > 0


def test_one_call_contract_is_fixed_and_cleans_ephemeral_alias(tmp_path: Path) -> None:
    _receipt_path, provider_path = _write_profile_inputs(tmp_path)
    profile = load_deepseek_profile(
        repo_root=tmp_path,
        provider_yaml_path=provider_path,
    )
    client = _Client(_valid_response())
    factory_kwargs: dict[str, Any] = {}

    def factory(**kwargs: Any) -> _Client:
        factory_kwargs.update(kwargs)
        return client

    ticks = iter((10.0, 10.125))
    environment = {"DEEPSEEK-api-key": "test-key-value"}
    result = run_live_capability_specimen(
        profile=profile,
        environment=environment,
        client_factory=factory,
        clock=lambda: next(ticks),
    )
    receipt = result.to_receipt()

    assert result.status == "completed"
    assert result.outcome == "structural_tool_protocol_observed"
    assert CANONICAL_DEEPSEEK_ALIAS not in environment
    assert factory_kwargs == {
        "api_key": "test-key-value",
        "base_url": "https://api.deepseek.com",
        "max_retries": 0,
        "timeout": 15.0,
    }
    assert client.closed is True
    assert client.completions.kwargs is not None
    assert client.completions.kwargs["max_tokens"] == 64
    assert client.completions.kwargs["parallel_tool_calls"] is False
    assert client.completions.kwargs["extra_body"] == {
        "thinking": {"type": "disabled"}
    }
    assert client.completions.kwargs["tool_choice"] == {
        "type": "function",
        "function": {"name": DECLARED_TOOL_NAME},
    }
    assert validate_live_capability_receipt(receipt) == ()
    assert "test-key-value" not in json.dumps(receipt)
    assert "cmpl-not-persisted" not in json.dumps(receipt)


def test_wrong_tool_is_a_one_attempt_block_and_is_never_executed(tmp_path: Path) -> None:
    _receipt_path, provider_path = _write_profile_inputs(tmp_path)
    profile = load_deepseek_profile(
        repo_root=tmp_path,
        provider_yaml_path=provider_path,
    )
    client = _Client(_valid_response(tool_name="wrong_tool"))
    environment = {"DEEPSEEK-api-key": "test-key-value"}

    result = run_live_capability_specimen(
        profile=profile,
        environment=environment,
        client_factory=lambda **_: client,
        clock=lambda: 1.0,
    )

    assert result.status == "blocked"
    assert result.request_count == 1
    assert result.retry_count == 0
    assert result.tool_execution_count == 0
    assert result.engine_invocations == 0
    assert "live.tool_name_invalid" in result.validation_issues
    assert CANONICAL_DEEPSEEK_ALIAS not in environment


def test_missing_alias_stops_before_creating_a_client(tmp_path: Path) -> None:
    _receipt_path, provider_path = _write_profile_inputs(tmp_path)
    profile = load_deepseek_profile(
        repo_root=tmp_path,
        provider_yaml_path=provider_path,
    )
    factory_called = False

    def factory(**_: Any) -> _Client:
        nonlocal factory_called
        factory_called = True
        return _Client(_valid_response())

    result = run_live_capability_specimen(
        profile=profile,
        environment={},
        client_factory=factory,
    )

    assert result.status == "blocked"
    assert result.outcome == "preflight_blocked_no_request"
    assert result.request_count == 0
    assert factory_called is False


def test_legacy_api_env_is_read_for_one_process_and_then_cleared(tmp_path: Path) -> None:
    _receipt_path, provider_path = _write_profile_inputs(tmp_path)
    profile = load_deepseek_profile(
        repo_root=tmp_path,
        provider_yaml_path=provider_path,
    )
    legacy_env = tmp_path / "api.env"
    legacy_env.write_text("DEEPSEEK-api-key=test-key-value\n", encoding="utf-8")
    environment: dict[str, str] = {}

    resolution = preflight_credential_resolution(
        profile=profile,
        environment=environment,
        legacy_env_paths=(legacy_env,),
    )

    assert resolution.source_class == "configured_legacy_api_env_bound_in_process"
    assert resolution.bound_in_process is True
    assert CANONICAL_DEEPSEEK_ALIAS not in environment


def test_receipt_validator_rejects_an_execution_boundary_violation(tmp_path: Path) -> None:
    _receipt_path, provider_path = _write_profile_inputs(tmp_path)
    profile = load_deepseek_profile(
        repo_root=tmp_path,
        provider_yaml_path=provider_path,
    )
    receipt = run_live_capability_specimen(
        profile=profile,
        environment={"DEEPSEEK-api-key": "test-key-value"},
        client_factory=lambda **_: _Client(_valid_response()),
        clock=lambda: 1.0,
    ).to_receipt()
    receipt["non_execution"]["tool_execution_count"] = 1

    assert "live.execution_boundary_violated" in validate_live_capability_receipt(
        receipt
    )


def test_recorded_live_specimen_receipt_validates() -> None:
    root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [
            sys.executable,
            "scripts/review/validate_frontier_live_provider.py",
            "--repo",
            str(root),
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
