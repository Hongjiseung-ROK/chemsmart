"""Focused contracts for the selectively ported xTB backend."""

from click.testing import CliRunner
import os
import pytest
import subprocess

from chemsmart.cli.config import Config
from chemsmart.cli.run import run
from chemsmart.cli.sub import sub
from chemsmart.jobs.xtb.hess import XTBHessJob
from chemsmart.jobs.xtb.opt import XTBOptJob
from chemsmart.jobs.xtb.singlepoint import XTBSinglePointJob


WATER_XYZ = """3
water
O 0 0 0
H 0 0 1
H 0 1 0
"""


def test_xtb_help_exposes_exactly_three_reviewed_leaves() -> None:
    result = CliRunner().invoke(run, ["xtb", "--help"])

    assert result.exit_code == 0, result.output
    for leaf in ("opt", "sp", "hess"):
        assert leaf in result.output


def test_xtb_job_types_are_distinct() -> None:
    assert XTBOptJob.TYPE == "xtbopt"
    assert XTBSinglePointJob.TYPE == "xtbsp"
    assert XTBHessJob.TYPE == "xtbhess"


def test_xtb_workspace_project_overrides_packaged_defaults(
    tmp_path,
    monkeypatch,
) -> None:
    from chemsmart.settings.xtb import XTBProjectSettings

    project_dir = tmp_path / ".chemsmart" / "xtb"
    project_dir.mkdir(parents=True)
    (project_dir / "test.yaml").write_text(
        "sp:\n  gfn_version: gfn1\n  charge: 0\n  multiplicity: 1\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert XTBProjectSettings.from_project("test").sp_settings().gfn_version == (
        "gfn1"
    )


