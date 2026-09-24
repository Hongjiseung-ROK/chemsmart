"""A quantity a delivered claim carries as its uncertainty was rendered.

The settlement holds a goal open over quantities the host "computed and
never rendered as a claim", because a number no reader can see is not
delivered. It counted every output an expression exported and subtracted
the ones claimed -- and an output a claim carries as its measured
uncertainty is claimed nowhere by id, so it counted as unseen. Two goals
whose completions had passed returned to the human that way: r10/q3 g2
(CUHK Slurm 2152066; the D0 spread, on both headline claims) and r10/q9 g1
(the BDE's 6.0 kJ/mol); eight more had a revision opened for it. Replayed
through the driver's settle step, the base tree reproduces both words
byte for byte.

Driven through the goal loop, with the run's analysis stream built by the
host's own tools.
"""

from __future__ import annotations

import json
import shutil
from types import SimpleNamespace

import pytest

from chemsmart.agent.execution import build_program_execution_receipt
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

from .test_runtime_v2_launch_fence import _reserve
from .test_the_goal_loop_recovers_or_returns import (
    _loop,
    _planning_session,
    _review_payload,
)

_TASK = "a" * 64


def _run_claiming_with_its_spread(tmp_path):
    """A validated run whose chain claims a value with a measured spread.

    The spread is an exported output of its own expression, cited as the
    claim's uncertainty by `<receipt>:<quantity>` exactly as the executor
    writes it for a planned estimator.
    """

    def step(run_directory):
        build = tmp_path / f"build-{run_directory.name}"
        store = RuntimeEventStore(
            build / "events.jsonl", session_id="water-session"
        )
        _, plan, _m, _a, invocation = _reserve(store, build)
        store.record_program_execution_receipt(
            turn_id="turn-1",
            workflow_id=plan.workflow_id,
            run_id="run.water-approval",
            receipt=build_program_execution_receipt(
                invocation,
                execution_state="validated",
                exit_status=0,
                child_exit_status=0,
                engine_complete=True,
                validated=True,
                validator_receipt_sha256s=("e" * 64,),
                result_validation_receipt_sha256="e" * 64,
                started_at="2026-08-04T00:00:00+00:00",
                finished_at="2026-08-04T00:00:05+00:00",
            ),
        )
        host = CommandCompiledToolHostV1(
            event_store=store,
            artifacts={},
            task_spec_sha256s=(_TASK,),
            approved_workspace=build / "ws",
        )

        def literal(expression_id, value):
            reply = host.dispatch(
                turn_id="t1",
                tool_name="evaluate_quantity_expression",
                arguments={
                    "expression_id": expression_id,
                    "inputs": [],
                    "nodes": [
                        {
                            "node_id": expression_id,
                            "operation": "literal",
                            "literal_value": value,
                            "literal_unit": "kJ/mol",
                        }
                    ],
                    "output_node_ids": [expression_id],
                },
            )
            return reply["result"]["receipt_sha256"]

        value = literal("bde-kj", 435.3)
        spread = literal("bde-uncert", 6.0)
        claimed = host.dispatch(
            turn_id="t1",
            tool_name="record_analysis_claims",
            arguments={
                "task_spec_sha256": _TASK,
                "claims": [
                    {
                        "claim_id": "bde-oh-298",
                        "receipt_sha256": value,
                        "quantity_id": "bde-kj",
                        "display_unit": "kJ/mol",
                        "uncertainty": 6.0,
                        "uncertainty_basis": "measured",
                        "uncertainty_reference": f"{spread}:bde-uncert",
                    }
                ],
            },
        )
        assert claimed["status"] == "ok", claimed
        host._record_toolchain_completion(
            "b" * 64,
            task_spec_sha256=_TASK,
            source_receipt_sha256s=(value, spread),
        )
        run_directory.mkdir(parents=True, exist_ok=True)
        shutil.copy(build / "events.jsonl", run_directory / "events.jsonl")
        return SimpleNamespace(status="completed", analysis_status="completed")

    return step


@pytest.mark.capability("tool:record_analysis_claims")
def test_a_spread_on_a_delivered_claim_holds_nothing_open(tmp_path):
    result = _loop(
        tmp_path,
        sessions=[_planning_session("live-1", review=_review_payload())],
        executes=[_run_claiming_with_its_spread(tmp_path)],
        max_revisions=0,
    )
    ledger = (
        tmp_path / "ws" / ".chemsmart-agent" / "goals" / "goal-t1"
    ) / "ledger.jsonl"
    (settled,) = [
        row
        for row in map(json.loads, ledger.read_text().splitlines())
        if row["kind"] == "goal_settled"
    ]
    assert "never rendered as a claim" not in " ".join(
        settled["payload"]["reasons"]
    )
    assert result.settlement in ("achieved", "achieved_with_observations")
