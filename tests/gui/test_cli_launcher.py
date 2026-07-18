"""Safety contracts for the explicit desktop CLI child boundary."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess

import pytest

from chemsmart.gui.application import cli_launcher
from chemsmart.gui.application.task_controller import (
    CancellationToken,
    TaskCancelled,
    TaskContext,
)
from chemsmart.gui.frozen_dispatch import internal_cli_command


WATER_XYZ = """3
water
O  0.000000  0.000000  0.000000
H  0.758602  0.000000  0.504284
H -0.758602  0.000000  0.504284
"""


class _CompletedProcess:
    def __init__(self) -> None:
        self.returncode = 0
        self.terminated = False
        self.killed = False

    def communicate(self, timeout=None):
        return None, None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


@pytest.mark.parametrize(
    "argv",
    [
        ("chemsmart", "sub", "gaussian", "opt"),
        ("chemsmart", "run", "--fake", "gaussian", "opt"),
        ("chemsmart", "run", "--no-scratch", "gaussian", "opt"),
        ("chemsmart", "run", "xtb", "opt"),
        ("untrusted", "run", "gaussian", "opt"),
    ],
)
def test_dry_run_request_rejects_unsafe_or_unsupported_argv(tmp_path, argv):
    with pytest.raises(ValueError):
        cli_launcher.DryRunRequest(argv=argv, cwd=tmp_path)


def test_launcher_uses_absolute_dispatch_minimal_env_and_owned_flags(
    tmp_path, monkeypatch
) -> None:
    captured = {}
    process = _CompletedProcess()
    molecule = tmp_path / "water.xyz"
    molecule.write_text(WATER_XYZ, encoding="utf-8")
    request = cli_launcher.DryRunRequest(
        argv=(
            "chemsmart",
            "run",
            "gaussian",
            "-p",
            "test",
            "-f",
            str(molecule),
            "-c",
            "0",
            "-m",
            "1",
            "opt",
        ),
        cwd=tmp_path,
    )

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        workdir = Path(kwargs["cwd"])
        (workdir / "water_opt_fake.com").write_text(
            "# opt b3lyp/6-31g(d)\n\nwater\n\n0 1\n"
            "O 0 0 0\nH 0 0 1\nH 0 1 0\n\n",
            encoding="utf-8",
        )
        kwargs["stdout"].write(b"fake input generated\n")
        return process

    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("CHEMSMART_API_ENV", "/must/not/leak")
    monkeypatch.setattr(
        cli_launcher,
        "internal_cli_command",
        lambda args: ["/absolute/ChemSmart", "--chemsmart-internal-cli", *args],
    )
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    progress = []
    context = TaskContext(CancellationToken(), progress.append)

    result = cli_launcher.launch_dry_run(request, context)

    assert captured["command"] == [
        "/absolute/ChemSmart",
        "--chemsmart-internal-cli",
        "run",
        "--fake",
        "--no-scratch",
        "gaussian",
        "-p",
        "test",
        "-f",
        str(molecule),
        "-c",
        "0",
        "-m",
        "1",
        "opt",
    ]
    assert Path(captured["cwd"]).parent == tmp_path
    assert Path(captured["cwd"]).name.startswith(".chemsmart-preview-")
    assert not Path(captured["cwd"]).exists()
    assert captured["env"]["PATH"] == "/usr/bin:/bin:/usr/sbin:/sbin"
    assert captured["start_new_session"] is True
    assert "OPENAI_API_KEY" not in captured["env"]
    assert "CHEMSMART_API_ENV" not in captured["env"]
    assert result.returncode == 0
    assert result.output == "fake input generated\n"
    assert result.semantic.verdict == "ok"
    assert len(result.artifacts) == 1
    assert result.artifacts[0].name == "water_opt_fake.com"
    assert result.artifacts[0].sha256 == hashlib.sha256(
        result.artifacts[0].content.encode("utf-8")
    ).hexdigest()
    assert progress[-1].indeterminate


def test_dry_run_request_strictly_rejects_unknown_leaf_option(tmp_path) -> None:
    with pytest.raises(ValueError, match="Invalid ChemSmart"):
        cli_launcher.DryRunRequest(
            argv=(
                "chemsmart",
                "run",
                "gaussian",
                "opt",
                "--not-a-real-option",
                "value",
            ),
            cwd=tmp_path,
        )


@pytest.mark.parametrize(
    ("program", "kind", "rule"),
    [
        ("gaussian", "scan", "scan_required_parameters"),
        ("orca", "scan", "scan_required_parameters"),
        ("gaussian", "traj", "traj_jobtype_required"),
        ("gaussian", "dias", "dias_fragment_indices_required"),
        ("gaussian", "userjob", "required fields: route"),
    ],
)
def test_dry_run_rejects_missing_leaf_contract_fields(
    tmp_path,
    program,
    kind,
    rule,
) -> None:
    molecule = tmp_path / "water.xyz"
    molecule.write_text(WATER_XYZ, encoding="utf-8")
    with pytest.raises(ValueError, match=rule):
        cli_launcher.DryRunRequest(
            argv=(
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
                kind,
            ),
            cwd=tmp_path,
        )


def test_stop_process_escalates_after_bounded_terminate() -> None:
    class HungProcess(_CompletedProcess):
        def __init__(self):
            super().__init__()
            self.returncode = None
            self.calls = 0

        def poll(self):
            return None

        def communicate(self, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("fake", timeout)
            self.returncode = -9
            return "", None

    process = HungProcess()

    cli_launcher._stop_process(process)

    assert process.terminated
    assert process.killed


def test_cancellation_terminates_child_and_cleans_isolated_workspace(
    tmp_path,
    monkeypatch,
) -> None:
    molecule = tmp_path / "water.xyz"
    molecule.write_text(WATER_XYZ, encoding="utf-8")
    token = CancellationToken()
    captured = {}

    class HangingProcess(_CompletedProcess):
        def __init__(self):
            super().__init__()
            self.returncode = None
            self.calls = 0

        def poll(self):
            return self.returncode

        def communicate(self, timeout=None):
            self.calls += 1
            if self.calls == 1:
                token.cancel()
                raise subprocess.TimeoutExpired("fake", timeout)
            self.returncode = -15
            return None, None

    process = HangingProcess()

    def fake_popen(_command, **kwargs):
        captured["cwd"] = Path(kwargs["cwd"])
        return process

    request = cli_launcher.DryRunRequest(
        argv=(
            "chemsmart",
            "run",
            "gaussian",
            "-p",
            "test",
            "-f",
            str(molecule),
            "-c",
            "0",
            "-m",
            "1",
            "opt",
        ),
        cwd=tmp_path,
    )
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    with pytest.raises(TaskCancelled):
        cli_launcher.launch_dry_run(request, TaskContext(token, lambda _p: None))

    assert process.terminated
    assert not captured["cwd"].exists()


def test_timeout_terminates_child_and_cleans_isolated_workspace(
    tmp_path,
    monkeypatch,
) -> None:
    molecule = tmp_path / "water.xyz"
    molecule.write_text(WATER_XYZ, encoding="utf-8")
    captured = {}

    class TimedOutProcess(_CompletedProcess):
        def __init__(self):
            super().__init__()
            self.returncode = None
            self.calls = 0

        def poll(self):
            return self.returncode

        def communicate(self, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("fake", timeout)
            self.returncode = -15
            return None, None

    process = TimedOutProcess()

    def fake_popen(_command, **kwargs):
        captured["cwd"] = Path(kwargs["cwd"])
        return process

    request = cli_launcher.DryRunRequest(
        argv=(
            "chemsmart",
            "run",
            "gaussian",
            "-p",
            "test",
            "-f",
            str(molecule),
            "-c",
            "0",
            "-m",
            "1",
            "opt",
        ),
        cwd=tmp_path,
        timeout_s=0.0001,
    )
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    with pytest.raises(TimeoutError):
        cli_launcher.launch_dry_run(
            request,
            TaskContext(CancellationToken(), lambda _p: None),
        )

    assert process.terminated
    assert not captured["cwd"].exists()


def test_process_output_is_bounded_and_artifact_limit_cleans_workspace(
    tmp_path,
    monkeypatch,
) -> None:
    molecule = tmp_path / "water.xyz"
    molecule.write_text(WATER_XYZ, encoding="utf-8")
    captured = {}
    process = _CompletedProcess()

    def fake_popen(_command, **kwargs):
        workdir = Path(kwargs["cwd"])
        captured["cwd"] = workdir
        (workdir / "water_opt_fake.com").write_text(
            "# opt b3lyp/6-31g(d)\n\nwater\n\n0 1\n"
            "O 0 0 0\nH 0 0 1\nH 0 1 0\n\n",
            encoding="utf-8",
        )
        kwargs["stdout"].write(b"x" * (cli_launcher._MAX_OUTPUT_BYTES + 100))
        return process

    request = cli_launcher.DryRunRequest(
        argv=(
            "chemsmart",
            "run",
            "gaussian",
            "-p",
            "test",
            "-f",
            str(molecule),
            "-c",
            "0",
            "-m",
            "1",
            "opt",
        ),
        cwd=tmp_path,
    )
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    result = cli_launcher.launch_dry_run(
        request,
        TaskContext(CancellationToken(), lambda _p: None),
    )

    assert result.output_truncated
    assert result.output.startswith("… earlier process output omitted …")
    assert len(result.output.encode("utf-8")) < cli_launcher._MAX_OUTPUT_BYTES + 100
    assert not captured["cwd"].exists()

    monkeypatch.setattr(cli_launcher, "_MAX_ARTIFACT_BYTES", 32)
    with pytest.raises(RuntimeError, match="(?:safety|file) limit"):
        cli_launcher.launch_dry_run(
            request,
            TaskContext(CancellationToken(), lambda _p: None),
        )
    assert not captured["cwd"].exists()


def test_generated_input_size_is_rejected_before_file_open(
    tmp_path,
    monkeypatch,
) -> None:
    from chemsmart.agent.harness.safe_runtime import generated_inputs

    artifact = tmp_path / "oversized.com"
    artifact.write_bytes(b"x" * 64)
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        if path == artifact:
            raise AssertionError("oversized generated input was opened")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    with pytest.raises(RuntimeError, match="file limit"):
        generated_inputs(
            tmp_path,
            {},
            software="gaussian",
            max_file_bytes=32,
        )


def test_dependency_size_is_rejected_before_file_open(
    tmp_path,
    monkeypatch,
) -> None:
    dependency = tmp_path / "oversized.xyz"
    dependency.write_bytes(b"x" * 64)
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        if path == dependency:
            raise AssertionError("oversized dependency was opened")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(cli_launcher, "_MAX_DEPENDENCY_BYTES", 32)
    with pytest.raises(RuntimeError, match="safety limit"):
        cli_launcher._capture_dependencies(tmp_path)


def test_artifact_capture_rechecks_size_before_second_read(
    tmp_path,
    monkeypatch,
) -> None:
    artifact = tmp_path / "oversized.com"
    artifact.write_bytes(b"x" * 64)
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        if path == artifact:
            raise AssertionError("oversized artifact was opened")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(cli_launcher, "_MAX_ARTIFACT_BYTES", 32)
    with pytest.raises(RuntimeError, match="safety limit"):
        cli_launcher._capture_artifacts(
            tmp_path,
            [{"path": str(artifact), "software": "gaussian"}],
        )


@pytest.mark.parametrize(
    ("program", "suffix", "project_yaml", "route_marker"),
    [
        (
            "gaussian",
            ".com",
            "gas:\n  functional: pbe0\n  basis: 6-31g(d)\n"
            "solv:\n  functional: pbe0\n  basis: 6-31g(d)\n",
            "pbe0 6-31g(d)",
        ),
        (
            "orca",
            ".inp",
            "gas:\n  functional: pbe0\n  basis: def2-svp\n"
            "solv:\n  functional: pbe0\n  basis: def2-svp\n",
            "PBE0 def2-SVP",
        ),
        (
            "xtb",
            ".xyz",
            "opt:\n  gfn_version: gfn1\n",
            "--gfn 1",
        ),
    ],
)
def test_gui_self_dispatch_matches_direct_cli_fake_input_bytes(
    tmp_path,
    monkeypatch,
    program,
    suffix,
    project_yaml,
    route_marker,
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
    molecule = workspace / "water.xyz"
    molecule.write_text(WATER_XYZ, encoding="utf-8")
    for root in (workspace, direct_workspace):
        project_dir = root / ".chemsmart" / program
        project_dir.mkdir(parents=True)
        (project_dir / "workspace-only.yaml").write_text(
            project_yaml,
            encoding="utf-8",
        )
    argv = (
        "chemsmart",
        "run",
        program,
        "-p",
        "workspace-only",
        "-f",
        str(molecule),
        "-c",
        "0",
        "-m",
        "1",
        "opt",
    )
    context = TaskContext(CancellationToken(), lambda _progress: None)

    gui_result = cli_launcher.launch_dry_run(
        cli_launcher.DryRunRequest(argv=argv, cwd=workspace),
        context,
    )
    direct_command = internal_cli_command(
        ["run", "--fake", "--no-scratch", *argv[2:]]
    )
    direct = subprocess.run(
        direct_command,
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
    direct_artifact = direct_workspace / f"water_opt_fake{suffix}"

    assert direct.returncode == 0, direct.stdout.decode(
        "utf-8", errors="replace"
    )[-2000:]
    assert gui_result.returncode == 0
    assert gui_result.semantic.verdict == "ok"
    assert len(gui_result.artifacts) == 1
    assert gui_result.artifacts[0].content.encode("utf-8") == (
        direct_artifact.read_bytes()
    )
    assert route_marker.lower() in gui_result.artifacts[0].route.lower()
    assert gui_result.artifacts[0].sha256 == hashlib.sha256(
        direct_artifact.read_bytes()
    ).hexdigest()
    assert gui_result.dependencies == ()
    assert list(workspace.glob(".chemsmart-preview-*")) == []
