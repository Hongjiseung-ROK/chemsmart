"""A project an Agent authors says what it wants in typed settings.

CHEMSMART writes each program's input from a project's typed settings
and reads each one back from the written input. The settings classes
also carry fields whose values reach the input verbatim, and a session
reaches for them when it does not find the typed setting. Census R10 Q28
(ax41 and CUHK R8-R10, deepseek-v4-flash-0731): 104 authoring calls in
16 of 842 sessions carried such a field; 88% stated an intent a typed
setting already carried (a broken-symmetry guess, reaction-path
controls, optimiser convergence and cycle caps), one wrote an
``input_string`` that replaced a whole ORCA input with 22 bytes and ran
no method, basis or geometry (R10 Q15 g1), and three Gaussian goals were
refused ``maxcycles`` and ``scf_convergence`` because Gaussian had no
typed field for them -- while a Gaussian ``defgrid`` was accepted and
never written.

Pinned: where an Agent authors a project, a native word for a typed
intent is refused naming the typed setting, and that setting writes the
word; a word no typed setting carries still renders; a person's project
keeps every field and the review shows the ones that reach the input;
and Gaussian writes and reads back the typed numerics the sessions
asked for.
"""

from __future__ import annotations

import pytest

from chemsmart.agent._contracts import RoutedContractError
from chemsmart.agent.projects import project_document, render_project_yaml

from .gaussian_fake_preview import fake_preview, validate

_WATER = (
    "3\nwater\nO 0.0 0.0 0.1173\nH 0.0 0.7572 -0.4692\nH 0.0 -0.7572 -0.4692\n"
)
_LEVEL = {
    "orca": {"functional": "b3lyp", "basis": "def2-svp"},
    "gaussian": {"functional": "b3lyp", "basis": "def2svp"},
}


def _render(program, sections):
    return render_project_yaml(
        project_document(program=program, sections=sections)
    )


def _refusal(program, sections):
    with pytest.raises(RoutedContractError) as caught:
        _render(program, sections)
    report = caught.value.failure_report
    assert report["gate"] == "project.native_words_have_typed_settings"
    return report


@pytest.mark.capability("setting:orca:additional_route_parameters")
@pytest.mark.capability("setting:gaussian:additional_route_parameters")
@pytest.mark.parametrize("program", ["orca", "gaussian"])
@pytest.mark.parametrize(
    "field, value",
    [
        ("input_string", "%scf\n FlipSpin 1,6\nend"),
        ("route_to_be_written", "HF STO-3G Opt"),
    ],
)
def test_a_field_that_replaces_the_hosts_input_is_refused(
    program, field, value
):
    """R10 Q15 g1's input_string replaced a whole ORCA input."""

    report = _refusal(program, {"gas": {**_LEVEL[program], field: value}})
    assert f"gas.{field}" in report["diagnosis"]
    assert "functional" in report["route"] and "basis" in report["route"]


#: A census word, the program, the section it was written in, and the
#: typed setting whose route the refusal must name -- with that setting's
#: value, which must then write the program's word itself.
_TYPED_ROUTES = [
    # R10 Q15 g1/g2, ax41 ino2: broken symmetry through native words.
    ("orca", "gas", "FlipSpin 1,6", {"broken_symmetry": True}, "guessmix 45"),
    ("orca", "gas", "BrokenSym 1,1", {"broken_symmetry": True}, "guessmix 45"),
    (
        "gaussian",
        "gas",
        "Guess=(Mix,Always)",
        {"broken_symmetry": True},
        "guess=mix",
    ),
    # ax41 c034 and ino1: optimiser convergence and cycle cap.
    ("orca", "opt", "TightOpt", {"opt_convergence": "tight"}, "tightopt"),
    ("orca", "opt", "maxiter 500", {"geom_maxiter": 500}, "maxiter 500"),
    # The Gaussian numerics that had no typed field before this change.
    (
        "gaussian",
        "gas",
        "scf=verytight",
        {"scf_convergence": "verytight"},
        "scf=verytight",
    ),
    (
        "gaussian",
        "gas",
        "int=superfinegrid",
        {"defgrid": "superfinegrid"},
        "int=superfinegrid",
    ),
]


