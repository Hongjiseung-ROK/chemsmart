"""A Gaussian scan and a constrained optimisation preview what was asked.

Every stage here is driven through the planning session's own preview
chain -- ``validate_project_yaml`` -> the public ``run --fake`` command ->
the live preview verifier -- with the project shapes live sessions write:
a level of theory in ``gas:`` and nothing else, and the same with
``freq`` stated either way.
"""

from __future__ import annotations

import pytest

from tests.agent.gaussian_fake_preview import fake_preview

#: Hydrogen peroxide with its torsion near 111 degrees; a preview runs no
#: engine, so the geometry need only be a molecule.
_H2O2_XYZ = (
    "4\nhydrogen peroxide\n"
    "O 0.000 0.000 0.000\nO 1.450 0.000 0.000\n"
    "H -0.320 0.905 0.000\nH 1.770 -0.325 0.845\n"
)
_TORSION = "[[3,1,2,4]]"
_LEVEL = {"functional": "b3lyp", "basis": "def2-svp"}

#: What a job type is asked for on the command line, beside the project.
_JOB_ARGUMENTS = {
    "scan": ("-c", _TORSION, "-s", "15", "-n", "12"),
    "modred": ("-c", _TORSION),
    "td": (),
}


@pytest.mark.capability("program_jobtype:gaussian:cpu:scan")
@pytest.mark.capability("program_jobtype:gaussian:cpu:modred")
@pytest.mark.capability("program_jobtype:gaussian:cpu:td")
@pytest.mark.parametrize("jobtype", ("scan", "modred", "td"))
def test_a_written_gaussian_input_reads_back_as_the_job_it_asks_for(
    tmp_path, jobtype
):
    """The input reader answers what the log reader will answer.

    ``opt=modredundant`` is written for a scan and for a constrained
    optimisation alike, and a response calculation has no job keyword;
    the route-word chain called a written scan ``modred`` and a written TD
    input ``sp``, so the preview compared the declared job type with the
    wrong word.
    """

    from chemsmart.io.gaussian.input import Gaussian16Input

    sections = (
        {"td": {**_LEVEL, "nstates": 2}}
        if jobtype == "td"
        else {"gas": dict(_LEVEL)}
    )
    _receipt, written = fake_preview(
        tmp_path,
        "gaussian",
        sections,
        _H2O2_XYZ,
        (0, 1),
        jobtype,
        _JOB_ARGUMENTS[jobtype],
    )
    path = tmp_path / "written.com"
    path.write_text(written, encoding="utf-8")
    assert Gaussian16Input(filename=str(path)).jobtype == jobtype
