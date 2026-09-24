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
_PROGRAMS = ("gaussian", "orca", "pyscf")


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
@pytest.mark.capability("setting:pyscf:state_manifold")
@pytest.mark.parametrize("program", _PROGRAMS)
def test_every_program_declares_every_manifold_word(program):
    """The words a model may write are the same set in every program."""

    assert set(_declared(program, "state_manifold")) == _EVERY_WORD


def _cases():
    return [
        (program, word)
        for program in _PROGRAMS
        for word in _declared(program, "state_manifold")
    ]


def _pyscf_fake_preview(tmp_path, section, xyz_text, state):
    """The same chain for the program whose preview is a run receipt."""

    from chemsmart.agent.live_session import _preview_server_profile
    from chemsmart.agent.program_verifiers import (
        build_preview_expectation,
        validate_preview_workspace,
    )
    from chemsmart.cli.main import entry_point
    from tests.agent.gaussian_fake_preview import artifact, validate

    charge, multiplicity = state
    xyz = tmp_path / "input.xyz"
    xyz.write_text(xyz_text, encoding="utf-8")
    project, validation = validate(tmp_path, "pyscf", {"td": section}, "td")
    assert validation.status == "valid", validation.diagnostic
    server = tmp_path / "preview-server.yaml"
    server.write_text(_preview_server_profile(), encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=workspace) as cwd:
        result = runner.invoke(
            entry_point,
            [
                "run",
                "--server",
                str(server),
                "--fake",
                "--no-scratch",
                "pyscf",
                "--project",
                str(project),
                "--filename",
                str(xyz),
                "--charge",
                str(charge),
                "--multiplicity",
                str(multiplicity),
                "td",
            ],
        )
        preview_dir = cwd
    assert result.exit_code == 0, (result.output[-600:], result.exception)
    expectation = build_preview_expectation(
        program="pyscf",
        jobtype="td",
        input_artifact=artifact(xyz, "geometry_xyz"),
        project=validation,
        charge=charge,
        multiplicity=multiplicity,
    )
    return validate_preview_workspace(expectation, preview_dir)


@pytest.mark.capability("setting:gaussian:state_manifold")
@pytest.mark.capability("setting:orca:state_manifold")
@pytest.mark.capability("setting:pyscf:state_manifold")
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
    xyz_text = _HYDROXYL_XYZ if open_shell else _WATER_XYZ
    state = (0, 2) if open_shell else (0, 1)
    section = _section(program, manifold)
    if program == "pyscf":
        receipt = _pyscf_fake_preview(tmp_path, section, xyz_text, state)
        written = ""
    else:
        receipt, written = fake_preview(
            tmp_path, program, {"td": section}, xyz_text, state, "td"
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


@pytest.mark.capability("setting:pyscf:excited_state_root")
def test_a_followed_root_names_one_manifold(tmp_path):
    """A root is the k-th of one manifold; two blocks have two k-th roots.

    ``singlet_triplet`` is two spin blocks solved side by side, so an
    optimisation asked to follow "root 1" of it would follow S1 or T1 by
    an accident of implementation.  The project is refused when it is
    validated, naming the edit.
    """

    from tests.agent.gaussian_fake_preview import validate

    section = _section("pyscf", "singlet_triplet")
    section["excited_state_root"] = 1
    _project, receipt = validate(tmp_path, "pyscf", {"opt": section}, "opt")
    assert receipt.status == "invalid"
    assert "one manifold" in receipt.diagnostic
