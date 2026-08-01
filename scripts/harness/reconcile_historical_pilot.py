#!/usr/bin/env python3
"""Create a deterministic M0 reconciliation receipt for a paper pilot tree."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from chemsmart.agent.experiment_reconciliation import reconcile_experiment_files


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def reconcile_tree(root: Path) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    for public_path in sorted(root.glob("deepseek-v4-flash-*/public-receipt.json")):
        run_id = public_path.parent.name
        event_paths = sorted(
            public_path.parent.glob(
                "private/sessions/*/*/runtime_events.jsonl"
            )
        )
        for event_path in event_paths:
            case_id = event_path.parents[1].name
            receipt = reconcile_experiment_files(
                runtime_events_path=event_path,
                public_source_path=public_path,
                case_id=case_id,
            )
            mismatch_class = "none"
            if receipt.mismatches:
                mismatch_class = (
                    "false_completed"
                    if receipt.public_turn_outcome == "completed"
                    and receipt.terminal.outcome.value == "turn_blocked"
                    else "terminal_label_disagreement"
                )
            observations.append(
                {
                    "run_id": run_id,
                    "case_id": case_id,
                    "runtime_events_sha256": receipt.runtime_events_sha256,
                    "public_source_sha256": receipt.public_source_sha256,
                    "reconciliation_receipt_sha256": receipt.receipt_sha256,
                    "authoritative_turn_outcome": receipt.terminal.outcome.value,
                    "authoritative_rule_ids": list(receipt.terminal.rule_ids),
                    "public_turn_outcome": receipt.public_turn_outcome,
                    "tool_domain_outcome": (
                        receipt.outcome_classification.tool_domain_outcome.value
                    ),
                    "scientific_readiness": (
                        receipt.outcome_classification.scientific_readiness.value
                    ),
                    "mismatch_class": mismatch_class,
                    "mismatch_rule_ids": [
                        item.rule_id.value for item in receipt.mismatches
                    ],
                }
            )

    if not observations:
        raise ValueError("pilot root contains no Runtime V2 streams")
    terminal_counts = Counter(
        item["authoritative_turn_outcome"] for item in observations
    )
    mismatch_counts = Counter(item["mismatch_class"] for item in observations)
    false_completed = [
        item for item in observations if item["mismatch_class"] == "false_completed"
    ]
    false_completed_rules = sorted(
        {
            rule_id
            for item in false_completed
            for rule_id in item["authoritative_rule_ids"]
        }
    )
    body: dict[str, Any] = {
        "schema_version": "chemsmart.historical-pilot-reconciliation.v1",
        "evidence_scope": "azide-allene-deepseek-v4-flash-2026-08-01",
        "authority": "runtime_v2_terminal_event",
        "retired_metric": "public_terminal_outcome_completed_as_success",
        "stream_count": len(observations),
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "terminal_label_disagreement_count": (
            mismatch_counts["false_completed"]
            + mismatch_counts["terminal_label_disagreement"]
        ),
        "false_completed_count": mismatch_counts["false_completed"],
        "false_completed_unique_blocker_rule_count": len(false_completed_rules),
        "false_completed_unique_blocker_rule_ids": false_completed_rules,
        "chemistry_engine_calls": 0,
        "hpc_calls": 0,
        "historical_evidence_mutated": False,
        "observations": observations,
    }
    body["receipt_sha256"] = _sha256_json(body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = reconcile_tree(args.pilot_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output.exists() and args.output.read_text(encoding="utf-8") != rendered:
        raise RuntimeError("refusing to overwrite a different reconciliation receipt")
    args.output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "receipt_sha256": receipt["receipt_sha256"],
                "stream_count": receipt["stream_count"],
                "terminal_label_disagreement_count": receipt[
                    "terminal_label_disagreement_count"
                ],
                "false_completed_count": receipt["false_completed_count"],
                "false_completed_unique_blocker_rule_count": receipt[
                    "false_completed_unique_blocker_rule_count"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
