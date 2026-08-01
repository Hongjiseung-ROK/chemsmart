from __future__ import annotations

import pytest
from pydantic import ValidationError

from chemsmart.agent.harness.scientific_settings import (
    LoaderObservation,
    RendererObservation,
    ScientificProgram,
    ScientificSettingsValidationReceiptV1,
    SettingMatchKind,
    SettingResolutionStatus,
    build_scientific_settings_validation_receipt,
    content_sha256,
    load_scientific_settings_registry,
    list_scientific_settings,
    resolve_scientific_setting,
    scientific_settings_overlay_sha256,
    scientific_settings_receipt_sha256,
    scientific_settings_registry_sha256,
    validate_scientific_settings_source_snapshot,
)


def test_frozen_registry_and_overlay_digests_are_deterministic():
    registry = load_scientific_settings_registry()

    assert registry.registry_sha256 == scientific_settings_registry_sha256(
        registry
    )
    assert len(registry.registry_sha256) == 64
    assert registry.cli_schema_sha256 == (
        "0cc218099762f0dd3f5bc0dabecbd29dab5c29666c8691dbc5d0f9b633850ebb"
    )
    assert registry.basis_catalog_sha256 == (
        "ed4ef918fb80e8ad3c2396c237d2120c31892cfaa2a61fb61af52965dc723c0b"
    )
    assert tuple(item.overlay_id for item in registry.overlays) == (
        "settings.gaussian.v1",
        "settings.orca.v1",
        "settings.xtb.v1",
    )
    assert all(
        overlay.overlay_sha256
        == scientific_settings_overlay_sha256(overlay)
        for overlay in registry.overlays
    )
    assert registry.evidence_ceiling.maximum_claim == (
        "loader_renderer_verification_only"
    )
    assert registry.evidence_ceiling.engine_executed is False
    assert registry.evidence_ceiling.setting_combination_verified is False
    assert validate_scientific_settings_source_snapshot(registry) == ()


def test_orca_basis_and_dispersion_are_separate_observed_capabilities():
    registry = load_scientific_settings_registry()
    orca = next(
        item for item in registry.overlays if item.program is ScientificProgram.ORCA
    )
    capability_by_id = {
        item.capability_id: item for item in orca.capabilities
    }

    basis = capability_by_id["orca.basis.ma-def2-tzvp"]
    dispersion = capability_by_id["orca.dispersion.d3bj"]
    assert basis.setting_path == "method.basis"
    assert dispersion.setting_path == "method.dispersion"
    assert basis.combination_verified is False
    assert dispersion.combination_verified is False
    assert basis.renderer_observation is RendererObservation.PRESERVED
    assert dispersion.loader_observation is LoaderObservation.ACCEPTED
    assert dispersion.renderer_observation is RendererObservation.PRESERVED


def test_exact_registered_alias_is_not_fuzzy_readiness():
    alias = resolve_scientific_setting(
        program="orca",
        setting_path="method.dispersion",
        value="D3(BJ)",
        job_kind="opt",
    )
    basis_alias = resolve_scientific_setting(
        program=ScientificProgram.ORCA,
        setting_path="method.basis",
        value="ma def2 TZVP",
        job_kind="opt",
    )

    assert alias.status is SettingResolutionStatus.EXACT_REGISTERED
    assert alias.matched_by is SettingMatchKind.REGISTERED_ALIAS
    assert alias.canonical_value == "D3BJ"
    assert alias.loader_renderer_eligible is True
    assert basis_alias.status is SettingResolutionStatus.EXACT_REGISTERED
    assert basis_alias.matched_by is SettingMatchKind.REGISTERED_ALIAS
    assert basis_alias.canonical_value == "ma-def2-TZVP"
    assert basis_alias.loader_renderer_eligible is True


def test_fuzzy_basis_discovery_remains_candidate_only():
    result = resolve_scientific_setting(
        program="orca",
        setting_path="method.basis",
        value="Karlsruhe triple zeta diffuse basis",
        job_kind="opt",
    )

    assert result.status is SettingResolutionStatus.CANDIDATE_ONLY
    assert result.matched_by is SettingMatchKind.FUZZY_CANDIDATE
    assert result.capability_id is None
    assert result.candidate_values
    assert result.loader_renderer_eligible is False


def test_full_bse_and_orca_native_basis_inventory_is_queryable_but_bounded():
    gaussian = list_scientific_settings(
        program="gaussian",
        setting_path="method.basis",
        query="aug-cc-pvtz",
        limit=5,
    )
    orca = list_scientific_settings(
        program="orca",
        setting_path="method.basis",
        query="ma-def2",
        limit=4,
    )
    xtb = list_scientific_settings(
        program="xtb",
        setting_path="method.basis",
    )

    assert gaussian["inventory_count"] >= 748
    assert gaussian["returned_count"] <= 5
    assert "aug-cc-pVTZ" in gaussian["values"]
    assert orca["inventory_count"] >= 748
    assert orca["returned_count"] <= 4
    assert any("ma-def2" in value for value in orca["values"])
    assert xtb["status"] == "not_applicable"

    bse_exact = resolve_scientific_setting(
        program="gaussian",
        setting_path="method.basis",
        value="aug cc pVTZ",
    )
    native_exact = resolve_scientific_setting(
        program="orca",
        setting_path="method.basis",
        value="ma-def2-qzvpp",
    )
    assert bse_exact.status is SettingResolutionStatus.EXACT_REGISTERED
    assert bse_exact.loader_renderer_eligible is True
    assert native_exact.status is SettingResolutionStatus.EXACT_REGISTERED
    assert native_exact.loader_renderer_eligible is True


