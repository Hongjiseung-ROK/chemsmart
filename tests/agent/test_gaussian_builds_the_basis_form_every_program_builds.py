"""Gaussian is told the angular form ORCA and PySCF build a basis in.

Gaussian builds 3-21G, 6-21G, 4-31G, the 6-31G family, CEP-31G, D95 and
D95V from Cartesian d functions unless told otherwise (and CEP-31G from
Cartesian f: told ``5D`` alone it printed ``(5D, 10F)``); ORCA has spherical
harmonics only and PySCF builds spherical ones.  Before R10 Q12 the writer
said nothing, so ``6-31G(d)`` was 34 functions for CH2O in Gaussian and 32
in the others, 0.25-4.1 mEh lower across eight species (CUHK Slurm
2151772).  Driven through the public ``run --fake``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

WATER = (
    "3\nwater\nO 0.0 0.0 0.1173\nH 0.0 0.7572 -0.4692\nH 0.0 -0.7572 -0.4692\n"
)


def _written_route(tmp_path, section):
    from chemsmart.agent.live_session import _preview_server_profile
    from chemsmart.cli.main import entry_point

    project = tmp_path / "project.yaml"
    project.write_text(yaml.safe_dump({"gas": section}), encoding="utf-8")
    xyz = tmp_path / "water.xyz"
    xyz.write_text(WATER, encoding="utf-8")
    server = tmp_path / "server.yaml"
    server.write_text(_preview_server_profile(), encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=workspace) as cwd:
        result = runner.invoke(
            entry_point,
            [
                "run",
                "--server",
                str(server),
                "--fake",
                "--no-scratch",
                "gaussian",
                "--project",
                str(project),
                "--filename",
                str(xyz),
                "--charge",
                "0",
                "--multiplicity",
                "1",
                "sp",
            ],
        )
        assert result.exit_code == 0, (result.output[-600:], result.exception)
        written = next(Path(cwd).rglob("*.com")).read_text(encoding="utf-8")
    return next(line for line in written.splitlines() if line.startswith("#"))


@pytest.mark.capability("setting:gaussian:basis")
@pytest.mark.parametrize(
    "section, spherical",
    (
        ({"functional": "b3lyp", "basis": "6-31G(d)"}, True),
        ({"ab_initio": "mp2", "basis": "6-31+G(d,p)"}, True),
        ({"functional": "b3lyp", "basis": "CEP-31G"}, True),
        ({"functional": "b3lyp", "basis": "6-311+G(d,p)"}, False),
        ({"functional": "b3lyp", "basis": "def2-SVP"}, False),
        (
            {
                "functional": "b3lyp",
                "basis": "6-31G(d)",
                "additional_route_parameters": "6d",
            },
            False,
        ),
    ),
)
def test_gaussian_is_told_the_form_every_program_builds(
    tmp_path, section, spherical
):
    route = _written_route(tmp_path, section).lower().split()

    assert ("5d" in route) is spherical
    assert ("7f" in route) is spherical
    if "additional_route_parameters" in section:
        assert "6d" in route
