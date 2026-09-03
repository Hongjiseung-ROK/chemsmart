"""The grant investigates an anomaly; it never delivers the deliverable.

The edge rule refuses a tagged node feeding another calculation node. A
probe found what it missed: a tagged LEAF node, whose result the
analysis chain reads and claims, buys the asked observable with the free
line (2026-09-03). Reading an excursion is its whole point -- a
replication receipt needs its numbers -- so the refusal is narrower than
"no analysis may read it": no required output may descend from a tagged
node.
"""

from __future__ import annotations

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from tests.agent.neutral_workflow_fixture import (
    build_neutral_workflow_fixture,
)

_ANOMALY = "f" * 64


def _extraction_node(node_id: str, producer: str, output_id: str) -> dict:
    return {
        "node_id": node_id,
        "analysis_kind": "result_extraction",
        "dependencies": [],
        "inputs": [
            {
                "input_id": "result",
                "source_kind": "program_output",
                "producer_node_id": producer,
                "producer_output_id": "structured_result",
            }
        ],
        "selectors": [{"quantity_id": output_id, "selector": "energy"}],
        "outputs": [
            {
                "output_id": output_id,
                "quantity_kind": "energy",
                "unit": "hartree",
            }
        ],
        "expression_nodes": [],
        "expression_output_node_ids": [],
        "support_state": "planned",
        "blocked_reason": "",
        "validation_rules": [],
    }


def _plan(tmp_path, *, tag_node: str, required: tuple[str, ...], chain):
    fixture = build_neutral_workflow_fixture(tmp_path / "fixture")
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="excursion"
        ),
        task_spec_sha256s=(fixture.public_context.task_spec_sha256,),
        approved_workspace=tmp_path / "preview",
        prior_anomaly_observations=[
            {
                "receipt_sha256": _ANOMALY,
                "signal_id": "geometry.heavy_atom_rmsd_ge_0.3",
                "status": "unreplicated",
                "node_id": "node.opt",
            }
        ],
        **fixture.host_inputs,
    )
    action = next(
        item
        for item in fixture.public_context.next_actions
        if item.tool_name == "plan_scientific_workflow"
    )
    fields = dict(action.fields)
    for node in fields["calculation_nodes"]:
        if node["node_id"] == tag_node:
            node["excursion"] = _ANOMALY
    fields["analysis_nodes"] = list(chain)
    fields["required_output_ids"] = list(required)
    return host.dispatch(
        turn_id="t1", tool_name="plan_scientific_workflow", arguments=fields
    )


@pytest.mark.capability("rule:plan.excursion_grant")
def test_a_required_output_may_not_descend_from_a_tagged_node(tmp_path):
    chain = [_extraction_node("read-hess", "node.hess", "e_total")]
    with pytest.raises(ContractError, match="never produces the asked"):
        _plan(
            tmp_path / "a",
            tag_node="node.hess",
            required=("e_total",),
            chain=chain,
        )


@pytest.mark.capability("rule:plan.excursion_grant")
def test_the_excursion_may_still_be_read(tmp_path):
    """Its numbers are the whole point: an anomaly investigation that
    nothing may extract from could never replicate or refute anything."""

    chain = [
        _extraction_node("read-hess", "node.hess", "probe_energy"),
        _extraction_node("read-opt", "node.opt", "e_total"),
    ]
    assert (
        _plan(
            tmp_path / "b",
            tag_node="node.hess",
            required=("e_total",),
            chain=chain,
        )
        is not None
    )