def test_unknown_and_cross_program_values_fail_closed():
    unknown = resolve_scientific_setting(
        program="gaussian",
        setting_path="method.functional",
        value="definitely-not-a-real-functional-92831",
    )
    incompatible = resolve_scientific_setting(
        program="gaussian",
        setting_path="method.gfn_version",
        value="GFN2-xTB",
    )
    wrong_job = resolve_scientific_setting(
        program="xtb",
        setting_path="method.gfn_version",
        value="gfn2",
        job_kind="md",
    )

    assert unknown.status is SettingResolutionStatus.UNKNOWN_UNVERIFIED
    assert unknown.matched_by is SettingMatchKind.NONE
    assert incompatible.status is SettingResolutionStatus.INCOMPATIBLE
    assert incompatible.matched_by is SettingMatchKind.REGISTERED_ELSEWHERE
    assert wrong_job.status is SettingResolutionStatus.INCOMPATIBLE
    assert wrong_job.matched_by is SettingMatchKind.JOB_SCOPE_MISMATCH


def test_sidecar_binds_exact_project_bytes_and_registry_digest():
    project_yaml = b"gas:\n  functional: B3LYP\n  basis: ma-def2-TZVP\n"
    resolutions = (
        resolve_scientific_setting(
            program="orca",
            setting_path="method.functional",
            value="B3LYP",
            job_kind="opt",
        ),
        resolve_scientific_setting(
            program="orca",
            setting_path="method.basis",
            value="ma-def2-TZVP",
            job_kind="opt",
        ),
    )
    receipt = build_scientific_settings_validation_receipt(
        project_yaml=project_yaml,
        resolutions=reversed(resolutions),
        project_config_sha256="1" * 64,
    )

    assert receipt.project_yaml_sha256 == content_sha256(project_yaml)
    assert receipt.registry_sha256 == (
        load_scientific_settings_registry().registry_sha256
    )
    assert receipt.status == "registered_only"
    assert receipt.all_settings_exact_registered is True
    assert receipt.all_loader_renderer_observations_preserved is True
    assert receipt.safe_preview_executed is False
    assert receipt.engine_executed is False
    assert receipt.receipt_sha256 == scientific_settings_receipt_sha256(
        receipt
    )
    assert tuple(item.setting_path for item in receipt.resolutions) == (
        "method.basis",
        "method.functional",
    )

    changed = build_scientific_settings_validation_receipt(
        project_yaml=project_yaml + b"\n",
        resolutions=resolutions,
        project_config_sha256="1" * 64,
    )
    assert changed.project_yaml_sha256 != receipt.project_yaml_sha256
    assert changed.receipt_sha256 != receipt.receipt_sha256


def test_sidecar_preserves_verified_dispersion_and_blocks_unverified_resolution():
    dispersion = resolve_scientific_setting(
        program="orca",
        setting_path="method.dispersion",
        value="D3BJ",
    )
    candidate = resolve_scientific_setting(
        program="orca",
        setting_path="method.basis",
        value="diffuse Karlsruhe triple zeta",
    )

    renderer_receipt = build_scientific_settings_validation_receipt(
        project_yaml="gas:\n  dispersion: D3BJ\n",
        resolutions=(dispersion,),
    )
    resolution_block = build_scientific_settings_validation_receipt(
        project_yaml="gas:\n  basis: unresolved\n",
        resolutions=(candidate,),
    )

    assert renderer_receipt.all_settings_exact_registered is True
    assert renderer_receipt.status == "registered_only"
    assert renderer_receipt.blocking_rule_ids == ()
    assert resolution_block.all_settings_exact_registered is False
    assert resolution_block.status == "blocked_resolution"


def test_content_addressed_sidecar_rejects_tampering():
    resolution = resolve_scientific_setting(
        program="xtb",
        setting_path="method.gfn_version",
        value="gfn2",
        job_kind="sp",
    )
    receipt = build_scientific_settings_validation_receipt(
        project_yaml="sp:\n  gfn_version: gfn2\n",
        resolutions=(resolution,),
    )
    payload = receipt.model_dump(mode="json")
    payload["project_yaml_sha256"] = "0" * 64

    with pytest.raises(ValidationError, match="receipt SHA-256"):
        ScientificSettingsValidationReceiptV1.model_validate(payload)
