#!/usr/bin/env python3
"""Verify and reconcile an immutable settings-by-knowledge campaign receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.settings_knowledge_ablation import (
    SettingsKnowledgeRunOutcomeV2,
)
from chemsmart.agent.settings_knowledge_experiment import (
    case_by_id,
    grade_settings_plan,
)


SCHEMA_VERSION = "chemsmart.settings-knowledge-campaign-reconciliation.v1"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _without(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    return {item_key: value for item_key, value in mapping.items() if item_key != key}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return payload


def _event_index(root: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for path in sorted(root.rglob("runtime_events.jsonl")):
        digest = _sha256_bytes(path.read_bytes())
        index.setdefault(digest, []).append(path)
    return index


def _usage(
    *,
    offered: bool,
    tool_name: str,
    trace: dict[str, Any],
) -> dict[str, Any]:
    requests = trace.get("tool_requests") or []
    outcomes = trace.get("tool_outcomes") or []
    return {
        "offered": offered,
        "requested": sum(item.get("name") == tool_name for item in requests),
        "succeeded": sum(
            item.get("name") == tool_name and item.get("status") == "ok"
            for item in outcomes
        ),
    }


def reconcile(
    *,
    repository_root: Path,
    campaign_receipt: Path,
    private_events_root: Path,
) -> dict[str, Any]:
    raw_bytes = campaign_receipt.read_bytes()
    raw = _load_json(campaign_receipt)
    embedded_receipt_sha256 = str(raw.get("receipt_sha256") or "")
    event_index = _event_index(private_events_root)
    reconciled_runs: list[dict[str, Any]] = []

    for item in raw.get("results") or []:
        case_id = str(item["case_id"])
        arm = str(item["arm"])
        stem = f"{case_id}-{arm}"
        response_path = repository_root / item["outcome"]["sanitized_response_path"]
        trace_path = campaign_receipt.parent / "tool-traces" / f"{stem}.json"
        response_bytes = response_path.read_bytes()
        trace_bytes = trace_path.read_bytes()
        response = _load_json(response_path)
        trace = _load_json(trace_path)
        case = case_by_id(case_id)
        regrade = grade_settings_plan(
            case,
            response.get("typed_proposal"),
            str(response.get("assistant_text") or ""),
        )
        exposure = item["run_spec"]["exposure"]
        event_digest = str(item["authoritative_terminal"]["event_log_sha256"])
        event_paths = event_index.get(event_digest, [])
        replay_verified = False
        event_count = 0
        terminal_kinds: list[str] = []
        if len(event_paths) == 1:
            events = RuntimeEventStore(event_paths[0]).load()
            event_count = len(events)
            terminal_kinds = [
                event.kind.value
                for event in events
                if event.kind.value
                in {"turn_completed", "turn_blocked", "turn_failed"}
            ]
            replay_verified = len(terminal_kinds) == 1

        run_without_hash = _without(item, "run_record_sha256")
        outcome_valid = True
        try:
            SettingsKnowledgeRunOutcomeV2.model_validate(item["outcome"])
        except Exception:
            outcome_valid = False
        raw_failed = sorted(item["grade"].get("failed_oracle_ids") or [])
        regraded_failed = sorted(regrade.get("failed_oracle_ids") or [])
        reconciled_runs.append(
            {
                "run_id": item["run_spec"]["run_id"],
                "case_id": case_id,
                "arm": arm,
                "public_artifacts": {
                    "response_path": str(response_path.relative_to(repository_root)),
                    "tool_trace_path": str(trace_path.relative_to(repository_root)),
                },
                "run_record_integrity": (
                    item.get("run_record_sha256") == _sha256_json(run_without_hash)
                ),
                "outcome_integrity": outcome_valid,
                "response_integrity": (
                    item["outcome"]["sanitized_response_sha256"]
                    == _sha256_bytes(response_bytes)
                ),
                "trace_integrity": (
                    item["outcome"]["public_tool_trace_sha256"]
                    == _sha256_bytes(trace_bytes)
                ),
                "event_integrity": {
                    "matching_private_artifact_count": len(event_paths),
                    "event_count": event_count,
                    "terminal_kinds": terminal_kinds,
                    "hash_chain_replay_verified": replay_verified,
                    "event_log_sha256": event_digest,
                },
                "corrected_exposure_use": {
                    "scientific_settings_registry": _usage(
                        offered=bool(exposure["scientific_settings_registry"]),
                        tool_name="inspect_case_settings",
                        trace=trace,
                    ),
                    "domain_knowledge_packs": _usage(
                        offered=bool(exposure["domain_knowledge_packs"]),
                        tool_name="inspect_case_knowledge",
                        trace=trace,
                    ),
                },
                "readiness": regrade.get("details", {}).get("readiness"),
                "raw_and_regraded_oracle_sets_match": raw_failed == regraded_failed,
                "oracle_passed": bool(regrade.get("oracle_passed")),
                "failed_oracle_ids": regraded_failed,
                "explicit_setting_fields": len(case.expected_settings),
                "explicit_setting_fields_correct": (
                    len(case.expected_settings)
                    - sum(
                        rule_id.startswith("oracle.setting.")
                        for rule_id in regraded_failed
                    )
                ),
                "project_loader_passed": (
                    "oracle.project-loader-valid" not in regraded_failed
                ),
                "project_semantic_equivalence_passed": (
                    "oracle.project-semantic-equivalence" not in regraded_failed
                ),
                "transport_attempts": int(item["outcome"]["transport_attempts"]),
                "input_tokens": int(item["outcome"]["input_tokens"]),
                "output_tokens": int(item["outcome"]["output_tokens"]),
                "wall_time_ms": int(item["outcome"]["wall_time_ms"]),
                "observed_model": item["outcome"].get("observed_model"),
                "reasoning_continuation_observed": bool(
                    item["provider"].get("reasoning_continuation_observed")
                ),
            }
        )

    by_arm: dict[str, dict[str, int]] = {}
    for arm in ("S0K0", "S1K0", "S0K1", "S1K1"):
        selected = [item for item in reconciled_runs if item["arm"] == arm]
        by_arm[arm] = {
            "runs": len(selected),
            "oracle_passes": sum(int(item["oracle_passed"]) for item in selected),
            "false_ready": sum(
                int((item.get("readiness") or {}).get("classification") == "false_ready")
                for item in selected
            ),
            "false_block": sum(
                int((item.get("readiness") or {}).get("classification") == "false_block")
                for item in selected
            ),
            "wrong_block_state": sum(
                int(
                    (item.get("readiness") or {}).get("classification")
                    == "wrong_block_state"
                )
                for item in selected
            ),
            "transport_attempts": sum(item["transport_attempts"] for item in selected),
            "input_tokens": sum(item["input_tokens"] for item in selected),
            "output_tokens": sum(item["output_tokens"] for item in selected),
            "wall_time_ms": sum(item["wall_time_ms"] for item in selected),
        }

    integrity_fields = (
        "run_record_integrity",
        "outcome_integrity",
        "response_integrity",
        "trace_integrity",
        "raw_and_regraded_oracle_sets_match",
    )
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": raw["campaign_id"],
        "classification": "transported_development_ablation_with_additive_metadata_correction",
        "raw_campaign_receipt": {
            "path": str(campaign_receipt.relative_to(repository_root)),
            "file_sha256": _sha256_bytes(raw_bytes),
            "embedded_receipt_sha256": embedded_receipt_sha256,
            "embedded_receipt_integrity": (
                embedded_receipt_sha256
                == _sha256_json(_without(raw, "receipt_sha256"))
            ),
            "mutated": False,
        },
        "corrections": [
            {
                "field": "results[*].exposure_use[*].offered",
                "reason": "runner used a stale preparation-loop exposure value",
                "authority": "run_spec.exposure plus the hashed public tool trace",
            },
            {
                "field": "summary.by_arm[*].false_ready",
                "reason": "the raw summary counted every readiness mismatch as false-ready",
                "authority": "typed proposal plus deterministic registry-derived expected readiness",
            },
        ],
        "private_event_evidence": {
            "git_ignored_locator": str(private_events_root.relative_to(repository_root)),
            "runtime_event_artifacts_indexed": sum(len(paths) for paths in event_index.values()),
            "secret_or_reasoning_content_asserted_public": False,
        },
        "runs": reconciled_runs,
        "summary": {
            "runs": len(reconciled_runs),
            "transport_attempts": sum(item["transport_attempts"] for item in reconciled_runs),
            "oracle_passes": sum(int(item["oracle_passed"]) for item in reconciled_runs),
            "explicit_setting_fields": sum(
                item["explicit_setting_fields"] for item in reconciled_runs
            ),
            "explicit_setting_fields_correct": sum(
                item["explicit_setting_fields_correct"] for item in reconciled_runs
            ),
            "project_loader_passes": sum(
                int(item["project_loader_passed"]) for item in reconciled_runs
            ),
            "project_semantic_equivalence_passes": sum(
                int(item["project_semantic_equivalence_passed"])
                for item in reconciled_runs
            ),
            "by_arm": by_arm,
            "all_public_artifact_and_record_checks_pass": all(
                all(bool(item[field]) for field in integrity_fields)
                for item in reconciled_runs
            ),
            "all_event_hash_chains_replay": all(
                item["event_integrity"]["hash_chain_replay_verified"]
                for item in reconciled_runs
            ),
            "all_observed_models": sorted(
                {
                    str(item["observed_model"])
                    for item in reconciled_runs
                    if item["observed_model"]
                }
            ),
            "reasoning_continuation_runs": sum(
                int(item["reasoning_continuation_observed"])
                for item in reconciled_runs
            ),
        },
        "interpretation_limits": [
            "Three development cases do not establish cross-paper generalization or SOTA.",
            "This campaign prepared project candidates only and executed no chemistry engine.",
            "Knowledge-pack eligibility differed by program and must be stratified.",
            "The raw receipt remains the immutable primary observation; this sidecar owns corrected derived metrics only.",
            "Nine continuation request hashes depend on intentionally ephemeral provider reasoning state and are not exactly reconstructible from public artifacts.",
            "The uncommitted generation source was not content-addressed at campaign start; current-code reconstruction is supporting evidence, not exact source provenance.",
        ],
    }
    receipt["receipt_sha256"] = _sha256_json(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--campaign-receipt", type=Path, required=True)
    parser.add_argument("--private-events-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = reconcile(
        repository_root=args.repository_root.resolve(),
        campaign_receipt=args.campaign_receipt.resolve(),
        private_events_root=args.private_events_root.resolve(),
    )
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "receipt_sha256": receipt["receipt_sha256"],
                "summary": receipt["summary"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
