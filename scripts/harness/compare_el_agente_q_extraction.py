#!/usr/bin/env python3
"""Regrade El Agente Q extraction receipts with one deterministic oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ACCEPTABLE_CLAIM_LINES: dict[str, dict[str, tuple[int, ...]]] = {
    "architecture_targeted": {
        "elq.architecture.memory": (156, 170, 171, 172, 173),
        "elq.architecture.specialist_hierarchy": (
            176,
            177,
            178,
            179,
            180,
            281,
            285,
        ),
        "elq.architecture.validation_need": (224, 326, 327),
    },
    "failure_targeted": {
        "elq.failure.invalid_orca_keywords": (224,),
        "elq.failure.message_passing_loss": (326,),
        "elq.failure.precondition_checks": (327,),
    },
    "native_input_contrast": {
        "elq.native_input.generation": (182, 188),
        "elq.native_input.repair_loop": (190,),
        "elq.native_input.validation_limit": (224, 327),
    },
    "architecture_full_context": {
        "elq.architecture.memory": (156, 170, 171, 172, 173),
        "elq.architecture.specialist_hierarchy": (
            176,
            177,
            178,
            179,
            180,
            281,
            285,
        ),
        "elq.architecture.validation_need": (224, 326, 327),
    },
    "data_availability": {
        "elq.resource.replication_data": (448,),
    },
}


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _covered_lines(result: object) -> set[int]:
    if not isinstance(result, dict) or result.get("status") != "extracted":
        return set()
    covered: set[int] = set()
    for locator in (result.get("source_evidence") or {}).get("locators") or []:
        if not isinstance(locator, dict):
            continue
        covered.update(
            range(int(locator["start_line"]), int(locator["end_line"]) + 1)
        )
    return covered


def _grade_tool_result(case_id: str, result: object) -> dict[str, Any]:
    expected = ACCEPTABLE_CLAIM_LINES[case_id]
    covered = _covered_lines(result)
    observed_claim_ids = (
        tuple(result.get("claim_ids") or ()) if isinstance(result, dict) else ()
    )
    expected_claim_ids = tuple(sorted(expected))
    claim_line_hits = {
        claim_id: sorted(covered.intersection(lines))
        for claim_id, lines in expected.items()
    }
    missing = sorted(key for key, hits in claim_line_hits.items() if not hits)
    rules = []
    if missing:
        rules.append("experiment.oracle.claim_evidence_missing")
    if observed_claim_ids != expected_claim_ids:
        rules.append("experiment.oracle.claim_id_mismatch")
    return {
        "passed": not rules,
        "claim_line_hits": claim_line_hits,
        "missing_claim_ids": missing,
        "selected_line_count": len(covered),
        "claim_ids_match": observed_claim_ids == expected_claim_ids,
        "rule_ids": rules,
    }


def _grade_case(result: dict[str, Any]) -> dict[str, Any]:
    case_id = result["case_id"]
    outcomes = result.get("tool_outcomes") or []
    grades = [
        _grade_tool_result(case_id, item.get("result"))
        if item.get("status") == "ok"
        else {
            "passed": False,
            "rule_ids": ["experiment.oracle.tool_outcome_not_ok"],
        }
        for item in outcomes
    ]
    passing = [index for index, grade in enumerate(grades) if grade["passed"]]
    observations = (result.get("provider") or {}).get("request_observations") or []
    return {
        "case_id": case_id,
        "pass_at_1": bool(grades and grades[0]["passed"]),
        "bounded_repair_pass": bool(passing),
        "first_passing_tool_index": passing[0] + 1 if passing else None,
        "repair_count_before_pass": passing[0] if passing else None,
        "tool_request_count": len(result.get("tool_requests") or []),
        "transport_attempts": len(observations),
        "input_tokens": sum(int(item.get("input_tokens") or 0) for item in observations),
        "output_tokens": sum(int(item.get("output_tokens") or 0) for item in observations),
        "latency_ms": sum(int(item.get("latency_ms") or 0) for item in observations),
        "reasoning_continuation_observed": bool(
            (result.get("provider") or {}).get("reasoning_continuation_observed")
        ),
        "terminal_kind": (result.get("authoritative_terminal") or {}).get("kind"),
        "tool_grades": grades,
    }


def _campaign(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = [_grade_case(item) for item in payload["results"]]
    if {item["case_id"] for item in cases} != set(ACCEPTABLE_CLAIM_LINES):
        raise ValueError(f"campaign case set is incomplete: {path}")
    return {
        "receipt_path": str(path),
        "receipt_sha256": payload["receipt_sha256"],
        "tool_contract": payload.get("tool_contract", "model_full"),
        "cases": cases,
        "totals": {
            "cases": len(cases),
            "pass_at_1": sum(item["pass_at_1"] for item in cases),
            "bounded_repair_pass": sum(
                item["bounded_repair_pass"] for item in cases
            ),
            "repairs_before_pass": sum(
                int(item["repair_count_before_pass"] or 0) for item in cases
            ),
            "transport_attempts": sum(item["transport_attempts"] for item in cases),
            "input_tokens": sum(item["input_tokens"] for item in cases),
            "output_tokens": sum(item["output_tokens"] for item in cases),
            "latency_ms": sum(item["latency_ms"] for item in cases),
            "reasoning_continuation_cases": sum(
                item["reasoning_continuation_observed"] for item in cases
            ),
        },
        "safety": payload["safety"],
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, int]:
    keys = (
        "pass_at_1",
        "bounded_repair_pass",
        "repairs_before_pass",
        "transport_attempts",
        "input_tokens",
        "output_tokens",
        "latency_ms",
    )
    return {
        key: int(after["totals"][key]) - int(before["totals"][key])
        for key in keys
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--permission-denied", type=Path, required=True)
    parser.add_argument("--model-full", type=Path, required=True)
    parser.add_argument("--host-bound", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    campaigns = {
        "permission_denied": _campaign(args.permission_denied),
        "model_full": _campaign(args.model_full),
        "host_bound": _campaign(args.host_bound),
    }
    host_cases = {
        item["case_id"]: item for item in campaigns["host_bound"]["cases"]
    }
    targeted = host_cases["architecture_targeted"]
    full = host_cases["architecture_full_context"]
    receipt: dict[str, Any] = {
        "schema_version": "chemsmart.el-agente-q-adaptive-comparison.v1",
        "oracle": {
            "kind": "claim-specific-acceptable-source-line-sets",
            "oracle_sha256": _sha256_json(ACCEPTABLE_CLAIM_LINES),
            "pass_at_1_and_bounded_repair_are_separate": True,
        },
        "campaigns": campaigns,
        "contrasts": {
            "read_only_permission_registration": _delta(
                campaigns["model_full"], campaigns["permission_denied"]
            ),
            "host_bound_claim_contract": _delta(
                campaigns["host_bound"], campaigns["model_full"]
            ),
            "host_bound_full_vs_targeted_architecture": {
                "same_oracle_result": (
                    full["pass_at_1"] == targeted["pass_at_1"] is True
                ),
                "input_token_delta": full["input_tokens"] - targeted["input_tokens"],
                "latency_ms_delta": full["latency_ms"] - targeted["latency_ms"],
            },
        },
        "interpretation_limits": [
            "Five extraction cases from one paper are engineering evidence, not a general scientific benchmark.",
            "Provider sampling is not repeated; numerical deltas are descriptive, not inferential.",
            "Line-set oracles verify evidence localization, not the truth of downstream scientific claims.",
        ],
    }
    receipt["receipt_sha256"] = _sha256_json(receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"receipt_sha256": receipt["receipt_sha256"], "contrasts": receipt["contrasts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
