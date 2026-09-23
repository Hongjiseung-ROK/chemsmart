"""One td request is one calculation in Gaussian, ORCA and PySCF.

ORCA's and PySCF's settings take a response calculation as
``response_method`` (``tddft`` or ``tda``) and ``state_manifold``.
Gaussian's took its own ``states: singlets|triplets|50-50`` and always ran
full TD-DFT: the loader refused ``response_method`` as an unknown key, so
the same request could not be sent to the three programs unchanged, a
model had to know Gaussian's dialect to ask for singlets, and the
Tamm-Dancoff approximation was unreachable in Gaussian through a typed
setting.  The hub owns the translation now -- ``TD``/``TDA`` and the spin
option -- and a result says which response ran.

Every value below comes from the Gaussian capability's own declared
domains, and every preview is driven through the public ``run --fake``
command and the live preview verifier: ``validate_project_yaml`` ->
``build_preview_expectation`` -> ``validate_preview_workspace``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from chemsmart.settings.capabilities import PROGRAM_CAPABILITIES

pytestmark = pytest.mark.capability("program_jobtype:gaussian:cpu:td")

_WATER_XYZ = (
    "3\nwater\nO 0.0 0.0 0.1173\nH 0.0 0.7572 -0.4692\nH 0.0 -0.7572 -0.4692\n"
)
_HYDROXYL_XYZ = "2\nhydroxyl radical\nO 0.0 0.0 0.0\nH 0.0 0.0 0.97\n"
_DATA = Path(__file__).resolve().parents[1] / "data" / "GaussianTests"


def _artifact(path: Path, kind: str):
    from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256

    return TrustedArtifactRefV1(
        artifact_id=path.stem,
        kind=kind,
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=str(path),
    )


def _capability(program: str, jobtype: str):
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


def _validate(tmp_path: Path, program: str, sections: dict, jobtype: str):
    from chemsmart.agent.projects import validate_project_yaml

    project = tmp_path / f"{program}-{jobtype}.yaml"
    project.write_text(yaml.safe_dump(sections), encoding="utf-8")
    return project, validate_project_yaml(
        _artifact(project, "project_yaml"),
        capability=_capability(program, jobtype),
    )


def _gaussian_fake_preview(tmp_path, sections, xyz_text, state, jobtype):
    """Public ``run --fake`` of one Gaussian stage and the live verifier."""

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
    project, validation = _validate(tmp_path, "gaussian", sections, jobtype)
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
        "gaussian",
        "--project",
        str(project),
        "--filename",
        str(xyz),
        "--charge",
        str(charge),
        "--multiplicity",
        str(multiplicity),
        jobtype,
    ]
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=workspace) as cwd:
        result = runner.invoke(entry_point, argv)
        preview_dir = Path(cwd)
    assert result.exit_code == 0, (result.output[-600:], result.exception)
    expectation = build_preview_expectation(
        program="gaussian",
        jobtype=jobtype,
        input_artifact=_artifact(xyz, "geometry_xyz"),
        project=validation,
        charge=charge,
        multiplicity=multiplicity,
    )
    receipt = validate_preview_workspace(expectation, preview_dir)
    written = next(preview_dir.rglob("*.com")).read_text(encoding="utf-8")
    return receipt, written


def _declared(name: str) -> tuple[str, ...]:
    domains = dict(PROGRAM_CAPABILITIES["gaussian"].project_parameter_domains)
    assert name in domains, f"Gaussian declares no domain for {name}"
    return domains[name]


def _gaussian_response_cases():
    return [
        ("response_method", value) for value in _declared("response_method")
    ] + [("state_manifold", value) for value in _declared("state_manifold")]


@pytest.mark.capability("setting:gaussian:response_method")
@pytest.mark.capability("setting:gaussian:state_manifold")
@pytest.mark.parametrize(("parameter", "value"), _gaussian_response_cases())
def test_a_declared_gaussian_response_round_trips_through_the_fake_preview(
    tmp_path, parameter, value
):
    """Declared word -> public run --fake -> the route it means -> green.

    The route is checked against the writer's own tables, so the test
    restates no Gaussian grammar: the response keyword for the declared
    response, the spin option (none for an unrestricted manifold) for the
    declared manifold.
    """

    from chemsmart.jobs.gaussian.settings import (
        GAUSSIAN_TD_MANIFOLD_OPTIONS,
        GAUSSIAN_TD_RESPONSE_KEYWORDS,
    )

    section = {
        "functional": "b3lyp",
        "basis": "def2-svp",
        "nstates": 2,
        "response_method": "tddft",
        "state_manifold": "singlet",
    }
    section[parameter] = value
    open_shell = section["state_manifold"] == "unrestricted"
    receipt, written = _gaussian_fake_preview(
        tmp_path,
        {"td": section},
        _HYDROXYL_XYZ if open_shell else _WATER_XYZ,
        (0, 2) if open_shell else (0, 1),
        "td",
    )
    assert receipt.status == "valid", [
        (item.field, item.expected, item.observed) for item in receipt.findings
    ]
    route = next(line for line in written.splitlines() if line.startswith("#"))
    keyword = GAUSSIAN_TD_RESPONSE_KEYWORDS[section["response_method"]]
    leaf = re.search(rf"(?<![A-Za-z]){keyword}\(([^)]*)\)", route)
    assert leaf is not None, route
    option = GAUSSIAN_TD_MANIFOLD_OPTIONS[section["state_manifold"]]
    words = leaf.group(1).split(",")
    if option is None:
        assert not set(words) & {
            word for word in GAUSSIAN_TD_MANIFOLD_OPTIONS.values() if word
        }, route
    else:
        assert option in words, route


@pytest.mark.capability("setting:gaussian:response_method")
@pytest.mark.capability("setting:orca:response_method")
@pytest.mark.capability("setting:pyscf:response_method")
@pytest.mark.parametrize("response", ("tda", "tddft"))
def test_one_td_section_validates_unchanged_in_all_three_programs(
    tmp_path, response
):
    """The same request, sent unchanged, is a valid request everywhere."""

    section = {
        "functional": "b3lyp",
        "basis": "def2-svp",
        "nstates": 3,
        "response_method": response,
        "state_manifold": "singlet",
    }
    for program in ("gaussian", "orca", "pyscf"):
        _project, receipt = _validate(
            tmp_path, program, {"td": dict(section)}, "td"
        )
        assert receipt.status == "valid", (program, receipt.diagnostic)
        settings = dict(receipt.settings)
        assert settings["response_method"] == response, program
        assert settings["state_manifold"] == "singlet", program


def test_two_words_for_two_manifolds_are_one_ambiguous_request(tmp_path):
    """Gaussian's own word and the shared word may not disagree."""

    _project, receipt = _validate(
        tmp_path,
        "gaussian",
        {
            "td": {
                "functional": "b3lyp",
                "basis": "def2-svp",
                "states": "triplets",
                "state_manifold": "singlet",
            }
        },
        "td",
    )
    assert receipt.status == "invalid"


@pytest.mark.capability("selector:gaussian:td:excitation_energies")
def test_a_gaussian_response_result_states_the_response_it_ran():
    """An archived open-shell TD log: full TD-DFT, the one manifold.

    The route asked ``TD(singlets,nstates=50,root=1)`` of a doublet, and
    Gaussian's spin options act on closed shells only, so the manifold
    that ran is the unrestricted one -- which is what the level says.
    """

    from chemsmart.analysis.result_readers import RESULT_READERS

    reader = RESULT_READERS["gaussian"]
    output = reader.open_output(
        _DATA / "tddft" / "tddft_r1s50_gas_radical_anion.log"
    )
    level = dict(reader.resolve_level(output))
    assert level["response_method"] == "tddft"
    assert level["state_manifold"] == "unrestricted"
    assert level["nstates"] == 50
