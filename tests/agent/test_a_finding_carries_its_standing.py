"""A conclusion the Agent reaches keeps its standing to the settlement.

Every value in it is still the host's: a finding is the session's
sentence bound to relations the host evaluated over claims it rendered,
and an observation reaches the word that names it with the receipts it
stands on.
"""

from __future__ import annotations

import json

import pytest

from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

from .test_the_goal_loop_recovers_or_returns import _driver_after_run

pytestmark = pytest.mark.capability("tool:record_scientific_decision")

_TASK = "a" * 64


def _host(events_path, workspace, **kwargs):
    workspace.mkdir(parents=True, exist_ok=True)
    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(events_path, session_id="s1"),
        artifacts={},
        task_spec_sha256s=(_TASK,),
        approved_workspace=workspace,
        **kwargs,
    )


def _literal(host, expression_id, value, unit):
    reply = host.dispatch(
        turn_id="t1",
        tool_name="evaluate_quantity_expression",
        arguments={
            "expression_id": expression_id,
            "inputs": [],
            "nodes": [
                {
                    "node_id": "n1",
                    "operation": "literal",
                    "literal_value": value,
                    "literal_unit": unit,
                }
            ],
            "output_node_ids": ["n1"],
        },
    )
    assert reply["status"] == "ok", reply
    return reply["result"]["receipt_sha256"]


def test_a_diverged_expectation_settles_on_its_own_receipts(tmp_path):
    """r9 g5 (Slurm 2144929) and r8 goal-irc2 delivered every declared
    observable through an approved chain, and the session's own
    pre-registered band diverged from one delivered number. The
    completion carried ``falsified_expectation:...`` and the word became
    achieved_with_observations -- a word that settles on receipts -- and
    the executor's stream holds no decision, so the settlement found no
    evidence, raised, and both goals returned to the human with a
    contract error in place of their delivery."""

    declaration = {
        "observable_id": "ecoplanar-rel-min",
        "unit": "kcal/mol",
        "dimension": (1, 0, 0, 0, 0, 0),
        "meaning": "coplanar-constrained energy above the minimum",
        "expectation_basis": "BINOL racemisation barriers near 9 kcal/mol",
        "expected_sign": "positive",
        "expected_low": 5.0,
        "expected_high": 25.0,
    }
    build = tmp_path / "executor"
    host = _host(
        build / "events.jsonl",
        tmp_path / "executor-workspace",
        approved_requested_observable_declarations=[declaration],
    )
    receipt = _literal(host, "coplanar-gap", 32.05, "kcal/mol")
    host.dispatch(
        turn_id="t1",
        tool_name="record_analysis_claims",
        arguments={
            "task_spec_sha256": _TASK,
            "claims": [
                {
                    "claim_id": "ecoplanar-rel-min",
                    "receipt_sha256": receipt,
                    "quantity_id": "n1",
                    "display_unit": "kcal/mol",
                }
            ],
        },
    )
    # What the provider-free executor records once every approved node
    # validated: the chain's completion over the receipts it produced.
    host._record_toolchain_completion(
        "b" * 64, task_spec_sha256=_TASK, source_receipt_sha256s=(receipt,)
    )
    rows = [
        json.loads(line)
        for line in (build / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert any(
        "falsified_expectation:ecoplanar-rel-min"
        in (row.get("payload") or {}).get("anomaly_output_ids", ())
        for row in rows
    )

    driver = _driver_after_run(tmp_path, calls=1, failed=False, rows=rows)

    settled = driver.ledger.entries()[-1]["payload"]
    assert settled["state"] == "achieved_with_observations", settled
    assert "falsified_expectation:ecoplanar-rel-min" in " ".join(
        settled["reasons"]
    )
    assert settled["evidence"]["receipt_sha256s"]
