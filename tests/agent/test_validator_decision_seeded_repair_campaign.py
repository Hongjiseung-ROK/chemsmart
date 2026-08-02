from __future__ import annotations

from pathlib import Path
from typing import Any

from chemsmart.agent.settings_registry_stress_receipts import (
    canonical_json_sha256,
)
from scripts.harness import run_validator_decision_projection_campaign as v5r2
from scripts.harness import run_validator_decision_seeded_repair_campaign as v5r3


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _binding(case_id: str) -> Any:
    bundle = v5r2.v5.v4.load_registry_v2_bundle(REPOSITORY_ROOT)
    return v5r2.build_validator_decision_case(
        REPOSITORY_ROOT,
        v5r2._case(case_id),
        bundle,
    )


def _request(
    *, ordinal: int, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    return {
        "name": name,
        "request_id": f"request:{ordinal}",
        "arguments": arguments,
        "arguments_sha256": canonical_json_sha256(arguments),
    }


def _outcome(
    *, ordinal: int, name: str, result: dict[str, Any]
) -> dict[str, Any]:
    return {
        "name": name,
        "request_id": f"request:{ordinal}",
        "result": result,
    }


def test_each_seed_changes_exactly_one_submit_field() -> None:
    for fault in v5r3.FAULTS:
        binding = _binding(str(fault["case_id"]))
        correct = v5r3._correct_submit_args(binding)
        seeded = v5r3._seeded_submit_args(binding, fault)
        changed = [field for field in correct if correct[field] != seeded[field]]
        assert changed == [fault["failed_field"]]


def test_seeded_repair_oracle_replays_all_four_fields() -> None:
    for fault in v5r3.FAULTS:
        binding = _binding(str(fault["case_id"]))
        registry = v5r2.build_validator_decision_registry(binding)
        inspect_arguments: dict[str, Any] = {}
        seeded_arguments = v5r3._seeded_submit_args(binding, fault)
        repaired_arguments = v5r3._correct_submit_args(binding)
        inspection = registry.call(
            "inspect_case_validator_decision", inspect_arguments
        )
        rejected = registry.call(
            "submit_validator_decision_plan", seeded_arguments
        )
        accepted = registry.call(
            "submit_validator_decision_plan", repaired_arguments
        )
        requests = [
            _request(
                ordinal=1,
                name="inspect_case_validator_decision",
                arguments=inspect_arguments,
            ),
            _request(
                ordinal=2,
                name="submit_validator_decision_plan",
                arguments=seeded_arguments,
            ),
            _request(
                ordinal=3,
                name="submit_validator_decision_plan",
                arguments=repaired_arguments,
            ),
        ]
        outcomes = [
            _outcome(
                ordinal=1,
                name="inspect_case_validator_decision",
                result=inspection,
            ),
            _outcome(
                ordinal=2,
                name="submit_validator_decision_plan",
                result=rejected,
            ),
            _outcome(
                ordinal=3,
                name="submit_validator_decision_plan",
                result=accepted,
            ),
        ]
        run = {
            "failed_field": fault["failed_field"],
            "counterexample_rule_id": fault["counterexample_rule_id"],
        }
        oracle = v5r3._repair_oracle(
            run=run,
            binding=binding,
            fault=fault,
            requests=requests,
            outcomes=outcomes,
        )
        assert oracle["passed"] is True
        assert all(oracle["checks"].values())


def test_malformed_submit_result_fails_closed_without_crashing() -> None:
    fault = v5r3.FAULTS[0]
    binding = _binding(str(fault["case_id"]))
    registry = v5r2.build_validator_decision_registry(binding)
    inspection = registry.call("inspect_case_validator_decision", {})
    repaired_arguments = v5r3._correct_submit_args(binding)
    accepted = registry.call(
        "submit_validator_decision_plan", repaired_arguments
    )
    requests = [
        _request(
            ordinal=1,
            name="inspect_case_validator_decision",
            arguments={},
        ),
        _request(
            ordinal=2,
            name="submit_validator_decision_plan",
            arguments=v5r3._seeded_submit_args(binding, fault),
        ),
        _request(
            ordinal=3,
            name="submit_validator_decision_plan",
            arguments=repaired_arguments,
        ),
    ]
    outcomes = [
        _outcome(
            ordinal=1,
            name="inspect_case_validator_decision",
            result=inspection,
        ),
        _outcome(
            ordinal=2,
            name="submit_validator_decision_plan",
            result={"accepted": False},
        ),
        _outcome(
            ordinal=3,
            name="submit_validator_decision_plan",
            result=accepted,
        ),
    ]
    oracle = v5r3._repair_oracle(
        run={
            "failed_field": fault["failed_field"],
            "counterexample_rule_id": fault["counterexample_rule_id"],
        },
        binding=binding,
        fault=fault,
        requests=requests,
        outcomes=outcomes,
    )
    assert oracle["passed"] is False
    assert oracle["checks"]["all_submit_results_well_formed"] is False


def test_private_seal_uses_v5r3_identity(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    (private_root / "events.jsonl").write_text(
        '{"event":"safe"}\n', encoding="utf-8"
    )
    receipt, manifest, _, _ = v5r3._seal_private_campaign_evidence(
        run_root=private_root,
        campaign_plan_sha256="1" * 64,
        source_binding_sha256="2" * 64,
        secret_values=(),
    )
    assert receipt["campaign_id"] == v5r3.CAMPAIGN_ID
    assert receipt["schema_version"] == (
        "chemsmart.seeded-repair-private-receipt.v1"
    )
    assert manifest.manifest_id == f"{v5r3.CAMPAIGN_ID}:private"
