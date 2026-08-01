"""Frozen repair sidecar for non-exhaustive Registry V2 capability slices."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from chemsmart.agent.harness.scientific_settings.contracts_v2 import (
    SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION,
    SettingInventoryEntryV2,
    normalize_setting_literal_for_version,
)
from chemsmart.agent.harness.scientific_settings.registry import (
    load_scientific_settings_registry_v1,
)
from chemsmart.agent.harness.scientific_settings.registry_v2 import (
    load_populated_scientific_settings_inventories_v2,
    load_populated_scientific_settings_registry_v2,
)
from chemsmart.agent.harness.scientific_settings.repair_contracts_v2 import (
    CarryForwardProbeV2,
    ScopeCompletenessV2,
    ScientificSettingsRepairSidecarV2,
    carry_forward_probe_v2_sha256,
    scientific_settings_repair_sidecar_v2_sha256,
)
from chemsmart.agent.project_protocol import render_project_document
from chemsmart.settings.gaussian import YamlGaussianProjectSettings


FROZEN_REPAIR_SIDECAR_V2_SHA256 = (
    "c20cc93e5fa734524beb610d44c53b641167d202e74f9155f99ec7af42ff1ca7"
)

_CARRY_FORWARD_ENTRY_ID = (
    "setting.gaussian.method_functional.carryforward_b3lyp"
)
_SOURCE_IDS = (
    "gaussian-job-settings-125f2878",
    "gaussian-project-loader-125f2878",
    "gaussian-reference-125f2878",
    "project-protocol-125f2878",
)
_EXHAUSTIVE_SCOPES = frozenset(
    {
        ("xtb", "method.basis"),
        ("xtb", "method.gfn_version"),
        ("xtb", "optimization.level"),
        ("xtb", "solvent.id"),
        ("xtb", "solvent.model"),
    }
)
_TARGET_ENTRY_IDS = {
    "gaussian.basis.def2-tzvp": (
        "setting.gaussian.method_basis.d3a76ab40220bac1932e"
    ),
    "orca.basis.ma-def2-tzvp": (
        "setting.orca.method_basis.cacd75214ff3402d48ea"
    ),
    "orca.dispersion.d3bj": (
        "setting.orca.method_dispersion.e73ac4973a18172cac80"
    ),
    "orca.functional.b3lyp": (
        "setting.orca.method_functional.d34018d588c050ffd3c5"
    ),
    "xtb.method.gfn2": (
        "setting.xtb.method_gfn_version.ca97034691da605500c6"
    ),
}


def build_gaussian_b3lyp_carry_forward_probe_v2(
    probe_path: str | Path,
) -> CarryForwardProbeV2:
    """Probe B3LYP through the current paper renderer and real YAML loader."""

    path = Path(probe_path)
    rendered = render_project_document(
        {
            "method": {
                "functional": "B3LYP",
                "basis": "def2-SVP",
                "freq": False,
            }
        },
        "registry_repair_probe",
        "gaussian",
        profile="paper",
    )
    yaml_text = rendered.get("yaml_text")
    if not isinstance(yaml_text, str):
        raise ValueError("Gaussian B3LYP carry-forward renderer probe failed")
    document = yaml.safe_load(yaml_text)
    if not isinstance(document, dict):
        raise ValueError("Gaussian B3LYP carry-forward probe produced invalid YAML")
    path.write_text(yaml_text, encoding="utf-8")
    loaded = YamlGaussianProjectSettings.from_yaml(str(path)).opt_settings()
    return _probe(
        rendered_literal=str(document["gas"]["functional"]),
        loaded_literal=str(loaded.functional),
    )


def _probe(*, rendered_literal: str, loaded_literal: str) -> CarryForwardProbeV2:
    body: dict[str, Any] = {
        "schema_version": (
            "chemsmart.scientific-settings-carry-forward-probe.v2"
        ),
        "probe_sha256": "0" * 64,
        "predecessor_capability_id": "gaussian.functional.b3lyp",
        "entry_id": _CARRY_FORWARD_ENTRY_ID,
        "program": "gaussian",
        "setting_path": "method.functional",
        "normalization_version": (
            SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION
        ),
        "input_literal": "B3LYP",
        "rendered_literals": (rendered_literal,),
        "loaded_literals": (loaded_literal,),
        "carry_forward_canonical_value": "B3LYP",
        "normalized_semantic_literal": normalize_setting_literal_for_version(
            "B3LYP",
            SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION,
        ),
        "observed_job_kinds": ("opt",),
        "transform_id": "paper_project.functional_literal_normalization",
        "loader_accepted": True,
        "renderer_preserved": True,
        "safe_preview_executed": False,
        "engine_executed": False,
    }
    body["probe_sha256"] = carry_forward_probe_v2_sha256(body)
    return CarryForwardProbeV2.model_validate(body)


def _carry_forward_entry() -> SettingInventoryEntryV2:
    return SettingInventoryEntryV2(
        entry_id=_CARRY_FORWARD_ENTRY_ID,
        program="gaussian",
        setting_path="method.functional",
        canonical_value="B3LYP",
        aliases=("b3-lyp",),
        applicable_job_kinds=("opt",),
        applicability_rule_ids=(),
        validator_enforced=False,
        source_ids=_SOURCE_IDS,
        loader_observation="accepted",
        renderer_observation="preserved",
        observation_note=(
            "Current paper renderer and Gaussian project loader preserved "
            "B3LYP as b3lyp for opt. The predecessor wildcard job scope is "
            "not reasserted; no safe preview or engine execution occurred."
        ),
        engine_executed=False,
        combination_verified=False,
    )


def _sidecar_body() -> dict[str, Any]:
    registry = load_populated_scientific_settings_registry_v2()
    inventories = load_populated_scientific_settings_inventories_v2()
    all_sources = {
        source.source_id: source
        for inventory in inventories
        for source in inventory.sources
    }
    sources = tuple(all_sources[source_id] for source_id in _SOURCE_IDS)
    scope_keys = sorted(
        {
            (scope.program.value, scope.setting_path)
            for descriptor in registry.inventories
            for scope in descriptor.scopes
        }
        | {("xtb", "method.basis")}
    )
    scopes = tuple(
        {
            "program": program,
            "setting_path": setting_path,
            "completeness": (
                ScopeCompletenessV2.EXHAUSTIVE_TYPED_DOMAIN.value
                if (program, setting_path) in _EXHAUSTIVE_SCOPES
                else ScopeCompletenessV2.ENUMERATED_NON_EXHAUSTIVE.value
            ),
            "reason_rule_ids": (
                (
                    "scientific_settings.scope.closed_typed_domain",
                )
                if (program, setting_path) in _EXHAUSTIVE_SCOPES
                else (
                    "scientific_settings.scope.enumerated_non_exhaustive",
                )
            ),
        }
        for program, setting_path in scope_keys
    )
    dispositions = []
    for capability_id in sorted(
        capability.capability_id
        for overlay in load_scientific_settings_registry_v1().overlays
        for capability in overlay.capabilities
    ):
        is_probe = capability_id == "gaussian.functional.b3lyp"
        dispositions.append(
            {
                "predecessor_capability_id": capability_id,
                "disposition": (
                    "carry_forward_probe"
                    if is_probe
                    else "present_in_bound_inventory"
                ),
                "target_entry_id": (
                    _CARRY_FORWARD_ENTRY_ID
                    if is_probe
                    else _TARGET_ENTRY_IDS[capability_id]
                ),
                "reason_rule_ids": (
                    (
                        "scientific_settings.repair.predecessor_capability_probed",
                        "scientific_settings.repair.predecessor_job_scope_narrowed",
                    )
                    if is_probe
                    else (
                        "scientific_settings.repair.predecessor_capability_present",
                    )
                ),
            }
        )
    return {
        "schema_version": "chemsmart.scientific-settings-repair-sidecar.v2",
        "sidecar_id": "chemsmart.scientific-settings.repair-0a26c0da",
        "sidecar_version": "1.1.0",
        "sidecar_sha256": FROZEN_REPAIR_SIDECAR_V2_SHA256,
        "base_registry_sha256": registry.registry_sha256,
        "base_inventory_sha256s": tuple(
            sorted(inventory.inventory_sha256 for inventory in inventories)
        ),
        "predecessor_registry_sha256": registry.predecessor.registry_sha256,
        "sources": tuple(source.model_dump(mode="json") for source in sources),
        "scopes": scopes,
        "carry_forward_entries": (
            _carry_forward_entry().model_dump(mode="json"),
        ),
        "carry_forward_probes": (
            _probe(
                rendered_literal="b3lyp",
                loaded_literal="b3lyp",
            ).model_dump(mode="json"),
        ),
        "predecessor_dispositions": tuple(dispositions),
    }


@lru_cache(maxsize=1)
def load_scientific_settings_repair_sidecar_v2(
) -> ScientificSettingsRepairSidecarV2:
    body = _sidecar_body()
    observed = scientific_settings_repair_sidecar_v2_sha256(body)
    if observed != FROZEN_REPAIR_SIDECAR_V2_SHA256:
        raise ValueError("frozen Registry V2 repair sidecar digest mismatch")
    sidecar = ScientificSettingsRepairSidecarV2.model_validate(body)
    _validate_predecessor_monotonicity(sidecar)
    return sidecar


def _validate_predecessor_monotonicity(
    sidecar: ScientificSettingsRepairSidecarV2,
) -> None:
    predecessor = load_scientific_settings_registry_v1()
    inventories = load_populated_scientific_settings_inventories_v2()
    base_entries = {
        entry.entry_id: entry
        for inventory in inventories
        for entry in inventory.entries
    }
    carry_entries = {entry.entry_id: entry for entry in sidecar.carry_forward_entries}
    dispositions = {
        item.predecessor_capability_id: item
        for item in sidecar.predecessor_dispositions
    }
    capabilities = {
        capability.capability_id: capability
        for overlay in predecessor.overlays
        for capability in overlay.capabilities
    }
    if set(dispositions) != set(capabilities):
        raise ValueError("repair sidecar does not disposition every V1 capability")
    normalization_version = inventories[0].normalization_version
    for capability_id, capability in capabilities.items():
        disposition = dispositions[capability_id]
        if disposition.disposition == "retired":
            continue
        entries = (
            carry_entries
            if disposition.disposition == "carry_forward_probe"
            else base_entries
        )
        entry = entries.get(str(disposition.target_entry_id))
        if entry is None:
            raise ValueError("V1 capability target is absent from bound evidence")
        if (
            entry.program is not capability.program
            or entry.setting_path != capability.setting_path
        ):
            raise ValueError("V1 capability target changed program or setting path")
        expected = normalize_setting_literal_for_version(
            capability.canonical_value,
            normalization_version,
        )
        observed = {
            normalize_setting_literal_for_version(value, normalization_version)
            for value in (entry.canonical_value, *entry.aliases)
        }
        if expected not in observed:
            raise ValueError("V1 capability literal was not carried forward")


def repair_sidecar_scope_policy(
    sidecar: ScientificSettingsRepairSidecarV2,
    *,
    program: str,
    setting_path: str,
):
    matches = tuple(
        scope
        for scope in sidecar.scopes
        if scope.program.value == program and scope.setting_path == setting_path
    )
    if len(matches) != 1:
        raise ValueError("repair sidecar has no unique requested scope policy")
    return matches[0]


__all__ = [
    "FROZEN_REPAIR_SIDECAR_V2_SHA256",
    "build_gaussian_b3lyp_carry_forward_probe_v2",
    "load_scientific_settings_repair_sidecar_v2",
    "repair_sidecar_scope_policy",
]
