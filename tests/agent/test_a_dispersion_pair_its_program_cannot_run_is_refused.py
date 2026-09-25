"""A functional and dispersion pair is written only where its program has one.

Gaussian 16 and ORCA 6.1.1 each parameterise a dispersion correction for some
functionals and not others, and the writers wrote any pair. R10 Q15 g2's four
Gaussian nodes asked for wB97X with D3(BJ) (CUHK Slurm 2153334): the preview
was green and Gaussian stopped each in link 301 before any SCF ("R6DS8: Unable
to choose the S8 parameter"); ORCA aborts the same pair after the SCF, past
its input check (R10 Q14 O1 L1). R10 census D (CUHK Slurm 2153534) ran every
pair the writers produce in both programs: 179 Gaussian and 96 ORCA routes
died on the program's own parameters; ORCA's D2 substitutes a default C6
scaling, without an error, for any functional it does not recognise --
B3LYP/G, the form ``b3lyp`` names, among them; and ORCA's bare D3 is D3(BJ)
while the hub's ``d3`` is Gaussian's zero-damping GD3.

This drives the public path -- project YAML through the live loader, the
settings the project tool validates, the writer -- and reads the refusal
where a session reads it: the validation diagnostic, cut at 500 characters.
"""

from __future__ import annotations

import pytest

from chemsmart.agent.projects import _public_loader_diagnostic
from chemsmart.jobs.gaussian import GaussianOptJob, GaussianSinglePointJob
from chemsmart.jobs.gaussian.writer import GaussianInputWriter
from chemsmart.jobs.orca import ORCASinglePointJob
from chemsmart.jobs.orca.writer import ORCAInputWriter
from chemsmart.settings.gaussian import YamlGaussianProjectSettings
from chemsmart.settings.orca import YamlORCAProjectSettings

pytestmark = pytest.mark.capability("setting:*")

#: R10 Q15 g2's own project for node ene-opt, byte for byte
#: (projects/project-g-ene-opt.yaml of live-20260924T152328812196Z).
Q15_G2_ENE_OPT = (
    "gas:\n"
    "  basis: def2-tzvp\n"
    "  dispersion: d3bj\n"
    "  freq: true\n"
    "  functional: wb97x\n"
)

WATER = (
    "3\nwater\nO 0.0 0.0 0.1173\nH 0.0 0.7572 -0.4692\nH 0.0 -0.7572 -0.4692\n"
)

LOADERS = {
    "gaussian": YamlGaussianProjectSettings,
    "orca": YamlORCAProjectSettings,
}


def _project(tmp_path, program, body):
    path = tmp_path / f"{program}.yaml"
    path.write_text(body, encoding="utf-8")
    return LOADERS[program].from_yaml(str(path))


def _validate(settings):
    """What the project tool does with a stage's settings (projects.py)."""

    validator = getattr(settings, "validate", None)
    if callable(validator):
        validator()


def _level(functional, dispersion, basis="def2-svp"):
    return (
        f"gas:\n  functional: {functional}\n  dispersion: {dispersion}\n"
        f"  basis: {basis}\n  freq: false\n"
    )


#: (program, project, jobtype, words the refusal must name)
REFUSED = (
    pytest.param(
        "gaussian",
        Q15_G2_ENE_OPT,
        "opt",
        ("GD3BJ", "WB97X", "link 301", "Route:"),
        id="q15-g2-wb97x-gd3bj",
    ),
    pytest.param(
        "gaussian",
        _level("m062x", "d3bj"),
        "sp",
        ("GD3BJ", "M062X", "It has GD3 for M062X", "Route:"),
        id="gaussian-m062x-gd3bj",
    ),
    pytest.param(
        "orca",
        _level("wb97x", "d3bj"),
        "sp",
        ("D3BJ", "after the SCF", "It has D4 for wb97x", "Route:"),
        id="q14-o1-l1-wb97x-d3bj",
    ),
    pytest.param(
        "orca",
        _level("b3lyp", "d2"),
        "sp",
        ("D2", "B3LYP/G", "C6 scaling 1.2", "Gaussian has the pair", "Route:"),
        id="orca-b3lyp-d2-default",
    ),
    pytest.param(
        "orca",
        _level("b3lyp", "d3"),
        "sp",
        ("D3(BJ)", "d3zero", "d3bj"),
        id="orca-d3-is-two-corrections",
    ),
    pytest.param(
        "gaussian",
        "gas:\n  functional: tpss-d3bj\n  basis: def2-svp\n  freq: false\n",
        "sp",
        ("'tpss'", "no keyword TPSS", "link 1"),
        id="gaussian-shorthand-base-is-no-keyword",
    ),
)


