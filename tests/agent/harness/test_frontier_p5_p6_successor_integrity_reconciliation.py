"""Focused offline test for the P5/P6 successor-integrity reconciliation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_successor_integrity_reconciliation_validates() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/review/validate_frontier_p5_p6_successor_integrity_reconciliation.py",
            "--repo",
            str(ROOT),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
