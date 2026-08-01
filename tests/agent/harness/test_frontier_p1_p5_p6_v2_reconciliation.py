"""Focused offline validation for the post-P3 v2 P1/P5/P6 reconciliation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_p1_p5_p6_v2_reconciliation_validates() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/review/validate_frontier_p1_p5_p6_v2_reconciliation.py",
            "--repo",
            str(ROOT),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
