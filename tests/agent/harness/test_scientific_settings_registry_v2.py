from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from chemsmart.agent.harness.scientific_settings import (
    ScientificSettingsInventoryArtifactError,
    ScientificSettingsInventoryDescriptorV2,
    ScientificSettingsInventoryV2,
    ScientificSettingsRegistryDigestNotFoundError,
    ScientificSettingsRegistryV1,
    ScientificSettingsRegistryV2,
    SettingInventoryEntryV2,
    build_scientific_settings_validation_receipt,
    load_scientific_settings_inventory_v2,
    load_scientific_settings_registry,
    load_scientific_settings_registry_by_sha256,
    load_scientific_settings_registry_v1,
    load_scientific_settings_registry_v2,
    resolve_scientific_setting,
    scientific_settings_inventory_v2_sha256,
    scientific_settings_registry_v2_sha256,
)


V1_REGISTRY_SHA256 = (
    "ff7ee8b9371ae00981a82d8ee4b88e6dec8bf6910ad1cecf916d6f0e6645a3d4"
)
V1_OVERLAY_SHA256S = {
    "settings.gaussian.v1": (
        "f33acd725a2fb81ec4c583a36a97c2b0207c44dd802414257666fe6f2e1e6f2a"
    ),
    "settings.orca.v1": (
        "bc19792d745cddf0446810862ebe522fa1e14a196c6a12befc3ff817e4f1b36f"
    ),
    "settings.xtb.v1": (
        "4b8f1445842b6c723d6eeddd400fdaab4dd3dda082d7e27f049615aa97c4a805"
    ),
}
V2_REGISTRY_SHA256 = (
    "f7528e3f2cfbffcc72d2f677e9e146f80ab9e603207db6631789666b6af0db15"
)


def test_v1_golden_registry_and_overlay_identities_are_unchanged():
    registry = load_scientific_settings_registry()

    assert load_scientific_settings_registry_v1 is (
        load_scientific_settings_registry
    )
    assert load_scientific_settings_registry_v1() is registry
    assert type(registry) is ScientificSettingsRegistryV1
    assert registry.schema_version == "chemsmart.scientific-settings-registry.v1"
    assert registry.registry_sha256 == V1_REGISTRY_SHA256
    assert {
        overlay.overlay_id: overlay.overlay_sha256
        for overlay in registry.overlays
    } == V1_OVERLAY_SHA256S


def test_v1_golden_resolution_and_receipt_replay_are_unchanged():
    resolution = resolve_scientific_setting(
        program="orca",
        setting_path="method.basis",
        value="ma-def2-TZVP",
        job_kind="opt",
    )
    receipt = build_scientific_settings_validation_receipt(
        project_yaml=b"gas:\n  basis: ma-def2-TZVP\n",
        resolutions=(resolution,),
        project_config_sha256="1" * 64,
    )

    assert resolution.schema_version == (
        "chemsmart.scientific-setting-resolution.v1"
    )
    assert resolution.resolution_sha256 == (
        "2a72157cd48646dbd0619c2a56b1e137fd071810083e1007bb52a86908dff173"
    )
    assert receipt.schema_version == (
        "chemsmart.scientific-settings-validation-receipt.v1"
    )
    assert receipt.receipt_sha256 == (
        "366e1489f318344861df1338a5ff219821d9657b5cbf3d769fd69c996434ed0d"
    )


def test_v2_is_a_separate_empty_non_authoritative_lineage_snapshot():
    registry = load_scientific_settings_registry_v2()

    assert type(registry) is ScientificSettingsRegistryV2
    assert registry.schema_version == "chemsmart.scientific-settings-registry.v2"
    assert registry.registry_sha256 == V2_REGISTRY_SHA256
    assert registry.predecessor.registry_id == (
        "chemsmart.scientific-settings.source-snapshot-c793db6"
    )
    assert registry.predecessor.registry_version == "1.0.0"
    assert registry.predecessor.registry_sha256 == V1_REGISTRY_SHA256
    assert registry.predecessor.target_schema_version == (
        "chemsmart.scientific-settings-registry.v1"
    )
    assert registry.inventories == ()
    assert registry.inventory_population_state == "empty_skeleton"
    assert registry.experimental is True
    assert registry.default_runtime_authority is False


