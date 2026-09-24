"""A Hessian named for a TS search or an IRC is the one ORCA reads.

ORCA opens a starting Hessian only when told to -- ``InitHess read`` in
``%irc``, ``InHess Read`` in ``%geom`` -- and ChemSmart wrote the file
into the input only when the project also said so. A Hessian named on
the command line alone, which is how the host hands a saddle's Hessian
to the IRC that walks from it, never reached ORCA: every executed ORCA
TS -> IRC Hessian binding in the archive (six) displaced its IRC along a
Hessian ORCA computed afresh ("Initial displacement Hessian type ....
Compute numerically"), and a TS search named a starting Hessian beside
``Calc_Hess True``, which asks ORCA to compute the very thing it was
handed.

Driven through the public ``run --fake`` command and the planning
session's own preview verifier, on the Hessian and geometry of a real
ORCA saddle (F- + CH3Cl, M06-2X/def2-SVP, archived output).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.agent._contracts import file_sha256
from tests.agent.gaussian_fake_preview import fake_preview

_SADDLE = (
    Path(__file__).resolve().parents[1] / "data" / "ORCATests" / "outputs"
)
_STATE = (-1, 1)


def _preview(tmp_path, jobtype, section, *arguments):
    xyz_text = (_SADDLE / "sn2_ts.xyz").read_text(encoding="utf-8")
    receipt, written = fake_preview(
        tmp_path,
        "orca",
        {jobtype: section},
        xyz_text,
        _STATE,
        jobtype,
        job_arguments=arguments,
    )
    preview_dir = next(
        path.parent
        for path in (tmp_path / "workspace").rglob("*.inp")
        if path.is_file()
    )
    return receipt, written, preview_dir


def _staged(preview_dir: Path, source: Path) -> bool:
    staged = preview_dir / source.name
    return staged.is_file() and file_sha256(staged) == file_sha256(source)


@pytest.mark.capability("program_jobtype:orca:cpu:irc")
@pytest.mark.capability("setting:orca:inithess")
def test_an_irc_given_a_hessian_file_reads_it(tmp_path):
    hessian = _SADDLE / "sn2_ts.hess"

    receipt, written, preview_dir = _preview(
        tmp_path,
        "irc",
        {"functional": "m062x", "basis": "def2-svp", "direction": "forward"},
        "--hess-filename",
        str(hessian),
    )

    assert receipt.status == "valid", [
        (item.field, item.expected, item.observed) for item in receipt.findings
    ]
    assert "inithess read" in written.casefold(), written
    assert 'Hess_Filename "sn2_ts.hess"' in written, written
    assert _staged(
        preview_dir, hessian
    ), "ORCA would find no Hessian beside its input"

    from chemsmart.io.orca.input import ORCAInput

    native = next(preview_dir.glob("*.inp"))
    parsed = ORCAInput(str(native))
    assert parsed.irc_inithess == "read"
    assert parsed.irc_hess_filename == "sn2_ts.hess"


@pytest.mark.capability("program_jobtype:orca:cpu:ts")
def test_a_ts_search_given_a_hessian_file_reads_it_and_computes_none(
    tmp_path,
):
    hessian = _SADDLE / "sn2_ts.hess"

    receipt, written, preview_dir = _preview(
        tmp_path,
        "ts",
        {"functional": "m062x", "basis": "def2-svp"},
        "--inhess-filename",
        str(hessian),
    )

    assert receipt.status == "valid", [
        (item.field, item.expected, item.observed) for item in receipt.findings
    ]
    assert "InHess Read" in written, written
    assert 'InHessName "sn2_ts.hess"' in written, written
    assert "Calc_Hess True" not in written, (
        "a read starting Hessian beside Calc_Hess asks ORCA to compute "
        "the Hessian it was handed"
    )
    assert _staged(preview_dir, hessian)


@pytest.mark.capability("program_jobtype:orca:cpu:ts")
def test_a_ts_search_with_no_hessian_file_still_computes_one(tmp_path):
    receipt, written, _preview_dir = _preview(
        tmp_path, "ts", {"functional": "m062x", "basis": "def2-svp"}
    )

    assert receipt.status == "valid"
    assert "Calc_Hess True" in written
    assert "InHess" not in written


@pytest.mark.capability("setting:orca:inithess")
def test_a_named_file_and_a_computed_start_are_refused_together(tmp_path):
    import numpy as np

    from chemsmart.io.molecules.structure import Molecule
    from chemsmart.jobs.orca.settings import ORCAIRCJobSettings
    from chemsmart.jobs.orca.writer import ORCAInputWriter

    settings = ORCAIRCJobSettings(
        direction="forward",
        inithess="calc_anfreq",
        hess_filename=str(_SADDLE / "sn2_ts.hess"),
    )
    settings.functional = "m062x"
    settings.basis = "def2-svp"
    settings.charge = 0
    settings.multiplicity = 1
    job = type(
        "Job",
        (),
        {
            "settings": settings,
            "molecule": Molecule(
                symbols=["H", "H"],
                positions=np.array([[0.0, 0.0, -0.37], [0.0, 0.0, 0.37]]),
            ),
            "jobrunner": type("Runner", (), {"num_cores": 1, "mem_gb": 1})(),
            "folder": str(tmp_path),
            "label": "branch",
        },
    )()

    with pytest.raises(ValueError, match="calc_anfreq"):
        ORCAInputWriter(job).write()
