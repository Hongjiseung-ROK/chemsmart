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


#: The project shapes live sessions write for these stages.
_PROJECTS = {
    "level_only": {"gas": dict(_LEVEL)},
    "freq_true": {"gas": {**_LEVEL, "freq": True}},
    "freq_false": {"gas": {**_LEVEL, "freq": False}},
}


def _route(written: str) -> str:
    return next(line for line in written.splitlines() if line.startswith("#"))


def _findings(receipt) -> list:
    return [
        (item.field, item.expected, item.observed) for item in receipt.findings
    ]


@pytest.mark.capability("program_jobtype:gaussian:cpu:scan")
@pytest.mark.parametrize("shape", sorted(_PROJECTS))
def test_a_relaxed_scan_previews_green_from_an_ordinary_project(
    tmp_path, shape
):
    """A scan runs no frequency step, and its settings say so.

    The loader hands a scan the phase section's (or the shared default's)
    ``freq: true`` and the route getter silently dropped it, so the
    declaration the preview compares against the written input said a
    Hessian would run: every preview from a project that left ``freq``
    at its default was red on ``freq``.
    """

    receipt, written = fake_preview(
        tmp_path,
        "gaussian",
        _PROJECTS[shape],
        _H2O2_XYZ,
        (0, 1),
        "scan",
        _JOB_ARGUMENTS["scan"],
    )
    assert receipt.status == "valid", _findings(receipt)
    assert "freq" not in _route(written).lower().split()


@pytest.mark.capability("program_jobtype:gaussian:cpu:modred")
@pytest.mark.parametrize("shape", sorted(_PROJECTS))
def test_a_constrained_optimisation_computes_the_hessian_its_project_asks_for(
    tmp_path, shape
):
    """The route runs a frequency step exactly when the project asks.

    The route getter set ``freq = True`` on every constrained
    optimisation, so a project that declared ``freq: false`` -- the
    reviewed setting -- ran a Hessian anyway, and its preview was red on
    ``freq``.  The loader's default (a Hessian) is unchanged.
    """

    from chemsmart.settings.gaussian import YamlGaussianProjectSettings

    receipt, written = fake_preview(
        tmp_path,
        "gaussian",
        _PROJECTS[shape],
        _H2O2_XYZ,
        (0, 1),
        "modred",
        _JOB_ARGUMENTS["modred"],
    )
    assert receipt.status == "valid", _findings(receipt)
    applied = YamlGaussianProjectSettings.from_yaml(
        str(tmp_path / "gaussian-modred.yaml")
    ).modred_settings()
    assert ("freq" in _route(written).lower().split()) is bool(applied.freq)
