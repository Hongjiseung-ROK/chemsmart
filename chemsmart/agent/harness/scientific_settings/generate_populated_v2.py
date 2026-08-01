"""Generate the immutable, experimental populated V2 settings snapshot.

The generator is intentionally offline.  It reads checked-in references,
passes every included literal through the paper-profile renderer and the real
project-settings loader, and records exclusions and applicability gaps.  Its
coverage claim is limited to the enumerated typed project paths and observed
job families below; it is not a comprehensive engine-capability inventory.
It does not invoke a chemistry engine, safe preview, a provider, or the network.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import tempfile
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import yaml

from chemsmart.agent.harness.scientific_settings.contracts_v2 import (
    SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION,
    SCIENTIFIC_SETTINGS_INVENTORY_DESCRIPTOR_V2_SCHEMA_VERSION,
    SCIENTIFIC_SETTINGS_INVENTORY_V2_SCHEMA_VERSION,
    SCIENTIFIC_SETTINGS_REGISTRY_REF_V2_SCHEMA_VERSION,
    SCIENTIFIC_SETTINGS_REGISTRY_V2_SCHEMA_VERSION,
    ScientificSettingsInventoryDescriptorV2,
    ScientificSettingsInventoryScopeV2,
    ScientificSettingsInventoryV2,
    ScientificSettingsRegistryV2,
    SettingEvidenceSourceV2,
    SettingInventoryEntryV2,
    normalize_setting_literal_for_version,
    scientific_settings_inventory_v2_sha256,
    scientific_settings_registry_v2_sha256,
)
from chemsmart.agent.harness.scientific_settings.manifest import (
    FROZEN_EVIDENCE_CEILING_V1,
)
from chemsmart.agent.harness.scientific_settings.manifest_v2 import (
    FROZEN_V1_REGISTRY_SHA256,
)
from chemsmart.agent.project_protocol import render_project_document
from chemsmart.agent.project_yaml_values import SOLVENT_ALIASES
from chemsmart.io.gaussian import (
    GAUSSIAN_AB_INITIO,
    GAUSSIAN_ADDITIONAL_OPT_OPTIONS,
    GAUSSIAN_ADDITIONAL_ROUTE_PARAMETERS,
    GAUSSIAN_BASES,
    GAUSSIAN_FUNCTIONALS,
    GAUSSIAN_SEMIEMPIRICAL,
    GAUSSIAN_SOLVATION_MODELS,
)
from chemsmart.io.orca import (
    ORCA_ALL_AB_INITIO,
    ORCA_ALL_AUXILIARY_BASIS_SETS,
    ORCA_ALL_BASIS_SETS,
    ORCA_ALL_DENSITY_OPTIONS,
    ORCA_ALL_DISPERSION_CORRECTIONS,
    ORCA_ALL_EXTRAPOLATION_BASIS_SETS,
    ORCA_ALL_FUNCTIONALS,
    ORCA_ALL_JOB_TYPES,
    ORCA_ALL_SCF_ALGORITHMS,
    ORCA_ALL_SOLVENT_MODELS,
    ORCA_ALL_SOLVENTS,
    ORCA_SCF_CONVERGENCE,
)
from chemsmart.io.xtb import (
    XTB_ALL_GROUPS,
    XTB_ALL_JOB_TYPES,
    XTB_ALL_METHODS,
    XTB_ALL_OPT_ENGINES,
    XTB_ALL_OPT_LEVELS,
    XTB_ALL_SOLVENT_IDS,
    XTB_ALL_SOLVENT_MODELS,
)
from chemsmart.settings.gaussian import YamlGaussianProjectSettings
from chemsmart.settings.orca import YamlORCAProjectSettings
from chemsmart.settings.xtb import YamlXTBProjectSettings


SOURCE_CHECKPOINT = "125f2878d46b948e20cd1fba5baeaaa65f08f8d0"
CHEMSMART_VERSION = "2.0.1"
CLI_SCHEMA_SHA256 = (
    "0cc218099762f0dd3f5bc0dabecbd29dab5c29666c8691dbc5d0f9b633850ebb"
)
BSE_VERSION = "0.11"
BSE_ARTIFACT_SHA256 = (
    "ed4ef918fb80e8ad3c2396c237d2120c31892cfaa2a61fb61af52965dc723c0b"
)
BSE_CONTENT_SHA256 = (
    "a4c39327851ed653ec849c2109549cad4f0ee4e4207ea20143a368d25b2e2732"
)
INVENTORY_ID = "chemsmart.scientific-settings.inventory-125f2878"
INVENTORY_VERSION = "2.1.0"
REGISTRY_ID = "chemsmart.scientific-settings.v2-populated-125f2878"
REGISTRY_VERSION = "2.1.0"
INVENTORY_LOCATOR = (
    "chemsmart/agent/harness/scientific_settings/data/"
    "scientific_settings_inventory_v2.json"
)
RECEIPT_LOCATOR = (
    "chemsmart/agent/harness/scientific_settings/data/"
    "scientific_settings_inventory_v2_generation_receipt.json"
)
GENERATOR_LOCATOR = (
    "chemsmart/agent/harness/scientific_settings/"
    "generate_populated_v2.py"
)

_MATERIALIZATION_RULE = (
    "scientific_settings.basis.bse_materialization_required"
)
_ELEMENT_COVERAGE_RULE = (
    "scientific_settings.basis.request_element_coverage_required"
)
_ECP_RULE = "scientific_settings.basis.ecp_applicability_required"
_REGISTRY_INTEGRATION_RULE = (
    "scientific_settings.basis.registry_validator_integration_required"
)
_SOLVENT_PAIR_RULE = "scientific_settings.solvent.pair_required"
_XTB_SOLVENT_COMPATIBILITY_RULE = (
    "scientific_settings.xtb.solvent_compatibility_required"
)
_DISPERSION_CONFLICT_RULE = (
    "scientific_settings.dispersion.functional_conflict_guard"
)

_SOURCE_FILES = {
    "gaussian-job-settings-125f2878": (
        "checked_in_loader_renderer",
        "chemsmart/jobs/gaussian/settings.py",
    ),
    "gaussian-project-loader-125f2878": (
        "checked_in_loader_renderer",
        "chemsmart/settings/gaussian.py",
    ),
    "gaussian-reference-125f2878": (
        "checked_in_reference",
        "chemsmart/io/gaussian/__init__.py",
    ),
    "orca-job-settings-125f2878": (
        "checked_in_loader_renderer",
        "chemsmart/jobs/orca/settings.py",
    ),
    "orca-project-loader-125f2878": (
        "checked_in_loader_renderer",
        "chemsmart/settings/orca.py",
    ),
    "orca-reference-125f2878": (
        "checked_in_reference",
        "chemsmart/io/orca/__init__.py",
    ),
    "project-protocol-125f2878": (
        "checked_in_loader_renderer",
        "chemsmart/agent/project_protocol.py",
    ),
    "project-values-125f2878": (
        "checked_in_loader_renderer",
        "chemsmart/agent/project_yaml_values.py",
    ),
    "xtb-job-settings-125f2878": (
        "checked_in_loader_renderer",
        "chemsmart/jobs/xtb/settings.py",
    ),
    "xtb-project-loader-125f2878": (
        "checked_in_loader_renderer",
        "chemsmart/settings/xtb.py",
    ),
    "xtb-reference-125f2878": (
        "checked_in_reference",
        "chemsmart/io/xtb/__init__.py",
    ),
}


@dataclass(frozen=True)
class _Candidate:
    program: str
    setting_path: str
    canonical_value: str
    aliases: tuple[str, ...]
    applicable_job_kinds: tuple[str, ...]
    applicability_rule_ids: tuple[str, ...]
    validator_enforced: bool
    source_ids: tuple[str, ...]
    category: str


@dataclass(frozen=True)
class GeneratedPopulationArtifactsV2:
    inventory: ScientificSettingsInventoryV2
    descriptor: ScientificSettingsInventoryDescriptorV2
    registry: ScientificSettingsRegistryV2
    inventory_bytes: bytes
    receipt: Mapping[str, Any]
    receipt_bytes: bytes


def build_populated_scientific_settings_artifacts_v2(
    repository_root: str | Path | None = None,
) -> GeneratedPopulationArtifactsV2:
    """Build deterministic bytes without mutating the repository."""

    root = _repository_root(repository_root)
    catalog, catalog_bytes = _load_checked_bse_catalog(root)
    sources = _build_sources(root, catalog_bytes)
    candidates, exclusions, merge_receipts, raw_candidate_count = (
        _build_candidates(catalog)
    )

    entries: list[SettingInventoryEntryV2] = []
    probe_observations: list[dict[str, Any]] = []
    probe_failures: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="chemsmart-settings-v2-") as tmp:
        probe_path = Path(tmp) / "registry_probe.yaml"
        for candidate in sorted(
            candidates,
            key=lambda item: (
                item.program,
                item.setting_path,
                item.canonical_value.casefold(),
                item.canonical_value,
            ),
        ):
            observation = _probe_candidate(candidate, probe_path)
            if not observation["preserved"]:
                probe_failures.append(
                    _exclusion(
                        program=candidate.program,
                        setting_path=candidate.setting_path,
                        value=candidate.canonical_value,
                        category="loader_renderer_probe_failure",
                        rule_id=str(observation["rule_id"]),
                        source_ids=candidate.source_ids,
                        evidence=str(observation["detail"]),
                    )
                )
                continue
            entry = _entry_from_candidate(candidate, observation)
            entries.append(entry)
            probe_observations.append(
                _probe_observation_receipt(entry, candidate, observation)
            )

    exclusions.extend(probe_failures)
    entries_tuple = tuple(sorted(entries, key=lambda item: item.entry_id))
    inventory_body: dict[str, Any] = {
        "schema_version": SCIENTIFIC_SETTINGS_INVENTORY_V2_SCHEMA_VERSION,
        "inventory_id": INVENTORY_ID,
        "inventory_version": INVENTORY_VERSION,
        "normalization_version": (
            SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION
        ),
        "sources": tuple(item.model_dump(mode="json") for item in sources),
        "entries": tuple(item.model_dump(mode="json") for item in entries_tuple),
        "evidence_ceiling": FROZEN_EVIDENCE_CEILING_V1,
    }
    inventory_body["inventory_sha256"] = (
        scientific_settings_inventory_v2_sha256(inventory_body)
    )
    inventory = ScientificSettingsInventoryV2.model_validate(inventory_body)
    inventory_bytes = _canonical_json_bytes(inventory.model_dump(mode="json"))
    descriptor = _descriptor(inventory, inventory_bytes)
    registry = _registry(descriptor)

    receipt_body = _generation_receipt_body(
        root=root,
        catalog=catalog,
        sources=sources,
        candidates=candidates,
        raw_candidate_count=raw_candidate_count,
        merge_receipts=merge_receipts,
        probe_observations=tuple(probe_observations),
        inventory=inventory,
        descriptor=descriptor,
        registry=registry,
        inventory_bytes=inventory_bytes,
        exclusions=tuple(_ordered_exclusions(exclusions)),
    )
    receipt_body["receipt_sha256"] = _identity_sha256(
        receipt_body,
        "receipt_sha256",
    )
    receipt_bytes = _canonical_json_bytes(receipt_body)
    return GeneratedPopulationArtifactsV2(
        inventory=inventory,
        descriptor=descriptor,
        registry=registry,
        inventory_bytes=inventory_bytes,
        receipt=receipt_body,
        receipt_bytes=receipt_bytes,
    )


def write_populated_scientific_settings_artifacts_v2(
    repository_root: str | Path | None = None,
) -> tuple[Path, Path]:
    """Regenerate the two checked-in data artifacts explicitly."""

    root = _repository_root(repository_root)
    artifacts = build_populated_scientific_settings_artifacts_v2(root)
    inventory_path = root / INVENTORY_LOCATOR
    receipt_path = root / RECEIPT_LOCATOR
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_bytes(artifacts.inventory_bytes)
    receipt_path.write_bytes(artifacts.receipt_bytes)
    return inventory_path, receipt_path


def _build_sources(
    root: Path,
    catalog_bytes: bytes,
) -> tuple[SettingEvidenceSourceV2, ...]:
    sources = [
        SettingEvidenceSourceV2(
            source_id="bse-catalog-0.11",
            source_kind="basis_set_exchange_catalog",
            locator=(
                "chemsmart/agent/harness/basis_sets/"
                "bse_basis_catalog.json"
            ),
            artifact_sha256=hashlib.sha256(catalog_bytes).hexdigest(),
            source_revision="basis_set_exchange==0.11",
        )
    ]
    for source_id, (kind, locator) in sorted(_SOURCE_FILES.items()):
        sources.append(
            SettingEvidenceSourceV2(
                source_id=source_id,
                source_kind=kind,
                locator=locator,
                artifact_sha256=_file_sha256(root / locator),
                source_revision=SOURCE_CHECKPOINT,
            )
        )
    return tuple(sorted(sources, key=lambda item: item.source_id))


def _build_candidates(
    catalog: Mapping[str, Any],
) -> tuple[
    tuple[_Candidate, ...],
    list[dict[str, Any]],
    tuple[Mapping[str, Any], ...],
    int,
]:
    candidates: list[_Candidate] = []
    exclusions: list[dict[str, Any]] = []
    basis_sets = catalog["basis_sets"]
    orbital: dict[str, Mapping[str, Any]] = {}
    for entry in basis_sets.values():
        display_name = str(entry["display_name"])
        role = str(entry["role"])
        function_types = tuple(str(item) for item in entry["function_types"])
        if role != "orbital":
            for program in ("gaussian", "orca"):
                exclusions.append(
                    _exclusion(
                        program=program,
                        setting_path="method.basis",
                        value=display_name,
                        category="non_orbital_basis_role",
                        rule_id="scientific_settings.basis.non_orbital_role",
                        source_ids=("bse-catalog-0.11",),
                        evidence=f"BSE role={role}; not an orbital project basis.",
                    )
                )
            continue
        if "gto" not in function_types:
            for program in ("gaussian", "orca"):
                exclusions.append(
                    _exclusion(
                        program=program,
                        setting_path="method.basis",
                        value=display_name,
                        category="ecp_only_no_orbitals",
                        rule_id="scientific_settings.basis.ecp_only",
                        source_ids=("bse-catalog-0.11",),
                        evidence=(
                            "BSE function_types contains scalar_ecp but no gto; "
                            "it cannot fill method.basis."
                        ),
                    )
                )
            continue
        normalized = _normalize(display_name)
        if normalized in orbital:
            raise ValueError("populated normalization collides for BSE bases")
        orbital[normalized] = entry

    orca_native = {_normalize(value): str(value) for value in ORCA_ALL_BASIS_SETS}
    for program in ("gaussian", "orca"):
        basis_keys = set(orbital)
        if program == "orca":
            basis_keys.update(orca_native)
        for normalized in sorted(basis_keys):
            bse_entry = orbital.get(normalized)
            native_value = orca_native.get(normalized) if program == "orca" else None
            canonical = (
                str(bse_entry["display_name"])
                if bse_entry is not None
                else str(native_value)
            )
            source_ids = {
                "project-protocol-125f2878",
                f"{program}-job-settings-125f2878",
                f"{program}-project-loader-125f2878",
            }
            rules: list[str] = []
            if bse_entry is not None:
                source_ids.add("bse-catalog-0.11")
                rules.append(_ELEMENT_COVERAGE_RULE)
                function_types = set(bse_entry["function_types"])
                if "scalar_ecp" in function_types:
                    rules.append(_ECP_RULE)
                if program == "gaussian" or native_value is None:
                    rules.append(_MATERIALIZATION_RULE)
            else:
                source_ids.add("orca-reference-125f2878")
                rules.append(_REGISTRY_INTEGRATION_RULE)
            if native_value is not None:
                source_ids.add("orca-reference-125f2878")
            aliases = _aliases(canonical, *((native_value,) if native_value else ()))
            candidates.append(
                _Candidate(
                    program=program,
                    setting_path="method.basis",
                    canonical_value=canonical,
                    aliases=aliases,
                    applicable_job_kinds=("opt",),
                    applicability_rule_ids=tuple(sorted(set(rules))),
                    validator_enforced=False,
                    source_ids=tuple(sorted(source_ids)),
                    category="orbital_basis",
                )
            )

    for program, values in (
        ("gaussian", GAUSSIAN_FUNCTIONALS),
        ("orca", ORCA_ALL_FUNCTIONALS),
    ):
        for value in sorted(map(str, values), key=lambda item: (item.casefold(), item)):
            candidates.append(
                _simple_candidate(
                    program=program,
                    setting_path="method.functional",
                    value=value,
                    source_ids=(
                        f"{program}-job-settings-125f2878",
                        f"{program}-project-loader-125f2878",
                        f"{program}-reference-125f2878",
                        "project-protocol-125f2878",
                    ),
                    category="functional",
                )
            )

    for program in ("gaussian", "orca"):
        for canonical, aliases in (
            ("D3", ("gd3",)),
            ("D3BJ", ("D3(BJ)", "D3-BJ", "gd3bj")),
        ):
            candidates.append(
                _simple_candidate(
                    program=program,
                    setting_path="method.dispersion",
                    value=canonical,
                    aliases=aliases,
                    applicability_rule_ids=(_DISPERSION_CONFLICT_RULE,),
                    validator_enforced=False,
                    source_ids=(
                        f"{program}-job-settings-125f2878",
                        f"{program}-project-loader-125f2878",
                        "project-protocol-125f2878",
                    ),
                    category="dispersion",
                )
            )
    for unsupported in sorted(
        set(map(str.casefold, ORCA_ALL_DISPERSION_CORRECTIONS))
        - {"d3bj"}
    ):
        exclusions.append(
            _exclusion(
                program="orca",
                setting_path="method.dispersion",
                value=unsupported,
                category="typed_compiler_unsupported",
                rule_id="paper.project.dispersion_unsupported",
                source_ids=(
                    "orca-reference-125f2878",
                    "project-protocol-125f2878",
                ),
                evidence="Checked-in ORCA reference exists, but paper profile preserves only D3/D3BJ.",
            )
        )

    for program, models in (
        ("gaussian", GAUSSIAN_SOLVATION_MODELS),
        ("orca", ORCA_ALL_SOLVENT_MODELS),
    ):
        for value in sorted(set(map(str, models)), key=str.casefold):
            candidates.append(
                _solvent_candidate(
                    program=program,
                    setting_path="solvent.model",
                    value=value,
                    source_ids=(
                        f"{program}-job-settings-125f2878",
                        f"{program}-project-loader-125f2878",
                        f"{program}-reference-125f2878",
                        "project-protocol-125f2878",
                    ),
                )
            )

    gaussian_solvents = sorted(set(SOLVENT_ALIASES.values()), key=str.casefold)
    inverse_aliases: dict[str, list[str]] = defaultdict(list)
    for alias, canonical in SOLVENT_ALIASES.items():
        inverse_aliases[canonical].append(alias)
    for value in gaussian_solvents:
        candidates.append(
            _solvent_candidate(
                program="gaussian",
                setting_path="solvent.id",
                value=value,
                aliases=tuple(inverse_aliases[value]),
                source_ids=(
                    "gaussian-job-settings-125f2878",
                    "gaussian-project-loader-125f2878",
                    "project-protocol-125f2878",
                    "project-values-125f2878",
                ),
            )
        )
    for value in sorted(set(map(str, ORCA_ALL_SOLVENTS)), key=str.casefold):
        candidates.append(
            _solvent_candidate(
                program="orca",
                setting_path="solvent.id",
                value=value,
                source_ids=(
                    "orca-job-settings-125f2878",
                    "orca-project-loader-125f2878",
                    "orca-reference-125f2878",
                    "project-protocol-125f2878",
                ),
            )
        )

    candidates.append(
        _simple_candidate(
            program="gaussian",
            setting_path="method.integration_grid",
            value="UltraFine",
            aliases=("99590",),
            source_ids=(
                "gaussian-job-settings-125f2878",
                "gaussian-project-loader-125f2878",
                "project-protocol-125f2878",
            ),
            category="integration_grid",
        )
    )
    exclusions.append(
        _exclusion(
            program="orca",
            setting_path="method.integration_grid",
            value="*",
            category="typed_path_not_applicable",
            rule_id="paper.project.field_not_applicable",
            source_ids=("project-protocol-125f2878",),
            evidence="The paper-profile ORCA project compiler has no typed integration-grid path.",
        )
    )

    for value in sorted(set(map(str, XTB_ALL_METHODS)), key=str.casefold):
        number = value.removeprefix("gfn")
        aliases = (f"GFN{number}-xTB",) if number != "ff" else ("GFN-FF",)
        candidates.append(
            _simple_candidate(
                program="xtb",
                setting_path="method.gfn_version",
                value=value,
                aliases=aliases,
                applicable_job_kinds=("hess", "opt", "sp"),
                source_ids=(
                    "project-protocol-125f2878",
                    "xtb-job-settings-125f2878",
                    "xtb-project-loader-125f2878",
                    "xtb-reference-125f2878",
                ),
                category="gfn_method",
            )
        )
    for value in sorted(set(map(str, XTB_ALL_OPT_LEVELS)), key=str.casefold):
        candidates.append(
            _simple_candidate(
                program="xtb",
                setting_path="optimization.level",
                value=value,
                applicable_job_kinds=("opt",),
                source_ids=(
                    "project-protocol-125f2878",
                    "xtb-job-settings-125f2878",
                    "xtb-project-loader-125f2878",
                    "xtb-reference-125f2878",
                ),
                category="optimization_level",
            )
        )
    for setting_path, values in (
        ("solvent.model", XTB_ALL_SOLVENT_MODELS),
        ("solvent.id", XTB_ALL_SOLVENT_IDS),
    ):
        for value in sorted(set(map(str, values)), key=str.casefold):
            candidates.append(
                _solvent_candidate(
                    program="xtb",
                    setting_path=setting_path,
                    value=value,
                    applicable_job_kinds=("hess", "opt", "sp"),
                    source_ids=(
                        "project-protocol-125f2878",
                        "xtb-job-settings-125f2878",
                        "xtb-project-loader-125f2878",
                        "xtb-reference-125f2878",
                    ),
                )
            )
    exclusions.append(
        _exclusion(
            program="xtb",
            setting_path="method.basis",
            value="N/A",
            category="scientifically_not_applicable",
            rule_id="scientific_settings.v2.xtb_basis_not_applicable",
            source_ids=(
                "project-protocol-125f2878",
                "xtb-reference-125f2878",
            ),
            evidence="GFN-xTB methods do not use an orbital basis project field.",
        )
    )

    raw_candidate_count = len(candidates)
    deduplicated, merge_receipts = _deduplicate_candidates(candidates)
    return deduplicated, exclusions, merge_receipts, raw_candidate_count


def _simple_candidate(
    *,
    program: str,
    setting_path: str,
    value: str,
    source_ids: Sequence[str],
    category: str,
    aliases: Sequence[str] = (),
    applicable_job_kinds: tuple[str, ...] = ("opt",),
    applicability_rule_ids: tuple[str, ...] = (),
    validator_enforced: bool = False,
) -> _Candidate:
    return _Candidate(
        program=program,
        setting_path=setting_path,
        canonical_value=str(value),
        aliases=_aliases(str(value), *aliases),
        applicable_job_kinds=tuple(sorted(applicable_job_kinds)),
        applicability_rule_ids=tuple(sorted(applicability_rule_ids)),
        validator_enforced=validator_enforced,
        source_ids=tuple(sorted(set(source_ids))),
        category=category,
    )


def _solvent_candidate(**kwargs: Any) -> _Candidate:
    program = str(kwargs.get("program"))
    rules = [_SOLVENT_PAIR_RULE]
    validator_enforced = False
    if program == "xtb":
        rules = [_XTB_SOLVENT_COMPATIBILITY_RULE]
        kwargs.setdefault("applicable_job_kinds", ("hess", "opt", "sp"))
    else:
        kwargs.setdefault("applicable_job_kinds", ("sp",))
    return _simple_candidate(
        **kwargs,
        category="solvent_setting",
        applicability_rule_ids=tuple(sorted(rules)),
        validator_enforced=validator_enforced,
    )


def _deduplicate_candidates(
    candidates: Sequence[_Candidate],
) -> tuple[tuple[_Candidate, ...], tuple[Mapping[str, Any], ...]]:
    by_key: dict[tuple[str, str, str], _Candidate] = {}
    merge_receipts: list[Mapping[str, Any]] = []
    for candidate in candidates:
        key = (
            candidate.program,
            candidate.setting_path,
            _normalize(candidate.canonical_value),
        )
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = candidate
            continue
        semantic_fields = (
            "category",
            "applicable_job_kinds",
            "applicability_rule_ids",
            "validator_enforced",
        )
        incompatible = tuple(
            field
            for field in semantic_fields
            if getattr(existing, field) != getattr(candidate, field)
        )
        existing_aliases = {
            _normalize(value) for value in existing.aliases
        }
        candidate_aliases = {
            _normalize(value) for value in candidate.aliases
        }
        if existing_aliases != candidate_aliases:
            incompatible += ("aliases",)
        if incompatible:
            raise ValueError(
                "incompatible candidate collision after normalization: "
                f"{key!r}; fields={incompatible!r}"
            )
        merged_source_ids = tuple(
            sorted(set(existing.source_ids) | set(candidate.source_ids))
        )
        by_key[key] = replace(
            existing,
            source_ids=merged_source_ids,
        )
        merge_digest = hashlib.sha256(
            "\x1f".join(
                (
                    *key,
                    existing.canonical_value,
                    candidate.canonical_value,
                )
            ).encode("utf-8")
        ).hexdigest()[:20]
        merge_receipts.append(
            {
                "merge_id": f"candidate-merge.{merge_digest}",
                "program": candidate.program,
                "setting_path": candidate.setting_path,
                "normalized_key": key[2],
                "retained_canonical_value": existing.canonical_value,
                "merged_canonical_value": candidate.canonical_value,
                "category": candidate.category,
                "aliases_normalized": tuple(sorted(existing_aliases)),
                "applicable_job_kinds": candidate.applicable_job_kinds,
                "applicability_rule_ids": candidate.applicability_rule_ids,
                "validator_enforced": candidate.validator_enforced,
                "source_ids": merged_source_ids,
                "compatibility_basis": (
                    "normalized literal, aliases, category, job scope, rules, "
                    "and validator semantics are identical"
                ),
            }
        )
    return (
        tuple(by_key[key] for key in sorted(by_key)),
        tuple(sorted(merge_receipts, key=lambda item: str(item["merge_id"]))),
    )


def _probe_candidate(
    candidate: _Candidate,
    probe_path: Path,
) -> dict[str, Any]:
    protocol = {"method": _probe_method(candidate)}
    try:
        rendered = render_project_document(
            protocol,
            "registry_probe",
            candidate.program,
            profile="paper",
        )
    except Exception as exc:
        return {
            "preserved": False,
            "rule_id": "scientific_settings.population.renderer_exception",
            "detail": f"{type(exc).__name__}: {exc}",
        }
    yaml_text = rendered.get("yaml_text")
    if not isinstance(yaml_text, str):
        blockers = rendered.get("blocking_issues") or ()
        return {
            "preserved": False,
            "rule_id": "scientific_settings.population.renderer_rejected",
            "detail": json.dumps(blockers, sort_keys=True),
        }
    document = yaml.safe_load(yaml_text)
    if not isinstance(document, dict):
        return {
            "preserved": False,
            "rule_id": "scientific_settings.population.renderer_invalid_yaml",
            "detail": "paper renderer did not produce a mapping",
        }
    probe_path.write_text(yaml_text, encoding="utf-8")
    try:
        with _silence_loader_logging():
            settings = _load_project_settings(candidate.program, probe_path)
    except Exception as exc:
        return {
            "preserved": False,
            "rule_id": "scientific_settings.population.loader_rejected",
            "detail": f"{type(exc).__name__}: {exc}",
        }
    rendered_literals, loaded_literals, observed_job_kinds = (
        _semantic_observation(candidate, document, settings)
    )
    transform_id = _observation_transform_id(candidate)
    preserved = (
        rendered_literals == loaded_literals
        and bool(rendered_literals)
        and observed_job_kinds == candidate.applicable_job_kinds
    )
    return {
        "preserved": preserved,
        "rule_id": (
            "scientific_settings.population.preserved"
            if preserved
            else "scientific_settings.population.semantic_loss"
        ),
        "detail": (
            f"input={candidate.canonical_value!r}; "
            f"rendered={rendered_literals!r}; loaded={loaded_literals!r}; "
            f"jobs={observed_job_kinds!r}; transform={transform_id}"
        ),
        "input_literal": candidate.canonical_value,
        "rendered_literals": rendered_literals,
        "loaded_literals": loaded_literals,
        "observed_job_kinds": observed_job_kinds,
        "transform_id": transform_id,
    }


def _probe_method(candidate: _Candidate) -> dict[str, Any]:
    if candidate.program == "xtb":
        method: dict[str, Any] = {
            "gfn_version": "gfn2",
            "optimization_level": "normal",
        }
    else:
        method = {"functional": "pbe", "basis": "def2-SVP", "freq": False}
    field = candidate.setting_path
    if field == "method.basis":
        method["basis"] = candidate.canonical_value
    elif field == "method.functional":
        method["functional"] = candidate.canonical_value
    elif field == "method.dispersion":
        method["dispersion"] = candidate.canonical_value
    elif field == "method.integration_grid":
        method["integration_grid"] = candidate.canonical_value
    elif field == "method.gfn_version":
        method["gfn_version"] = candidate.canonical_value
    elif field == "optimization.level":
        method["optimization_level"] = candidate.canonical_value
    elif field == "solvent.model":
        method["solvent_model"] = candidate.canonical_value
        method["solvent_id"] = "water"
    elif field == "solvent.id":
        method["solvent_model"] = "smd" if candidate.program != "xtb" else "alpb"
        method["solvent_id"] = candidate.canonical_value
    else:
        raise ValueError(f"no population probe for {field}")
    return method


def _load_project_settings(program: str, path: Path) -> Any:
    if program == "gaussian":
        return YamlGaussianProjectSettings.from_yaml(str(path))
    if program == "orca":
        return YamlORCAProjectSettings.from_yaml(str(path))
    return YamlXTBProjectSettings.from_yaml(str(path))


def _semantic_observation(
    candidate: _Candidate,
    document: Mapping[str, Any],
    settings: Any,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    field = candidate.setting_path
    if candidate.program == "xtb":
        jobs = ("opt",) if field == "optimization.level" else ("hess", "opt", "sp")
        attribute = {
            "method.gfn_version": "gfn_version",
            "optimization.level": "optimization_level",
            "solvent.model": "solvent_model",
            "solvent.id": "solvent_id",
        }[field]
        yaml_key = {
            "method.gfn_version": "gfn_version",
            "optimization.level": "optimization_level",
            "solvent.model": "solvent_model",
            "solvent.id": "solvent_id",
        }[field]
        expected = tuple(str(document[job][yaml_key]) for job in jobs)
        observed = tuple(
            str(getattr(getattr(settings, f"{job}_settings")(), attribute))
            for job in jobs
        )
        return expected, observed, jobs

    phase = "solv" if field.startswith("solvent.") else "gas"
    job = "sp" if phase == "solv" else "opt"
    loaded = getattr(settings, f"{job}_settings")()
    if field == "method.basis":
        return (str(document[phase]["basis"]),), (str(loaded.basis),), (job,)
    if field == "method.functional":
        return (
            (str(document[phase]["functional"]),),
            (str(loaded.functional),),
            (job,),
        )
    if field == "method.dispersion" and candidate.program == "gaussian":
        return (
            (str(document[phase]["functional"]),),
            (str(loaded.functional),),
            (job,),
        )
    if field == "method.dispersion":
        return (
            (str(document[phase]["dispersion"]),),
            (str(loaded.dispersion),),
            (job,),
        )
    if field == "method.integration_grid":
        expected = str(document[phase]["additional_route_parameters"])
        return (
            (expected,),
            (str(loaded.additional_route_parameters),),
            (job,),
        )
    attribute = "solvent_model" if field == "solvent.model" else "solvent_id"
    yaml_key = attribute
    return (
        (str(document[phase][yaml_key]),),
        (str(getattr(loaded, attribute)),),
        (job,),
    )


def _observation_transform_id(candidate: _Candidate) -> str:
    if candidate.setting_path == "method.basis":
        return "paper_project.basis_literal_normalization"
    if candidate.setting_path == "method.functional":
        return "paper_project.functional_literal_normalization"
    if candidate.setting_path == "method.dispersion":
        if candidate.program == "gaussian":
            return "paper_project.gaussian_dispersion_route_compilation"
        return "paper_project.orca_dispersion_keyword_normalization"
    if candidate.setting_path == "method.integration_grid":
        return "paper_project.gaussian_grid_route_compilation"
    if candidate.program == "xtb":
        return "paper_project.xtb_literal_normalization"
    return "paper_project.solvent_literal_normalization"


def _entry_from_candidate(
    candidate: _Candidate,
    observation: Mapping[str, Any],
) -> SettingInventoryEntryV2:
    digest = hashlib.sha256(
        "\x1f".join(
            (candidate.program, candidate.setting_path, candidate.canonical_value)
        ).encode("utf-8")
    ).hexdigest()[:20]
    note = (
        f"Observed allowed transform {observation['transform_id']}: "
        f"input={observation['input_literal']!r} -> "
        f"rendered={observation['rendered_literals']!r} -> "
        f"loaded={observation['loaded_literals']!r}; "
        f"jobs={observation['observed_job_kinds']!r}. Rendered and loaded "
        "literals matched. No safe preview or engine execution."
    )
    return SettingInventoryEntryV2(
        entry_id=(
            f"setting.{candidate.program}."
            f"{candidate.setting_path.replace('.', '_')}.{digest}"
        ),
        program=candidate.program,
        setting_path=candidate.setting_path,
        canonical_value=candidate.canonical_value,
        aliases=candidate.aliases,
        applicable_job_kinds=candidate.applicable_job_kinds,
        applicability_rule_ids=candidate.applicability_rule_ids,
        validator_enforced=candidate.validator_enforced,
        source_ids=candidate.source_ids,
        loader_observation="accepted",
        renderer_observation="preserved",
        observation_note=note,
        engine_executed=False,
        combination_verified=False,
    )


def _probe_observation_receipt(
    entry: SettingInventoryEntryV2,
    candidate: _Candidate,
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "entry_id": entry.entry_id,
        "program": candidate.program,
        "setting_path": candidate.setting_path,
        "category": candidate.category,
        "input_literal": observation["input_literal"],
        "rendered_literals": observation["rendered_literals"],
        "loaded_literals": observation["loaded_literals"],
        "observed_job_kinds": observation["observed_job_kinds"],
        "allowed_transform_id": observation["transform_id"],
        "rendered_loaded_equal": True,
    }


def _descriptor(
    inventory: ScientificSettingsInventoryV2,
    inventory_bytes: bytes,
) -> ScientificSettingsInventoryDescriptorV2:
    counts = Counter(
        (entry.program, entry.setting_path) for entry in inventory.entries
    )
    scopes = tuple(
        ScientificSettingsInventoryScopeV2(
            program=program,
            setting_path=setting_path,
            entry_count=count,
        )
        for (program, setting_path), count in sorted(
            counts.items(), key=lambda item: (item[0][0].value, item[0][1])
        )
    )
    return ScientificSettingsInventoryDescriptorV2(
        schema_version=(
            SCIENTIFIC_SETTINGS_INVENTORY_DESCRIPTOR_V2_SCHEMA_VERSION
        ),
        inventory_schema_version=inventory.schema_version,
        normalization_version=inventory.normalization_version,
        inventory_id=inventory.inventory_id,
        inventory_version=inventory.inventory_version,
        inventory_sha256=inventory.inventory_sha256,
        artifact_locator=INVENTORY_LOCATOR,
        artifact_sha256=hashlib.sha256(inventory_bytes).hexdigest(),
        entry_count=len(inventory.entries),
        scopes=scopes,
    )


def _registry(
    descriptor: ScientificSettingsInventoryDescriptorV2,
) -> ScientificSettingsRegistryV2:
    body: dict[str, Any] = {
        "schema_version": SCIENTIFIC_SETTINGS_REGISTRY_V2_SCHEMA_VERSION,
        "registry_id": REGISTRY_ID,
        "registry_version": REGISTRY_VERSION,
        "chemsmart_version": CHEMSMART_VERSION,
        "source_revision": SOURCE_CHECKPOINT,
        "cli_schema_sha256": CLI_SCHEMA_SHA256,
        "predecessor": {
            "schema_version": SCIENTIFIC_SETTINGS_REGISTRY_REF_V2_SCHEMA_VERSION,
            "target_schema_version": "chemsmart.scientific-settings-registry.v1",
            "registry_id": "chemsmart.scientific-settings.source-snapshot-c793db6",
            "registry_version": "1.0.0",
            "registry_sha256": FROZEN_V1_REGISTRY_SHA256,
        },
        "inventories": (descriptor.model_dump(mode="json"),),
        "inventory_population_state": "populated",
        "evidence_ceiling": FROZEN_EVIDENCE_CEILING_V1,
        "experimental": True,
        "default_runtime_authority": False,
    }
    body["registry_sha256"] = scientific_settings_registry_v2_sha256(body)
    return ScientificSettingsRegistryV2.model_validate(body)


def _generation_receipt_body(
    *,
    root: Path,
    catalog: Mapping[str, Any],
    sources: Sequence[SettingEvidenceSourceV2],
    candidates: Sequence[_Candidate],
    raw_candidate_count: int,
    merge_receipts: Sequence[Mapping[str, Any]],
    probe_observations: Sequence[Mapping[str, Any]],
    inventory: ScientificSettingsInventoryV2,
    descriptor: ScientificSettingsInventoryDescriptorV2,
    registry: ScientificSettingsRegistryV2,
    inventory_bytes: bytes,
    exclusions: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    scope_counts = Counter(
        (entry.program.value, entry.setting_path) for entry in inventory.entries
    )
    gap_counts = Counter(
        rule
        for entry in inventory.entries
        if not entry.validator_enforced
        for rule in entry.applicability_rule_ids
    )
    role_counts = Counter(
        str(item["role"]) for item in catalog["basis_sets"].values()
    )
    legacy_groups = _legacy_normalization_collision_groups(catalog)
    bse_orbital_names = {
        _normalize(str(item["display_name"]))
        for item in catalog["basis_sets"].values()
        if item["role"] == "orbital" and "gto" in item["function_types"]
    }
    orca_native_names = {_normalize(str(value)) for value in ORCA_ALL_BASIS_SETS}
    exclusion_counts = Counter(str(item["category"]) for item in exclusions)
    transform_counts = Counter(
        str(item["allowed_transform_id"]) for item in probe_observations
    )
    source_files = tuple(
        {
            "source_id": source.source_id,
            "locator": source.locator,
            "artifact_sha256": source.artifact_sha256,
            "source_revision": source.source_revision,
        }
        for source in sources
    )
    return {
        "schema_version": (
            "chemsmart.scientific-settings-population-receipt.v2"
        ),
        "receipt_sha256": "0" * 64,
        "source_checkpoint": SOURCE_CHECKPOINT,
        "generator": {
            "locator": GENERATOR_LOCATOR,
            "artifact_sha256": _file_sha256(root / GENERATOR_LOCATOR),
        },
        "source_files": source_files,
        "bse_catalog": {
            "source_version": catalog["metadata"]["source_version"],
            "artifact_sha256": BSE_ARTIFACT_SHA256,
            "content_sha256": BSE_CONTENT_SHA256,
            "record_count": len(catalog["basis_sets"]),
            "role_counts": dict(sorted(role_counts.items())),
            "orbital_with_gto_count": sum(
                item["role"] == "orbital"
                and "gto" in item["function_types"]
                for item in catalog["basis_sets"].values()
            ),
            "ecp_only_count": sum(
                "gto" not in item["function_types"]
                for item in catalog["basis_sets"].values()
            ),
            "non_orbital_role_count": sum(
                item["role"] != "orbital"
                for item in catalog["basis_sets"].values()
            ),
        },
        "checked_in_reference_counts": {
            "gaussian_functionals": len(GAUSSIAN_FUNCTIONALS),
            "gaussian_solvent_ids": len(set(SOLVENT_ALIASES.values())),
            "gaussian_solvent_models": len(GAUSSIAN_SOLVATION_MODELS),
            "orca_basis_names": len(ORCA_ALL_BASIS_SETS),
            "orca_basis_bse_orbital_overlap": len(
                bse_orbital_names & orca_native_names
            ),
            "orca_basis_native_only": len(
                orca_native_names - bse_orbital_names
            ),
            "orca_basis_union": len(
                bse_orbital_names | orca_native_names
            ),
            "orca_functionals_raw": len(ORCA_ALL_FUNCTIONALS),
            "orca_functionals_normalized_unique": len(
                {_normalize(str(value)) for value in ORCA_ALL_FUNCTIONALS}
            ),
            "orca_solvent_ids": len(ORCA_ALL_SOLVENTS),
            "orca_solvent_models": len(ORCA_ALL_SOLVENT_MODELS),
            "xtb_gfn_methods": len(XTB_ALL_METHODS),
            "xtb_optimization_levels": len(XTB_ALL_OPT_LEVELS),
            "xtb_solvent_ids": len(XTB_ALL_SOLVENT_IDS),
            "xtb_solvent_models": len(XTB_ALL_SOLVENT_MODELS),
        },
        "coverage": {
            "claim": "enumerated_typed_project_paths_only",
            "comprehensive_engine_inventory": False,
            "enumerated_scopes": tuple(
                {
                    "program": program,
                    "setting_path": setting_path,
                    "observed_job_kinds": tuple(
                        sorted(
                            {
                                job
                                for entry in inventory.entries
                                if entry.program.value == program
                                and entry.setting_path == setting_path
                                for job in entry.applicable_job_kinds
                            }
                        )
                    ),
                    "entry_count": count,
                }
                for (program, setting_path), count in sorted(scope_counts.items())
            ),
            "out_of_scope_reference_collections": (
                _out_of_scope_reference_collections()
            ),
        },
        "normalization": {
            "selected_version": (
                SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION
            ),
            "legacy_collision_group_count": len(legacy_groups),
            "legacy_collision_entry_count": sum(map(len, legacy_groups)),
            "legacy_collision_examples": tuple(legacy_groups[:5]),
            "populated_orbital_basis_collision_count": 0,
        },
        "probe": {
            "raw_candidate_count": raw_candidate_count,
            "candidate_count_after_compatible_deduplication": len(candidates),
            "preserved_count": len(inventory.entries),
            "excluded_probe_failure_count": sum(
                item["category"] == "loader_renderer_probe_failure"
                for item in exclusions
            ),
            "profile": "paper",
            "actual_project_loader_used": True,
            "transform_counts": dict(sorted(transform_counts.items())),
            "observations": tuple(probe_observations),
        },
        "deduplication": {
            "policy": "fail_unless_scientific_semantics_are_identical",
            "raw_candidate_count": raw_candidate_count,
            "unique_candidate_count": len(candidates),
            "merge_count": len(merge_receipts),
            "merge_receipts": tuple(merge_receipts),
        },
        "inventory": {
            "locator": INVENTORY_LOCATOR,
            "artifact_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
            "inventory_sha256": inventory.inventory_sha256,
            "entry_count": len(inventory.entries),
            "scope_counts": tuple(
                {
                    "program": program,
                    "setting_path": setting_path,
                    "entry_count": count,
                }
                for (program, setting_path), count in sorted(scope_counts.items())
            ),
            "project_candidate_eligible_count": sum(
                not entry.applicability_rule_ids or entry.validator_enforced
                for entry in inventory.entries
            ),
            "blocked_validation_coverage_count": sum(
                bool(entry.applicability_rule_ids)
                and not entry.validator_enforced
                for entry in inventory.entries
            ),
            "applicability_gap_counts": dict(sorted(gap_counts.items())),
        },
        "descriptor": descriptor.model_dump(mode="json"),
        "registry": registry.model_dump(mode="json"),
        "exclusions": exclusions,
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "evidence_ceiling": inventory.evidence_ceiling.model_dump(mode="json"),
        "execution_boundary": {
            "network_calls": 0,
            "provider_calls": 0,
            "safe_previews": 0,
            "native_inputs_generated": 0,
            "chemistry_engine_calls": 0,
            "scientific_adequacy_verified": False,
        },
        "interpretation": {
            "basis_registry_scope": (
                "BSE establishes names, orbital role, format serialization, "
                "and declared elements; it does not prove ChemSmart project "
                "materialization or native engine acceptance."
            ),
            "eligibility_scope": (
                "project-literal candidate only; molecule-specific element, "
                "ECP, method-combination, preview, and engine gates remain."
            ),
            "request_bound_readiness": (
                "Every BSE-backed basis remains blocked because this snapshot "
                "does not execute or bind a request-specific element-coverage "
                "validator receipt. Dispersion-conflict and Gaussian/ORCA "
                "solvent-pair rules likewise remain unenforced and blocked."
            ),
            "xtb_basis": "not_applicable",
        },
    }


def _out_of_scope_reference_collections() -> tuple[Mapping[str, Any], ...]:
    collections = (
        (
            "gaussian",
            "GAUSSIAN_BASES",
            len(GAUSSIAN_BASES),
            "gaussian-reference-125f2878",
            "parser prefixes, not exact typed basis literals",
        ),
        (
            "gaussian",
            "GAUSSIAN_AB_INITIO",
            len(GAUSSIAN_AB_INITIO),
            "gaussian-reference-125f2878",
            "no enumerated paper-profile project setting path",
        ),
        (
            "gaussian",
            "GAUSSIAN_SEMIEMPIRICAL",
            len(GAUSSIAN_SEMIEMPIRICAL),
            "gaussian-reference-125f2878",
            "no enumerated paper-profile project setting path",
        ),
        (
            "gaussian",
            "GAUSSIAN_ADDITIONAL_OPT_OPTIONS",
            len(GAUSSIAN_ADDITIONAL_OPT_OPTIONS),
            "gaussian-reference-125f2878",
            "free-form route collection lacks a typed inventory path",
        ),
        (
            "gaussian",
            "GAUSSIAN_ADDITIONAL_ROUTE_PARAMETERS",
            len(GAUSSIAN_ADDITIONAL_ROUTE_PARAMETERS),
            "gaussian-reference-125f2878",
            "free-form route collection lacks a typed inventory path",
        ),
        (
            "orca",
            "ORCA_ALL_AUXILIARY_BASIS_SETS",
            len(ORCA_ALL_AUXILIARY_BASIS_SETS),
            "orca-reference-125f2878",
            "auxiliary bases are not method.basis orbital values",
        ),
        (
            "orca",
            "ORCA_ALL_EXTRAPOLATION_BASIS_SETS",
            len(ORCA_ALL_EXTRAPOLATION_BASIS_SETS),
            "orca-reference-125f2878",
            "extrapolation composites lack a typed inventory path",
        ),
        (
            "orca",
            "ORCA_ALL_AB_INITIO",
            len(ORCA_ALL_AB_INITIO),
            "orca-reference-125f2878",
            "no enumerated paper-profile project setting path",
        ),
        (
            "orca",
            "ORCA_ALL_JOB_TYPES",
            len(ORCA_ALL_JOB_TYPES),
            "orca-reference-125f2878",
            "job families are outside the settings-literal inventory",
        ),
        (
            "orca",
            "ORCA_ALL_SCF_ALGORITHMS",
            len(ORCA_ALL_SCF_ALGORITHMS),
            "orca-reference-125f2878",
            "no enumerated paper-profile project setting path",
        ),
        (
            "orca",
            "ORCA_SCF_CONVERGENCE",
            len(ORCA_SCF_CONVERGENCE),
            "orca-reference-125f2878",
            "no enumerated paper-profile project setting path",
        ),
        (
            "orca",
            "ORCA_ALL_DENSITY_OPTIONS",
            len(ORCA_ALL_DENSITY_OPTIONS),
            "orca-reference-125f2878",
            "no enumerated paper-profile project setting path",
        ),
        (
            "xtb",
            "XTB_ALL_OPT_ENGINES",
            len(XTB_ALL_OPT_ENGINES),
            "xtb-reference-125f2878",
            "optimization engine lacks a typed paper-profile setting path",
        ),
        (
            "xtb",
            "XTB_ALL_JOB_TYPES",
            len(XTB_ALL_JOB_TYPES),
            "xtb-reference-125f2878",
            "job families are outside the settings-literal inventory",
        ),
        (
            "xtb",
            "XTB_ALL_GROUPS",
            len(XTB_ALL_GROUPS),
            "xtb-reference-125f2878",
            "CLI groups are outside the settings-literal inventory",
        ),
    )
    return tuple(
        {
            "program": program,
            "collection": collection,
            "record_count": count,
            "source_id": source_id,
            "disposition": "out_of_scope_no_enumerated_typed_path",
            "reason_rule_id": (
                "scientific_settings.population.reference_collection_out_of_scope"
            ),
            "note": note,
        }
        for program, collection, count, source_id, note in collections
    )


def _load_checked_bse_catalog(root: Path) -> tuple[dict[str, Any], bytes]:
    path = root / (
        "chemsmart/agent/harness/basis_sets/bse_basis_catalog.json"
    )
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BSE_ARTIFACT_SHA256:
        raise ValueError("BSE catalog exact-byte digest changed")
    catalog = json.loads(raw.decode("utf-8"))
    if _canonical_content_sha256(catalog) != BSE_CONTENT_SHA256:
        raise ValueError("BSE catalog semantic digest changed")
    if str(catalog["metadata"]["source_version"]) != BSE_VERSION:
        raise ValueError("BSE catalog source version changed")
    return catalog, raw


def _legacy_normalization_collision_groups(
    catalog: Mapping[str, Any],
) -> list[tuple[str, ...]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for item in catalog["basis_sets"].values():
        if item["role"] == "orbital" and "gto" in item["function_types"]:
            legacy = re.sub(
                r"[^a-z0-9]+",
                "",
                str(item["display_name"]).casefold().replace("ζ", "zeta"),
            )
            groups[legacy].append(str(item["display_name"]))
    return sorted(
        (
            tuple(sorted(values, key=str.casefold))
            for values in groups.values()
            if len(values) > 1
        ),
        key=lambda values: tuple(item.casefold() for item in values),
    )


def _exclusion(
    *,
    program: str,
    setting_path: str,
    value: str,
    category: str,
    rule_id: str,
    source_ids: Sequence[str],
    evidence: str,
) -> dict[str, Any]:
    digest = hashlib.sha256(
        "\x1f".join((program, setting_path, value, rule_id)).encode("utf-8")
    ).hexdigest()[:20]
    return {
        "exclusion_id": f"exclusion.{digest}",
        "program": program,
        "setting_path": setting_path,
        "canonical_value": value,
        "category": category,
        "rule_id": rule_id,
        "source_ids": tuple(sorted(set(source_ids))),
        "evidence": evidence,
        "disposition": "excluded_from_inventory",
    }


def _ordered_exclusions(
    exclusions: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    return sorted(
        exclusions,
        key=lambda item: (
            str(item["program"]),
            str(item["setting_path"]),
            str(item["canonical_value"]).casefold(),
            str(item["rule_id"]),
        ),
    )


def _aliases(canonical: str, *values: str) -> tuple[str, ...]:
    canonical_normalized = _normalize(canonical)
    aliases: dict[str, str] = {}
    for value in values:
        selected = str(value).strip()
        if not selected:
            continue
        normalized = _normalize(selected)
        if normalized == canonical_normalized:
            continue
        aliases.setdefault(normalized, selected)
    return tuple(sorted(aliases.values(), key=lambda item: (item.casefold(), item)))


def _normalize(value: str) -> str:
    return normalize_setting_literal_for_version(
        value,
        SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION,
    )


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_content_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _identity_sha256(value: Mapping[str, Any], field: str) -> str:
    return _canonical_content_sha256(
        {key: item for key, item in value.items() if key != field}
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository_root(value: str | Path | None) -> Path:
    if value is not None:
        return Path(value).resolve()
    return Path(__file__).resolve().parents[4]


@contextmanager
def _silence_loader_logging() -> Iterator[None]:
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(previous)


if __name__ == "__main__":
    for generated_path in write_populated_scientific_settings_artifacts_v2():
        print(generated_path)


__all__ = [
    "BSE_ARTIFACT_SHA256",
    "BSE_CONTENT_SHA256",
    "BSE_VERSION",
    "GENERATOR_LOCATOR",
    "GeneratedPopulationArtifactsV2",
    "INVENTORY_LOCATOR",
    "RECEIPT_LOCATOR",
    "SOURCE_CHECKPOINT",
    "build_populated_scientific_settings_artifacts_v2",
    "write_populated_scientific_settings_artifacts_v2",
]
