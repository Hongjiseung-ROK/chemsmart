"""Versioned, evidence-bound scientific knowledge-pack contracts.

The models in this module externalize computational-chemistry rules that would
otherwise be hidden in a persona or prompt.  A pack is descriptive until every
referenced deterministic validator is present and the pack is explicitly
selected for a matching domain and engine scope.  It cannot approve, execute,
or repair a calculation.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


DOMAIN_KNOWLEDGE_PACK_SCHEMA_VERSION = "chemsmart.domain-knowledge-pack.v1"

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
_RULE_ID = r"^knowledge\.[a-z0-9_.-]+$"
_SHA256 = r"^[0-9a-f]{64}$"
_SEMVER = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$"
_VERSION_RANGE = r"^[0-9A-Za-z*<>=., +_-]{1,120}$"
_SAFE_TEXT = re.compile(r"^[^\x00-\x1f\x7f]+$")


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class ScientificDomain(str, Enum):
    GENERAL = "general"
    REACTION_MECHANISM = "reaction_mechanism"
    TRANSITION_METAL = "transition_metal"
    EXCITED_STATE = "excited_state"
    CONFORMER_ENSEMBLE = "conformer_ensemble"
    THERMOCHEMISTRY = "thermochemistry"
    MULTISCALE_QMMM = "multiscale_qmmm"


class KnowledgeProgram(str, Enum):
    GAUSSIAN = "gaussian"
    ORCA = "orca"
    XTB = "xtb"


class KnowledgeSourceRef(_Contract):
    """A locator and digest for evidence supporting pack rules."""

    source_id: str = Field(pattern=_IDENTIFIER)
    canonical_identifier: str = Field(min_length=1, max_length=512)
    locator: str = Field(min_length=1, max_length=1024)
    artifact_sha256: str = Field(pattern=_SHA256)
    evidence_class: Literal[
        "peer_reviewed_article",
        "supporting_information",
        "official_manual",
        "open_specification",
        "validated_local_fixture",
    ]

    @field_validator("canonical_identifier", "locator")
    @classmethod
    def _safe_source_text(cls, value: str) -> str:
        if not _SAFE_TEXT.fullmatch(value):
            raise ValueError("knowledge source fields must not contain controls")
        return value


class EngineScope(_Contract):
    program: KnowledgeProgram
    version_constraint: str = Field(pattern=_VERSION_RANGE)


class KnowledgeRule(_Contract):
    """One sourced rule with an external deterministic validator."""

    rule_id: str = Field(pattern=_RULE_ID)
    domains: tuple[ScientificDomain, ...] = Field(min_length=1)
    engine_scopes: tuple[EngineScope, ...] = Field(min_length=1)
    statement: str = Field(min_length=1, max_length=1000)
    allowed_setting_paths: tuple[str, ...] = ()
    prohibited_condition_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = Field(min_length=1)
    validator_ids: tuple[str, ...] = Field(min_length=1)
    severity: Literal["critical", "error", "warning"]

    @field_validator("domains")
    @classmethod
    def _canonical_domains(
        cls, value: tuple[ScientificDomain, ...]
    ) -> tuple[ScientificDomain, ...]:
        if len(value) != len(set(value)):
            raise ValueError("knowledge rule tuple values must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @field_validator("engine_scopes")
    @classmethod
    def _canonical_engine_scopes(
        cls, value: tuple[EngineScope, ...]
    ) -> tuple[EngineScope, ...]:
        if len(value) != len(set(value)):
            raise ValueError("knowledge rule tuple values must be unique")
        return tuple(
            sorted(
                value,
                key=lambda item: (item.program.value, item.version_constraint),
            )
        )

    @field_validator(
        "allowed_setting_paths",
        "prohibited_condition_ids",
        "source_ids",
        "validator_ids",
    )
    @classmethod
    def _canonical_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("knowledge rule tuple values must be unique")
        return tuple(sorted(value))

    @field_validator("statement")
    @classmethod
    def _safe_statement(cls, value: str) -> str:
        if not _SAFE_TEXT.fullmatch(value):
            raise ValueError("knowledge statements must not contain controls")
        return value


class DomainKnowledgePack(_Contract):
    """Content-addressable rule bundle; never an implicit prompt authority."""

    schema_version: Literal[DOMAIN_KNOWLEDGE_PACK_SCHEMA_VERSION] = (
        DOMAIN_KNOWLEDGE_PACK_SCHEMA_VERSION
    )
    pack_id: str = Field(pattern=_IDENTIFIER)
    version: str = Field(pattern=_SEMVER)
    domains: tuple[ScientificDomain, ...] = Field(min_length=1)
    engine_scopes: tuple[EngineScope, ...] = Field(min_length=1)
    sources: tuple[KnowledgeSourceRef, ...] = Field(min_length=1)
    rules: tuple[KnowledgeRule, ...] = Field(min_length=1)
    validator_registry_sha256: str = Field(pattern=_SHA256)
    can_approve: Literal[False] = False
    can_execute: Literal[False] = False
    model_persona_authoritative: Literal[False] = False

    @field_validator("domains")
    @classmethod
    def _canonical_domains(
        cls, value: tuple[ScientificDomain, ...]
    ) -> tuple[ScientificDomain, ...]:
        if len(value) != len(set(value)):
            raise ValueError("pack domains must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @field_validator("engine_scopes")
    @classmethod
    def _canonical_engine_scopes(
        cls, value: tuple[EngineScope, ...]
    ) -> tuple[EngineScope, ...]:
        if len(value) != len(set(value)):
            raise ValueError("pack engine scopes must be unique")
        return tuple(
            sorted(
                value,
                key=lambda item: (item.program.value, item.version_constraint),
            )
        )

    @field_validator("sources")
    @classmethod
    def _canonical_sources(
        cls, value: tuple[KnowledgeSourceRef, ...]
    ) -> tuple[KnowledgeSourceRef, ...]:
        _require_unique((item.source_id for item in value), "source_id")
        return tuple(sorted(value, key=lambda item: item.source_id))

    @field_validator("rules")
    @classmethod
    def _canonical_rules(
        cls, value: tuple[KnowledgeRule, ...]
    ) -> tuple[KnowledgeRule, ...]:
        _require_unique((item.rule_id for item in value), "rule_id")
        return tuple(sorted(value, key=lambda item: item.rule_id))

    @model_validator(mode="after")
    def _references_and_scopes_are_closed(self) -> "DomainKnowledgePack":
        source_ids = {source.source_id for source in self.sources}
        pack_domains = set(self.domains)
        pack_scopes = set(self.engine_scopes)
        for rule in self.rules:
            missing = sorted(set(rule.source_ids).difference(source_ids))
            if missing:
                raise ValueError(
                    "knowledge rule references unknown source_ids: "
                    + ", ".join(missing)
                )
            if not set(rule.domains).issubset(pack_domains):
                raise ValueError("knowledge rule domain exceeds pack scope")
            if not set(rule.engine_scopes).issubset(pack_scopes):
                raise ValueError("knowledge rule engine exceeds pack scope")
        return self


def domain_knowledge_pack_sha256(pack: DomainKnowledgePack) -> str:
    """Return a stable digest over a freshly validated public pack contract.

    Pydantic's ``model_copy(update=...)`` deliberately skips validation.  A
    pack may cross a model or event boundary before it is hashed, so the digest
    function is also a trust boundary and must reject such unchecked copies.
    """

    validated = DomainKnowledgePack.model_validate(
        pack.model_dump(mode="python")
    )
    payload = validated.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _require_unique(values: object, label: str) -> None:
    items = list(values)
    if len(items) != len(set(items)):
        raise ValueError(f"{label} values must be unique")


__all__ = [
    "DOMAIN_KNOWLEDGE_PACK_SCHEMA_VERSION",
    "DomainKnowledgePack",
    "EngineScope",
    "KnowledgeProgram",
    "KnowledgeRule",
    "KnowledgeSourceRef",
    "ScientificDomain",
    "domain_knowledge_pack_sha256",
]
