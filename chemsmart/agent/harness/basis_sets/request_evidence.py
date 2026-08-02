"""Request-bound, offline BSE basis/ECP evidence.

This additive overlay binds an exact program, basis literal, role, and element
set to the existing local BSE element inspector.  It does not change a
scientific-settings registry, select a fuzzy candidate, infer suitability, or
contact a network service.
"""

from __future__ import annotations

import hashlib
import json
import re
from contextvars import ContextVar
from enum import Enum
from typing import Any, Iterable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from chemsmart.agent.harness.basis_sets.catalog import (
    BasisElementInspectionResult,
    _element_symbol,
    _normalize_basis_elements,
    inspect_basis_elements,
    load_basis_catalog,
    normalize_basis_identity,
)


BASIS_EVIDENCE_REQUEST_SCHEMA_VERSION = (
    "chemsmart.request-bound-basis-evidence-request.v1"
)
BASIS_EVIDENCE_RECEIPT_SCHEMA_VERSION = (
    "chemsmart.request-bound-basis-evidence-receipt.v1"
)
BASIS_EVIDENCE_REF_SCHEMA_VERSION = (
    "chemsmart.request-bound-basis-evidence-ref.v1"
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_RULE_ID = r"^[a-z][a-z0-9_.-]+$"
_SHA256 = r"^[0-9a-f]{64}$"
_SAFE_TEXT = re.compile(r"^[^\x00-\x1f\x7f]+$")
_SOURCE_REPLAY_ACTIVE: ContextVar[bool] = ContextVar(
    "chemsmart_basis_evidence_source_replay_active",
    default=False,
)


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class BasisEvidenceProgram(str, Enum):
    GAUSSIAN = "gaussian"
    ORCA = "orca"
    XTB = "xtb"


class BasisEvidenceRole(str, Enum):
    """An exact requested role; ``any`` is intentionally not representable."""

    ORBITAL = "orbital"
    ECP = "ecp"
    JFIT = "jfit"
    JKFIT = "jkfit"
    RIFIT = "rifit"
    ADMMFIT = "admmfit"
    OPTRI = "optri"
    GUESS = "guess"
    DFTJFIT = "dftjfit"
    DFTXFIT = "dftxfit"


class BasisEvidenceState(str, Enum):
    VERIFIED = "verified"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    CONFLICT = "conflict"


class RequestBoundBasisEvidenceRequestV1(_Contract):
    schema_version: Literal[BASIS_EVIDENCE_REQUEST_SCHEMA_VERSION] = (
        BASIS_EVIDENCE_REQUEST_SCHEMA_VERSION
    )
    request_id: str = Field(pattern=_IDENTIFIER)
    program: BasisEvidenceProgram
    basis_literal: str = Field(min_length=1, max_length=160)
    role: BasisEvidenceRole
    atomic_numbers: tuple[int, ...] = Field(min_length=1)
    request_sha256: str = Field(pattern=_SHA256)
    substitution_allowed: Literal[False] = False
    model_confidence_used: Literal[False] = False
    network_allowed: Literal[False] = False

    @field_validator("basis_literal")
    @classmethod
    def _safe_basis_literal(cls, value: str) -> str:
        if not _SAFE_TEXT.fullmatch(value) or not normalize_basis_identity(value):
            raise ValueError("basis literal is not a safe exact identity")
        return value

    @field_validator("atomic_numbers")
    @classmethod
    def _canonical_atomic_numbers(
        cls,
        values: tuple[int, ...],
    ) -> tuple[int, ...]:
        if values != tuple(sorted(set(values))):
            raise ValueError("requested atomic numbers must be unique and sorted")
        if any(isinstance(value, bool) or not 1 <= value <= 118 for value in values):
            raise ValueError("requested atomic numbers must be within 1..118")
        return values

    @model_validator(mode="after")
    def _request_is_content_addressed(self) -> "RequestBoundBasisEvidenceRequestV1":
        if self.request_sha256 != basis_evidence_request_sha256(self):
            raise ValueError("request-bound basis evidence request digest mismatch")
        return self


class RequestBoundBasisElementEvidenceV1(_Contract):
    atomic_number: int = Field(ge=1, le=118)
    symbol: str = Field(pattern=r"^[A-Z][a-z]?$", max_length=2)
    covered: bool | None
    orbital_present: bool | None
    electron_shell_count: int | None = Field(default=None, ge=0)
    ecp_present: bool | None
    ecp_potential_count: int | None = Field(default=None, ge=0)
    ecp_electrons: int | None = Field(default=None, ge=0)
    state: BasisEvidenceState
    reason_rule_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("reason_rule_ids")
    @classmethod
    def _canonical_rules(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_rule_ids(values)

    @model_validator(mode="after")
    def _element_evidence_is_consistent(
        self,
    ) -> "RequestBoundBasisElementEvidenceV1":
        if self.symbol != _element_symbol(self.atomic_number):
            raise ValueError("basis evidence symbol does not match atomic number")
        if self.covered is None:
            if any(
                value is not None
                for value in (
                    self.orbital_present,
                    self.electron_shell_count,
                    self.ecp_present,
                    self.ecp_potential_count,
                    self.ecp_electrons,
                )
            ):
                raise ValueError("unobserved element cannot contain BSE observations")
        elif self.covered is False and any(
            value not in {False, 0, None}
            for value in (
                self.orbital_present,
                self.electron_shell_count,
                self.ecp_present,
                self.ecp_potential_count,
                self.ecp_electrons,
            )
        ):
            raise ValueError("uncovered element cannot contain basis data")
        if self.ecp_present is False and self.ecp_electrons is not None:
            if self.state is not BasisEvidenceState.CONFLICT:
                raise ValueError("ECP electron count conflicts with ECP absence")
        if self.ecp_present is True and self.ecp_electrons is None:
            if self.state is not BasisEvidenceState.CONFLICT:
                raise ValueError("ECP presence requires an electron count")
        return self


class RequestBoundBasisEvidenceReceiptV1(_Contract):
    schema_version: Literal[BASIS_EVIDENCE_RECEIPT_SCHEMA_VERSION] = (
        BASIS_EVIDENCE_RECEIPT_SCHEMA_VERSION
    )
    receipt_id: str = Field(pattern=_IDENTIFIER)
    request: RequestBoundBasisEvidenceRequestV1
    state: BasisEvidenceState
    requested_basis_identity: str = Field(min_length=1, max_length=160)
    canonical_basis_name: str | None = Field(default=None, max_length=160)
    canonical_basis_identity: str | None = Field(default=None, max_length=160)
    catalog_key: str | None = Field(default=None, max_length=160)
    catalog_role: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_-]{0,79}$",
    )
    function_types: tuple[str, ...] = ()
    elements: tuple[RequestBoundBasisElementEvidenceV1, ...] = Field(
        min_length=1
    )
    inspection_status: str | None = Field(default=None, max_length=120)
    inspection_receipt_sha256: str | None = Field(default=None, pattern=_SHA256)
    definition_sha256: str | None = Field(default=None, pattern=_SHA256)
    catalog_artifact_sha256: str | None = Field(default=None, pattern=_SHA256)
    catalog_content_sha256: str | None = Field(default=None, pattern=_SHA256)
    source_package: Literal["basis_set_exchange"] | None = None
    source_version: str | None = Field(default=None, max_length=80)
    catalog_source_version: str | None = Field(default=None, max_length=80)
    source_version_matches_catalog: bool | None
    error_class: str | None = Field(default=None, max_length=160)
    reason_rule_ids: tuple[str, ...] = Field(min_length=1)
    evidence_scope: Literal[
        "bse_local_element_definition_only",
        "typed_program_not_applicable",
    ]
    substitution_performed: Literal[False] = False
    model_confidence_used: Literal[False] = False
    local_data_only: Literal[True] = True
    network_accessed: Literal[False] = False
    native_engine_verified: Literal[False] = False
    safe_preview_executed: Literal[False] = False
    engine_executed: Literal[False] = False
    scientific_suitability_verified: Literal[False] = False
    receipt_sha256: str = Field(pattern=_SHA256)

    @field_validator("function_types")
    @classmethod
    def _canonical_function_types(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        if values != tuple(sorted(set(values))):
            raise ValueError("BSE function types must be unique and sorted")
        return values

    @field_validator("reason_rule_ids")
    @classmethod
    def _canonical_rules(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_rule_ids(values)

    @field_validator("elements")
    @classmethod
    def _canonical_elements(
        cls,
        values: tuple[RequestBoundBasisElementEvidenceV1, ...],
    ) -> tuple[RequestBoundBasisElementEvidenceV1, ...]:
        numbers = tuple(value.atomic_number for value in values)
        if numbers != tuple(sorted(set(numbers))):
            raise ValueError("basis element evidence must be unique and sorted")
        return values

    @model_validator(mode="after")
    def _receipt_is_consistent(self) -> "RequestBoundBasisEvidenceReceiptV1":
        if self.requested_basis_identity != normalize_basis_identity(
            self.request.basis_literal
        ):
            raise ValueError("requested basis identity is not canonical")
        if self.canonical_basis_name is None:
            if self.canonical_basis_identity is not None:
                raise ValueError("canonical identity requires a canonical basis")
        else:
            expected_identity = normalize_basis_identity(self.canonical_basis_name)
            if self.canonical_basis_identity != expected_identity:
                raise ValueError("canonical basis identity is inconsistent")
            if self.canonical_basis_identity != self.requested_basis_identity:
                raise ValueError("request-bound basis evidence substituted a basis")
        if tuple(value.atomic_number for value in self.elements) != (
            self.request.atomic_numbers
        ):
            raise ValueError("basis evidence changed the requested element set")
        states = tuple(value.state for value in self.elements)
        if self.state is BasisEvidenceState.VERIFIED:
            if any(value is not BasisEvidenceState.VERIFIED for value in states):
                raise ValueError("verified receipt contains a non-verified element")
            if any(
                value is None
                for value in (
                    self.canonical_basis_name,
                    self.catalog_key,
                    self.inspection_status,
                    self.inspection_receipt_sha256,
                    self.definition_sha256,
                    self.catalog_artifact_sha256,
                    self.catalog_content_sha256,
                    self.source_version,
                    self.catalog_source_version,
                )
            ) or (
                self.source_package != "basis_set_exchange"
                or self.source_version_matches_catalog is not True
                or self.source_version != self.catalog_source_version
                or self.error_class is not None
                or self.evidence_scope != "bse_local_element_definition_only"
                or "basis.request.exact_local_bse_evidence"
                not in self.reason_rule_ids
            ):
                raise ValueError("verified receipt requires authoritative local BSE evidence")
            if self.request.role is BasisEvidenceRole.ECP:
                if any(
                    value.covered is not True
                    or value.ecp_present is not True
                    or not value.ecp_potential_count
                    or not value.ecp_electrons
                    for value in self.elements
                ):
                    raise ValueError("verified ECP evidence lacks an observed potential")
            else:
                if self.catalog_role != self.request.role.value:
                    raise ValueError("verified evidence has the wrong catalog role")
                if any(
                    value.covered is not True
                    or value.orbital_present is not True
                    or not value.electron_shell_count
                    for value in self.elements
                ):
                    raise ValueError("verified orbital evidence lacks observed functions")
        elif self.state is BasisEvidenceState.NOT_APPLICABLE:
            if any(
                value is not BasisEvidenceState.NOT_APPLICABLE for value in states
            ):
                raise ValueError("not-applicable receipt has mixed element states")
            if self.evidence_scope == "bse_local_element_definition_only" and (
                self.request.role is not BasisEvidenceRole.ECP
                or any(
                    value.covered is not True
                    or value.ecp_present is not False
                    or value.ecp_electrons is not None
                    for value in self.elements
                )
            ):
                raise ValueError("local BSE not-applicable evidence must be ECP absence")
        elif self.state is BasisEvidenceState.UNKNOWN:
            if BasisEvidenceState.UNKNOWN not in states:
                raise ValueError("unknown receipt requires unknown element evidence")
        elif self.state is BasisEvidenceState.CONFLICT:
            if not any(
                rule.endswith("conflict") for rule in self.reason_rule_ids
            ) and BasisEvidenceState.CONFLICT not in states:
                raise ValueError("conflict receipt requires an explicit conflict")
        if self.evidence_scope == "typed_program_not_applicable":
            if (
                self.request.program is not BasisEvidenceProgram.XTB
                or self.state is not BasisEvidenceState.NOT_APPLICABLE
                or self.inspection_receipt_sha256 is not None
                or any(
                    value is not None
                    for value in (
                        self.canonical_basis_name,
                        self.canonical_basis_identity,
                        self.catalog_key,
                        self.catalog_role,
                        self.inspection_status,
                        self.definition_sha256,
                        self.catalog_artifact_sha256,
                        self.catalog_content_sha256,
                        self.source_package,
                        self.source_version,
                        self.catalog_source_version,
                        self.source_version_matches_catalog,
                        self.error_class,
                    )
                )
                or self.function_types
            ):
                raise ValueError("typed not-applicable evidence is inconsistent")
        elif self.request.program is BasisEvidenceProgram.XTB:
            raise ValueError("xTB cannot claim local BSE element evidence")
        if self.receipt_sha256 != basis_evidence_receipt_sha256(self):
            raise ValueError("request-bound basis evidence receipt digest mismatch")
        if not _SOURCE_REPLAY_ACTIVE.get():
            token = _SOURCE_REPLAY_ACTIVE.set(True)
            try:
                replayed = inspect_request_bound_basis_evidence_v1(self.request)
            finally:
                _SOURCE_REPLAY_ACTIVE.reset(token)
            if replayed != self:
                raise ValueError(
                    "basis evidence is not the current pinned local BSE observation"
                )
        return self

    def evidence_ref(self) -> "RequestBoundBasisEvidenceRefV1":
        body: dict[str, Any] = {
            "schema_version": BASIS_EVIDENCE_REF_SCHEMA_VERSION,
            "evidence_id": f"basis-evidence:{self.request.request_id}",
            "kind": "request_bound_basis_evidence",
            "receipt_id": self.receipt_id,
            "request_sha256": self.request.request_sha256,
            "artifact_sha256": self.receipt_sha256,
            "media_type": "application/json",
            "ref_sha256": "0" * 64,
        }
        body["ref_sha256"] = basis_evidence_ref_sha256(body)
        return RequestBoundBasisEvidenceRefV1.model_validate(body)


class RequestBoundBasisEvidenceRefV1(_Contract):
    """Path-free EvidenceRef for one exact request-bound receipt."""

    schema_version: Literal[BASIS_EVIDENCE_REF_SCHEMA_VERSION] = (
        BASIS_EVIDENCE_REF_SCHEMA_VERSION
    )
    evidence_id: str = Field(pattern=_IDENTIFIER)
    kind: Literal["request_bound_basis_evidence"]
    receipt_id: str = Field(pattern=_IDENTIFIER)
    request_sha256: str = Field(pattern=_SHA256)
    artifact_sha256: str = Field(pattern=_SHA256)
    media_type: Literal["application/json"] = "application/json"
    ref_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _reference_is_content_addressed(self) -> "RequestBoundBasisEvidenceRefV1":
        if self.ref_sha256 != basis_evidence_ref_sha256(self):
            raise ValueError("request-bound basis EvidenceRef digest mismatch")
        return self


def build_request_bound_basis_evidence_request_v1(
    *,
    request_id: str,
    program: BasisEvidenceProgram | str,
    basis_literal: str,
    role: BasisEvidenceRole | str,
    elements: Iterable[int | str],
) -> RequestBoundBasisEvidenceRequestV1:
    body: dict[str, Any] = {
        "schema_version": BASIS_EVIDENCE_REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "program": _program(program),
        "basis_literal": basis_literal,
        "role": _role(role),
        "atomic_numbers": _normalize_basis_elements(elements),
        "request_sha256": "0" * 64,
        "substitution_allowed": False,
        "model_confidence_used": False,
        "network_allowed": False,
    }
    body["request_sha256"] = basis_evidence_request_sha256(body)
    return RequestBoundBasisEvidenceRequestV1.model_validate(body)


def inspect_request_bound_basis_evidence_v1(
    request: RequestBoundBasisEvidenceRequestV1,
) -> RequestBoundBasisEvidenceReceiptV1:
    """Inspect one exact request using only the frozen catalog and local BSE."""

    bound_request = RequestBoundBasisEvidenceRequestV1.model_validate(
        request.model_dump(mode="json")
    )
    if bound_request.program is BasisEvidenceProgram.XTB:
        elements = tuple(
            _unobserved_element(
                atomic_number,
                state=BasisEvidenceState.NOT_APPLICABLE,
                rule_id="basis.request.xtb_basis_not_applicable",
            )
            for atomic_number in bound_request.atomic_numbers
        )
        return _build_receipt(
            request=bound_request,
            state=BasisEvidenceState.NOT_APPLICABLE,
            elements=elements,
            reason_rule_ids=("basis.request.xtb_basis_not_applicable",),
            evidence_scope="typed_program_not_applicable",
            inspection=None,
            catalog_entry=None,
        )

    inspection = inspect_basis_elements(
        bound_request.basis_literal,
        program=bound_request.program.value,
        elements=bound_request.atomic_numbers,
    )
    catalog = load_basis_catalog()
    catalog_entry = (
        catalog.get("basis_sets", {}).get(inspection.catalog_key)
        if inspection.catalog_key is not None
        else None
    )
    if not isinstance(catalog_entry, Mapping):
        catalog_entry = None

    unknown_statuses = {
        "bse_data_unavailable",
        "catalog_unavailable",
        "catalog_non_authoritative",
        "source_version_mismatch",
    }
    if inspection.status in unknown_statuses:
        rule = "basis.request.local_bse_data_unknown"
        return _build_receipt(
            request=bound_request,
            state=BasisEvidenceState.UNKNOWN,
            elements=tuple(
                _unobserved_element(
                    atomic_number,
                    state=BasisEvidenceState.UNKNOWN,
                    rule_id=rule,
                )
                for atomic_number in bound_request.atomic_numbers
            ),
            reason_rule_ids=(rule,),
            evidence_scope="bse_local_element_definition_only",
            inspection=inspection,
            catalog_entry=catalog_entry,
        )

    if inspection.status == "basis_unresolved":
        known_program_conflict = bool(
            inspection.canonical_name is not None
            and inspection.catalog_key is not None
        )
        state = (
            BasisEvidenceState.CONFLICT
            if known_program_conflict
            else BasisEvidenceState.UNKNOWN
        )
        rule = (
            "basis.request.program_conflict"
            if known_program_conflict
            else "basis.request.basis_unknown"
        )
        return _build_receipt(
            request=bound_request,
            state=state,
            elements=tuple(
                _unobserved_element(
                    atomic_number,
                    state=state,
                    rule_id=rule,
                )
                for atomic_number in bound_request.atomic_numbers
            ),
            reason_rule_ids=(rule,),
            evidence_scope="bse_local_element_definition_only",
            inspection=inspection,
            catalog_entry=catalog_entry,
        )

    observations = {value.atomic_number: value for value in inspection.elements}
    if bound_request.role is BasisEvidenceRole.ECP:
        elements = tuple(
            _ecp_element_evidence(observations[atomic_number])
            for atomic_number in bound_request.atomic_numbers
        )
        if inspection.ecp_definition_coherent is False:
            state = BasisEvidenceState.CONFLICT
            rule_ids = ("basis.request.ecp_definition_conflict",)
        elif any(
            value.state is BasisEvidenceState.CONFLICT for value in elements
        ):
            state = BasisEvidenceState.CONFLICT
            rule_ids = ("basis.request.element_coverage_conflict",)
        elif all(
            value.state is BasisEvidenceState.VERIFIED for value in elements
        ):
            state = BasisEvidenceState.VERIFIED
            rule_ids = ("basis.request.exact_local_bse_evidence",)
        elif all(
            value.state is BasisEvidenceState.NOT_APPLICABLE for value in elements
        ):
            state = BasisEvidenceState.NOT_APPLICABLE
            rule_ids = ("basis.request.ecp_definition_not_applicable",)
        else:
            state = BasisEvidenceState.CONFLICT
            rule_ids = ("basis.request.ecp_role_conflict",)
    else:
        catalog_role = str(catalog_entry.get("role")) if catalog_entry else None
        if catalog_role != bound_request.role.value:
            state = BasisEvidenceState.CONFLICT
            rule_ids = ("basis.request.role_conflict",)
            elements = tuple(
                _observed_element(
                    observations[atomic_number],
                    state=BasisEvidenceState.CONFLICT,
                    rule_id="basis.request.role_conflict",
                )
                for atomic_number in bound_request.atomic_numbers
            )
        else:
            elements = tuple(
                _orbital_element_evidence(observations[atomic_number])
                for atomic_number in bound_request.atomic_numbers
            )
            if all(
                value.state is BasisEvidenceState.VERIFIED for value in elements
            ):
                state = BasisEvidenceState.VERIFIED
                rule_ids = ("basis.request.exact_local_bse_evidence",)
            elif any(not value.covered for value in elements):
                state = BasisEvidenceState.CONFLICT
                rule_ids = ("basis.request.element_coverage_conflict",)
            else:
                state = BasisEvidenceState.CONFLICT
                rule_ids = ("basis.request.orbital_function_conflict",)

    return _build_receipt(
        request=bound_request,
        state=state,
        elements=elements,
        reason_rule_ids=rule_ids,
        evidence_scope="bse_local_element_definition_only",
        inspection=inspection,
        catalog_entry=catalog_entry,
    )


def _build_receipt(
    *,
    request: RequestBoundBasisEvidenceRequestV1,
    state: BasisEvidenceState,
    elements: tuple[RequestBoundBasisElementEvidenceV1, ...],
    reason_rule_ids: tuple[str, ...],
    evidence_scope: Literal[
        "bse_local_element_definition_only",
        "typed_program_not_applicable",
    ],
    inspection: BasisElementInspectionResult | None,
    catalog_entry: Mapping[str, Any] | None,
) -> RequestBoundBasisEvidenceReceiptV1:
    canonical_name = inspection.canonical_name if inspection else None
    function_types = tuple(
        sorted(set(map(str, catalog_entry.get("function_types", ()))))
    ) if catalog_entry else ()
    body: dict[str, Any] = {
        "schema_version": BASIS_EVIDENCE_RECEIPT_SCHEMA_VERSION,
        "receipt_id": f"basis-evidence-receipt:{request.request_id}",
        "request": request.model_dump(mode="json"),
        "state": state,
        "requested_basis_identity": normalize_basis_identity(
            request.basis_literal
        ),
        "canonical_basis_name": canonical_name,
        "canonical_basis_identity": (
            normalize_basis_identity(canonical_name)
            if canonical_name is not None
            else None
        ),
        "catalog_key": inspection.catalog_key if inspection else None,
        "catalog_role": (
            str(catalog_entry.get("role")) if catalog_entry else None
        ),
        "function_types": function_types,
        "elements": tuple(value.model_dump(mode="json") for value in elements),
        "inspection_status": inspection.status if inspection else None,
        "inspection_receipt_sha256": (
            inspection.receipt_sha256 if inspection else None
        ),
        "definition_sha256": inspection.definition_sha256 if inspection else None,
        "catalog_artifact_sha256": (
            inspection.catalog_artifact_sha256 if inspection else None
        ),
        "catalog_content_sha256": (
            inspection.catalog_content_sha256 if inspection else None
        ),
        "source_package": inspection.source_package if inspection else None,
        "source_version": inspection.source_version if inspection else None,
        "catalog_source_version": (
            inspection.catalog_source_version if inspection else None
        ),
        "source_version_matches_catalog": (
            inspection.source_version_matches_catalog if inspection else None
        ),
        "error_class": inspection.error_class if inspection else None,
        "reason_rule_ids": tuple(sorted(set(reason_rule_ids))),
        "evidence_scope": evidence_scope,
        "substitution_performed": False,
        "model_confidence_used": False,
        "local_data_only": True,
        "network_accessed": False,
        "native_engine_verified": False,
        "safe_preview_executed": False,
        "engine_executed": False,
        "scientific_suitability_verified": False,
        "receipt_sha256": "0" * 64,
    }
    body["receipt_sha256"] = basis_evidence_receipt_sha256(body)
    return RequestBoundBasisEvidenceReceiptV1.model_validate(body)


def _orbital_element_evidence(
    observation: Any,
) -> RequestBoundBasisElementEvidenceV1:
    if not observation.covered:
        state = BasisEvidenceState.CONFLICT
        rule = "basis.request.element_coverage_conflict"
    elif _ecp_observation_is_inconsistent(observation):
        state = BasisEvidenceState.CONFLICT
        rule = "basis.request.ecp_definition_conflict"
    elif observation.orbital_present:
        state = BasisEvidenceState.VERIFIED
        rule = "basis.request.orbital_functions_observed"
    else:
        state = BasisEvidenceState.CONFLICT
        rule = "basis.request.orbital_function_conflict"
    return _observed_element(observation, state=state, rule_id=rule)


def _ecp_element_evidence(
    observation: Any,
) -> RequestBoundBasisElementEvidenceV1:
    if not observation.covered:
        state = BasisEvidenceState.CONFLICT
        rule = "basis.request.element_coverage_conflict"
    elif _ecp_observation_is_inconsistent(observation):
        state = BasisEvidenceState.CONFLICT
        rule = "basis.request.ecp_definition_conflict"
    elif observation.ecp_present:
        state = BasisEvidenceState.VERIFIED
        rule = "basis.request.ecp_definition_observed"
    else:
        state = BasisEvidenceState.NOT_APPLICABLE
        rule = "basis.request.ecp_definition_not_applicable"
    return _observed_element(observation, state=state, rule_id=rule)


def _ecp_observation_is_inconsistent(observation: Any) -> bool:
    return bool(observation.ecp_present) != bool(
        observation.ecp_electrons is not None
        and observation.ecp_electrons > 0
    )


def _observed_element(
    observation: Any,
    *,
    state: BasisEvidenceState,
    rule_id: str,
) -> RequestBoundBasisElementEvidenceV1:
    return RequestBoundBasisElementEvidenceV1(
        atomic_number=observation.atomic_number,
        symbol=observation.symbol,
        covered=observation.covered,
        orbital_present=observation.orbital_present,
        electron_shell_count=observation.electron_shell_count,
        ecp_present=observation.ecp_present,
        ecp_potential_count=observation.ecp_potential_count,
        ecp_electrons=observation.ecp_electrons,
        state=state,
        reason_rule_ids=(rule_id,),
    )


def _unobserved_element(
    atomic_number: int,
    *,
    state: BasisEvidenceState,
    rule_id: str,
) -> RequestBoundBasisElementEvidenceV1:
    return RequestBoundBasisElementEvidenceV1(
        atomic_number=atomic_number,
        symbol=_element_symbol(atomic_number),
        covered=None,
        orbital_present=None,
        electron_shell_count=None,
        ecp_present=None,
        ecp_potential_count=None,
        ecp_electrons=None,
        state=state,
        reason_rule_ids=(rule_id,),
    )


def _program(value: BasisEvidenceProgram | str) -> BasisEvidenceProgram:
    if isinstance(value, BasisEvidenceProgram):
        return value
    return BasisEvidenceProgram(str(value).strip().casefold())


def _role(value: BasisEvidenceRole | str) -> BasisEvidenceRole:
    if isinstance(value, BasisEvidenceRole):
        return value
    return BasisEvidenceRole(str(value).strip().casefold())


def _canonical_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    if values != tuple(sorted(set(values))):
        raise ValueError("basis evidence rule IDs must be unique and sorted")
    if any(re.fullmatch(_RULE_ID, value) is None for value in values):
        raise ValueError("basis evidence rule ID is invalid")
    return values


def _identity_sha256(value: BaseModel | Mapping[str, Any], field: str) -> str:
    if isinstance(value, BaseModel):
        body = value.model_dump(mode="json")
    else:
        body = dict(value)
    body[field] = "0" * 64
    encoded = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def basis_evidence_request_sha256(
    value: RequestBoundBasisEvidenceRequestV1 | Mapping[str, Any],
) -> str:
    return _identity_sha256(value, "request_sha256")


def basis_evidence_receipt_sha256(
    value: RequestBoundBasisEvidenceReceiptV1 | Mapping[str, Any],
) -> str:
    return _identity_sha256(value, "receipt_sha256")


def basis_evidence_ref_sha256(
    value: RequestBoundBasisEvidenceRefV1 | Mapping[str, Any],
) -> str:
    return _identity_sha256(value, "ref_sha256")


__all__ = [
    "BASIS_EVIDENCE_RECEIPT_SCHEMA_VERSION",
    "BASIS_EVIDENCE_REF_SCHEMA_VERSION",
    "BASIS_EVIDENCE_REQUEST_SCHEMA_VERSION",
    "BasisEvidenceProgram",
    "BasisEvidenceRole",
    "BasisEvidenceState",
    "RequestBoundBasisElementEvidenceV1",
    "RequestBoundBasisEvidenceReceiptV1",
    "RequestBoundBasisEvidenceRefV1",
    "RequestBoundBasisEvidenceRequestV1",
    "basis_evidence_receipt_sha256",
    "basis_evidence_ref_sha256",
    "basis_evidence_request_sha256",
    "build_request_bound_basis_evidence_request_v1",
    "inspect_request_bound_basis_evidence_v1",
]
