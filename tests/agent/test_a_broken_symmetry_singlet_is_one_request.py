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
