"""A handoff refused after its producer validated is the consumer's word.

CUHK r9o-g5 cycle 2 ran an ORCA modred for 19,578 s; it validated, and
the host then refused to hand its structure to the saddle search that
waited on it. The refusal was raised inside the producer's own execution
step before the producer's state was written, so the executor recorded
the node that had run as a launch refusal, the run stayed ``running``,
and the recovery found nothing terminal to read.

A refusal now blocks only the consumer it concerns, under a
``workflow.dependency.`` rule and in the consumer's name, after the
producer's validated state is written; the run outcome reads the
producer as validated and the consumer as a dependency that did not
arrive. Driven through the host's own event store and outcome reader.
"""

from __future__ import annotations

import pytest

from chemsmart.agent._contracts import canonical_data, canonical_sha256
from chemsmart.agent.execution import (
    ProgramResultValidationReceiptV1,
    build_producer_edge_rule,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.terminal_states import (
    derive_run_outcome,
    read_run_events,
)
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from tests.agent.test_scientific_workflow_v2 import _approval, _water_plan

pytestmark = pytest.mark.capability("gate:terminal_state_vocabulary")


def _validation(
    node_id: str, jobtype: str
) -> ProgramResultValidationReceiptV1:
    body = {
        "schema_version": "chemsmart.program-result-validation-receipt.v1",
        "validator_id": "pyscf-result-validator",
        "validator_schema_version": "chemsmart.pyscf-result-validation.v1",
        "validator_version": "1",
        "invocation_sha256": "7" * 64,
        "node_id": node_id,
        "program": "pyscf",
        "engine": "cpu",
        "jobtype": jobtype,
        "input_artifact_sha256": "1" * 64,
        "project_artifact_sha256": "2" * 64,
        "capability_environment_receipt_sha256": "3" * 64,
        "run_environment_receipt_sha256": "",
        "environment_validation_sha256": "",
        "stationary_point_policy_sha256": "",
        "output_artifacts": (),
        "observations": {"state": "validated"},
        "findings": (),
        "state": "valid",
    }
    return ProgramResultValidationReceiptV1(
        **body, receipt_sha256=canonical_sha256(body)
    )


def test_a_refused_handoff_blocks_the_consumer_and_keeps_the_producer(
    tmp_path,
):
    plan = _water_plan()
    _, materialized, approval = _approval(plan)
    events = tmp_path / "events" / "runtime.jsonl"
    store = RuntimeEventStore(events, session_id="water-session")
    store.record_materialized_workflow(turn_id="turn-1", workflow=materialized)
    store.consume_and_start_workflow(
        turn_id="turn-1",
        plan=plan,
        approval=approval,
        run_id="water-run",
        node_id="opt-initial",
        invocation_sha256="7" * 64,
        timestamp="2026-09-24T00:00:00+00:00",
    )
    store.transition_workflow_run_node(
        turn_id="turn-1",
        run_id="water-run",
        node_id="opt-initial",
        new_state="engine_complete",
        execution_receipt_sha256="8" * 64,
        output_artifact_sha256s=("9" * 64,),
        timestamp="2026-09-24T00:00:01+00:00",
    )
    validation = _validation("opt-initial", "opt")
    store.append(
        turn_id="turn-1",
        kind=EventKind.RESULT_VERIFIED.value,
        payload={
            "receipt_sha256": validation.receipt_sha256,
            "status": "valid",
            "critical_finding_count": 0,
            "record": canonical_data(validation),
        },
        idempotency_key="result-validation:" + validation.receipt_sha256,
    )
    store.transition_workflow_run_node(
        turn_id="turn-1",
        run_id="water-run",
        node_id="opt-initial",
        new_state="validated",
        validator_receipt_sha256s=(validation.receipt_sha256,),
        result_validation_receipt=validation,
        timestamp="2026-09-24T00:00:02+00:00",
    )

    host = object.__new__(CommandCompiledToolHostV1)
    host.event_store = store
    edge = build_producer_edge_rule(
        producer_node_id="opt-initial",
        consumer_node_id="hess-optimized",
        artifact_kind="geometry_xyz",
        selection_rule="validated_optimized_geometry",
    )
    host._block_refused_consumers(
        "turn-1",
        run_id="water-run",
        plan=plan,
        refused=((edge, "orca result is not a converged OPT or TS"),),
        timestamp="2026-09-24T00:00:03+00:00",
    )

    rows = {
        row["node_id"]: row
        for row in store.state().workflow_run_records["water-run"]["nodes"]
    }
    assert rows["opt-initial"]["state"] == "validated"
    assert rows["hess-optimized"]["state"] == "blocked"
    assert tuple(rows["hess-optimized"]["failure_rule_ids"]) == (
        "workflow.dependency.handoff_refused.opt-initial",
    )
    refusals = [
        event.payload
        for event in store.read_events()
        if event.kind == EventKind.WORKFLOW_NODE_LAUNCH_REFUSED.value
    ]
    assert [item["node_id"] for item in refusals] == ["hess-optimized"]
    assert "opt-initial" in refusals[0]["reason"]

    outcome = derive_run_outcome(read_run_events(events))
    words = {node.node_id: node.state for node in outcome.nodes}
    assert words["opt-initial"] == "validated"
    assert words["hess-optimized"] == "blocked_dependency"
