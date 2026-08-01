"""Immutable v1 contracts for paper-derived ChemSmart research plans.

These models record source evidence and scientific intent.  They do not
retrieve papers, render native engine inputs, execute commands, or decide that
a calculation succeeded.  Command workflows and runtime receipts remain
separate, content-addressed contracts so their existing deterministic gates
retain authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StrictBool,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)

from chemsmart.agent.domain_knowledge import ScientificDomain
from chemsmart.agent.command_workflow import CommandWorkflowSpec
from chemsmart.agent.scientific_task import ScientificTaskSpec


PAPER_SOURCE_BUNDLE_SCHEMA_VERSION = "chemsmart.paper-source-bundle.v1"
MOLECULAR_SYSTEM_SCHEMA_VERSION = "chemsmart.molecular-system.v1"
PROJECT_CONFIG_SCHEMA_VERSION = "chemsmart.project-config.v1"
PAPER_RESEARCH_PLAN_SCHEMA_VERSION = "chemsmart.paper-research-plan.v1"
REQUIRED_PROTOCOL_COVERAGE_SCHEMA_VERSION = (
    "chemsmart.required-protocol-coverage.v1"
)
CLAIM_VALIDATION_RECEIPT_SCHEMA_VERSION = (
    "chemsmart.claim-validation-receipt.v1"
)
PROJECT_LOADER_RECEIPT_SCHEMA_VERSION = (
    "chemsmart.project-loader-validation-receipt.v1"
)
WORKFLOW_PREVIEW_RECEIPT_SCHEMA_VERSION = (
    "chemsmart.workflow-preview-validation-receipt.v1"
)
REVIEW_VALIDATION_RECEIPT_SCHEMA_VERSION = (
    "chemsmart.review-validation-receipt.v1"
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
_SHA256 = r"^[0-9a-f]{64}$"
_SETTING_NAME = r"^[a-z][a-z0-9_.-]{0,127}$"
_NO_CONTROL_CHARACTERS = re.compile(r"^[^\x00-\x1f\x7f]+$")

ClaimScalar = StrictBool | StrictInt | StrictFloat | str
_ClaimFact = tuple[str, tuple[str, ...], ClaimScalar, str | None]


class _Contract(BaseModel):
    """Strict and transitively immutable paper-research contract base."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        str_strip_whitespace=True,
    )


class SourceArtifactKind(str, Enum):
    ARTICLE = "article"
    SUPPORTING_INFORMATION = "supporting_information"
    FIGURE = "figure"
    TABLE = "table"
    GEOMETRY = "geometry"
    DATASET = "dataset"
    CODE = "code"
    CITED_PROTOCOL = "cited_protocol"
    SOFTWARE_MANUAL = "software_manual"


class SourceAccess(str, Enum):
    OPEN = "open"
    PUBLIC_METADATA = "public_metadata"
    PRIVATE_FULL_TEXT = "private_full_text"


class EpistemicStatus(str, Enum):
    EXPLICIT = "explicit"
    DERIVED = "derived"
    INFERRED = "inferred"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"
    NOT_APPLICABLE = "not_applicable"


class ClaimCriticality(str, Enum):
    CRITICAL = "critical"
    IMPORTANT = "important"
    CONTEXT = "context"


class ReadinessState(str, Enum):
    READY = "ready"
    BLOCKED_MISSING_EVIDENCE = "blocked_missing_evidence"


class Program(str, Enum):
    GAUSSIAN = "gaussian"
    ORCA = "orca"
    XTB = "xtb"


class PlanState(str, Enum):
    DRAFTING = "drafting"
    BLOCKED_MISSING_EVIDENCE = "blocked_missing_evidence"
    BLOCKED_CAPABILITY_GAP = "blocked_capability_gap"
    PLANNED = "planned"
    PREVIEWED = "previewed"
    VALIDATED = "validated"
    FAILED = "failed"


class ExecutionState(str, Enum):
    NOT_STARTED = "not_started"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    RUNNING = "running"
    EXECUTED = "executed"
    VALIDATED = "validated"
    REPRODUCED = "reproduced"
    BLOCKED = "blocked"
    FAILED = "failed"


class ResearchGraphKind(str, Enum):
    VALIDATION = "validation"
    ANALYSIS = "analysis"
    REVIEW = "review"
    REPORT = "report"


class PaperReviewRole(str, Enum):
    DOMAIN = "domain"
    COMMAND_EVIDENCE = "command_evidence"
    ADVERSARIAL = "adversarial"


class PlanValidationStatus(str, Enum):
    VALID = "valid"
    BLOCKED_MISSING_EVIDENCE = "blocked_missing_evidence"
    BLOCKED_CAPABILITY_GAP = "blocked_capability_gap"
    INVALID = "invalid"


class FindingSeverity(str, Enum):
    BLOCKING = "blocking"
    ERROR = "error"


class SourceArtifact(_Contract):
    """Content-addressed paper or protocol artifact without a host path."""

    artifact_id: str = Field(pattern=_IDENTIFIER)
    kind: SourceArtifactKind
    locator: str = Field(min_length=1, max_length=2048)
    sha256: str = Field(pattern=_SHA256)
    size_bytes: int = Field(ge=0)
    media_type: str = Field(min_length=1, max_length=255)
    retrieval_receipt_id: str = Field(pattern=_IDENTIFIER)
    access: SourceAccess
    license_id: str | None = Field(default=None, max_length=160)
    derived_from_artifact_ids: tuple[str, ...] = ()

    @field_validator("locator")
    @classmethod
    def _safe_source_locator(cls, value: str) -> str:
        if not _NO_CONTROL_CHARACTERS.fullmatch(value):
            raise ValueError("source text fields must not contain control characters")
        if _looks_like_host_path(value):
            raise ValueError("source locators must not contain host paths")
        return value

    @field_validator("media_type", "license_id")
    @classmethod
    def _reject_control_characters(cls, value: str | None) -> str | None:
        if value is not None and not _NO_CONTROL_CHARACTERS.fullmatch(value):
            raise ValueError("source text fields must not contain control characters")
        return value

    @field_validator("derived_from_artifact_ids")
    @classmethod
    def _canonical_derived_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_identifiers(value, "derived_from_artifact_ids")

    @model_validator(mode="after")
    def _not_derived_from_self(self) -> "SourceArtifact":
        if self.artifact_id in self.derived_from_artifact_ids:
            raise ValueError("a source artifact cannot derive from itself")
        return self


class PaperSourceBundle(_Contract):
    """The declared source set required to reconstruct one paper."""

    schema_version: str = Field(
        default=PAPER_SOURCE_BUNDLE_SCHEMA_VERSION,
        pattern=r"^chemsmart\.paper-source-bundle\.v1$",
    )
    bundle_id: str = Field(pattern=_IDENTIFIER)
    paper_id: str = Field(pattern=_IDENTIFIER)
    canonical_identifier: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=1024)
    domain: ScientificDomain
    required_artifact_kinds: tuple[SourceArtifactKind, ...] = (
        SourceArtifactKind.ARTICLE,
    )
    artifacts: tuple[SourceArtifact, ...] = Field(min_length=1)

    @field_validator("canonical_identifier", "title")
    @classmethod
    def _safe_text(cls, value: str) -> str:
        if not _NO_CONTROL_CHARACTERS.fullmatch(value):
            raise ValueError("paper metadata must not contain control characters")
        return value

    @field_validator("required_artifact_kinds")
    @classmethod
    def _canonical_required_kinds(
        cls, value: tuple[SourceArtifactKind, ...]
    ) -> tuple[SourceArtifactKind, ...]:
        if SourceArtifactKind.ARTICLE not in value:
            raise ValueError("required_artifact_kinds must include article")
        if len(value) != len(set(value)):
            raise ValueError("required_artifact_kinds must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @field_validator("artifacts")
    @classmethod
    def _canonical_artifacts(
        cls, value: tuple[SourceArtifact, ...]
    ) -> tuple[SourceArtifact, ...]:
        _require_unique_ids(
            (item.artifact_id for item in value), "source artifact_id"
        )
        return tuple(sorted(value, key=lambda item: item.artifact_id))


class ClaimSourceLocator(_Contract):
    """Exact fragment of a source artifact supporting a protocol claim."""

    artifact_id: str = Field(pattern=_IDENTIFIER)
    locator: str = Field(min_length=1, max_length=512)

    @field_validator("locator")
    @classmethod
    def _safe_locator(cls, value: str) -> str:
        if not _NO_CONTROL_CHARACTERS.fullmatch(value):
            raise ValueError("claim locator must not contain control characters")
        if _looks_like_host_path(value):
            raise ValueError("claim locators must not contain host paths")
        return value


class ClaimValidationPurpose(str, Enum):
    DERIVATION = "derivation"
    APPLICABILITY = "applicability"


class ClaimEvidenceRef(_Contract):
    """Content-addressed source input consumed by a claim validator."""

    artifact_id: str = Field(pattern=_IDENTIFIER)
    sha256: str = Field(pattern=_SHA256)


class ClaimValidationReceipt(_Contract):
    """Deterministic proof for a derived value or critical N/A decision."""

    schema_version: str = Field(
        default=CLAIM_VALIDATION_RECEIPT_SCHEMA_VERSION,
        pattern=r"^chemsmart\.claim-validation-receipt\.v1$",
    )
    kind: str = Field(pattern=r"^claim_validation$")
    receipt_id: str = Field(pattern=_IDENTIFIER)
    claim_id: str = Field(pattern=_IDENTIFIER)
    purpose: ClaimValidationPurpose
    rule_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,191}$")
    source_artifacts: tuple[ClaimEvidenceRef, ...] = Field(min_length=1)
    result_sha256: str = Field(pattern=_SHA256)
    verdict: str = Field(pattern=r"^valid$")
    receipt_sha256: str = Field(pattern=_SHA256)

    @field_validator("source_artifacts")
    @classmethod
    def _canonical_source_artifacts(
        cls, value: tuple[ClaimEvidenceRef, ...]
    ) -> tuple[ClaimEvidenceRef, ...]:
        _require_unique_ids(
            (item.artifact_id for item in value),
            "claim validation source artifact_id",
        )
        return tuple(sorted(value, key=lambda item: item.artifact_id))

    @model_validator(mode="after")
    def _receipt_is_content_addressed(self) -> "ClaimValidationReceipt":
        if self.receipt_sha256 != _content_addressed_receipt_sha256(self):
            raise ValueError("claim validation receipt digest mismatch")
        return self


class ClaimAlternative(_Contract):
    """One sourced candidate retained for a conflicting protocol field."""

    alternative_id: str = Field(pattern=_IDENTIFIER)
    value: ClaimScalar
    units: str | None = Field(default=None, max_length=80)
    source_locators: tuple[ClaimSourceLocator, ...] = Field(min_length=1)

    @field_validator("source_locators")
    @classmethod
    def _canonical_sources(
        cls, value: tuple[ClaimSourceLocator, ...]
    ) -> tuple[ClaimSourceLocator, ...]:
        return _canonical_source_locators(value)


class ProtocolClaim(_Contract):
    """A typed paper-derived field with an explicit epistemic state."""

    claim_id: str = Field(pattern=_IDENTIFIER)
    field_path: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z][A-Za-z0-9_.:-]*$",
    )
    value: ClaimScalar | None = None
    units: str | None = Field(default=None, max_length=80)
    epistemic_status: EpistemicStatus
    criticality: ClaimCriticality
    source_locators: tuple[ClaimSourceLocator, ...] = ()
    alternatives: tuple[ClaimAlternative, ...] = ()
    derivation: str = Field(default="", max_length=1024)
    rationale: str = Field(default="", max_length=1024)
    derivation_receipt: ClaimValidationReceipt | None = None
    applicability_receipt: ClaimValidationReceipt | None = None

    @field_validator("source_locators")
    @classmethod
    def _canonical_sources(
        cls, value: tuple[ClaimSourceLocator, ...]
    ) -> tuple[ClaimSourceLocator, ...]:
        return _canonical_source_locators(value)

    @field_validator("alternatives")
    @classmethod
    def _canonical_alternatives(
        cls, value: tuple[ClaimAlternative, ...]
    ) -> tuple[ClaimAlternative, ...]:
        _require_unique_ids(
            (item.alternative_id for item in value), "claim alternative_id"
        )
        return tuple(sorted(value, key=lambda item: item.alternative_id))

    @model_validator(mode="after")
    def _epistemic_contract(self) -> "ProtocolClaim":
        status = self.epistemic_status
        if status in {
            EpistemicStatus.EXPLICIT,
            EpistemicStatus.DERIVED,
            EpistemicStatus.INFERRED,
        } and self.value is None:
            raise ValueError(f"{status.value} claims require a value")
        if status in {
            EpistemicStatus.UNKNOWN,
            EpistemicStatus.CONFLICT,
            EpistemicStatus.NOT_APPLICABLE,
        } and self.value is not None:
            raise ValueError(f"{status.value} claims must not assert a value")
        if status is EpistemicStatus.EXPLICIT and not self.source_locators:
            raise ValueError("explicit claims require a source locator")
        if status is EpistemicStatus.DERIVED:
            if (
                not self.source_locators
                or not self.derivation
                or self.derivation_receipt is None
            ):
                raise ValueError(
                    "derived claims require sources, a deterministic derivation, "
                    "and a validator receipt"
                )
            if (
                self.derivation_receipt.claim_id != self.claim_id
                or self.derivation_receipt.purpose
                is not ClaimValidationPurpose.DERIVATION
            ):
                raise ValueError("derived claim receipt does not bind this claim")
        elif self.derivation_receipt is not None:
            raise ValueError("derivation receipts are reserved for derived claims")
        if status is EpistemicStatus.INFERRED and not self.rationale:
            raise ValueError("inferred claims require a candidate rationale")
        if status is EpistemicStatus.CONFLICT:
            if len(self.alternatives) < 2 or not self.rationale:
                raise ValueError(
                    "conflict claims require two sourced alternatives and a rationale"
                )
        elif self.alternatives:
            raise ValueError("alternatives are reserved for conflict claims")
        if status in {
            EpistemicStatus.UNKNOWN,
            EpistemicStatus.NOT_APPLICABLE,
        } and not self.rationale:
            raise ValueError(f"{status.value} claims require a rationale")
        if (
            status is EpistemicStatus.NOT_APPLICABLE
            and self.criticality is ClaimCriticality.CRITICAL
        ):
            if self.applicability_receipt is None:
                raise ValueError(
                    "critical not_applicable claims require an applicability receipt"
                )
            if (
                self.applicability_receipt.claim_id != self.claim_id
                or self.applicability_receipt.purpose
                is not ClaimValidationPurpose.APPLICABILITY
            ):
                raise ValueError(
                    "applicability receipt does not bind this critical claim"
                )
        elif self.applicability_receipt is not None:
            raise ValueError(
                "applicability receipts are reserved for critical "
                "not_applicable claims"
            )
        return self

    @property
    def blocks_paper_faithful_execution(self) -> bool:
        return self.criticality is ClaimCriticality.CRITICAL and (
            self.epistemic_status
            in {
                EpistemicStatus.INFERRED,
                EpistemicStatus.UNKNOWN,
                EpistemicStatus.CONFLICT,
            }
        )