def test_digest_lookup_replays_v1_and_v2_without_implicit_migration():
    v1 = load_scientific_settings_registry()
    v2 = load_scientific_settings_registry_v2()

    replayed_v1 = load_scientific_settings_registry_by_sha256(
        v1.registry_sha256
    )
    replayed_v2 = load_scientific_settings_registry_by_sha256(
        v2.registry_sha256
    )

    assert type(replayed_v1) is ScientificSettingsRegistryV1
    assert replayed_v1.registry_sha256 == V1_REGISTRY_SHA256
    assert type(replayed_v2) is ScientificSettingsRegistryV2
    assert replayed_v2.predecessor.registry_sha256 == V1_REGISTRY_SHA256


def test_digest_lookup_rejects_invalid_and_unknown_digests():
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        load_scientific_settings_registry_by_sha256("A" * 64)

    with pytest.raises(ScientificSettingsRegistryDigestNotFoundError):
        load_scientific_settings_registry_by_sha256("0" * 64)


def test_v2_registry_identity_rejects_tampering():
    registry = load_scientific_settings_registry_v2()
    payload = registry.model_dump(mode="json")
    payload["registry_id"] = "chemsmart.scientific-settings.tampered"

    with pytest.raises(ValidationError, match="frozen V2 content"):
        ScientificSettingsRegistryV2.model_validate(payload)


def test_v2_inventory_rejects_ambiguous_or_unsafe_literals():
    first = _entry(
        entry_id="entry.a",
        canonical_value="B3LYP",
        aliases=("PBE-0",),
    )
    second = _entry(
        entry_id="entry.b",
        canonical_value="PBE0",
    )
    payload = _inventory_payload((first, second))

    with pytest.raises(ValidationError, match="ambiguous normalized literal"):
        ScientificSettingsInventoryV2.model_validate(payload)

    with pytest.raises(ValidationError, match="control characters"):
        SettingInventoryEntryV2.model_validate(
            _entry(
                entry_id="entry.control",
                canonical_value="PBE0",
                aliases=("bad\x00alias",),
            )
        )

    with pytest.raises(ValidationError, match="normalize to a literal"):
        SettingInventoryEntryV2.model_validate(
            _entry(entry_id="entry.empty", canonical_value="---")
        )

    with pytest.raises(ValidationError, match="at least 1 item"):
        SettingInventoryEntryV2.model_validate(
            _entry(
                entry_id="entry.no-jobs",
                canonical_value="PBE0",
                applicable_job_kinds=(),
            )
        )


def test_v2_known_but_unenforced_rules_remain_representable():
    known_unenforced = SettingInventoryEntryV2.model_validate(
        _entry(
            entry_id="entry.known-unenforced",
            canonical_value="M06-2X",
            applicability_rule_ids=("scientific_settings.rule.known",),
            validator_enforced=False,
        )
    )
    assert known_unenforced.validator_enforced is False
    assert known_unenforced.applicability_rule_ids

    with pytest.raises(ValidationError, match="requires an applicability rule"):
        SettingInventoryEntryV2.model_validate(
            _entry(
                entry_id="entry.false-enforcement",
                canonical_value="M06-2X",
                validator_enforced=True,
            )
        )


def test_v2_descriptor_binds_exact_scope_topology_and_safe_locator():
    body = _descriptor_payload()
    descriptor = ScientificSettingsInventoryDescriptorV2.model_validate(body)
    assert tuple(
        (scope.program.value, scope.setting_path, scope.entry_count)
        for scope in descriptor.scopes
    ) == (("gaussian", "method.functional", 1),)

    mismatched = dict(body)
    mismatched["entry_count"] = 2
    with pytest.raises(ValidationError, match="scope counts"):
        ScientificSettingsInventoryDescriptorV2.model_validate(mismatched)

    unsafe = dict(body)
    unsafe["artifact_locator"] = "/etc/passwd.json"
    with pytest.raises(ValidationError, match="repository-relative"):
        ScientificSettingsInventoryDescriptorV2.model_validate(unsafe)


