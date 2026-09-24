"""A point of a completed Gaussian scan can be carried forward.

The scan-point binding read ``geometry_file`` off every scan record, a
field only ORCA's reader writes (ORCA leaves one file per point). A
Gaussian record held only ``index``, so binding any point of a Gaussian
surface raised ``KeyError: 'geometry_file'`` -- the route the relaxed-scan
guide names for "any other point" was a dead end for Gaussian (R10 Q7 G2,
CUHK 2150187, followed the guide into it).

A Gaussian record now carries the fields ORCA's does, with the structure
the log converged at that point, and the host writes that structure as
an ordinary trusted geometry. Driven through the public tool on an
archived real Gaussian scan log.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.exposure import build_exposure
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.io.gaussian.output import Gaussian16Output
from chemsmart.io.molecules.structure import Molecule
from tests.agent.neutral_workflow_fixture import build_neutral_workflow_fixture

pytestmark = pytest.mark.capability("tool:bind_scan_point_geometry")

_SCAN = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "GaussianTests"
    / "outputs"
    / "cationic_failed_scan.log"
)


def test_a_point_of_a_gaussian_surface_binds_as_a_geometry(tmp_path):
    fixture = build_neutral_workflow_fixture(tmp_path / "fixture")
    scan = TrustedArtifactRefV1(
        artifact_id="gaussian-scan-result",
        kind="gaussian_output",
        sha256=file_sha256(_SCAN),
        size_bytes=_SCAN.stat().st_size,
        path=str(_SCAN),
        cli_value=str(_SCAN),
    )
    inputs = dict(fixture.host_inputs)
    inputs["artifacts"] = {**inputs["artifacts"], scan.artifact_id: scan}
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events" / "runtime.jsonl", session_id="session"
        ),
        task_spec_sha256s=(fixture.public_context.task_spec_sha256,),
        approved_workspace=tmp_path / "workspace",
        exposure=build_exposure("host_search").with_pinned(
            ("bind_scan_point_geometry",)
        ),
        **inputs,
    )

    reply = host.dispatch(
        turn_id="turn-1",
        tool_name="bind_scan_point_geometry",
        arguments={
            "artifact_id": scan.artifact_id,
            "point_index": 1,
            "program": "gaussian",
        },
    )

    assert reply["status"] == "ok", reply
    result = reply["result"]
    assert result["point_index"] == 1
    assert result["coordinate"] == pytest.approx(2.596054, abs=1e-6)
    assert result["energy_hartree"] == pytest.approx(-2630.89252367)
    bound_id = result["artifact"]["artifact_id"]
    assert bound_id == "gaussian-scan-result.point.001"
    written = Path(host.artifacts[bound_id].path)
    assert written.is_file()
    bound = Molecule.from_filepath(str(written))
    converged = Gaussian16Output(str(_SCAN)).all_structures[0]
    assert list(bound.chemical_symbols) == list(converged.chemical_symbols)
    assert bound.positions == pytest.approx(converged.positions, abs=1e-9)
