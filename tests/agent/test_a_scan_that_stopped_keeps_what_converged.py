"""A relaxed scan that stopped early keeps every step that converged.

ORCA prints its surface table only after the last step, so a scan the clock
or an error stopped left no table. The ORCA reader then served no point,
``bind_scan_point_geometry`` answered "records no scan surface", and
``bind_reached_geometry`` refuses every scan by declaration. R10 Q20 G1
(CUHK 2153658) lost 14 and 10 converged points this way -- the second scan's
last one 0.07 A from the saddle the goal then went looking for -- R10 Q4 g1
lost 17 after 18010 s, and two ax41 goals lost 11 and 10.

What is pinned: a step whose constrained optimisation converged is a point,
read from ORCA's own output, and it is a constrained minimum at its held
value; a step that did not converge is not a point even where ORCA wrote its
file; a completed scan's steps are its table's rows; the public binding
carries a converged point of a scan that stopped early and says what the
source was and what the point is; and inspecting such a result shows the
points. Driven on the real outputs of that goal.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from chemsmart.agent._contracts import (
    ContractError,
    TrustedArtifactRefV1,
    file_sha256,
)
from chemsmart.agent.exposure import build_exposure
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.io.molecules.structure import Molecule
from chemsmart.io.orca.output import ORCAOutput
from tests.agent.neutral_workflow_fixture import build_neutral_workflow_fixture

pytestmark = pytest.mark.capability("tool:bind_scan_point_geometry")

_ORCA = Path(__file__).resolve().parents[1] / "data" / "ORCATests"
#: Killed by the node's 3 h limit during step 11 (R10 Q20 G1, cycle 2).
_TIMED_OUT = (
    _ORCA / "scan_stopped_early" / "timeout" / "hx-opt-geom_scan_scan.out"
)
#: Step 1 ran out of optimisation cycles (R10 Q20 G1, cycle 3).
_STEP_FAILED = (
    _ORCA
    / "scan_stopped_early"
    / "step_not_converged"
    / "hx-opt-geom_scan_scan.out"
)
#: A completed 13-point scan (R10 Q7's CLI oracle).
_COMPLETED = _ORCA / "scan_completed" / "h2o2_o_scan.out"


def _host(tmp_path, *results):
    fixture = build_neutral_workflow_fixture(tmp_path / "fixture")
    artifacts = {
        artifact_id: TrustedArtifactRefV1(
            artifact_id=artifact_id,
            kind="orca_output",
            sha256=file_sha256(path),
            size_bytes=path.stat().st_size,
            path=str(path),
            cli_value=str(path),
        )
        for artifact_id, path in results
    }
    inputs = dict(fixture.host_inputs)
    inputs["artifacts"] = {**inputs["artifacts"], **artifacts}
    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events" / "runtime.jsonl", session_id="session"
        ),
        task_spec_sha256s=(fixture.public_context.task_spec_sha256,),
        approved_workspace=tmp_path / "workspace",
        exposure=build_exposure("host_search").with_pinned(
            (
                "bind_scan_point_geometry",
                "bind_reached_geometry",
                "inspect_run",
            )
        ),
        **inputs,
    )


def test_each_step_that_converged_before_the_clock_is_a_point():
    output = ORCAOutput(str(_TIMED_OUT))
    points = output.scan_points_converged

    # ORCA printed no table: the completed-surface readers see nothing.
    assert output.scan_profile == ()
    assert output.scan_point_records == ()
    assert output.scan_step_count == 11
    assert [point["index"] for point in points] == list(range(1, 11))
    assert points[0]["coordinate"] == pytest.approx(4.5)
    assert points[-1]["coordinate"] == pytest.approx(2.325)
    # The final evaluation of each converged step, as ORCA printed it.
    assert points[0]["energy"] == pytest.approx(-233.503525042464, abs=1e-12)
    assert points[-1]["energy"] == pytest.approx(-233.464021633484, abs=1e-12)
    for point in points:
        # A converged step's file is the structure ORCA printed at its
        # final evaluation, and the driven C1...C6 distance is the held
        # value: a constrained minimum at that value.
        written = Molecule.from_filepath(point["geometry_file"])
        assert list(written.chemical_symbols) == list(
            point["structure"].chemical_symbols
        )
        assert np.allclose(
            written.positions, point["structure"].positions, atol=1e-6
        )
        held = np.linalg.norm(
            np.asarray(point["structure"].positions[0])
            - np.asarray(point["structure"].positions[5])
        )
        assert held == pytest.approx(point["coordinate"], abs=1e-3)


def test_a_step_that_ran_out_of_cycles_is_not_a_point_though_its_file_is_there():
    output = ORCAOutput(str(_STEP_FAILED))

    assert output.scan_step_count == 1
    assert _STEP_FAILED.with_name("hx-opt-geom_scan_scan.001.xyz").is_file()
    assert output.scan_points_converged == ()


def test_a_completed_scan_read_step_by_step_is_its_own_table():
    output = ORCAOutput(str(_COMPLETED))
    table = output.scan_point_records
    points = output.scan_points_converged

    assert len(table) == len(points) == 13
    for row, point in zip(table, points):
        assert point["index"] == row["index"]
        assert point["coordinate"] == pytest.approx(
            row["coordinate"], abs=1e-6
        )
        assert point["energy"] == pytest.approx(row["energy"], abs=5e-8)
        assert point["geometry_file"] == row["geometry_file"]


@pytest.mark.capability("rule:recovery.scan_points_that_converged")
def test_a_converged_point_of_a_scan_the_clock_stopped_binds(tmp_path):
    host = _host(tmp_path, ("orca-result-scan-r2", _TIMED_OUT))

    reply = host.dispatch(
        turn_id="turn-1",
        tool_name="bind_scan_point_geometry",
        arguments={
            "artifact_id": "orca-result-scan-r2",
            "point_index": 10,
            "program": "orca",
        },
    )

    assert reply["status"] == "ok", reply
    result = reply["result"]
    assert result["point_index"] == 10
    assert result["coordinate"] == pytest.approx(2.325)
    assert result["energy_hartree"] == pytest.approx(-233.464021633484)
    # The source keeps its ending and the point says what it is.
    assert result["source_normal_termination"] is False
    stopped = result["scan_stopped_early"]
    assert stopped["steps_started"] == 11
    assert stopped["points_planned"] == 13
    assert stopped["converged_steps"] == list(range(1, 11))
    assert "constrained minimum" in result["point_is"]
    assert "not a saddle" in result["point_is"]
    bound = host.artifacts[result["artifact"]["artifact_id"]]
    expected = ORCAOutput(str(_TIMED_OUT)).scan_points_converged[-1]
    carried = Molecule.from_filepath(bound.path)
    assert np.allclose(
        carried.positions, expected["structure"].positions, atol=1e-6
    )


def test_a_step_the_scan_did_not_finish_is_refused_with_the_steps_that_did(
    tmp_path,
):
    host = _host(
        tmp_path,
        ("orca-result-scan-r2", _TIMED_OUT),
        ("orca-result-scan-r3", _STEP_FAILED),
    )

    with pytest.raises(ContractError, match=r"converged are 1-10.*step 11"):
        host.dispatch(
            turn_id="turn-1",
            tool_name="bind_scan_point_geometry",
            arguments={
                "artifact_id": "orca-result-scan-r2",
                "point_index": 11,
                "program": "orca",
            },
        )
    with pytest.raises(ContractError, match="no step converged"):
        host.dispatch(
            turn_id="turn-1",
            tool_name="bind_scan_point_geometry",
            arguments={
                "artifact_id": "orca-result-scan-r3",
                "point_index": 1,
                "program": "orca",
            },
        )


def test_the_reached_structure_refusal_names_the_route_a_scan_has(tmp_path):
    """What R10 Q20 G1's cycle 3 met twice, on these bytes: a refusal that
    named single points and Hessians and no route a scan has."""

    host = _host(tmp_path, ("orca-result-99fd69768f6248ea", _TIMED_OUT))

    with pytest.raises(ContractError) as refused:
        host.dispatch(
            turn_id="turn-1",
            tool_name="bind_reached_geometry",
            arguments={
                "artifact_id": "orca-result-99fd69768f6248ea",
                "reached_artifact_id": "geometry-scan-r2-reached",
                "program": "orca",
            },
        )

    message = str(refused.value)
    assert "'as_reached'" in message
    assert "bind_scan_point_geometry" in message
    assert "inspect_run" in message


def test_inspecting_a_scan_that_stopped_early_shows_its_converged_points(
    tmp_path,
):
    host = _host(tmp_path, ("orca-result-scan-r2", _TIMED_OUT))

    reply = host.dispatch(
        turn_id="turn-1",
        tool_name="inspect_run",
        arguments={"artifact_id": "orca-result-scan-r2", "program": "orca"},
    )

    assert reply["status"] == "ok", reply
    partial = reply["result"]["scan_stopped_early"]
    assert partial["steps_started"] == 11
    assert [row["index"] for row in partial["converged_points"]] == list(
        range(1, 11)
    )
    last = partial["converged_points"][-1]
    assert last["coordinate"] == pytest.approx(2.325)
    assert last["energy_hartree"] == pytest.approx(-233.464021633484)
