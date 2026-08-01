"""Explicit V2 loading and fail-closed digest-addressed registry replay."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from chemsmart.agent.harness.scientific_settings.contracts import (
    SCIENTIFIC_SETTINGS_REGISTRY_SCHEMA_VERSION,
    ScientificSettingsRegistryV1,
)
from chemsmart.agent.harness.scientific_settings.contracts_v2 import (
    ScientificSettingsInventoryDescriptorV2,
    ScientificSettingsInventoryScopeV2,
    ScientificSettingsInventoryV2,
    ScientificSettingsRegistryV2,
    scientific_settings_registry_v2_sha256,
)
from chemsmart.agent.harness.scientific_settings.manifest_v2 import (
    FROZEN_MANIFEST_V2,
    FROZEN_V2_REGISTRY_SHA256,
)
from chemsmart.agent.harness.scientific_settings.registry import (
    load_scientific_settings_registry_v1,
)


ScientificSettingsRegistrySnapshot = (
    ScientificSettingsRegistryV1 | ScientificSettingsRegistryV2
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ScientificSettingsRegistryDigestNotFoundError(LookupError):
    """Raised when no immutable registry snapshot has the requested digest."""


class ScientificSettingsInventoryArtifactError(ValueError):
    """Raised when an inventory artifact fails a deterministic binding."""


@lru_cache(maxsize=1)
def load_scientific_settings_registry_v2() -> ScientificSettingsRegistryV2:
    """Load the separate, experimental V2 skeleton.

    This does not alter the unversioned V1 loader or make V2 a runtime
    authority.  The initial V2 snapshot intentionally has no inventory.
    """

    body = dict(FROZEN_MANIFEST_V2)
    observed_sha256 = scientific_settings_registry_v2_sha256(body)
    if observed_sha256 != FROZEN_V2_REGISTRY_SHA256:
        raise ValueError("frozen V2 registry digest does not match its manifest")
    body["registry_sha256"] = observed_sha256
    registry = ScientificSettingsRegistryV2.model_validate(body)

    predecessor = registry.predecessor
    v1 = load_scientific_settings_registry_v1()
    expected_predecessor = (
        SCIENTIFIC_SETTINGS_REGISTRY_SCHEMA_VERSION,
        v1.registry_id,
        v1.registry_version,
        v1.registry_sha256,
    )
    observed_predecessor = (
        predecessor.target_schema_version,
        predecessor.registry_id,
        predecessor.registry_version,
        predecessor.registry_sha256,
    )
    if observed_predecessor != expected_predecessor:
        raise ValueError("V2 predecessor does not match the exact V1 snapshot")
    return registry


def load_scientific_settings_inventory_v2(
    *,
    registry: ScientificSettingsRegistryV2,
    descriptor: ScientificSettingsInventoryDescriptorV2,
    repository_root: str | Path | None = None,
) -> ScientificSettingsInventoryV2:
    """Load one descriptor-bound inventory with exact-byte verification.

    The empty V2 skeleton cannot use this function because it has no declared
    descriptor.  A populated registry must bind the descriptor before any
    artifact path is opened.
    """

    validated_registry = ScientificSettingsRegistryV2.model_validate(
        registry.model_dump(mode="json")
    )
    validated_descriptor = ScientificSettingsInventoryDescriptorV2.model_validate(
        descriptor.model_dump(mode="json")
    )
    if validated_registry.inventory_population_state != "populated":
        raise ScientificSettingsInventoryArtifactError(
            "an empty registry cannot load an inventory artifact"
        )
    if validated_descriptor not in validated_registry.inventories:
        raise ScientificSettingsInventoryArtifactError(
            "inventory descriptor is not bound by the registry"
        )

    root = (
        Path(repository_root)
        if repository_root is not None
        else Path(__file__).resolve().parents[4]
    ).resolve()
    relative = PurePosixPath(validated_descriptor.artifact_locator)
    artifact_path = root.joinpath(*relative.parts).resolve()
    if not artifact_path.is_relative_to(root):
        raise ScientificSettingsInventoryArtifactError(
            "inventory artifact escapes the repository root"
        )
    if not artifact_path.is_file():
        raise ScientificSettingsInventoryArtifactError(
            "inventory artifact is missing"
        )

    artifact_bytes = artifact_path.read_bytes()
    artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    if artifact_sha256 != validated_descriptor.artifact_sha256:
        raise ScientificSettingsInventoryArtifactError(
            "inventory artifact exact-byte SHA-256 mismatch"
        )
    try:
        payload = json.loads(
            artifact_bytes.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ScientificSettingsInventoryArtifactError(
            "inventory artifact is not duplicate-free UTF-8 JSON"
        ) from exc
    try:
        inventory = ScientificSettingsInventoryV2.model_validate(payload)
    except ValueError as exc:
        raise ScientificSettingsInventoryArtifactError(
            "inventory artifact violates the V2 contract"
        ) from exc

    observed_scopes = _inventory_scopes(inventory)
    mismatches = (
        inventory.schema_version
        != validated_descriptor.inventory_schema_version,
        inventory.normalization_version
        != validated_descriptor.normalization_version,
        inventory.inventory_id != validated_descriptor.inventory_id,
        inventory.inventory_version != validated_descriptor.inventory_version,
        inventory.inventory_sha256 != validated_descriptor.inventory_sha256,
        len(inventory.entries) != validated_descriptor.entry_count,
        observed_scopes != validated_descriptor.scopes,
        inventory.evidence_ceiling != validated_registry.evidence_ceiling,
    )
    if any(mismatches):
        raise ScientificSettingsInventoryArtifactError(
            "inventory artifact metadata does not match its registry descriptor"
        )
    return inventory


def load_scientific_settings_registry_by_sha256(
    registry_sha256: str,
) -> ScientificSettingsRegistrySnapshot:
    """Replay an exact known registry generation without implicit migration."""

    if not isinstance(registry_sha256, str) or _SHA256.fullmatch(
        registry_sha256
    ) is None:
        raise ValueError("registry_sha256 must be 64 lowercase hexadecimal digits")

    v1 = load_scientific_settings_registry_v1()
    if registry_sha256 == v1.registry_sha256:
        return v1

    v2 = load_scientific_settings_registry_v2()
    if registry_sha256 == v2.registry_sha256:
        return v2

    raise ScientificSettingsRegistryDigestNotFoundError(
        f"unknown scientific-settings registry digest: {registry_sha256}"
    )


def _inventory_scopes(
    inventory: ScientificSettingsInventoryV2,
) -> tuple[ScientificSettingsInventoryScopeV2, ...]:
    counts = Counter(
        (entry.program, entry.setting_path) for entry in inventory.entries
    )
    return tuple(
        ScientificSettingsInventoryScopeV2(
            program=program,
            setting_path=setting_path,
            entry_count=count,
        )
        for (program, setting_path), count in sorted(
            counts.items(), key=lambda item: (item[0][0].value, item[0][1])
        )
    )


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


__all__ = [
    "ScientificSettingsInventoryArtifactError",
    "ScientificSettingsRegistryDigestNotFoundError",
    "ScientificSettingsRegistrySnapshot",
    "load_scientific_settings_inventory_v2",
    "load_scientific_settings_registry_by_sha256",
    "load_scientific_settings_registry_v2",
]
