"""Safety contracts for the explicit desktop CLI child boundary."""

from __future__ import annotations

import subprocess

import pytest

from chemsmart.gui.application import cli_launcher
from chemsmart.gui.application.task_controller import (
    CancellationToken,
    TaskContext,
)


class _CompletedProcess:
    def __init__(self) -> None:
        self.returncode = 0
        self.terminated = False
        self.killed = False

    def communicate(self, timeout=None):
        return "fake input generated\n", None

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
    request = cli_launcher.DryRunRequest(
        argv=("chemsmart", "run", "gaussian", "opt"),
        cwd=tmp_path,
    )

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
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
        "opt",
    ]
    assert captured["cwd"] == tmp_path
    assert captured["env"]["PATH"] == "/usr/bin:/bin:/usr/sbin:/sbin"
    assert "OPENAI_API_KEY" not in captured["env"]
    assert "CHEMSMART_API_ENV" not in captured["env"]
    assert result.returncode == 0
    assert result.output == "fake input generated\n"
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
