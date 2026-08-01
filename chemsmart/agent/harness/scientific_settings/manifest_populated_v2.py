"""Frozen populated scientific-settings registry V2 manifest."""

from __future__ import annotations

from chemsmart.agent.harness.scientific_settings.contracts_v2 import (
    SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION,
    SCIENTIFIC_SETTINGS_INVENTORY_DESCRIPTOR_V2_SCHEMA_VERSION,
    SCIENTIFIC_SETTINGS_INVENTORY_V2_SCHEMA_VERSION,
    SCIENTIFIC_SETTINGS_REGISTRY_REF_V2_SCHEMA_VERSION,
    SCIENTIFIC_SETTINGS_REGISTRY_V2_SCHEMA_VERSION,
)
from chemsmart.agent.harness.scientific_settings.manifest import (
    FROZEN_EVIDENCE_CEILING_V1,
)
from chemsmart.agent.harness.scientific_settings.manifest_v2 import (
    FROZEN_V1_REGISTRY_SHA256,
)


FROZEN_POPULATED_V2_REGISTRY_SHA256 = (
    "3331cd8a74b1343e31da2b7df4530f50fcbaa9bf4894aad7abf9b7257f36ee7f"
)
FROZEN_POPULATED_V2_INVENTORY_SHA256 = (
    "cb6eaa89f210eb82743045472d5fcd16e3935d0abbe218468c90d33a8523a1fe"
)
FROZEN_POPULATED_V2_INVENTORY_ARTIFACT_SHA256 = (
    "c684b1da7f338aab6738b5dcb19d6dd4176847fddc57fc2d91fd2e587673edd4"
)
FROZEN_POPULATED_V2_GENERATION_RECEIPT_SHA256 = (
    "97581167614c886fb9d690a390940cb90f063637f4b3cb0e1e3d9c8e4abc084b"
)
FROZEN_POPULATED_V2_GENERATION_RECEIPT_ARTIFACT_SHA256 = (
    "a9975d16233404eed491b6693c136ce0c03ec8167d299dca6ff22012b1684148"
)
FROZEN_POPULATED_V2_GENERATION_RECEIPT = {
    "locator": (
        "chemsmart/agent/harness/scientific_settings/data/"
        "scientific_settings_inventory_v2_generation_receipt.json"
    ),
    "receipt_sha256": FROZEN_POPULATED_V2_GENERATION_RECEIPT_SHA256,
    "artifact_sha256": (
        FROZEN_POPULATED_V2_GENERATION_RECEIPT_ARTIFACT_SHA256
    ),
    "source_revision": "125f2878d46b948e20cd1fba5baeaaa65f08f8d0",
}

_INVENTORY_DESCRIPTOR = {
    "schema_version": (
        SCIENTIFIC_SETTINGS_INVENTORY_DESCRIPTOR_V2_SCHEMA_VERSION
    ),
    "inventory_schema_version": SCIENTIFIC_SETTINGS_INVENTORY_V2_SCHEMA_VERSION,
    "normalization_version": (
        SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION
    ),
    "inventory_id": "chemsmart.scientific-settings.inventory-125f2878",
    "inventory_version": "2.1.0",
    "inventory_sha256": FROZEN_POPULATED_V2_INVENTORY_SHA256,
    "artifact_locator": (
        "chemsmart/agent/harness/scientific_settings/data/"
        "scientific_settings_inventory_v2.json"
    ),
    "artifact_sha256": FROZEN_POPULATED_V2_INVENTORY_ARTIFACT_SHA256,
    "entry_count": 1771,
    "scopes": (
        {
            "program": "gaussian",
            "setting_path": "method.basis",
            "entry_count": 642,
        },
        {
            "program": "gaussian",
            "setting_path": "method.dispersion",
            "entry_count": 2,
        },
        {
            "program": "gaussian",
            "setting_path": "method.functional",
            "entry_count": 11,
        },
        {
            "program": "gaussian",
            "setting_path": "method.integration_grid",
            "entry_count": 1,
        },
        {
            "program": "gaussian",
            "setting_path": "solvent.id",
            "entry_count": 12,
        },
        {
            "program": "gaussian",
            "setting_path": "solvent.model",
            "entry_count": 7,
        },
        {
            "program": "orca",
            "setting_path": "method.basis",
            "entry_count": 772,
        },
        {
            "program": "orca",
            "setting_path": "method.dispersion",
            "entry_count": 2,
        },
        {
            "program": "orca",
            "setting_path": "method.functional",
            "entry_count": 94,
        },
        {
            "program": "orca",
            "setting_path": "solvent.id",
            "entry_count": 180,
        },
        {
            "program": "orca",
            "setting_path": "solvent.model",
            "entry_count": 4,
        },
        {
            "program": "xtb",
            "setting_path": "method.gfn_version",
            "entry_count": 4,
        },
        {
            "program": "xtb",
            "setting_path": "optimization.level",
            "entry_count": 8,
        },
        {
            "program": "xtb",
            "setting_path": "solvent.id",
            "entry_count": 27,
        },
        {
            "program": "xtb",
            "setting_path": "solvent.model",
            "entry_count": 5,
        },
    ),
}

FROZEN_POPULATED_MANIFEST_V2 = {
    "schema_version": SCIENTIFIC_SETTINGS_REGISTRY_V2_SCHEMA_VERSION,
    "registry_id": "chemsmart.scientific-settings.v2-populated-125f2878",
    "registry_version": "2.1.0",
    "chemsmart_version": "2.0.1",
    "source_revision": "125f2878d46b948e20cd1fba5baeaaa65f08f8d0",
    "cli_schema_sha256": (
        "0cc218099762f0dd3f5bc0dabecbd29dab5c29666c8691dbc5d0f9b633850ebb"
    ),
    "predecessor": {
        "schema_version": SCIENTIFIC_SETTINGS_REGISTRY_REF_V2_SCHEMA_VERSION,
        "target_schema_version": "chemsmart.scientific-settings-registry.v1",
        "registry_id": "chemsmart.scientific-settings.source-snapshot-c793db6",
        "registry_version": "1.0.0",
        "registry_sha256": FROZEN_V1_REGISTRY_SHA256,
    },
    "inventories": (_INVENTORY_DESCRIPTOR,),
    "inventory_population_state": "populated",
    "evidence_ceiling": FROZEN_EVIDENCE_CEILING_V1,
    "experimental": True,
    "default_runtime_authority": False,
}


__all__ = [
    "FROZEN_POPULATED_MANIFEST_V2",
    "FROZEN_POPULATED_V2_GENERATION_RECEIPT",
    "FROZEN_POPULATED_V2_GENERATION_RECEIPT_ARTIFACT_SHA256",
    "FROZEN_POPULATED_V2_GENERATION_RECEIPT_SHA256",
    "FROZEN_POPULATED_V2_INVENTORY_ARTIFACT_SHA256",
    "FROZEN_POPULATED_V2_INVENTORY_SHA256",
    "FROZEN_POPULATED_V2_REGISTRY_SHA256",
]
