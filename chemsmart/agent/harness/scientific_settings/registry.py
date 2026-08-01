"""Frozen registry loading, conservative resolution, and sidecar receipts."""

from __future__ import annotations

from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from chemsmart.agent.cli_schema import build_chemsmart_cli_schema
from chemsmart.agent.command_workflow import cli_schema_digest
from chemsmart.agent.harness.basis_sets import (
    load_basis_catalog,
    resolve_basis_name,
    search_basis_sets,
)
from chemsmart.agent.harness.scientific_settings.contracts import (
    LoaderObservation,
    RendererObservation,
    ScientificProgram,
    ScientificSettingsOverlayV1,
    ScientificSettingsRegistryV1,
    ScientificSettingsValidationReceiptV1,
    SettingCapabilityV1,
    SettingMatchKind,
    SettingResolutionStatus,
    SettingResolutionV1,
    content_sha256,
    normalize_setting_literal,
    scientific_setting_resolution_sha256,
    scientific_settings_overlay_sha256,
    scientific_settings_receipt_sha256,
    scientific_settings_registry_sha256,
)
from chemsmart.agent.harness.scientific_settings.manifest import (
    FROZEN_MANIFEST_V1,
)
from chemsmart.agent.harness.scientific_settings.overlays import (
    FROZEN_OVERLAYS_V1,
)
from chemsmart.io.orca import ORCA_ALL_BASIS_SETS


@lru_cache(maxsize=1)
def load_scientific_settings_registry() -> ScientificSettingsRegistryV1:
    """Load the immutable source-snapshot registry with checked digests."""

    overlays = tuple(
        _build_overlay(raw_overlay) for raw_overlay in FROZEN_OVERLAYS_V1
    )
    body = {
        **FROZEN_MANIFEST_V1,
        "overlays": tuple(
            item.model_dump(mode="json") for item in overlays
        ),
    }
    body["registry_sha256"] = scientific_settings_registry_sha256(body)
    return ScientificSettingsRegistryV1.model_validate(body)


# Preserve an explicit handle to the immutable V1 loader before a future
# release assigns any newer generation to the unversioned API.
load_scientific_settings_registry_v1 = load_scientific_settings_registry


