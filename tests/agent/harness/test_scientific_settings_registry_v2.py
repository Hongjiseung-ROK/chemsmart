from __future__ import annotations

import hashlib
import json
from collections import Counter

import pytest
from pydantic import ValidationError

from chemsmart.agent.harness.scientific_settings import (
    ScientificSettingsInventoryArtifactError,
    ScientificSettingsInventoryDescriptorV2,
    ScientificSettingsInventoryV2,
    ScientificSettingsListStatusV2,
    ScientificSettingsRegistryDigestNotFoundError,
    ScientificSettingsRegistryV1,
    ScientificSettingsRegistryV2,
    SettingInventoryEntryV2,
    SettingMatchKindV2,
    SettingResolutionStatusV2,
    SettingResolutionV2,
    build_scientific_settings_validation_receipt,
    load_scientific_settings_inventory_v2,
    list_scientific_settings_v2,
    load_scientific_settings_registry,
    load_scientific_settings_registry_by_sha256,
    load_scientific_settings_registry_v1,
    load_scientific_settings_registry_v2,
    resolve_scientific_setting,
    resolve_scientific_setting_v2,
    scientific_setting_resolution_v2_sha256,
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


def test_v2_lookup_requires_explicit_populated_registry():
    with pytest.raises(ValueError, match="explicitly populated"):
        resolve_scientific_setting_v2(
            registry=load_scientific_settings_registry_v2(),
            loaded_inventories=(),
            program="gaussian",
            setting_path="method.functional",
            value="B3LYP",
            job_kind="opt",
        )


def test_v2_exact_and_validation_coverage_states_are_separate(tmp_path):
    registry, inventories = _loaded_lookup_context(
        tmp_path,
        entries=(
            _entry(
                entry_id="entry.b3lyp",
                canonical_value="B3LYP",
                aliases=("B3-LYP",),
                applicable_job_kinds=("opt",),
            ),
            _entry(
                entry_id="entry.m062x",
                canonical_value="M06-2X",
                applicable_job_kinds=("opt",),
                applicability_rule_ids=(
                    "scientific_settings.functional.m062x_scope",
                ),
                validator_enforced=False,
            ),
            _entry(
                entry_id="entry.pbe0",
                canonical_value="PBE0",
                applicable_job_kinds=("opt",),
                applicability_rule_ids=(
                    "scientific_settings.functional.pbe0_scope",
                ),
                validator_enforced=True,
            ),
        ),
    )

    exact = resolve_scientific_setting_v2(
        registry=registry,
        loaded_inventories=inventories,
        program="gaussian",
        setting_path="method.functional",
        value="B3-LYP",
        job_kind="opt",
    )
    blocked = resolve_scientific_setting_v2(
        registry=registry,
        loaded_inventories=inventories,
        program="gaussian",
        setting_path="method.functional",
        value="M06-2X",
        job_kind="opt",
    )
    enforced = resolve_scientific_setting_v2(
        registry=registry,
        loaded_inventories=inventories,
        program="gaussian",
        setting_path="method.functional",
        value="PBE0",
        job_kind="opt",
    )

    assert exact.status is SettingResolutionStatusV2.EXACT_REGISTERED
    assert exact.matched_by is SettingMatchKindV2.REGISTERED_ALIAS
    assert exact.source_registered is True
    assert exact.loader_accepted is True
    assert exact.renderer_preserved is True
    assert exact.applicability_rules_present is False
    assert exact.deterministic_validator_enforced is False
    assert exact.project_candidate_eligible is True
    assert exact.resolution_sha256 == scientific_setting_resolution_v2_sha256(
        exact
    )

    assert blocked.status is (
        SettingResolutionStatusV2.BLOCKED_VALIDATION_COVERAGE
    )
    assert blocked.reason_rule_id == (
        "scientific_settings.v2.validation_coverage_gap"
    )
    assert blocked.source_registered is True
    assert blocked.applicability_rules_present is True
    assert blocked.deterministic_validator_enforced is False
    assert blocked.project_candidate_eligible is False

    assert enforced.status is SettingResolutionStatusV2.EXACT_REGISTERED
    assert enforced.applicability_rules_present is True
    assert enforced.deterministic_validator_enforced is True
    assert enforced.project_candidate_eligible is True


def test_v2_mismatch_unknown_and_xtb_basis_fail_closed(tmp_path):
    registry, inventories = _loaded_lookup_context(
        tmp_path,
        entries=(
            _entry(
                entry_id="entry.gaussian.b3lyp",
                canonical_value="B3LYP",
                applicable_job_kinds=("opt",),
            ),
            _entry(
                entry_id="entry.xtb.gfn2",
                program="xtb",
                setting_path="method.gfn_version",
                canonical_value="GFN2-xTB",
                applicable_job_kinds=("sp",),
            ),
        ),
    )

    job_mismatch = resolve_scientific_setting_v2(
        registry=registry,
        loaded_inventories=inventories,
        program="gaussian",
        setting_path="method.functional",
        value="B3LYP",
        job_kind="sp",
    )
    elsewhere = resolve_scientific_setting_v2(
        registry=registry,
        loaded_inventories=inventories,
        program="orca",
        setting_path="method.functional",
        value="B3LYP",
        job_kind="opt",
    )
    unknown = resolve_scientific_setting_v2(
        registry=registry,
        loaded_inventories=inventories,
        program="gaussian",
        setting_path="method.functional",
        value="definitely-unknown-92831",
        job_kind="opt",
        allow_fuzzy_candidates=False,
    )
    not_applicable = resolve_scientific_setting_v2(
        registry=registry,
        loaded_inventories=inventories,
        program="xtb",
        setting_path="method.basis",
        value="def2-SVP",
        job_kind="sp",
    )

    assert job_mismatch.status is SettingResolutionStatusV2.INCOMPATIBLE
    assert job_mismatch.matched_by is SettingMatchKindV2.JOB_SCOPE_MISMATCH
    assert job_mismatch.job_scope_compatible is False
    assert elsewhere.status is SettingResolutionStatusV2.INCOMPATIBLE
    assert elsewhere.matched_by is SettingMatchKindV2.REGISTERED_ELSEWHERE
    assert elsewhere.job_scope_compatible is None
    assert unknown.status is SettingResolutionStatusV2.UNKNOWN_UNVERIFIED
    assert unknown.source_registered is False
    assert unknown.loader_accepted is False
    assert unknown.project_candidate_eligible is False
    assert not_applicable.status is SettingResolutionStatusV2.NOT_APPLICABLE
    assert not_applicable.reason_rule_id == (
        "scientific_settings.v2.xtb_basis_not_applicable"
    )


def test_v2_fuzzy_candidates_are_ranked_but_never_substituted(tmp_path):
    registry, inventories = _loaded_lookup_context(
        tmp_path,
        entries=(
            _entry(
                entry_id="entry.b3lyp",
                canonical_value="B3LYP",
            ),
            _entry(
                entry_id="entry.b3pw91",
                canonical_value="B3PW91",
            ),
        ),
    )

    first = resolve_scientific_setting_v2(
        registry=registry,
        loaded_inventories=inventories,
        program="gaussian",
        setting_path="method.functional",
        value="B3LYPP",
        job_kind="opt",
    )
    repeated = resolve_scientific_setting_v2(
        registry=registry,
        loaded_inventories=inventories,
        program="gaussian",
        setting_path="method.functional",
        value="B3LYPP",
        job_kind="opt",
    )

    assert first.status is SettingResolutionStatusV2.CANDIDATE_ONLY
    assert first.entry_id is None
    assert first.canonical_value is None
    assert first.source_registered is False
    assert first.project_candidate_eligible is False
    assert first.candidates[0].canonical_value == "B3LYP"
    assert first.candidates[0].source_registered is True
    assert first.resolution_sha256 == repeated.resolution_sha256
    assert first.candidates == repeated.candidates


def test_v2_bounded_listing_preserves_eligibility_and_not_applicable(tmp_path):
    registry, inventories = _loaded_lookup_context(
        tmp_path,
        entries=(
            _entry(
                entry_id="entry.b3lyp",
                canonical_value="B3LYP",
            ),
            _entry(
                entry_id="entry.m062x",
                canonical_value="M06-2X",
                applicability_rule_ids=(
                    "scientific_settings.functional.m062x_scope",
                ),
                validator_enforced=False,
            ),
        ),
    )

    bounded = list_scientific_settings_v2(
        registry=registry,
        loaded_inventories=inventories,
        program="gaussian",
        setting_path="method.functional",
        job_kind="opt",
        limit=1,
    )
    searched = list_scientific_settings_v2(
        registry=registry,
        loaded_inventories=inventories,
        program="gaussian",
        setting_path="method.functional",
        job_kind="opt",
        query="M06-2Y",
    )
    searched_repeated = list_scientific_settings_v2(
        registry=registry,
        loaded_inventories=inventories,
        program="gaussian",
        setting_path="method.functional",
        job_kind="opt",
        query="M06-2Y",
    )
    not_applicable = list_scientific_settings_v2(
        registry=registry,
        loaded_inventories=inventories,
        program="xtb",
        setting_path="method.basis",
        job_kind="sp",
    )

    assert bounded.status is ScientificSettingsListStatusV2.OK
    assert bounded.inventory_count == 2
    assert bounded.returned_count == 1
    assert bounded.truncated is True
    assert bounded.items[0].canonical_value == "B3LYP"
    assert searched.items[0].canonical_value == "M06-2X"
    assert searched.items[0].applicability_rules_present is True
    assert searched.items[0].deterministic_validator_enforced is False
    assert searched.items[0].project_candidate_eligible is False
    assert searched.listing_sha256 == searched_repeated.listing_sha256
    assert not_applicable.status is (
        ScientificSettingsListStatusV2.NOT_APPLICABLE
    )
    assert not_applicable.items == ()


def test_v2_resolution_hash_rejects_observation_tampering(tmp_path):
    registry, inventories = _loaded_lookup_context(
        tmp_path,
        entries=(
            _entry(entry_id="entry.b3lyp", canonical_value="B3LYP"),
        ),
    )
    resolution = resolve_scientific_setting_v2(
        registry=registry,
        loaded_inventories=inventories,
        program="gaussian",
        setting_path="method.functional",
        value="B3LYP",
        job_kind="opt",
    )
    payload = resolution.model_dump(mode="json")
    payload["renderer_preserved"] = False

    with pytest.raises(ValidationError):
        SettingResolutionV2.model_validate(payload)


def _entry(
    *,
    entry_id: str,
    canonical_value: str,
    program: str = "gaussian",
    setting_path: str = "method.functional",
    aliases: tuple[str, ...] = (),
    applicable_job_kinds: tuple[str, ...] = ("*",),
    applicability_rule_ids: tuple[str, ...] = (),
    validator_enforced: bool = False,
) -> dict[str, object]:
    return {
        "entry_id": entry_id,
        "program": program,
        "setting_path": setting_path,
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
    entry_count: int = 1,
    scopes: tuple[dict[str, object], ...] | None = None,
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
        "entry_count": entry_count,
        "scopes": scopes
        or (
            {
                "program": "gaussian",
                "setting_path": "method.functional",
                "entry_count": entry_count,
            },
        ),
    }


def _loaded_lookup_context(
    tmp_path,
    *,
    entries: tuple[dict[str, object], ...],
):
    ordered_entries = tuple(sorted(entries, key=lambda item: item["entry_id"]))
    inventory_payload = _inventory_payload(ordered_entries)
    artifact_bytes = json.dumps(
        inventory_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    artifact_path = tmp_path / "inventory.json"
    artifact_path.write_bytes(artifact_bytes)

    counts = Counter(
        (str(item["program"]), str(item["setting_path"]))
        for item in ordered_entries
    )
    scopes = tuple(
        {
            "program": program,
            "setting_path": setting_path,
            "entry_count": count,
        }
        for (program, setting_path), count in sorted(counts.items())
    )
    descriptor = ScientificSettingsInventoryDescriptorV2.model_validate(
        _descriptor_payload(
            inventory_sha256=str(inventory_payload["inventory_sha256"]),
            artifact_sha256=hashlib.sha256(artifact_bytes).hexdigest(),
            entry_count=len(ordered_entries),
            scopes=scopes,
        )
    )
    registry_body = load_scientific_settings_registry_v2().model_dump(mode="json")
    registry_body["registry_id"] = "chemsmart.scientific-settings.test-lookup"
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
    return registry, (loaded,)
