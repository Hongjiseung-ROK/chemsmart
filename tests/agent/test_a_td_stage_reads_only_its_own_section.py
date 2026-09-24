"""What a Gaussian or ORCA td stage reads from a project, said once.

The molecular project loader seeds a ``td:`` section from the stage
defaults and never from ``gas:`` or ``solv:``; the section view the
Agent's project observation reports (``molecular_project_section_sources``)
said the opposite for a project with no ``gas:``, and a project with no
``td:`` section gave its td stage the shared default's frequency step.
"""

from __future__ import annotations

import pytest
import yaml

_LEVEL = {"functional": "b3lyp", "basis": "def2-svp"}
#: Response settings only, in the words both programs take.
_RESPONSE = {
    "nstates": 4,
    "response_method": "tddft",
    "state_manifold": "singlet",
}


def _load(tmp_path, program: str, sections: dict):
    path = tmp_path / f"{program}.yaml"
    path.write_text(yaml.safe_dump(sections), encoding="utf-8")
    if program == "gaussian":
        from chemsmart.settings.gaussian import YamlGaussianProjectSettings

        return YamlGaussianProjectSettings.from_yaml(str(path))
    from chemsmart.settings.orca import YamlORCAProjectSettings

    return YamlORCAProjectSettings.from_yaml(str(path))


@pytest.mark.capability("tool:validate_project_yaml")
@pytest.mark.parametrize("program", ("gaussian", "orca"))
@pytest.mark.parametrize(
    "sections",
    (
        {"solv": dict(_LEVEL), "td": dict(_RESPONSE)},
        {"gas": dict(_LEVEL), "td": dict(_RESPONSE)},
        {"solv": dict(_LEVEL)},
    ),
    ids=("solv+td", "gas+td", "solv-only"),
)
def test_the_sections_said_to_feed_td_are_the_sections_the_loader_applies(
    tmp_path, program, sections
):
    """Every value the reported sections declare is the value applied."""

    from chemsmart.jobs.settings import molecular_project_section_sources

    applied = _load(tmp_path, program, sections).td_settings()
    reported = molecular_project_section_sources(
        sections, program=program, jobtype="td"
    )
    declared = {}
    for name in reported:
        declared.update(sections[name])
    assert {key: getattr(applied, key) for key in declared} == declared, (
        reported,
        sections,
    )


@pytest.mark.parametrize("program", ("gaussian", "orca"))
def test_a_td_stage_borrowing_a_phase_is_never_a_frequency_job(
    tmp_path, program
):
    """A solv-only project's td stage is a vertical spectrum.

    Gaussian wrote ``freq TD(...)`` -- an excited-state frequency
    calculation -- where ORCA's td settings refuse ``freq`` outright.
    """

    applied = _load(tmp_path, program, {"solv": dict(_LEVEL)}).td_settings()
    assert applied.freq is False
    assert applied.numfreq is False
