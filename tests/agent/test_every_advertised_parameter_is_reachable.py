"""Advertised, settable, written, and read back — or not advertised.

A project-owned parameter is advertised to the model as something it may
set, and project YAML is the only channel it has: no workflow node and no
typed tool carries per-node program settings. The loader refuses any key
absent from the stage defaults, so a name the capability registry
advertises and no settings class carries is an instruction that cannot be
followed -- the model reads the capability, writes the key, and the
project is rejected.

Thirteen names were in exactly that state: four for ORCA
(`additional_opt_options`, `append_additional_info`, `dieze_tag`,
`solvent_options`) and nine for Gaussian, the latter including four core
SCF controls (`scf_algorithm`, `scf_convergence`, `scf_maxiter`,
`scf_tol`).

The registry now computes what it advertises from what the settings
classes accept, so the guarantee stays true as those classes change
rather than being true on the day someone last checked.
"""

from __future__ import annotations

import importlib

import pytest

from chemsmart.settings.capabilities import PROJECT_OWNED_PARAMETERS

#: Settings classes the project loader can lift a section into, per
#: program. A jobtype with its own class makes its fields settable from
#: that section, which is why the irc and neb fields are legitimately
#: advertised for ORCA.
_SETTINGS_CLASSES = {
    "orca": (
        "chemsmart.jobs.orca.settings",
        (
            "ORCAJobSettings",
            "ORCAIRCJobSettings",
            "ORCANEBJobSettings",
            # A saddle search has its own class for the same reason irc
            # and neb do, and the loader lifts a ``ts:`` section into it.
            # That is asserted below by loading one, not assumed here.
            "ORCATSJobSettings",
        ),
    ),
    "gaussian": (
        "chemsmart.jobs.gaussian.settings",
        (
            "GaussianJobSettings",
            "GaussianTDDFTJobSettings",
            "GaussianLinkJobSettings",
        ),
    ),
}


def _settable(program):
    module_name, class_names = _SETTINGS_CLASSES[program]
    module = importlib.import_module(module_name)
    names = set()
    for class_name in class_names:
        names.update(getattr(module, class_name).default().__dict__)
    return names


@pytest.mark.parametrize("program", sorted(_SETTINGS_CLASSES))
def test_no_parameter_is_advertised_that_nothing_can_set(program):
    advertised = set(PROJECT_OWNED_PARAMETERS[program])
    unsettable = sorted(advertised - _settable(program))

    assert unsettable == [], (
        f"{program} advertises {len(unsettable)} project parameters that no "
        f"settings class accepts, so a model following the capability list "
        f"writes a key the project loader rejects: {unsettable}"
    )


@pytest.mark.parametrize("program", sorted(_SETTINGS_CLASSES))
def test_the_advertised_set_is_not_empty(program):
    """Guard the filter itself: over-filtering would be silent."""

    assert len(PROJECT_OWNED_PARAMETERS[program]) > 20


def test_the_controls_that_were_lost_are_back_where_they_belong():
    """Four Gaussian SCF controls were advertised and unsettable.

    They are not restored by advertising them again -- Gaussian's settings
    class genuinely has no such fields -- so the honest state is that
    Gaussian does not advertise them, while ORCA, which does carry them,
    does.
    """

    gaussian = set(PROJECT_OWNED_PARAMETERS["gaussian"])
    orca = set(PROJECT_OWNED_PARAMETERS["orca"])
    for control in (
        "scf_algorithm",
        "scf_convergence",
        "scf_maxiter",
        "scf_tol",
    ):
        assert control not in gaussian
        assert control in orca


@pytest.mark.parametrize(
    "jobtype,class_name",
    [
        ("ts", "ORCATSJobSettings"),
        ("irc", "ORCAIRCJobSettings"),
        ("neb", "ORCANEBJobSettings"),
    ],
)
def test_the_loader_really_lifts_the_section_into_its_own_class(
    tmp_path, jobtype, class_name
):
    """Membership in the list above is a claim; this is the evidence.

    A jobtype's fields are legitimately advertised only if the project
    loader lifts that section into the class carrying them. Listing the
    class proves nothing on its own -- ``ts`` was in exactly that state,
    its settings class present and its section not dispatched, so a
    project setting a TS control was rejected with "Keyword 'inhess' is
    not in list of keywords" while the capability list said nothing was
    wrong.

    Checking it by loading a project keeps the list above honest against
    a dispatch table it does not share.
    """

    from chemsmart.settings.orca import YamlORCAProjectSettingsBuilder

    path = tmp_path / "probe.yaml"
    path.write_text(
        f"{jobtype}:\n  functional: b3lyp\n  basis: def2-svp\n",
        encoding="utf-8",
    )

    project = YamlORCAProjectSettingsBuilder(filename=str(path)).build()
    settings = getattr(project, f"{jobtype}_settings")()

    assert type(settings).__name__ == class_name
