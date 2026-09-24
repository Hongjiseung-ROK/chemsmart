"""A scan runs the range its node states, in every program that scans.

The node's scan is physical -- these atoms, from ``start`` to ``stop`` in
``points`` points -- and the host renders it into each program's idiom.
ORCA takes the range as absolute endpoints. Gaussian takes ``S <steps>
<size>`` and walks from the value the input geometry already has: the R8
human-CLI scan of a hydrogen peroxide at -60 degrees ran -60 .. 120 (CUHK
Slurm 2142374), and a value written on the scan row is no start either --
G16 C.02 read ``D 3 1 2 4 0.0 S 2 15.0`` as ``D 3 1 2 4 0.0000 B`` and ran
a plain optimisation with no scan (CUHK Slurm 2150076). So the same node
ran 0 .. 180 in ORCA and 115 .. 295 in Gaussian from the same geometry,
and the host said nothing. Given the geometry the node runs on, it now
measures the coordinate and refuses a range Gaussian would not run, naming
the edit that makes it runnable.
"""

from __future__ import annotations

import pytest

from chemsmart.agent._contracts import RoutedContractError
from chemsmart.agent.commands import native_coordinate_options

pytestmark = pytest.mark.capability("program_jobtype:gaussian:cpu:scan")

#: Hydrogen peroxide at its torsion of 115.0 degrees, and exactly cis.
_H2O2_115 = (
    "4\nH2O2 near equilibrium\n"
    "O 0.000000 0.000000 0.000000\nO 1.450000 0.000000 0.000000\n"
    "H -0.168400 0.955300 0.000000\nH 1.618400 -0.403700 0.865800\n"
)
_H2O2_CIS = (
    "4\nH2O2 cis\n"
    "O 0.000000 0.000000 0.000000\nO 1.450000 0.000000 0.000000\n"
    "H -0.320000 0.900000 0.000000\nH 1.770000 0.900000 0.000000\n"
)


def _torsion(start=0.0, stop=180.0, points=13):
    return {
        "scan": {
            "kind": "dihedral",
            "atoms": [3, 1, 2, 4],
            "start": start,
            "stop": stop,
            "points": points,
        }
    }


def _geometry(tmp_path, text, name):
    path = tmp_path / f"{name}.xyz"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_start_the_geometry_does_not_have_is_refused_with_the_edit(
    tmp_path,
):
    path = _geometry(tmp_path, _H2O2_115, "h2o2")

    with pytest.raises(RoutedContractError) as refused:
        native_coordinate_options("gaussian", _torsion(), geometry_path=path)

    report = refused.value.failure_report
    assert report["gate"] == "scan.start_is_where_the_geometry_is"
    assert "114.998" in report["diagnosis"]
    assert "set_dihedral" in report["route"]


def test_a_geometry_at_the_start_runs_the_range_it_states(tmp_path):
    path = _geometry(tmp_path, _H2O2_CIS, "cis")

    values = native_coordinate_options(
        "gaussian", _torsion(), geometry_path=path
    )

    assert (values["step_size"], values["num_steps"]) == ("15.0", "12")


def test_a_start_restated_as_the_geometry_s_own_value_is_admitted(tmp_path):
    path = _geometry(tmp_path, _H2O2_115, "h2o2")

    values = native_coordinate_options(
        "gaussian",
        _torsion(start=115.0, stop=295.0),
        geometry_path=path,
    )

    assert values["num_steps"] == "12"


def test_a_torsion_start_is_compared_around_the_circle(tmp_path):
    """180 and -180 degrees are one torsion."""

    path = _geometry(tmp_path, _H2O2_115, "h2o2")

    native_coordinate_options(
        "gaussian",
        _torsion(start=115.0 - 360.0, stop=-65.0),
        geometry_path=path,
    )


def test_a_bond_start_is_held_to_the_bond_the_geometry_has(tmp_path):
    path = _geometry(tmp_path, _H2O2_115, "h2o2")
    stretch = {
        "scan": {
            "kind": "bond",
            "atoms": [1, 2],
            "start": 1.45,
            "stop": 1.65,
            "points": 5,
        }
    }

    native_coordinate_options("gaussian", stretch, geometry_path=path)
    with pytest.raises(RoutedContractError, match="set_bond_length"):
        native_coordinate_options(
            "gaussian",
            {"scan": {**stretch["scan"], "start": 1.40}},
            geometry_path=path,
        )


def test_an_absolute_range_program_is_not_held_to_the_geometry(tmp_path):
    """ORCA's scan sets its own start, so its range runs as stated."""

    path = _geometry(tmp_path, _H2O2_115, "h2o2")

    values = native_coordinate_options("orca", _torsion(), geometry_path=path)

    assert (values["dist_start"], values["dist_end"]) == ("0.0", "180.0")
