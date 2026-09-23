"""A Gaussian scan and a constrained optimisation preview what was asked.

Every stage here is driven through the planning session's own preview
chain -- ``validate_project_yaml`` -> the public ``run --fake`` command ->
the live preview verifier -- with the project shapes live sessions write:
a level of theory in ``gas:`` and nothing else, and the same with
``freq`` stated either way.
"""

from __future__ import annotations

from pathlib import Path

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


#: Quantities that belong to a stationary point: a harmonic spectrum and
#: what is derived from one.
_STATIONARY_POINT_QUANTITIES = frozenset(
    {
        "entropy_times_temperature",
        "gibbs_free_energy",
        "ir_intensities",
        "vibrational_frequencies",
        "vibrational_mode_atom_participation",
        "vibrational_mode_degeneracy_group",
        "vpt2_fundamental_frequencies",
        "vpt2_harmonic_frequencies",
        "vpt2_zero_point_rovibrational_energy",
    }
)


@pytest.mark.capability("selector:gaussian:modred:*")
@pytest.mark.capability("selector:orca:modred:*")
@pytest.mark.parametrize("jobtype", ("modred", "scan"))
def test_no_reader_serves_a_spectrum_where_nothing_is_stationary(jobtype):
    """One job type, one answer, in every program that runs it.

    A constrained optimum is stationary only orthogonal to what it held
    and a scan point is a constrained optimum, so the whole Hessian a
    program may print there is not the Hessian of a stationary point.
    ORCA's modred declared no such quantity by decision; Gaussian's
    declared the spectrum and its IR intensities, so the same request
    answered a frequency in one program and refused it in the other.
    """

    from chemsmart.analysis.result_readers import RESULT_READERS

    served = {
        program: sorted(
            set(reader.selectors_for_jobtype(jobtype) or ())
            & _STATIONARY_POINT_QUANTITIES
        )
        for program, reader in RESULT_READERS.items()
    }
    assert not any(served.values()), served


_DATA = Path(__file__).resolve().parents[1] / "data"
#: One constrained optimisation (H2O2 held at a 90 degree torsion, CUHK
#: Slurm 2150076) in each program, and an archived Gaussian one that ran
#: out of steps.
_HELD_90 = {
    "gaussian": _DATA
    / "GaussianTests"
    / "constrained_dihedral"
    / "h2o2_b3lyp_def2svp_hooh90.log",
    "orca": _DATA
    / "ORCATests"
    / "constrained_dihedral"
    / "h2o2_b3lyp_def2svp_hooh90.out",
}
_EXHAUSTED = (
    _DATA / "GaussianTests" / "outputs" / "cage_free_failed_modred.log"
)
_HELD_ANSWERS = (
    "constrained_coordinate_count",
    "constrained_dihedral_angles",
    "constrained_dihedral_atoms",
    "converged",
)


@pytest.mark.capability("selector:gaussian:modred:converged")
@pytest.mark.capability("selector:gaussian:modred:constrained_dihedral_angles")
def test_a_constrained_optimum_answers_the_same_questions_in_both_programs():
    """What it held, where, and whether it finished -- in either program.

    ORCA's constrained optimisation says which coordinates it held, at
    what value in the structure it returned, and whether the relaxation
    converged; Gaussian's said none of it, so the same question about
    the same calculation had an answer in one program and a refusal in
    the other.
    """

    from chemsmart.analysis.result_readers import RESULT_READERS

    answers = {}
    for program, path in _HELD_90.items():
        reader = RESULT_READERS[program]
        output = reader.open_output(path)
        assert output.jobtype == "modred"
        assert set(_HELD_ANSWERS) <= set(
            reader.selectors_for_jobtype("modred")
        )
        answers[program] = {
            selector: reader.read(output, selector)
            for selector in _HELD_ANSWERS
        }
    gaussian, orca = answers["gaussian"], answers["orca"]
    for selector in _HELD_ANSWERS:
        assert gaussian[selector][1] == orca[selector][1], selector

    # One torsion, whichever end a program names first: ORCA prints the
    # held dihedral as 4-2-1-3, Gaussian echoes 3-1-2-4 as written.
    def torsion(rows):
        return [min(tuple(row), tuple(reversed(row))) for row in rows]

    assert torsion(gaussian["constrained_dihedral_atoms"][0]) == [
        (2.0, 0.0, 1.0, 3.0)
    ]
    assert torsion(orca["constrained_dihedral_atoms"][0]) == [
        (2.0, 0.0, 1.0, 3.0)
    ]
    for program in _HELD_90:
        assert answers[program]["converged"][0] == 1
        assert answers[program]["constrained_coordinate_count"][0] == 1.0
        (held,) = answers[program]["constrained_dihedral_angles"][0]
        assert held == pytest.approx(90.0, abs=0.01)


@pytest.mark.capability("selector:gaussian:modred:converged")
def test_a_constrained_optimisation_that_ran_out_of_steps_says_so():
    """``Optimization stopped.`` after 58 steps is an observation, 0."""

    from chemsmart.analysis.result_readers import RESULT_READERS

    reader = RESULT_READERS["gaussian"]
    output = reader.open_output(_EXHAUSTED)
    assert reader.read(output, "converged") == (0, "1")
    count, _unit = reader.read(output, "constrained_coordinate_count")
    assert count == 3.0
