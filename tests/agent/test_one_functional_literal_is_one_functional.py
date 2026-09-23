"""A functional literal is one functional in every program ChemSmart writes.

``functional: b3lyp`` was three spellings with two meanings: ORCA's bare
``B3LYP`` is the VWN5 form and Gaussian's ``B3LYP`` and PySCF's ``b3lypg``
the VWN RPA form -- 0.032-0.154 Eh apart on eight species and 2.34 kcal/mol
apart in the vertical IP of water, while the three programs agree to 2.2e-6
Eh at one form (CUHK Slurm 2149277/2149278). Gaussian ran the route word
``pbe0`` as the PBE0-DH double hybrid. Each program's settings class now
spells a literal from its own table and its parser reads the written input
back to the literal, so this is a heartbeat: project YAML through the live
loader, the real job and writer, and the program's own parser.
"""

from __future__ import annotations

import pytest

from chemsmart.io.gaussian.input import Gaussian16Input
from chemsmart.io.orca.input import ORCAInput
from chemsmart.jobs.gaussian import GaussianSinglePointJob
from chemsmart.jobs.gaussian.writer import GaussianInputWriter
from chemsmart.jobs.orca import ORCASinglePointJob
from chemsmart.jobs.orca.writer import ORCAInputWriter
from chemsmart.settings.gaussian import YamlGaussianProjectSettings
from chemsmart.settings.orca import YamlORCAProjectSettings
from chemsmart.settings.pyscf import YamlPySCFProjectSettings

pytestmark = pytest.mark.capability("setting:*")

#: (literal, ORCA keyword, Gaussian keyword or None where Gaussian refuses,
#: PySCF xc) -- what each writer is expected to produce, stated once here as
#: the observation the oracle above made, not as the writers' own tables.
WRITTEN = (
    ("b3lyp", "B3LYP/G", "b3lyp", "b3lypg"),
    ("b3lyp5", "B3LYP", None, "b3lyp5"),
    ("pbe0", "pbe0", "PBE1PBE", "pbe0"),
    ("pbe", "pbe", "PBEPBE", "pbe"),
)

WATER = (
    "3\nwater\nO 0.0 0.0 0.1173\nH 0.0 0.7572 -0.4692\nH 0.0 -0.7572 -0.4692\n"
)


def _water(tmp_path):
    path = tmp_path / "water.xyz"
    path.write_text(WATER, encoding="utf-8")
    return str(path)


def _project(tmp_path, name, body):
    path = tmp_path / f"{name}.yaml"
    path.write_text(body, encoding="utf-8")
    return str(path)


@pytest.mark.parametrize(("literal", "orca_word", "g16_word", "xc"), WRITTEN)
def test_orca_writes_the_form_the_literal_names_and_reads_it_back(
    tmp_path, orca_jobrunner_no_scratch, literal, orca_word, g16_word, xc
):
    project = YamlORCAProjectSettings.from_yaml(
        _project(
            tmp_path,
            "orca",
            f"gas:\n  functional: {literal}\n  basis: def2-svp\n",
        )
    )
    settings = project.sp_settings()
    settings.charge, settings.multiplicity = 0, 1
    job = ORCASinglePointJob.from_filename(
        filename=_water(tmp_path),
        settings=settings,
        label="orca_sp",
        jobrunner=orca_jobrunner_no_scratch,
    )
    ORCAInputWriter(job=job).write(target_directory=str(tmp_path))

    written = ORCAInput(filename=str(tmp_path / "orca_sp.inp"))

    assert orca_word.casefold() in written.route_object.route_keywords
    assert written.functional == literal


@pytest.mark.parametrize(("literal", "orca_word", "g16_word", "xc"), WRITTEN)
def test_gaussian_writes_the_form_the_literal_names_or_refuses_it(
    tmp_path, gaussian_jobrunner_no_scratch, literal, orca_word, g16_word, xc
):
    project = YamlGaussianProjectSettings.from_yaml(
        _project(
            tmp_path,
            "gaussian",
            f"gas:\n  functional: {literal}\n  basis: def2-svp\n",
        )
    )
    settings = project.sp_settings()
    settings.charge, settings.multiplicity = 0, 1
    job = GaussianSinglePointJob.from_filename(
        filename=_water(tmp_path),
        settings=settings,
        label="g16_sp",
        jobrunner=gaussian_jobrunner_no_scratch,
    )
    if g16_word is None:
        with pytest.raises(ValueError, match="ORCA or PySCF"):
            GaussianInputWriter(job=job).write(target_directory=str(tmp_path))
        return
    GaussianInputWriter(job=job).write(target_directory=str(tmp_path))

    written = Gaussian16Input(filename=str(tmp_path / "g16_sp.com"))

    assert g16_word.casefold() in written.route_string.casefold().split()
    assert written.functional == literal


@pytest.mark.parametrize(("literal", "orca_word", "g16_word", "xc"), WRITTEN)
def test_pyscf_resolves_the_form_the_literal_names(
    tmp_path, literal, orca_word, g16_word, xc
):
    project = YamlPySCFProjectSettings.from_yaml(
        _project(
            tmp_path,
            "pyscf",
            f"sp:\n  functional: {literal}\n  basis: def2-svp\n"
            "  freq: false\n",
        )
    )

    assert project.sp_settings().xc == xc


@pytest.mark.parametrize("literal", [row[0] for row in WRITTEN])
def test_every_program_records_one_identity_for_one_literal(literal):
    """The receipt each program's settings mint names one functional."""

    from chemsmart.jobs.gaussian.settings import (
        describe_functional_resolution as gaussian_resolution,
    )
    from chemsmart.jobs.orca.settings import (
        describe_functional_resolution as orca_resolution,
    )
    from chemsmart.jobs.pyscf.settings import (
        describe_functional_resolution as pyscf_resolution,
    )

    records = [
        describe(literal)
        for describe in (
            orca_resolution,
            gaussian_resolution,
            pyscf_resolution,
        )
    ]
    identities = {
        (
            record["canonical_literal"],
            record["functional_family"],
            record["correlation_convention"],
        )
        for record in records
    }

    assert len(identities) == 1
    assert {record["status"] for record in records} == {"canonical_literal"}


def test_gaussian_refuses_a_word_it_would_complete_to_another_keyword():
    """Gaussian ran ``pbe0`` as PBE0-DH; a word it completes is refused."""

    from chemsmart.jobs.gaussian.settings import gaussian_native_functional

    with pytest.raises(ValueError, match="PBE0DH"):
        gaussian_native_functional("pbe0d")
    assert gaussian_native_functional("pbe0") == "PBE1PBE"
