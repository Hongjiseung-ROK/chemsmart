"""Policy-bound lookup over the immutable populated Registry V2 snapshot."""

from __future__ import annotations

from typing import Sequence

from chemsmart.agent.harness.scientific_settings.contracts import (
    ScientificProgram,
)
from chemsmart.agent.harness.scientific_settings.contracts_v2 import (
    ScientificSettingsInventoryV2,
    ScientificSettingsRegistryV2,
)
from chemsmart.agent.harness.scientific_settings.lookup_v2 import (
    list_scientific_settings_v2,
    resolve_scientific_setting_v2,
)
from chemsmart.agent.harness.scientific_settings.repair_contracts_v2 import (
    PolicyBoundScientificSettingsListV2,
    PolicyBoundSettingResolutionV2,
    ScopeCompletenessV2,
    ScientificSettingsRepairSidecarV2,
    ScientificSettingsScopePolicyV2,
    policy_bound_scientific_settings_list_v2_sha256,
    policy_bound_setting_resolution_v2_sha256,
)
from chemsmart.agent.harness.scientific_settings.repair_v2 import (
    load_scientific_settings_repair_sidecar_v2,
    repair_sidecar_scope_policy,
)


def resolve_scientific_setting_repaired_v2(
    *,
    registry: ScientificSettingsRegistryV2,
    loaded_inventories: Sequence[ScientificSettingsInventoryV2],
    program: ScientificProgram | str,
    setting_path: str,
    value: str,
    job_kind: str,
    allow_fuzzy_candidates: bool = True,
    candidate_limit: int = 5,
    sidecar: ScientificSettingsRepairSidecarV2 | None = None,
) -> PolicyBoundSettingResolutionV2:
    """Resolve with explicit completeness and carry-forward evidence.

    The nested V2 resolution retains the immutable base registry and inventory
    digests.  The outer binding makes the repair sidecar and its scope policy
    part of the evidence identity.
    """

    bound_sidecar, scope = _bound_repair_context(
        registry=registry,
        loaded_inventories=loaded_inventories,
        program=program,
        setting_path=setting_path,
        sidecar=sidecar,
    )
    resolution = resolve_scientific_setting_v2(
        registry=registry,
        loaded_inventories=loaded_inventories,
        program=program,
        setting_path=setting_path,
        value=value,
        job_kind=job_kind,
        allow_fuzzy_candidates=allow_fuzzy_candidates,
        candidate_limit=candidate_limit,
        _additional_bound_entries=bound_sidecar.carry_forward_entries,
        _registered_elsewhere_is_incompatible=(
            scope.completeness is ScopeCompletenessV2.EXHAUSTIVE_TYPED_DOMAIN
        ),
    )
    body = {
        "schema_version": "chemsmart.policy-bound-setting-resolution.v2",
        "binding_sha256": "0" * 64,
        "sidecar_sha256": bound_sidecar.sidecar_sha256,
        "scope_completeness": scope.completeness,
        "resolution": resolution.model_dump(mode="json"),
    }
    body["binding_sha256"] = policy_bound_setting_resolution_v2_sha256(body)
    return PolicyBoundSettingResolutionV2.model_validate(body)


def list_scientific_settings_repaired_v2(
    *,
    registry: ScientificSettingsRegistryV2,
    loaded_inventories: Sequence[ScientificSettingsInventoryV2],
    program: ScientificProgram | str,
    setting_path: str,
    job_kind: str,
    query: str = "",
    limit: int = 20,
    sidecar: ScientificSettingsRepairSidecarV2 | None = None,
) -> PolicyBoundScientificSettingsListV2:
    """List the same sidecar-bound entries and scope used by repaired resolve."""

    bound_sidecar, scope = _bound_repair_context(
        registry=registry,
        loaded_inventories=loaded_inventories,
        program=program,
        setting_path=setting_path,
        sidecar=sidecar,
    )
    listing = list_scientific_settings_v2(
        registry=registry,
        loaded_inventories=loaded_inventories,
        program=program,
        setting_path=setting_path,
        job_kind=job_kind,
        query=query,
        limit=limit,
        _additional_bound_entries=bound_sidecar.carry_forward_entries,
    )
    body = {
        "schema_version": "chemsmart.policy-bound-scientific-settings-list.v2",
        "binding_sha256": "0" * 64,
        "sidecar_sha256": bound_sidecar.sidecar_sha256,
        "scope_completeness": scope.completeness,
        "listing": listing.model_dump(mode="json"),
    }
    body["binding_sha256"] = (
        policy_bound_scientific_settings_list_v2_sha256(body)
    )
    return PolicyBoundScientificSettingsListV2.model_validate(body)


def _bound_repair_context(
    *,
    registry: ScientificSettingsRegistryV2,
    loaded_inventories: Sequence[ScientificSettingsInventoryV2],
    program: ScientificProgram | str,
    setting_path: str,
    sidecar: ScientificSettingsRepairSidecarV2 | None,
) -> tuple[ScientificSettingsRepairSidecarV2, ScientificSettingsScopePolicyV2]:
    bound_sidecar = sidecar or load_scientific_settings_repair_sidecar_v2()
    inventory_sha256s = tuple(
        sorted(inventory.inventory_sha256 for inventory in loaded_inventories)
    )
    if registry.registry_sha256 != bound_sidecar.base_registry_sha256:
        raise ValueError("repair sidecar is bound to a different V2 registry")
    if inventory_sha256s != bound_sidecar.base_inventory_sha256s:
        raise ValueError("repair sidecar is bound to different V2 inventories")
    selected_program = (
        program
        if isinstance(program, ScientificProgram)
        else ScientificProgram(str(program).strip().casefold())
    )
    scope = repair_sidecar_scope_policy(
        bound_sidecar,
        program=selected_program.value,
        setting_path=setting_path,
    )
    return bound_sidecar, scope


__all__ = [
    "list_scientific_settings_repaired_v2",
    "resolve_scientific_setting_repaired_v2",
]
