"""Empty, lineage-bound scientific-settings registry V2 manifest."""

from __future__ import annotations

from chemsmart.agent.harness.scientific_settings.contracts_v2 import (
    SCIENTIFIC_SETTINGS_REGISTRY_REF_V2_SCHEMA_VERSION,
    SCIENTIFIC_SETTINGS_REGISTRY_V2_SCHEMA_VERSION,
)
from chemsmart.agent.harness.scientific_settings.manifest import (
    FROZEN_EVIDENCE_CEILING_V1,
)


FROZEN_V1_REGISTRY_SHA256 = (
    "ff7ee8b9371ae00981a82d8ee4b88e6dec8bf6910ad1cecf916d6f0e6645a3d4"
)
FROZEN_V2_REGISTRY_SHA256 = (
    "f7528e3f2cfbffcc72d2f677e9e146f80ab9e603207db6631789666b6af0db15"
)


FROZEN_MANIFEST_V2 = {
    "schema_version": SCIENTIFIC_SETTINGS_REGISTRY_V2_SCHEMA_VERSION,
    "registry_id": "chemsmart.scientific-settings.v2-skeleton-c793db6",
    "registry_version": "2.0.0-pre.1",
    "chemsmart_version": "2.0.1",
    "source_revision": "c793db616d313ef783085f0584f83f0ceca83b73",
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
    "inventories": (),
    "inventory_population_state": "empty_skeleton",
    "evidence_ceiling": FROZEN_EVIDENCE_CEILING_V1,
    "experimental": True,
    "default_runtime_authority": False,
}


__all__ = [
    "FROZEN_MANIFEST_V2",
    "FROZEN_V1_REGISTRY_SHA256",
    "FROZEN_V2_REGISTRY_SHA256",
]
