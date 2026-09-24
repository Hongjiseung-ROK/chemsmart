"""A node's input check speaks for the compile it read, and for no later one.

ORCA's own input check (the probe) runs at preflight on the previewed
input and is recorded per node; its word rides the compile reply the
model reads, the review the approval freezes, and the executor's launch
check, which refuses a node whose check aborted "on these exact bytes".
The record was written when a check ran and never retired when a later
compile of the same node ran none. In R10 Q15's g1 (CUHK Slurm 2152875) a
session planned ``ts-search`` and ``pbnz-opt`` in ORCA with ``FlipSpin
1,6`` on the simple-input line, which ORCA rejects at its input check,
then re-planned both nodes, under the same ids, in Gaussian, which has no
probe. The compile replies for the Gaussian nodes, the frozen review and
the executor all carried ORCA's refusal of the earlier ORCA bytes, the
executor refused both launches, and the goal returned to the human after
one of eleven approved nodes had run.
"""

from __future__ import annotations

import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from chemsmart.agent._contracts import file_sha256

from .test_a_declared_observable_carries_its_band import _host

# ORCA 6.1.1's own lines for the rejected keyword, as g1's probe recorded them.
_REJECTED = """\
UNRECOGNIZED OR DUPLICATED KEYWORD(S) IN SIMPLE INPUT LINE

INPUT ERROR

FLIPSPIN 1,6
"""


def _retained_preview(retention: Path, name: str, text: str):
    """A preview whose single input the host retained by its digest."""

    retention.mkdir(exist_ok=True)
    source = retention.parent / name
    source.write_text(text)
    digest = file_sha256(source)
    (retention / digest).write_bytes(source.read_bytes())
    return SimpleNamespace(
        status="previewed",
        artifacts=(
            SimpleNamespace(relative_path=f"job/{name}", sha256=digest),
        ),
    )


def _orca_that_rejects(tmp_path: Path) -> Path:
    script = tmp_path / "orca"
    script.write_text("#!/bin/bash\n" f"cat <<'EOF'\n{_REJECTED}EOF\nexit 1\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def _later_compile(kind: str, retention: Path):
    """A later compile of the same node that runs no input check."""

    if kind == "another_program":
        return "gaussian", _retained_preview(
            retention,
            "ts.com",
            "# opt=(ts,calcfc,noeigentest) freq b3lyp def2tzvp\n\nts\n\n0 1\n",
        )
    return "orca", SimpleNamespace(status="failed", artifacts=())


@pytest.mark.capability("rule:compile.the_probe_is_the_programs_check")
@pytest.mark.parametrize("kind", ["another_program", "a_preview_that_failed"])
def test_a_later_compile_retires_the_check_an_earlier_one_earned(
    tmp_path, monkeypatch, kind
):
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    monkeypatch.delenv("PBS_JOBID", raising=False)
    retention = tmp_path / "previews"
    host = _host(
        tmp_path,
        preview_retention_root=retention,
        input_check_executable=_orca_that_rejects(tmp_path),
        input_check_cap_seconds=10.0,
    )
    first = host._probe_input_check(
        "t1",
        node_id="ts-search",
        program="orca",
        safe_preview=_retained_preview(
            retention,
            "ts.inp",
            "! OptTS Freq B3LYP/G def2-tzvp FlipSpin 1,6\n* xyz 0 1\n*\n",
        ),
    )
    assert first.status == "aborted", first.reason
    assert host._probe_observations_for("ts-search")[0].startswith(
        "input-check probe: aborted"
    )

    program, preview = _later_compile(kind, retention)
    host._probe_input_check(
        "t2", node_id="ts-search", program=program, safe_preview=preview
    )

    # The compile reply and the frontier read the accessor; the review the
    # approval freezes reads the record. Neither may carry a check of
    # bytes this compile did not produce.
    assert host._probe_observations_for("ts-search") == ()
    assert "ts-search" not in host._input_check_by_node