@pytest.mark.capability("setting:orca:broken_symmetry")
@pytest.mark.capability("setting:gaussian:scf_convergence")
@pytest.mark.capability("setting:gaussian:defgrid")
@pytest.mark.parametrize(
    "program, section, word, typed, written_word", _TYPED_ROUTES
)
def test_a_native_word_for_a_typed_intent_names_the_setting_that_writes_it(
    tmp_path, program, section, word, typed, written_word
):
    report = _refusal(
        program,
        (
            {
                "gas": dict(_LEVEL[program]),
                section: {"additional_route_parameters": word},
            }
            if section != "gas"
            else {
                "gas": {**_LEVEL[program], "additional_route_parameters": word}
            }
        ),
    )
    (name,) = typed
    assert name in report["route"]

    # The route is walkable: the typed setting renders, validates, and the
    # written input carries the program's word for it.
    sections = {"gas": {**_LEVEL[program], **typed}}
    jobtype = "opt" if section == "opt" else "sp"
    _render(program, sections)
    receipt, written = fake_preview(
        tmp_path, program, sections, _WATER, (0, 1), jobtype
    )
    assert receipt.status == "valid", receipt
    assert written_word in " ".join(written.lower().split())


@pytest.mark.capability("setting:gaussian:geom_maxiter")
def test_a_gaussian_cycle_cap_in_the_opt_options_names_geom_maxiter(
    tmp_path,
):
    """R9 g2, R9 g3 and R10 Q15 g1 asked Gaussian for maxcycles."""

    report = _refusal(
        "gaussian",
        {
            "gas": dict(_LEVEL["gaussian"]),
            "ts": {"additional_opt_options_in_route": "maxcycles=100"},
        },
    )
    assert "geom_maxiter: 100" in report["route"]

    sections = {"gas": {**_LEVEL["gaussian"], "geom_maxiter": 100}}
    receipt, written = fake_preview(
        tmp_path, "gaussian", sections, _WATER, (0, 1), "opt"
    )
    assert receipt.status == "valid", receipt
    assert "opt=(maxcycles=100)" in written.lower()


@pytest.mark.capability("setting:orca:additional_route_parameters")
@pytest.mark.capability("setting:gaussian:additional_route_parameters")
@pytest.mark.parametrize(
    "program, value",
    [
        # A print directive with no typed setting (R10 ax41 interop-fukui).
        ("orca", "Hirshfeld"),
        ("orca", "NoUseSym"),
        ("gaussian", "scf=(tight,xqc) nosymm pop=hirshfeld 6d"),
    ],
)
def test_a_word_no_typed_setting_carries_still_renders(program, value):
    receipt = _render(
        program,
        {"gas": {**_LEVEL[program], "additional_route_parameters": value}},
    )
    assert receipt.status == "candidate_rendered"


@pytest.mark.capability("setting:orca:additional_route_parameters")
def test_a_persons_project_keeps_the_field_and_the_review_shows_it(
    tmp_path,
):
    """The loader still takes the field; its receipt now records it.

    The receipt's settings are what the review renders, and they held only
    advertised names, so an input_string that replaced a whole input was
    absent from the settings a human approved.
    """

    _project, receipt = validate(
        tmp_path,
        "orca",
        {"gas": {**_LEVEL["orca"], "input_string": "! HF STO-3G\n"}},
        "sp",
    )
    assert receipt.status == "valid", receipt.diagnostic
    assert dict(receipt.settings)["input_string"] == "! HF STO-3G\n"


@pytest.mark.parametrize("program", ["orca", "gaussian"])
def test_the_capability_offers_no_field_the_project_tool_refuses(program):
    """A field refused whenever set is a person's; it is not offered."""

    from chemsmart.jobs.settings import (
        agent_refused_fields,
        project_native_words,
    )
    from chemsmart.settings.capabilities import PROJECT_OWNED_PARAMETERS

    refused = agent_refused_fields(program)
    assert "input_string" in refused and "route_to_be_written" in refused
    assert not set(refused) & set(PROJECT_OWNED_PARAMETERS[program])
    for field in refused:
        found = project_native_words(program, {"gas": {field: "x"}})
        assert [item.field for _section, item in found] == [field]


@pytest.mark.capability("setting:gaussian:defgrid")
def test_another_programs_grid_word_is_redirected_in_a_gaussian_project():
    """Gaussian declares its own grid words; ORCA's are ORCA's."""

    from chemsmart.agent._contracts import ContractError

    with pytest.raises(ContractError) as caught:
        _render(
            "gaussian",
            {"gas": {**_LEVEL["gaussian"], "defgrid": "defgrid2"}},
        )
    assert "implemented by: orca" in str(caught.value)
    assert "gaussian's defgrid vocabulary" in str(caught.value)


def test_an_unknown_setting_is_answered_with_the_offered_settings(tmp_path):
    """The loader's key list taught input_string (R10 Q15 g1)."""

    _project, receipt = validate(
        tmp_path,
        "gaussian",
        {"gas": {**_LEVEL["gaussian"], "maxcycle": 100}},
        "opt",
    )
    assert receipt.status == "invalid"
    assert "`maxcycle`" in receipt.diagnostic
    assert "route_to_be_written" not in receipt.diagnostic
    assert "input_string" not in receipt.diagnostic
