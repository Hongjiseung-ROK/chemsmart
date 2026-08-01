"""BSE-backed basis-set name validation for chemsmart harnesses.

This module intentionally validates *names and intent*, not atomic basis
coefficients. Coefficient/source-of-truth data remains in Basis Set Exchange;
chemsmart keeps a small generated catalog so runtime harness checks are fast
and reproducible offline.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass, replace
from functools import lru_cache
from importlib import metadata as importlib_metadata
from importlib.resources import files
from typing import Any, Iterable, Literal

BasisProgram = Literal["gaussian", "orca"]
BasisIntentVerdict = Literal["ok", "warn", "reject", "ask_user"]
BasisRole = Literal["any", "orbital", "jfit", "jkfit", "rifit", "admmfit"]
BasisElementInspectionStatus = Literal[
    "all_elements_covered",
    "basis_unresolved",
    "element_coverage_missing",
    "source_version_mismatch",
    "bse_data_unavailable",
    "catalog_unavailable",
    "catalog_non_authoritative",
    "ecp_definition_inconsistent",
    "orbital_functions_missing",
]

_DATA_FILE = "bse_basis_catalog.json"
_FROZEN_CATALOG_ARTIFACT_SHA256 = (
    "ed4ef918fb80e8ad3c2396c237d2120c31892cfaa2a61fb61af52965dc723c0b"
)
_FROZEN_CATALOG_CONTENT_SHA256 = (
    "a4c39327851ed653ec849c2109549cad4f0ee4e4207ea20143a368d25b2e2732"
)
_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9*+]+")
_AMBIGUOUS_QUALITY_RE = re.compile(
    r"\b(good|reasonable|standard|large|small|better|best|accurate|cheap|"
    r"fast|diffuse|polarized|polarised|double[-\s]*zeta|triple[-\s]*zeta|"
    r"karlsruhe|dunning|pople)\b",
    re.IGNORECASE,
)
_MAX_SEARCH_LIMIT = 20

_FAMILY_TERMS = {
    "ahlrichs": {"ahlrichs", "karlsruhe", "def2", "def"},
    "dunning": {"dunning", "correlation consistent", "cc", "aug cc"},
    "pople": {
        "pople",
        "split valence",
        "split-valence",
        "six thirty one",
        "6-31",
        "631",
    },
}
_QUALITY_TERMS = {
    "double_zeta": {
        "double zeta",
        "double-zeta",
        "dz",
        "svp",
        "valence double",
    },
    "triple_zeta": {
        "triple zeta",
        "triple-zeta",
        "tz",
        "tzv",
        "tzvp",
        "tee zeta",
        "three zeta",
        "valence triple",
    },
    "quadruple_zeta": {"quadruple zeta", "quadruple-zeta", "qz", "qzvp"},
    "diffuse": {"diffuse", "augmented", "aug", "+", "svpd", "tzvpd"},
    "polarized": {
        "polarized",
        "polarised",
        "polarization",
        "polarisation",
        "star",
        "*",
        "vp",
    },
}
_ROLE_TERMS = {
    "jfit": {"jfit", "j fit", "coulomb fitting", "coulomb-fit"},
    "jkfit": {"jkfit", "jk fit", "exchange fitting", "exchange-fit"},
    "rifit": {"rifit", "ri fit", "ri-fit", "resolution of identity", "aux"},
    "admmfit": {"admm", "admmfit", "admm fit"},
}


@dataclass(frozen=True)
class BasisIntentResult:
    verdict: BasisIntentVerdict
    input_text: str
    program: BasisProgram
    canonical_name: str | None = None
    catalog_key: str | None = None
    message: str = ""
    candidates: tuple[str, ...] = ()
    evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "input_text": self.input_text,
            "program": self.program,
            "canonical_name": self.canonical_name,
            "catalog_key": self.catalog_key,
            "message": self.message,
            "candidates": list(self.candidates),
            "evidence": self.evidence or {},
        }


@dataclass(frozen=True)
class BasisElementObservation:
    """Element-resolved orbital/ECP facts from one pinned BSE definition."""

    atomic_number: int
    symbol: str
    covered: bool
    orbital_present: bool
    electron_shell_count: int
    ecp_present: bool
    ecp_potential_count: int
    ecp_electrons: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "atomic_number": self.atomic_number,
            "symbol": self.symbol,
            "covered": self.covered,
            "orbital_present": self.orbital_present,
            "electron_shell_count": self.electron_shell_count,
            "ecp_present": self.ecp_present,
            "ecp_potential_count": self.ecp_potential_count,
            "ecp_electrons": self.ecp_electrons,
        }


@dataclass(frozen=True)
class BasisElementInspectionResult:
    """Typed, non-engine receipt for basis coverage and embedded BSE ECP data.

    This result says only what the installed, version-matched BSE definition
    contains for the requested elements.  It does not prove that a native
    engine keyword is accepted, that a project combination is suitable, or
    that safe preview or an engine execution succeeded.  Its SHA-256 values
    are deterministic content identities for replay and accidental-mutation
    detection; they are not signatures and do not authenticate a producer.
    """

    schema_version: Literal["chemsmart.basis-element-inspection.v1"]
    verdict: Literal["ok", "reject"]
    status: BasisElementInspectionStatus
    input_text: str
    program: BasisProgram
    canonical_name: str | None
    catalog_key: str | None
    source_package: Literal["basis_set_exchange"]
    source_version: str | None
    catalog_source_version: str | None
    source_version_matches_catalog: bool
    catalog_artifact_sha256: str | None
    catalog_content_sha256: str | None
    catalog_authority: Literal[
        "frozen_default",
        "frozen_default_digest_mismatch",
        "custom_non_authoritative",
        "unavailable",
    ]
    catalog_authoritative: bool
    requested_atomic_numbers: tuple[int, ...]
    elements: tuple[BasisElementObservation, ...]
    missing_atomic_numbers: tuple[int, ...]
    rule_ids: tuple[str, ...]
    definition_sha256: str | None
    orbital_basis_usable: bool | None
    ecp_definition_coherent: bool | None
    error_class: str | None
    receipt_sha256: str
    evidence_scope: Literal["bse_element_definition_only"] = (
        "bse_element_definition_only"
    )
    native_engine_verified: Literal[False] = False
    safe_preview_executed: Literal[False] = False
    engine_executed: Literal[False] = False
    hash_semantics: Literal["content_identity_not_authentication"] = (
        "content_identity_not_authentication"
    )

    def _receipt_content(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "verdict": self.verdict,
            "status": self.status,
            "input_text": self.input_text,
            "program": self.program,
            "canonical_name": self.canonical_name,
            "catalog_key": self.catalog_key,
            "source_package": self.source_package,
            "source_version": self.source_version,
            "catalog_source_version": self.catalog_source_version,
            "source_version_matches_catalog": (
                self.source_version_matches_catalog
            ),
            "catalog_artifact_sha256": self.catalog_artifact_sha256,
            "catalog_content_sha256": self.catalog_content_sha256,
            "catalog_authority": self.catalog_authority,
            "catalog_authoritative": self.catalog_authoritative,
            "requested_atomic_numbers": list(self.requested_atomic_numbers),
            "elements": [item.to_dict() for item in self.elements],
            "missing_atomic_numbers": list(self.missing_atomic_numbers),
            "rule_ids": list(self.rule_ids),
            "definition_sha256": self.definition_sha256,
            "orbital_basis_usable": self.orbital_basis_usable,
            "ecp_definition_coherent": self.ecp_definition_coherent,
            "error_class": self.error_class,
            "evidence_scope": self.evidence_scope,
            "native_engine_verified": self.native_engine_verified,
            "safe_preview_executed": self.safe_preview_executed,
            "engine_executed": self.engine_executed,
            "hash_semantics": self.hash_semantics,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._receipt_content(),
            "receipt_sha256": self.receipt_sha256,
        }

    def receipt_sha256_is_valid(self) -> bool:
        """Return whether the stored receipt digest matches current content."""

        return self.receipt_sha256 == _canonical_content_sha256(
            self._receipt_content()
        )


@lru_cache(maxsize=1)
def _load_basis_catalog_snapshot() -> tuple[dict[str, Any], str, str]:
    path = files(__package__).joinpath(_DATA_FILE)
    with path.open("rb") as handle:
        raw = handle.read()
    catalog = json.loads(raw.decode("utf-8"))
    artifact_sha256 = hashlib.sha256(raw).hexdigest()
    content_sha256 = _canonical_content_sha256(catalog)
    return catalog, artifact_sha256, content_sha256


def load_basis_catalog() -> dict[str, Any]:
    """Return an isolated copy of the frozen catalog snapshot.

    The internal cache is never exposed, so a caller cannot mutate the catalog
    used by later name resolutions or element inspections.
    """

    catalog, _, _ = _load_basis_catalog_snapshot()
    return deepcopy(catalog)


def resolve_basis_name(
    name: str,
    *,
    program: BasisProgram,
    catalog: dict[str, Any] | None = None,
) -> BasisIntentResult:
    """Resolve an explicit basis-set name against a program-specific catalog."""

    catalog = catalog or load_basis_catalog()
    normalized = normalize_basis_name(name)
    aliases = catalog.get("aliases", {})
    entry_key = aliases.get(normalized)
    if entry_key is None:
        return BasisIntentResult(
            verdict="reject",
            input_text=name,
            program=program,
            message="basis set name is not in the BSE-backed chemsmart catalog",
            candidates=_near_matches(normalized, catalog),
            evidence={"normalized": normalized},
        )

    entry = catalog["basis_sets"][entry_key]
    programs = set(entry.get("programs", []))
    if program not in programs:
        return BasisIntentResult(
            verdict="reject",
            input_text=name,
            program=program,
            canonical_name=entry.get("display_name"),
            catalog_key=entry_key,
            message=f"basis set exists in BSE but is not renderable for {program}",
            evidence={
                "normalized": normalized,
                "programs": sorted(programs),
                "family": entry.get("family"),
                "role": entry.get("role"),
            },
        )

    return BasisIntentResult(
        verdict="ok",
        input_text=name,
        program=program,
        canonical_name=entry.get("display_name"),
        catalog_key=entry_key,
        message="basis set name resolved to a BSE canonical entry",
        evidence={
            "normalized": normalized,
            "family": entry.get("family"),
            "role": entry.get("role"),
            "function_types": entry.get("function_types", []),
            "elements_count": len(entry.get("elements", [])),
        },
    )


def inspect_basis_elements(
    name: str,
    *,
    program: BasisProgram,
    elements: Iterable[int | str],
    catalog: dict[str, Any] | None = None,
) -> BasisElementInspectionResult:
    """Inspect per-element orbital and ECP presence in pinned local BSE data.

    ``resolve_basis_name`` remains the name/program gate.  This additive
    inspector then binds that exact entry to a canonical set of atomic numbers
    and reads BSE's structured data without rendering native input or invoking
    a chemistry engine.
    """

    atomic_numbers = _normalize_basis_elements(elements)
    selected_catalog: dict[str, Any] | None = None
    catalog_artifact_sha256: str | None = None
    catalog_content_sha256: str | None = None
    catalog_source_version: str | None = None
    catalog_authority: Literal[
        "frozen_default",
        "frozen_default_digest_mismatch",
        "custom_non_authoritative",
        "unavailable",
    ] = "unavailable"
    catalog_authoritative = False
    source_version: str | None = None
    source_version_matches_catalog = False

    def finish(
        *,
        status: BasisElementInspectionStatus,
        rule_ids: Iterable[str],
        canonical_name: str | None = None,
        catalog_key: str | None = None,
        observations: tuple[BasisElementObservation, ...] = (),
        missing_atomic_numbers: tuple[int, ...] = (),
        definition_sha256: str | None = None,
        orbital_basis_usable: bool | None = None,
        ecp_definition_coherent: bool | None = None,
        error_class: str | None = None,
    ) -> BasisElementInspectionResult:
        ordered_rules = tuple(dict.fromkeys(rule_ids))
        return _build_basis_element_inspection_result(
            schema_version="chemsmart.basis-element-inspection.v1",
            verdict="reject" if ordered_rules else "ok",
            status=status,
            input_text=name,
            program=program,
            canonical_name=canonical_name,
            catalog_key=catalog_key,
            source_package="basis_set_exchange",
            source_version=source_version,
            catalog_source_version=catalog_source_version,
            source_version_matches_catalog=source_version_matches_catalog,
            catalog_artifact_sha256=catalog_artifact_sha256,
            catalog_content_sha256=catalog_content_sha256,
            catalog_authority=catalog_authority,
            catalog_authoritative=catalog_authoritative,
            requested_atomic_numbers=atomic_numbers,
            elements=observations,
            missing_atomic_numbers=missing_atomic_numbers,
            rule_ids=ordered_rules,
            definition_sha256=definition_sha256,
            orbital_basis_usable=orbital_basis_usable,
            ecp_definition_coherent=ecp_definition_coherent,
            error_class=error_class,
        )

    catalog_rules: list[str] = []
    try:
        if catalog is None:
            snapshot, artifact_digest, content_digest = (
                _load_basis_catalog_snapshot()
            )
            selected_catalog = deepcopy(snapshot)
            catalog_artifact_sha256 = artifact_digest
            catalog_content_sha256 = content_digest
            catalog_authoritative = bool(
                artifact_digest == _FROZEN_CATALOG_ARTIFACT_SHA256
                and content_digest == _FROZEN_CATALOG_CONTENT_SHA256
            )
            catalog_authority = (
                "frozen_default"
                if catalog_authoritative
                else "frozen_default_digest_mismatch"
            )
            if not catalog_authoritative:
                catalog_rules.append(
                    "basis.element_inspection.catalog_digest_mismatch"
                )
        else:
            catalog_authority = "custom_non_authoritative"
            catalog_rules.append(
                "basis.element_inspection.custom_catalog_non_authoritative"
            )
            _validate_basis_catalog_shape(catalog)
            selected_catalog = deepcopy(catalog)
            catalog_content_sha256 = _canonical_content_sha256(
                selected_catalog
            )
        catalog_source_version = str(
            selected_catalog["metadata"]["source_version"]
        )
    except Exception as exc:
        return finish(
            status="catalog_unavailable",
            rule_ids=(
                *catalog_rules,
                "basis.element_inspection.catalog_unavailable",
            ),
            error_class=type(exc).__name__,
        )

    if not catalog_authoritative and catalog is None:
        return finish(
            status="catalog_unavailable",
            rule_ids=catalog_rules,
            error_class="CatalogDigestMismatch",
        )

    try:
        source_version = importlib_metadata.version("basis_set_exchange")
    except Exception as exc:
        return finish(
            status="bse_data_unavailable",
            rule_ids=(
                *catalog_rules,
                "basis.element_inspection.bse_data_unavailable",
            ),
            error_class=type(exc).__name__,
        )

    source_version_matches_catalog = source_version == catalog_source_version
    if not source_version_matches_catalog:
        return finish(
            status="source_version_mismatch",
            rule_ids=(
                *catalog_rules,
                "basis.element_inspection.source_version_mismatch",
            ),
            error_class="SourceVersionMismatch",
        )

    try:
        import basis_set_exchange as bse
    except Exception as exc:
        return finish(
            status="bse_data_unavailable",
            rule_ids=(
                *catalog_rules,
                "basis.element_inspection.bse_data_unavailable",
            ),
            error_class=type(exc).__name__,
        )

    assert selected_catalog is not None
    try:
        resolution = resolve_basis_name(
            name,
            program=program,
            catalog=selected_catalog,
        )
    except Exception as exc:
        return finish(
            status="catalog_unavailable",
            rule_ids=(
                *catalog_rules,
                "basis.element_inspection.catalog_unavailable",
            ),
            error_class=type(exc).__name__,
        )
    if resolution.verdict != "ok" or resolution.catalog_key is None:
        return finish(
            status="basis_unresolved",
            rule_ids=(
                *catalog_rules,
                "basis.element_inspection.basis_unresolved",
            ),
            canonical_name=resolution.canonical_name,
            catalog_key=resolution.catalog_key,
            observations=tuple(
                _missing_element_observation(z) for z in atomic_numbers
            ),
            missing_atomic_numbers=atomic_numbers,
        )

    try:
        entry = selected_catalog["basis_sets"][resolution.catalog_key]
        declared = {int(z) for z in entry.get("elements", ())}
    except Exception as exc:
        return finish(
            status="catalog_unavailable",
            rule_ids=(
                *catalog_rules,
                "basis.element_inspection.catalog_unavailable",
            ),
            canonical_name=resolution.canonical_name,
            catalog_key=resolution.catalog_key,
            error_class=type(exc).__name__,
        )

    covered = tuple(z for z in atomic_numbers if z in declared)
    missing_atomic_numbers = tuple(z for z in atomic_numbers if z not in declared)
    observations_by_z: dict[int, BasisElementObservation] = {}
    used_element_data: dict[str, Any] = {}
    ecp_inconsistent = False
    try:
        if covered:
            data = bse.get_basis(
                resolution.canonical_name,
                elements=list(covered),
                fmt=None,
                header=False,
            )
            if not isinstance(data, dict):
                raise InvalidBSEPayloadError("BSE result is not a mapping")
            bse_elements = data.get("elements")
            if not isinstance(bse_elements, dict):
                raise InvalidBSEPayloadError(
                    "BSE elements payload is not a mapping"
                )
            for atomic_number in covered:
                element = bse_elements.get(str(atomic_number))
                if not isinstance(element, dict):
                    raise InvalidBSEPayloadError(
                        "BSE element payload is not a mapping"
                    )
                electron_shells = element.get("electron_shells") or ()
                ecp_potentials = element.get("ecp_potentials") or ()
                if not isinstance(electron_shells, (list, tuple)) or not isinstance(
                    ecp_potentials, (list, tuple)
                ):
                    raise InvalidBSEPayloadError(
                        "BSE shell or ECP payload is not a sequence"
                    )
                raw_ecp_electrons = element.get("ecp_electrons")
                ecp_electrons = (
                    int(raw_ecp_electrons)
                    if raw_ecp_electrons is not None
                    else None
                )
                ecp_present = bool(ecp_potentials)
                positive_ecp_electrons = bool(
                    ecp_electrons is not None and ecp_electrons > 0
                )
                if ecp_present != positive_ecp_electrons:
                    ecp_inconsistent = True
                used_element_data[str(atomic_number)] = element
                observations_by_z[atomic_number] = BasisElementObservation(
                    atomic_number=atomic_number,
                    symbol=_element_symbol(atomic_number),
                    covered=True,
                    orbital_present=bool(electron_shells),
                    electron_shell_count=len(electron_shells),
                    ecp_present=ecp_present,
                    ecp_potential_count=len(ecp_potentials),
                    ecp_electrons=ecp_electrons,
                )
    except Exception as exc:
        return finish(
            status="bse_data_unavailable",
            rule_ids=(
                *catalog_rules,
                "basis.element_inspection.bse_data_unavailable",
            ),
            canonical_name=resolution.canonical_name,
            catalog_key=resolution.catalog_key,
            error_class=type(exc).__name__,
        )

    observations = tuple(
        observations_by_z.get(
            atomic_number,
            _missing_element_observation(atomic_number),
        )
        for atomic_number in atomic_numbers
    )
    definition_sha256 = (
        _canonical_content_sha256(
            {
                "schema_version": "chemsmart.bse-element-definition-digest.v1",
                "source_package": "basis_set_exchange",
                "source_version": source_version,
                "canonical_name": resolution.canonical_name,
                "elements": used_element_data,
            }
        )
        if used_element_data
        else None
    )
    orbital_basis_usable = bool(
        not missing_atomic_numbers
        and observations
        and all(item.orbital_present for item in observations)
    )
    rule_ids = list(catalog_rules)
    if missing_atomic_numbers:
        rule_ids.append("basis.element_inspection.element_coverage_missing")
    if ecp_inconsistent:
        rule_ids.append("basis.element_inspection.ecp_definition_inconsistent")
    if not missing_atomic_numbers and not orbital_basis_usable:
        rule_ids.append("basis.element_inspection.orbital_functions_missing")

    if missing_atomic_numbers:
        status: BasisElementInspectionStatus = "element_coverage_missing"
    elif ecp_inconsistent:
        status = "ecp_definition_inconsistent"
    elif not orbital_basis_usable:
        status = "orbital_functions_missing"
    elif catalog_rules:
        status = "catalog_non_authoritative"
    else:
        status = "all_elements_covered"
    return finish(
        status=status,
        rule_ids=rule_ids,
        canonical_name=resolution.canonical_name,
        catalog_key=resolution.catalog_key,
        observations=observations,
        missing_atomic_numbers=missing_atomic_numbers,
        definition_sha256=definition_sha256,
        orbital_basis_usable=orbital_basis_usable,
        ecp_definition_coherent=not ecp_inconsistent,
    )


def _build_basis_element_inspection_result(
    **values: Any,
) -> BasisElementInspectionResult:
    provisional = BasisElementInspectionResult(
        **values,
        receipt_sha256="",
    )
    return replace(
        provisional,
        receipt_sha256=_canonical_content_sha256(
            provisional._receipt_content()
        ),
    )


def _canonical_content_sha256(value: Any) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class InvalidBSEPayloadError(ValueError):
    """Raised when local BSE data does not match its structured contract."""


def _validate_basis_catalog_shape(catalog: Any) -> None:
    if not isinstance(catalog, dict):
        raise ValueError("basis catalog must be a mapping")
    metadata = catalog.get("metadata")
    if not isinstance(metadata, dict) or not metadata.get("source_version"):
        raise ValueError("basis catalog source version is missing")
    for key in ("aliases", "basis_sets", "programs"):
        if not isinstance(catalog.get(key), dict):
            raise ValueError(f"basis catalog {key} mapping is missing")


@lru_cache(maxsize=1)
def _periodic_table() -> Any:
    from chemsmart.utils.periodictable import PeriodicTable

    return PeriodicTable()


def _normalize_basis_elements(elements: Iterable[int | str]) -> tuple[int, ...]:
    periodic_table = _periodic_table()
    atomic_numbers: set[int] = set()
    for element in elements:
        if isinstance(element, bool):
            raise ValueError("basis elements must be atomic numbers or symbols")
        if isinstance(element, int):
            atomic_number = element
        elif isinstance(element, str):
            symbol = element.strip()
            if not symbol or not symbol.isalpha():
                raise ValueError(f"invalid element symbol: {element!r}")
            try:
                normalized_symbol = periodic_table.to_element(symbol)
                atomic_number = int(
                    periodic_table.to_atomic_number(normalized_symbol)
                )
            except (IndexError, KeyError, ValueError) as exc:
                raise ValueError(f"unknown element symbol: {element!r}") from exc
        else:
            raise ValueError("basis elements must be atomic numbers or symbols")
        if not 1 <= atomic_number <= 118:
            raise ValueError(f"atomic number is outside 1..118: {atomic_number}")
        atomic_numbers.add(atomic_number)
    if not atomic_numbers:
        raise ValueError("at least one basis element is required")
    return tuple(sorted(atomic_numbers))


def _element_symbol(atomic_number: int) -> str:
    return str(_periodic_table().to_symbol(atomic_number))


def _missing_element_observation(atomic_number: int) -> BasisElementObservation:
    return BasisElementObservation(
        atomic_number=atomic_number,
        symbol=_element_symbol(atomic_number),
        covered=False,
        orbital_present=False,
        electron_shell_count=0,
        ecp_present=False,
        ecp_potential_count=0,
        ecp_electrons=None,
    )


def check_basis_intent(
    text: str,
    *,
    program: BasisProgram,
    catalog: dict[str, Any] | None = None,
) -> BasisIntentResult:
    """Classify whether user/model text defines a concrete basis-set name.

    This is deliberately conservative. If a phrase sounds like a basis-set
    family or quality request but does not contain a concrete BSE name, the
    result is ``ask_user`` rather than guessing a basis.
    """

    catalog = catalog or load_basis_catalog()
    names = _basis_mentions(text, catalog)
    if len(names) == 1:
        return resolve_basis_name(names[0], program=program, catalog=catalog)
    if len(names) > 1:
        return BasisIntentResult(
            verdict="warn",
            input_text=text,
            program=program,
            message=(
                "multiple concrete basis names were found; caller must decide "
                "whether this is a mixed-basis request"
            ),
            candidates=tuple(names),
            evidence={"mentions": names},
        )
    if _AMBIGUOUS_QUALITY_RE.search(text or ""):
        return BasisIntentResult(
            verdict="ask_user",
            input_text=text,
            program=program,
            message=(
                "basis intent is qualitative or family-level, not a concrete "
                "basis-set name"
            ),
            candidates=tuple(_family_candidates(text, catalog)),
            evidence={"reason": "qualitative_or_family_basis_intent"},
        )
    return BasisIntentResult(
        verdict="reject",
        input_text=text,
        program=program,
        message="no basis-set intent or concrete basis-set name was detected",
    )


def search_basis_sets(
    query: str,
    *,
    program: BasisProgram = "gaussian",
    limit: int = 8,
    role: BasisRole = "any",
) -> dict[str, Any]:
    """Search BSE-backed basis-set names for a short user phrase.

    This tool is intentionally top-k only. It exists so model providers can
    resolve user phrases such as "Karlsruhe triple zeta diffuse" or "RI fit
    for def2-TZVP" without receiving the full BSE catalog in the prompt.
    """

    catalog = load_basis_catalog()
    limit = max(1, min(int(limit or 8), _MAX_SEARCH_LIMIT))
    query = (query or "").strip()
    normalized_query = normalize_basis_name(_expand_common_spoken_forms(query))
    intent = _query_intent(query)
    requested_role = _infer_role(query, role)
    scored: list[tuple[int, str, list[str]]] = []

    for key, entry in catalog.get("basis_sets", {}).items():
        if program not in set(entry.get("programs", [])):
            continue
        if requested_role != "any" and entry.get("role") != requested_role:
            continue

        score, reasons = _score_entry(
            key=key,
            entry=entry,
            normalized_query=normalized_query,
            query_intent=intent,
            requested_role=requested_role,
        )
        if score > 0:
            scored.append((score, key, reasons))

    ranked = sorted(
        scored,
        key=lambda item: (
            -item[0],
            catalog["basis_sets"][item[1]].get("role") != "orbital",
            len(catalog["basis_sets"][item[1]].get("display_name", "")),
            catalog["basis_sets"][item[1]].get("display_name", ""),
        ),
    )
    candidates = [
        _candidate_payload(catalog["basis_sets"][key], score, reasons)
        for score, key, reasons in ranked[:limit]
    ]
    verdict: BasisIntentVerdict = "ok" if candidates else "reject"
    if candidates and _qualitative_intent_only(intent, normalized_query):
        verdict = "ask_user"
    elif len(candidates) > 1 and ranked[0][0] - ranked[1][0] < 15:
        verdict = "warn"

    return {
        "ok": bool(candidates),
        "verdict": verdict,
        "query": query,
        "program": program,
        "normalized_query": normalized_query,
        "requested_role": requested_role,
        "result_count": len(candidates),
        "limit": limit,
        "truncated": len(ranked) > limit,
        "token_policy": "top_k_only; full catalog is never returned",
        "candidates": candidates,
        "message": _search_message(verdict, candidates),
    }


def normalize_basis_name(name: str) -> str:
    text = (name or "").strip().lower()
    text = text.replace("ζ", "zeta")
    # BSE names are punctuation-sensitive in display form, but harness lookup
    # should tolerate user/model spelling variants such as def2 TZVP.
    return "".join(part for part in _TOKEN_SPLIT_RE.split(text) if part)


def _basis_mentions(text: str, catalog: dict[str, Any]) -> list[str]:
    lowered = text or ""
    found: list[str] = []
    seen: set[str] = set()
    display_names = catalog.get("display_name_to_key", {})
    for display_name in sorted(display_names, key=len, reverse=True):
        if _display_name_in_text(display_name, lowered):
            key = display_names[display_name]
            if key not in seen:
                found.append(display_name)
                seen.add(key)
    return found


def _display_name_in_text(display_name: str, text: str) -> bool:
    pattern = re.escape(display_name).replace(r"\-", r"[-\s]?")
    return (
        re.search(
            rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])",
            text,
            re.IGNORECASE,
        )
        is not None
    )


def _near_matches(
    normalized: str, catalog: dict[str, Any], limit: int = 6
) -> tuple[str, ...]:
    if not normalized:
        return ()
    aliases = catalog.get("aliases", {})
    scored = []
    for alias, key in aliases.items():
        if normalized in alias or alias in normalized:
            display = catalog["basis_sets"][key]["display_name"]
            scored.append((abs(len(alias) - len(normalized)), display))
    return tuple(name for _, name in sorted(scored)[:limit])


def _family_candidates(
    text: str, catalog: dict[str, Any], limit: int = 8
) -> list[str]:
    lowered = (text or "").lower()
    family = None
    if "karlsruhe" in lowered or "def2" in lowered or "ahlrichs" in lowered:
        family = "ahlrichs"
    elif "dunning" in lowered or "cc-" in lowered:
        family = "dunning"
    elif "pople" in lowered or "31g" in lowered:
        family = "pople"
    if family is None:
        return []
    names = [
        entry["display_name"]
        for entry in catalog.get("basis_sets", {}).values()
        if entry.get("family") == family and entry.get("role") == "orbital"
    ]
    return sorted(names)[:limit]


def _expand_common_spoken_forms(text: str) -> str:
    lowered = (text or "").lower()
    replacements = {
        "six thirty one": "6-31",
        "six three one": "6-31",
        "six dash thirty one": "6-31",
        "six thirty-one": "6-31",
        "double star": "**",
        "star star": "**",
        "single star": "*",
        "tee zeta": "tz",
        "three zeta": "tz",
    }
    for old, new in replacements.items():
        lowered = lowered.replace(old, new)
    return lowered


def _query_intent(query: str) -> dict[str, str | None | set[str]]:
    lowered = _expand_common_spoken_forms(query)
    family = None
    for family_name, terms in _FAMILY_TERMS.items():
        if any(term in lowered for term in terms):
            family = family_name
            break

    quality = {
        label
        for label, terms in _QUALITY_TERMS.items()
        if any(term in lowered for term in terms)
    }
    return {"family": family, "quality": quality}


def _infer_role(query: str, requested: BasisRole) -> BasisRole:
    if requested != "any":
        return requested
    lowered = _expand_common_spoken_forms(query)
    for role, terms in _ROLE_TERMS.items():
        if any(term in lowered for term in terms):
            return role  # type: ignore[return-value]
    return "any"


def _score_entry(
    *,
    key: str,
    entry: dict[str, Any],
    normalized_query: str,
    query_intent: dict[str, str | None | set[str]],
    requested_role: BasisRole,
) -> tuple[int, list[str]]:
    display = entry.get("display_name", "")
    normalized_display = normalize_basis_name(display)
    score, reasons = _name_match_score(normalized_query, normalized_display)

    query_tokens = set(
        _TOKEN_SPLIT_RE.split(_expand_common_spoken_forms(normalized_query))
    )
    display_tokens = set(_TOKEN_SPLIT_RE.split(normalized_display))
    overlap = {token for token in query_tokens & display_tokens if token}
    if overlap:
        score += 12 * len(overlap)
        reasons.append("token_overlap")

    family = query_intent.get("family")
    if family and entry.get("family") == family:
        score += 40
        reasons.append(f"family:{family}")

    quality = query_intent.get("quality") or set()
    if isinstance(quality, set):
        quality_score, quality_reasons = _quality_score(
            normalized_display,
            quality,
        )
        score += quality_score
        reasons.extend(quality_reasons)

    role = entry.get("role")
    if requested_role != "any" and role == requested_role:
        score += 55
        reasons.append(f"role:{requested_role}")
    elif requested_role == "any" and role == "orbital":
        score += 8
        reasons.append("role:orbital")

    if score == 8 and role == "orbital":
        return 0, []
    if key in {"sto-3g", "3-21g"} and "cheap" not in normalized_query:
        score -= 10
    return score, reasons


def _name_match_score(
    normalized_query: str,
    normalized_display: str,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if not normalized_query:
        return score, reasons
    if normalized_query == normalized_display:
        score += 200
        reasons.append("exact_name")
    elif normalized_query in normalized_display:
        score += 90
        reasons.append("name_contains_query")
    elif normalized_display in normalized_query:
        score += 80
        reasons.append("query_contains_name")
    if "631" in normalized_query and normalized_display.startswith("631g"):
        score += 70
        reasons.append("pople_shorthand:6-31")
    if normalized_query.startswith("631") and normalized_display == "631g*":
        score += 80
        reasons.append("spoken_name:six_thirty_one_star")
    if "def2tzvp" in normalized_query and "def2tzvp" in normalized_display:
        score += 90
        reasons.append("base_basis:def2-tzvp")
    return score, reasons


def _quality_score(
    normalized_display: str,
    quality: set[str],
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if "double_zeta" in quality and any(
        tag in normalized_display for tag in ("svp", "dz")
    ):
        score += 26
        reasons.append("quality:double_zeta")
    if "triple_zeta" in quality and any(
        tag in normalized_display for tag in ("tzvp", "tzv", "tz")
    ):
        score += 30
        reasons.append("quality:triple_zeta")
    if "quadruple_zeta" in quality and any(
        tag in normalized_display for tag in ("qzvp", "qzv", "qz")
    ):
        score += 30
        reasons.append("quality:quadruple_zeta")
    if "diffuse" in quality and any(
        tag in normalized_display
        for tag in ("aug", "+", "svpd", "tzvpd", "qzvpd")
    ):
        score += 26
        reasons.append("quality:diffuse")
    if "polarized" in quality and any(
        tag in normalized_display for tag in ("*", "p", "d")
    ):
        score += 18
        reasons.append("quality:polarized")
    return score, reasons


def _candidate_payload(
    entry: dict[str, Any],
    score: int,
    reasons: list[str],
) -> dict[str, Any]:
    payload = {
        "name": entry.get("display_name"),
        "family": entry.get("family"),
        "role": entry.get("role"),
        "score": score,
        "match_reason": reasons[:5],
        "elements_count": len(entry.get("elements", [])),
    }
    auxiliaries = entry.get("auxiliaries") or {}
    if auxiliaries:
        payload["auxiliaries"] = dict(sorted(auxiliaries.items())[:4])
    return payload


def _qualitative_intent_only(
    intent: dict[str, str | None | set[str]],
    normalized_query: str,
) -> bool:
    return bool(intent.get("family") or intent.get("quality")) and not any(
        token in normalized_query
        for token in ("631", "def2", "ccp", "augcc", "lanl", "sto")
    )


def _search_message(
    verdict: BasisIntentVerdict,
    candidates: list[dict[str, Any]],
) -> str:
    if not candidates:
        return "no BSE-backed basis-set candidates matched the query"
    if verdict == "ask_user":
        return "qualitative basis intent matched candidates; ask user or choose conservatively with evidence"
    if verdict == "warn":
        return "multiple close basis-set candidates matched; preserve ambiguity in the answer"
    return "basis-set search returned ranked BSE-backed candidates"
