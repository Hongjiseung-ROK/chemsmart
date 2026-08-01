"""Focused offline validation for the P4 archive non-admission triage."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_p4_archived_result_triage_validates() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/review/validate_frontier_p4_archived_result_triage.py",
            "--repo",
            str(ROOT),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
