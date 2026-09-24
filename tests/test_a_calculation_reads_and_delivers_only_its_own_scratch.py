"""A calculation's scratch is its own: nothing an earlier run left is read or delivered.

The Agent's executor launches every node as ``python -m chemsmart run
--scratch --delete-scratch --server <execution profile> <program> ...`` in
an empty branch folder, and the host binds every file that folder holds
afterwards as that node's output. The runner used to stage the engine in
``<scratch_root>/<label>``. A label is the input's stem, the job type and
the solvent -- not the node, the method, the charge or the multiplicity --
and scratch was deleted only after a *complete* run, so a failed run left
its files for the next run of the same label:

- ORCA's AutoStart read the failed run's ``.gbw`` as the next run's guess
  ("GBW file was renamed to GES file ... Guess is set to MORead"), an input
  no record named (R10 Q6 pair3-b, CUHK Slurm 2150179: cycle-1 ``h-sp-dft``,
  wB97X-D3BJ on the H atom, started from ``h-sp``'s DLPNO/UHF orbitals);
- the copy-back delivered the failed run's ``.gbw``, ``.property.txt``,
  orbital files and integrals into the next run's branch, where the host
  bound them as that node's outputs (cycle-3 ``rad-sp-cc-r3`` died at
  ORCA's input check and held cycle 2's files, 5 GB of them).

This drives the executor's own command line twice, with one label, one
scratch root and two branch folders, against a stand-in for the engine
that does only the two things ORCA does that matter here: it reads a
``.gbw`` of its basename if one is in its working directory, and a failed
run leaves its files behind.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import chemsmart

#: ORCA's AutoStart and ORCA's leftovers, and nothing else. The route line
#: is the run's fingerprint: whatever it writes carries it.
_ENGINE = r"""#!/bin/bash
inp="$1"
base="${inp%.inp}"
if [ -f "$base.gbw" ]; then
  echo "AutoStart read: $(cat "$base.gbw")"
  mv "$base.gbw" "$base.ges"
fi
route="$(grep -m1 '^!' "$inp")"
echo "$route" > "$base.gbw"
echo "$route" > "$base.property.txt"
echo "$route" > "$base.PNO4.tmp.0"
if echo "$route" | grep -qiw hf; then
  echo "ORCA finished by error termination in SCF"
  exit 1
fi
rm -f "$base".*.tmp.*
echo "****ORCA TERMINATED NORMALLY****"
"""


def _profile(tmp_path: Path) -> Path:
    engine_folder = tmp_path / "orca"
    engine_folder.mkdir()
    engine = engine_folder / "orca"
    engine.write_text(_ENGINE)
    engine.chmod(engine.stat().st_mode | stat.S_IXUSR)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    profile = tmp_path / "execution-server.yaml"
    profile.write_text(
        "SERVER:\n"
        "  SCHEDULER: null\n"
        "  NUM_HOURS: 1\n"
        "  MEM_GB: 2\n"
        "  NUM_CORES: 1\n"
        "  NUM_GPUS: 0\n"
        "  NUM_THREADS: 1\n"
        f"  SCRATCH_DIR: {str(scratch)!r}\n"
        "ORCA:\n"
        f"  EXEFOLDER: {str(engine_folder)!r}\n"
        "  LOCAL_RUN: true\n"
        "  SCRATCH: true\n"
    )
    return profile


def _run(tmp_path: Path, profile: Path, branch: str, method: str):
    """One node, launched the way the executor launches it."""

    folder = tmp_path / branch
    folder.mkdir()
    project = tmp_path / f"{branch}.yaml"
    project.write_text(f"gas:\n  {method}\n  basis: def2-svp\n")
    geometry = tmp_path / "h2.xyz"
    if not geometry.exists():
        geometry.write_text("2\nH2\nH 0.0 0.0 0.0\nH 0.0 0.0 0.74\n")
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(chemsmart.__file__).parents[1])
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "chemsmart",
            "run",
            "--no-fake",
            "--delete-scratch",
            "--scratch",
            "--server",
            str(profile),
            "orca",
            "--project",
            str(project),
            "--filename",
            str(geometry),
            "--charge",
            "0",
            "--multiplicity",
            "1",
            "sp",
        ],
        cwd=folder,
        env=environment,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return folder, completed


def _fingerprinted(folder: Path, route_fragment: str) -> list[str]:
    """Files in a branch that carry another run's fingerprint."""

    return sorted(
        path.name
        for path in folder.iterdir()
        if path.is_file()
        and path.suffix != ".inp"
        and route_fragment in path.read_text(errors="replace").casefold()
    )


@pytest.mark.capability("program_jobtype:orca:cpu:sp")
def test_a_later_run_of_one_label_neither_reads_nor_delivers_an_earlier_one(
    tmp_path,
):
    profile = _profile(tmp_path)
    failed, first = _run(tmp_path, profile, "node-a", "ab_initio: hf")
    assert first.returncode != 0, first.stdout + first.stderr
    later, second = _run(tmp_path, profile, "node-b", "functional: b3lyp")
    assert second.returncode == 0, second.stdout + second.stderr

    outputs = sorted(later.glob("*.out"))
    assert outputs, sorted(path.name for path in later.iterdir())
    engine_text = outputs[0].read_text()
    # The engine read nothing the earlier run wrote.
    assert "AutoStart read" not in engine_text, engine_text
    # And the branch holds nothing the earlier run wrote.
    assert _fingerprinted(later, "hf def2-svp") == []
    # The failed run's own record is where it was.
    assert _fingerprinted(failed, "hf def2-svp")


@pytest.mark.capability("program_jobtype:orca:cpu:sp")
def test_a_failed_runs_numbered_temporaries_stay_in_scratch(tmp_path):
    """ORCA's per-rank temporaries are scratch, not evidence.

    The copy-back meant to leave them behind tested
    ``endswith((".tmp", ".tmp.*"))``, whose second member is a literal
    string, so ``<base>.PNO4.tmp.0`` and its siblings came back: 9.9 GB of
    DLPNO pair integrals under /project for one failed node, each file then
    hashed and bound as that node's output (R10 Q6 pair3-b).
    """

    profile = _profile(tmp_path)
    failed, first = _run(tmp_path, profile, "node-a", "ab_initio: hf")
    assert first.returncode != 0, first.stdout + first.stderr

    names = sorted(path.name for path in failed.iterdir())
    assert [name for name in names if ".tmp" in name] == [], names
    # What the failed run wrote as its record still arrives.
    assert any(name.endswith(".gbw") for name in names), names
    assert any(name.endswith(".out") for name in names), names