def test_v2_exact_byte_inventory_loader_is_bound_and_fail_closed(tmp_path):
    inventory_payload = _inventory_payload(
        (
            _entry(
                entry_id="entry.pbe0",
                canonical_value="PBE0",
                aliases=("PBE-0",),
            ),
        )
    )
    artifact_bytes = json.dumps(
        inventory_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    artifact_path = tmp_path / "inventory.json"
    artifact_path.write_bytes(artifact_bytes)

    descriptor_body = _descriptor_payload(
        inventory_sha256=inventory_payload["inventory_sha256"],
        artifact_sha256=hashlib.sha256(artifact_bytes).hexdigest(),
    )
    descriptor = ScientificSettingsInventoryDescriptorV2.model_validate(
        descriptor_body
    )
    registry_body = load_scientific_settings_registry_v2().model_dump(mode="json")
    registry_body["registry_id"] = "chemsmart.scientific-settings.test-populated"
    registry_body["inventories"] = (descriptor.model_dump(mode="json"),)
    registry_body["inventory_population_state"] = "populated"
    registry_body["registry_sha256"] = scientific_settings_registry_v2_sha256(
        registry_body
    )
    registry = ScientificSettingsRegistryV2.model_validate(registry_body)

    loaded = load_scientific_settings_inventory_v2(
        registry=registry,
        descriptor=descriptor,
        repository_root=tmp_path,
    )
    assert loaded.inventory_sha256 == inventory_payload["inventory_sha256"]

    artifact_path.write_bytes(artifact_bytes + b"\n")
    with pytest.raises(
        ScientificSettingsInventoryArtifactError,
        match="exact-byte SHA-256 mismatch",
    ):
        load_scientific_settings_inventory_v2(
            registry=registry,
            descriptor=descriptor,
            repository_root=tmp_path,
        )


def _entry(
    *,
    entry_id: str,
    canonical_value: str,
    aliases: tuple[str, ...] = (),
    applicable_job_kinds: tuple[str, ...] = ("*",),
    applicability_rule_ids: tuple[str, ...] = (),
    validator_enforced: bool = False,
) -> dict[str, object]:
    return {
        "entry_id": entry_id,
        "program": "gaussian",
        "setting_path": "method.functional",
        "canonical_value": canonical_value,
        "aliases": aliases,
        "applicable_job_kinds": applicable_job_kinds,
        "applicability_rule_ids": applicability_rule_ids,
        "validator_enforced": validator_enforced,
        "source_ids": ("source.one",),
        "loader_observation": "accepted",
        "renderer_observation": "preserved",
        "observation_note": "Observed by a deterministic loader/renderer probe.",
        "engine_executed": False,
        "combination_verified": False,
    }


def _inventory_payload(
    entries: tuple[dict[str, object], ...],
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": "chemsmart.scientific-settings-inventory.v2",
        "inventory_id": "inventory.test",
        "inventory_version": "2.0.0",
        "normalization_version": "chemsmart.scientific-setting-literal.v1",
        "sources": (
            {
                "source_id": "source.one",
                "source_kind": "checked_in_loader_renderer",
                "locator": "chemsmart/jobs/gaussian/settings.py",
                "artifact_sha256": "3" * 64,
                "source_revision": "test-revision",
            },
        ),
        "entries": entries,
        "evidence_ceiling": (
            load_scientific_settings_registry_v2().evidence_ceiling.model_dump(
                mode="json"
            )
        ),
    }
    body["inventory_sha256"] = scientific_settings_inventory_v2_sha256(body)
    return body


def _descriptor_payload(
    *,
    inventory_sha256: str = "1" * 64,
    artifact_sha256: str = "2" * 64,
) -> dict[str, object]:
    return {
        "schema_version": (
            "chemsmart.scientific-settings-inventory-descriptor.v2"
        ),
        "inventory_schema_version": (
            "chemsmart.scientific-settings-inventory.v2"
        ),
        "normalization_version": "chemsmart.scientific-setting-literal.v1",
        "inventory_id": "inventory.test",
        "inventory_version": "2.0.0",
        "inventory_sha256": inventory_sha256,
        "artifact_locator": "inventory.json",
        "artifact_sha256": artifact_sha256,
        "entry_count": 1,
        "scopes": (
            {
                "program": "gaussian",
                "setting_path": "method.functional",
                "entry_count": 1,
            },
        ),
    }
