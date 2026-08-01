"""Offline contract test for the Frontier Agent program charter."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_frontier_agent_program_artifacts_validate() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/review/validate_frontier_program.py",
            "--repo",
            str(ROOT),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
