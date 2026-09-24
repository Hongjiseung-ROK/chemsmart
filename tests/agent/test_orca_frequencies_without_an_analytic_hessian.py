"""A project's frequencies reach ORCA as NumFreq where ORCA has no Hessian.

ORCA 6.1.1's input check refuses ``Freq`` for MP2, RI-MP2 and the double
hybrids ("MP2 analytic Hessian calculations are not implemented - please
use NumFreq"; R10 Q14 oracle O1, CUHK Slurm 2152636), and R10 Q3 g1 lost a
cycle to it. The project's ``freq: true`` asks for harmonic frequencies,
which ORCA computes for these methods only numerically, so the writer asks
for NumFreq, the preview verifier reads the two spellings as one request,
and the compile reply says what the input does.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

pytestmark = [
    pytest.mark.capability("program_jobtype:orca:cpu:opt"),
    pytest.mark.capability("setting:orca:freq"),
]

WATER = (
    "3\nwater\nO 0.0 0.0 0.1173\nH 0.0 0.7572 -0.4692\n"
    "H 0.0 -0.7572 -0.4692\n"
)


def _preview(tmp_path, section, jobtype="opt"):
    """Validate the project, preview it through the public CLI, verify it."""

    from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
    from chemsmart.agent.capabilities import (
        ProgramCapabilityQueryV1,
        build_command_compiled_preview_overlay,
        build_program_component_conformance_receipt,
        load_program_capabilities,
        query_capability,
    )
    from chemsmart.agent.cli_schema import build_live_click_schema
    from chemsmart.agent.live_session import _preview_server_profile
    from chemsmart.agent.program_verifiers import (
        build_preview_expectation,
        validate_preview_workspace,
    )
    from chemsmart.agent.projects import validate_project_yaml
    from chemsmart.cli.main import entry_point

    xyz = tmp_path / "water.xyz"
    xyz.write_text(WATER, encoding="utf-8")
    project = tmp_path / "project.yaml"
    project.write_text(yaml.safe_dump({"gas": section}), encoding="utf-8")
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
                "orca",
                "--project",
                str(project),
                "--filename",
                str(xyz),
                "--charge",
                "0",
                "--multiplicity",
                "1",
                jobtype,
            ],
        )
        preview_dir = Path(cwd)
        (written,) = sorted(preview_dir.glob("*.inp"))
        route = written.read_text().splitlines()[0]
    assert result.exit_code == 0, result.output[-600:]

    registry = load_program_capabilities()
    live_schema = build_live_click_schema()
    conformance = build_program_component_conformance_receipt(
        program="orca",
        registry_sha256=registry.registry_sha256,
        live_cli_schema_sha256=live_schema.schema_sha256,
        fixture_bundle_sha256="1" * 64,
        covered_jobtypes=(jobtype,),
        covered_engines=("cpu",),
        covered_engine_job_pairs=(("cpu", jobtype),),
        compiler_receipt_sha256="2" * 64,
        preview_receipt_sha256="3" * 64,
        preflight_receipt_sha256="4" * 64,
        verifier_receipt_sha256="5" * 64,
        compiler_status="passed",
        preview_status="passed",
        preflight_status="passed",
        verifier_status="passed",
    )
    overlay = build_command_compiled_preview_overlay(
        registry, conformance_receipts=(conformance,), live_schema=live_schema
    )
    capability = query_capability(
        ProgramCapabilityQueryV1("orca", jobtype, "cpu"),
        registry=registry,
        live_schema=live_schema,
        overlay=overlay,
    )

    def _artifact(path, kind):
        return TrustedArtifactRefV1(
            artifact_id=path.stem,
            kind=kind,
            sha256=file_sha256(path),
            size_bytes=path.stat().st_size,
            path=str(path),
            cli_value=str(path),
        )

    validation = validate_project_yaml(
        _artifact(project, "project_yaml"), capability=capability
    )
    assert validation.status == "valid", validation.diagnostic
    expectation = build_preview_expectation(
        program="orca",
        jobtype=jobtype,
        input_artifact=_artifact(xyz, "geometry_xyz"),
        project=validation,
        charge=0,
        multiplicity=1,
    )
    receipt = validate_preview_workspace(expectation, preview_dir)
    return route, receipt, validation


@pytest.mark.parametrize(
    "section",
    [
        {"ab_initio": "mp2", "basis": "def2-svp", "freq": True},
        {
            "ab_initio": "mp2",
            "basis": "def2-svp",
            "ri_approximation": "ri",
            "aux_basis": "def2-svp/c",
            "freq": True,
        },
        {
            "functional": "b2plyp",
            "basis": "def2-svp",
            "aux_basis": "def2-svp/c",
            "freq": True,
        },
    ],
)
def test_frequencies_orca_cannot_differentiate_analytically_are_numfreq(
    tmp_path, section
):
    from chemsmart.agent.tool_runtime import compile_time_observations

    route, receipt, validation = _preview(tmp_path, section)
    assert " NumFreq " in f"{route} "
    assert " Freq " not in f"{route} "
    assert receipt.status == "valid", [
        (item.field, item.expected, item.observed) for item in receipt.findings
    ]
    stated = compile_time_observations(
        program="orca",
        jobtype="opt",
        settings=validation.settings,
        atom_count=3,
    )
    assert any("NumFreq" in sentence for sentence in stated)


def test_a_method_with_an_analytic_hessian_keeps_freq(tmp_path):
    route, receipt, _validation = _preview(
        tmp_path, {"ab_initio": "hf", "basis": "def2-svp", "freq": True}
    )
    assert " Freq " in f"{route} "
    assert receipt.status == "valid"
