"""Focused offline check for the P3 v2 persisted-receipt validator."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from chemsmart.agent.harness.frontier_live_provider import DeepSeekProfile
from chemsmart.agent.harness.frontier_live_provider_v2 import (
    FROZEN_P3_V1_RECEIPT_SHA256,
    V2Profile,
    run_live_capability_specimen_v2,
)


ROOT = Path(__file__).resolve().parents[3]


class _Response:
    def model_dump(self) -> dict[str, Any]:
        return {
            "id": "fixture-response-id",
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
        }


class _Client:
    def __init__(self) -> None:
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **_kwargs: Any) -> _Response:
        return _Response()

    def close(self) -> None:
        pass


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prepare_receipt_root(tmp_path: Path) -> None:
    schema_path = ROOT / "docs/program/frontier-agent/receipts/p3-live-provider-capability-v2.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for relative in schema["required_source_paths"]:
        source = ROOT / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    receipt_dir = tmp_path / "docs/program/frontier-agent/receipts"
    v1_source = ROOT / "docs/program/frontier-agent/receipts/p3-live-provider-capability-v1.json"
    (receipt_dir / v1_source.name).write_bytes(v1_source.read_bytes())
    base_url = "https://api.deepseek.com"
    p1_path = receipt_dir / "p1-api-usage.json"
    p1_path.write_text(
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
    profile = V2Profile(
        p1_profile=DeepSeekProfile(
            model="deepseek-v4-pro",
            configured_api_key_env="DEEPSEEK-api-key",
            base_url_sha256=hashlib.sha256(base_url.encode()).hexdigest(),
            p1_receipt_sha256=_sha256_file(p1_path),
            p1_observed_at="2026-08-01T00:00:00Z",
            p1_verified_allowance_usd=Decimal("0.82"),
        ),
        p3_v1_receipt_sha256=FROZEN_P3_V1_RECEIPT_SHA256,
    )
    receipt = run_live_capability_specimen_v2(
        profile=profile,
        environment={"DEEPSEEK-api-key": "fixture-only-key"},
        client_factory=lambda **_: _Client(),
        clock=lambda: 1.0,
    )
    receipt["observed_at"] = "2026-08-01T00:00:00Z"
    receipt["source_artifacts"] = [
        {"path": relative, "sha256": _sha256_file(tmp_path / relative)}
        for relative in schema["required_source_paths"]
    ]
    receipt["pre_call_validation"] = {
        "offline_contract_result": "10 passed in fixture-only validation",
        "dry_run_outcome": "no_request_dry_run",
        "credential_preflight_outcome": "credential_resolved_no_request",
        "credential_value_retained": False,
    }
    (receipt_dir / "p3-live-provider-capability-v2.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def test_v2_receipt_validator_accepts_only_the_redacted_pinned_shape(tmp_path: Path) -> None:
    _prepare_receipt_root(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/review/validate_frontier_live_provider_v2.py"),
            "--repo",
            str(tmp_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_v2_receipt_validator_rejects_a_retained_credential_flag(tmp_path: Path) -> None:
    _prepare_receipt_root(tmp_path)
    receipt_path = tmp_path / "docs/program/frontier-agent/receipts/p3-live-provider-capability-v2.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["redaction"]["credentials_retained"] = True
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/review/validate_frontier_live_provider_v2.py"),
            "--repo",
            str(tmp_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "redaction" in result.stdout
