#!/usr/bin/env python3
"""Build a public failure taxonomy receipt from adaptive campaign evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from chemsmart.agent.experiment_failures import (
    FailureCategory,
    FailureDisposition,
    FailureObservationV1,
    FailureSeverity,
    FailureStage,
    Recoverability,
    summarize_failures,
)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _observation(**values: Any) -> FailureObservationV1:
    return FailureObservationV1.model_validate(values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--permission-run", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--coordinates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    reconciliation = _read(args.reconciliation)
    permission = _read(args.permission_run)
    comparison = _read(args.comparison)
    coordinates = _read(args.coordinates)
    observations: list[FailureObservationV1] = []

    for index, item in enumerate(
        (
            value
            for value in reconciliation["observations"]
            if value["mismatch_class"] == "false_completed"
        ),
        1,
    ):
        observations.append(
            _observation(
                observation_id=f"failure.false-terminal.{index}",
                run_id=item["run_id"],
                case_id=item["case_id"],
                rule_id=item["authoritative_rule_ids"][0],
                category=FailureCategory.FALSE_TERMINAL,
                stage=FailureStage.TERMINAL,
                severity=FailureSeverity.CRITICAL,
                disposition=FailureDisposition.ARCHITECTURAL_CHANGE,
                recoverability=Recoverability.CAPABILITY_CHANGE_REQUIRED,
                evidence_sha256=item["runtime_events_sha256"],
                recovered=False,
            )
        )

    for index, item in enumerate(permission["results"], 1):
        observations.append(
            _observation(
                observation_id=f"failure.read-only-permission.{index}",
                run_id="elq-permission-denied",
                case_id=item["case_id"],
                rule_id="runtime.permission.read-only-tool-unregistered",
                category=FailureCategory.PROVIDER_OR_CONTEXT,
                stage=FailureStage.PROVIDER,
                severity=FailureSeverity.ERROR,
                disposition=FailureDisposition.REPAIR,
                recoverability=Recoverability.IMMEDIATE,
                evidence_sha256=item["authoritative_terminal"]["event_log_sha256"],
                recovered=True,
                repair_count=1,
            )
        )

    comparison_sha = comparison["receipt_sha256"]
    for index, case_id in enumerate(
        (
            "architecture_targeted",
            "native_input_contrast",
            "architecture_full_context",
        ),
        1,
    ):
        observations.append(
            _observation(
                observation_id=f"failure.retired-oracle.{index}",
                run_id="elq-model-full",
                case_id=case_id,
                rule_id="experiment.metric.exact-line-or-single-outcome-retired",
                category=FailureCategory.CRITIC_ERROR,
                stage=FailureStage.REVIEW,
                severity=FailureSeverity.WARNING,
                disposition=FailureDisposition.REPAIR,
                recoverability=Recoverability.IMMEDIATE,
                evidence_sha256=comparison_sha,
                recovered=True,
                repair_count=1,
            )
        )
    observations.append(
        _observation(
            observation_id="failure.claim-order-repair.1",
            run_id="elq-model-full",
            case_id="architecture_targeted",
            rule_id="paper.claim.claim-ids-invalid",
            category=FailureCategory.PROVIDER_OR_CONTEXT,
            stage=FailureStage.PROVIDER,
            severity=FailureSeverity.WARNING,
            disposition=FailureDisposition.REPAIR,
            recoverability=Recoverability.BOUNDED_REPAIR,
            evidence_sha256=comparison_sha,
            recovered=True,
            repair_count=1,
        )
    )
    observations.append(
        _observation(
            observation_id="failure.full-context-overhead.1",
            run_id="elq-host-bound",
            case_id="architecture_full_context",
            rule_id="experiment.resource.full-context-overhead",
            category=FailureCategory.RESOURCE_OR_REPAIR_LIMIT,
            stage=FailureStage.PROVIDER,
            severity=FailureSeverity.WARNING,
            disposition=FailureDisposition.ARCHITECTURAL_CHANGE,
            recoverability=Recoverability.CAPABILITY_CHANGE_REQUIRED,
            evidence_sha256=comparison_sha,
            recovered=False,
        )
    )

    conflict_assets = [
        item for item in coordinates["assets"] if item["state"] == "blocked_version_conflict"
    ]
    for index, item in enumerate(conflict_assets, 1):
        observations.append(
            _observation(
                observation_id=f"failure.coordinate-version-conflict.{index}",
                run_id="pcp-ttm-coordinate-provenance",
                case_id=f"pcp-ttm-coordinate-{index}",
                rule_id=item["blocker_rule_ids"][0],
                category=FailureCategory.ARTIFACT_OR_PROVENANCE,
                stage=FailureStage.SOURCE,
                severity=FailureSeverity.ERROR,
                disposition=FailureDisposition.BLOCK,
                recoverability=Recoverability.USER_EVIDENCE_REQUIRED,
                evidence_sha256=item["provenance"]["provenance_receipt_sha256"],
                recovered=False,
            )
        )

    canonical = tuple(sorted(observations, key=lambda item: item.observation_id))
    summary = summarize_failures(canonical)
    receipt: dict[str, Any] = {
        "schema_version": "chemsmart.adaptive-failure-analysis.v1",
        "source_receipts": {
            "reconciliation": reconciliation["receipt_sha256"],
            "permission_run": permission["receipt_sha256"],
            "comparison": comparison["receipt_sha256"],
            "coordinates": coordinates["receipt_sha256"],
        },
        "observations": [item.model_dump(mode="json") for item in canonical],
        "summary": summary.model_dump(mode="json"),
        "interpretation": {
            "confirmed_facts": [
                "Historical public completed labels disagreed with blocked Runtime V2 terminals in four observations.",
                "A static read-only allowlist denied five otherwise valid evidence tool requests.",
                "Two official coordinate files diverged between Zenodo versions and were blocked.",
            ],
            "supported_interpretations": [
                "Host-bound claim contracts remove avoidable model-controlled fields.",
                "Targeted evidence windows can preserve this oracle result with substantially lower context use.",
            ],
            "unverified_hypotheses": [
                "The observed gains generalize beyond one paper and seeded evidence cases.",
                "Three independent critics meet the preregistered recall and false-rejection gates.",
            ],
            "known_unknowns": [
                "Which divergent coordinate version matches the exact paper analysis.",
                "Whether ten strict PRP-10 papers can be source-complete without relaxing eligibility.",
            ],
            "retired_metrics": [
                "Public completed as a success metric.",
                "One exact source line per claim when equivalent evidence exists elsewhere.",
                "Exactly one tool outcome as the only success metric; pass_at_1 and bounded repair are separate.",
            ],
        },
    }
    receipt["receipt_sha256"] = _sha_json(receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt["receipt_sha256"],
                "observations": len(canonical),
                "highest_value_categories": [
                    item.value for item in summary.highest_value_categories
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
