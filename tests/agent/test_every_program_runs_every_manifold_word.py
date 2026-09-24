"""One excited-state manifold vocabulary, asked of every program.

A td stage names the manifold it wants in the words every program's
settings take: ``singlet``, ``triplet`` or ``singlet_triplet`` of a
closed-shell reference, and ``unrestricted``, the one spin-conserving
manifold of an open-shell reference.  Which of them a reference has is a
fact about the reference, so the three programs ask one rule
(``td_manifold_reference_refusal``) rather than three.

Before R10 Q8 the same ``td:`` section sent to the three writers came back
three ways: ORCA refused ``triplet`` and ``unrestricted`` although it
computes both (the triplet block of a ``Triplets true`` solve; TD-DFT on
its unrestricted reference), PySCF refused ``singlet_triplet``, and no
refusal named a route -- a model had to learn each program's gaps.

Every preview below is driven through the public ``run --fake`` command
and the live preview verifier, and every word comes from the program's own
declared domain.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from chemsmart.jobs.settings import (
    TD_CLOSED_SHELL_MANIFOLDS,
    TD_OPEN_SHELL_MANIFOLD,
    td_manifold_reference_refusal,
)
from chemsmart.settings.capabilities import PROGRAM_CAPABILITIES
from tests.agent.gaussian_fake_preview import fake_preview

_WATER_XYZ = (
    "3\nwater\nO 0.0 0.0 0.1173\nH 0.0 0.7572 -0.4692\nH 0.0 -0.7572 -0.4692\n"
)
_HYDROXYL_XYZ = "2\nhydroxyl radical\nO 0.0 0.0 0.0\nH 0.0 0.0 0.97\n"
_EVERY_WORD = frozenset(TD_CLOSED_SHELL_MANIFOLDS) | {TD_OPEN_SHELL_MANIFOLD}
_NATIVE_PREVIEW_PROGRAMS = ("gaussian", "orca")


def _declared(program: str, name: str) -> tuple[str, ...]:
    domains = dict(PROGRAM_CAPABILITIES[program].project_parameter_domains)
    assert name in domains, f"{program} declares no domain for {name}"
    return domains[name]


def _section(program: str, manifold: str) -> dict:
    section = {
        "functional": "b3lyp",
        "basis": "def2-svp",
        "nstates": 2,
        "response_method": "tddft",
        "state_manifold": manifold,
    }
    if program == "orca":
        section["ri_approximation"] = "none"
    return section


@pytest.mark.capability("setting:gaussian:state_manifold")
@pytest.mark.capability("setting:orca:state_manifold")
@pytest.mark.parametrize("program", _NATIVE_PREVIEW_PROGRAMS)
def test_every_program_declares_every_manifold_word(program):
    """The words a model may write are the same set in every program."""

    assert set(_declared(program, "state_manifold")) == _EVERY_WORD


def _cases():
    return [
        (program, word)
        for program in _NATIVE_PREVIEW_PROGRAMS
        for word in _declared(program, "state_manifold")
    ]


@pytest.mark.capability("setting:gaussian:state_manifold")
@pytest.mark.capability("setting:orca:state_manifold")
@pytest.mark.parametrize(("program", "manifold"), _cases())
def test_a_declared_manifold_word_previews_as_itself(
    tmp_path, program, manifold
):
    """Declared word -> public run --fake -> the verifier reads it back.

    ORCA spells ``triplet`` and ``singlet_triplet`` alike
    (``Triplets true``); the written input still reads back as the word
    that was asked, which is what the preview verifier compares.
    """

    open_shell = manifold == TD_OPEN_SHELL_MANIFOLD
    receipt, written = fake_preview(
        tmp_path,
        program,
        {"td": _section(program, manifold)},
        _HYDROXYL_XYZ if open_shell else _WATER_XYZ,
        (0, 2) if open_shell else (0, 1),
        "td",
    )
    assert receipt.status == "valid", [
        (item.field, item.expected, item.observed) for item in receipt.findings
    ]
    if program == "orca":
        from chemsmart.jobs.orca.settings import ORCA_TD_TRIPLET_SOLVES

        triplets = "  Triplets true" in written
        assert triplets == (manifold in ORCA_TD_TRIPLET_SOLVES), written


def _reference_mismatches():
    return [
        (program, word, multiplicity)
        for program in ("gaussian", "orca", "pyscf")
        for word, multiplicity in (
            ("singlet", 2),
            ("singlet_triplet", 2),
            ("triplet", 2),
            (TD_OPEN_SHELL_MANIFOLD, 1),
        )
        if word in _declared(program, "state_manifold")
    ]


@pytest.mark.capability("setting:gaussian:state_manifold")
@pytest.mark.capability("setting:orca:state_manifold")
@pytest.mark.capability("setting:pyscf:state_manifold")
@pytest.mark.parametrize(
    ("program", "manifold", "multiplicity"), _reference_mismatches()
)
def test_a_manifold_the_reference_does_not_have_is_refused_alike(
    tmp_path, program, manifold, multiplicity
):
    """One sentence, naming the manifold the reference does have."""

    from chemsmart.cli.main import entry_point

    xyz = tmp_path / "mol.xyz"
    xyz.write_text(_HYDROXYL_XYZ if multiplicity == 2 else _WATER_XYZ)
    project = tmp_path / "project.yaml"
    import yaml

    project.write_text(yaml.safe_dump({"td": _section(program, manifold)}))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=workspace):
        result = runner.invoke(
            entry_point,
            [
                "run",
                "--fake",
                "--no-scratch",
                program,
                "--project",
                str(project),
                "--filename",
                str(xyz),
                "--charge",
                "0",
                "--multiplicity",
                str(multiplicity),
                "td",
            ],
        )
    assert result.exit_code != 0
    sentence = td_manifold_reference_refusal(manifold, multiplicity)
    assert sentence
    assert sentence in (str(result.exception) + result.output)
