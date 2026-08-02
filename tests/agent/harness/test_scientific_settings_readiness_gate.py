from __future__ import annotations

import subprocess
import sys

import pytest
from pydantic import ValidationError

from chemsmart.agent.harness.scientific_settings import (
    PolicyBoundSettingResolutionV2,
    load_populated_scientific_settings_inventories_v2,
    load_populated_scientific_settings_registry_v2,
    resolve_scientific_setting_repaired_v2,
)
from chemsmart.agent.harness.scientific_settings.readiness_gate import (
    ScientificSettingsReadinessGateV1,
    ScientificSettingsReadinessStatusV1,
    assess_scientific_settings_readiness,
    scientific_settings_readiness_gate_v1_sha256,
    scientific_settings_readiness_input_sha256,
)
from chemsmart.agent.project_readiness import assess_typed_project_readiness


def test_project_readiness_direct_import_has_no_order_dependent_cycle():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from chemsmart.agent.project_readiness import "
                "assess_typed_project_readiness; "
                "assert callable(assess_typed_project_readiness)"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.fixture(scope="module")
def registry_context():
    return (
        load_populated_scientific_settings_registry_v2(),
        load_populated_scientific_settings_inventories_v2(),
    )


def _resolve(
    registry_context,
    *,
    program: str,
    setting_path: str,
    value: str,
    job_kind: str,
    allow_fuzzy_candidates: bool = True,
) -> PolicyBoundSettingResolutionV2:
    registry, inventories = registry_context
    return resolve_scientific_setting_repaired_v2(
        registry=registry,
        loaded_inventories=inventories,
        program=program,
        setting_path=setting_path,
        value=value,
        job_kind=job_kind,
        allow_fuzzy_candidates=allow_fuzzy_candidates,
    )


def _project_receipt(
    *,
    case_id: str,
    program: str,
    job_kind: str,
    method: dict,
    resolutions: tuple[PolicyBoundSettingResolutionV2, ...],
):
    return assess_typed_project_readiness(
        case_id=case_id,
        program=program,
        job_kind=job_kind,
        method=method,
        registry_resolution_sha256s=tuple(
            item.resolution.resolution_sha256 for item in resolutions
        ),
    )


def test_all_exact_and_typed_project_supported_is_content_bound_candidate(
    registry_context,
):
    functional = _resolve(
        registry_context,
        program="gaussian",
        setting_path="method.functional",
        value="B3LYP",
        job_kind="opt",
    )
    grid = _resolve(
        registry_context,
        program="gaussian",
        setting_path="method.integration_grid",
        value="UltraFine",
        job_kind="opt",
    )
    supplied = (grid, functional)
    project = _project_receipt(
        case_id="settings-ready-gaussian",
        program="gaussian",
        job_kind="opt",
        method={
            "functional": "B3LYP",
            "basis": "def2-SVP",
            "integration_grid": "UltraFine",
            "freq": True,
        },
        resolutions=supplied,
    )

    gate = assess_scientific_settings_readiness(
        policy_bound_resolutions=supplied,
        project_readiness=project,
    )
    replay = assess_scientific_settings_readiness(
        policy_bound_resolutions=tuple(reversed(supplied)),
        project_readiness=project,
    )

    assert gate.status is ScientificSettingsReadinessStatusV1.PROJECT_CANDIDATE
    assert gate.blocking_rule_ids == ()
    assert gate.gate_sha256 == replay.gate_sha256
    assert gate.gate_sha256 == scientific_settings_readiness_gate_v1_sha256(gate)
    assert gate.input_sha256 == scientific_settings_readiness_input_sha256(
        gate.policy_bound_resolutions,
        project,
    )
    assert gate.resolution_binding_sha256s == tuple(
        sorted(item.binding_sha256 for item in supplied)
    )
    assert gate.project_request_sha256 == project.request.request_sha256
    assert gate.project_readiness_receipt_sha256 == project.receipt_sha256
    assert "scientific_settings.readiness.all_resolutions_exact_project_eligible" in (
        gate.derivation_rule_ids
    )
    ScientificSettingsReadinessGateV1.model_validate(
        gate.model_dump(mode="json")
    )


@pytest.mark.parametrize(
    ("value", "allow_fuzzy_candidates", "reason_rule_id"),
    (
        (
            "PBE0",
            False,
            "scientific_settings.v2.non_exhaustive_scope_unverified",
        ),
        (
            "PBE0X",
            True,
            "scientific_settings.v2.candidate_requires_selection",
        ),
    ),
)
def test_unknown_and_fuzzy_candidate_fail_closed_as_unverified(
    registry_context,
    value,
    allow_fuzzy_candidates,
    reason_rule_id,
):
    resolution = _resolve(
        registry_context,
        program="gaussian",
        setting_path="method.functional",
        value=value,
        job_kind="opt",
        allow_fuzzy_candidates=allow_fuzzy_candidates,
    )
    project = _project_receipt(
        case_id=f"settings-unverified-{value.lower()}",
        program="gaussian",
        job_kind="opt",
        method={"functional": value, "basis": "def2-SVP", "freq": True},
        resolutions=(resolution,),
    )

    gate = assess_scientific_settings_readiness(
        policy_bound_resolutions=(resolution,),
        project_readiness=project,
    )

    assert gate.status is (
        ScientificSettingsReadinessStatusV1.BLOCKED_UNVERIFIED_SETTING
    )
    assert reason_rule_id in gate.blocking_rule_ids
    assert "scientific_settings.readiness.unverified_setting" in (
        gate.blocking_rule_ids
    )


