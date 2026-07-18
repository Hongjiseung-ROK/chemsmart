"""Slow end-to-end parity gates for high-risk desktop job routes."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

from chemsmart.gui.application.cli_launcher import (
    DryRunRequest,
    launch_dry_run,
)
from chemsmart.gui.application.task_controller import (
    CancellationToken,
    TaskContext,
)
from chemsmart.gui.frozen_dispatch import internal_cli_command


H4_XYZ = """4
contract H4
H 0 0 0
H 0 0 0.74
H 0 1.5 0
H 0 1.5 0.74
"""


HIGH_RISK_CASES = (
    (
        "gaussian_ts",
        "gaussian",
        ("ts",),
        1,
    ),
    (
        "gaussian_scan",
        "gaussian",
        (
            "scan",
            "--coordinates",
            "[[1,2]]",
            "--step-size",
            "0.05",
            "--num-steps",
            "4",
        ),
        1,
    ),
    (
        "gaussian_modred",
        "gaussian",
        ("modred", "--coordinates", "[[1,2]]"),
        1,
    ),
    (
        "gaussian_td",
        "gaussian",
        (
            "td",
            "--states",
            "singlets",
            "--nstates",
            "5",
            "--root",
            "1",
        ),
        1,
    ),
    (
        "gaussian_dias",
        "gaussian",
        ("dias", "--fragment-indices", "1,2"),
        3,
    ),
    ("gaussian_wbi", "gaussian", ("wbi",), 1),
    ("orca_ts", "orca", ("ts",), 1),
    (
        "orca_scan",
        "orca",
        (
            "scan",
            "--coordinates",
            "[1,2]",
            "--dist-start",
            "0.7",
            "--dist-end",
            "1.0",
            "--num-steps",
            "4",
        ),
        1,
    ),
    (
        "orca_modred",
        "orca",
        ("modred", "--coordinates", "[[1,2]]"),
        1,
    ),
    (
        "orca_neb",
        "orca",
        (
            "neb",
            "--nimages",
            "5",
            "--joboption",
            "NEB-TS",
            "-e",
            "{product}",
            "-i",
            "{guess}",
            "-o",
            "-s",
            "XTB2",
        ),
        1,
    ),
    (
        "orca_neb_restart",
        "orca",
        (
            "neb",
            "--nimages",
            "5",
            "--joboption",
            "NEB",
            "-r",
            "{restart}",
        ),
        1,
    ),
    (
        "orca_aux_basis",
        "orca",
        ("--aux-basis", "def2/J", "opt"),
        1,
    ),
)

REMAINING_LEAF_CASES = (
    (
        "gaussian_com",
        "gaussian",
        "tests/data/GaussianTests/inputs/model_opt_input.com",
        ("com",),
        1,
    ),
    ("gaussian_crest", "gaussian", "{trajectory}", ("crest", "--jobtype", "opt", "--num-confs-to-run", "2"), 2),
    ("gaussian_irc", "gaussian", "{molecule}", ("irc", "--direction", "forward"), 1),
    (
        "gaussian_link",
        "gaussian",
        "tests/data/GaussianTests/outputs/link/oxygen_openshell_singlet_ts_link.log",
        ("link", "--jobtype", "opt"),
        1,
    ),
    ("gaussian_nci", "gaussian", "{molecule}", ("nci",), 1),
    (
        "gaussian_qrc",
        "gaussian",
        "tests/data/GaussianTests/outputs/water_mp2.log",
        ("qrc",),
        2,
    ),
    ("gaussian_resp", "gaussian", "{molecule}", ("resp",), 1),
    ("gaussian_sp", "gaussian", "{molecule}", ("sp",), 1),
    (
        "gaussian_traj",
        "gaussian",
        "{trajectory}",
        ("traj", "--jobtype", "opt", "--num-structures-to-run", "2"),
        1,
    ),
    (
        "gaussian_userjob",
        "gaussian",
        "{molecule}",
        ("userjob", "--route", "# sp b3lyp/6-31g(d)"),
        1,
    ),
    (
        "orca_inp",
        "orca",
        "tests/data/ORCATests/inputs/water_opt.inp",
        ("inp",),
        1,
    ),
    ("orca_irc", "orca", "{molecule}", ("irc",), 1),
    (
        "orca_qrc",
        "orca",
        "tests/data/ORCATests/outputs/water_opt.out",
        ("qrc",),
        2,
    ),
    ("orca_sp", "orca", "{molecule}", ("sp",), 1),
)


@pytest.mark.slow
@pytest.mark.parametrize(
    ("case_name", "program", "leaf_args", "expected_count"),
    HIGH_RISK_CASES,
)
def test_gui_fake_run_matches_direct_cli_bytes_for_high_risk_routes(
    tmp_path,
    monkeypatch,
    case_name,
    program,
    leaf_args,
    expected_count,
) -> None:
    from chemsmart.cli.config import Config

    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    direct_workspace = tmp_path / "direct"
    home.mkdir()
    workspace.mkdir()
    direct_workspace.mkdir()
    monkeypatch.setenv("HOME", str(home))
    Config().ensure_user_config_tree()
    molecule = workspace / "molecule.xyz"
    product = workspace / "product.xyz"
    guess = workspace / "guess.xyz"
    restart = workspace / "restart.allxyz"
    molecule.write_text(H4_XYZ, encoding="utf-8")
    product.write_text(H4_XYZ.replace("0.74", "0.80"), encoding="utf-8")
    guess.write_text(H4_XYZ.replace("0.74", "0.90"), encoding="utf-8")
    restart.write_text(H4_XYZ + H4_XYZ.replace("0.74", "0.82"), encoding="utf-8")
    resolved_leaf = tuple(
        str(product)
        if token == "{product}"
        else str(guess)
        if token == "{guess}"
        else str(restart)
        if token == "{restart}"
        else token
        for token in leaf_args
    )
    argv = (
        "chemsmart",
        "run",
        program,
        "-p",
        "test",
        "-f",
        str(molecule),
        "-c",
        "0",
        "-m",
        "1",
        *resolved_leaf,
    )

    gui_result, _direct = _assert_cli_parity(
        case_name=case_name,
        argv=argv,
        workspace=workspace,
        direct_workspace=direct_workspace,
        home=home,
        expected_count=expected_count,
    )
    if case_name == "orca_neb":
        assert [item.name for item in gui_result.dependencies] == [
            "guess.xyz",
            "product.xyz",
        ]
        assert (direct_workspace / "product.xyz").read_bytes() == product.read_bytes()
        assert (direct_workspace / "guess.xyz").read_bytes() == guess.read_bytes()
        content = gui_result.artifacts[0].content
        assert 'NEB_TS_XYZFILE "guess.xyz"' in content
        assert "PREOPT_ENDS True" in content
        assert "XTB2" in gui_result.artifacts[0].route
    if case_name == "orca_neb_restart":
        assert [item.name for item in gui_result.dependencies] == [
            "restart.allxyz"
        ]
        assert (direct_workspace / "restart.allxyz").read_bytes() == (
            restart.read_bytes()
        )
        assert 'Restart_ALLXYZFile "restart.allxyz"' in (
            gui_result.artifacts[0].content
        )
    if case_name == "orca_aux_basis":
        assert "def2/J" in gui_result.artifacts[0].route


@pytest.mark.slow
@pytest.mark.parametrize(
    ("case_name", "program", "source_ref", "leaf_args", "expected_count"),
    REMAINING_LEAF_CASES,
)
def test_remaining_live_leaves_match_direct_cli_bytes(
    tmp_path,
    monkeypatch,
    case_name,
    program,
    source_ref,
    leaf_args,
    expected_count,
) -> None:
    from chemsmart.cli.config import Config

    repo_root = Path(__file__).resolve().parents[2]
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    direct_workspace = tmp_path / "direct"
    home.mkdir()
    workspace.mkdir()
    direct_workspace.mkdir()
    monkeypatch.setenv("HOME", str(home))
    Config().ensure_user_config_tree()
    molecule = workspace / "molecule.xyz"
    trajectory = workspace / "trajectory.xyz"
    molecule.write_text(H4_XYZ, encoding="utf-8")
    trajectory.write_text(
        H4_XYZ
        + H4_XYZ.replace("0.74", "0.76")
        + H4_XYZ.replace("0.74", "0.78"),
        encoding="utf-8",
    )
    source = {
        "{molecule}": molecule,
        "{trajectory}": trajectory,
    }.get(source_ref, repo_root / source_ref)
    argv = (
        "chemsmart",
        "run",
        program,
        "-p",
        "test",
        "-f",
        str(source),
        "-c",
        "0",
        "-m",
        "1",
        *leaf_args,
    )

    _assert_cli_parity(
        case_name=case_name,
        argv=argv,
        workspace=workspace,
        direct_workspace=direct_workspace,
        home=home,
        expected_count=expected_count,
    )


def _assert_cli_parity(
    *,
    case_name: str,
    argv: tuple[str, ...],
    workspace: Path,
    direct_workspace: Path,
    home: Path,
    expected_count: int,
):
    gui_result = launch_dry_run(
        DryRunRequest(argv=argv, cwd=workspace),
        TaskContext(CancellationToken(), lambda _progress: None),
    )
    direct = subprocess.run(
        internal_cli_command(["run", "--fake", "--no-scratch", *argv[2:]]),
        cwd=direct_workspace,
        env={
            "HOME": str(home),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONUTF8": "1",
            **(
                {"TMPDIR": os.environ["TMPDIR"]}
                if os.environ.get("TMPDIR")
                else {}
            ),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=90,
        check=False,
    )
    direct_inputs = {
        path.name: path.read_bytes()
        for suffix in (".com", ".gjf", ".inp")
        for path in sorted(direct_workspace.glob(f"*{suffix}"))
    }
    gui_inputs = {
        artifact.name: artifact.content.encode("utf-8")
        for artifact in gui_result.artifacts
    }

    assert direct.returncode == 0, (
        case_name,
        direct.stdout.decode("utf-8", errors="replace")[-2000:],
    )
    assert gui_result.returncode == 0
    assert gui_result.semantic.verdict == "ok", (
        case_name,
        gui_result.semantic.failed_rule_ids,
    )
    assert len(gui_inputs) == expected_count
    assert gui_inputs == direct_inputs
    assert not list(workspace.glob(".chemsmart-preview-*"))
    return gui_result, direct
