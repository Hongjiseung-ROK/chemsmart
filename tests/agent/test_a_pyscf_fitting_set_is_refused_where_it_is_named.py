"""An ORCA-spelled fitting set is refused where a PySCF project names it.

``def2/J`` is ORCA's name for a Coulomb-only fitting set; PySCF has no
basis of that name, and its density fitting fits the exchange with the same
set. The compute interpreter's probe refused it, but only at run time, and
``--fake`` skips that probe: a PySCF preview with ``aux_basis: def2/J``
passed, and the approved node was the first thing to fail (R10 Q12's
finding, CUHK Slurm 2151773). The refusal now happens where the project is
validated, the preview included, and names PySCF's equivalent set.
"""

from __future__ import annotations

import pytest
import yaml
from click.testing import CliRunner

pytestmark = pytest.mark.capability("program_jobtype:pyscf:sp")

WATER = (
    "3\nwater\nO 0.0 0.0 0.1173\nH 0.0 0.7572 -0.4692\n"
    "H 0.0 -0.7572 -0.4692\n"
)


def _preview(tmp_path, aux_basis):
    from chemsmart.agent.live_session import _preview_server_profile
    from chemsmart.cli.main import entry_point

    xyz = tmp_path / "water.xyz"
    xyz.write_text(WATER, encoding="utf-8")
    project = tmp_path / "project.yaml"
    project.write_text(
        yaml.safe_dump(
            {
                "sp": {
                    "functional": "b3lyp",
                    "basis": "def2-svp",
                    "density_fit": True,
                    "aux_basis": aux_basis,
                }
            }
        ),
        encoding="utf-8",
    )
    server = tmp_path / "server.yaml"
    server.write_text(_preview_server_profile(), encoding="utf-8")
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        return runner.invoke(
            entry_point,
            [
                "run",
                "--server",
                str(server),
                "--fake",
                "--no-scratch",
                "pyscf",
                "--project",
                str(project),
                "--filename",
                str(xyz),
                "--charge",
                "0",
                "--multiplicity",
                "1",
                "--no-gpu",
                "sp",
            ],
        )


@pytest.mark.parametrize(
    "aux_basis,route",
    [
        ("def2/J", "def2-universal-jkfit"),
        ("def2/JK", "def2-universal-jkfit"),
        ("def2-TZVP/C", "def2-universal-jkfit"),
        ("AutoAux", "Omit aux_basis"),
    ],
)
def test_an_orca_fitting_set_is_refused_at_preview_with_pyscf_s_name(
    tmp_path, aux_basis, route
):
    result = _preview(tmp_path, aux_basis)
    assert result.exit_code != 0
    message = str(result.exception) + result.output
    assert route in message
    assert "density_fit: false" in message


def test_pyscf_s_own_fitting_set_previews(tmp_path):
    result = _preview(tmp_path, "def2-universal-jkfit")
    assert result.exit_code == 0, result.output[-600:]