def resolve_scientific_setting(
    *,
    program: ScientificProgram | str,
    setting_path: str,
    value: str,
    job_kind: str | None = None,
    registry: ScientificSettingsRegistryV1 | None = None,
    allow_fuzzy_candidates: bool = True,
) -> SettingResolutionV1:
    """Resolve one literal without promoting fuzzy discovery to readiness."""

    frozen_registry = _validated_registry(
        registry or load_scientific_settings_registry()
    )
    selected_program = (
        program
        if isinstance(program, ScientificProgram)
        else ScientificProgram(str(program).strip().casefold())
    )
    selected_path = str(setting_path or "").strip().casefold()
    requested_value = str(value or "").strip()
    normalized_value = normalize_setting_literal(requested_value)
    selected_job = (
        str(job_kind).strip().casefold() if job_kind is not None else None
    )
    if not selected_path:
        raise ValueError("setting_path must not be empty")
    if not normalized_value:
        raise ValueError("setting value must contain a resolvable literal")

    scoped = tuple(
        item
        for item in _capabilities(frozen_registry)
        if item.program is selected_program
        and item.setting_path == selected_path
    )
    exact = _exact_capability(scoped, normalized_value)
    if exact is None:
        exact = _derived_exact_capability(
            registry=frozen_registry,
            program=selected_program,
            setting_path=selected_path,
            requested_value=requested_value,
        )
    if exact is not None:
        if not _job_is_compatible(exact, selected_job):
            return _build_resolution(
                registry=frozen_registry,
                program=selected_program,
                setting_path=selected_path,
                requested_value=requested_value,
                job_kind=selected_job,
                status=SettingResolutionStatus.INCOMPATIBLE,
                matched_by=SettingMatchKind.JOB_SCOPE_MISMATCH,
                capability=exact,
                candidates=(),
                reason_rule_id="scientific_settings.job_scope_incompatible",
            )
        match_kind = (
            SettingMatchKind.CANONICAL_LITERAL
            if requested_value.casefold() == exact.canonical_value.casefold()
            else SettingMatchKind.REGISTERED_ALIAS
        )
        return _build_resolution(
            registry=frozen_registry,
            program=selected_program,
            setting_path=selected_path,
            requested_value=requested_value,
            job_kind=selected_job,
            status=SettingResolutionStatus.EXACT_REGISTERED,
            matched_by=match_kind,
            capability=exact,
            candidates=(),
            reason_rule_id="scientific_settings.exact_registered",
        )

    elsewhere = _exact_capability(
        tuple(
            item
            for item in _capabilities(frozen_registry)
            if not (
                item.program is selected_program
                and item.setting_path == selected_path
            )
        ),
        normalized_value,
    )
    if elsewhere is not None:
        return _build_resolution(
            registry=frozen_registry,
            program=selected_program,
            setting_path=selected_path,
            requested_value=requested_value,
            job_kind=selected_job,
            status=SettingResolutionStatus.INCOMPATIBLE,
            matched_by=SettingMatchKind.REGISTERED_ELSEWHERE,
            capability=elsewhere,
            candidates=(),
            reason_rule_id="scientific_settings.program_or_path_incompatible",
        )

    candidates = (
        _candidate_values(
            requested_value,
            normalized_value,
            program=selected_program,
            setting_path=selected_path,
            scoped_capabilities=scoped,
        )
        if allow_fuzzy_candidates
        else ()
    )
    if candidates:
        return _build_resolution(
            registry=frozen_registry,
            program=selected_program,
            setting_path=selected_path,
            requested_value=requested_value,
            job_kind=selected_job,
            status=SettingResolutionStatus.CANDIDATE_ONLY,
            matched_by=SettingMatchKind.FUZZY_CANDIDATE,
            capability=None,
            candidates=candidates,
            reason_rule_id="scientific_settings.candidate_requires_selection",
        )

    return _build_resolution(
        registry=frozen_registry,
        program=selected_program,
        setting_path=selected_path,
        requested_value=requested_value,
        job_kind=selected_job,
        status=SettingResolutionStatus.UNKNOWN_UNVERIFIED,
        matched_by=SettingMatchKind.NONE,
        capability=None,
        candidates=(),
        reason_rule_id="scientific_settings.unknown_unverified",
    )


def list_scientific_settings(
    *,
    program: ScientificProgram | str,
    setting_path: str,
    query: str = "",
    limit: int = 20,
    registry: ScientificSettingsRegistryV1 | None = None,
) -> dict[str, object]:
    """Return a bounded view over the full frozen setting inventory.

    The complete inventory remains in content-addressed BSE and native-source
    snapshots.  This view never sends hundreds of literals to a model.
    """

    frozen_registry = _validated_registry(
        registry or load_scientific_settings_registry()
    )
    selected_program = (
        program
        if isinstance(program, ScientificProgram)
        else ScientificProgram(str(program).strip().casefold())
    )
    selected_path = str(setting_path or "").strip().casefold()
    bounded_limit = max(1, min(int(limit or 20), 50))
    if selected_program is ScientificProgram.XTB and selected_path == "method.basis":
        return {
            "ok": False,
            "program": selected_program.value,
            "setting_path": selected_path,
            "status": "not_applicable",
            "inventory_count": 0,
            "returned_count": 0,
            "values": [],
            "registry_sha256": frozen_registry.registry_sha256,
            "rule_ids": ["scientific_settings.xtb_basis_not_applicable"],
        }

    values = _inventory_values(
        frozen_registry,
        selected_program,
        selected_path,
    )
    normalized_query = normalize_setting_literal(query)
    matches = (
        tuple(
            value
            for value in values
            if normalized_query in normalize_setting_literal(value)
        )
        if normalized_query
        else values
    )
    returned = matches[:bounded_limit]
    return {
        "ok": bool(values),
        "program": selected_program.value,
        "setting_path": selected_path,
        "status": "inventory_available" if values else "coverage_gap",
        "inventory_count": len(values),
        "matched_count": len(matches),
        "returned_count": len(returned),
        "truncated": len(matches) > len(returned),
        "values": list(returned),
        "registry_sha256": frozen_registry.registry_sha256,
        "token_policy": "bounded_view_only",
        "rule_ids": [],
    }


