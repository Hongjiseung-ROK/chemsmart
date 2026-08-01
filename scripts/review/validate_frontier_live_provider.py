#!/usr/bin/env python3
"""Validate the separate, redacted P3 live-provider capability receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping


_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from chemsmart.agent.harness.frontier_live_provider import (  # noqa: E402
    validate_live_capability_receipt,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_FIELDS = frozenset(
    {
        "raw_prompt",
        "prompt_text",
        "raw_response",
        "response_text",
        "tool_arguments",
        "reasoning_content",
        "credential_value",
        "authorization",
    }
)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    receipt_path = root / "docs/program/frontier-agent/receipts/p3-live-provider-capability-v1.json"
    p1_path = root / "docs/program/frontier-agent/receipts/p1-api-usage.json"
    receipt = _load_object(receipt_path, errors)
    p1 = _load_object(p1_path, errors)
    if not receipt or not p1:
        return errors
    errors.extend(validate_live_capability_receipt(receipt))
    if receipt.get("status") not in {"completed", "blocked"}:
        errors.append("live receipt must be terminal")
    if not isinstance(receipt.get("observed_at"), str):
        errors.append("live receipt needs an observation time")

    provider = _mapping(receipt.get("provider"), "provider", errors)
    contract = _mapping(receipt.get("contract"), "contract", errors)
    observation = _mapping(receipt.get("observation"), "observation", errors)
    redaction = _mapping(receipt.get("redaction"), "redaction", errors)
    phase_close = _mapping(
        receipt.get("phase_close_validation"), "phase-close validation", errors
    )
    if not all((provider, contract, observation, redaction, phase_close)):
        return errors
    p1_aliases = _mapping(p1.get("alias_resolution"), "P1 aliases", errors)
    p1_deepseek = _mapping(p1_aliases.get("deepseek"), "P1 DeepSeek", errors)
    if (
        provider.get("model") != "deepseek-v4-pro"
        or provider.get("returned_model") != provider.get("model")
        or provider.get("endpoint_id") != "deepseek.chat.completions.v1"
        or provider.get("configured_base_url_sha256")
        != p1_deepseek.get("base_url_sha256")
        or provider.get("p1_receipt_sha256") != _sha256_file(p1_path)
    ):
        errors.append("live provider does not match the P1-pinned surface")
    resolution = _mapping(provider.get("credential_resolution"), "credential resolution", errors)
    if (
        resolution.get("canonical_alias") != "DEEPSEEK_API_KEY"
        or resolution.get("bound_in_process") is not True
    ):
        errors.append("live credential resolution is not canonical and process-local")

    budget = _mapping(contract.get("declared_budget"), "declared budget", errors)
    expected_budget = {
        "max_model_calls": 1,
        "max_tokens": 64,
        "max_tool_calls": 1,
        "max_tool_executions": 0,
        "max_wall_time_s": 15.0,
        "max_request_bytes": 4096,
        "max_cost_usd": "0.005",
    }
    if any(budget.get(field) != expected for field, expected in expected_budget.items()):
        errors.append("live receipt changed the frozen budget")
    elif (
        not isinstance(budget.get("actual_request_bytes"), int)
        or budget["actual_request_bytes"] > budget["max_request_bytes"]
    ):
        errors.append("live receipt exceeds its input-byte ceiling")
    if contract.get("thinking_disabled_requested") is not True or contract.get(
        "parallel_tool_calls"
    ) is not False:
        errors.append("live receipt did not pin thinking/tool parallelism")
    for field in ("prompt_sha256", "tool_schema_sha256", "request_contract_sha256"):
        if not isinstance(contract.get(field), str) or not _SHA256.fullmatch(contract[field]):
            errors.append(f"live receipt has invalid {field}")

    if observation.get("request_count") != 1 or observation.get("retry_count") != 0:
        errors.append("live receipt must record exactly one request and no retry")
    elapsed_ms = observation.get("elapsed_ms")
    if not isinstance(elapsed_ms, int) or elapsed_ms < 0 or elapsed_ms > 15000:
        errors.append("live receipt elapsed time is over the frozen ceiling")
    usage = _mapping(observation.get("usage"), "usage", errors)
    if any(
        not isinstance(usage.get(field), int) or usage[field] < 0
        for field in ("prompt_tokens", "completion_tokens", "total_tokens")
    ):
        errors.append("live receipt usage is invalid")
    elif usage["total_tokens"] < usage["prompt_tokens"] + usage["completion_tokens"]:
        errors.append("live receipt usage total is inconsistent")
    try:
        cost = Decimal(str(observation.get("observed_cost_upper_bound_usd")))
    except (InvalidOperation, ValueError):
        errors.append("live receipt cost upper bound is invalid")
    else:
        if cost < 0 or cost > Decimal("0.005"):
            errors.append("live receipt cost upper bound exceeds cap")

    if any(value is not False for value in redaction.values()):
        errors.append("live receipt redaction boundary is invalid")
    if _contains_forbidden_field(receipt):
        errors.append("live receipt retains prohibited raw content")
    issues = receipt.get("validation_issues")
    if not isinstance(issues, list) or not all(isinstance(value, str) and value for value in issues):
        errors.append("live receipt validation findings are invalid")
    if receipt.get("status") == "completed":
        if issues or observation.get("finish_reason") != "tool_calls" or observation.get(
            "arguments_schema_valid"
        ) is not True:
            errors.append("completed live specimen has a red gate")
    elif not issues:
        errors.append("blocked live specimen must preserve its finding")
    if not isinstance(phase_close.get("command"), str) or not isinstance(
        phase_close.get("result"), str
    ) or not isinstance(phase_close.get("validated_at"), str):
        errors.append("live receipt phase-close validation is incomplete")

    artifacts = receipt.get("source_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("live receipt requires pinned source artifacts")
    else:
        for artifact in artifacts:
            if not isinstance(artifact, Mapping):
                errors.append("live source artifact is malformed")
                continue
            relative = artifact.get("path")
            digest = artifact.get("sha256")
            target = root / relative if isinstance(relative, str) else None
            if (
                target is None
                or not target.is_file()
                or not isinstance(digest, str)
                or not _SHA256.fullmatch(digest)
                or _sha256_file(target) != digest
            ):
                errors.append(f"live source artifact drift: {relative}")
    return errors


def _load_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(f"unreadable receipt: {path.name}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"receipt must be an object: {path.name}")
        return {}
    return value


def _mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"live receipt section is missing: {label}")
        return {}
    return value


def _contains_forbidden_field(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key in _FORBIDDEN_FIELDS or _contains_forbidden_field(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_field(item) for item in value)
    return False


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=_ROOT)
    args = parser.parse_args()
    errors = validate(args.repo.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Frontier live-provider receipt validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
