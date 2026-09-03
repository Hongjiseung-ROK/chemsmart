"""A host-detected surprise is a receipt beneath the verdict, never a verdict.

A retrospective audit found twenty-four archived optimisations that
ended on a structural saddle, every one named only as a failure to
repair and none delivered as the stationary point it was. The verdict
still says the run failed its promise; the anomaly observation says,
with the numbers that tripped it, what the structure is. It cites the
validation receipt, moves no state, no finding and no terminal word,
and is never model-authored.
"""

import hashlib
from pathlib import Path

import pytest

from chemsmart.agent._contracts import ContractError, TrustedArtifactRefV1
from chemsmart.agent.execution import (
    build_anomaly_observation,
    build_program_result_validation_receipt,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.runtime.reducer import replay_events
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

_SN2 = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "ORCATests"
    / "outputs"
    / "sn2_ts.out"
)


def _artifact(path: Path) -> TrustedArtifactRefV1:
    return TrustedArtifactRefV1(
        artifact_id="result.sn2",
        kind="orca_output",
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        size_bytes=path.stat().st_size,
        path=str(path.resolve()),
        cli_value=str(path.resolve()),
    )


def _evaluate(jobtype: str):
    return CommandCompiledToolHostV1._evaluate_execution_outputs(
        program="orca",
        jobtype=jobtype,
        charge=-1,
        multiplicity=1,
        output_artifacts=(_artifact(_SN2),),
        exit_status=0,
    )


@pytest.mark.capability("predicate:stationary_point.unexpected_order")
def test_a_saddle_where_a_minimum_was_promised_is_an_observation():
    evaluation = _evaluate("opt")
    assert "result.stationary_point_order" in evaluation.findings
    (anomaly,) = evaluation.anomalies
    assert anomaly["signal_id"] == "stationary_point.unexpected_order"
    assert anomaly["expected_imaginary_modes"] == 0
    assert anomaly["observed_imaginary_modes"] == 1
    assert anomaly["lowest_imaginary_cm1"] < -20.0
    assert anomaly["participating_heavy_atoms"]
    assert 0.0 < anomaly["heavy_atom_share"] <= 1.0


@pytest.mark.capability("predicate:stationary_point.unexpected_order")
def test_a_kept_promise_is_no_anomaly():
    evaluation = _evaluate("ts")
    assert "result.stationary_point_order" not in evaluation.findings
    assert evaluation.anomalies == ()


@pytest.mark.capability("predicate:stationary_point.unexpected_order")
def test_the_verdict_receipt_never_carries_the_anomaly():
    """The validation receipt is built from observations and findings
    alone, so a sensor can never move a verdict or a stored digest."""

    import inspect
    import json

    evaluation = _evaluate("opt")
    assert evaluation.anomalies
    parameters = inspect.signature(
        build_program_result_validation_receipt
    ).parameters
    assert "anomalies" not in parameters
    assert "anomal" not in json.dumps(evaluation.observations).lower()


def test_an_anomaly_cites_its_verdict_and_names_its_status(tmp_path):
    receipt = build_anomaly_observation(
        node_id="opt-a",
        program="orca",
        jobtype="opt",
        signal_id="stationary_point.unexpected_order",
        values={"observed_imaginary_modes": 1, "lowest_imaginary_cm1": -422.6},
        source_receipt_sha256="a" * 64,
    )
    assert receipt.status == "unreplicated"
    with pytest.raises(ContractError, match="status"):
        build_anomaly_observation(
            node_id="opt-a",
            program="orca",
            jobtype="opt",
            signal_id="stationary_point.unexpected_order",
            values={},
            source_receipt_sha256="a" * 64,
            status="believed",
        )
    store = RuntimeEventStore(tmp_path / "events.jsonl", session_id="s")
    store.append(
        turn_id="t1",
        kind=EventKind.ANOMALY_OBSERVED.value,
        payload={
            "receipt_sha256": receipt.receipt_sha256,
            "status": receipt.status,
            "node_id": receipt.node_id,
            "signal_id": receipt.signal_id,
        },
    )
    state = replay_events(store.read_events())
    assert state.anomaly_records == [receipt.receipt_sha256]