def validate_scientific_settings_source_snapshot(
    registry: ScientificSettingsRegistryV1 | None = None,
) -> tuple[str, ...]:
    """Recompute local file and live-schema bindings for the frozen registry."""

    frozen_registry = _validated_registry(
        registry or load_scientific_settings_registry()
    )
    findings: list[str] = []
    repository_root = Path(__file__).resolve().parents[4]
    for source in frozen_registry.sources:
        if source.source_kind == "generated_cli_schema":
            observed = cli_schema_digest(build_chemsmart_cli_schema())
            if observed != source.artifact_sha256:
                findings.append("scientific_settings.source.cli_schema_drift")
            continue
        locator = repository_root / source.locator
        if not locator.is_file():
            findings.append("scientific_settings.source.file_missing")
            continue
        if content_sha256(locator.read_bytes()) != source.artifact_sha256:
            findings.append("scientific_settings.source.file_hash_mismatch")
    catalog = load_basis_catalog()
    if catalog.get("metadata", {}).get("renderability_verification") != (
        "all_declared_elements"
    ):
        findings.append("scientific_settings.source.bse_element_scope_missing")
    return tuple(sorted(set(findings)))


def build_scientific_settings_validation_receipt(
    *,
    project_yaml: str | bytes,
    resolutions: Sequence[SettingResolutionV1],
    project_config_sha256: str | None = None,
    registry: ScientificSettingsRegistryV1 | None = None,
) -> ScientificSettingsValidationReceiptV1:
    """Build a non-execution sidecar over exact project-YAML bytes."""

    frozen_registry = _validated_registry(
        registry or load_scientific_settings_registry()
    )
    validated_resolutions = tuple(
        SettingResolutionV1.model_validate(item.model_dump(mode="json"))
        for item in resolutions
    )
    if not validated_resolutions:
        raise ValueError("at least one setting resolution is required")
    ordered = tuple(sorted(validated_resolutions, key=_resolution_sort_key))
    if any(
        item.registry_sha256 != frozen_registry.registry_sha256
        for item in ordered
    ):
        raise ValueError("resolution was produced by a different registry")

    all_exact = all(
        item.status is SettingResolutionStatus.EXACT_REGISTERED
        for item in ordered
    )
    all_preserved = all(item.loader_renderer_eligible for item in ordered)
    if not all_exact:
        status = "blocked_resolution"
        blocking_rule_ids = tuple(
            sorted(
                {
                    item.reason_rule_id
                    for item in ordered
                    if item.status
                    is not SettingResolutionStatus.EXACT_REGISTERED
                }
            )
        )
    elif not all_preserved:
        status = "blocked_capability_observation"
        blocking_rule_ids = (
            "scientific_settings.loader_renderer_not_ready",
        )
    else:
        status = "registered_only"
        blocking_rule_ids = ()

    body = {
        "schema_version": (
            "chemsmart.scientific-settings-validation-receipt.v1"
        ),
        "project_yaml_sha256": content_sha256(project_yaml),
        "project_config_sha256": project_config_sha256,
        "registry_sha256": frozen_registry.registry_sha256,
        "resolutions": tuple(
            item.model_dump(mode="json") for item in ordered
        ),
        "all_settings_exact_registered": all_exact,
        "all_loader_renderer_observations_preserved": all_preserved,
        "status": status,
        "blocking_rule_ids": blocking_rule_ids,
        "evidence_ceiling": frozen_registry.evidence_ceiling.model_dump(
            mode="json"
        ),
        "safe_preview_executed": False,
        "engine_executed": False,
    }
    body["receipt_sha256"] = scientific_settings_receipt_sha256(body)
    return ScientificSettingsValidationReceiptV1.model_validate(body)


def _build_overlay(
    raw_overlay: Mapping[str, object],
) -> ScientificSettingsOverlayV1:
    body = dict(raw_overlay)
    body["overlay_sha256"] = scientific_settings_overlay_sha256(body)
    return ScientificSettingsOverlayV1.model_validate(body)


def _validated_registry(
    registry: ScientificSettingsRegistryV1,
) -> ScientificSettingsRegistryV1:
    return ScientificSettingsRegistryV1.model_validate(
        registry.model_dump(mode="json")
    )


