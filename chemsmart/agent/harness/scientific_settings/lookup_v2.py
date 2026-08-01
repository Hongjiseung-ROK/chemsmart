"""Explicit, bounded lookup over descriptor-bound V2 inventories."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from chemsmart.agent.harness.scientific_settings.contracts import (
    LoaderObservation,
    RendererObservation,
    ScientificProgram,
    normalize_setting_literal,
)
from chemsmart.agent.harness.scientific_settings.contracts_v2 import (
    ScientificSettingsInventoryScopeV2,
    ScientificSettingsInventoryV2,
    ScientificSettingsRegistryV2,
    SettingInventoryEntryV2,
)
from chemsmart.agent.harness.scientific_settings.lookup_contracts_v2 import (
    ScientificSettingsListItemV2,
    ScientificSettingsListStatusV2,
    ScientificSettingsListV2,
    SettingCandidateV2,
    SettingMatchKindV2,
    SettingResolutionStatusV2,
    SettingResolutionV2,
    scientific_setting_resolution_v2_sha256,
    scientific_settings_list_v2_sha256,
)


_SETTING_PATH = re.compile(r"^[a-z][a-z0-9_.-]{0,191}$")
_JOB_KIND = re.compile(r"^[a-z][a-z0-9_-]{0,79}$")
_SAFE_TEXT = re.compile(r"^[^\x00-\x1f\x7f]+$")
_FUZZY_MINIMUM_BASIS_POINTS = 5500


@dataclass(frozen=True)
class _LookupContext:
    registry: ScientificSettingsRegistryV2
    inventories: tuple[ScientificSettingsInventoryV2, ...]
    entries: tuple[SettingInventoryEntryV2, ...]
    inventory_sha256s: tuple[str, ...]


def resolve_scientific_setting_v2(
    *,
    registry: ScientificSettingsRegistryV2,
    loaded_inventories: Sequence[ScientificSettingsInventoryV2],
    program: ScientificProgram | str,
    setting_path: str,
    value: str,
    job_kind: str,
    allow_fuzzy_candidates: bool = True,
    candidate_limit: int = 5,
) -> SettingResolutionV2:
    """Resolve a literal without substituting fuzzy candidates.

    Callers must explicitly provide a populated V2 registry and all inventory
    models returned by the exact-byte loader.  Every semantic inventory digest
    and descriptor summary is checked again before lookup.
    """

    context = _validated_lookup_context(registry, loaded_inventories)
    selected_program = _program(program)
    selected_path = _setting_path(setting_path)
    requested_value = _literal(value)
    normalized_value = normalize_setting_literal(requested_value)
    selected_job = _job_kind(job_kind)
    bounded_candidate_limit = max(1, min(int(candidate_limit or 5), 10))

    if (
        selected_program is ScientificProgram.XTB
        and selected_path == "method.basis"
    ):
        return _build_resolution(
            context=context,
            program=selected_program,
            setting_path=selected_path,
            requested_value=requested_value,
            normalized_value=normalized_value,
            job_kind=selected_job,
            status=SettingResolutionStatusV2.NOT_APPLICABLE,
            matched_by=SettingMatchKindV2.NOT_APPLICABLE,
            entry=None,
            candidates=(),
            job_scope_compatible=None,
            reason_rule_id=(
                "scientific_settings.v2.xtb_basis_not_applicable"
            ),
        )

    scoped_entries = tuple(
        entry
        for entry in context.entries
        if entry.program is selected_program
        and entry.setting_path == selected_path
    )
    exact = _exact_entry(scoped_entries, normalized_value)
    if exact is not None:
        matched_by = (
            SettingMatchKindV2.CANONICAL_LITERAL
            if requested_value.casefold() == exact.canonical_value.casefold()
            else SettingMatchKindV2.REGISTERED_ALIAS
        )
        job_compatible = _job_is_compatible(exact, selected_job)
        if not job_compatible:
            return _build_resolution(
                context=context,
                program=selected_program,
                setting_path=selected_path,
                requested_value=requested_value,
                normalized_value=normalized_value,
                job_kind=selected_job,
                status=SettingResolutionStatusV2.INCOMPATIBLE,
                matched_by=SettingMatchKindV2.JOB_SCOPE_MISMATCH,
                entry=exact,
                candidates=(),
                job_scope_compatible=False,
                reason_rule_id=(
                    "scientific_settings.v2.job_scope_incompatible"
                ),
            )
        if exact.applicability_rule_ids and not exact.validator_enforced:
            return _build_resolution(
                context=context,
                program=selected_program,
                setting_path=selected_path,
                requested_value=requested_value,
                normalized_value=normalized_value,
                job_kind=selected_job,
                status=(
                    SettingResolutionStatusV2.BLOCKED_VALIDATION_COVERAGE
                ),
                matched_by=matched_by,
                entry=exact,
                candidates=(),
                job_scope_compatible=True,
                reason_rule_id=(
                    "scientific_settings.v2.validation_coverage_gap"
                ),
            )
        return _build_resolution(
            context=context,
            program=selected_program,
            setting_path=selected_path,
            requested_value=requested_value,
            normalized_value=normalized_value,
            job_kind=selected_job,
            status=SettingResolutionStatusV2.EXACT_REGISTERED,
            matched_by=matched_by,
            entry=exact,
            candidates=(),
            job_scope_compatible=True,
            reason_rule_id="scientific_settings.v2.exact_registered",
        )

    elsewhere = _exact_entry(
        tuple(
            entry
            for entry in context.entries
            if not (
                entry.program is selected_program
                and entry.setting_path == selected_path
            )
        ),
        normalized_value,
    )
    if elsewhere is not None:
        return _build_resolution(
            context=context,
            program=selected_program,
            setting_path=selected_path,
            requested_value=requested_value,
            normalized_value=normalized_value,
            job_kind=selected_job,
            status=SettingResolutionStatusV2.INCOMPATIBLE,
            matched_by=SettingMatchKindV2.REGISTERED_ELSEWHERE,
            entry=elsewhere,
            candidates=(),
            job_scope_compatible=None,
            reason_rule_id=(
                "scientific_settings.v2.program_or_path_incompatible"
            ),
        )

    candidates = (
        _fuzzy_candidates(
            scoped_entries,
            normalized_value=normalized_value,
            job_kind=selected_job,
            limit=bounded_candidate_limit,
        )
        if allow_fuzzy_candidates
        else ()
    )
    if candidates:
        return _build_resolution(
            context=context,
            program=selected_program,
            setting_path=selected_path,
            requested_value=requested_value,
            normalized_value=normalized_value,
            job_kind=selected_job,
            status=SettingResolutionStatusV2.CANDIDATE_ONLY,
            matched_by=SettingMatchKindV2.FUZZY_CANDIDATE,
            entry=None,
            candidates=candidates,
            job_scope_compatible=None,
            reason_rule_id=(
                "scientific_settings.v2.candidate_requires_selection"
            ),
        )

    return _build_resolution(
        context=context,
        program=selected_program,
        setting_path=selected_path,
        requested_value=requested_value,
        normalized_value=normalized_value,
        job_kind=selected_job,
        status=SettingResolutionStatusV2.UNKNOWN_UNVERIFIED,
        matched_by=SettingMatchKindV2.NONE,
        entry=None,
        candidates=(),
        job_scope_compatible=None,
        reason_rule_id="scientific_settings.v2.unknown_unverified",
    )


def list_scientific_settings_v2(
    *,
    registry: ScientificSettingsRegistryV2,
    loaded_inventories: Sequence[ScientificSettingsInventoryV2],
    program: ScientificProgram | str,
    setting_path: str,
    job_kind: str,
    query: str = "",
    limit: int = 20,
) -> ScientificSettingsListV2:
    """Return a bounded deterministic view over explicit V2 inventories."""

    context = _validated_lookup_context(registry, loaded_inventories)
    selected_program = _program(program)
    selected_path = _setting_path(setting_path)
    selected_job = _job_kind(job_kind)
    selected_query = _query(query)
    normalized_query = normalize_setting_literal(selected_query)
    bounded_limit = max(1, min(int(limit or 20), 50))

    if (
        selected_program is ScientificProgram.XTB
        and selected_path == "method.basis"
    ):
        return _build_listing(
            context=context,
            program=selected_program,
            setting_path=selected_path,
            query=selected_query,
            normalized_query=normalized_query,
            job_kind=selected_job,
            limit=bounded_limit,
            status=ScientificSettingsListStatusV2.NOT_APPLICABLE,
            inventory_count=0,
            matched_count=0,
            items=(),
            reason_rule_ids=(
                "scientific_settings.v2.xtb_basis_not_applicable",
            ),
        )

    scoped_entries = tuple(
        entry
        for entry in context.entries
        if entry.program is selected_program
        and entry.setting_path == selected_path
    )
    if normalized_query:
        ranked = tuple(
            item
            for item in (
                _ranked_entry(entry, normalized_query) for entry in scoped_entries
            )
            if item[0] >= _FUZZY_MINIMUM_BASIS_POINTS
        )
        ordered = tuple(
            sorted(
                ranked,
                key=lambda item: (
                    -item[0],
                    item[1].canonical_value.casefold(),
                    item[1].entry_id,
                ),
            )
        )
    else:
        ordered = tuple(
            (0, entry, None)
            for entry in sorted(
                scoped_entries,
                key=lambda item: (
                    item.canonical_value.casefold(),
                    item.entry_id,
                ),
            )
        )
    returned = ordered[:bounded_limit]
    items = tuple(
        _list_item(
            rank=index,
            entry=entry,
            job_kind=selected_job,
            score=(score if normalized_query else None),
            matched_literal=(literal if normalized_query else None),
        )
        for index, (score, entry, literal) in enumerate(returned, start=1)
    )
    return _build_listing(
        context=context,
        program=selected_program,
        setting_path=selected_path,
        query=selected_query,
        normalized_query=normalized_query,
        job_kind=selected_job,
        limit=bounded_limit,
        status=ScientificSettingsListStatusV2.OK,
        inventory_count=len(scoped_entries),
        matched_count=len(ordered),
        items=items,
        reason_rule_ids=(),
    )


def _validated_lookup_context(
    registry: ScientificSettingsRegistryV2,
    loaded_inventories: Sequence[ScientificSettingsInventoryV2],
) -> _LookupContext:
    validated_registry = ScientificSettingsRegistryV2.model_validate(
        registry.model_dump(mode="json")
    )
    if validated_registry.inventory_population_state != "populated":
        raise ValueError("V2 lookup requires an explicitly populated registry")
    inventories = tuple(
        ScientificSettingsInventoryV2.model_validate(
            inventory.model_dump(mode="json")
        )
        for inventory in loaded_inventories
    )
    if not inventories:
        raise ValueError("V2 lookup requires loaded descriptor-bound inventories")
    if len({item.inventory_sha256 for item in inventories}) != len(inventories):
        raise ValueError("V2 lookup inventories must be unique")

    descriptor_by_key = {
        (
            item.inventory_id,
            item.inventory_version,
            item.inventory_sha256,
        ): item
        for item in validated_registry.inventories
    }
    matched_descriptor_ids: set[str] = set()
    for inventory in inventories:
        key = (
            inventory.inventory_id,
            inventory.inventory_version,
            inventory.inventory_sha256,
        )
        descriptor = descriptor_by_key.get(key)
        if descriptor is None:
            raise ValueError("V2 lookup inventory is not registry-bound")
        if (
            descriptor.inventory_schema_version != inventory.schema_version
            or descriptor.normalization_version
            != inventory.normalization_version
            or descriptor.entry_count != len(inventory.entries)
            or descriptor.scopes != _inventory_scopes(inventory)
            or inventory.evidence_ceiling != validated_registry.evidence_ceiling
        ):
            raise ValueError("V2 lookup inventory descriptor does not match content")
        matched_descriptor_ids.add(descriptor.inventory_id)
    if matched_descriptor_ids != {
        item.inventory_id for item in validated_registry.inventories
    }:
        raise ValueError("V2 lookup requires every registry inventory")

    entries = tuple(
        sorted(
            (
                entry
                for inventory in inventories
                for entry in inventory.entries
            ),
            key=lambda item: (
                item.program.value,
                item.setting_path,
                item.entry_id,
            ),
        )
    )
    _validate_global_entry_namespace(entries)
    ordered_inventories = tuple(
        sorted(inventories, key=lambda item: item.inventory_sha256)
    )
    return _LookupContext(
        registry=validated_registry,
        inventories=ordered_inventories,
        entries=entries,
        inventory_sha256s=tuple(
            item.inventory_sha256 for item in ordered_inventories
        ),
    )


def _validate_global_entry_namespace(
    entries: tuple[SettingInventoryEntryV2, ...],
) -> None:
    entry_ids: set[str] = set()
    literal_owner: dict[tuple[ScientificProgram, str, str], str] = {}
    for entry in entries:
        if entry.entry_id in entry_ids:
            raise ValueError("V2 lookup entry IDs collide across inventories")
        entry_ids.add(entry.entry_id)
        for literal in (entry.canonical_value, *entry.aliases):
            key = (
                entry.program,
                entry.setting_path,
                normalize_setting_literal(literal),
            )
            owner = literal_owner.get(key)
            if owner not in {None, entry.entry_id}:
                raise ValueError(
                    "V2 lookup literals collide across inventories"
                )
            literal_owner[key] = entry.entry_id


def _build_resolution(
    *,
    context: _LookupContext,
    program: ScientificProgram,
    setting_path: str,
    requested_value: str,
    normalized_value: str,
    job_kind: str,
    status: SettingResolutionStatusV2,
    matched_by: SettingMatchKindV2,
    entry: SettingInventoryEntryV2 | None,
    candidates: tuple[SettingCandidateV2, ...],
    job_scope_compatible: bool | None,
    reason_rule_id: str,
) -> SettingResolutionV2:
    observations = _entry_observations(
        entry,
        job_scope_compatible=job_scope_compatible,
    )
    project_eligible = bool(
        entry is not None
        and job_scope_compatible is True
        and observations["loader_accepted"]
        and observations["renderer_preserved"]
        and (
            not observations["applicability_rules_present"]
            or observations["deterministic_validator_enforced"]
        )
        and status is SettingResolutionStatusV2.EXACT_REGISTERED
    )
    body = {
        "schema_version": "chemsmart.scientific-setting-resolution.v2",
        "registry_sha256": context.registry.registry_sha256,
        "inventory_sha256s": context.inventory_sha256s,
        "program": program,
        "setting_path": setting_path,
        "requested_value": requested_value,
        "normalized_requested_value": normalized_value,
        "job_kind": job_kind,
        "status": status,
        "matched_by": matched_by,
        "entry_id": entry.entry_id if entry is not None else None,
        "canonical_value": (
            entry.canonical_value if entry is not None else None
        ),
        "candidates": tuple(item.model_dump(mode="json") for item in candidates),
        **observations,
        "job_scope_compatible": job_scope_compatible,
        "project_candidate_eligible": project_eligible,
        "reason_rule_id": reason_rule_id,
        "evidence_ceiling": context.registry.evidence_ceiling.model_dump(
            mode="json"
        ),
    }
    body["resolution_sha256"] = scientific_setting_resolution_v2_sha256(body)
    return SettingResolutionV2.model_validate(body)


def _build_listing(
    *,
    context: _LookupContext,
    program: ScientificProgram,
    setting_path: str,
    query: str,
    normalized_query: str,
    job_kind: str,
    limit: int,
    status: ScientificSettingsListStatusV2,
    inventory_count: int,
    matched_count: int,
    items: tuple[ScientificSettingsListItemV2, ...],
    reason_rule_ids: tuple[str, ...],
) -> ScientificSettingsListV2:
    body = {
        "schema_version": "chemsmart.scientific-settings-list.v2",
        "registry_sha256": context.registry.registry_sha256,
        "inventory_sha256s": context.inventory_sha256s,
        "program": program,
        "setting_path": setting_path,
        "query": query,
        "normalized_query": normalized_query,
        "job_kind": job_kind,
        "limit": limit,
        "status": status,
        "inventory_count": inventory_count,
        "matched_count": matched_count,
        "returned_count": len(items),
        "truncated": matched_count > len(items),
        "items": tuple(item.model_dump(mode="json") for item in items),
        "reason_rule_ids": reason_rule_ids,
        "token_policy": "bounded_view_only",
        "evidence_ceiling": context.registry.evidence_ceiling.model_dump(
            mode="json"
        ),
    }
    body["listing_sha256"] = scientific_settings_list_v2_sha256(body)
    return ScientificSettingsListV2.model_validate(body)


def _entry_observations(
    entry: SettingInventoryEntryV2 | None,
    *,
    job_scope_compatible: bool | None,
) -> dict[str, object]:
    if entry is None:
        return {
            "source_registered": False,
            "loader_observation": LoaderObservation.NOT_OBSERVED,
            "loader_accepted": False,
            "renderer_observation": RendererObservation.NOT_OBSERVED,
            "renderer_preserved": False,
            "applicability_rule_ids": (),
            "applicability_rules_present": False,
            "deterministic_validator_enforced": False,
        }
    return {
        "source_registered": True,
        "loader_observation": entry.loader_observation,
        "loader_accepted": (
            entry.loader_observation is LoaderObservation.ACCEPTED
        ),
        "renderer_observation": entry.renderer_observation,
        "renderer_preserved": (
            entry.renderer_observation is RendererObservation.PRESERVED
        ),
        "applicability_rule_ids": entry.applicability_rule_ids,
        "applicability_rules_present": bool(entry.applicability_rule_ids),
        "deterministic_validator_enforced": entry.validator_enforced,
    }


def _fuzzy_candidates(
    entries: tuple[SettingInventoryEntryV2, ...],
    *,
    normalized_value: str,
    job_kind: str,
    limit: int,
) -> tuple[SettingCandidateV2, ...]:
    ranked = tuple(
        item
        for item in (
            _ranked_entry(entry, normalized_value) for entry in entries
        )
        if item[0] >= _FUZZY_MINIMUM_BASIS_POINTS
        and item[0] < 10000
    )
    ordered = tuple(
        sorted(
            ranked,
            key=lambda item: (
                -item[0],
                item[1].canonical_value.casefold(),
                item[1].entry_id,
            ),
        )[:limit]
    )
    return tuple(
        _candidate(
            rank=index,
            entry=entry,
            matched_literal=literal,
            score=score,
            job_kind=job_kind,
        )
        for index, (score, entry, literal) in enumerate(ordered, start=1)
    )


def _candidate(
    *,
    rank: int,
    entry: SettingInventoryEntryV2,
    matched_literal: str,
    score: int,
    job_kind: str,
) -> SettingCandidateV2:
    job_compatible = _job_is_compatible(entry, job_kind)
    rules_present = bool(entry.applicability_rule_ids)
    eligible = bool(
        job_compatible
        and (not rules_present or entry.validator_enforced)
        and entry.loader_observation is LoaderObservation.ACCEPTED
        and entry.renderer_observation is RendererObservation.PRESERVED
    )
    return SettingCandidateV2(
        rank=rank,
        entry_id=entry.entry_id,
        canonical_value=entry.canonical_value,
        matched_literal=matched_literal,
        similarity_basis_points=score,
        source_registered=True,
        loader_observation=entry.loader_observation,
        loader_accepted=(
            entry.loader_observation is LoaderObservation.ACCEPTED
        ),
        renderer_observation=entry.renderer_observation,
        renderer_preserved=(
            entry.renderer_observation is RendererObservation.PRESERVED
        ),
        applicability_rule_ids=entry.applicability_rule_ids,
        applicability_rules_present=rules_present,
        deterministic_validator_enforced=entry.validator_enforced,
        job_scope_compatible=job_compatible,
        project_candidate_eligible_after_selection=eligible,
    )


def _list_item(
    *,
    rank: int,
    entry: SettingInventoryEntryV2,
    job_kind: str,
    score: int | None,
    matched_literal: str | None,
) -> ScientificSettingsListItemV2:
    job_compatible = _job_is_compatible(entry, job_kind)
    rules_present = bool(entry.applicability_rule_ids)
    eligible = bool(
        job_compatible
        and (not rules_present or entry.validator_enforced)
        and entry.loader_observation is LoaderObservation.ACCEPTED
        and entry.renderer_observation is RendererObservation.PRESERVED
    )
    return ScientificSettingsListItemV2(
        rank=rank,
        entry_id=entry.entry_id,
        canonical_value=entry.canonical_value,
        matched_literal=matched_literal,
        similarity_basis_points=score,
        source_registered=True,
        loader_observation=entry.loader_observation,
        loader_accepted=(
            entry.loader_observation is LoaderObservation.ACCEPTED
        ),
        renderer_observation=entry.renderer_observation,
        renderer_preserved=(
            entry.renderer_observation is RendererObservation.PRESERVED
        ),
        applicability_rule_ids=entry.applicability_rule_ids,
        applicability_rules_present=rules_present,
        deterministic_validator_enforced=entry.validator_enforced,
        job_scope_compatible=job_compatible,
        project_candidate_eligible=eligible,
    )


def _ranked_entry(
    entry: SettingInventoryEntryV2,
    normalized_query: str,
) -> tuple[int, SettingInventoryEntryV2, str]:
    scored_literals = tuple(
        (
            _similarity_basis_points(
                normalized_query,
                normalize_setting_literal(literal),
            ),
            literal,
        )
        for literal in (entry.canonical_value, *entry.aliases)
    )
    score, literal = min(
        scored_literals,
        key=lambda item: (-item[0], item[1].casefold(), item[1]),
    )
    return score, entry, literal


def _similarity_basis_points(left: str, right: str) -> int:
    if left == right:
        return 10000
    maximum_length = max(len(left), len(right))
    if maximum_length == 0:
        return 0
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1]
                    + (left_character != right_character),
                )
            )
        previous = current
    distance = previous[-1]
    return ((maximum_length - distance) * 10000) // maximum_length


def _exact_entry(
    entries: tuple[SettingInventoryEntryV2, ...],
    normalized_value: str,
) -> SettingInventoryEntryV2 | None:
    for entry in entries:
        if normalized_value in {
            normalize_setting_literal(literal)
            for literal in (entry.canonical_value, *entry.aliases)
        }:
            return entry
    return None


def _job_is_compatible(entry: SettingInventoryEntryV2, job_kind: str) -> bool:
    return bool(
        "*" in entry.applicable_job_kinds
        or job_kind in entry.applicable_job_kinds
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


def _program(value: ScientificProgram | str) -> ScientificProgram:
    if isinstance(value, ScientificProgram):
        return value
    return ScientificProgram(str(value).strip().casefold())


def _setting_path(value: str) -> str:
    selected = str(value or "").strip().casefold()
    if _SETTING_PATH.fullmatch(selected) is None:
        raise ValueError("setting_path is invalid")
    return selected


def _job_kind(value: str) -> str:
    selected = str(value or "").strip().casefold()
    if _JOB_KIND.fullmatch(selected) is None:
        raise ValueError("job_kind is invalid")
    return selected


def _literal(value: str) -> str:
    selected = str(value or "").strip()
    if (
        not selected
        or len(selected) > 300
        or _SAFE_TEXT.fullmatch(selected) is None
        or not normalize_setting_literal(selected)
    ):
        raise ValueError("setting value is invalid")
    return selected


def _query(value: str) -> str:
    selected = str(value or "").strip()
    if len(selected) > 300 or (
        selected and _SAFE_TEXT.fullmatch(selected) is None
    ):
        raise ValueError("setting query is invalid")
    return selected


__all__ = [
    "list_scientific_settings_v2",
    "resolve_scientific_setting_v2",
]
