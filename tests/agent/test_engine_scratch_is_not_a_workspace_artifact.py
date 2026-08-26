"""A crashed engine's intermediates are not user-approved artifacts.

Observed live: a relaxed scan died on its node timeout and left its
per-point geometries in the envelope's scratch root, which the fixture had
placed inside the workspace. The next planning session scanned them as
ordinary workspace geometries, measured one, bound it, and edited it -- a
constrained mid-scan structure entered the evidence chain presenting as a
file the user had placed, with nothing on the review saying where it
really came from.

Scratch is working space, not evidence. Whatever root the envelope
declares for it is barred from every artifact scan: geometry, database,
and each program-result adapter. Completed results under ``nodes/`` keep
their deliberate admission -- they carry termination-validated provenance
through their parsers; scratch never does.
"""

from __future__ import annotations

from pathlib import Path

from chemsmart.agent.live_session import (
    _scan_database_artifacts,
    _scan_orca_result_artifacts,
    _scan_xyz_artifacts,
)

_WATER = "3\nwater\nO 0.0 0.0 0.117\nH 0.0 0.757 -0.470\nH 0.0 -0.757 -0.470\n"

#: A mid-scan constrained point: same species, different coordinates, so it
#: carries its own content digest instead of deduplicating into the input.
_SCAN_POINT = (
    "3\nscan point 001\n"
    "O 0.0 0.0 0.200\nH 0.0 0.900 -0.400\nH 0.0 -0.900 -0.400\n"
)


def _workspace_with_scratch(tmp_path) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    scratch = workspace / "scratch" / "some-scan_scan"
    scratch.mkdir(parents=True)
    (workspace / "supplied.xyz").write_text(_WATER)
    (scratch / "some-scan_scan.001.xyz").write_text(_SCAN_POINT)
    return workspace, workspace / "scratch"


def test_a_scratch_geometry_is_not_scanned(tmp_path):
    workspace, scratch_root = _workspace_with_scratch(tmp_path)

    admitted = _scan_xyz_artifacts(workspace, (scratch_root.resolve(),))
    names = [Path(item.artifact.path).name for item in admitted]
    assert names == ["supplied.xyz"]

    # Without the exclusion the leak reproduces, which is what made this a
    # live defect rather than a hypothetical: the scan point presents as a
    # user-placed file.
    unguarded = _scan_xyz_artifacts(workspace)
    assert len(unguarded) == 2


def test_scratch_results_and_databases_are_not_scanned(tmp_path):
    workspace = tmp_path / "workspace"
    scratch = workspace / "scratch"
    scratch.mkdir(parents=True)
    (scratch / "leftover.out").write_text("not a result\n")
    (scratch / "leftover.db").write_text("not a database\n")

    barred = (scratch.resolve(),)
    assert _scan_orca_result_artifacts(workspace, barred) == ()
    assert _scan_database_artifacts(workspace, barred) == ()
