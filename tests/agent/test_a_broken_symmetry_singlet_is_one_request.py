"""An open-shell (broken-symmetry) singlet is one typed request in every
program, written in each program's own mechanism.

Before it, a session that needed a singlet diradical could only write a
program's native words, and each one failed differently: R10 Q15 g1 put
ORCA's FlipSpin on the simple-input line three ways (the input check aborted
each) and then a Gaussian ``guess=mix`` on restricted routes, which run
restricted; an R8 twisted-ethylene session delivered the restricted barrier
(97.3 kcal/mol against ~65) because no broken-symmetry state was selectable;
an ax41 session substituted an M=3 determinant for the Ms=0 state. Oracle
O0 (R10 Q18, CUHK Slurm 2153330) measured what each program's own mechanism
reaches, and this file pins that the request is written as that mechanism
and reads back to itself, through the ``chemsmart run --fake`` path the
preview takes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

pytestmark = pytest.mark.capability(
    "setting:gaussian:broken_symmetry",
    "setting:orca:broken_symmetry",
    "setting:pyscf:broken_symmetry",
)

P_BENZYNE = (
    "10\np-benzyne, a regular hexagon (R10 Q18 O0)\n"
    "C 1.3950 0.0 0.0\nC 0.6975 1.2081 0.0\nC -0.6975 1.2081 0.0\n"
    "C -1.3950 0.0 0.0\nC -0.6975 -1.2081 0.0\nC 0.6975 -1.2081 0.0\n"
    "H 1.2400 2.1477 0.0\nH -1.2400 2.1477 0.0\nH -1.2400 -2.1477 0.0\n"
    "H 1.2400 -2.1477 0.0\n"
)

#: The section each program's project takes the request in, and the file
#: its writer leaves for the program.
SECTION = {"gaussian": "gas", "orca": "gas", "pyscf": "sp"}
WRITTEN = {"gaussian": ".com", "orca": ".inp", "pyscf": ".py"}


def _fake_run(tmp_path, program, settings, *, multiplicity=1, jobtype="sp"):
    """``chemsmart run --fake`` on one project, the path a preview takes."""

    from chemsmart.agent.live_session import _preview_server_profile
    from chemsmart.cli.main import entry_point

    xyz = tmp_path / "pbz.xyz"
    xyz.write_text(P_BENZYNE, encoding="utf-8")
    project = tmp_path / "project.yaml"
    project.write_text(
        yaml.safe_dump({SECTION[program]: settings}), encoding="utf-8"
    )
    server = tmp_path / "server.yaml"
    server.write_text(_preview_server_profile(), encoding="utf-8")
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        result = runner.invoke(
            entry_point,
            [
                "run",
                "--server",
                str(server),
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
                jobtype,
            ],
        )
        written = sorted(Path(cwd).rglob(f"*{WRITTEN[program]}"))
        text = written[0].read_text() if written else ""
        path = written[0] if written else None
        if path is not None:
            kept = tmp_path / path.name
            kept.write_text(text)
            path = kept
    return result, text, path


REQUEST = {"functional": "b3lyp", "basis": "def2-svp", "broken_symmetry": True}


def test_gaussian_writes_the_unrestricted_method_and_its_mixing_guess(
    tmp_path,
):
    from chemsmart.jobs.gaussian.settings import GaussianJobSettings

    result, text, path = _fake_run(tmp_path, "gaussian", REQUEST)
    assert result.exit_code == 0, result.output
    route = next(line for line in text.splitlines() if line.startswith("#"))
    words = route.lower().split()
    # U prefixed, because guess=mix on a restricted route runs restricted
    # (O0: every restricted route stayed RB3LYP/RHF).
    assert "ub3lyp" in words and "guess=mix" in words, route
    # The written input reads back to the request that produced it.
    parsed = GaussianJobSettings.from_comfile(str(path))
    assert parsed.broken_symmetry is True
    assert parsed.functional == "b3lyp"
    assert not parsed.additional_route_parameters


def test_orca_writes_the_unrestricted_determinant_and_its_mixing_guess(
    tmp_path,
):
    from chemsmart.io.orca.input import ORCAInput

    result, text, path = _fake_run(tmp_path, "orca", REQUEST)
    assert result.exit_code == 0, result.output
    block = re.search(r"%scf\n(.*?)\nend", text, re.DOTALL)
    assert block is not None, text
    lines = [line.strip() for line in block.group(1).splitlines()]
    assert "HFTyp UHF" in lines and "GuessMix 45" in lines, lines
    # Nothing of the request rides the simple-input line, where ORCA's input
    # check aborted FlipSpin three times in R10 Q15 g1.
    assert "guessmix" not in text.splitlines()[0].lower()
    parsed = ORCAInput(filename=str(path)).read_settings()
    assert parsed.broken_symmetry is True and parsed.reference == "uhf"


def test_pyscf_follows_its_own_instability_into_the_unrestricted_singlet(
    tmp_path,
):
    result, text, _path = _fake_run(tmp_path, "pyscf", REQUEST)
    assert result.exit_code == 0, result.output
    payload = re.search(r'CONFIG = json.loads\("""(.*?)"""\)', text, re.DOTALL)
    config = json.loads(payload.group(1))
    # The one singlet whose recorded reference family is unrestricted, and
    # the driver that follows the restricted solution's instability into it.
    assert config["broken_symmetry"] is True
    assert config["reference_family"] == "uks"
    assert "def _broken_symmetry_scf(" in text
    assert "rhf_external" in text


@pytest.mark.parametrize("program", ["gaussian", "orca", "pyscf"])
def test_a_state_the_request_does_not_define_is_refused_by_name(
    tmp_path, program
):
    """The request is the Ms = 0 singlet; a triplet node carrying it is
    refused with the routes that remain, never run without it."""

    result, _text, _path = _fake_run(
        tmp_path, program, REQUEST, multiplicity=3
    )
    assert result.exit_code != 0
    assert "broken_symmetry asks for the open-shell singlet" in str(
        result.exception
    )


# ----------------------------------------------------------------------
# the reference that ran is read from the program's own record
# ----------------------------------------------------------------------

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.mark.capability("tool:inspect_run")
@pytest.mark.parametrize(
    "program,relative,reference",
    [
        # Gaussian's SCF Done label: E(RB3LYP), E(UB3LYP).
        (
            "gaussian",
            "GaussianTests/basis_forms/water_b3lyp_631gd_5d.log",
            "rks",
        ),
        (
            "gaussian",
            "GaussianTests/stability/g_o2_triplet_stable_gas_phase.log",
            "uks",
        ),
        # ORCA's HFTyp line beside its Hamiltonian line.
        ("orca", "ORCATests/spectrum_energy/water_sp.out", "rks"),
        ("orca", "ORCATests/basis_forms/h_mp2_def2svp.out", "uhf"),
        (
            "orca",
            "ORCATests/outputs/orca_methyl_hirshfeld_gas_phase.out",
            "uks",
        ),
    ],
)
def test_a_level_states_the_reference_its_program_ran(
    program, relative, reference
):
    """The Gaussian reader read ``SCF Done: E(UB3LYP)`` and kept only the
    functional, so no result could say which determinant it ran; ORCA's
    printed HFTyp was read by no reader at all."""

    from chemsmart.analysis.result_readers import reader_for

    reader = reader_for(program)
    level = reader.level_for_output(reader.open_output(DATA / relative))
    assert level["reference"] == reference
    assert "broken_symmetry" not in level


@pytest.mark.capability("tool:inspect_run")
def test_an_open_shell_singlet_reads_as_broken_a_closed_shell_as_restricted():
    """An archived Gaussian link job reached the open-shell singlet of O2
    (stable=opt, then guess=read; <S**2> 1.0034): the host reads it as a
    UKS singlet whose spin symmetry broke; a closed-shell RB3LYP result
    has a reference and no spin-symmetry word at all."""

    from chemsmart.analysis.result_readers import reader_for

    reader = reader_for("gaussian")
    singlet = reader.spin_symmetry_for_output(
        reader.open_output(
            DATA
            / "GaussianTests/outputs/link/oxygen_openshell_singlet_opt_link.log"
        )
    )
    assert singlet["reference"] == "uks"
    assert singlet["spin_symmetry"] == "broken"
    assert singlet["spin_square"] == pytest.approx(1.0034)
    closed = reader.spin_symmetry_for_output(
        reader.open_output(
            DATA / "GaussianTests/basis_forms/water_b3lyp_631gd_5d.log"
        )
    )
    assert closed == {"reference": "rks", "broken_symmetry_requested": False}


@pytest.mark.parametrize("program", ["gaussian", "orca", "pyscf"])
def test_the_compile_reply_names_the_mechanism_each_program_runs(program):
    from chemsmart.agent.tool_runtime import compile_time_observations

    observations = compile_time_observations(
        program=program,
        jobtype="sp",
        settings={**REQUEST},
        atom_count=10,
        multiplicity=1,
    )
    (sentence,) = [
        item for item in observations if item.startswith("broken_symmetry:")
    ]
    mechanism = {
        "gaussian": "guess=mix",
        "orca": "GuessMix 45",
        "pyscf": "RHF/RKS -> UHF/UKS instability",
    }[program]
    assert mechanism in sentence
    assert "spin.broken_symmetry_request_unbroken" in sentence


def test_a_restricted_gaussian_mixing_guess_is_named_as_restricted():
    """Q15 g1's route: ``guess=mix`` on a restricted singlet route, which
    the compile reply now says runs restricted."""

    from chemsmart.agent.tool_runtime import compile_time_observations

    observations = compile_time_observations(
        program="gaussian",
        jobtype="opt",
        settings={
            "functional": "b3lyp",
            "basis": "def2-tzvp",
            "additional_route_parameters": "guess=mix",
        },
        atom_count=10,
        multiplicity=1,
    )
    assert any(
        item.startswith("guess=mix on this singlet route runs restricted")
        for item in observations
    ), observations
