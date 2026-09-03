"""A decision cites an anomaly by the digest of the receipt the host minted.

The model's reading of a surprise is prose beside a cited receipt, never
a record of its own: an anomaly:<sha256> evidence reference resolves
only to an observation this host recorded or an earlier cycle handed
down, so nothing enters the decision that no receipt backs.
"""

import pytest

from chemsmart.agent._contracts import ContractError, canonical_sha256
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1


def _decision(task_sha256: str, reference: str) -> dict:
    return {
        "decision_id": "saddle-is-the-finding",
        "task_spec_sha256": task_sha256,
        "assumptions": ["The planar structure is the inversion saddle."],
        "method_rationale": "The anomaly names the mode and its atoms.",
        "alternatives": [],
        "uncertainties": ["The barrier lies below the zero-point level."],
        "diagnostics": [],
        "stage_order": ["opt"],
        "evidence_refs": [reference],
    }


@pytest.mark.capability("tool:record_scientific_decision")
def test_an_anomaly_reference_resolves_to_a_recorded_receipt(tmp_path):
    task_sha256 = canonical_sha256("anomaly-task")
    known = "a" * 64
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="anomaly"
        ),
        task_spec_sha256s=(task_sha256,),
        prior_anomaly_observations=(
            {
                "receipt_sha256": known,
                "signal_id": "stationary_point.unexpected_order",
                "status": "unreplicated",
                "node_id": "opt-a",
            },
        ),
    )
    result = host.dispatch(
        turn_id="turn-1",
        tool_name="record_scientific_decision",
        arguments=_decision(task_sha256, "anomaly:" + known),
    )
    assert result["status"] == "ok"
    with pytest.raises(ContractError, match="unknown anomaly observation"):
        host.dispatch(
            turn_id="turn-2",
            tool_name="record_scientific_decision",
            arguments=_decision(task_sha256, "anomaly:" + "b" * 64),
        )
