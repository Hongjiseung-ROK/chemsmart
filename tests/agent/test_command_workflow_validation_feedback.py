from __future__ import annotations

import json

from chemsmart.agent.command_workflow_tools import synthesize_command


def test_invalid_typed_contract_returns_bounded_field_local_feedback() -> None:
    result = synthesize_command(
        {
            "task_spec_id": "task-invalid",
            "molecule_id": "molecule",
            "post_execution_validation_obligations": [
                "frequency:exactly-one-imaginary-mode"
            ],
        },
        {},
    )

    assert result["status"] == "needs_clarification"
    assert result["rule_ids"][0] == "cmd.ir.invalid_typed_contract"
    details = result["counterexamples"][1:]
    assert details
    assert len(details) <= 5
    assert all(item["failed_field"] != "typed_payload" for item in details)
    assert all(item["rule_id"].startswith("cmd.ir.contract.") for item in details)


def test_invalid_contract_feedback_never_echoes_rejected_input() -> None:
    secret_like_model_input = "DO-NOT-ECHO-MODEL-PAYLOAD-72819"
    result = synthesize_command(
        {
            "task_spec_id": "task-invalid",
            "molecule_id": "molecule",
            "unexpected": secret_like_model_input,
        },
        {},
    )

    assert secret_like_model_input not in json.dumps(result)