def test_validation_coverage_has_no_discharge_in_v1(registry_context):
    resolution = _resolve(
        registry_context,
        program="gaussian",
        setting_path="method.basis",
        value="def2-SVP",
        job_kind="opt",
    )
    project = _project_receipt(
        case_id="settings-basis-coverage",
        program="gaussian",
        job_kind="opt",
        method={"functional": "B3LYP", "basis": "def2-SVP", "freq": True},
        resolutions=(resolution,),
    )

    gate = assess_scientific_settings_readiness(
        policy_bound_resolutions=(resolution,),
        project_readiness=project,
    )

    assert gate.status is (
        ScientificSettingsReadinessStatusV1.BLOCKED_VALIDATION_COVERAGE
    )
    assert gate.validation_coverage_discharge_policy == "no_discharge_supported_v1"
    assert (
        "scientific_settings.readiness.validation_coverage_undischarged_v1"
        in gate.blocking_rule_ids
    )
    assert "scientific_settings.readiness.v1_has_no_coverage_discharge" in (
        gate.derivation_rule_ids
    )


@pytest.mark.parametrize(
    ("setting_path", "value", "method"),
    (
        (
            "method.basis",
            "def2-SVP",
            {"gfn_version": "gfn2", "basis": "def2-SVP"},
        ),
        (
            "method.gfn_version",
            "B3LYP",
            {"gfn_version": "B3LYP"},
        ),
    ),
)
def test_not_applicable_and_incompatible_are_unsupported(
    registry_context,
    setting_path,
    value,
    method,
):
    resolution = _resolve(
        registry_context,
        program="xtb",
        setting_path=setting_path,
        value=value,
        job_kind="sp",
        allow_fuzzy_candidates=False,
    )
    project = _project_receipt(
        case_id=f"settings-unsupported-{setting_path.replace('.', '-')}",
        program="xtb",
        job_kind="sp",
        method=method,
        resolutions=(resolution,),
    )

    gate = assess_scientific_settings_readiness(
        policy_bound_resolutions=(resolution,),
        project_readiness=project,
    )

    assert gate.status is (
        ScientificSettingsReadinessStatusV1.BLOCKED_UNSUPPORTED_SETTING
    )
    assert "scientific_settings.readiness.unsupported_setting" in (
        gate.blocking_rule_ids
    )


@pytest.mark.parametrize(
    ("case_id", "method", "expected_status", "project_rule"),
    (
        (
            "settings-project-missing",
            {"functional": "B3LYP", "freq": True},
            ScientificSettingsReadinessStatusV1.BLOCKED_MISSING_EVIDENCE,
            "scientific_settings.readiness.project.blocked_missing_evidence",
        ),
        (
            "settings-project-unsupported",
            {
                "functional": "B3LYP",
                "basis": "def2-SVP",
                "dispersion": "D4",
                "freq": True,
            },
            ScientificSettingsReadinessStatusV1.BLOCKED_UNSUPPORTED_SETTING,
            "scientific_settings.readiness.project.blocked_unsupported_setting",
        ),
    ),
)
def test_project_receipt_blocks_are_preserved_conservatively(
    registry_context,
    case_id,
    method,
    expected_status,
    project_rule,
):
    exact = _resolve(
        registry_context,
        program="gaussian",
        setting_path="method.functional",
        value="B3LYP",
        job_kind="opt",
    )
    project = _project_receipt(
        case_id=case_id,
        program="gaussian",
        job_kind="opt",
        method=method,
        resolutions=(exact,),
    )

    gate = assess_scientific_settings_readiness(
        policy_bound_resolutions=(exact,),
        project_readiness=project,
    )

    assert gate.status is expected_status
    assert project_rule in gate.blocking_rule_ids
    assert set(project.typed_project_support.blocking_rule_ids).issubset(
        gate.blocking_rule_ids
    )


def test_empty_resolution_set_is_not_vacuously_ready():
    project = _project_receipt(
        case_id="settings-empty-resolution-set",
        program="xtb",
        job_kind="sp",
        method={"gfn_version": "gfn2"},
        resolutions=(),
    )

    gate = assess_scientific_settings_readiness(
        policy_bound_resolutions=(),
        project_readiness=project,
    )

    assert gate.status is (
        ScientificSettingsReadinessStatusV1.BLOCKED_UNVERIFIED_SETTING
    )
    assert gate.resolution_sha256s == ()
    assert "scientific_settings.readiness.no_resolution_binding" in (
        gate.blocking_rule_ids
    )


def test_gate_rejects_unbound_project_discovery_and_hash_tampering(
    registry_context,
):
    exact = _resolve(
        registry_context,
        program="gaussian",
        setting_path="method.functional",
        value="B3LYP",
        job_kind="opt",
    )
    unbound_project = _project_receipt(
        case_id="settings-unbound-project",
        program="gaussian",
        job_kind="opt",
        method={"functional": "B3LYP", "basis": "def2-SVP", "freq": True},
        resolutions=(),
    )

    with pytest.raises(ValidationError, match="does not bind every resolution"):
        assess_scientific_settings_readiness(
            policy_bound_resolutions=(exact,),
            project_readiness=unbound_project,
        )

    project = _project_receipt(
        case_id="settings-bound-project",
        program="gaussian",
        job_kind="opt",
        method={"functional": "B3LYP", "basis": "def2-SVP", "freq": True},
        resolutions=(exact,),
    )
    gate = assess_scientific_settings_readiness(
        policy_bound_resolutions=(exact,),
        project_readiness=project,
    )
    tampered = gate.model_dump(mode="json")
    tampered["project_readiness_receipt_sha256"] = "f" * 64

    with pytest.raises(ValidationError, match="does not bind every gate input"):
        ScientificSettingsReadinessGateV1.model_validate(tampered)
