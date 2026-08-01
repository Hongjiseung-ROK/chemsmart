#!/usr/bin/env python3
"""Validate a redacted P3 v2 DeepSeek capability receipt."""

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

from chemsmart.agent.harness.frontier_live_provider_v2 import (  # noqa: E402
    FROZEN_P3_V1_RECEIPT_SHA256,
    validate_live_capability_v2_receipt,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_FIELDS = frozenset({
    "raw_prompt",
    "prompt_text",
    "messages",
    "raw_response",
    "response_text",
    "provider_transcript",
    "tool_arguments",
    "reasoning_content",
    "credential_value",
    "authorization",
    "headers",
    "error_text",
})


def validate(root: Path) -> list[str]:
    """Return deterministic defects for the one immutable v2 observation."""

    errors: list[str] = []
    receipt_path = root / "docs/program/frontier-agent/receipts/p3-live-provider-capability-v2.json"
    schema_path = root / "docs/program/frontier-agent/receipts/p3-live-provider-capability-v2.schema.json"
    p1_path = root / "docs/program/frontier-agent/receipts/p1-api-usage.json"
    v1_path = root / "docs/program/frontier-agent/receipts/p3-live-provider-capability-v1.json"
    receipt = _load_object(receipt_path, errors)
    schema = _load_object(schema_path, errors)
    p1 = _load_object(p1_path, errors)
    if not receipt or not schema or not p1:
        return errors
    if not v1_path.is_file() or _sha256_file(v1_path) != FROZEN_P3_V1_RECEIPT_SHA256:
        errors.append("v2 frozen v1 input hash drift")

    required = schema.get("required_top_level_fields")
    if not isinstance(required, list) or any(not isinstance(key, str) for key in required):
        errors.append("v2 receipt schema required-field list is invalid")
    elif any(key not in receipt for key in required):
        errors.append("v2 receipt lacks a required field")
    errors.extend(validate_live_capability_v2_receipt(receipt))
    if not isinstance(receipt.get("observed_at"), str) or not receipt["observed_at"].endswith("Z"):
        errors.append("v2 receipt observation time is invalid")

    provider = _mapping(receipt.get("provider"), "provider", errors)
    contract = _mapping(receipt.get("contract"), "contract", errors)
    observation = _mapping(receipt.get("observation"), "observation", errors)
    pre_call = _mapping(receipt.get("pre_call_validation"), "pre-call validation", errors)
    if not all((provider, contract, observation, pre_call)):
        return errors
    p1_aliases = _mapping(p1.get("alias_resolution"), "P1 aliases", errors)
    p1_deepseek = _mapping(p1_aliases.get("deepseek"), "P1 DeepSeek", errors)
    if (
        provider.get("model") != "deepseek-v4-pro"
        or provider.get("endpoint_id") != "deepseek.chat.completions.v2"
        or provider.get("configured_base_url_sha256") != p1_deepseek.get("base_url_sha256")
        or provider.get("p1_receipt_sha256") != _sha256_file(p1_path)
        or provider.get("p3_v1_receipt_sha256") != FROZEN_P3_V1_RECEIPT_SHA256
    ):
        errors.append("v2 provider does not match pinned P1/v1 inputs")
    resolution = _mapping(provider.get("credential_resolution"), "credential resolution", errors)
    if (
        resolution.get("canonical_alias") != "DEEPSEEK_API_KEY"
        or resolution.get("bound_in_process") is not True
    ):
        errors.append("v2 credential resolution is not canonical and process-local")

    budget = _mapping(contract.get("declared_budget"), "declared budget", errors)
    expected_budget = {
        "max_model_calls": 1,
        "max_tokens": 256,
        "max_tool_calls": 1,
        "max_tool_executions": 0,
        "max_wall_time_s": 15.0,
        "max_request_bytes": 4096,
        "max_cost_usd": "0.005",
        "estimated_max_cost_usd": "0.00400896",
    }
    if any(budget.get(field) != expected for field, expected in expected_budget.items()):
        errors.append("v2 receipt changed the frozen budget")
    elif (
        not isinstance(budget.get("actual_request_bytes"), int)
        or budget["actual_request_bytes"] > budget["max_request_bytes"]
    ):
        errors.append("v2 receipt exceeds its input-byte ceiling")
    for field in ("prompt_sha256", "tool_schema_sha256", "request_contract_sha256"):
        if not isinstance(contract.get(field), str) or not _SHA256.fullmatch(contract[field]):
            errors.append(f"v2 receipt has invalid {field}")
    if contract.get("v1_to_v2_change") != "max_tokens_64_to_256_only":
        errors.append("v2 receipt lacks its immutable delta declaration")

    if observation.get("request_count") != 1 or observation.get("retry_count") != 0:
        errors.append("v2 receipt must record exactly one request and no retry")
    elapsed_ms = observation.get("elapsed_ms")
    if not isinstance(elapsed_ms, int) or elapsed_ms < 0 or elapsed_ms > 15000:
        errors.append("v2 receipt elapsed time exceeds the ceiling")
    usage = _mapping(observation.get("usage"), "usage", errors)
    if any(
        not isinstance(usage.get(field), int) or usage[field] < 0
        for field in ("prompt_tokens", "completion_tokens", "total_tokens")
    ):
        errors.append("v2 receipt usage is invalid")
    elif (
        usage["completion_tokens"] > 256
        or usage["total_tokens"] < usage["prompt_tokens"] + usage["completion_tokens"]
    ):
        errors.append("v2 receipt usage violates its token ceiling")
    try:
        cost = Decimal(str(observation.get("observed_cost_upper_bound_usd")))
    except (InvalidOperation, ValueError):
        errors.append("v2 receipt cost upper bound is invalid")
    else:
        if cost < 0 or cost > Decimal("0.005"):
            errors.append("v2 receipt cost upper bound exceeds the cap")

    required_pre_call = schema.get("pre_call_validation_fields")
    if not isinstance(required_pre_call, list) or any(key not in pre_call for key in required_pre_call):
        errors.append("v2 pre-call validation is incomplete")
    elif (
        not isinstance(pre_call.get("offline_contract_result"), str)
        or "passed" not in pre_call["offline_contract_result"]
        or pre_call.get("dry_run_outcome") != "no_request_dry_run"
        or pre_call.get("credential_preflight_outcome") != "credential_resolved_no_request"
        or pre_call.get("credential_value_retained") is not False
    ):
        errors.append("v2 pre-call validation is not green and redacted")

    expected_redaction = schema.get("required_redaction_flags")
    if not isinstance(expected_redaction, Mapping) or receipt.get("redaction") != expected_redaction:
        errors.append("v2 receipt redaction boundary is invalid")
    if _contains_forbidden_field(receipt):
        errors.append("v2 receipt retains prohibited raw content")
    _validate_sources(receipt, schema, root, errors)
    if receipt.get("status") == "blocked" and not receipt.get("validation_issues"):
        errors.append("v2 blocked receipt needs a retained red finding")
    return errors


def _validate_sources(
    receipt: Mapping[str, Any], schema: Mapping[str, Any], root: Path, errors: list[str]
) -> None:
    expected = schema.get("required_source_paths")
    artifacts = receipt.get("source_artifacts")
    if not isinstance(expected, list) or not isinstance(artifacts, list):
        errors.append("v2 source-artifact manifest is invalid")
        return
    indexed: dict[str, Mapping[str, Any]] = {}
    for artifact in artifacts:
        if not isinstance(artifact, Mapping) or not isinstance(artifact.get("path"), str):
            errors.append("v2 source artifact is malformed")
            continue
        indexed[artifact["path"]] = artifact
    if set(indexed) != set(expected):
        errors.append("v2 source-artifact coverage drift")
        return
    for relative in expected:
        artifact = indexed[relative]
        digest = artifact.get("sha256")
        target = root / relative
        if (
            not target.is_file()
            or not isinstance(digest, str)
            or not _SHA256.fullmatch(digest)
            or _sha256_file(target) != digest
        ):
            errors.append(f"v2 source artifact drift: {relative}")


def _load_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(f"unreadable JSON artifact: {path.name}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"JSON artifact must be an object: {path.name}")
        return {}
    return value


def _mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"missing mapping: {label}")
        return {}
    return value


def _contains_forbidden_field(value: Any) -> bool:
    if isinstance(value, Mapping):
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
    print("Frontier v2 live-provider receipt validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