def test_xtb_project_state_survives_when_cli_state_is_omitted(
    tmp_path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    Config().ensure_user_config_tree()
    project_dir = tmp_path / ".chemsmart" / "xtb"
    project_dir.mkdir(parents=True)
    (project_dir / "anion.yaml").write_text(
        "sp:\n  charge: -1\n  multiplicity: 2\n",
        encoding="utf-8",
    )
    molecule = tmp_path / "water.xyz"
    molecule.write_text(WATER_XYZ, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        run,
        ["--fake", "--no-scratch", "xtb", "-p", "anion", "-f", str(molecule), "sp"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    output = (tmp_path / "water_sp_fake.out").read_text(encoding="utf-8")
    assert "--chrg -1 --uhf 1" in output


@pytest.mark.parametrize("flag", ["--solvent-model", "--solvent-id"])
def test_xtb_rejects_half_specified_solvation(
    tmp_path,
    monkeypatch,
    flag,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    Config().ensure_user_config_tree()
    molecule = tmp_path / "water.xyz"
    molecule.write_text(WATER_XYZ, encoding="utf-8")
    value = "alpb" if flag == "--solvent-model" else "water"

    result = CliRunner().invoke(
        run,
        ["xtb", "-p", "test", "-f", str(molecule), flag, value, "sp"],
    )

    assert result.exit_code != 0
    assert "requires both --solvent-model and --solvent-id" in result.output


def test_xtb_project_cannot_redirect_leaf_or_use_unknown_method(tmp_path) -> None:
    from chemsmart.settings.xtb import XTBProjectSettings

    redirected = tmp_path / "redirected.yaml"
    redirected.write_text(
        "sp:\n  jobtype: hess\n  gfn_version: gfn1\n",
        encoding="utf-8",
    )
    assert XTBProjectSettings.from_yaml(redirected).sp_settings().jobtype == "sp"

    malformed = tmp_path / "malformed.yaml"
    malformed.write_text(
        "sp:\n  gfn_version: gfn9\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unknown xTB GFN version"):
        XTBProjectSettings.from_yaml(malformed)

    typo = tmp_path / "typo.yaml"
    typo.write_text(
        "sp:\n  gfn_versoin: gfn1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unknown xTB project setting"):
        XTBProjectSettings.from_yaml(typo)


def test_xtb_generated_invariant_rejects_dropped_explicit_solvation(
    tmp_path,
) -> None:
    from chemsmart.agent.harness.generated_invariants import (
        check_generated_input_invariants,
    )

    artifact = tmp_path / "water_sp_fake.xyz"
    artifact.write_text(WATER_XYZ, encoding="utf-8")
    issues = check_generated_input_invariants(
        "chemsmart run xtb -p test -f water.xyz -c 0 -m 1 "
        "--solvent-model alpb --solvent-id water sp",
        [
            {
                "path": str(artifact),
                "software": "xtb",
                "route": "xtb water_sp_fake.xyz --gfn 2 --chrg 0 --uhf 0",
                "content_tail": WATER_XYZ,
                "charge": 0,
                "multiplicity": 1,
                "element_counts": {"H": 2, "O": 1},
            }
        ],
        cwd=str(tmp_path),
    )

    assert "input.xtb.solvent_preservation" in {
        issue.rule_id for issue in issues
    }


@pytest.mark.parametrize(
    ("leaf", "expected_flags"),
    [
        ("opt", "--gfn 2 --opt tight --chrg -1 --uhf 1 --alpb water --grad"),
        ("sp", "--gfn 2 --chrg -1 --uhf 1 --alpb water --grad"),
        ("hess", "--gfn 2 --hess --chrg -1 --uhf 1 --alpb water --grad"),
    ],
)
def test_xtb_fake_run_generates_geometry_and_exact_command(
    tmp_path,
    monkeypatch,
    leaf,
    expected_flags,
) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    home.mkdir()
    workspace.mkdir()
    monkeypatch.setenv("HOME", str(home))
    Config().ensure_user_config_tree()
    molecule = workspace / "water.xyz"
    molecule.write_text(WATER_XYZ, encoding="utf-8")
    monkeypatch.chdir(workspace)
    leaf_args = [leaf]
    if leaf == "opt":
        leaf_args.extend(("--optimization-level", "tight"))

    result = CliRunner().invoke(
        run,
        [
            "--fake",
            "--no-scratch",
            "xtb",
            "-p",
            "test",
            "-f",
            str(molecule),
            "-c",
            "-1",
            "-m",
            "2",
            "-sm",
            "alpb",
            "-si",
            "water",
            "--grad",
            *leaf_args,
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    artifact = workspace / f"water_{leaf}_fake.xyz"
    output = workspace / f"water_{leaf}_fake.out"
    assert artifact.is_file()
    assert artifact.read_text(encoding="utf-8").startswith("3\n")
    assert expected_flags in output.read_text(encoding="utf-8")
    assert not (workspace / f"water_{leaf}_fake.err").exists()
    assert not list(workspace.glob(".chemsmart-preview-*"))


def test_xtb_real_runner_is_never_selected_by_desktop_request(tmp_path) -> None:
    from chemsmart.gui.application.cli_launcher import DryRunRequest

    molecule = tmp_path / "water.xyz"
    molecule.write_text(WATER_XYZ, encoding="utf-8")
    with pytest.raises(ValueError, match="launcher-owned"):
        DryRunRequest(
            argv=(
                "chemsmart",
                "run",
                "--no-fake",
                "xtb",
                "-p",
                "test",
                "-f",
                str(molecule),
                "-c",
                "0",
                "-m",
                "1",
                "sp",
            ),
            cwd=tmp_path,
        )


def test_xtb_submission_test_mode_preserves_cli_backend(
    tmp_path,
    server_yaml_file,
    monkeypatch,
) -> None:
    molecule = tmp_path / "water.xyz"
    molecule.write_text(WATER_XYZ, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        sub,
        [
            "-s",
            server_yaml_file,
            "--test",
            "xtb",
            "-p",
            "test",
            "-f",
            str(molecule),
            "sp",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    run_script = tmp_path / "chemsmart_run_water_sp.py"
    submit_script = tmp_path / "chemsmart_sub_water_sp.sh"
    assert run_script.is_file()
    assert submit_script.is_file()
    assert "'--test'" not in run_script.read_text(encoding="utf-8")
    assert "'xtb'" in run_script.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("leaf", "leaf_args"),
    [
        ("opt", ("opt", "--optimization-level", "tight")),
        ("sp", ("sp",)),
        ("hess", ("hess",)),
    ],
)
def test_xtb_gui_artifact_matches_direct_cli_bytes(
    tmp_path,
    monkeypatch,
    leaf,
    leaf_args,
) -> None:
    from chemsmart.gui.application.cli_launcher import (
        DryRunRequest,
        launch_dry_run,
    )
    from chemsmart.gui.application.task_controller import (
        CancellationToken,
        TaskContext,
    )
    from chemsmart.gui.frozen_dispatch import internal_cli_command

    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    direct_workspace = tmp_path / "direct"
    home.mkdir()
    workspace.mkdir()
    direct_workspace.mkdir()
    monkeypatch.setenv("HOME", str(home))
    Config().ensure_user_config_tree()
    molecule = workspace / "water.xyz"
    molecule.write_text(WATER_XYZ, encoding="utf-8")
    argv = (
        "chemsmart",
        "run",
        "xtb",
        "-p",
        "test",
        "-f",
        str(molecule),
        "-c",
        "0",
        "-m",
        "1",
        *leaf_args,
    )

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
    direct_artifact = direct_workspace / f"water_{leaf}_fake.xyz"

    assert direct.returncode == 0, direct.stdout.decode(
        "utf-8", errors="replace"
    )[-2000:]
    assert gui_result.semantic.verdict == "ok"
    assert len(gui_result.artifacts) == 1
    assert gui_result.artifacts[0].software == "xtb"
    assert "--chrg 0 --uhf 0" in gui_result.artifacts[0].route
    assert gui_result.artifacts[0].charge == 0
    assert gui_result.artifacts[0].multiplicity == 1
    assert gui_result.artifacts[0].content.encode("utf-8") == (
        direct_artifact.read_bytes()
    )
    assert gui_result.dependencies == ()
    assert not list(workspace.glob(".chemsmart-preview-*"))
