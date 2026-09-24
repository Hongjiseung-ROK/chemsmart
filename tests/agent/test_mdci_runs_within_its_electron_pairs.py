"""ORCA's MDCI is never asked for more processes than it has electron pairs.

MDCI hands each MPI process a share of the correlated electron pairs and
aborts after the SCF when a process would get none. The host wrote
``%pal nprocs`` from the granted cores whatever the state, and four R10
goals lost approved calls to it: the H atom three times (Q6 pair3-b, Q9 G1,
Q12 g1-hi) and a water monomer and dimer at 32 processes (Q3 g2). The
expected process counts below are ORCA's own numbers from oracle O1 (R10
Q14, CUHK Slurm 2152636, ORCA 6.1.1): each is the pair count ORCA printed,
or for a local (DLPNO) method the diagonal pairs it always keeps.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

pytestmark = pytest.mark.capability("program_jobtype:orca:sp")

GEOMETRIES = {
    "h": "1\nH atom\nH 0.0 0.0 0.0\n",
    "h2": "2\nH2\nH 0.0 0.0 0.0\nH 0.0 0.0 0.7414\n",
    "h2o": (
        "3\nwater\nO 0.0 0.0 0.1173\nH 0.0 0.7572 -0.4692\n"
        "H 0.0 -0.7572 -0.4692\n"
    ),
    "oh": "2\nhydroxyl\nO 0.0 0.0 0.0\nH 0.0 0.0 0.9697\n",
    "li": "1\nLi atom\nLi 0.0 0.0 0.0\n",
    "na": "1\nNa atom\nNa 0.0 0.0 0.0\n",
    "dimer": (
        "6\nwater dimer (R10 Q3 g2)\n"
        "O -0.0159120000 0.0043960000 0.0000020000\n"
        "H 0.9508300000 0.0052000000 -0.0000010000\n"
        "H -0.2650880000 0.9305950000 -0.0000010000\n"
        "O 2.9282420000 -0.0068350000 -0.0000000000\n"
        "H 3.2436640000 -0.4947270000 0.7651980000\n"
        "H 3.2436660000 -0.4947260000 -0.7651980000\n"
    ),
}

CCSDT = {"ab_initio": "ccsd(t)", "basis": "def2-svp"}
CCSDT_UHF = {"ab_initio": "ccsd(t)", "basis": "def2-tzvp", "reference": "uhf"}
DLPNO = {
    "ab_initio": "dlpno-ccsd(t)",
    "basis": "def2-tzvp",
    "aux_basis": "def2-tzvp/c",
}
DLPNO_DIMER = {
    "ab_initio": "dlpno-ccsd(t)",
    "basis": "aug-cc-pvtz",
    "aux_basis": "aug-cc-pvtz/c",
    "ri_approximation": "rijcosx",
}


def _write_input(tmp_path, geometry, settings, charge, multiplicity, cores):
    from chemsmart.agent.live_session import _preview_server_profile
    from chemsmart.cli.main import entry_point

    xyz = tmp_path / f"{geometry}.xyz"
    xyz.write_text(GEOMETRIES[geometry], encoding="utf-8")
    project = tmp_path / "project.yaml"
    project.write_text(yaml.safe_dump({"gas": settings}), encoding="utf-8")
    server = tmp_path / "server.yaml"
    server.write_text(
        _preview_server_profile().replace(
            "NUM_CORES: 4", f"NUM_CORES: {cores}"
        ),
        encoding="utf-8",
    )
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
                "orca",
                "--project",
                str(project),
                "--filename",
                str(xyz),
                "--charge",
                str(charge),
                "--multiplicity",
                str(multiplicity),
                "sp",
            ],
        )
        written = sorted(Path(cwd).glob("*.inp"))
        text = written[0].read_text() if written else ""
    return result, text


@pytest.mark.parametrize(
    "geometry,settings,charge,multiplicity,granted,expected",
    [
        # ORCA: "Number of processes (2) ... exceeds number of pairs (1)"
        ("h2", CCSDT, 0, 1, 2, 1),
        # closed shell, O 1s frozen: 4 correlated orbitals, 10 pairs
        ("h2o", CCSDT, 0, 1, 11, 10),
        # UHF, 7 correlated electrons: 21 pairs
        ("oh", CCSDT_UHF, 0, 2, 22, 21),
        # nothing frozen in Li: 3 electrons, 3 pairs
        ("li", CCSDT_UHF, 0, 2, 4, 3),
        # Na freezes 1s only: 9 electrons, 36 pairs, no change
        ("na", CCSDT_UHF, 0, 2, 2, 2),
        # DLPNO keeps 10 of water's 10 and 27 of the dimer's 36 pairs as
        # CCSD pairs, but only the diagonal ones (4 and 8) are certain
        ("h2o", DLPNO, 0, 1, 11, 4),
        ("dimer", DLPNO_DIMER, 0, 1, 28, 8),
        # not an MDCI method: the grant is written as granted
        ("h2o", {"ab_initio": "hf", "basis": "def2-svp"}, 0, 1, 11, 11),
    ],
)
def test_the_input_asks_mdci_for_no_more_processes_than_pairs(
    tmp_path, geometry, settings, charge, multiplicity, granted, expected
):
    result, text = _write_input(
        tmp_path, geometry, settings, charge, multiplicity, granted
    )
    assert result.exit_code == 0, result.output[-600:]
    (nprocs,) = re.findall(r"%pal nprocs (\d+) end", text)
    assert int(nprocs) == expected
    (maxcore,) = re.findall(r"%maxcore (\d+)", text)
    # the processes that run share the granted memory, never exceed it
    assert int(nprocs) * int(maxcore) <= 0.75 * 4 * 1000


@pytest.mark.parametrize("settings", [CCSDT_UHF, dict(DLPNO, reference="uhf")])
def test_a_state_with_no_electron_pair_is_refused_before_any_input(
    tmp_path, settings
):
    # O1: 1 process "exceeds number of pairs (0)"; DLPNO crashed at 1 and 2
    result, text = _write_input(tmp_path, "h", settings, 0, 2, 1)
    assert result.exit_code != 0
    assert text == ""
    message = str(result.exception)
    assert "identically zero" in message
    assert "PySCF or Gaussian" in message


def test_the_compile_reply_says_what_the_input_runs(tmp_path):
    from chemsmart.agent.tool_runtime import compile_time_observations
    from chemsmart.io.molecules.structure import Molecule

    xyz = tmp_path / "water.xyz"
    xyz.write_text(GEOMETRIES["h2o"], encoding="utf-8")
    water = Molecule.from_filepath(str(xyz))
    (sentence,) = compile_time_observations(
        program="orca",
        jobtype="sp",
        settings=tuple(CCSDT.items()),
        atom_count=3,
        charge=0,
        multiplicity=1,
        granted_cores=32,
        geometry=water,
    )
    assert "10 pairs" in sentence
    assert "runs 10 of the 32 granted processes" in sentence
    assert (
        compile_time_observations(
            program="orca",
            jobtype="sp",
            settings=tuple(CCSDT.items()),
            atom_count=3,
            charge=0,
            multiplicity=1,
            granted_cores=8,
            geometry=water,
        )
        == ()
    )
