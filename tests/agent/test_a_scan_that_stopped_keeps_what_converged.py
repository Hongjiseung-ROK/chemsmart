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
file; a completed scan's steps are its table's rows. Driven on the real
outputs of that goal.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from chemsmart.io.molecules.structure import Molecule
from chemsmart.io.orca.output import ORCAOutput

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
