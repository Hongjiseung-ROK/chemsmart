from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from chemsmart.gui import frozen_dispatch


def test_source_dispatch_uses_current_interpreter_not_ambient_path(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    command = frozen_dispatch.internal_cli_command(["--version"])

    assert command == [
        sys.executable,
        "-I",
        "-c",
        frozen_dispatch._SOURCE_DISPATCH,
        str(Path(frozen_dispatch.__file__).resolve().parents[2]),
        frozen_dispatch.INTERNAL_CLI_MARKER,
        "--version",
    ]
    assert "chemsmart" not in command[:1]


def test_frozen_dispatch_self_executes_absolute_binary(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    command = frozen_dispatch.internal_cli_command(["run", "--help"])

    assert command == [
        sys.executable,
        frozen_dispatch.INTERNAL_CLI_MARKER,
        "run",
        "--help",
    ]


def test_source_internal_cli_child_runs_with_clean_path(tmp_path):
    command = frozen_dispatch.internal_cli_command(["--version"])
    result = subprocess.run(
        command,
        cwd=tmp_path,
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert "CHEMSMART, version" in result.stdout


def test_source_dispatch_ignores_shadow_package_in_child_workspace(tmp_path):
    shadow = tmp_path / "chemsmart"
    shadow.mkdir()
    (shadow / "__init__.py").write_text(
        "raise RuntimeError('shadow package imported')\n",
        encoding="utf-8",
    )
    command = frozen_dispatch.internal_cli_command(["--version"])

    result = subprocess.run(
        command,
        cwd=tmp_path,
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert "CHEMSMART, version" in result.stdout
    assert "shadow package imported" not in result.stdout
