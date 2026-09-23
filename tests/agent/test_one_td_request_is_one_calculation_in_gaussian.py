"""One td request is one calculation in Gaussian, ORCA and PySCF.

ORCA's and PySCF's settings take a response calculation as
``response_method`` (``tddft`` or ``tda``) and ``state_manifold``.
Gaussian's took its own ``states: singlets|triplets|50-50`` and always ran
full TD-DFT: the loader refused ``response_method`` as an unknown key, so
the same request could not be sent to the three programs unchanged, a
model had to know Gaussian's dialect to ask for singlets, and the
Tamm-Dancoff approximation was unreachable in Gaussian through a typed
setting.  The hub owns the translation now -- ``TD``/``TDA`` and the spin
option -- and a result says which response ran.

Every value below comes from the Gaussian capability's own declared
domains, and every preview is driven through the public ``run --fake``
command and the live preview verifier: ``validate_project_yaml`` ->
``build_preview_expectation`` -> ``validate_preview_workspace``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from chemsmart.settings.capabilities import PROGRAM_CAPABILITIES
from tests.agent.gaussian_fake_preview import fake_preview, validate

pytestmark = pytest.mark.capability("program_jobtype:gaussian:cpu:td")

_WATER_XYZ = (
    "3\nwater\nO 0.0 0.0 0.1173\nH 0.0 0.7572 -0.4692\nH 0.0 -0.7572 -0.4692\n"
)
_HYDROXYL_XYZ = "2\nhydroxyl radical\nO 0.0 0.0 0.0\nH 0.0 0.0 0.97\n"
_DATA = Path(__file__).resolve().parents[1] / "data" / "GaussianTests"


def _declared(name: str) -> tuple[str, ...]:
    domains = dict(PROGRAM_CAPABILITIES["gaussian"].project_parameter_domains)
    assert name in domains, f"Gaussian declares no domain for {name}"
    return domains[name]


def _gaussian_response_cases():
    return [
        ("response_method", value) for value in _declared("response_method")
    ] + [("state_manifold", value) for value in _declared("state_manifold")]


@pytest.mark.capability("setting:gaussian:response_method")
@pytest.mark.capability("setting:gaussian:state_manifold")
@pytest.mark.parametrize(("parameter", "value"), _gaussian_response_cases())
def test_a_declared_gaussian_response_round_trips_through_the_fake_preview(
    tmp_path, parameter, value
):
    """Declared word -> public run --fake -> the route it means -> green.

    The route is checked against the writer's own tables, so the test
    restates no Gaussian grammar: the response keyword for the declared
    response, the spin option (none for an unrestricted manifold) for the
    declared manifold.
    """

    from chemsmart.jobs.gaussian.settings import (
        GAUSSIAN_TD_MANIFOLD_OPTIONS,
        GAUSSIAN_TD_RESPONSE_KEYWORDS,
    )

    section = {
        "functional": "b3lyp",
        "basis": "def2-svp",
        "nstates": 2,
        "response_method": "tddft",
        "state_manifold": "singlet",
    }
    section[parameter] = value
    open_shell = section["state_manifold"] == "unrestricted"
    receipt, written = fake_preview(
        tmp_path,
        "gaussian",
        {"td": section},
        _HYDROXYL_XYZ if open_shell else _WATER_XYZ,
        (0, 2) if open_shell else (0, 1),
        "td",
    )
    assert receipt.status == "valid", [
        (item.field, item.expected, item.observed) for item in receipt.findings
    ]
    route = next(line for line in written.splitlines() if line.startswith("#"))
    keyword = GAUSSIAN_TD_RESPONSE_KEYWORDS[section["response_method"]]
    leaf = re.search(rf"(?<![A-Za-z]){keyword}\(([^)]*)\)", route)
    assert leaf is not None, route
    option = GAUSSIAN_TD_MANIFOLD_OPTIONS[section["state_manifold"]]
    words = leaf.group(1).split(",")
    if option is None:
        assert not set(words) & {
            word for word in GAUSSIAN_TD_MANIFOLD_OPTIONS.values() if word
        }, route
    else:
        assert option in words, route


@pytest.mark.capability("setting:gaussian:response_method")
@pytest.mark.capability("setting:orca:response_method")
@pytest.mark.capability("setting:pyscf:response_method")
@pytest.mark.parametrize("response", ("tda", "tddft"))
def test_one_td_section_validates_unchanged_in_all_three_programs(
    tmp_path, response
):
    """The same request, sent unchanged, is a valid request everywhere."""

    section = {
        "functional": "b3lyp",
        "basis": "def2-svp",
        "nstates": 3,
        "response_method": response,
        "state_manifold": "singlet",
    }
    for program in ("gaussian", "orca", "pyscf"):
        _project, receipt = validate(
            tmp_path, program, {"td": dict(section)}, "td"
        )
        assert receipt.status == "valid", (program, receipt.diagnostic)
        settings = dict(receipt.settings)
        assert settings["response_method"] == response, program
        assert settings["state_manifold"] == "singlet", program


def test_two_words_for_two_manifolds_are_one_ambiguous_request(tmp_path):
    """Gaussian's own word and the shared word may not disagree."""

    _project, receipt = validate(
        tmp_path,
        "gaussian",
        {
            "td": {
                "functional": "b3lyp",
                "basis": "def2-svp",
                "states": "triplets",
                "state_manifold": "singlet",
            }
        },
        "td",
    )
    assert receipt.status == "invalid"


@pytest.mark.capability("selector:gaussian:td:excitation_energies")
def test_a_gaussian_response_result_states_the_response_it_ran():
    """An archived open-shell TD log: full TD-DFT, the one manifold.

    The route asked ``TD(singlets,nstates=50,root=1)`` of a doublet, and
    Gaussian's spin options act on closed shells only, so the manifold
    that ran is the unrestricted one -- which is what the level says.
    """

    from chemsmart.analysis.result_readers import RESULT_READERS

    reader = RESULT_READERS["gaussian"]
    output = reader.open_output(
        _DATA / "tddft" / "tddft_r1s50_gas_radical_anion.log"
    )
    level = dict(reader.resolve_level(output))
    assert level["response_method"] == "tddft"
    assert level["state_manifold"] == "unrestricted"
    assert level["nstates"] == 50


@pytest.mark.capability("tool:validate_project_yaml")
def test_a_td_stage_that_names_no_method_is_refused_when_validated(tmp_path):
    """The project shape live sessions write for every other stage.

    A level named once in ``gas:`` beside ``td: {nstates: ...}``: the td
    section is read on its own, so the route has no method.  Validation
    called that ``valid`` and the writer died inside the preview with a
    traceback; the refusal now comes when the project is validated.
    """

    _project, receipt = validate(
        tmp_path,
        "gaussian",
        {
            "gas": {"functional": "b3lyp", "basis": "def2-svp"},
            "td": {"nstates": 4},
        },
        "td",
    )
    assert receipt.status == "invalid"
    assert "td:" in receipt.diagnostic
