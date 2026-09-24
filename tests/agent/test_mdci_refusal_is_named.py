"""ORCA's MDCI refusal of its process count is named as its own class.

It fell through to ``native_runtime``, a class that names no cause, on
every live instance (R10 Q6 pair3-b, Q9 G1, Q12 g1-hi, Q3 g2). The
fixture is an excerpt of Q9 G1's real output (CUHK Slurm 2150438).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.io.native_failure import summarize_orca_native_failure

pytestmark = pytest.mark.capability("program_jobtype:orca:sp")


def test_mdci_s_own_refusal_is_named_as_its_own_class():
    lines = (
        Path("tests/data/agent/native_failures")
        / "orca_mdci_processes_exceed_pairs.txt"
    ).read_text(encoding="utf-8")
    summary = summarize_orca_native_failure(lines.splitlines())
    assert summary.error_class == "mdci_processes_exceed_pairs"
    assert summary.engine_lines[0].startswith(
        "Error (ORCA_MDCI): Number of processes (8)"
    )