@pytest.mark.parametrize(("program", "body", "jobtype", "names"), REFUSED)
def test_a_pair_the_program_cannot_run_is_refused_at_validation_with_its_route(
    tmp_path, program, body, jobtype, names
):
    settings = getattr(
        _project(tmp_path, program, body), f"{jobtype}_settings"
    )()

    with pytest.raises(ValueError) as refused:
        _validate(settings)

    diagnostic = _public_loader_diagnostic(refused.value, "")
    for name in names:
        assert name in diagnostic, (name, diagnostic)


def test_q15_g2_is_refused_by_the_writer_it_reached(
    tmp_path, gaussian_jobrunner_no_scratch
):
    """The bytes Gaussian refused are never written again."""

    settings = _project(tmp_path, "gaussian", Q15_G2_ENE_OPT).opt_settings()
    settings.charge, settings.multiplicity = 0, 1
    xyz = tmp_path / "water.xyz"
    xyz.write_text(WATER, encoding="utf-8")
    job = GaussianOptJob.from_filename(
        filename=str(xyz),
        settings=settings,
        label="q15_g2_ene_opt",
        jobrunner=gaussian_jobrunner_no_scratch,
    )

    with pytest.raises(ValueError, match="GD3BJ parameters for WB97X"):
        GaussianInputWriter(job=job).write(target_directory=str(tmp_path))


#: (program, functional, dispersion, route words) -- pairs the census ran.
WRITTEN = (
    ("gaussian", "b3lyp", "d3bj", ("b3lyp", "empiricaldispersion=gd3bj")),
    ("gaussian", "m062x", "d3", ("m062x", "empiricaldispersion=gd3")),
    ("gaussian", "wb97xd", "gd2", ("wb97xd", "empiricaldispersion=gd2")),
    ("orca", "b3lyp", "d3bj", ("b3lyp/g", "d3bj")),
    ("orca", "b3lyp5", "d2", ("b3lyp", "d2")),
    ("orca", "wb97x", "d4", ("wb97x", "d4")),
    ("orca", "m062x", "d3zero", ("m062x", "d3zero")),
)


@pytest.mark.parametrize(
    ("program", "functional", "dispersion", "words"), WRITTEN
)
def test_a_pair_the_program_ran_is_still_written(
    tmp_path,
    gaussian_jobrunner_no_scratch,
    orca_jobrunner_no_scratch,
    program,
    functional,
    dispersion,
    words,
):
    settings = _project(
        tmp_path, program, _level(functional, dispersion)
    ).sp_settings()
    _validate(settings)
    settings.charge, settings.multiplicity = 0, 1
    xyz = tmp_path / "water.xyz"
    xyz.write_text(WATER, encoding="utf-8")
    if program == "gaussian":
        job = GaussianSinglePointJob.from_filename(
            filename=str(xyz),
            settings=settings,
            label="pair",
            jobrunner=gaussian_jobrunner_no_scratch,
        )
        GaussianInputWriter(job=job).write(target_directory=str(tmp_path))
        route = next(
            line
            for line in (tmp_path / "pair.com").read_text().splitlines()
            if line.startswith("#")
        )
    else:
        job = ORCASinglePointJob.from_filename(
            filename=str(xyz),
            settings=settings,
            label="pair",
            jobrunner=orca_jobrunner_no_scratch,
        )
        ORCAInputWriter(job=job).write(target_directory=str(tmp_path))
        route = next(
            line
            for line in (tmp_path / "pair.inp").read_text().splitlines()
            if line.startswith("!")
        )
    tokens = route.casefold().split()
    for word in words:
        assert word.casefold() in tokens, (word, route)
