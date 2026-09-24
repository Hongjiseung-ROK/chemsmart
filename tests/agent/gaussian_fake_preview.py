"""Drive one program stage through the planning session's own preview chain.

``validate_project_yaml`` -> the public ``run --fake`` command ->
``build_preview_expectation`` -> ``validate_preview_workspace``: the chain
a planning session walks before any engine runs.  A test helper, not host
code; the capability receipt is built the way the session builds it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import yaml


def artifact(path: Path, kind: str):
    """A host artifact binding for a file the test wrote."""

    from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256

    return TrustedArtifactRefV1(
        artifact_id=path.stem,
        kind=kind,
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=str(path),
    )


def capability(program: str, jobtype: str):
    """The capability receipt a planning session holds for one stage."""

    from chemsmart.agent.capabilities import (
        ProgramCapabilityQueryV1,
        build_command_compiled_preview_overlay,
        build_program_component_conformance_receipt,
        load_program_capabilities,
        query_capability,
    )
    from chemsmart.agent.cli_schema import build_live_click_schema

    registry = load_program_capabilities()
    live_schema = build_live_click_schema()
    pairs = tuple(
        sorted(
            pair
            for pair in registry.get(program).preview_engine_job_pairs
            if pair[0] == "cpu"
        )
    )
    conformance = build_program_component_conformance_receipt(
        program=program,
        registry_sha256=registry.registry_sha256,
        live_cli_schema_sha256=live_schema.schema_sha256,
        fixture_bundle_sha256="1" * 64,
        covered_jobtypes=tuple(sorted({jobtype for _e, jobtype in pairs})),
        covered_engines=("cpu",),
        covered_engine_job_pairs=pairs,
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
    return query_capability(
        ProgramCapabilityQueryV1(program, jobtype, "cpu"),
        registry=registry,
        live_schema=live_schema,
        overlay=overlay,
    )


def validate(tmp_path: Path, program: str, sections: dict, jobtype: str):
    """Write one project and validate it as the session's tool does."""

    from chemsmart.agent.projects import validate_project_yaml

    project = tmp_path / f"{program}-{jobtype}.yaml"
    project.write_text(yaml.safe_dump(sections), encoding="utf-8")
    return project, validate_project_yaml(
        artifact(project, "project_yaml"),
        capability=capability(program, jobtype),
    )


def fake_preview(
    tmp_path: Path,
    program: str,
    sections: dict,
    xyz_text: str,
    state: tuple[int, int],
    jobtype: str,
    job_arguments: Sequence[str] = (),
):
    """Public ``run --fake`` of one stage, verified as a session's preview.

    Returns the preview verifier's receipt and the written native input.
    """

    from click.testing import CliRunner

    from chemsmart.agent.live_session import _preview_server_profile
    from chemsmart.agent.program_verifiers import (
        build_preview_expectation,
        validate_preview_workspace,
    )
    from chemsmart.cli.main import entry_point

    charge, multiplicity = state
    xyz = tmp_path / "input.xyz"
    xyz.write_text(xyz_text, encoding="utf-8")
    project, validation = validate(tmp_path, program, sections, jobtype)
    assert validation.status == "valid", validation.diagnostic
    server = tmp_path / "preview-server.yaml"
    server.write_text(_preview_server_profile(), encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    argv = [
        "run",
        "--server",
        str(server),
        "--fake",
        "--no-scratch",
        program,
        "--project",
        str(project),
        "--filename",
        str(xyz),
        "--charge",
        str(charge),
        "--multiplicity",
        str(multiplicity),
        jobtype,
        *job_arguments,
    ]
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=workspace) as cwd:
        result = runner.invoke(entry_point, argv)
        preview_dir = Path(cwd)
    assert result.exit_code == 0, (result.output[-600:], result.exception)
    expectation = build_preview_expectation(
        program=program,
        jobtype=jobtype,
        input_artifact=artifact(xyz, "geometry_xyz"),
        project=validation,
        charge=charge,
        multiplicity=multiplicity,
    )
    receipt = validate_preview_workspace(expectation, preview_dir)
    suffixes = {".com", ".gjf", ".inp"}
    written = next(
        path for path in preview_dir.rglob("*") if path.suffix in suffixes
    ).read_text(encoding="utf-8")
    return receipt, written


__all__ = ["artifact", "capability", "fake_preview", "validate"]
