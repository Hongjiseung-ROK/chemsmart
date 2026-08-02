"""Content-addressed, read-only authority for typed project support.

Registry discovery and a plausible model proposal do not establish that
ChemSmart can preserve a scientific setting in a project.  This module binds
the requested program, job, method, basis/ECP, dispersion, and solvent intent,
then delegates exclusively to the existing paper project renderer, real
project loader, and required-job semantic validation.

The authority writes no workspace project, performs no safe preview, and
starts no chemistry engine or scheduler.  Its affirmative status means only
``typed_project_supported`` within that deliberately narrow evidence scope.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from chemsmart.agent.harness.basis_sets.catalog import inspect_basis_elements
from chemsmart.agent.project_yaml import render_project_yaml


PROJECT_READINESS_SCHEMA_VERSION = "chemsmart.typed-project-readiness.v1"
PROJECT_READINESS_REQUEST_SCHEMA_VERSION = (
    "chemsmart.typed-project-readiness-request.v1"
)
PROJECT_READINESS_EVIDENCE_REF_SCHEMA_VERSION = (
    "chemsmart.project-readiness-evidence-ref.v1"
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_JOB_KIND = r"^[a-z][a-z0-9_-]{0,79}$"
_RULE_ID = r"^[a-z][a-z0-9_.-]+$"
_SHA256 = r"^[0-9a-f]{64}$"
_ELEMENT = re.compile(r"^[A-Z][a-z]?$|^X$")


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        # Exact project YAML and canonical embedded JSON are evidence bytes.
        # Field patterns and explicit validators own normalization elsewhere.
        str_strip_whitespace=False,
        allow_inf_nan=False,
    )


class TypedProjectSupportStatus(str, Enum):
    TYPED_PROJECT_SUPPORTED = "typed_project_supported"
    BLOCKED_MISSING_EVIDENCE = "blocked_missing_evidence"
    BLOCKED_UNSUPPORTED_SETTING = "blocked_unsupported_setting"
    BLOCKED_INVALID_SPECIFICATION = "blocked_invalid_specification"
    BLOCKED_REQUIRED_JOB_VALIDATION = "blocked_required_job_validation"
    BLOCKED_SEMANTIC_DRIFT = "blocked_semantic_drift"
    BLOCKED_ECP_BINDING = "blocked_ecp_binding"


class ProjectMethodIntentV1(_Contract):
    """Project-level scientific intent accepted by the current compiler."""

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
    ecp_binding: Literal["not_requested", "required_elements"] = (
        "not_requested"
    )
    required_ecp_elements: tuple[str, ...] = ()

    @field_validator("heavy_elements", "required_ecp_elements")
    @classmethod
    def _elements_are_canonical(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if any(_ELEMENT.fullmatch(item) is None for item in value):
            raise ValueError("project element symbol is invalid")
        if value != tuple(sorted(set(value))):
            raise ValueError("project elements must be unique and sorted")
        return value

    @model_validator(mode="after")
    def _ecp_binding_is_coherent(self) -> "ProjectMethodIntentV1":
        if self.ecp_binding == "required_elements":
            ecp_basis = self.heavy_elements_basis or self.basis
            if ecp_basis is None or not self.required_ecp_elements:
                raise ValueError(
                    "required ECP binding needs a basis and explicit elements"
                )
            if self.heavy_elements_basis is not None and not set(
                self.required_ecp_elements
            ).issubset(self.heavy_elements):
                raise ValueError(
                    "mixed-basis ECP elements must be declared heavy elements"
                )
        elif self.required_ecp_elements:
            raise ValueError(
                "ECP elements require ecp_binding='required_elements'"
            )
        return self

    def renderer_method(self) -> dict[str, Any]:
        """Return only fields owned by the typed project compiler."""

        excluded = {"ecp_binding", "required_ecp_elements"}
        payload = {
            key: value
            for key, value in self.model_dump(mode="python").items()
            if key not in excluded and value not in (None, (), [])
        }
        if "heavy_elements" in payload:
            payload["heavy_elements"] = list(payload["heavy_elements"])
        return payload


class ProjectReadinessRequestV1(_Contract):
    schema_version: Literal[PROJECT_READINESS_REQUEST_SCHEMA_VERSION] = (
        PROJECT_READINESS_REQUEST_SCHEMA_VERSION
    )
    case_id: str = Field(pattern=_IDENTIFIER)
    program: Literal["gaussian", "orca", "xtb"]
    job_kind: str = Field(pattern=_JOB_KIND)
    method: ProjectMethodIntentV1
    request_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _request_is_bound(self) -> "ProjectReadinessRequestV1":
        if self.program == "xtb" and self.method.ecp_binding != "not_requested":
            raise ValueError("xTB cannot carry an orbital-basis ECP binding")
        if self.request_sha256 != project_readiness_request_sha256(self):
            raise ValueError("project-readiness request digest mismatch")
        return self


class RegistryDiscoveryBindingV1(_Contract):
    """Opaque registry identities that have discovery, not support, scope."""

    resolution_sha256s: tuple[str, ...] = ()
    evidence_role: Literal[
        "registry_discovery_only"
    ] = "registry_discovery_only"
    establishes_typed_project_support: Literal[False] = False

    @field_validator("resolution_sha256s")
    @classmethod
    def _resolution_hashes_are_canonical(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("registry resolution digests must be unique and sorted")
        if any(re.fullmatch(_SHA256, item) is None for item in value):
            raise ValueError("registry resolution digest is invalid")
        return value


class BasisEcpObservationV1(_Contract):
    assessment: Literal["not_requested", "bse_definition"]
    basis: str | None = Field(default=None, max_length=300)
    required_elements: tuple[str, ...] = ()
    observed_ecp_elements: tuple[str, ...] = ()
    verdict: Literal["not_checked", "ok", "reject"]
    status: str = Field(min_length=1, max_length=100)
    rule_ids: tuple[str, ...] = ()
    basis_element_receipt_sha256: str | None = Field(
        default=None,
        pattern=_SHA256,
    )
    evidence_role: Literal[
        "basis_definition_only"
    ] = "basis_definition_only"
    establishes_typed_project_support: Literal[False] = False

    @field_validator("required_elements", "observed_ecp_elements")
    @classmethod
    def _elements_are_canonical(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("ECP observation elements must be unique and sorted")
        if any(_ELEMENT.fullmatch(item) is None for item in value):
            raise ValueError("ECP observation element is invalid")
        return value

    @field_validator("rule_ids")
    @classmethod
    def _rule_ids_are_canonical(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _canonical_rule_ids(value)

    @model_validator(mode="after")
    def _observation_is_coherent(self) -> "BasisEcpObservationV1":
        if self.assessment == "not_requested":
            if any(
                (
                    self.basis is not None,
                    bool(self.required_elements),
                    bool(self.observed_ecp_elements),
                    self.verdict != "not_checked",
                    self.basis_element_receipt_sha256 is not None,
                )
            ):
                raise ValueError("an unrequested ECP assessment has evidence")
        elif self.basis is None or not self.required_elements:
            raise ValueError("BSE ECP assessment needs a basis and elements")
        return self


class RequiredJobObservationV1(_Contract):
    jobtype: str = Field(pattern=_JOB_KIND)
    origin: Literal["explicit", "derived", "default"]
    source_block: str | None = Field(default=None, pattern=_JOB_KIND)
    ab_initio: str | None = Field(default=None, max_length=300)
    semiempirical: str | None = Field(default=None, max_length=300)
    functional: str | None = Field(default=None, max_length=300)
    gfn_version: str | None = Field(default=None, max_length=160)
    basis: str | None = Field(default=None, max_length=300)
    gen_genecp_file: str | None = Field(default=None, max_length=512)
    heavy_elements: tuple[str, ...] = ()
    heavy_elements_basis: str | None = Field(default=None, max_length=300)
    light_elements_basis: str | None = Field(default=None, max_length=300)
    dispersion: str | None = Field(default=None, max_length=160)
    solvent_model: str | None = Field(default=None, max_length=160)
    solvent_id: str | None = Field(default=None, max_length=160)
    custom_solvent: str | None = Field(default=None, max_length=1000)
    freq: bool | None = None
    numfreq: bool | None = None
    optimization_level: str | None = Field(default=None, max_length=160)
    additional_route_parameters: str | None = Field(
        default=None,
        max_length=1000,
    )


class TypedProjectSupportObservationV1(_Contract):
    status: TypedProjectSupportStatus
    support_scope: Literal[
        "paper_renderer_loader_required_job_only"
    ] = "paper_renderer_loader_required_job_only"
    renderer_status: str = Field(min_length=1, max_length=100)
    project_yaml_text: str | None = None
    project_yaml_sha256: str | None = Field(default=None, pattern=_SHA256)
    validation_record_json: str = Field(min_length=2)
    validation_sha256: str = Field(pattern=_SHA256)
    runtime_summary_json: str = Field(min_length=2)
    runtime_summary_sha256: str = Field(pattern=_SHA256)
    validation_verdict: Literal["ok", "warn", "reject", "not_run"]
    required_job: str = Field(pattern=_JOB_KIND)
    required_job_observation: RequiredJobObservationV1 | None = None
    finding_rule_ids: tuple[str, ...] = ()
    blocking_rule_ids: tuple[str, ...] = ()

    @field_validator("finding_rule_ids", "blocking_rule_ids")
    @classmethod
    def _rules_are_canonical(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _canonical_rule_ids(value)

    @model_validator(mode="after")
    def _support_is_coherent(self) -> "TypedProjectSupportObservationV1":
        validation_record = _canonical_json_object(
            self.validation_record_json,
            label="validation record",
        )
        runtime_summary = _canonical_json_object(
            self.runtime_summary_json,
            label="runtime summary",
        )
        if self.project_yaml_text is None:
            if self.project_yaml_sha256 is not None:
                raise ValueError("absent project YAML cannot have a digest")
        elif self.project_yaml_sha256 != _sha256_bytes(
            self.project_yaml_text.encode("utf-8")
        ):
            raise ValueError("project YAML digest mismatch")
        if self.validation_sha256 != _sha256_bytes(
            self.validation_record_json.encode("utf-8")
        ):
            raise ValueError("embedded validation record digest mismatch")
        if self.runtime_summary_sha256 != _sha256_bytes(
            self.runtime_summary_json.encode("utf-8")
        ):
            raise ValueError("embedded runtime summary digest mismatch")
        embedded_runtime = validation_record.get("runtime_summary")
        if embedded_runtime is None:
            embedded_runtime = {}
        if embedded_runtime != runtime_summary:
            raise ValueError("validation and runtime-summary bodies disagree")
        if self.project_yaml_text is None:
            if self.validation_verdict != "not_run" or runtime_summary:
                raise ValueError("blocked rendering cannot claim loader validation")
            derived_observation = None
        else:
            if validation_record.get("verdict") != self.validation_verdict:
                raise ValueError("validation verdict disagrees with its body")
            derived_observation = _required_job_observation(
                runtime_summary.get(self.required_job)
            )
        if derived_observation != self.required_job_observation:
            raise ValueError(
                "required-job observation is not derived from runtime body"
            )
        validation_findings, validation_blockers = _validation_rule_sets(
            validation_record
        )
        if not validation_findings.issubset(self.finding_rule_ids):
            raise ValueError("validation findings are missing from support evidence")
        if not validation_blockers.issubset(self.blocking_rule_ids):
            raise ValueError("validation blockers are missing from support evidence")
        supported = (
            self.status
            is TypedProjectSupportStatus.TYPED_PROJECT_SUPPORTED
        )
        if supported and (
            self.project_yaml_sha256 is None
            or self.validation_verdict not in {"ok", "warn"}
            or self.required_job_observation is None
            or self.blocking_rule_ids
        ):
            raise ValueError("typed-project support lacks required evidence")
        return self

    @property
    def validation_record(self) -> dict[str, Any]:
        return json.loads(self.validation_record_json)

    @property
    def runtime_summary(self) -> dict[str, Any]:
        return json.loads(self.runtime_summary_json)


class ProjectReadinessSafetyV1(_Contract):
    workspace_project_writes: Literal[0] = 0
    native_input_previews: Literal[0] = 0
    chemistry_engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0
    registry_discovery_grants_support: Literal[False] = False


class ProjectReadinessReceiptV1(_Contract):
    schema_version: Literal[PROJECT_READINESS_SCHEMA_VERSION] = (
        PROJECT_READINESS_SCHEMA_VERSION
    )
    authority_id: Literal[
        "chemsmart.paper-project-renderer-loader-required-job"
    ] = "chemsmart.paper-project-renderer-loader-required-job"
    authority_version: Literal["1.0.0"] = "1.0.0"
    request: ProjectReadinessRequestV1
    registry_discovery: RegistryDiscoveryBindingV1
    basis_ecp: BasisEcpObservationV1
    typed_project_support: TypedProjectSupportObservationV1
    safety: ProjectReadinessSafetyV1 = Field(
        default_factory=ProjectReadinessSafetyV1
    )
    receipt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _receipt_is_bound(self) -> "ProjectReadinessReceiptV1":
        support = self.typed_project_support
        if support.required_job != self.request.job_kind:
            raise ValueError("support observation belongs to another job")
        if (
            support.status
            is TypedProjectSupportStatus.TYPED_PROJECT_SUPPORTED
            and self.basis_ecp.verdict == "reject"
        ):
            raise ValueError("typed-project support cannot ignore an ECP block")
        validation_findings, validation_blockers = _validation_rule_sets(
            support.validation_record
        )
        if (
            support.project_yaml_text is not None
            and support.validation_verdict in {"ok", "warn"}
            and support.required_job_observation is None
        ):
            missing_rule = "project_readiness.required_job_observation_missing"
            validation_findings.add(missing_rule)
            validation_blockers.add(missing_rule)
        if self.basis_ecp.verdict == "reject":
            validation_findings.update(self.basis_ecp.rule_ids)
            validation_blockers.update(self.basis_ecp.rule_ids)
        if set(support.finding_rule_ids) != validation_findings:
            raise ValueError("support findings are not reproducible from evidence")
        if set(support.blocking_rule_ids) != validation_blockers:
            raise ValueError("support blockers are not reproducible from evidence")
        method = self.request.method
        replayed_basis_ecp = _basis_ecp_observation(self.request)
        if replayed_basis_ecp != self.basis_ecp:
            raise ValueError("ECP evidence is not the current local BSE observation")
        if method.ecp_binding == "not_requested":
            if self.basis_ecp.assessment != "not_requested":
                raise ValueError("unrequested ECP evidence is not empty")
        else:
            expected_ecp_basis = method.heavy_elements_basis or method.basis
            if (
                self.basis_ecp.assessment != "bse_definition"
                or self.basis_ecp.basis != expected_ecp_basis
                or self.basis_ecp.required_elements
                != method.required_ecp_elements
                or self.basis_ecp.basis_element_receipt_sha256 is None
            ):
                raise ValueError("ECP evidence is not bound to the request")
        expected_name = f"readiness-{self.request.request_sha256[:16]}"
        if support.validation_record.get("project_name") != expected_name:
            raise ValueError("validation record belongs to another project")
        replayed = render_project_yaml(
            {
                "program": self.request.program,
                "method": self.request.method.renderer_method(),
            },
            project_name=expected_name,
            program=self.request.program,
            profile="paper",
            required_job_kinds=(self.request.job_kind,),
        )
        replayed_validation = replayed.get("validation")
        replayed_validation = (
            dict(replayed_validation)
            if isinstance(replayed_validation, dict)
            else {}
        )
        replayed_validation.pop("revalidation_skipped", None)
        if replayed.get("yaml_text") != support.project_yaml_text:
            raise ValueError("project YAML does not preserve the bound request")
        if _canonical_json_text(replayed_validation) != (
            support.validation_record_json
        ):
            raise ValueError(
                "validation record is not the current loader output"
            )
        if support.project_yaml_text is None:
            expected_status = _render_block_status(replayed)
            expected_renderer_status = str(
                replayed.get("status") or expected_status.value
            )
        else:
            expected_status = _validated_support_status(
                support.validation_verdict,
                validation_blockers,
                self.basis_ecp,
            )
            expected_renderer_status = "rendered"
        if support.renderer_status != expected_renderer_status:
            raise ValueError("renderer status is not reproducible")
        if support.status is not expected_status:
            raise ValueError("project-readiness status is not reproducible")
        if self.receipt_sha256 != project_readiness_receipt_sha256(self):
            raise ValueError("project-readiness receipt digest mismatch")
        return self

    def evidence_ref(self) -> "ProjectReadinessEvidenceRefV1":
        body: dict[str, Any] = {
            "schema_version": PROJECT_READINESS_EVIDENCE_REF_SCHEMA_VERSION,
            "evidence_id": f"project-readiness:{self.request.case_id}",
            "kind": "typed_project_readiness",
            "request_sha256": self.request.request_sha256,
            "artifact_sha256": self.receipt_sha256,
            "media_type": "application/json",
            "ref_sha256": "0" * 64,
        }
        body["ref_sha256"] = project_readiness_evidence_ref_sha256(body)
        return ProjectReadinessEvidenceRefV1.model_validate(body)


class ProjectReadinessEvidenceRefV1(_Contract):
    """Path-free reference to an exact typed-project readiness receipt."""

    schema_version: Literal[PROJECT_READINESS_EVIDENCE_REF_SCHEMA_VERSION] = (
        PROJECT_READINESS_EVIDENCE_REF_SCHEMA_VERSION
    )
    evidence_id: str = Field(pattern=_IDENTIFIER)
    kind: Literal["typed_project_readiness"]
    request_sha256: str = Field(pattern=_SHA256)
    artifact_sha256: str = Field(pattern=_SHA256)
    media_type: Literal["application/json"] = "application/json"
    ref_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _reference_is_bound(self) -> "ProjectReadinessEvidenceRefV1":
        if self.ref_sha256 != project_readiness_evidence_ref_sha256(self):
            raise ValueError("project-readiness EvidenceRef digest mismatch")
        return self


def assess_typed_project_readiness(
    *,
    case_id: str,
    program: Literal["gaussian", "orca", "xtb"],
    job_kind: str,
    method: ProjectMethodIntentV1 | Mapping[str, Any],
    registry_resolution_sha256s: Sequence[str] = (),
) -> ProjectReadinessReceiptV1:
    """Build deterministic project-support evidence without execution."""

    typed_method = (
        method
        if isinstance(method, ProjectMethodIntentV1)
        else ProjectMethodIntentV1.model_validate(method)
    )
    request_body = {
        "schema_version": PROJECT_READINESS_REQUEST_SCHEMA_VERSION,
        "case_id": case_id,
        "program": program,
        "job_kind": job_kind,
        "method": typed_method,
    }
    request_body["request_sha256"] = project_readiness_request_sha256(
        request_body
    )
    request = ProjectReadinessRequestV1.model_validate(request_body)
    registry = RegistryDiscoveryBindingV1(
        resolution_sha256s=tuple(sorted(set(registry_resolution_sha256s)))
    )
    basis_ecp = _basis_ecp_observation(request)

    project_name = f"readiness-{request.request_sha256[:16]}"
    rendered = render_project_yaml(
        {"program": request.program, "method": typed_method.renderer_method()},
        project_name=project_name,
        program=request.program,
        profile="paper",
        required_job_kinds=(request.job_kind,),
    )
    support = _typed_project_support_observation(
        request,
        rendered,
        basis_ecp,
    )
    body = {
        "schema_version": PROJECT_READINESS_SCHEMA_VERSION,
        "authority_id": (
            "chemsmart.paper-project-renderer-loader-required-job"
        ),
        "authority_version": "1.0.0",
        "request": request,
        "registry_discovery": registry,
        "basis_ecp": basis_ecp,
        "typed_project_support": support,
        "safety": ProjectReadinessSafetyV1(),
    }
    body["receipt_sha256"] = project_readiness_receipt_sha256(body)
    return ProjectReadinessReceiptV1.model_validate(body)


def _basis_ecp_observation(
    request: ProjectReadinessRequestV1,
) -> BasisEcpObservationV1:
    method = request.method
    if method.ecp_binding == "not_requested":
        return BasisEcpObservationV1(
            assessment="not_requested",
            verdict="not_checked",
            status="not_requested",
        )
    ecp_basis = method.heavy_elements_basis or method.basis
    if ecp_basis is None:  # guarded by ProjectMethodIntentV1
        raise ValueError("required ECP binding has no inspectable basis")
    result = inspect_basis_elements(
        ecp_basis,
        program=request.program,  # type: ignore[arg-type]
        elements=method.required_ecp_elements,
    )
    observed = tuple(
        sorted(item.symbol for item in result.elements if item.ecp_present)
    )
    rules = set(result.rule_ids)
    if observed != method.required_ecp_elements:
        rules.add("project_readiness.ecp_required_elements_mismatch")
    verdict: Literal["ok", "reject"] = (
        "ok" if result.verdict == "ok" and not rules else "reject"
    )
    return BasisEcpObservationV1(
        assessment="bse_definition",
        basis=ecp_basis,
        required_elements=method.required_ecp_elements,
        observed_ecp_elements=observed,
        verdict=verdict,
        status=result.status,
        rule_ids=tuple(sorted(rules)),
        basis_element_receipt_sha256=result.receipt_sha256,
    )


def _typed_project_support_observation(
    request: ProjectReadinessRequestV1,
    rendered: dict[str, Any],
    basis_ecp: BasisEcpObservationV1,
) -> TypedProjectSupportObservationV1:
    yaml_text = rendered.get("yaml_text")
    validation = rendered.get("validation")
    validation = dict(validation) if isinstance(validation, dict) else {}
    # ``validate_project_yaml`` marks cache hits for loop control. That marker
    # describes how the observation was obtained, not different chemistry,
    # and therefore must not perturb a content-addressed scientific receipt.
    validation.pop("revalidation_skipped", None)
    runtime_summary = validation.get("runtime_summary")
    runtime_summary = runtime_summary if isinstance(runtime_summary, dict) else {}
    issues = validation.get("issues")
    issues = issues if isinstance(issues, list) else []
    finding_rules = {
        str(item.get("rule_id"))
        for item in issues
        if isinstance(item, dict) and item.get("rule_id")
    }
    blocking_rules = {
        str(item.get("rule_id"))
        for item in issues
        if isinstance(item, dict)
        and item.get("rule_id")
        and item.get("severity") == "reject"
    }
    if not isinstance(yaml_text, str):
        status = _render_block_status(rendered)
        renderer_status = str(rendered.get("status") or status.value)
        observation = None
        verdict: Literal["reject", "not_run"] = "not_run"
        project_yaml_sha256 = None
    else:
        renderer_status = "rendered"
        verdict = str(validation.get("verdict") or "reject")  # type: ignore[assignment]
        project_yaml_sha256 = _sha256_bytes(yaml_text.encode("utf-8"))
        observation = _required_job_observation(
            runtime_summary.get(request.job_kind)
        )
        if observation is None and verdict in {"ok", "warn"}:
            missing_rule = (
                "project_readiness.required_job_observation_missing"
            )
            finding_rules.add(missing_rule)
            blocking_rules.add(missing_rule)
            status = (
                TypedProjectSupportStatus.BLOCKED_REQUIRED_JOB_VALIDATION
            )
        else:
            status = _validated_support_status(
                verdict,
                blocking_rules,
                basis_ecp,
            )
    if basis_ecp.verdict == "reject":
        finding_rules.update(basis_ecp.rule_ids)
        blocking_rules.update(basis_ecp.rule_ids)
    validation_record_json = _canonical_json_text(validation)
    runtime_summary_json = _canonical_json_text(runtime_summary)
    return TypedProjectSupportObservationV1(
        status=status,
        renderer_status=renderer_status,
        project_yaml_text=yaml_text if isinstance(yaml_text, str) else None,
        project_yaml_sha256=project_yaml_sha256,
        validation_record_json=validation_record_json,
        validation_sha256=_sha256_bytes(
            validation_record_json.encode("utf-8")
        ),
        runtime_summary_json=runtime_summary_json,
        runtime_summary_sha256=_sha256_bytes(
            runtime_summary_json.encode("utf-8")
        ),
        validation_verdict=verdict,
        required_job=request.job_kind,
        required_job_observation=observation,
        finding_rule_ids=tuple(sorted(finding_rules)),
        blocking_rule_ids=tuple(sorted(blocking_rules)),
    )


def _render_block_status(
    rendered: dict[str, Any],
) -> TypedProjectSupportStatus:
    if rendered.get("status") == "blocked_missing_evidence":
        return TypedProjectSupportStatus.BLOCKED_MISSING_EVIDENCE
    if rendered.get("status") == "blocked_unsupported_setting":
        return TypedProjectSupportStatus.BLOCKED_UNSUPPORTED_SETTING
    return TypedProjectSupportStatus.BLOCKED_INVALID_SPECIFICATION


def _validated_support_status(
    verdict: str,
    blocking_rules: set[str],
    basis_ecp: BasisEcpObservationV1,
) -> TypedProjectSupportStatus:
    if {
        "yaml.runtime.required_job_semantic_mismatch",
        "yaml.runtime.required_job_origin_mismatch",
    }.intersection(blocking_rules):
        return TypedProjectSupportStatus.BLOCKED_SEMANTIC_DRIFT
    if any(rule.startswith("yaml.runtime.required_job") for rule in blocking_rules):
        return TypedProjectSupportStatus.BLOCKED_REQUIRED_JOB_VALIDATION
    if verdict not in {"ok", "warn"}:
        return TypedProjectSupportStatus.BLOCKED_INVALID_SPECIFICATION
    if basis_ecp.verdict == "reject":
        return TypedProjectSupportStatus.BLOCKED_ECP_BINDING
    return TypedProjectSupportStatus.TYPED_PROJECT_SUPPORTED


def _required_job_observation(value: Any) -> RequiredJobObservationV1 | None:
    if not isinstance(value, dict):
        return None
    jobtype = value.get("jobtype")
    provenance = value.get("jobtype_observation")
    if not isinstance(jobtype, str) or not isinstance(provenance, dict):
        return None
    heavy_elements = value.get("heavy_elements")
    return RequiredJobObservationV1(
        jobtype=jobtype,
        origin=provenance.get("origin"),
        source_block=provenance.get("source_block"),
        ab_initio=value.get("ab_initio"),
        semiempirical=value.get("semiempirical"),
        functional=value.get("functional"),
        gfn_version=value.get("gfn_version"),
        basis=value.get("basis"),
        gen_genecp_file=value.get("gen_genecp_file"),
        heavy_elements=tuple(heavy_elements or ()),
        heavy_elements_basis=value.get("heavy_elements_basis"),
        light_elements_basis=value.get("light_elements_basis"),
        dispersion=value.get("dispersion"),
        solvent_model=value.get("solvent_model"),
        solvent_id=value.get("solvent_id"),
        custom_solvent=value.get("custom_solvent"),
        freq=value.get("freq"),
        numfreq=value.get("numfreq"),
        optimization_level=value.get("optimization_level"),
        additional_route_parameters=value.get(
            "additional_route_parameters"
        ),
    )


def _validation_rule_sets(
    validation: Mapping[str, Any],
) -> tuple[set[str], set[str]]:
    issues = validation.get("issues")
    issues = issues if isinstance(issues, list) else []
    findings = {
        str(item.get("rule_id"))
        for item in issues
        if isinstance(item, dict) and item.get("rule_id")
    }
    blockers = {
        str(item.get("rule_id"))
        for item in issues
        if isinstance(item, dict)
        and item.get("rule_id")
        and item.get("severity") == "reject"
    }
    return findings, blockers


def project_readiness_request_sha256(
    value: ProjectReadinessRequestV1 | Mapping[str, Any],
) -> str:
    return _contract_sha256(value, "request_sha256")


def project_readiness_receipt_sha256(
    value: ProjectReadinessReceiptV1 | Mapping[str, Any],
) -> str:
    return _contract_sha256(value, "receipt_sha256")


def project_readiness_evidence_ref_sha256(
    value: ProjectReadinessEvidenceRefV1 | Mapping[str, Any],
) -> str:
    return _contract_sha256(value, "ref_sha256")


def _contract_sha256(
    value: BaseModel | Mapping[str, Any],
    digest_field: str,
) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude={digest_field})
    else:
        payload = {
            str(key): _jsonable(item)
            for key, item in value.items()
            if key != digest_field
        }
    return _sha256_json(payload)


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json_text(value).encode("utf-8"))


def _canonical_json_text(value: Any) -> str:
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _canonical_json_object(value: str, *, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object")
    if _canonical_json_text(parsed) != value:
        raise ValueError(f"{label} is not canonical JSON")
    return parsed


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _canonical_rule_ids(value: tuple[str, ...]) -> tuple[str, ...]:
    if value != tuple(sorted(set(value))):
        raise ValueError("rule IDs must be unique and sorted")
    if any(re.fullmatch(_RULE_ID, item) is None for item in value):
        raise ValueError("rule ID is invalid")
    return value


__all__ = [
    "PROJECT_READINESS_EVIDENCE_REF_SCHEMA_VERSION",
    "PROJECT_READINESS_REQUEST_SCHEMA_VERSION",
    "PROJECT_READINESS_SCHEMA_VERSION",
    "BasisEcpObservationV1",
    "ProjectMethodIntentV1",
    "ProjectReadinessReceiptV1",
    "ProjectReadinessEvidenceRefV1",
    "ProjectReadinessRequestV1",
    "RegistryDiscoveryBindingV1",
    "RequiredJobObservationV1",
    "TypedProjectSupportObservationV1",
    "TypedProjectSupportStatus",
    "assess_typed_project_readiness",
    "project_readiness_receipt_sha256",
    "project_readiness_evidence_ref_sha256",
    "project_readiness_request_sha256",
]