def _capabilities(
    registry: ScientificSettingsRegistryV1,
) -> tuple[SettingCapabilityV1, ...]:
    return tuple(
        capability
        for overlay in registry.overlays
        for capability in overlay.capabilities
    )


def _exact_capability(
    capabilities: Iterable[SettingCapabilityV1],
    normalized_value: str,
) -> SettingCapabilityV1 | None:
    for capability in capabilities:
        literals = (capability.canonical_value, *capability.aliases)
        if normalized_value in {
            normalize_setting_literal(item) for item in literals
        }:
            return capability
    return None


def _derived_exact_capability(
    *,
    registry: ScientificSettingsRegistryV1,
    program: ScientificProgram,
    setting_path: str,
    requested_value: str,
) -> SettingCapabilityV1 | None:
    if setting_path != "method.basis" or program is ScientificProgram.XTB:
        return None

    bse_result = resolve_basis_name(
        requested_value,
        program=program.value,
    )
    if bse_result.verdict == "ok" and bse_result.canonical_name is not None:
        aliases = _aliases_for_derived_capability(
            bse_result.canonical_name,
            requested_value,
        )
        settings_source = (
            "gaussian-settings-3bd8915"
            if program is ScientificProgram.GAUSSIAN
            else "orca-settings-3bd8915"
        )
        return SettingCapabilityV1(
            capability_id=(
                f"{program.value}.basis.bse."
                f"{normalize_setting_literal(bse_result.canonical_name)}"
            ),
            program=program,
            setting_path=setting_path,
            canonical_value=bse_result.canonical_name,
            aliases=aliases,
            applicable_job_kinds=("*",),
            source_ids=tuple(
                sorted(
                    (
                        "bse-catalog-0.11",
                        "project-protocol-c793db6",
                        settings_source,
                    )
                )
            ),
            loader_observation=LoaderObservation.ACCEPTED,
            renderer_observation=RendererObservation.PRESERVED,
            observation_note=(
                "BSE 0.11 serialized every declared element for the target "
                "program, and the frozen ChemSmart loader/renderer path "
                "preserves the selected literal; no safe preview or engine "
                "execution was performed."
            ),
            engine_executed=False,
            combination_verified=False,
        )

    if program is ScientificProgram.ORCA:
        normalized = requested_value.strip().casefold()
        native_values = {
            str(value).casefold(): str(value) for value in ORCA_ALL_BASIS_SETS
        }
        native = native_values.get(normalized)
        if native is not None:
            return SettingCapabilityV1(
                capability_id=(
                    "orca.basis.native."
                    f"{normalize_setting_literal(native)}"
                ),
                program=program,
                setting_path=setting_path,
                canonical_value=native,
                aliases=_aliases_for_derived_capability(native, requested_value),
                applicable_job_kinds=("*",),
                source_ids=(
                    "orca-references-3bd8915",
                    "orca-settings-3bd8915",
                    "project-protocol-c793db6",
                ),
                loader_observation=LoaderObservation.ACCEPTED,
                renderer_observation=RendererObservation.PRESERVED,
                observation_note=(
                    "The frozen ORCA native-reference list and generic "
                    "ChemSmart loader/renderer path preserve this literal; "
                    "BSE membership, safe preview, and engine execution are "
                    "not claimed."
                ),
                engine_executed=False,
                combination_verified=False,
            )
    return None


def _aliases_for_derived_capability(
    canonical_value: str,
    requested_value: str,
) -> tuple[str, ...]:
    requested = requested_value.strip()
    aliases = (
        {requested}
        if requested and requested.casefold() != canonical_value.casefold()
        else set()
    )
    return tuple(sorted(aliases, key=str.casefold))


def _inventory_values(
    registry: ScientificSettingsRegistryV1,
    program: ScientificProgram,
    setting_path: str,
) -> tuple[str, ...]:
    values_by_key = {
        capability.canonical_value.casefold(): capability.canonical_value
        for capability in _capabilities(registry)
        if capability.program is program
        and capability.setting_path == setting_path
    }
    if setting_path == "method.basis" and program in {
        ScientificProgram.GAUSSIAN,
        ScientificProgram.ORCA,
    }:
        catalog = load_basis_catalog()
        for value in catalog["programs"][program.value]["basis_names"]:
            literal = str(value)
            values_by_key.setdefault(literal.casefold(), literal)
        if program is ScientificProgram.ORCA:
            for value in ORCA_ALL_BASIS_SETS:
                literal = str(value)
                values_by_key.setdefault(
                    literal.casefold(),
                    literal,
                )
    return tuple(sorted(values_by_key.values(), key=str.casefold))