class ClaimReadinessAssessment(_Contract):
    status: ReadinessState
    blocking_claim_ids: tuple[str, ...] = ()
    blocking_epistemic_states: tuple[EpistemicStatus, ...] = ()


class RequiredProtocolField(_Contract):
    """Independently declared critical field that the plan must account for."""

    field_path: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z][A-Za-z0-9_.:-]*$",
    )
    expected_units: str | None = Field(default=None, max_length=80)
    rationale: str = Field(min_length=1, max_length=512)


class RequiredProtocolCoverage(_Contract):
    """Out-of-band source and field inventory used as the completeness oracle."""

    schema_version: str = Field(
        default=REQUIRED_PROTOCOL_COVERAGE_SCHEMA_VERSION,
        pattern=r"^chemsmart\.required-protocol-coverage\.v1$",
    )
    coverage_id: str = Field(pattern=_IDENTIFIER)
    source_bundle_sha256: str = Field(pattern=_SHA256)
    declarer_id: str = Field(pattern=_IDENTIFIER)
    declaration_receipt_sha256: str = Field(pattern=_SHA256)
    required_artifact_kinds: tuple[SourceArtifactKind, ...] = Field(
        min_length=1
    )
    required_fields: tuple[RequiredProtocolField, ...] = Field(min_length=1)
    required_system_ids: tuple[str, ...] = ()
    required_project_ids: tuple[str, ...] = ()
    required_workflow_ids: tuple[str, ...] = ()

    @field_validator("required_artifact_kinds")
    @classmethod
    def _canonical_required_artifacts(
        cls, value: tuple[SourceArtifactKind, ...]
    ) -> tuple[SourceArtifactKind, ...]:
        if SourceArtifactKind.ARTICLE not in value:
            raise ValueError("coverage must require the article")
        if len(value) != len(set(value)):
            raise ValueError("coverage artifact kinds must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @field_validator("required_fields")
    @classmethod
    def _canonical_required_fields(
        cls, value: tuple[RequiredProtocolField, ...]
    ) -> tuple[RequiredProtocolField, ...]:
        _require_unique_ids(
            (item.field_path for item in value),
            "required protocol field_path",
        )
        return tuple(sorted(value, key=lambda item: item.field_path))

    @field_validator(
        "required_system_ids",
        "required_project_ids",
        "required_workflow_ids",
    )
    @classmethod
    def _canonical_required_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_identifiers(value, "required coverage identifiers")


class MolecularFragment(_Contract):
    fragment_id: str = Field(pattern=_IDENTIFIER)
    atom_indices: tuple[int, ...] = Field(min_length=1)
    charge: StrictInt | None = None
    multiplicity: StrictInt | None = Field(default=None, ge=1)

    @field_validator("atom_indices")
    @classmethod
    def _canonical_atom_indices(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if any(index < 0 for index in value):
            raise ValueError("atom indices are zero-based and must be non-negative")
        if len(value) != len(set(value)):
            raise ValueError("atom_indices must be unique within a fragment")
        return tuple(sorted(value))


class MolecularConstraintRef(_Contract):
    constraint_id: str = Field(pattern=_IDENTIFIER)
    kind: str = Field(pattern=_SETTING_NAME)
    definition_sha256: str = Field(pattern=_SHA256)
    claim_ids: tuple[str, ...] = ()

    @field_validator("claim_ids")
    @classmethod
    def _canonical_claim_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_identifiers(value, "constraint claim_ids")


class MolecularSystemSpec(_Contract):
    """Exact molecular identity and electronic state for one paper species."""

    schema_version: str = Field(
        default=MOLECULAR_SYSTEM_SCHEMA_VERSION,
        pattern=r"^chemsmart\.molecular-system\.v1$",
    )
    system_id: str = Field(pattern=_IDENTIFIER)
    species_id: str = Field(pattern=_IDENTIFIER)
    conformer_id: str = Field(pattern=_IDENTIFIER)
    atom_count: int = Field(ge=1)
    geometry_artifact_id: str = Field(pattern=_IDENTIFIER)
    geometry_sha256: str = Field(pattern=_SHA256)
    ordered_geometry_sha256: str = Field(pattern=_SHA256)
    atom_order_sha256: str = Field(pattern=_SHA256)
    coordinate_units: str = Field(pattern=r"^(angstrom|bohr)$")
    charge: StrictInt
    multiplicity: StrictInt = Field(ge=1)
    fragments: tuple[MolecularFragment, ...] = ()
    constraints: tuple[MolecularConstraintRef, ...] = ()
    claim_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("fragments")
    @classmethod
    def _canonical_fragments(
        cls, value: tuple[MolecularFragment, ...]
    ) -> tuple[MolecularFragment, ...]:
        _require_unique_ids(
            (item.fragment_id for item in value), "molecular fragment_id"
        )
        return tuple(sorted(value, key=lambda item: item.fragment_id))

    @field_validator("constraints")
    @classmethod
    def _canonical_constraints(
        cls, value: tuple[MolecularConstraintRef, ...]
    ) -> tuple[MolecularConstraintRef, ...]:
        _require_unique_ids(
            (item.constraint_id for item in value), "molecular constraint_id"
        )
        return tuple(sorted(value, key=lambda item: item.constraint_id))

    @field_validator("claim_ids")
    @classmethod
    def _canonical_claim_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_identifiers(value, "molecular claim_ids")

    @model_validator(mode="after")
    def _fragment_indices_are_in_range(self) -> "MolecularSystemSpec":
        for fragment in self.fragments:
            if fragment.atom_indices[-1] >= self.atom_count:
                raise ValueError("fragment atom index exceeds atom_count")
        return self


class SelectorAssignment(_Contract):
    selector: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=240)


class SolventSpec(_Contract):
    model: str = Field(min_length=1, max_length=80)
    solvent_id: str = Field(min_length=1, max_length=120)


class ProjectSetting(_Contract):
    name: str = Field(pattern=_SETTING_NAME)
    value: ClaimScalar
    units: str | None = Field(default=None, max_length=80)
    claim_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("claim_ids")
    @classmethod
    def _canonical_claim_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_identifiers(value, "project setting claim_ids")


class SettingClaimBinding(_Contract):
    setting_name: str = Field(pattern=_SETTING_NAME)
    claim_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("claim_ids")
    @classmethod
    def _canonical_claim_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_identifiers(value, "setting claim_ids")


class ProjectConfigSpec(_Contract):
    """Evidence-bound candidate for one canonical ChemSmart project YAML."""

    schema_version: str = Field(
        default=PROJECT_CONFIG_SCHEMA_VERSION,
        pattern=r"^chemsmart\.project-config\.v1$",
    )
    project_id: str = Field(pattern=_IDENTIFIER)
    project_name: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    program: Program
    program_version: str = Field(min_length=1, max_length=80)
    method: str = Field(min_length=1, max_length=160)
    basis_assignments: tuple[SelectorAssignment, ...] = ()
    ecp_assignments: tuple[SelectorAssignment, ...] = ()
    dispersion: str | None = Field(default=None, min_length=1, max_length=80)
    solvent: SolventSpec | None = None
    integration_grid: str | None = Field(
        default=None, min_length=1, max_length=120
    )
    scf_convergence: str | None = Field(
        default=None, min_length=1, max_length=120
    )
    geometry_convergence: str | None = Field(
        default=None, min_length=1, max_length=120
    )
    temperature_kelvin: FiniteFloat | None = Field(default=None, gt=0)
    standard_state: str | None = Field(
        default=None, min_length=1, max_length=160
    )
    additional_settings: tuple[ProjectSetting, ...] = ()
    setting_claims: tuple[SettingClaimBinding, ...] = Field(min_length=3)
    project_yaml_artifact_id: str | None = Field(
        default=None, pattern=_IDENTIFIER
    )
    project_yaml_sha256: str | None = Field(default=None, pattern=_SHA256)
    loader_receipt_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    loader_receipt_sha256: str | None = Field(default=None, pattern=_SHA256)

    @field_validator("basis_assignments", "ecp_assignments")
    @classmethod
    def _canonical_assignments(
        cls, value: tuple[SelectorAssignment, ...]
    ) -> tuple[SelectorAssignment, ...]:
        _require_unique_ids(
            (item.selector for item in value), "project assignment selector"
        )
        return tuple(sorted(value, key=lambda item: item.selector))

    @field_validator("additional_settings")
    @classmethod
    def _canonical_additional_settings(
        cls, value: tuple[ProjectSetting, ...]
    ) -> tuple[ProjectSetting, ...]:
        _require_unique_ids(
            (item.name for item in value), "additional project setting"
        )
        return tuple(sorted(value, key=lambda item: item.name))

    @field_validator("setting_claims")
    @classmethod
    def _canonical_setting_claims(
        cls, value: tuple[SettingClaimBinding, ...]
    ) -> tuple[SettingClaimBinding, ...]:
        _require_unique_ids(
            (item.setting_name for item in value), "setting claim binding"
        )
        return tuple(sorted(value, key=lambda item: item.setting_name))

    @model_validator(mode="after")
    def _project_contract_is_complete(self) -> "ProjectConfigSpec":
        if (self.project_yaml_artifact_id is None) != (
            self.project_yaml_sha256 is None
        ):
            raise ValueError(
                "project YAML artifact identity and digest must be paired"
            )
        if (self.loader_receipt_id is None) != (
            self.loader_receipt_sha256 is None
        ):
            raise ValueError("project loader receipt identity and digest must pair")
        if self.loader_receipt_id is not None and self.project_yaml_sha256 is None:
            raise ValueError("project loader receipt requires a rendered project YAML")
        if self.program is Program.XTB and (
            self.basis_assignments or self.ecp_assignments
        ):
            raise ValueError("xTB project settings must not declare basis or ECP")
        required = {"program", "program_version", "method"}
        optional_values = {
            "basis": self.basis_assignments,
            "ecp": self.ecp_assignments,
            "dispersion": self.dispersion,
            "solvent": self.solvent,
            "integration_grid": self.integration_grid,
            "scf_convergence": self.scf_convergence,
            "geometry_convergence": self.geometry_convergence,
            "temperature_kelvin": self.temperature_kelvin,
            "standard_state": self.standard_state,
        }
        required.update(
            name for name, value in optional_values.items() if value
        )
        observed = {item.setting_name for item in self.setting_claims}
        missing = sorted(required.difference(observed))
        if missing:
            raise ValueError(
                "project settings lack claim bindings: " + ", ".join(missing)
            )
        return self


class ContractDigestRef(_Contract):
    contract_id: str = Field(pattern=_IDENTIFIER)
    schema_version: str = Field(min_length=1, max_length=160)
    sha256: str = Field(pattern=_SHA256)


class DomainKnowledgeBinding(_Contract):
    """Scope-bound reference to a versioned scientific knowledge pack."""

    pack_ref: ContractDigestRef
    domains: tuple[ScientificDomain, ...] = Field(min_length=1)
    programs: tuple[Program, ...] = Field(min_length=1)
    validator_registry_sha256: str = Field(pattern=_SHA256)

    @field_validator("domains", "programs")
    @classmethod
    def _canonical_scopes(cls, value: tuple[Any, ...]) -> tuple[Any, ...]:
        if len(value) != len(set(value)):
            raise ValueError("knowledge-pack scope values must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @model_validator(mode="after")
    def _binds_domain_knowledge_v1(self) -> "DomainKnowledgeBinding":
        if (
            self.pack_ref.schema_version
            != "chemsmart.domain-knowledge-pack.v1"
        ):
            raise ValueError("pack_ref must bind DomainKnowledgePack v1")
        return self


class ArtifactDigestRef(_Contract):
    artifact_id: str = Field(pattern=_IDENTIFIER)
    kind: str = Field(pattern=_SETTING_NAME)
    sha256: str = Field(pattern=_SHA256)


class ProjectLoaderValidationReceipt(_Contract):
    """Content address of one real project-loader observation."""

    schema_version: str = Field(
        default=PROJECT_LOADER_RECEIPT_SCHEMA_VERSION,
        pattern=r"^chemsmart\.project-loader-validation-receipt\.v1$",
    )
    kind: str = Field(pattern=r"^project_loader$")
    receipt_id: str = Field(pattern=_IDENTIFIER)
    project_id: str = Field(pattern=_IDENTIFIER)
    project_yaml_artifact_id: str = Field(pattern=_IDENTIFIER)
    project_yaml_sha256: str = Field(pattern=_SHA256)
    project_name: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    program: Program
    required_job_kinds: tuple[str, ...] = ()
    runtime_summary_sha256: str = Field(pattern=_SHA256)
    verdict: str = Field(pattern=r"^ok$")
    receipt_sha256: str = Field(pattern=_SHA256)

    @field_validator("required_job_kinds")
    @classmethod
    def _canonical_required_jobs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_setting_names(value, "required project job kinds")

    @model_validator(mode="after")
    def _receipt_is_content_addressed(self) -> "ProjectLoaderValidationReceipt":
        if self.receipt_sha256 != _content_addressed_receipt_sha256(self):
            raise ValueError("project loader receipt digest mismatch")
        return self


class ProjectValidationRecord(_Contract):
    """Private validation-context entry containing exact project YAML bytes."""

    # Exact YAML bytes are evidence.  The shared contract base strips string
    # whitespace for identifiers and labels, which would silently remove a
    # terminal newline before this record checks its content digest.
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=False,
    )

    project_id: str = Field(pattern=_IDENTIFIER)
    yaml_text: str = Field(min_length=1)
    loader_receipt: ProjectLoaderValidationReceipt

    @model_validator(mode="after")
    def _record_matches_receipt(self) -> "ProjectValidationRecord":
        if self.project_id != self.loader_receipt.project_id:
            raise ValueError("project record ID does not match loader receipt")
        if _sha256_text(self.yaml_text) != self.loader_receipt.project_yaml_sha256:
            raise ValueError("project YAML bytes do not match loader receipt")
        return self


class WorkflowPreviewValidationReceipt(_Contract):
    """Paper-layer semantic binding to an underlying command preview receipt."""

    schema_version: str = Field(
        default=WORKFLOW_PREVIEW_RECEIPT_SCHEMA_VERSION,
        pattern=r"^chemsmart\.workflow-preview-validation-receipt\.v1$",
    )
    kind: str = Field(pattern=r"^safe_preview$")
    receipt_id: str = Field(pattern=_IDENTIFIER)
    underlying_receipt_sha256: str = Field(pattern=_SHA256)
    workflow_ref: ContractDigestRef
    task_spec_ref: ContractDigestRef
    cli_schema_digest: str = Field(pattern=_SHA256)
    molecular_system_refs: tuple[ContractDigestRef, ...] = Field(min_length=1)
    project_yaml_refs: tuple[ArtifactDigestRef, ...] = ()
    status: str = Field(pattern=r"^previewed$")
    receipt_sha256: str = Field(pattern=_SHA256)

    @field_validator("molecular_system_refs")
    @classmethod
    def _canonical_system_refs(
        cls, value: tuple[ContractDigestRef, ...]
    ) -> tuple[ContractDigestRef, ...]:
        _require_unique_ids(
            (item.contract_id for item in value),
            "preview molecular system contract_id",
        )
        return tuple(sorted(value, key=lambda item: item.contract_id))

    @field_validator("project_yaml_refs")
    @classmethod
    def _canonical_project_refs(
        cls, value: tuple[ArtifactDigestRef, ...]
    ) -> tuple[ArtifactDigestRef, ...]:
        _require_unique_ids(
            (item.artifact_id for item in value),
            "preview project YAML artifact_id",
        )
        return tuple(sorted(value, key=lambda item: item.artifact_id))

    @model_validator(mode="after")
    def _receipt_is_content_addressed(self) -> "WorkflowPreviewValidationReceipt":
        if self.receipt_sha256 != _content_addressed_receipt_sha256(self):
            raise ValueError("workflow preview receipt digest mismatch")
        return self


class ReviewValidationReceipt(_Contract):
    """Content-addressed independent-review gate used by a paper plan."""

    schema_version: str = Field(
        default=REVIEW_VALIDATION_RECEIPT_SCHEMA_VERSION,
        pattern=r"^chemsmart\.review-validation-receipt\.v1$",
    )
    kind: str = Field(pattern=r"^review_gate$")
    review_id: str = Field(pattern=_IDENTIFIER)
    role: PaperReviewRole
    review_packet_sha256: str = Field(pattern=_SHA256)
    finding_set_sha256: str = Field(pattern=_SHA256)
    status: str = Field(pattern=r"^no_critical_findings_observed$")
    receipt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _receipt_is_content_addressed(self) -> "ReviewValidationReceipt":
        if self.receipt_sha256 != _content_addressed_receipt_sha256(self):
            raise ValueError("review validation receipt digest mismatch")
        return self


class CommandWorkflowBinding(_Contract):
    """Paper-level binding to the existing immutable command-workflow IR."""

    workflow_ref: ContractDigestRef
    task_spec_ref: ContractDigestRef
    molecular_system_ids: tuple[str, ...] = Field(min_length=1)
    project_ids: tuple[str, ...] = ()
    dependency_workflow_ids: tuple[str, ...] = ()
    safe_preview_receipt: ArtifactDigestRef | None = None

    @field_validator(
        "molecular_system_ids", "project_ids", "dependency_workflow_ids"
    )
    @classmethod
    def _canonical_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_identifiers(value, "workflow binding identifiers")

    @model_validator(mode="after")
    def _workflow_and_task_are_distinct(self) -> "CommandWorkflowBinding":
        if (
            self.workflow_ref.schema_version
            != "chemsmart.command-workflow.v1"
        ):
            raise ValueError(
                "workflow_ref must bind CommandWorkflowSpec v1"
            )
        if self.task_spec_ref.schema_version != "chemsmart.scientific-task.v1":
            raise ValueError("task_spec_ref must bind ScientificTaskSpec v1")
        if self.workflow_ref.contract_id == self.task_spec_ref.contract_id:
            raise ValueError("workflow and task contract IDs must be distinct")
        if self.workflow_ref.contract_id in self.dependency_workflow_ids:
            raise ValueError("a command workflow cannot depend on itself")
        return self


class ResearchGraphRef(_Contract):
    graph_id: str = Field(pattern=_IDENTIFIER)
    kind: ResearchGraphKind
    sha256: str = Field(pattern=_SHA256)


class PlanReviewGateRef(_Contract):
    """Digest binding to one independently validated read-only review."""

    role: PaperReviewRole
    review_id: str = Field(pattern=_IDENTIFIER)
    review_packet_sha256: str = Field(pattern=_SHA256)
    review_gate_sha256: str = Field(pattern=_SHA256)
    status: str = Field(
        pattern=r"^no_critical_findings_observed$"
    )


class PaperResearchPlan(_Contract):
    """Canonical paper-to-ChemSmart plan without execution authority."""

    schema_version: str = Field(
        default=PAPER_RESEARCH_PLAN_SCHEMA_VERSION,
        pattern=r"^chemsmart\.paper-research-plan\.v1$",
    )
    plan_id: str = Field(pattern=_IDENTIFIER)
    producer_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    source_bundle: PaperSourceBundle
    required_protocol_coverage_ref: ContractDigestRef | None = None
    claims: tuple[ProtocolClaim, ...] = ()
    molecular_systems: tuple[MolecularSystemSpec, ...] = ()
    project_configs: tuple[ProjectConfigSpec, ...] = ()
    command_workflows: tuple[CommandWorkflowBinding, ...] = ()
    domain_knowledge_packs: tuple[DomainKnowledgeBinding, ...] = ()
    graph_refs: tuple[ResearchGraphRef, ...] = ()
    review_gates: tuple[PlanReviewGateRef, ...] = ()
    capability_gap_refs: tuple[ArtifactDigestRef, ...] = ()
    approval_refs: tuple[ArtifactDigestRef, ...] = ()
    execution_receipts: tuple[ArtifactDigestRef, ...] = ()
    plan_state: PlanState = PlanState.DRAFTING
    execution_state: ExecutionState = ExecutionState.NOT_STARTED

    @field_validator("claims")
    @classmethod
    def _canonical_claims(
        cls, value: tuple[ProtocolClaim, ...]
    ) -> tuple[ProtocolClaim, ...]:
        _require_unique_ids((item.claim_id for item in value), "claim_id")
        return tuple(sorted(value, key=lambda item: item.claim_id))

    @field_validator("molecular_systems")
    @classmethod
    def _canonical_systems(
        cls, value: tuple[MolecularSystemSpec, ...]
    ) -> tuple[MolecularSystemSpec, ...]:
        _require_unique_ids((item.system_id for item in value), "system_id")
        return tuple(sorted(value, key=lambda item: item.system_id))

    @field_validator("project_configs")
    @classmethod
    def _canonical_projects(
        cls, value: tuple[ProjectConfigSpec, ...]
    ) -> tuple[ProjectConfigSpec, ...]:
        _require_unique_ids((item.project_id for item in value), "project_id")
        return tuple(sorted(value, key=lambda item: item.project_id))

    @field_validator("command_workflows")
    @classmethod
    def _canonical_workflows(
        cls, value: tuple[CommandWorkflowBinding, ...]
    ) -> tuple[CommandWorkflowBinding, ...]:
        _require_unique_ids(
            (item.workflow_ref.contract_id for item in value), "workflow_id"
        )
        return tuple(
            sorted(value, key=lambda item: item.workflow_ref.contract_id)
        )

    @field_validator("domain_knowledge_packs")
    @classmethod
    def _canonical_knowledge_packs(
        cls, value: tuple[DomainKnowledgeBinding, ...]
    ) -> tuple[DomainKnowledgeBinding, ...]:
        _require_unique_ids(
            (item.pack_ref.contract_id for item in value),
            "domain knowledge pack_id",
        )
        return tuple(sorted(value, key=lambda item: item.pack_ref.contract_id))

    @field_validator("graph_refs")
    @classmethod
    def _canonical_graphs(
        cls, value: tuple[ResearchGraphRef, ...]
    ) -> tuple[ResearchGraphRef, ...]:
        _require_unique_ids((item.graph_id for item in value), "graph_id")
        kinds = [item.kind for item in value]
        if len(kinds) != len(set(kinds)):
            raise ValueError("only one graph is allowed for each graph kind")
        return tuple(sorted(value, key=lambda item: item.kind.value))

    @field_validator("review_gates")
    @classmethod
    def _canonical_review_gates(
        cls, value: tuple[PlanReviewGateRef, ...]
    ) -> tuple[PlanReviewGateRef, ...]:
        _require_unique_ids((item.review_id for item in value), "review_id")
        roles = [item.role for item in value]
        if len(roles) != len(set(roles)):
            raise ValueError("only one review gate is allowed for each role")
        return tuple(sorted(value, key=lambda item: item.role.value))

    @field_validator(
        "capability_gap_refs",
        "approval_refs",
        "execution_receipts",
    )
    @classmethod
    def _canonical_artifact_refs(
        cls, value: tuple[ArtifactDigestRef, ...]
    ) -> tuple[ArtifactDigestRef, ...]:
        _require_unique_ids(
            (item.artifact_id for item in value), "plan artifact reference"
        )
        return tuple(sorted(value, key=lambda item: item.artifact_id))


class PaperResearchValidationContext(_Contract):
    """Out-of-band registry of actual contracts and validation receipts."""

    required_protocol_coverages: tuple[RequiredProtocolCoverage, ...] = ()
    scientific_tasks: tuple[ScientificTaskSpec, ...] = ()
    command_workflows: tuple[CommandWorkflowSpec, ...] = ()
    project_records: tuple[ProjectValidationRecord, ...] = ()
    preview_receipts: tuple[WorkflowPreviewValidationReceipt, ...] = ()
    review_receipts: tuple[ReviewValidationReceipt, ...] = ()

    @field_validator("required_protocol_coverages")
    @classmethod
    def _canonical_coverages(
        cls, value: tuple[RequiredProtocolCoverage, ...]
    ) -> tuple[RequiredProtocolCoverage, ...]:
        _require_unique_ids(
            (item.coverage_id for item in value),
            "validation coverage_id",
        )
        return tuple(sorted(value, key=lambda item: item.coverage_id))

    @field_validator("scientific_tasks")
    @classmethod
    def _canonical_tasks(
        cls, value: tuple[ScientificTaskSpec, ...]
    ) -> tuple[ScientificTaskSpec, ...]:
        _require_unique_ids(
            (item.task_spec_id for item in value),
            "validation task_spec_id",
        )
        return tuple(sorted(value, key=lambda item: item.task_spec_id))

    @field_validator("command_workflows")
    @classmethod
    def _canonical_context_workflows(
        cls, value: tuple[CommandWorkflowSpec, ...]
    ) -> tuple[CommandWorkflowSpec, ...]:
        _require_unique_ids(
            (item.workflow_id for item in value),
            "validation workflow_id",
        )
        return tuple(sorted(value, key=lambda item: item.workflow_id))

    @field_validator("project_records")
    @classmethod
    def _canonical_project_records(
        cls, value: tuple[ProjectValidationRecord, ...]
    ) -> tuple[ProjectValidationRecord, ...]:
        _require_unique_ids(
            (item.project_id for item in value),
            "validation project_id",
        )
        return tuple(sorted(value, key=lambda item: item.project_id))

    @field_validator("preview_receipts")
    @classmethod
    def _canonical_preview_receipts(
        cls, value: tuple[WorkflowPreviewValidationReceipt, ...]
    ) -> tuple[WorkflowPreviewValidationReceipt, ...]:
        _require_unique_ids(
            (item.receipt_id for item in value),
            "validation preview receipt_id",
        )
        return tuple(sorted(value, key=lambda item: item.receipt_id))

    @field_validator("review_receipts")
    @classmethod
    def _canonical_review_receipts(
        cls, value: tuple[ReviewValidationReceipt, ...]
    ) -> tuple[ReviewValidationReceipt, ...]:
        _require_unique_ids(
            (item.review_id for item in value),
            "validation review_id",
        )
        return tuple(sorted(value, key=lambda item: item.review_id))


class ResearchPlanFinding(_Contract):
    rule_id: str = Field(pattern=r"^paper\.[a-z0-9_.-]+$")
    severity: FindingSeverity
    field_path: str = Field(min_length=1, max_length=256)
    message: str = Field(min_length=1, max_length=1024)
    related_ids: tuple[str, ...] = ()

    @field_validator("related_ids")
    @classmethod
    def _canonical_related_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_identifiers(value, "finding related_ids")


class PaperResearchPlanValidation(_Contract):
    plan_sha256: str = Field(pattern=_SHA256)
    source_bundle_sha256: str = Field(pattern=_SHA256)
    status: PlanValidationStatus
    claim_readiness: ClaimReadinessAssessment
    findings: tuple[ResearchPlanFinding, ...] = ()

    @property
    def valid(self) -> bool:
        return self.status is PlanValidationStatus.VALID


def assess_claim_readiness(
    claims: tuple[ProtocolClaim, ...] | list[ProtocolClaim],
) -> ClaimReadinessAssessment:
    """Apply the non-model readiness rule for critical protocol claims."""

    blocking = sorted(
        (claim for claim in claims if claim.blocks_paper_faithful_execution),
        key=lambda item: item.claim_id,
    )
    states = tuple(
        sorted(
            {item.epistemic_status for item in blocking},
            key=lambda item: item.value,
        )
    )
    return ClaimReadinessAssessment(
        status=(
            ReadinessState.BLOCKED_MISSING_EVIDENCE
            if blocking
            else ReadinessState.READY
        ),
        blocking_claim_ids=tuple(item.claim_id for item in blocking),
        blocking_epistemic_states=states,
    )


def claim_validation_result_sha256(
    field_path: str,
    value: ClaimScalar | None,
    units: str | None,
    purpose: ClaimValidationPurpose,
) -> str:
    """Bind a validator result to the exact claim field, value, and units."""

    return _sha256_json(
        {
            "field_path": field_path,
            "value": value,
            "units": _canonical_claim_unit(units),
            "purpose": purpose.value,
        }
    )


def build_claim_validation_receipt(
    *,
    receipt_id: str,
    claim_id: str,
    purpose: ClaimValidationPurpose,
    rule_id: str,
    source_artifacts: tuple[ClaimEvidenceRef, ...],
    field_path: str,
    value: ClaimScalar | None,
    units: str | None = None,
) -> ClaimValidationReceipt:
    body = {
        "schema_version": CLAIM_VALIDATION_RECEIPT_SCHEMA_VERSION,
        "kind": "claim_validation",
        "receipt_id": receipt_id,
        "claim_id": claim_id,
        "purpose": purpose,
        "rule_id": rule_id,
        "source_artifacts": source_artifacts,
        "result_sha256": claim_validation_result_sha256(
            field_path,
            value,
            units,
            purpose,
        ),
        "verdict": "valid",
    }
    return ClaimValidationReceipt.model_validate(
        {**body, "receipt_sha256": _sha256_json(_jsonable(body))}
    )


def build_project_loader_validation_record(
    *,
    receipt_id: str,
    project_id: str,
    project_yaml_artifact_id: str,
    project_name: str,
    program: Program,
    yaml_text: str,
    required_job_kinds: tuple[str, ...] = (),
) -> ProjectValidationRecord:
    """Run the real loader and bind its exact semantic summary."""

    from chemsmart.agent.project_yaml import validate_project_yaml

    canonical_jobs = _canonical_setting_names(
        required_job_kinds,
        "required project job kinds",
    )
    validation = validate_project_yaml(
        yaml_text,
        program=program.value,
        project_name=project_name,
        required_job_kinds=canonical_jobs,
    )
    if validation.get("verdict") != "ok":
        raise ValueError("project YAML did not pass the real loader")
    runtime_summary = validation.get("runtime_summary") or {}
    body = {
        "schema_version": PROJECT_LOADER_RECEIPT_SCHEMA_VERSION,
        "kind": "project_loader",
        "receipt_id": receipt_id,
        "project_id": project_id,
        "project_yaml_artifact_id": project_yaml_artifact_id,
        "project_yaml_sha256": _sha256_text(yaml_text),
        "project_name": project_name,
        "program": program,
        "required_job_kinds": canonical_jobs,
        "runtime_summary_sha256": _sha256_json(runtime_summary),
        "verdict": "ok",
    }
    receipt = ProjectLoaderValidationReceipt.model_validate(
        {**body, "receipt_sha256": _sha256_json(_jsonable(body))}
    )
    return ProjectValidationRecord(
        project_id=project_id,
        yaml_text=yaml_text,
        loader_receipt=receipt,
    )


def build_workflow_preview_validation_receipt(
    *,
    receipt_id: str,
    underlying_receipt_sha256: str,
    workflow: CommandWorkflowSpec,
    task: ScientificTaskSpec,
    molecular_systems: tuple[MolecularSystemSpec, ...],
    project_configs: tuple[ProjectConfigSpec, ...] = (),
) -> WorkflowPreviewValidationReceipt:
    system_refs = tuple(
        ContractDigestRef(
            contract_id=item.system_id,
            schema_version=item.schema_version,
            sha256=contract_sha256(item),
        )
        for item in molecular_systems
    )
    project_refs = tuple(
        ArtifactDigestRef(
            artifact_id=item.project_yaml_artifact_id,
            kind="project_yaml",
            sha256=item.project_yaml_sha256,
        )
        for item in project_configs
        if item.project_yaml_artifact_id is not None
        and item.project_yaml_sha256 is not None
    )
    body = {
        "schema_version": WORKFLOW_PREVIEW_RECEIPT_SCHEMA_VERSION,
        "kind": "safe_preview",
        "receipt_id": receipt_id,
        "underlying_receipt_sha256": underlying_receipt_sha256,
        "workflow_ref": ContractDigestRef(
            contract_id=workflow.workflow_id,
            schema_version=workflow.schema_version,
            sha256=contract_sha256(workflow),
        ),
        "task_spec_ref": ContractDigestRef(
            contract_id=task.task_spec_id,
            schema_version=task.schema_version,
            sha256=contract_sha256(task),
        ),
        "cli_schema_digest": workflow.cli_schema_digest,
        "molecular_system_refs": system_refs,
        "project_yaml_refs": project_refs,
        "status": "previewed",
    }
    return WorkflowPreviewValidationReceipt.model_validate(
        {**body, "receipt_sha256": _sha256_json(_jsonable(body))}
    )


def build_review_validation_receipt(
    *,
    review_id: str,
    role: PaperReviewRole,
    review_packet_sha256: str,
    finding_set_sha256: str,
) -> ReviewValidationReceipt:
    body = {
        "schema_version": REVIEW_VALIDATION_RECEIPT_SCHEMA_VERSION,
        "kind": "review_gate",
        "review_id": review_id,
        "role": role,
        "review_packet_sha256": review_packet_sha256,
        "finding_set_sha256": finding_set_sha256,
        "status": "no_critical_findings_observed",
    }
    return ReviewValidationReceipt.model_validate(
        {**body, "receipt_sha256": _sha256_json(_jsonable(body))}
    )


def canonical_contract_json(contract: BaseModel) -> str:
    """Return canonical JSON after revalidating the concrete contract type.

    ``model_copy(update=...)`` can create an unchecked Pydantic instance. A
    content address must never bless such an object, so hashing is a validation
    boundary as well as a serialization operation.
    """

    validated = type(contract).model_validate(
        contract.model_dump(mode="python")
    )
    return json.dumps(
        validated.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def contract_sha256(contract: BaseModel) -> str:
    """Return the stable SHA-256 identity of canonical contract JSON."""

    return hashlib.sha256(canonical_contract_json(contract).encode()).hexdigest()


def validate_paper_research_plan(
    plan: PaperResearchPlan,
    *,
    context: PaperResearchValidationContext | None = None,
) -> PaperResearchPlanValidation:
    """Cross-check evidence links and readiness without executing anything."""

    # Pydantic's ``model_copy(update=...)`` deliberately skips validation.
    # Re-enter every externally supplied contract through its public schema so
    # copied tuples are canonical and no unchecked update can influence a
    # readiness decision or its digest.
    plan = PaperResearchPlan.model_validate(plan.model_dump(mode="json"))
    if context is not None:
        context = PaperResearchValidationContext.model_validate(
            context.model_dump(mode="json")
        )

    findings: list[ResearchPlanFinding] = []
    artifacts = {
        item.artifact_id: item for item in plan.source_bundle.artifacts
    }
    available_kinds = {item.kind for item in artifacts.values()}
    missing_kinds = sorted(
        set(plan.source_bundle.required_artifact_kinds).difference(
            available_kinds
        ),
        key=lambda item: item.value,
    )
    for kind in missing_kinds:
        findings.append(
            _finding(
                "paper.source.required_kind_missing",
                FindingSeverity.BLOCKING,
                "source_bundle.artifacts",
                f"required source artifact kind is missing: {kind.value}",
            )
        )
    for artifact in artifacts.values():
        missing = sorted(
            set(artifact.derived_from_artifact_ids).difference(artifacts)
        )
        if missing:
            findings.append(
                _finding(
                    "paper.source.lineage_unbound",
                    FindingSeverity.ERROR,
                    "source_bundle.artifacts",
                    "derived source artifact refers to an unknown source",
                    (artifact.artifact_id, *missing),
                )
            )

    claims = {item.claim_id: item for item in plan.claims}
    for claim in plan.claims:
        for locator in _all_claim_locators(claim):
            if locator.artifact_id not in artifacts:
                findings.append(
                    _finding(
                        "paper.claim.source_unbound",
                        FindingSeverity.ERROR,
                        f"claims.{claim.claim_id}.source_locators",
                        "claim source locator refers to an unknown artifact",
                        (claim.claim_id, locator.artifact_id),
                    )
                )
        _validate_claim_validation_receipts(
            findings,
            claim,
            artifacts,
        )

    systems = {item.system_id: item for item in plan.molecular_systems}
    for system in plan.molecular_systems:
        geometry = artifacts.get(system.geometry_artifact_id)
        if geometry is None or geometry.kind is not SourceArtifactKind.GEOMETRY:
            findings.append(
                _finding(
                    "paper.system.geometry_unbound",
                    FindingSeverity.ERROR,
                    f"molecular_systems.{system.system_id}.geometry_artifact_id",
                    "molecular system requires a bound geometry source artifact",
                    (system.system_id, system.geometry_artifact_id),
                )
            )
        elif geometry.sha256 != system.geometry_sha256:
            findings.append(
                _finding(
                    "paper.system.geometry_hash_mismatch",
                    FindingSeverity.ERROR,
                    f"molecular_systems.{system.system_id}.geometry_sha256",
                    "molecular geometry digest differs from source evidence",
                    (system.system_id, geometry.artifact_id),
                )
            )
        _check_claim_ids(
            findings,
            system.claim_ids,
            claims,
            f"molecular_systems.{system.system_id}.claim_ids",
            system.system_id,
        )
        _validate_molecular_state_claims(
            findings,
            system,
            claims,
            system_count=len(plan.molecular_systems),
        )
        for constraint in system.constraints:
            _check_claim_ids(
                findings,
                constraint.claim_ids,
                claims,
                (
                    f"molecular_systems.{system.system_id}."
                    f"constraints.{constraint.constraint_id}.claim_ids"
                ),
                constraint.constraint_id,
            )

    projects = {item.project_id: item for item in plan.project_configs}
    for project in plan.project_configs:
        for binding in project.setting_claims:
            _check_claim_ids(
                findings,
                binding.claim_ids,
                claims,
                (
                    f"project_configs.{project.project_id}."
                    f"setting_claims.{binding.setting_name}"
                ),
                project.project_id,
            )
        for setting in project.additional_settings:
            _check_claim_ids(
                findings,
                setting.claim_ids,
                claims,
                (
                    f"project_configs.{project.project_id}."
                    f"additional_settings.{setting.name}"
                ),
                project.project_id,
            )
        _validate_project_setting_claims(
            findings,
            project,
            claims,
            project_count=len(plan.project_configs),
        )

    workflows = {
        item.workflow_ref.contract_id: item
        for item in plan.command_workflows
    }
    for workflow_id, binding in workflows.items():
        missing_systems = sorted(
            set(binding.molecular_system_ids).difference(systems)
        )
        missing_projects = sorted(set(binding.project_ids).difference(projects))
        missing_dependencies = sorted(
            set(binding.dependency_workflow_ids).difference(workflows)
        )
        if missing_systems:
            findings.append(
                _finding(
                    "paper.workflow.system_unbound",
                    FindingSeverity.ERROR,
                    f"command_workflows.{workflow_id}.molecular_system_ids",
                    "command workflow refers to unknown molecular systems",
                    (workflow_id, *missing_systems),
                )
            )
        if missing_projects:
            findings.append(
                _finding(
                    "paper.workflow.project_unbound",
                    FindingSeverity.ERROR,
                    f"command_workflows.{workflow_id}.project_ids",
                    "command workflow refers to unknown project configs",
                    (workflow_id, *missing_projects),
                )
            )
        if missing_dependencies:
            findings.append(
                _finding(
                    "paper.workflow.dependency_unbound",
                    FindingSeverity.ERROR,
                    f"command_workflows.{workflow_id}.dependency_workflow_ids",
                    "command workflow refers to unknown dependencies",
                    (workflow_id, *missing_dependencies),
                )
            )
    if _has_workflow_cycle(workflows):
        findings.append(
            _finding(
                "paper.workflow.dependency_cycle",
                FindingSeverity.ERROR,
                "command_workflows",
                "paper-level command workflow dependencies contain a cycle",
                tuple(workflows),
            )
        )

    covered_domains = {
        domain for binding in plan.domain_knowledge_packs for domain in binding.domains
    }
    covered_programs = {
        program
        for binding in plan.domain_knowledge_packs
        for program in binding.programs
    }
    if plan.source_bundle.domain not in covered_domains and plan.domain_knowledge_packs:
        findings.append(
            _finding(
                "paper.knowledge.domain_unbound",
                FindingSeverity.ERROR,
                "domain_knowledge_packs",
                "no selected knowledge pack covers the paper domain",
                (plan.source_bundle.domain.value,),
            )
        )
    uncovered_programs = sorted(
        {project.program for project in plan.project_configs}.difference(
            covered_programs
        ),
        key=lambda item: item.value,
    )
    if uncovered_programs and plan.domain_knowledge_packs:
        findings.append(
            _finding(
                "paper.knowledge.program_unbound",
                FindingSeverity.ERROR,
                "domain_knowledge_packs",
                "selected knowledge packs do not cover every project program",
                tuple(item.value for item in uncovered_programs),
            )
        )

    _validate_required_protocol_coverage(plan, context, findings)
    _validate_content_addressed_context(plan, context, findings)
    readiness = assess_claim_readiness(plan.claims)
    _validate_declared_states(
        plan,
        readiness,
        bool(missing_kinds),
        findings,
    )
    findings.sort(
        key=lambda item: (
            item.severity.value,
            item.rule_id,
            item.field_path,
            item.related_ids,
        )
    )
    if any(item.severity is FindingSeverity.ERROR for item in findings):
        status = PlanValidationStatus.INVALID
    elif (
        readiness.status is ReadinessState.BLOCKED_MISSING_EVIDENCE
        or missing_kinds
    ):
        status = PlanValidationStatus.BLOCKED_MISSING_EVIDENCE
    elif plan.capability_gap_refs:
        status = PlanValidationStatus.BLOCKED_CAPABILITY_GAP
    else:
        status = PlanValidationStatus.VALID
    return PaperResearchPlanValidation(
        plan_sha256=contract_sha256(plan),
        source_bundle_sha256=contract_sha256(plan.source_bundle),
        status=status,
        claim_readiness=readiness,
        findings=tuple(findings),
    )


def _validate_claim_validation_receipts(
    findings: list[ResearchPlanFinding],
    claim: ProtocolClaim,
    artifacts: dict[str, SourceArtifact],
) -> None:
    receipts = tuple(
        item
        for item in (
            claim.derivation_receipt,
            claim.applicability_receipt,
        )
        if item is not None
    )
    for receipt in receipts:
        for source_ref in receipt.source_artifacts:
            artifact = artifacts.get(source_ref.artifact_id)
            if artifact is None or artifact.sha256 != source_ref.sha256:
                findings.append(
                    _finding(
                        "paper.claim.validator_source_mismatch",
                        FindingSeverity.ERROR,
                        f"claims.{claim.claim_id}.{receipt.purpose.value}_receipt",
                        "claim validator source does not match source bundle",
                        (claim.claim_id, source_ref.artifact_id),
                    )
                )
        expected_result = claim_validation_result_sha256(
            claim.field_path,
            claim.value,
            claim.units,
            receipt.purpose,
        )
        if receipt.result_sha256 != expected_result:
            findings.append(
                _finding(
                    "paper.claim.validator_result_mismatch",
                    FindingSeverity.ERROR,
                    f"claims.{claim.claim_id}.{receipt.purpose.value}_receipt",
                    "claim validator result digest does not bind claim value",
                    (claim.claim_id, receipt.receipt_id),
                )
            )


def _validate_required_protocol_coverage(
    plan: PaperResearchPlan,
    context: PaperResearchValidationContext | None,
    findings: list[ResearchPlanFinding],
) -> None:
    advanced = {
        PlanState.PLANNED,
        PlanState.PREVIEWED,
        PlanState.VALIDATED,
    }
    coverage_ref = plan.required_protocol_coverage_ref
    if coverage_ref is None:
        if plan.plan_state in advanced:
            findings.append(
                _finding(
                    "paper.coverage.reference_missing",
                    FindingSeverity.ERROR,
                    "required_protocol_coverage_ref",
                    "advanced plans require independent protocol coverage",
                )
            )
        return
    if (
        coverage_ref.schema_version
        != REQUIRED_PROTOCOL_COVERAGE_SCHEMA_VERSION
    ):
        findings.append(
            _finding(
                "paper.coverage.schema_mismatch",
                FindingSeverity.ERROR,
                "required_protocol_coverage_ref.schema_version",
                "coverage reference must use required-protocol-coverage v1",
            )
        )
        return
    if context is None:
        findings.append(
            _finding(
                "paper.coverage.registry_missing",
                FindingSeverity.ERROR,
                "required_protocol_coverage_ref",
                "coverage reference requires an out-of-band registry",
            )
        )
        return
    coverages = {
        item.coverage_id: item
        for item in context.required_protocol_coverages
    }
    coverage = coverages.get(coverage_ref.contract_id)
    if coverage is None:
        findings.append(
            _finding(
                "paper.coverage.unresolved",
                FindingSeverity.ERROR,
                "required_protocol_coverage_ref.contract_id",
                "coverage contract is absent from validation registry",
                (coverage_ref.contract_id,),
            )
        )
        return
    if contract_sha256(coverage) != coverage_ref.sha256:
        findings.append(
            _finding(
                "paper.coverage.digest_mismatch",
                FindingSeverity.ERROR,
                "required_protocol_coverage_ref.sha256",
                "coverage digest does not match registered contract",
                (coverage.coverage_id,),
            )
        )
    source_digest = contract_sha256(plan.source_bundle)
    if coverage.source_bundle_sha256 != source_digest:
        findings.append(
            _finding(
                "paper.coverage.source_bundle_mismatch",
                FindingSeverity.ERROR,
                "required_protocol_coverage_ref",
                "coverage was declared for a different source bundle",
                (coverage.coverage_id,),
            )
        )
    if plan.producer_id is None or plan.producer_id == coverage.declarer_id:
        findings.append(
            _finding(
                "paper.coverage.independence_missing",
                FindingSeverity.ERROR,
                "producer_id",
                "coverage declarer must be independent from plan producer",
                (coverage.coverage_id, coverage.declarer_id),
            )
        )

    artifacts_by_kind: dict[SourceArtifactKind, list[SourceArtifact]] = {}
    for artifact in plan.source_bundle.artifacts:
        artifacts_by_kind.setdefault(artifact.kind, []).append(artifact)
    for kind in coverage.required_artifact_kinds:
        candidates = artifacts_by_kind.get(kind, [])
        if not candidates:
            findings.append(
                _finding(
                    "paper.coverage.source_artifact_missing",
                    FindingSeverity.ERROR,
                    "source_bundle.artifacts",
                    f"independent coverage requires {kind.value}",
                )
            )
        elif not any(
            item.access is not SourceAccess.PUBLIC_METADATA
            and item.size_bytes > 0
            for item in candidates
        ):
            findings.append(
                _finding(
                    "paper.coverage.source_content_unavailable",
                    FindingSeverity.ERROR,
                    "source_bundle.artifacts",
                    (
                        "independent coverage requires retrievable content, "
                        f"not metadata only, for {kind.value}"
                    ),
                    tuple(item.artifact_id for item in candidates),
                )
            )

    claims_by_path: dict[str, list[ProtocolClaim]] = {}
    for claim in plan.claims:
        claims_by_path.setdefault(claim.field_path, []).append(claim)
    evidence_blocked_plan = (
        plan.plan_state is PlanState.BLOCKED_MISSING_EVIDENCE
        and assess_claim_readiness(plan.claims).status
        is ReadinessState.BLOCKED_MISSING_EVIDENCE
    )
    for required in coverage.required_fields:
        matched = claims_by_path.get(required.field_path, [])
        if len(matched) != 1:
            # An absent required claim in an honestly evidence-blocked plan is
            # the blocker being reported, not a structurally invalid success
            # attempt. Ambiguous duplicate claims remain an error, as does any
            # omission in an advanced or otherwise ready plan.
            severity = (
                FindingSeverity.WARNING
                if not matched and evidence_blocked_plan
                else FindingSeverity.ERROR
            )
            findings.append(
                _finding(
                    "paper.coverage.critical_field_missing_or_ambiguous",
                    severity,
                    required.field_path,
                    "exactly one critical protocol claim for required field",
                    tuple(item.claim_id for item in matched),
                )
            )
            continue
        claim = matched[0]
        if claim.criticality is not ClaimCriticality.CRITICAL:
            findings.append(
                _finding(
                    "paper.coverage.criticality_downgraded",
                    FindingSeverity.ERROR,
                    f"claims.{claim.claim_id}.criticality",
                    "independently required field must remain critical",
                    (claim.claim_id,),
                )
            )
        if _canonical_claim_unit(claim.units) != _canonical_claim_unit(
            required.expected_units
        ):
            findings.append(
                _finding(
                    "paper.coverage.units_mismatch",
                    FindingSeverity.ERROR,
                    f"claims.{claim.claim_id}.units",
                    "required field units do not match coverage contract",
                    (claim.claim_id,),
                )
            )

    _validate_required_ids(
        findings,
        coverage.required_system_ids,
        {item.system_id for item in plan.molecular_systems},
        "molecular_systems",
        "paper.coverage.system_missing",
    )
    _validate_required_ids(
        findings,
        coverage.required_project_ids,
        {item.project_id for item in plan.project_configs},
        "project_configs",
        "paper.coverage.project_missing",
    )
    _validate_required_ids(
        findings,
        coverage.required_workflow_ids,
        {
            item.workflow_ref.contract_id
            for item in plan.command_workflows
        },
        "command_workflows",
        "paper.coverage.workflow_missing",
    )


def _validate_required_ids(
    findings: list[ResearchPlanFinding],
    required: tuple[str, ...],
    observed: set[str],
    field_path: str,
    rule_id: str,
) -> None:
    missing = tuple(sorted(set(required).difference(observed)))
    if missing:
        findings.append(
            _finding(
                rule_id,
                FindingSeverity.ERROR,
                field_path,
                "independent protocol coverage contains missing objects",
                missing,
            )
        )


def _validate_content_addressed_context(
    plan: PaperResearchPlan,
    context: PaperResearchValidationContext | None,
    findings: list[ResearchPlanFinding],
) -> None:
    advanced = {
        PlanState.PLANNED,
        PlanState.PREVIEWED,
        PlanState.VALIDATED,
    }
    if context is None:
        if plan.plan_state in advanced:
            findings.append(
                _finding(
                    "paper.context.registry_missing",
                    FindingSeverity.ERROR,
                    "plan_state",
                    "advanced plan requires actual contract and receipt registry",
                )
            )
        return

    tasks = {item.task_spec_id: item for item in context.scientific_tasks}
    workflows = {
        item.workflow_id: item for item in context.command_workflows
    }
    project_records = {
        item.project_id: item for item in context.project_records
    }
    preview_receipts = {
        item.receipt_id: item for item in context.preview_receipts
    }
    review_receipts = {
        item.review_id: item for item in context.review_receipts
    }
    systems = {item.system_id: item for item in plan.molecular_systems}
    projects = {item.project_id: item for item in plan.project_configs}
    required_jobs: dict[str, set[str]] = {
        item.project_id: set() for item in plan.project_configs
    }

    for binding in plan.command_workflows:
        workflow_id = binding.workflow_ref.contract_id
        task_id = binding.task_spec_ref.contract_id
        workflow = workflows.get(workflow_id)
        task = tasks.get(task_id)
        if workflow is None:
            findings.append(
                _finding(
                    "paper.context.workflow_unresolved",
                    FindingSeverity.ERROR,
                    f"command_workflows.{workflow_id}.workflow_ref",
                    "registered CommandWorkflowSpec payload",
                    (workflow_id,),
                )
            )
            continue
        if task is None:
            findings.append(
                _finding(
                    "paper.context.task_unresolved",
                    FindingSeverity.ERROR,
                    f"command_workflows.{workflow_id}.task_spec_ref",
                    "registered ScientificTaskSpec payload",
                    (task_id,),
                )
            )
            continue
        if contract_sha256(workflow) != binding.workflow_ref.sha256:
            findings.append(
                _finding(
                    "paper.context.workflow_digest_mismatch",
                    FindingSeverity.ERROR,
                    f"command_workflows.{workflow_id}.workflow_ref.sha256",
                    "workflow reference must bind actual workflow payload",
                    (workflow_id,),
                )
            )
        if contract_sha256(task) != binding.task_spec_ref.sha256:
            findings.append(
                _finding(
                    "paper.context.task_digest_mismatch",
                    FindingSeverity.ERROR,
                    f"command_workflows.{workflow_id}.task_spec_ref.sha256",
                    "task reference must bind actual task payload",
                    (task_id,),
                )
            )
        if workflow.task_spec_id != task.task_spec_id:
            findings.append(
                _finding(
                    "paper.context.workflow_task_id_mismatch",
                    FindingSeverity.ERROR,
                    f"command_workflows.{workflow_id}.task_spec_ref",
                    "workflow and scientific task IDs must match",
                    (workflow_id, task_id),
                )
            )

        _validate_task_system_join(
            findings,
            workflow_id,
            binding,
            task,
            systems,
        )
        actual_project_ids = {
            node.project_ref.project_id
            for node in workflow.nodes
            if node.project_ref is not None
        }
        if actual_project_ids != set(binding.project_ids):
            findings.append(
                _finding(
                    "paper.context.workflow_project_set_mismatch",
                    FindingSeverity.ERROR,
                    f"command_workflows.{workflow_id}.project_ids",
                    "paper binding must equal workflow project references",
                    tuple(sorted(actual_project_ids.symmetric_difference(
                        binding.project_ids
                    ))),
                )
            )
        for node in workflow.nodes:
            if node.project_ref is None:
                continue
            project_id = node.project_ref.project_id
            project = projects.get(project_id)
            record = project_records.get(project_id)
            if project is None or record is None:
                continue
            if node.project_ref.sha256 != record.loader_receipt.project_yaml_sha256:
                findings.append(
                    _finding(
                        "paper.context.command_project_digest_mismatch",
                        FindingSeverity.ERROR,
                        f"command_workflows.{workflow_id}.project_ids",
                        "command project ref must bind exact project YAML",
                        (workflow_id, project_id),
                    )
                )
            program, job_kind = _program_and_job_from_path(node.command_path)
            if program and program != project.program.value:
                findings.append(
                    _finding(
                        "paper.context.command_project_program_mismatch",
                        FindingSeverity.ERROR,
                        f"command_workflows.{workflow_id}.project_ids",
                        "command program must match project program",
                        (workflow_id, project_id),
                    )
                )
            if job_kind:
                required_jobs.setdefault(project_id, set()).add(job_kind)

        if plan.plan_state in {PlanState.PREVIEWED, PlanState.VALIDATED}:
            _validate_workflow_preview_context(
                findings,
                binding,
                workflow,
                task,
                systems,
                projects,
                preview_receipts,
            )

    if plan.plan_state in {PlanState.PREVIEWED, PlanState.VALIDATED}:
        for project in plan.project_configs:
            _validate_project_record(
                findings,
                project,
                project_records.get(project.project_id),
                tuple(sorted(required_jobs.get(project.project_id, set()))),
            )

    if plan.plan_state is PlanState.VALIDATED:
        for gate in plan.review_gates:
            receipt = review_receipts.get(gate.review_id)
            if receipt is None:
                findings.append(
                    _finding(
                        "paper.context.review_receipt_unresolved",
                        FindingSeverity.ERROR,
                        f"review_gates.{gate.review_id}",
                        "registered content-addressed review receipt",
                        (gate.review_id,),
                    )
                )
                continue
            if (
                receipt.role is not gate.role
                or receipt.review_packet_sha256
                != gate.review_packet_sha256
                or receipt.receipt_sha256 != gate.review_gate_sha256
                or receipt.status != gate.status
            ):
                findings.append(
                    _finding(
                        "paper.context.review_receipt_mismatch",
                        FindingSeverity.ERROR,
                        f"review_gates.{gate.review_id}",
                        "review ref must match actual packet-bound receipt",
                        (gate.review_id,),
                    )
                )


def _validate_task_system_join(
    findings: list[ResearchPlanFinding],
    workflow_id: str,
    binding: CommandWorkflowBinding,
    task: ScientificTaskSpec,
    systems: dict[str, MolecularSystemSpec],
) -> None:
    if len(binding.molecular_system_ids) != 1:
        findings.append(
            _finding(
                "paper.context.task_system_cardinality",
                FindingSeverity.ERROR,
                f"command_workflows.{workflow_id}.molecular_system_ids",
                "ScientificTaskSpec v1 binds exactly one molecular system",
                binding.molecular_system_ids,
            )
        )
        return
    system_id = binding.molecular_system_ids[0]
    system = systems.get(system_id)
    if system is None:
        return
    mismatches: list[str] = []
    if task.geometry.artifact_id != system.geometry_artifact_id:
        mismatches.append("geometry_artifact_id")
    if task.geometry.sha256 != system.geometry_sha256:
        mismatches.append("geometry_sha256")
    if task.geometry.ordered_geometry_sha256 != system.ordered_geometry_sha256:
        mismatches.append("ordered_geometry_sha256")
    if task.geometry.coordinate_units != system.coordinate_units:
        mismatches.append("coordinate_units")
    if task.electronic_state.charge != system.charge:
        mismatches.append("charge")
    if task.electronic_state.multiplicity != system.multiplicity:
        mismatches.append("multiplicity")
    if mismatches:
        findings.append(
            _finding(
                "paper.context.task_system_semantic_mismatch",
                FindingSeverity.ERROR,
                f"command_workflows.{workflow_id}.molecular_system_ids",
                "task geometry and electronic state must match paper system",
                (workflow_id, system_id, *mismatches),
            )
        )


def _validate_workflow_preview_context(
    findings: list[ResearchPlanFinding],
    binding: CommandWorkflowBinding,
    workflow: CommandWorkflowSpec,
    task: ScientificTaskSpec,
    systems: dict[str, MolecularSystemSpec],
    projects: dict[str, ProjectConfigSpec],
    receipts: dict[str, WorkflowPreviewValidationReceipt],
) -> None:
    preview_ref = binding.safe_preview_receipt
    if preview_ref is None:
        return
    workflow_id = binding.workflow_ref.contract_id
    if preview_ref.kind != "safe_preview":
        findings.append(
            _finding(
                "paper.context.preview_kind_mismatch",
                FindingSeverity.ERROR,
                f"command_workflows.{workflow_id}.safe_preview_receipt.kind",
                "safe_preview receipt kind",
                (workflow_id, preview_ref.kind),
            )
        )
        return
    receipt = receipts.get(preview_ref.artifact_id)
    if receipt is None:
        findings.append(
            _finding(
                "paper.context.preview_receipt_unresolved",
                FindingSeverity.ERROR,
                f"command_workflows.{workflow_id}.safe_preview_receipt",
                "registered workflow preview receipt",
                (workflow_id, preview_ref.artifact_id),
            )
        )
        return
    expected_system_refs = tuple(
        sorted(
            (
                ContractDigestRef(
                    contract_id=system_id,
                    schema_version=MOLECULAR_SYSTEM_SCHEMA_VERSION,
                    sha256=contract_sha256(systems[system_id]),
                )
                for system_id in binding.molecular_system_ids
                if system_id in systems
            ),
            key=lambda item: item.contract_id,
        )
    )
    expected_project_refs = tuple(
        sorted(
            (
                ArtifactDigestRef(
                    artifact_id=project.project_yaml_artifact_id,
                    kind="project_yaml",
                    sha256=project.project_yaml_sha256,
                )
                for project_id in binding.project_ids
                if (project := projects.get(project_id)) is not None
                and project.project_yaml_artifact_id is not None
                and project.project_yaml_sha256 is not None
            ),
            key=lambda item: item.artifact_id,
        )
    )
    mismatched = (
        receipt.receipt_sha256 != preview_ref.sha256
        or receipt.workflow_ref.contract_id != workflow.workflow_id
        or receipt.workflow_ref.sha256 != contract_sha256(workflow)
        or receipt.task_spec_ref.contract_id != task.task_spec_id
        or receipt.task_spec_ref.sha256 != contract_sha256(task)
        or receipt.cli_schema_digest != workflow.cli_schema_digest
        or receipt.molecular_system_refs != expected_system_refs
        or receipt.project_yaml_refs != expected_project_refs
    )
    if mismatched:
        findings.append(
            _finding(
                "paper.context.preview_receipt_mismatch",
                FindingSeverity.ERROR,
                f"command_workflows.{workflow_id}.safe_preview_receipt",
                "preview receipt must bind workflow, task, systems, and projects",
                (workflow_id, receipt.receipt_id),
            )
        )


def _validate_project_record(
    findings: list[ResearchPlanFinding],
    project: ProjectConfigSpec,
    record: ProjectValidationRecord | None,
    required_job_kinds: tuple[str, ...],
) -> None:
    if record is None:
        findings.append(
            _finding(
                "paper.context.project_record_unresolved",
                FindingSeverity.ERROR,
                f"project_configs.{project.project_id}",
                "exact project YAML and loader receipt in registry",
                (project.project_id,),
            )
        )
        return
    receipt = record.loader_receipt
    identity_mismatch = (
        project.project_name != receipt.project_name
        or project.program is not receipt.program
        or project.project_yaml_artifact_id
        != receipt.project_yaml_artifact_id
        or project.project_yaml_sha256 != receipt.project_yaml_sha256
        or project.loader_receipt_id != receipt.receipt_id
        or project.loader_receipt_sha256 != receipt.receipt_sha256
        or receipt.required_job_kinds != required_job_kinds
    )
    if identity_mismatch:
        findings.append(
            _finding(
                "paper.context.project_loader_binding_mismatch",
                FindingSeverity.ERROR,
                f"project_configs.{project.project_id}",
                "project config must bind exact YAML and loader receipt",
                (project.project_id, receipt.receipt_id),
            )
        )
        return

    from chemsmart.agent.project_yaml import validate_project_yaml

    validation = validate_project_yaml(
        record.yaml_text,
        program=project.program.value,
        project_name=project.project_name,
        required_job_kinds=required_job_kinds,
    )
    summary = validation.get("runtime_summary") or {}
    if (
        validation.get("verdict") != "ok"
        or _sha256_json(summary) != receipt.runtime_summary_sha256
    ):
        findings.append(
            _finding(
                "paper.context.project_loader_observation_mismatch",
                FindingSeverity.ERROR,
                f"project_configs.{project.project_id}",
                "fresh loader observation must match content-addressed receipt",
                (project.project_id, receipt.receipt_id),
            )
        )
        return
    _validate_project_runtime_semantics(
        findings,
        project,
        summary,
        required_job_kinds,
        record.yaml_text,
    )


def _validate_project_runtime_semantics(
    findings: list[ResearchPlanFinding],
    project: ProjectConfigSpec,
    summary: dict[str, Any],
    required_job_kinds: tuple[str, ...],
    yaml_text: str,
) -> None:
    jobs = required_job_kinds or tuple(sorted(summary))
    for job_kind in jobs:
        settings = summary.get(job_kind)
        if not isinstance(settings, dict):
            findings.append(
                _finding(
                    "paper.context.project_job_settings_missing",
                    FindingSeverity.ERROR,
                    f"project_configs.{project.project_id}",
                    f"loader settings for used job {job_kind}",
                    (project.project_id, job_kind),
                )
            )
            continue
        observed_method = (
            settings.get("gfn_version")
            if project.program is Program.XTB
            else settings.get("functional")
        )
        if _normalized_scientific_value(observed_method) != (
            _normalized_scientific_value(project.method)
        ):
            findings.append(
                _finding(
                    "paper.context.project_method_mismatch",
                    FindingSeverity.ERROR,
                    f"project_configs.{project.project_id}.method",
                    "project method must match effective loader settings",
                    (project.project_id, job_kind),
                )
            )
        if project.solvent is not None:
            if (
                _normalized_scientific_value(settings.get("solvent_model"))
                != _normalized_scientific_value(project.solvent.model)
                or _normalized_scientific_value(settings.get("solvent_id"))
                != _normalized_scientific_value(project.solvent.solvent_id)
            ):
                findings.append(
                    _finding(
                        "paper.context.project_solvent_mismatch",
                        FindingSeverity.ERROR,
                        f"project_configs.{project.project_id}.solvent",
                        "project solvent must match effective loader settings",
                        (project.project_id, job_kind),
                    )
                )
        if project.basis_assignments:
            observed_basis_values = {
                _normalized_scientific_value(value)
                for value in (
                    settings.get("basis"),
                    settings.get("heavy_elements_basis"),
                    settings.get("light_elements_basis"),
                )
                if value is not None
            }
            missing_basis = tuple(
                item.selector
                for item in project.basis_assignments
                if _normalized_scientific_value(item.value)
                not in observed_basis_values
            )
            if missing_basis:
                findings.append(
                    _finding(
                        "paper.context.project_basis_mapping_mismatch",
                        FindingSeverity.ERROR,
                        f"project_configs.{project.project_id}.basis_assignments",
                        "basis assignments must appear in effective loader settings",
                        (project.project_id, job_kind, *missing_basis),
                    )
                )
    normalized_yaml = _normalized_scientific_value(yaml_text)
    for assignment in project.ecp_assignments:
        if (
            _normalized_scientific_value(assignment.selector)
            not in normalized_yaml
            or _normalized_scientific_value(assignment.value)
            not in normalized_yaml
        ):
            findings.append(
                _finding(
                    "paper.context.project_ecp_mapping_mismatch",
                    FindingSeverity.ERROR,
                    f"project_configs.{project.project_id}.ecp_assignments",
                    "ECP selector and value must be present in exact YAML",
                    (project.project_id, assignment.selector),
                )
            )


def _program_and_job_from_path(
    command_path: tuple[str, ...],
) -> tuple[str, str]:
    for program in ("gaussian", "orca", "xtb"):
        if program not in command_path:
            continue
        index = command_path.index(program)
        job = command_path[index + 1] if index + 1 < len(command_path) else ""
        return program, job
    return "", ""


def _validate_declared_states(
    plan: PaperResearchPlan,
    readiness: ClaimReadinessAssessment,
    source_incomplete: bool,
    findings: list[ResearchPlanFinding],
) -> None:
    blocked = (
        readiness.status is ReadinessState.BLOCKED_MISSING_EVIDENCE
        or source_incomplete
    )
    advanced = {
        PlanState.PLANNED,
        PlanState.PREVIEWED,
        PlanState.VALIDATED,
    }
    if blocked and plan.plan_state in advanced:
        findings.append(
            _finding(
                "paper.state.false_ready",
                FindingSeverity.ERROR,
                "plan_state",
                "critical missing evidence forbids an advanced plan state",
            )
        )
    if plan.plan_state is PlanState.BLOCKED_MISSING_EVIDENCE and not blocked:
        findings.append(
            _finding(
                "paper.state.blocked_without_evidence_gap",
                FindingSeverity.ERROR,
                "plan_state",
                "blocked_missing_evidence requires a deterministic blocker",
            )
        )
    if (
        plan.plan_state is PlanState.BLOCKED_CAPABILITY_GAP
        and not plan.capability_gap_refs
    ):
        findings.append(
            _finding(
                "paper.state.capability_gap_receipt_missing",
                FindingSeverity.ERROR,
                "capability_gap_refs",
                "blocked_capability_gap requires a typed gap artifact",
            )
        )
    if plan.capability_gap_refs and plan.plan_state in advanced:
        findings.append(
            _finding(
                "paper.state.capability_gap_false_ready",
                FindingSeverity.ERROR,
                "plan_state",
                "an unresolved CLI capability gap forbids an advanced plan state",
            )
        )
    if plan.plan_state in advanced:
        required_collections = {
            "claims": plan.claims,
            "molecular_systems": plan.molecular_systems,
            "project_configs": plan.project_configs,
            "command_workflows": plan.command_workflows,
            "domain_knowledge_packs": plan.domain_knowledge_packs,
        }
        for field_name, value in required_collections.items():
            if not value:
                findings.append(
                    _finding(
                        "paper.state.required_contract_missing",
                        FindingSeverity.ERROR,
                        field_name,
                        f"{plan.plan_state.value} requires {field_name}",
                    )
                )
    if plan.plan_state in {PlanState.PREVIEWED, PlanState.VALIDATED}:
        missing_project_receipts = tuple(
            item.project_id
            for item in plan.project_configs
            if item.project_yaml_sha256 is None
            or item.loader_receipt_sha256 is None
        )
        if missing_project_receipts:
            findings.append(
                _finding(
                    "paper.state.project_loader_receipt_missing",
                    FindingSeverity.ERROR,
                    "project_configs",
                    "previewed plans require rendered YAML and loader receipts",
                    missing_project_receipts,
                )
            )
        missing_receipts = tuple(
            item.workflow_ref.contract_id
            for item in plan.command_workflows
            if item.safe_preview_receipt is None
        )
        if missing_receipts:
            findings.append(
                _finding(
                    "paper.state.preview_receipt_missing",
                    FindingSeverity.ERROR,
                    "command_workflows",
                    "previewed plans require one receipt per command workflow",
                    missing_receipts,
                )
            )
    if plan.plan_state is PlanState.VALIDATED:
        observed_graphs = {item.kind for item in plan.graph_refs}
        missing_graphs = set(ResearchGraphKind).difference(observed_graphs)
        if missing_graphs:
            findings.append(
                _finding(
                    "paper.state.graph_missing",
                    FindingSeverity.ERROR,
                    "graph_refs",
                    "validated plans require validation, analysis, review, "
                    "and report graphs",
                    tuple(sorted(item.value for item in missing_graphs)),
                )
            )
        required_review_roles = set(PaperReviewRole)
        observed_review_roles = {item.role for item in plan.review_gates}
        missing_review_roles = required_review_roles.difference(
            observed_review_roles
        )
        if missing_review_roles:
            findings.append(
                _finding(
                    "paper.state.review_gate_missing",
                    FindingSeverity.ERROR,
                    "review_gates",
                    "validated plans require all three independent green reviews",
                    tuple(
                        sorted(item.value for item in missing_review_roles)
                    ),
                )
            )
    active_execution = {
        ExecutionState.RUNNING,
        ExecutionState.EXECUTED,
        ExecutionState.VALIDATED,
        ExecutionState.REPRODUCED,
    }
    if plan.execution_state is ExecutionState.WAITING_FOR_APPROVAL:
        if plan.plan_state not in {PlanState.PREVIEWED, PlanState.VALIDATED}:
            findings.append(
                _finding(
                    "paper.execution.plan_not_previewed",
                    FindingSeverity.ERROR,
                    "execution_state",
                    "approval may be requested only for a previewed plan",
                )
            )
        if not plan.approval_refs:
            findings.append(
                _finding(
                    "paper.execution.approval_request_missing",
                    FindingSeverity.ERROR,
                    "approval_refs",
                    "waiting_for_approval requires an approval request receipt",
                )
            )
    if plan.execution_state in active_execution:
        if plan.plan_state not in {PlanState.PREVIEWED, PlanState.VALIDATED}:
            findings.append(
                _finding(
                    "paper.execution.plan_not_previewed",
                    FindingSeverity.ERROR,
                    "execution_state",
                    "execution requires a previewed or validated plan",
                )
            )
        if not plan.approval_refs:
            findings.append(
                _finding(
                    "paper.execution.approval_receipt_missing",
                    FindingSeverity.ERROR,
                    "approval_refs",
                    "active or completed execution requires an approval receipt",
                )
            )
        if not plan.execution_receipts:
            findings.append(
                _finding(
                    "paper.execution.receipt_missing",
                    FindingSeverity.ERROR,
                    "execution_receipts",
                    "active or completed execution requires a receipt",
                )
            )


def _validate_molecular_state_claims(
    findings: list[ResearchPlanFinding],
    system: MolecularSystemSpec,
    claims: dict[str, ProtocolClaim],
    *,
    system_count: int,
) -> None:
    facts: tuple[_ClaimFact, ...] = (
        ("charge", ("charge",), system.charge, None),
        (
            "multiplicity",
            ("multiplicity",),
            system.multiplicity,
            None,
        ),
    )
    state_fields = {"charge", "multiplicity"}
    bound_claims = tuple(
        claim
        for claim_id in system.claim_ids
        if (claim := claims.get(claim_id)) is not None
        and (
            claim.field_path.rsplit(".", 1)[-1] in state_fields
            or _is_missing_evidence_claim(claim)
        )
    )
    _validate_claim_fact_group(
        findings,
        owner_kind="system",
        owner_id=system.system_id,
        bound_claims=bound_claims,
        facts=facts,
        generic_owner="system",
        collection_name="molecular_systems",
        owner_count=system_count,
        binding_path=(
            f"molecular_systems.{system.system_id}.claim_ids"
        ),
        defer_by_binding=True,
    )


def _validate_project_setting_claims(
    findings: list[ResearchPlanFinding],
    project: ProjectConfigSpec,
    claims: dict[str, ProtocolClaim],
    *,
    project_count: int,
) -> None:
    expected = _project_claim_facts(project)
    bindings = {
        binding.setting_name: binding for binding in project.setting_claims
    }
    for setting_name, facts in expected.items():
        binding = bindings.get(setting_name)
        binding_path = (
            f"project_configs.{project.project_id}."
            f"setting_claims.{setting_name}"
        )
        if binding is None:
            findings.append(
                _finding(
                    "paper.project.claim_binding_missing",
                    FindingSeverity.ERROR,
                    binding_path,
                    (
                        f"project setting {setting_name!r} lacks a claim "
                        "binding"
                    ),
                    (project.project_id,),
                )
            )
            continue
        bound_claims = tuple(
            claim
            for claim_id in binding.claim_ids
            if (claim := claims.get(claim_id)) is not None
        )
        _validate_claim_fact_group(
            findings,
            owner_kind="project",
            owner_id=project.project_id,
            bound_claims=bound_claims,
            facts=facts,
            generic_owner="project",
            collection_name="project_configs",
            owner_count=project_count,
            binding_path=binding_path,
            defer_by_binding=True,
            skip_if_no_bound=True,
        )

    for setting in project.additional_settings:
        bound_claims = tuple(
            claim
            for claim_id in setting.claim_ids
            if (claim := claims.get(claim_id)) is not None
        )
        _validate_claim_fact_group(
            findings,
            owner_kind="project",
            owner_id=project.project_id,
            bound_claims=bound_claims,
            facts=(
                (
                    f"additional_settings.{setting.name}",
                    (f"additional_settings.{setting.name}", setting.name),
                    setting.value,
                    setting.units,
                ),
            ),
            generic_owner="project",
            collection_name="project_configs",
            owner_count=project_count,
            binding_path=(
                f"project_configs.{project.project_id}."
                f"additional_settings.{setting.name}.claim_ids"
            ),
            defer_by_binding=True,
            skip_if_no_bound=True,
        )


def _project_claim_facts(
    project: ProjectConfigSpec,
) -> dict[str, tuple[_ClaimFact, ...]]:
    facts: dict[str, tuple[_ClaimFact, ...]] = {
        "program": (
            ("program", ("program",), project.program.value, None),
        ),
        "program_version": (
            (
                "program_version",
                ("program_version",),
                project.program_version,
                None,
            ),
        ),
        "method": (("method", ("method",), project.method, None),),
    }
    if project.basis_assignments:
        facts["basis"] = _assignment_claim_facts(
            "basis", project.basis_assignments
        )
    if project.ecp_assignments:
        facts["ecp"] = _assignment_claim_facts(
            "ecp", project.ecp_assignments
        )
    optional_scalars: tuple[tuple[str, ClaimScalar | None], ...] = (
        ("dispersion", project.dispersion),
        ("integration_grid", project.integration_grid),
        ("scf_convergence", project.scf_convergence),
        ("geometry_convergence", project.geometry_convergence),
        ("standard_state", project.standard_state),
    )
    for setting_name, value in optional_scalars:
        if value is not None:
            facts[setting_name] = (
                (setting_name, (setting_name,), value, None),
            )
    if project.solvent is not None:
        facts["solvent"] = (
            (
                "solvent.model",
                ("solvent.model", "solvent_model"),
                project.solvent.model,
                None,
            ),
            (
                "solvent.solvent_id",
                ("solvent.solvent_id", "solvent_id"),
                project.solvent.solvent_id,
                None,
            ),
        )
    if project.temperature_kelvin is not None:
        facts["temperature_kelvin"] = (
            (
                "temperature_kelvin",
                ("temperature_kelvin",),
                project.temperature_kelvin,
                "K",
            ),
        )
    return facts


def _assignment_claim_facts(
    setting_name: str,
    assignments: tuple[SelectorAssignment, ...],
) -> tuple[_ClaimFact, ...]:
    facts: list[_ClaimFact] = []
    for index, assignment in enumerate(assignments):
        leaf_paths = [
            f"{setting_name}_assignments.{index}",
            f"{setting_name}_assignments.{index}.value",
        ]
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_:\-]*", assignment.selector):
            leaf_paths.extend(
                (
                    f"{setting_name}.{assignment.selector}",
                    f"{setting_name}_assignments.{assignment.selector}",
                    (
                        f"{setting_name}_assignments."
                        f"{assignment.selector}.value"
                    ),
                )
            )
        if len(assignments) == 1:
            leaf_paths.append(setting_name)
        facts.append(
            (
                f"{setting_name}[{assignment.selector}]",
                tuple(leaf_paths),
                assignment.value,
                None,
            )
        )
    return tuple(facts)


def _validate_claim_fact_group(
    findings: list[ResearchPlanFinding],
    *,
    owner_kind: str,
    owner_id: str,
    bound_claims: tuple[ProtocolClaim, ...],
    facts: tuple[_ClaimFact, ...],
    generic_owner: str,
    collection_name: str,
    owner_count: int,
    binding_path: str,
    defer_by_binding: bool,
    skip_if_no_bound: bool = False,
) -> None:
    if not bound_claims and skip_if_no_bound:
        return
    deferred = tuple(
        claim for claim in bound_claims if _is_missing_evidence_claim(claim)
    )
    resolved = tuple(
        claim for claim in bound_claims if claim not in deferred
    )
    matched_claim_ids: set[str] = set()
    for fact_name, leaf_paths, expected_value, expected_units in facts:
        allowed_paths = _allowed_claim_paths(
            generic_owner=generic_owner,
            collection_name=collection_name,
            owner_id=owner_id,
            leaf_paths=leaf_paths,
            owner_count=owner_count,
        )
        matched = tuple(
            claim for claim in resolved if claim.field_path in allowed_paths
        )
        matched_claim_ids.update(claim.claim_id for claim in matched)
        deferred_for_fact = defer_by_binding or any(
            _claim_targets_fact(claim, leaf_paths) for claim in deferred
        )
        if not matched and not (deferred and deferred_for_fact):
            findings.append(
                _finding(
                    f"paper.{owner_kind}.claim_path_missing",
                    FindingSeverity.ERROR,
                    binding_path,
                    (
                        f"no bound claim has an allowed path for "
                        f"{fact_name!r}"
                    ),
                    (owner_id,),
                )
            )
        for claim in matched:
            _validate_bound_claim(
                findings,
                owner_kind=owner_kind,
                owner_id=owner_id,
                claim=claim,
                fact_name=fact_name,
                expected_value=expected_value,
                expected_units=expected_units,
            )

    for claim in resolved:
        if claim.claim_id not in matched_claim_ids:
            findings.append(
                _finding(
                    f"paper.{owner_kind}.claim_path_mismatch",
                    FindingSeverity.ERROR,
                    f"claims.{claim.claim_id}.field_path",
                    "bound claim path does not identify the bound fact",
                    (owner_id, claim.claim_id),
                )
            )


def _allowed_claim_paths(
    *,
    generic_owner: str,
    collection_name: str,
    owner_id: str,
    leaf_paths: tuple[str, ...],
    owner_count: int,
) -> frozenset[str]:
    paths = {
        f"{collection_name}.{owner_id}.{leaf_path}"
        for leaf_path in leaf_paths
    }
    if owner_count == 1:
        paths.update(
            f"{generic_owner}.{leaf_path}" for leaf_path in leaf_paths
        )
    return frozenset(paths)


def _is_missing_evidence_claim(claim: ProtocolClaim) -> bool:
    return (
        claim.criticality is ClaimCriticality.CRITICAL
        and claim.value is None
        and claim.epistemic_status
        in {EpistemicStatus.UNKNOWN, EpistemicStatus.CONFLICT}
    )


def _claim_targets_fact(
    claim: ProtocolClaim,
    leaf_paths: tuple[str, ...],
) -> bool:
    claimed_leaf = claim.field_path.rsplit(".", 1)[-1]
    return any(
        claimed_leaf == leaf_path.rsplit(".", 1)[-1]
        for leaf_path in leaf_paths
    )


def _validate_bound_claim(
    findings: list[ResearchPlanFinding],
    *,
    owner_kind: str,
    owner_id: str,
    claim: ProtocolClaim,
    fact_name: str,
    expected_value: ClaimScalar,
    expected_units: str | None,
) -> None:
    if claim.criticality is not ClaimCriticality.CRITICAL:
        findings.append(
            _finding(
                f"paper.{owner_kind}.claim_criticality_mismatch",
                FindingSeverity.ERROR,
                f"claims.{claim.claim_id}.criticality",
                f"bound fact {fact_name!r} requires a critical claim",
                (owner_id, claim.claim_id),
            )
        )
    if claim.epistemic_status in {
        EpistemicStatus.UNKNOWN,
        EpistemicStatus.CONFLICT,
        EpistemicStatus.NOT_APPLICABLE,
    }:
        findings.append(
            _finding(
                f"paper.{owner_kind}.claim_epistemic_status_invalid",
                FindingSeverity.ERROR,
                f"claims.{claim.claim_id}.epistemic_status",
                (
                    f"{claim.epistemic_status.value} cannot evidence an "
                    f"asserted {fact_name!r} value"
                ),
                (owner_id, claim.claim_id),
            )
        )
        return
    if not _claim_values_equal(claim.value, expected_value):
        findings.append(
            _finding(
                f"paper.{owner_kind}.claim_value_mismatch",
                FindingSeverity.ERROR,
                f"claims.{claim.claim_id}.value",
                (
                    f"bound claim value {claim.value!r} does not match "
                    f"{fact_name!r} value {expected_value!r}"
                ),
                (owner_id, claim.claim_id),
            )
        )
    if _canonical_claim_unit(claim.units) != _canonical_claim_unit(
        expected_units
    ):
        findings.append(
            _finding(
                f"paper.{owner_kind}.claim_units_mismatch",
                FindingSeverity.ERROR,
                f"claims.{claim.claim_id}.units",
                (
                    f"bound claim units {claim.units!r} do not match "
                    f"{fact_name!r} units {expected_units!r}"
                ),
                (owner_id, claim.claim_id),
            )
        )


def _claim_values_equal(observed: ClaimScalar | None, expected: ClaimScalar) -> bool:
    if isinstance(observed, bool) or isinstance(expected, bool):
        return isinstance(observed, bool) and isinstance(expected, bool) and (
            observed is expected
        )
    if isinstance(observed, (int, float)) and isinstance(
        expected, (int, float)
    ):
        return float(observed) == float(expected)
    if isinstance(observed, str) and isinstance(expected, str):
        return observed.casefold() == expected.casefold()
    return False


def _canonical_claim_unit(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.casefold().split())
    return {
        "kelvin": "k",
        "degree kelvin": "k",
        "degrees kelvin": "k",
        "°k": "k",
    }.get(normalized, normalized)


def _check_claim_ids(
    findings: list[ResearchPlanFinding],
    claim_ids: tuple[str, ...],
    claims: dict[str, ProtocolClaim],
    field_path: str,
    owner_id: str,
) -> None:
    missing = sorted(set(claim_ids).difference(claims))
    if missing:
        findings.append(
            _finding(
                "paper.claim.reference_unbound",
                FindingSeverity.ERROR,
                field_path,
                "scientific contract refers to unknown protocol claims",
                (owner_id, *missing),
            )
        )


def _all_claim_locators(claim: ProtocolClaim) -> tuple[ClaimSourceLocator, ...]:
    return (
        *claim.source_locators,
        *(
            locator
            for alternative in claim.alternatives
            for locator in alternative.source_locators
        ),
    )


def _has_workflow_cycle(
    workflows: dict[str, CommandWorkflowBinding],
) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(workflow_id: str) -> bool:
        if workflow_id in visiting:
            return True
        if workflow_id in visited:
            return False
        visiting.add(workflow_id)
        binding = workflows[workflow_id]
        for dependency in binding.dependency_workflow_ids:
            if dependency in workflows and visit(dependency):
                return True
        visiting.remove(workflow_id)
        visited.add(workflow_id)
        return False

    return any(visit(workflow_id) for workflow_id in workflows)


def _canonical_source_locators(
    value: tuple[ClaimSourceLocator, ...],
) -> tuple[ClaimSourceLocator, ...]:
    keys = [(item.artifact_id, item.locator) for item in value]
    if len(keys) != len(set(keys)):
        raise ValueError("claim source locators must be unique")
    return tuple(sorted(value, key=lambda item: (item.artifact_id, item.locator)))


def _content_addressed_receipt_sha256(contract: BaseModel) -> str:
    return _sha256_json(
        contract.model_dump(
            mode="json",
            exclude={"receipt_sha256"},
        )
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            _jsonable(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _looks_like_host_path(value: str) -> bool:
    stripped = value.strip()
    return bool(
        stripped.startswith(("/", "~", "\\\\"))
        or stripped.casefold().startswith("file:")
        or re.match(r"^[A-Za-z]:[\\/]", stripped)
    )


def _canonical_setting_names(
    value: tuple[str, ...], field_name: str
) -> tuple[str, ...]:
    for item in value:
        if re.fullmatch(_SETTING_NAME, item) is None:
            raise ValueError(f"{field_name} contains an invalid value")
    _require_unique_ids(value, field_name)
    return tuple(sorted(value))


def _normalized_scientific_value(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _canonical_identifiers(
    value: tuple[str, ...], field_name: str
) -> tuple[str, ...]:
    for item in value:
        if not re.fullmatch(_IDENTIFIER, item):
            raise ValueError(f"{field_name} contains an invalid identifier")
    _require_unique_ids(value, field_name)
    return tuple(sorted(value))


def _require_unique_ids(values: Any, field_name: str) -> None:
    materialized = tuple(values)
    if len(materialized) != len(set(materialized)):
        raise ValueError(f"{field_name} values must be unique")


def _finding(
    rule_id: str,
    severity: FindingSeverity,
    field_path: str,
    message: str,
    related_ids: tuple[str, ...] = (),
) -> ResearchPlanFinding:
    return ResearchPlanFinding(
        rule_id=rule_id,
        severity=severity,
        field_path=field_path,
        message=message,
        related_ids=related_ids,
    )


__all__ = [
    "ArtifactDigestRef",
    "ClaimAlternative",
    "ClaimCriticality",
    "ClaimEvidenceRef",
    "ClaimReadinessAssessment",
    "ClaimSourceLocator",
    "ClaimValidationPurpose",
    "ClaimValidationReceipt",
    "CLAIM_VALIDATION_RECEIPT_SCHEMA_VERSION",
    "CommandWorkflowBinding",
    "ContractDigestRef",
    "DomainKnowledgeBinding",
    "EpistemicStatus",
    "ExecutionState",
    "FindingSeverity",
    "MolecularConstraintRef",
    "MolecularFragment",
    "MolecularSystemSpec",
    "PAPER_RESEARCH_PLAN_SCHEMA_VERSION",
    "PAPER_SOURCE_BUNDLE_SCHEMA_VERSION",
    "PROJECT_CONFIG_SCHEMA_VERSION",
    "PROJECT_LOADER_RECEIPT_SCHEMA_VERSION",
    "MOLECULAR_SYSTEM_SCHEMA_VERSION",
    "PaperResearchPlan",
    "PaperResearchPlanValidation",
    "PaperResearchValidationContext",
    "PaperSourceBundle",
    "PaperReviewRole",
    "PlanReviewGateRef",
    "PlanState",
    "PlanValidationStatus",
    "Program",
    "ProjectConfigSpec",
    "ProjectLoaderValidationReceipt",
    "ProjectSetting",
    "ProjectValidationRecord",
    "ProtocolClaim",
    "ReadinessState",
    "RequiredProtocolCoverage",
    "RequiredProtocolField",
    "REQUIRED_PROTOCOL_COVERAGE_SCHEMA_VERSION",
    "ResearchGraphKind",
    "ResearchGraphRef",
    "ResearchPlanFinding",
    "ReviewValidationReceipt",
    "REVIEW_VALIDATION_RECEIPT_SCHEMA_VERSION",
    "SelectorAssignment",
    "SettingClaimBinding",
    "SolventSpec",
    "SourceAccess",
    "SourceArtifact",
    "SourceArtifactKind",
    "ScientificDomain",
    "WorkflowPreviewValidationReceipt",
    "WORKFLOW_PREVIEW_RECEIPT_SCHEMA_VERSION",
    "assess_claim_readiness",
    "build_claim_validation_receipt",
    "build_project_loader_validation_record",
    "build_review_validation_receipt",
    "build_workflow_preview_validation_receipt",
    "canonical_contract_json",
    "claim_validation_result_sha256",
    "contract_sha256",
    "validate_paper_research_plan",
]
