"""External contracts for preregistered novel settings challenges.

The challenge artifact is deliberately data, not a Python ``CASES`` table.
It freezes immutable settings inputs and deterministic expected outcomes before
any model transport.  Loading the artifact performs no model, network, project,
preview, engine, or scheduler action.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from chemsmart.agent.harness.basis_sets.request_evidence import (
    BasisEvidenceRole,
    BasisEvidenceState,
)
from chemsmart.agent.harness.scientific_settings.contracts import (
    ScientificProgram,
)
from chemsmart.agent.harness.scientific_settings.contracts_v2 import (
    ScientificSettingsInventoryV2,
    ScientificSettingsRegistryV2,
)
from chemsmart.agent.harness.scientific_settings.lookup_contracts_v2 import (
    SettingMatchKindV2,
    SettingResolutionStatusV2,
    SettingResolutionV2,
)
from chemsmart.agent.harness.scientific_settings.registry_v2 import (
    load_populated_scientific_settings_inventories_v2,
    load_populated_scientific_settings_registry_v2,
)
from chemsmart.agent.knowledge_packs import (
    default_domain_knowledge_catalog,
    domain_knowledge_catalog_sha256,
)
from chemsmart.agent.knowledge_packs.catalog import (
    KnowledgePackActivationReceiptV1,
    KnowledgePackSelectionStatus,
)
from chemsmart.agent.project_readiness import (
    ProjectReadinessReceiptV1,
    TypedProjectSupportStatus,
)
from chemsmart.agent.settings_registry_stress_receipts import (
    RegistryStressReadiness,
)


NOVEL_SETTINGS_CHALLENGE_SCHEMA_VERSION = (
    "chemsmart.novel-settings-challenge.v1"
)
NOVEL_SETTINGS_CHALLENGE_CASE_SCHEMA_VERSION = (
    "chemsmart.novel-settings-challenge-case.v1"
)
NOVEL_SETTINGS_CHALLENGE_BINDINGS_SCHEMA_VERSION = (
    "chemsmart.novel-settings-challenge-bindings.v1"
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_SETTING_PATH = r"^[a-z][a-z0-9_.-]{0,191}$"
_JOB_KIND = r"^[a-z][a-z0-9_-]{0,79}$"
_RULE_ID = r"^[a-z][a-z0-9_.-]+$"
_SHA1 = r"^[0-9a-f]{40}$"
_SHA256 = r"^[0-9a-f]{64}$"
_SEMVER = (
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z.-]+)?$"
)
_ENGINE_VERSION = r"^[0-9A-Za-z][0-9A-Za-z._-]{0,79}$"
_ELEMENT = r"^[A-Z][a-z]?$"
_SAFE_TEXT = re.compile(r"^[^\x00-\x1f\x7f]+$")


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _jsonable(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
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


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _ordered_unique(value: tuple[str, ...], label: str) -> tuple[str, ...]:
    if value != tuple(sorted(set(value))):
        raise ValueError(f"{label} must be unique and sorted")
    return value


def _canonical_rule_ids(value: tuple[str, ...]) -> tuple[str, ...]:
    if any(re.fullmatch(_RULE_ID, item) is None for item in value):
        raise ValueError("rule ID is invalid")
    return _ordered_unique(value, "rule IDs")


def _safe_text(value: str, label: str) -> str:
    if not _SAFE_TEXT.fullmatch(value):
        raise ValueError(f"{label} contains control characters")
    return value


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class NovelChallengeTaskKind(str, Enum):
    FREQUENCY = "frequency"
    GEOMETRY_OPTIMIZATION = "geometry_optimization"
    HESSIAN = "hessian"
    SINGLE_POINT = "single_point"


class NovelChallengeLifecycleState(str, Enum):
    """Highest public lifecycle state available to this settings-only slice."""

    PLANNED = "planned"


class NovelOneFactorHypothesisV1(_Contract):
    hypothesis_id: str = Field(pattern=_IDENTIFIER)
    baseline_condition_id: str = Field(pattern=_IDENTIFIER)
    intervention_condition_id: str = Field(pattern=_IDENTIFIER)
    changed_factor_id: str = Field(pattern=_IDENTIFIER)
    held_constant_dimensions: tuple[str, ...] = Field(min_length=1)
    expected_effect: str = Field(min_length=1, max_length=1000)

    @field_validator("held_constant_dimensions")
    @classmethod
    def _canonical_dimensions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _ordered_unique(value, "held-constant dimensions")

    @field_validator("expected_effect")
    @classmethod
    def _safe_expected_effect(cls, value: str) -> str:
        return _safe_text(value, "expected effect")

    @model_validator(mode="after")
    def _one_factor_is_observable(self) -> "NovelOneFactorHypothesisV1":
        if self.baseline_condition_id == self.intervention_condition_id:
            raise ValueError("one-factor conditions must differ")
        return self


class NovelSettingLookupExpectationV1(_Contract):
    lookup_id: str = Field(pattern=_IDENTIFIER)
    setting_path: str = Field(pattern=_SETTING_PATH)
    requested_value: str = Field(min_length=1, max_length=300)
    job_kind: str = Field(pattern=_JOB_KIND)
    allow_fuzzy_candidates: bool = False
    expected_status: SettingResolutionStatusV2
    expected_match_kind: SettingMatchKindV2
    expected_canonical_value: str | None = Field(default=None, max_length=160)
    expected_reason_rule_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("requested_value", "expected_canonical_value")
    @classmethod
    def _safe_literals(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value, "setting literal")

    @field_validator("expected_reason_rule_ids")
    @classmethod
    def _canonical_rules(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_rule_ids(value)

    @model_validator(mode="after")
    def _resolution_expectation_is_coherent(
        self,
    ) -> "NovelSettingLookupExpectationV1":
        entry_bound = self.expected_status in {
            SettingResolutionStatusV2.EXACT_REGISTERED,
            SettingResolutionStatusV2.BLOCKED_VALIDATION_COVERAGE,
            SettingResolutionStatusV2.INCOMPATIBLE,
        }
        if entry_bound != (self.expected_canonical_value is not None):
            raise ValueError(
                "entry-bound registry outcomes require one canonical value"
            )
        if self.expected_status is SettingResolutionStatusV2.UNKNOWN_UNVERIFIED:
            if self.expected_match_kind is not SettingMatchKindV2.NONE:
                raise ValueError("unknown setting must use match kind none")
        return self


class NovelBasisEvidenceExpectationV1(_Contract):
    basis_literal: str = Field(min_length=1, max_length=160)
    role: BasisEvidenceRole
    elements: tuple[str, ...] = Field(min_length=1)
    expected_state: BasisEvidenceState
    expected_catalog_role: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_-]{0,79}$",
    )
    expected_reason_rule_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("basis_literal")
    @classmethod
    def _safe_basis(cls, value: str) -> str:
        return _safe_text(value, "basis literal")

    @field_validator("elements")
    @classmethod
    def _canonical_elements(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(re.fullmatch(_ELEMENT, item) is None for item in value):
            raise ValueError("basis evidence contains an invalid element")
        return _ordered_unique(value, "basis evidence elements")

    @field_validator("expected_reason_rule_ids")
    @classmethod
    def _canonical_rules(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_rule_ids(value)

    @model_validator(mode="after")
    def _basis_state_is_coherent(self) -> "NovelBasisEvidenceExpectationV1":
        if self.expected_state is BasisEvidenceState.VERIFIED:
            if self.expected_catalog_role != self.role.value:
                raise ValueError("verified basis evidence must match its role")
        elif self.expected_state is BasisEvidenceState.CONFLICT:
            if self.expected_catalog_role == self.role.value:
                raise ValueError("role-conflict evidence must expose another role")
        return self


class NovelImmutableSettingsV1(_Contract):
    functional: str | None = Field(default=None, max_length=300)
    basis: str | None = Field(default=None, max_length=300)
    dispersion: str | None = Field(default=None, max_length=160)
    integration_grid: str | None = Field(default=None, max_length=160)
    heavy_elements: tuple[str, ...] = ()
    heavy_elements_basis: str | None = Field(default=None, max_length=300)
    light_elements_basis: str | None = Field(default=None, max_length=300)
    solvent_model: str | None = Field(default=None, max_length=160)
    solvent_id: str | None = Field(default=None, max_length=160)
    gfn_version: str | None = Field(default=None, max_length=160)
    optimization_level: str | None = Field(default=None, max_length=160)
    freq: bool | None = None
    solv_freq: bool | None = None

    @field_validator(
        "functional",
        "basis",
        "dispersion",
        "integration_grid",
        "heavy_elements_basis",
        "light_elements_basis",
        "solvent_model",
        "solvent_id",
        "gfn_version",
        "optimization_level",
    )
    @classmethod
    def _safe_optional_setting(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value, "immutable setting")

    @field_validator("heavy_elements")
    @classmethod
    def _canonical_heavy_elements(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if any(re.fullmatch(_ELEMENT, item) is None for item in value):
            raise ValueError("heavy-elements setting contains an invalid symbol")
        return _ordered_unique(value, "heavy elements")


class NovelChallengeInputV1(_Contract):
    program: ScientificProgram
    engine_version: str = Field(pattern=_ENGINE_VERSION)
    task_kind: NovelChallengeTaskKind
    project_job_kind: Literal["hess", "opt", "sp"]
    settings: NovelImmutableSettingsV1
    setting_lookups: tuple[NovelSettingLookupExpectationV1, ...] = Field(
        min_length=1
    )
    basis_evidence: tuple[NovelBasisEvidenceExpectationV1, ...] = ()
    coordinate_artifact_ids: tuple[str, ...] = ()

    @field_validator("setting_lookups")
    @classmethod
    def _canonical_lookups(
        cls,
        value: tuple[NovelSettingLookupExpectationV1, ...],
    ) -> tuple[NovelSettingLookupExpectationV1, ...]:
        ids = tuple(item.lookup_id for item in value)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("setting lookup IDs must be unique and sorted")
        return value

    @field_validator("basis_evidence")
    @classmethod
    def _canonical_basis_evidence(
        cls,
        value: tuple[NovelBasisEvidenceExpectationV1, ...],
    ) -> tuple[NovelBasisEvidenceExpectationV1, ...]:
        keys = tuple((item.basis_literal.casefold(), item.role.value) for item in value)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("basis evidence requests must be unique and sorted")
        return value

    @field_validator("coordinate_artifact_ids")
    @classmethod
    def _coordinates_remain_absent(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value:
            raise ValueError("novel settings challenges cannot bind coordinates")
        return value

    @model_validator(mode="after")
    def _program_fields_are_separate(self) -> "NovelChallengeInputV1":
        settings = self.settings
        if self.program is ScientificProgram.XTB:
            if settings.basis is not None or settings.functional is not None:
                raise ValueError("xTB challenge input cannot invent orbital DFT fields")
            if settings.gfn_version is None:
                raise ValueError("xTB challenge input requires an explicit GFN literal")
        elif settings.gfn_version is not None:
            raise ValueError("Gaussian/ORCA challenge cannot carry an xTB method")
        return self


class NovelLoaderExpectationV1(_Contract):
    expected_status: TypedProjectSupportStatus
    expected_rule_ids: tuple[str, ...] = ()
    semantic_fields_to_preserve: tuple[str, ...] = Field(min_length=1)
    final_readiness_authority: Literal[False] = False

    @field_validator("expected_rule_ids")
    @classmethod
    def _canonical_rules(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_rule_ids(value)

    @field_validator("semantic_fields_to_preserve")
    @classmethod
    def _canonical_fields(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(re.fullmatch(_SETTING_PATH, item) is None for item in value):
            raise ValueError("semantic preservation field is invalid")
        return _ordered_unique(value, "semantic preservation fields")

    @model_validator(mode="after")
    def _loader_status_is_coherent(self) -> "NovelLoaderExpectationV1":
        supported = (
            self.expected_status is TypedProjectSupportStatus.TYPED_PROJECT_SUPPORTED
        )
        if supported == bool(self.expected_rule_ids):
            raise ValueError(
                "supported loader outcome has no rules; blocked outcome has rules"
            )
        return self


class NovelKnowledgeExpectationV1(_Contract):
    expected_status: KnowledgePackSelectionStatus
    selected_pack_ids: tuple[str, ...] = ()
    expected_rule_ids: tuple[str, ...] = ()
    model_visible_exposure_requested: bool
    model_visible_exposure_expected: bool
    can_certify_registry_validity: Literal[False] = False
    can_set_readiness: Literal[False] = False

    @field_validator("selected_pack_ids")
    @classmethod
    def _canonical_packs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(re.fullmatch(_IDENTIFIER, item) is None for item in value):
            raise ValueError("selected knowledge-pack ID is invalid")
        return _ordered_unique(value, "selected knowledge-pack IDs")

    @field_validator("expected_rule_ids")
    @classmethod
    def _canonical_rules(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_rule_ids(value)

    @model_validator(mode="after")
    def _knowledge_selection_is_coherent(self) -> "NovelKnowledgeExpectationV1":
        selected = self.expected_status is KnowledgePackSelectionStatus.SELECTED
        if selected != bool(self.selected_pack_ids):
            raise ValueError("selected knowledge status must bind selected packs")
        expected_exposure = bool(
            selected and self.model_visible_exposure_requested
        )
        if self.model_visible_exposure_expected != expected_exposure:
            raise ValueError("knowledge exposure does not match selection")
        return self


class NovelExpectedOutcomeV1(_Contract):
    loader: NovelLoaderExpectationV1
    knowledge: NovelKnowledgeExpectationV1
    readiness: RegistryStressReadiness
    blocking_rule_ids: tuple[str, ...] = ()
    deterministic_host_is_final_authority: Literal[True] = True

    @field_validator("blocking_rule_ids")
    @classmethod
    def _canonical_rules(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_rule_ids(value)

    @model_validator(mode="after")
    def _readiness_matches_blockers(self) -> "NovelExpectedOutcomeV1":
        candidate = self.readiness is RegistryStressReadiness.PROJECT_CANDIDATE
        if candidate == bool(self.blocking_rule_ids):
            raise ValueError("project candidate has no blockers; blocked state has blockers")
        return self


class NovelChallengeSafetyCeilingV1(_Contract):
    maximum_lifecycle_state: Literal[
        NovelChallengeLifecycleState.PLANNED
    ] = NovelChallengeLifecycleState.PLANNED
    coordinates_present: Literal[False] = False
    project_writes_allowed: Literal[False] = False
    safe_preview_allowed: Literal[False] = False
    native_input_authoring_allowed: Literal[False] = False
    chemistry_engine_execution_allowed: Literal[False] = False
    hpc_execution_allowed: Literal[False] = False
    live_model_transport_in_fixture_loader: Literal[False] = False


class NovelSettingsChallengeBindingsV1(_Contract):
    schema_version: Literal[
        NOVEL_SETTINGS_CHALLENGE_BINDINGS_SCHEMA_VERSION
    ] = NOVEL_SETTINGS_CHALLENGE_BINDINGS_SCHEMA_VERSION
    baseline_source_commit_sha1: str = Field(pattern=_SHA1)
    settings_registry_source_revision_sha1: str = Field(pattern=_SHA1)
    cli_schema_sha256: str = Field(pattern=_SHA256)
    settings_registry_sha256: str = Field(pattern=_SHA256)
    settings_inventory_sha256: str = Field(pattern=_SHA256)
    settings_inventory_artifact_sha256: str = Field(pattern=_SHA256)
    bse_catalog_artifact_sha256: str = Field(pattern=_SHA256)
    bse_catalog_content_sha256: str = Field(pattern=_SHA256)
    settings_registry_schema_sha256: str = Field(pattern=_SHA256)
    settings_resolution_schema_sha256: str = Field(pattern=_SHA256)
    project_readiness_schema_sha256: str = Field(pattern=_SHA256)
    knowledge_activation_schema_sha256: str = Field(pattern=_SHA256)
    knowledge_catalog_sha256: str = Field(pattern=_SHA256)
    contract_schema_sha256: str = Field(pattern=_SHA256)
    binding_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _binding_is_content_addressed(self) -> "NovelSettingsChallengeBindingsV1":
        if self.binding_sha256 != novel_settings_bindings_sha256(self):
            raise ValueError("novel-settings evidence binding digest mismatch")
        return self


class NovelSettingsChallengeCaseV1(_Contract):
    schema_version: Literal[
        NOVEL_SETTINGS_CHALLENGE_CASE_SCHEMA_VERSION
    ] = NOVEL_SETTINGS_CHALLENGE_CASE_SCHEMA_VERSION
    case_id: str = Field(pattern=_IDENTIFIER)
    hypothesis: NovelOneFactorHypothesisV1
    immutable_input: NovelChallengeInputV1
    expected_outcome: NovelExpectedOutcomeV1
    deterministic_oracle_ids: tuple[str, ...] = Field(min_length=1)
    novelty_reason: str = Field(min_length=1, max_length=1200)
    evidence_binding_sha256: str = Field(pattern=_SHA256)
    contract_schema_sha256: str = Field(pattern=_SHA256)
    safety_ceiling: NovelChallengeSafetyCeilingV1 = Field(
        default_factory=NovelChallengeSafetyCeilingV1
    )
    case_sha256: str = Field(pattern=_SHA256)

    @field_validator("deterministic_oracle_ids")
    @classmethod
    def _canonical_oracles(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(re.fullmatch(_RULE_ID, item) is None for item in value):
            raise ValueError("deterministic oracle ID is invalid")
        return _ordered_unique(value, "deterministic oracle IDs")

    @field_validator("novelty_reason")
    @classmethod
    def _safe_novelty(cls, value: str) -> str:
        return _safe_text(value, "novelty reason")

    @model_validator(mode="after")
    def _case_is_content_addressed(self) -> "NovelSettingsChallengeCaseV1":
        if self.case_sha256 != novel_settings_case_sha256(self):
            raise ValueError("novel-settings case digest mismatch")
        return self


class NovelSettingsChallengeV1(_Contract):
    schema_version: Literal[NOVEL_SETTINGS_CHALLENGE_SCHEMA_VERSION] = (
        NOVEL_SETTINGS_CHALLENGE_SCHEMA_VERSION
    )
    challenge_id: str = Field(pattern=_IDENTIFIER)
    challenge_version: str = Field(pattern=_SEMVER)
    purpose: str = Field(min_length=1, max_length=1200)
    bindings: NovelSettingsChallengeBindingsV1
    cases: tuple[NovelSettingsChallengeCaseV1, ...] = Field(min_length=1)
    case_set_sha256: str = Field(pattern=_SHA256)
    maximum_lifecycle_state: Literal[
        NovelChallengeLifecycleState.PLANNED
    ] = NovelChallengeLifecycleState.PLANNED
    challenge_sha256: str = Field(pattern=_SHA256)

    @field_validator("purpose")
    @classmethod
    def _safe_purpose(cls, value: str) -> str:
        return _safe_text(value, "challenge purpose")

    @field_validator("cases")
    @classmethod
    def _canonical_cases(
        cls,
        value: tuple[NovelSettingsChallengeCaseV1, ...],
    ) -> tuple[NovelSettingsChallengeCaseV1, ...]:
        ids = tuple(item.case_id for item in value)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("challenge cases must be unique and sorted")
        return value

    @model_validator(mode="after")
    def _challenge_is_content_addressed(self) -> "NovelSettingsChallengeV1":
        if any(
            item.evidence_binding_sha256 != self.bindings.binding_sha256
            for item in self.cases
        ):
            raise ValueError("challenge case uses another evidence binding")
        if any(
            item.contract_schema_sha256 != self.bindings.contract_schema_sha256
            for item in self.cases
        ):
            raise ValueError("challenge case uses another contract schema")
        expected_case_set = _sha256_json(
            [
                {"case_id": item.case_id, "case_sha256": item.case_sha256}
                for item in self.cases
            ]
        )
        if self.case_set_sha256 != expected_case_set:
            raise ValueError("challenge case-set digest mismatch")
        if self.challenge_sha256 != novel_settings_challenge_sha256(self):
            raise ValueError("novel-settings challenge digest mismatch")
        return self


def novel_settings_case_sha256(
    case: NovelSettingsChallengeCaseV1 | Mapping[str, Any],
) -> str:
    return _content_sha256(case, "case_sha256")


def novel_settings_bindings_sha256(
    bindings: NovelSettingsChallengeBindingsV1 | Mapping[str, Any],
) -> str:
    return _content_sha256(bindings, "binding_sha256")


def novel_settings_challenge_sha256(
    challenge: NovelSettingsChallengeV1 | Mapping[str, Any],
) -> str:
    return _content_sha256(challenge, "challenge_sha256")


def novel_settings_contract_schema_sha256() -> str:
    """Hash the public V1 JSON schema independently of any fixture value."""

    return _sha256_json(NovelSettingsChallengeV1.model_json_schema())


def current_novel_settings_bindings_v1(
    *,
    baseline_source_commit_sha1: str,
    repository_root: str | Path | None = None,
) -> NovelSettingsChallengeBindingsV1:
    """Build current deterministic source/schema bindings without transport."""

    if re.fullmatch(_SHA1, baseline_source_commit_sha1) is None:
        raise ValueError("baseline source commit must be a SHA-1")
    root = (
        Path(repository_root).resolve()
        if repository_root is not None
        else Path(__file__).resolve().parents[4]
    )
    registry = load_populated_scientific_settings_registry_v2()
    inventories = load_populated_scientific_settings_inventories_v2(
        repository_root=root
    )
    if len(inventories) != 1 or len(registry.inventories) != 1:
        raise ValueError("novel-settings V1 requires exactly one bound inventory")
    inventory = inventories[0]
    descriptor = registry.inventories[0]
    bse_path = (
        root
        / "chemsmart/agent/harness/basis_sets/bse_basis_catalog.json"
    )
    bse_bytes = bse_path.read_bytes()
    bse_body = json.loads(
        bse_bytes.decode("utf-8"),
        object_pairs_hook=_reject_duplicate_json_keys,
    )
    catalog = default_domain_knowledge_catalog()
    body: dict[str, Any] = {
        "schema_version": NOVEL_SETTINGS_CHALLENGE_BINDINGS_SCHEMA_VERSION,
        "baseline_source_commit_sha1": baseline_source_commit_sha1,
        "settings_registry_source_revision_sha1": registry.source_revision,
        "cli_schema_sha256": registry.cli_schema_sha256,
        "settings_registry_sha256": registry.registry_sha256,
        "settings_inventory_sha256": inventory.inventory_sha256,
        "settings_inventory_artifact_sha256": descriptor.artifact_sha256,
        "bse_catalog_artifact_sha256": hashlib.sha256(bse_bytes).hexdigest(),
        "bse_catalog_content_sha256": _sha256_json(bse_body),
        "settings_registry_schema_sha256": _sha256_json(
            ScientificSettingsRegistryV2.model_json_schema()
        ),
        "settings_resolution_schema_sha256": _sha256_json(
            SettingResolutionV2.model_json_schema()
        ),
        "project_readiness_schema_sha256": _sha256_json(
            ProjectReadinessReceiptV1.model_json_schema()
        ),
        "knowledge_activation_schema_sha256": _sha256_json(
            KnowledgePackActivationReceiptV1.model_json_schema()
        ),
        "knowledge_catalog_sha256": domain_knowledge_catalog_sha256(catalog),
        "contract_schema_sha256": novel_settings_contract_schema_sha256(),
        "binding_sha256": "0" * 64,
    }
    body["binding_sha256"] = novel_settings_bindings_sha256(body)
    return NovelSettingsChallengeBindingsV1.model_validate(body)


def load_novel_settings_challenge_v1(
    path: str | Path,
    *,
    verify_current_bindings: bool = True,
    repository_root: str | Path | None = None,
) -> NovelSettingsChallengeV1:
    """Load duplicate-free UTF-8 JSON and optionally replay source bindings."""

    artifact = Path(path)
    try:
        payload = json.loads(
            artifact.read_bytes().decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("novel-settings challenge is not valid UTF-8 JSON") from exc
    challenge = NovelSettingsChallengeV1.model_validate(payload)
    if verify_current_bindings:
        replayed = current_novel_settings_bindings_v1(
            baseline_source_commit_sha1=(
                challenge.bindings.baseline_source_commit_sha1
            ),
            repository_root=repository_root,
        )
        if replayed != challenge.bindings:
            raise ValueError("novel-settings source/schema bindings do not replay")
    return challenge


def _content_sha256(
    value: BaseModel | Mapping[str, Any],
    identity_field: str,
) -> str:
    payload = (
        value.model_dump(mode="json", exclude={identity_field})
        if isinstance(value, BaseModel)
        else {key: item for key, item in value.items() if key != identity_field}
    )
    return _sha256_json(payload)


__all__ = [
    "NOVEL_SETTINGS_CHALLENGE_BINDINGS_SCHEMA_VERSION",
    "NOVEL_SETTINGS_CHALLENGE_CASE_SCHEMA_VERSION",
    "NOVEL_SETTINGS_CHALLENGE_SCHEMA_VERSION",
    "NovelBasisEvidenceExpectationV1",
    "NovelChallengeInputV1",
    "NovelChallengeLifecycleState",
    "NovelChallengeSafetyCeilingV1",
    "NovelChallengeTaskKind",
    "NovelExpectedOutcomeV1",
    "NovelImmutableSettingsV1",
    "NovelKnowledgeExpectationV1",
    "NovelLoaderExpectationV1",
    "NovelOneFactorHypothesisV1",
    "NovelSettingLookupExpectationV1",
    "NovelSettingsChallengeBindingsV1",
    "NovelSettingsChallengeCaseV1",
    "NovelSettingsChallengeV1",
    "current_novel_settings_bindings_v1",
    "load_novel_settings_challenge_v1",
    "novel_settings_bindings_sha256",
    "novel_settings_case_sha256",
    "novel_settings_challenge_sha256",
    "novel_settings_contract_schema_sha256",
]