def _job_is_compatible(
    capability: SettingCapabilityV1, job_kind: str | None
) -> bool:
    return bool(
        job_kind is None
        or "*" in capability.applicable_job_kinds
        or job_kind in capability.applicable_job_kinds
    )


def _candidate_values(
    requested_value: str,
    normalized_value: str,
    *,
    program: ScientificProgram,
    setting_path: str,
    scoped_capabilities: tuple[SettingCapabilityV1, ...],
) -> tuple[str, ...]:
    candidates: set[str] = set()
    normalized_to_canonical: dict[str, str] = {}
    for capability in scoped_capabilities:
        for literal in (capability.canonical_value, *capability.aliases):
            normalized_to_canonical[
                normalize_setting_literal(literal)
            ] = capability.canonical_value
    for match in get_close_matches(
        normalized_value,
        tuple(normalized_to_canonical),
        n=5,
        cutoff=0.6,
    ):
        candidates.add(normalized_to_canonical[match])

    if (
        setting_path == "method.basis"
        and program in {ScientificProgram.GAUSSIAN, ScientificProgram.ORCA}
    ):
        result = search_basis_sets(
            requested_value,
            program=program.value,
            limit=5,
        )
        for item in result.get("candidates", ()):
            name = item.get("name") if isinstance(item, Mapping) else None
            if isinstance(name, str) and name:
                candidates.add(name)
    return tuple(sorted(candidates, key=str.casefold))


def _build_resolution(
    *,
    registry: ScientificSettingsRegistryV1,
    program: ScientificProgram,
    setting_path: str,
    requested_value: str,
    job_kind: str | None,
    status: SettingResolutionStatus,
    matched_by: SettingMatchKind,
    capability: SettingCapabilityV1 | None,
    candidates: tuple[str, ...],
    reason_rule_id: str,
) -> SettingResolutionV1:
    exact = status is SettingResolutionStatus.EXACT_REGISTERED
    loader = (
        capability.loader_observation
        if capability is not None
        else LoaderObservation.NOT_OBSERVED
    )
    renderer = (
        capability.renderer_observation
        if capability is not None
        else RendererObservation.NOT_OBSERVED
    )
    eligible = bool(
        exact
        and loader is LoaderObservation.ACCEPTED
        and renderer is RendererObservation.PRESERVED
    )
    body = {
        "schema_version": "chemsmart.scientific-setting-resolution.v1",
        "registry_sha256": registry.registry_sha256,
        "program": program,
        "setting_path": setting_path,
        "requested_value": requested_value,
        "normalized_requested_value": normalize_setting_literal(
            requested_value
        ),
        "job_kind": job_kind,
        "status": status,
        "matched_by": matched_by,
        "canonical_value": (
            capability.canonical_value if capability is not None else None
        ),
        "capability_id": (
            capability.capability_id if capability is not None else None
        ),
        "candidate_values": tuple(sorted(candidates, key=str.casefold)),
        "loader_observation": loader,
        "renderer_observation": renderer,
        "loader_renderer_eligible": eligible,
        "reason_rule_id": reason_rule_id,
        "evidence_ceiling": registry.evidence_ceiling.model_dump(mode="json"),
    }
    body["resolution_sha256"] = scientific_setting_resolution_sha256(body)
    return SettingResolutionV1.model_validate(body)


def _resolution_sort_key(
    resolution: SettingResolutionV1,
) -> tuple[str, str, str, str]:
    return (
        resolution.program.value,
        resolution.setting_path,
        resolution.job_kind or "",
        resolution.normalized_requested_value,
    )


__all__ = [
    "build_scientific_settings_validation_receipt",
    "list_scientific_settings",
    "load_scientific_settings_registry",
    "load_scientific_settings_registry_v1",
    "resolve_scientific_setting",
    "validate_scientific_settings_source_snapshot",
]
