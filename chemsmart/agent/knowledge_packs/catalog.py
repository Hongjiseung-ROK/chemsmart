"""Deterministic catalog and router for evidence-bound knowledge packs."""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from chemsmart.agent.domain_knowledge import (
    DomainKnowledgePack,
    EngineScope,
    KnowledgeAuthorityCeilingV1,
    KnowledgeProgram,
    ScientificDomain,
    domain_knowledge_pack_sha256,
)


KNOWLEDGE_PACK_REGISTRATION_SCHEMA_VERSION = (
    "chemsmart.domain-knowledge-pack-registration.v1"
)
DOMAIN_KNOWLEDGE_CATALOG_SCHEMA_VERSION = (
    "chemsmart.domain-knowledge-catalog.v1"
)
KNOWLEDGE_PACK_ACTIVATION_REQUEST_SCHEMA_VERSION = (
    "chemsmart.knowledge-pack-activation-request.v1"
)
KNOWLEDGE_PACK_ACTIVATION_RECEIPT_SCHEMA_VERSION = (
    "chemsmart.knowledge-pack-activation-receipt.v1"
)

EXCLUDE_DOMAIN_MISMATCH = "knowledge.catalog.exclude.domain_mismatch"
EXCLUDE_PROGRAM_MISMATCH = "knowledge.catalog.exclude.program_mismatch"
EXCLUDE_VERSION_MISMATCH = "knowledge.catalog.exclude.version_mismatch"
EXCLUDE_POSITIVE_TRIGGER_MISSING = (
    "knowledge.catalog.exclude.positive_trigger_not_matched"
)
EXCLUDE_NEGATIVE_TRIGGER_MATCHED = (
    "knowledge.catalog.exclude.negative_trigger_matched"
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_RULE_ID = r"^knowledge\.[a-z0-9_.-]+$"
_TASK_KIND = r"^[a-z][a-z0-9_.-]{0,127}$"
_SHA256 = r"^[0-9a-f]{64}$"
_PACK_VERSION = (
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z.-]+)?$"
)
_ENGINE_VERSION = r"^(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*)){0,2}$"
_ADDITIVE_IDENTITY_NEUTRAL_FIELDS = frozenset({"authority_ceiling"})
_CONSTRAINT_CLAUSE = re.compile(
    r"^(>=|<=|==|!=|>|<|=)?"
    r"((?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){0,2})$"
)


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class KnowledgePackTriggerV1(_Contract):
    """Explicit alternative trigger over domain, engine, version, and task."""

    trigger_id: str = Field(pattern=_RULE_ID)
    domains: tuple[ScientificDomain, ...] = Field(min_length=1)
    engine_scopes: tuple[EngineScope, ...] = Field(min_length=1)
    task_kinds: tuple[str, ...] = Field(min_length=1)

    @field_validator("domains")
    @classmethod
    def _canonical_domains(
        cls, value: tuple[ScientificDomain, ...]
    ) -> tuple[ScientificDomain, ...]:
        if len(value) != len(set(value)):
            raise ValueError("trigger domains must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @field_validator("engine_scopes")
    @classmethod
    def _canonical_scopes(
        cls, value: tuple[EngineScope, ...]
    ) -> tuple[EngineScope, ...]:
        if len(value) != len(set(value)):
            raise ValueError("trigger engine scopes must be unique")
        for scope in value:
            _parse_constraint(scope.version_constraint)
        return tuple(
            sorted(
                value,
                key=lambda item: (
                    item.program.value,
                    item.version_constraint,
                ),
            )
        )

    @field_validator("task_kinds")
    @classmethod
    def _canonical_tasks(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("trigger task kinds must be unique")
        if any(re.fullmatch(_TASK_KIND, item) is None for item in value):
            raise ValueError("trigger task kind is invalid")
        return tuple(sorted(value))


class KnowledgePackRegistrationV1(_Contract):
    """One immutable pack plus explicit positive and negative routing rules."""

    schema_version: Literal[KNOWLEDGE_PACK_REGISTRATION_SCHEMA_VERSION] = (
        KNOWLEDGE_PACK_REGISTRATION_SCHEMA_VERSION
    )
    registration_sha256: str = Field(pattern=_SHA256)
    pack: DomainKnowledgePack
    pack_sha256: str = Field(pattern=_SHA256)
    positive_triggers: tuple[KnowledgePackTriggerV1, ...] = Field(
        min_length=1
    )
    negative_triggers: tuple[KnowledgePackTriggerV1, ...] = ()
    source_ledger_state: Literal["verified"] = "verified"
    model_visible_read_only: Literal[True] = True
    authority_ceiling: KnowledgeAuthorityCeilingV1 = Field(
        default_factory=KnowledgeAuthorityCeilingV1
    )
    can_approve: Literal[False] = False
    can_repair: Literal[False] = False
    can_execute: Literal[False] = False
    can_fill_missing_paper_facts: Literal[False] = False
    can_author_native_input: Literal[False] = False

    @field_validator("positive_triggers", "negative_triggers")
    @classmethod
    def _canonical_triggers(
        cls, value: tuple[KnowledgePackTriggerV1, ...]
    ) -> tuple[KnowledgePackTriggerV1, ...]:
        ids = tuple(item.trigger_id for item in value)
        if len(ids) != len(set(ids)):
            raise ValueError("knowledge-pack trigger IDs must be unique")
        return tuple(sorted(value, key=lambda item: item.trigger_id))

    @model_validator(mode="after")
    def _registration_is_closed(self) -> "KnowledgePackRegistrationV1":
        expected_pack_sha256 = domain_knowledge_pack_sha256(self.pack)
        if self.pack_sha256 != expected_pack_sha256:
            raise ValueError("registered knowledge-pack digest mismatch")
        all_trigger_ids = tuple(
            item.trigger_id
            for item in self.positive_triggers + self.negative_triggers
        )
        if len(all_trigger_ids) != len(set(all_trigger_ids)):
            raise ValueError("positive and negative trigger IDs must be unique")
        pack_domains = set(self.pack.domains)
        pack_scopes = set(self.pack.engine_scopes)
        for scope in self.pack.engine_scopes:
            _parse_constraint(scope.version_constraint)
        for trigger in self.positive_triggers + self.negative_triggers:
            if not set(trigger.domains).issubset(pack_domains):
                raise ValueError("trigger domain exceeds knowledge-pack scope")
            if not set(trigger.engine_scopes).issubset(pack_scopes):
                raise ValueError("trigger engine exceeds knowledge-pack scope")
        if self.registration_sha256 != _content_sha256(
            self, "registration_sha256"
        ):
            raise ValueError("knowledge-pack registration digest mismatch")
        return self


class DomainKnowledgeCatalogV1(_Contract):
    """A content-addressed catalog; an empty catalog is a valid K0 state."""

    schema_version: Literal[DOMAIN_KNOWLEDGE_CATALOG_SCHEMA_VERSION] = (
        DOMAIN_KNOWLEDGE_CATALOG_SCHEMA_VERSION
    )
    catalog_id: str = Field(pattern=_IDENTIFIER)
    catalog_sha256: str = Field(pattern=_SHA256)
    source_audit_manifest_sha256: str = Field(pattern=_SHA256)
    scientific_source_ledger_sha256: str = Field(pattern=_SHA256)
    registrations: tuple[KnowledgePackRegistrationV1, ...] = ()

    @field_validator("registrations")
    @classmethod
    def _canonical_registrations(
        cls, value: tuple[KnowledgePackRegistrationV1, ...]
    ) -> tuple[KnowledgePackRegistrationV1, ...]:
        pack_ids = tuple(item.pack.pack_id for item in value)
        if len(pack_ids) != len(set(pack_ids)):
            raise ValueError("catalog pack IDs must be unique")
        return tuple(
            sorted(
                value,
                key=lambda item: (item.pack.pack_id, item.pack.version),
            )
        )

    @model_validator(mode="after")
    def _catalog_is_content_addressed(self) -> "DomainKnowledgeCatalogV1":
        if self.catalog_sha256 != _content_sha256(self, "catalog_sha256"):
            raise ValueError("domain-knowledge catalog digest mismatch")
        return self


class KnowledgePackActivationRequestV1(_Contract):
    """Content-addressed routing input owned by the host coordinator."""

    schema_version: Literal[
        KNOWLEDGE_PACK_ACTIVATION_REQUEST_SCHEMA_VERSION
    ] = KNOWLEDGE_PACK_ACTIVATION_REQUEST_SCHEMA_VERSION
    request_sha256: str = Field(pattern=_SHA256)
    request_id: str = Field(pattern=_IDENTIFIER)
    domain: ScientificDomain
    program: KnowledgeProgram
    engine_version: str = Field(pattern=_ENGINE_VERSION)
    task_kind: str = Field(pattern=_TASK_KIND)
    input_sha256: str = Field(pattern=_SHA256)
    context_sha256: str = Field(pattern=_SHA256)
    critical_missing_fact_ids: tuple[str, ...] = ()
    model_visible_exposure_requested: bool = False

    @field_validator("critical_missing_fact_ids")
    @classmethod
    def _canonical_missing_facts(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("critical missing-fact IDs must be unique")
        if any(re.fullmatch(_IDENTIFIER, item) is None for item in value):
            raise ValueError("critical missing-fact ID is invalid")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def _request_is_content_addressed(
        self,
    ) -> "KnowledgePackActivationRequestV1":
        _parse_engine_version(self.engine_version)
        if self.request_sha256 != _content_sha256(
            self, "request_sha256"
        ):
            raise ValueError("knowledge-pack activation request digest mismatch")
        return self


class SelectedKnowledgePackRefV1(_Contract):
    pack_id: str = Field(pattern=_IDENTIFIER)
    version: str = Field(pattern=_PACK_VERSION)
    pack_sha256: str = Field(pattern=_SHA256)


class KnowledgePackConsiderationV1(_Contract):
    """Observable deterministic decision for one catalog entry."""

    pack_id: str = Field(pattern=_IDENTIFIER)
    version: str = Field(pattern=_PACK_VERSION)
    pack_sha256: str = Field(pattern=_SHA256)
    selected: bool
    matched_positive_trigger_ids: tuple[str, ...] = ()
    matched_negative_trigger_ids: tuple[str, ...] = ()
    exclusion_rule_ids: tuple[str, ...] = ()

    @field_validator(
        "matched_positive_trigger_ids",
        "matched_negative_trigger_ids",
        "exclusion_rule_ids",
    )
    @classmethod
    def _canonical_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("consideration rule IDs must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def _selection_matches_exclusions(self) -> "KnowledgePackConsiderationV1":
        if self.selected == bool(self.exclusion_rule_ids):
            raise ValueError("selected pack must have exactly zero exclusions")
        if self.selected and not self.matched_positive_trigger_ids:
            raise ValueError("selected pack requires a positive trigger")
        return self


class KnowledgePackSelectionStatus(str, Enum):
    CATALOG_EMPTY = "catalog_empty"
    NO_MATCH = "no_match"
    SELECTED = "selected"


class KnowledgePackActivationReceiptV1(_Contract):
    """Content-addressed selection evidence, never an approval or repair."""

    schema_version: Literal[
        KNOWLEDGE_PACK_ACTIVATION_RECEIPT_SCHEMA_VERSION
    ] = KNOWLEDGE_PACK_ACTIVATION_RECEIPT_SCHEMA_VERSION
    receipt_sha256: str = Field(pattern=_SHA256)
    request_id: str = Field(pattern=_IDENTIFIER)
    request_sha256: str = Field(pattern=_SHA256)
    catalog_id: str = Field(pattern=_IDENTIFIER)
    catalog_sha256: str = Field(pattern=_SHA256)
    source_audit_manifest_sha256: str = Field(pattern=_SHA256)
    scientific_source_ledger_sha256: str = Field(pattern=_SHA256)
    domain: ScientificDomain
    program: KnowledgeProgram
    engine_version: str = Field(pattern=_ENGINE_VERSION)
    task_kind: str = Field(pattern=_TASK_KIND)
    input_sha256: str = Field(pattern=_SHA256)
    context_sha256: str = Field(pattern=_SHA256)
    critical_missing_fact_ids: tuple[str, ...] = ()
    selection_status: KnowledgePackSelectionStatus
    selected_packs: tuple[SelectedKnowledgePackRefV1, ...] = ()
    considered_packs: tuple[KnowledgePackConsiderationV1, ...] = ()
    exclusion_rule_ids: tuple[str, ...] = ()
    model_visible_exposure_requested: bool
    model_visible_exposure: bool
    model_visible_pack_ids: tuple[str, ...] = ()
    read_only: Literal[True] = True
    authority_ceiling: KnowledgeAuthorityCeilingV1 = Field(
        default_factory=KnowledgeAuthorityCeilingV1
    )
    can_approve: Literal[False] = False
    can_repair: Literal[False] = False
    can_execute: Literal[False] = False
    can_fill_missing_paper_facts: Literal[False] = False
    can_author_native_input: Literal[False] = False

    @field_validator(
        "critical_missing_fact_ids",
        "exclusion_rule_ids",
        "model_visible_pack_ids",
    )
    @classmethod
    def _canonical_string_ids(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("activation receipt IDs must be unique")
        return tuple(sorted(value))

    @field_validator("selected_packs")
    @classmethod
    def _canonical_selected(
        cls, value: tuple[SelectedKnowledgePackRefV1, ...]
    ) -> tuple[SelectedKnowledgePackRefV1, ...]:
        ids = tuple(item.pack_id for item in value)
        if len(ids) != len(set(ids)):
            raise ValueError("selected knowledge-pack IDs must be unique")
        return tuple(sorted(value, key=lambda item: item.pack_id))

    @field_validator("considered_packs")
    @classmethod
    def _canonical_considered(
        cls, value: tuple[KnowledgePackConsiderationV1, ...]
    ) -> tuple[KnowledgePackConsiderationV1, ...]:
        ids = tuple(item.pack_id for item in value)
        if len(ids) != len(set(ids)):
            raise ValueError("considered knowledge-pack IDs must be unique")
        return tuple(sorted(value, key=lambda item: item.pack_id))

    @model_validator(mode="after")
    def _receipt_is_closed(self) -> "KnowledgePackActivationReceiptV1":
        selected_ids = tuple(item.pack_id for item in self.selected_packs)
        considered_selected = tuple(
            item.pack_id for item in self.considered_packs if item.selected
        )
        if selected_ids != considered_selected:
            raise ValueError("selected pack refs differ from considerations")
        aggregate_exclusions = tuple(
            sorted(
                {
                    rule_id
                    for item in self.considered_packs
                    for rule_id in item.exclusion_rule_ids
                }
            )
        )
        if self.exclusion_rule_ids != aggregate_exclusions:
            raise ValueError("activation exclusion-rule aggregate mismatch")
        expected_status = (
            KnowledgePackSelectionStatus.CATALOG_EMPTY
            if not self.considered_packs
            else (
                KnowledgePackSelectionStatus.SELECTED
                if self.selected_packs
                else KnowledgePackSelectionStatus.NO_MATCH
            )
        )
        if self.selection_status is not expected_status:
            raise ValueError("activation selection status is inconsistent")
        expected_model_ids = (
            selected_ids if self.model_visible_exposure_requested else ()
        )
        if self.model_visible_pack_ids != expected_model_ids:
            raise ValueError("model-visible pack IDs are inconsistent")
        if self.model_visible_exposure != bool(expected_model_ids):
            raise ValueError("model-visible exposure state is inconsistent")
        if self.receipt_sha256 != _content_sha256(
            self, "receipt_sha256"
        ):
            raise ValueError("knowledge-pack activation receipt digest mismatch")
        return self


def build_knowledge_pack_trigger_v1(
    *,
    trigger_id: str,
    domains: Sequence[ScientificDomain],
    engine_scopes: Sequence[EngineScope],
    task_kinds: Sequence[str],
) -> KnowledgePackTriggerV1:
    return KnowledgePackTriggerV1(
        trigger_id=trigger_id,
        domains=tuple(domains),
        engine_scopes=tuple(engine_scopes),
        task_kinds=tuple(task_kinds),
    )


def build_knowledge_pack_registration_v1(
    *,
    pack: DomainKnowledgePack,
    positive_triggers: Sequence[KnowledgePackTriggerV1],
    negative_triggers: Sequence[KnowledgePackTriggerV1] = (),
) -> KnowledgePackRegistrationV1:
    body = {
        "schema_version": KNOWLEDGE_PACK_REGISTRATION_SCHEMA_VERSION,
        "pack": pack,
        "pack_sha256": domain_knowledge_pack_sha256(pack),
        "positive_triggers": tuple(
            sorted(positive_triggers, key=lambda item: item.trigger_id)
        ),
        "negative_triggers": tuple(
            sorted(negative_triggers, key=lambda item: item.trigger_id)
        ),
        "source_ledger_state": "verified",
        "model_visible_read_only": True,
        "can_approve": False,
        "can_repair": False,
        "can_execute": False,
        "can_fill_missing_paper_facts": False,
        "can_author_native_input": False,
    }
    return KnowledgePackRegistrationV1.model_validate(
        {**body, "registration_sha256": _sha256_json(body)}
    )


def build_domain_knowledge_catalog_v1(
    *,
    catalog_id: str,
    source_audit_manifest_sha256: str,
    scientific_source_ledger_sha256: str,
    registrations: Sequence[KnowledgePackRegistrationV1] = (),
) -> DomainKnowledgeCatalogV1:
    body = {
        "schema_version": DOMAIN_KNOWLEDGE_CATALOG_SCHEMA_VERSION,
        "catalog_id": catalog_id,
        "source_audit_manifest_sha256": source_audit_manifest_sha256,
        "scientific_source_ledger_sha256": scientific_source_ledger_sha256,
        "registrations": tuple(
            sorted(
                registrations,
                key=lambda item: (item.pack.pack_id, item.pack.version),
            )
        ),
    }
    return DomainKnowledgeCatalogV1.model_validate(
        {**body, "catalog_sha256": _sha256_json(body)}
    )


def build_knowledge_pack_activation_request_v1(
    **values: Any,
) -> KnowledgePackActivationRequestV1:
    body = {
        "schema_version": KNOWLEDGE_PACK_ACTIVATION_REQUEST_SCHEMA_VERSION,
        **values,
    }
    body.pop("request_sha256", None)
    body.setdefault("critical_missing_fact_ids", ())
    body.setdefault("model_visible_exposure_requested", False)
    body["critical_missing_fact_ids"] = tuple(
        sorted(body["critical_missing_fact_ids"])
    )
    return KnowledgePackActivationRequestV1.model_validate(
        {**body, "request_sha256": _sha256_json(body)}
    )


def activate_domain_knowledge(
    catalog: DomainKnowledgeCatalogV1,
    request: KnowledgePackActivationRequestV1,
) -> KnowledgePackActivationReceiptV1:
    """Select packs deterministically and emit only observable decisions."""

    catalog = DomainKnowledgeCatalogV1.model_validate(
        catalog.model_dump(mode="python")
    )
    request = KnowledgePackActivationRequestV1.model_validate(
        request.model_dump(mode="python")
    )
    version = _parse_engine_version(request.engine_version)
    considerations: list[KnowledgePackConsiderationV1] = []
    selected: list[SelectedKnowledgePackRefV1] = []

    for registration in catalog.registrations:
        pack = registration.pack
        exclusions: set[str] = set()
        domain_matches = request.domain in pack.domains
        program_scopes = tuple(
            scope
            for scope in pack.engine_scopes
            if scope.program is request.program
        )
        version_matches = any(
            _constraint_matches(version, scope.version_constraint)
            for scope in program_scopes
        )
        if not domain_matches:
            exclusions.add(EXCLUDE_DOMAIN_MISMATCH)
        if not program_scopes:
            exclusions.add(EXCLUDE_PROGRAM_MISMATCH)
        elif not version_matches:
            exclusions.add(EXCLUDE_VERSION_MISMATCH)

        positive_ids: tuple[str, ...] = ()
        negative_ids: tuple[str, ...] = ()
        if domain_matches and program_scopes and version_matches:
            positive_ids = tuple(
                trigger.trigger_id
                for trigger in registration.positive_triggers
                if _trigger_matches(trigger, request, version)
            )
            if not positive_ids:
                exclusions.add(EXCLUDE_POSITIVE_TRIGGER_MISSING)
            else:
                negative_ids = tuple(
                    trigger.trigger_id
                    for trigger in registration.negative_triggers
                    if _trigger_matches(trigger, request, version)
                )
                if negative_ids:
                    exclusions.add(EXCLUDE_NEGATIVE_TRIGGER_MATCHED)

        is_selected = not exclusions
        consideration = KnowledgePackConsiderationV1(
            pack_id=pack.pack_id,
            version=pack.version,
            pack_sha256=registration.pack_sha256,
            selected=is_selected,
            matched_positive_trigger_ids=positive_ids,
            matched_negative_trigger_ids=negative_ids,
            exclusion_rule_ids=tuple(exclusions),
        )
        considerations.append(consideration)
        if is_selected:
            selected.append(
                SelectedKnowledgePackRefV1(
                    pack_id=pack.pack_id,
                    version=pack.version,
                    pack_sha256=registration.pack_sha256,
                )
            )

    considerations_tuple = tuple(
        sorted(considerations, key=lambda item: item.pack_id)
    )
    selected_tuple = tuple(sorted(selected, key=lambda item: item.pack_id))
    exclusion_ids = tuple(
        sorted(
            {
                rule_id
                for item in considerations_tuple
                for rule_id in item.exclusion_rule_ids
            }
        )
    )
    model_visible_ids = (
        tuple(item.pack_id for item in selected_tuple)
        if request.model_visible_exposure_requested
        else ()
    )
    status = (
        KnowledgePackSelectionStatus.CATALOG_EMPTY
        if not considerations_tuple
        else (
            KnowledgePackSelectionStatus.SELECTED
            if selected_tuple
            else KnowledgePackSelectionStatus.NO_MATCH
        )
    )
    body = {
        "schema_version": KNOWLEDGE_PACK_ACTIVATION_RECEIPT_SCHEMA_VERSION,
        "request_id": request.request_id,
        "request_sha256": request.request_sha256,
        "catalog_id": catalog.catalog_id,
        "catalog_sha256": catalog.catalog_sha256,
        "source_audit_manifest_sha256": (
            catalog.source_audit_manifest_sha256
        ),
        "scientific_source_ledger_sha256": (
            catalog.scientific_source_ledger_sha256
        ),
        "domain": request.domain,
        "program": request.program,
        "engine_version": request.engine_version,
        "task_kind": request.task_kind,
        "input_sha256": request.input_sha256,
        "context_sha256": request.context_sha256,
        "critical_missing_fact_ids": request.critical_missing_fact_ids,
        "selection_status": status,
        "selected_packs": selected_tuple,
        "considered_packs": considerations_tuple,
        "exclusion_rule_ids": exclusion_ids,
        "model_visible_exposure_requested": (
            request.model_visible_exposure_requested
        ),
        "model_visible_exposure": bool(model_visible_ids),
        "model_visible_pack_ids": model_visible_ids,
        "read_only": True,
        "can_approve": False,
        "can_repair": False,
        "can_execute": False,
        "can_fill_missing_paper_facts": False,
        "can_author_native_input": False,
    }
    return KnowledgePackActivationReceiptV1.model_validate(
        {**body, "receipt_sha256": _sha256_json(body)}
    )


def resolve_activation_packs(
    catalog: DomainKnowledgeCatalogV1,
    receipt: KnowledgePackActivationReceiptV1,
    *,
    for_model: bool,
) -> tuple[DomainKnowledgePack, ...]:
    """Resolve immutable packs while enforcing the recorded exposure mode."""

    catalog = DomainKnowledgeCatalogV1.model_validate(
        catalog.model_dump(mode="python")
    )
    receipt = KnowledgePackActivationReceiptV1.model_validate(
        receipt.model_dump(mode="python")
    )
    if receipt.catalog_id != catalog.catalog_id:
        raise ValueError("activation receipt targets a different catalog ID")
    if receipt.catalog_sha256 != catalog.catalog_sha256:
        raise ValueError("activation receipt targets a different catalog digest")
    selected_by_id = {item.pack_id: item for item in receipt.selected_packs}
    registrations = {
        item.pack.pack_id: item for item in catalog.registrations
    }
    allowed_ids = (
        set(receipt.model_visible_pack_ids)
        if for_model
        else set(selected_by_id)
    )
    resolved: list[DomainKnowledgePack] = []
    for pack_id in sorted(allowed_ids):
        selected_ref = selected_by_id.get(pack_id)
        registration = registrations.get(pack_id)
        if selected_ref is None or registration is None:
            raise ValueError("activation receipt references an unavailable pack")
        if registration.pack_sha256 != selected_ref.pack_sha256:
            raise ValueError("activation pack digest differs from catalog")
        if registration.pack.version != selected_ref.version:
            raise ValueError("activation pack version differs from catalog")
        resolved.append(registration.pack)
    return tuple(resolved)


def knowledge_pack_registration_sha256(
    registration: KnowledgePackRegistrationV1 | Mapping[str, Any],
) -> str:
    validated = _revalidate(
        KnowledgePackRegistrationV1,
        registration,
    )
    return _content_sha256(validated, "registration_sha256")


def domain_knowledge_catalog_sha256(
    catalog: DomainKnowledgeCatalogV1 | Mapping[str, Any],
) -> str:
    validated = _revalidate(DomainKnowledgeCatalogV1, catalog)
    return _content_sha256(validated, "catalog_sha256")


def knowledge_pack_activation_request_sha256(
    request: KnowledgePackActivationRequestV1 | Mapping[str, Any],
) -> str:
    validated = _revalidate(KnowledgePackActivationRequestV1, request)
    return _content_sha256(validated, "request_sha256")


def knowledge_pack_activation_receipt_sha256(
    receipt: KnowledgePackActivationReceiptV1 | Mapping[str, Any],
) -> str:
    validated = _revalidate(KnowledgePackActivationReceiptV1, receipt)
    return _content_sha256(validated, "receipt_sha256")


class DomainKnowledgeCatalogRouter:
    """Small immutable facade around selection and exposure resolution."""

    def __init__(self, catalog: DomainKnowledgeCatalogV1) -> None:
        self._catalog = DomainKnowledgeCatalogV1.model_validate(
            catalog.model_dump(mode="python")
        )

    @property
    def catalog(self) -> DomainKnowledgeCatalogV1:
        return self._catalog

    def activate(
        self, request: KnowledgePackActivationRequestV1
    ) -> KnowledgePackActivationReceiptV1:
        return activate_domain_knowledge(self._catalog, request)

    def resolve(
        self,
        receipt: KnowledgePackActivationReceiptV1,
        *,
        for_model: bool,
    ) -> tuple[DomainKnowledgePack, ...]:
        return resolve_activation_packs(
            self._catalog,
            receipt,
            for_model=for_model,
        )


def _trigger_matches(
    trigger: KnowledgePackTriggerV1,
    request: KnowledgePackActivationRequestV1,
    version: tuple[int, int, int],
) -> bool:
    return (
        request.domain in trigger.domains
        and request.task_kind in trigger.task_kinds
        and any(
            scope.program is request.program
            and _constraint_matches(version, scope.version_constraint)
            for scope in trigger.engine_scopes
        )
    )


def _parse_engine_version(value: str) -> tuple[int, int, int]:
    if re.fullmatch(_ENGINE_VERSION, value) is None:
        raise ValueError("engine version must contain one to three integers")
    parts = tuple(int(item) for item in value.split("."))
    return parts + (0,) * (3 - len(parts))


def _parse_constraint(
    value: str,
) -> tuple[tuple[str, tuple[int, ...]], ...]:
    stripped = value.strip()
    if stripped == "*":
        return (("*", ()),)
    clauses: list[tuple[str, tuple[int, ...]]] = []
    for raw_clause in stripped.split(","):
        clause = raw_clause.strip()
        if clause.endswith(".*"):
            prefix_text = clause[:-2]
            if re.fullmatch(_ENGINE_VERSION, prefix_text) is None:
                raise ValueError("unsupported engine version constraint")
            prefix = tuple(int(item) for item in prefix_text.split("."))
            if len(prefix) >= 3:
                raise ValueError("engine version wildcard must omit a component")
            clauses.append(("prefix", prefix))
            continue
        match = _CONSTRAINT_CLAUSE.fullmatch(clause)
        if match is None:
            raise ValueError("unsupported engine version constraint")
        operator = match.group(1) or "=="
        clauses.append((operator, _parse_engine_version(match.group(2))))
    if not clauses:
        raise ValueError("engine version constraint cannot be empty")
    return tuple(clauses)


def _constraint_matches(
    version: tuple[int, int, int],
    constraint: str,
) -> bool:
    for operator, expected in _parse_constraint(constraint):
        if operator == "*":
            matched = True
        elif operator == "prefix":
            matched = version[: len(expected)] == expected
        elif operator in {"=", "=="}:
            matched = version == expected
        elif operator == "!=":
            matched = version != expected
        elif operator == ">=":
            matched = version >= expected
        elif operator == "<=":
            matched = version <= expected
        elif operator == ">":
            matched = version > expected
        elif operator == "<":
            matched = version < expected
        else:  # pragma: no cover - parser closes the operator set
            raise ValueError("unsupported engine version operator")
        if not matched:
            return False
    return True


def _content_sha256(
    value: BaseModel | Mapping[str, Any],
    identity_field: str,
) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude={identity_field})
    else:
        payload = {
            key: item
            for key, item in value.items()
            if key != identity_field
        }
    return _sha256_json(payload)


def _revalidate(
    contract_type: type[BaseModel],
    value: BaseModel | Mapping[str, Any],
) -> BaseModel:
    payload = (
        value.model_dump(mode="python")
        if isinstance(value, BaseModel)
        else dict(value)
    )
    return contract_type.model_validate(payload)


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            _jsonable(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return _jsonable(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in value.items()
            if str(key) not in _ADDITIVE_IDENTITY_NEUTRAL_FIELDS
        }
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


__all__ = [
    "DOMAIN_KNOWLEDGE_CATALOG_SCHEMA_VERSION",
    "DomainKnowledgeCatalogRouter",
    "DomainKnowledgeCatalogV1",
    "EXCLUDE_DOMAIN_MISMATCH",
    "EXCLUDE_NEGATIVE_TRIGGER_MATCHED",
    "EXCLUDE_POSITIVE_TRIGGER_MISSING",
    "EXCLUDE_PROGRAM_MISMATCH",
    "EXCLUDE_VERSION_MISMATCH",
    "KNOWLEDGE_PACK_ACTIVATION_RECEIPT_SCHEMA_VERSION",
    "KNOWLEDGE_PACK_ACTIVATION_REQUEST_SCHEMA_VERSION",
    "KNOWLEDGE_PACK_REGISTRATION_SCHEMA_VERSION",
    "KnowledgePackActivationReceiptV1",
    "KnowledgePackActivationRequestV1",
    "KnowledgePackConsiderationV1",
    "KnowledgePackRegistrationV1",
    "KnowledgePackSelectionStatus",
    "KnowledgePackTriggerV1",
    "SelectedKnowledgePackRefV1",
    "activate_domain_knowledge",
    "build_domain_knowledge_catalog_v1",
    "build_knowledge_pack_activation_request_v1",
    "build_knowledge_pack_registration_v1",
    "build_knowledge_pack_trigger_v1",
    "domain_knowledge_catalog_sha256",
    "knowledge_pack_activation_receipt_sha256",
    "knowledge_pack_activation_request_sha256",
    "knowledge_pack_registration_sha256",
    "resolve_activation_packs",
]
