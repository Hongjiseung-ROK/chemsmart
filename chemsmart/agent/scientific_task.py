"""Typed scientific state and deterministic M2 command-workflow checks.

``ScientificTaskSpec`` is intentionally independent from the CLI command IR.
The task says what molecule, electronic state, method, and observable are
being preserved; ``CommandWorkflowSpec`` says which existing ChemSmart
commands can realize that task.  Keeping the contracts separate prevents a
valid Click command from being mistaken for a scientifically specified one.

The first command-compiled slice is deliberately narrow: a single-frame XYZ
in Angstrom, Gaussian/ORCA ``opt``/``ts``/``sp``/``td`` where the existing
project loader exposes settings, and xTB ``opt``/``sp``/``hess``.  Other job
families remain typed but cannot become ``previewed`` until they gain an
equally deterministic settings and geometry validator.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, Mapping, TYPE_CHECKING

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

from chemsmart.agent.command_workflow import (
    CommandCounterexample,
    CommandNode,
    CommandWorkflowCompilation,
    CommandWorkflowSpec,
)
from chemsmart.agent.geometry_identity import xyz_geometry_manifest
from chemsmart.agent.harness.command_semantics import CommandSemanticResult
from chemsmart.io.xtb import XTB_ALL_SOLVENT_MODELS

if TYPE_CHECKING:  # pragma: no cover - imports only guide static checkers
    from chemsmart.agent.workspace_bindings import WorkspaceBindings


SCIENTIFIC_TASK_SCHEMA_VERSION = "chemsmart.scientific-task.v1"
_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
_VALIDATION_OBLIGATION_IDENTIFIER = r"^[a-z][a-z0-9_]{0,127}$"
_SHA256 = r"^[0-9a-f]{64}$"
_PROGRAMS = frozenset({"gaussian", "orca", "xtb"})
_SUPPORTED_JOBS = {
    "gaussian": frozenset({"opt", "ts", "sp", "td"}),
    "orca": frozenset({"opt", "ts", "sp"}),
    "xtb": frozenset({"opt", "sp", "hess"}),
}
_M2_EVIDENCE_CLASSES = frozenset(
    {
        "cli_schema",
        "command_workflow_receipt",
        "geometry_identity",
        "project_yaml",
        "safe_preview",
    }
)


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


PostExecutionValidationObligation = Annotated[
    str,
    Field(pattern=_VALIDATION_OBLIGATION_IDENTIFIER),
]


class GeometryIdentity(_Contract):
    """Exact M2 source geometry selected by a content-addressed binding."""

    frame_id: str = Field(pattern=_IDENTIFIER)
    artifact_id: str = Field(pattern=_IDENTIFIER)
    sha256: str = Field(pattern=_SHA256)
    kind: Literal["geometry.xyz"] = "geometry.xyz"
    coordinate_units: Literal["angstrom"] = "angstrom"
    ordered_geometry_sha256: str = Field(pattern=_SHA256)


class ElectronicState(_Contract):
    """Explicit molecular charge and spin multiplicity."""

    charge: StrictInt
    multiplicity: StrictInt = Field(ge=1)


class ConstraintBinding(_Contract):
    """A stable constraint reference reserved for later supported families."""

    constraint_id: str = Field(pattern=_IDENTIFIER)
    kind: Literal["bond", "angle", "dihedral", "freeze", "qmmm_region", "neb"]
    definition_sha256: str = Field(pattern=_SHA256)


class NodeScientificRequirement(_Contract):
    """Method and state expectations for one computational command node."""

    node_id: str = Field(pattern=_IDENTIFIER)
    program: Literal["gaussian", "orca", "xtb"]
    job_kind: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    settings_source: Literal["project", "xtb_command"]
    method: str = Field(min_length=1, max_length=160)
    basis_or_ecp: str | None = Field(default=None, max_length=200)
    optimization_level: str | None = Field(default=None, max_length=80)
    solvent_model: str | None = Field(default=None, max_length=80)
    solvent_id: str | None = Field(default=None, max_length=120)
    integration_grid: str | None = Field(default=None, max_length=80)
    frequency_required: bool | None = None
    gradient_required: bool | None = None
    constraints_sha256: str | None = Field(default=None, pattern=_SHA256)

    @model_validator(mode="after")
    def _method_source_is_complete(self) -> "NodeScientificRequirement":
        if (self.solvent_model is None) != (self.solvent_id is None):
            raise ValueError(
                "solvent_model and solvent_id must be specified together"
            )
        if self.program in {"gaussian", "orca"}:
            if self.settings_source != "project":
                raise ValueError("Gaussian/ORCA methods must come from project YAML")
            if not self.basis_or_ecp:
                raise ValueError("Gaussian/ORCA requirements need basis_or_ecp")
            if self.optimization_level is not None:
                raise ValueError(
                    "optimization_level is only defined for xTB optimization"
                )
            if self.gradient_required is not None:
                raise ValueError("gradient_required is only defined for xTB")
        elif self.basis_or_ecp is not None:
            raise ValueError("xTB requirement must not contain basis_or_ecp")
        elif self.optimization_level is not None and self.job_kind != "opt":
            raise ValueError(
                "xTB optimization_level is only valid for the opt job family"
            )
        if self.integration_grid is not None and self.program != "gaussian":
            raise ValueError(
                "integration_grid is currently validated only for Gaussian"
            )
        return self


class ScientificTaskSpec(_Contract):
    """Scientific source of truth paired with a command-workflow proposal."""

    schema_version: Literal[SCIENTIFIC_TASK_SCHEMA_VERSION] = (
        SCIENTIFIC_TASK_SCHEMA_VERSION
    )
    task_spec_id: str = Field(pattern=_IDENTIFIER)
    molecule_id: str = Field(pattern=_IDENTIFIER)
    geometry: GeometryIdentity
    electronic_state: ElectronicState
    requested_observable: str = Field(min_length=1, max_length=240)
    node_requirements: tuple[NodeScientificRequirement, ...] = Field(min_length=1)
    constraints: tuple[ConstraintBinding, ...] = ()
    required_evidence: tuple[str, ...] = ()
    post_execution_validation_obligations: tuple[
        PostExecutionValidationObligation, ...
    ] = ()
    unresolved_facts: tuple[str, ...] = ()

    @field_validator("node_requirements")
    @classmethod
    def _canonical_node_requirements(
        cls, value: tuple[NodeScientificRequirement, ...]
    ) -> tuple[NodeScientificRequirement, ...]:
        return tuple(sorted(value, key=lambda item: item.node_id))

    @field_validator("constraints")
    @classmethod
    def _canonical_constraints(
        cls, value: tuple[ConstraintBinding, ...]
    ) -> tuple[ConstraintBinding, ...]:
        return tuple(sorted(value, key=lambda item: item.constraint_id))

    @field_validator(
        "required_evidence",
        "post_execution_validation_obligations",
        "unresolved_facts",
    )
    @classmethod
    def _canonical_string_sets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("set-like scientific task fields must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def _unique_references(self) -> "ScientificTaskSpec":
        node_ids = [item.node_id for item in self.node_requirements]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("node_requirements must have unique node_id values")
        constraint_ids = [item.constraint_id for item in self.constraints]
        if len(constraint_ids) != len(set(constraint_ids)):
            raise ValueError("constraints must have unique constraint_id values")
        return self


@dataclass(frozen=True)
class ScientificTaskValidation:
    """Path-free deterministic scientific preflight observations."""

    task_spec_sha256: str
    status: Literal["ok", "needs_clarification", "infeasible", "blocked"]
    molecule_id: str
    requested_observable: str
    required_evidence: tuple[str, ...]
    post_execution_validation_obligations: tuple[str, ...]
    findings: tuple[CommandCounterexample, ...]

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_spec_sha256": self.task_spec_sha256,
            "status": self.status,
            "scientific_identity": {
                "molecule_id": self.molecule_id,
                "requested_observable": self.requested_observable,
                "required_evidence": list(self.required_evidence),
                "post_execution_validation_obligations": list(
                    self.post_execution_validation_obligations
                ),
            },
            "post_execution_validation": {
                "status": (
                    "pending_execution"
                    if self.post_execution_validation_obligations
                    else "not_required"
                ),
                "satisfied_obligations": [],
            },
            "findings": [item.model_dump(mode="json") for item in self.findings],
        }


def task_spec_sha256(task: ScientificTaskSpec) -> str:
    """Return a stable identity for the complete typed scientific task."""

    canonical = ScientificTaskSpec.model_validate(task.model_dump(mode="json"))
    return _sha256_json(canonical.model_dump(mode="json"))


def validate_scientific_task_workflow(
    task: ScientificTaskSpec,
    workflow: CommandWorkflowSpec,
    bindings: "WorkspaceBindings",
) -> ScientificTaskValidation:
    """Validate scientific intent before command compilation or preview."""

    # Reject unchecked ``model_copy(update=...)`` mutations and restore every
    # set-like tuple to the contract's canonical order before validation.
    task = ScientificTaskSpec.model_validate(task.model_dump(mode="json"))
    workflow = CommandWorkflowSpec.model_validate(
        workflow.model_dump(mode="json")
    )

    findings: list[CommandCounterexample] = []
    if task.task_spec_id != workflow.task_spec_id:
        findings.append(
            _finding(
                "cmd.science.task_id_mismatch",
                None,
                "task_spec_id",
                task.task_spec_id,
                workflow.task_spec_id,
            )
        )
    for _fact in task.unresolved_facts:
        findings.append(
            _finding(
                "cmd.science.unresolved_fact",
                None,
                "unresolved_facts",
                "no unresolved scientifically consequential facts",
                "unresolved",
            )
        )
    for evidence_class in task.required_evidence:
        if evidence_class not in _M2_EVIDENCE_CLASSES:
            findings.append(
                _finding(
                    "cmd.science.evidence.unsupported",
                    None,
                    "required_evidence",
                    sorted(_M2_EVIDENCE_CLASSES),
                    evidence_class,
                )
            )
    _validate_geometry_identity(task, bindings, findings)

    computational_nodes = [
        node for node in workflow.nodes if _program_from_node(node) in _PROGRAMS
    ]
    requirements = {item.node_id: item for item in task.node_requirements}
    node_ids = {node.node_id for node in computational_nodes}
    for node_id in sorted(node_ids.difference(requirements)):
        findings.append(
            _finding(
                "cmd.science.node_requirement_missing",
                node_id,
                "node_requirements",
                "one typed scientific requirement for every computational node",
                "missing",
            )
        )
    for node_id in sorted(set(requirements).difference(node_ids)):
        findings.append(
            _finding(
                "cmd.science.node_requirement_unbound",
                node_id,
                "node_requirements",
                "a computational CommandNode with this node_id",
                "unbound",
            )
        )
    for node in computational_nodes:
        requirement = requirements.get(node.node_id)
        if requirement is None:
            continue
        _validate_node_requirement(task, node, requirement, bindings, findings)

    declared_constraints = {item.constraint_id for item in task.constraints}
    bound_constraints = {
        constraint_id
        for node in workflow.nodes
        for constraint_id in node.constraint_ids
    }
    for constraint_id in sorted(bound_constraints.difference(declared_constraints)):
        findings.append(
            _finding(
                "cmd.science.constraint.unbound",
                None,
                "constraint_ids",
                "constraint declared in ScientificTaskSpec",
                constraint_id,
            )
        )
    constraints_by_sha256 = {
        item.definition_sha256: item for item in task.constraints
    }
    for node in computational_nodes:
        requirement = requirements.get(node.node_id)
        if requirement is None or requirement.constraints_sha256 is None:
            continue
        declared = constraints_by_sha256.get(requirement.constraints_sha256)
        if declared is None:
            findings.append(
                _finding(
                    "cmd.science.constraint.requirement_unbound",
                    node.node_id,
                    "constraints_sha256",
                    "a declared ScientificTaskSpec constraint digest",
                    requirement.constraints_sha256,
                )
            )
        elif declared.constraint_id not in node.constraint_ids:
            findings.append(
                _finding(
                    "cmd.science.constraint.node_binding_missing",
                    node.node_id,
                    "constraint_ids",
                    declared.constraint_id,
                    list(node.constraint_ids),
                )
            )
    if declared_constraints:
        # The data remains recorded and bound, but M2 has no complete
        # cross-program constraint parser. Do not relabel it as previewed.
        findings.append(
            _finding(
                "cmd.science.constraint.unverifiable",
                None,
                "constraints",
                "a supported constraint-specific validator",
                "not_available_in_m2",
            )
        )
    return _validation(task, findings)


def validate_scientific_preview(
    task: ScientificTaskSpec,
    workflow: CommandWorkflowSpec,
    compilation: CommandWorkflowCompilation,
    preview_results: Mapping[str, CommandSemanticResult],
    bindings: "WorkspaceBindings",
) -> ScientificTaskValidation:
    """Check safe-preview evidence against the typed scientific task.

    This is intentionally not an execution validator. It checks only that the
    isolated fake/test command rendered what the approved scientific task
    requires, including charge/multiplicity and the ordered geometry for
    Gaussian/ORCA native inputs.
    """

    task = ScientificTaskSpec.model_validate(task.model_dump(mode="json"))
    workflow = CommandWorkflowSpec.model_validate(
        workflow.model_dump(mode="json")
    )
    preflight = validate_scientific_task_workflow(task, workflow, bindings)
    findings = list(preflight.findings)
    if compilation.status != "previewable":
        findings.append(
            _finding(
                "cmd.science.preview.compilation_not_previewable",
                None,
                "compilation.status",
                "previewable",
                compilation.status,
            )
        )
        return _validation(task, findings)
    requirements = {item.node_id: item for item in task.node_requirements}
    for invocation in compilation.invocations:
        requirement = requirements.get(invocation.node_id)
        if requirement is None:
            continue
        semantic = preview_results.get(invocation.node_id)
        if semantic is None or semantic.verdict != "ok":
            findings.append(
                _finding(
                    "cmd.science.preview.safe_gate_red",
                    invocation.node_id,
                    "safe_preview",
                    "semantic verdict ok",
                    getattr(semantic, "verdict", "missing"),
                )
            )
            continue
        _validate_generated_preview(task, invocation.node_id, requirement, semantic, findings)
    return _validation(task, findings)


def _validate_geometry_identity(
    task: ScientificTaskSpec,
    bindings: "WorkspaceBindings",
    findings: list[CommandCounterexample],
) -> None:
    geometry = task.geometry
    artifact = bindings.artifacts.get(geometry.artifact_id)
    if artifact is None:
        findings.append(
            _finding(
                "cmd.science.geometry.unbound",
                None,
                "geometry.artifact_id",
                "workspace geometry artifact",
                geometry.artifact_id,
            )
        )
        return
    if artifact.sha256 != geometry.sha256:
        findings.append(
            _finding(
                "cmd.science.geometry.hash_mismatch",
                None,
                "geometry.sha256",
                artifact.sha256,
                geometry.sha256,
            )
        )
    if artifact.kind != "geometry.xyz":
        findings.append(
            _finding(
                "cmd.science.geometry.kind_unsupported",
                None,
                "geometry.kind",
                "geometry.xyz",
                artifact.kind,
            )
        )
        return
    try:
        manifest = xyz_geometry_manifest(artifact.path)
    except ValueError:
        findings.append(
            _finding(
                "cmd.science.geometry.frame_unverified",
                None,
                "geometry",
                "single-frame parseable XYZ geometry",
                "unverified",
            )
        )
        return
    if manifest.ordered_geometry_sha256 != geometry.ordered_geometry_sha256:
        findings.append(
            _finding(
                "cmd.science.geometry.manifest_mismatch",
                None,
                "geometry.ordered_geometry_sha256",
                manifest.ordered_geometry_sha256,
                geometry.ordered_geometry_sha256,
            )
        )


def _validate_node_requirement(
    task: ScientificTaskSpec,
    node: CommandNode,
    requirement: NodeScientificRequirement,
    bindings: "WorkspaceBindings",
    findings: list[CommandCounterexample],
) -> None:
    program = _program_from_node(node)
    job_kind = _job_from_node(node, program)
    if node.execution_intent != "preview":
        findings.append(
            _finding(
                "cmd.science.execution.not_preview",
                node.node_id,
                "execution_intent",
                "preview",
                node.execution_intent,
            )
        )
    if requirement.program != program:
        findings.append(
            _finding(
                "cmd.science.program_mismatch",
                node.node_id,
                "program",
                requirement.program,
                program,
            )
        )
    if requirement.job_kind != job_kind:
        findings.append(
            _finding(
                "cmd.science.job_kind_mismatch",
                node.node_id,
                "job_kind",
                requirement.job_kind,
                job_kind,
            )
        )
    if program not in _SUPPORTED_JOBS or job_kind not in _SUPPORTED_JOBS[program]:
        findings.append(
            _finding(
                "cmd.science.job_unverifiable",
                node.node_id,
                "command_path",
                "an M2 supported program/job family",
                job_kind or "none",
            )
        )
    if node.charge != task.electronic_state.charge:
        findings.append(
            _finding(
                "cmd.science.charge_mismatch",
                node.node_id,
                "charge",
                task.electronic_state.charge,
                node.charge,
            )
        )
    if node.multiplicity != task.electronic_state.multiplicity:
        findings.append(
            _finding(
                "cmd.science.multiplicity_mismatch",
                node.node_id,
                "multiplicity",
                task.electronic_state.multiplicity,
                node.multiplicity,
            )
        )
    _validate_node_geometry(task, node, findings)
    if program in {"gaussian", "orca"} or (
        program == "xtb" and requirement.settings_source == "project"
    ):
        _validate_project_settings(node, requirement, program, bindings, findings)
    elif program == "xtb":
        _validate_xtb_settings(node, requirement, findings)
    if program == "xtb":
        _validate_xtb_job_controls(node, requirement, findings)


def _validate_node_geometry(
    task: ScientificTaskSpec,
    node: CommandNode,
    findings: list[CommandCounterexample],
) -> None:
    root_bindings = [
        item for item in node.input_artifacts if item.producer_node_id is None
    ]
    if not root_bindings:
        if any(item.producer_node_id is not None for item in node.input_artifacts):
            findings.append(
                _finding(
                    "cmd.science.geometry.handoff_unverifiable",
                    node.node_id,
                    "input_artifacts",
                    "a producer receipt with an ordered geometry digest",
                    "content hash without ordered-geometry handoff receipt",
                )
            )
        return
    if len(root_bindings) != 1:
        findings.append(
            _finding(
                "cmd.science.geometry.root_cardinality",
                node.node_id,
                "input_artifacts",
                "one root geometry binding",
                len(root_bindings),
            )
        )
        return
    bound = root_bindings[0]
    if (
        bound.artifact_id != task.geometry.artifact_id
        or bound.sha256 != task.geometry.sha256
        or bound.kind != task.geometry.kind
    ):
        findings.append(
            _finding(
                "cmd.science.geometry.root_mismatch",
                node.node_id,
                "input_artifacts",
                task.geometry.artifact_id,
                bound.artifact_id,
            )
        )


def _validate_project_settings(
    node: CommandNode,
    requirement: NodeScientificRequirement,
    program: str,
    bindings: "WorkspaceBindings",
    findings: list[CommandCounterexample],
) -> None:
    if node.project_ref is None:
        findings.append(
            _finding(
                "cmd.science.project.required",
                node.node_id,
                "project_ref",
                "content-addressed project reference",
                "missing",
            )
        )
        return
    project = bindings.projects.get(node.project_ref.project_id)
    if project is None:
        findings.append(
            _finding(
                "cmd.science.project.unbound",
                node.node_id,
                "project_ref.project_id",
                "workspace project binding",
                node.project_ref.project_id,
            )
        )
        return
    if project.program != program:
        findings.append(
            _finding(
                "cmd.science.project.program_mismatch",
                node.node_id,
                "project.program",
                program,
                project.program,
            )
        )
    if project.sha256 != node.project_ref.sha256:
        findings.append(
            _finding(
                "cmd.science.project.hash_mismatch",
                node.node_id,
                "project_ref.sha256",
                project.sha256,
                node.project_ref.sha256,
            )
        )
        return
    try:
        yaml_text = project.path.read_text(encoding="utf-8")
    except OSError:
        findings.append(
            _finding(
                "cmd.science.project.unreadable",
                node.node_id,
                "project_ref",
                "readable bound project YAML",
                "unreadable",
            )
        )
        return
    from chemsmart.agent.project_yaml import validate_project_yaml

    validation = validate_project_yaml(
        yaml_text=yaml_text,
        program=program,  # type: ignore[arg-type]
        project_name=project.command_value,
        required_job_kinds=(requirement.job_kind,),
    )
    if validation.get("verdict") != "ok":
        findings.append(
            _finding(
                "cmd.science.project.loader_rejected",
                node.node_id,
                "project_ref",
                "loader-validated project YAML without warnings",
                str(validation.get("verdict") or "rejected"),
            )
        )
        return
    settings = (validation.get("runtime_summary") or {}).get(
        _project_job_key(requirement.job_kind)
    )
    if not isinstance(settings, Mapping):
        findings.append(
            _finding(
                "cmd.science.project.settings_missing",
                node.node_id,
                "job_kind",
                "effective project settings for this job",
                requirement.job_kind,
            )
        )
        return
    if program == "xtb":
        _compare_setting(
            findings,
            node.node_id,
            "gfn_version",
            requirement.method,
            settings.get("gfn_version"),
            "cmd.science.xtb.gfn_mismatch",
        )
        if requirement.job_kind == "opt":
            parsed = validation.get("parsed") or {}
            parsed_block = (
                parsed.get("opt") if isinstance(parsed, Mapping) else None
            )
            observed_optimization = (
                parsed_block.get("optimization_level")
                if requirement.optimization_level is None
                and isinstance(parsed_block, Mapping)
                else settings.get("optimization_level")
            )
            _compare_setting(
                findings,
                node.node_id,
                "optimization_level",
                requirement.optimization_level,
                observed_optimization,
                "cmd.science.xtb.optimization_level_mismatch",
            )
    else:
        if _normalized(requirement.basis_or_ecp) in {"gen", "genecp"}:
            findings.append(
                _finding(
                    "cmd.science.basis_mapping_unverifiable",
                    node.node_id,
                    "basis_or_ecp",
                    "an element-resolved basis/ECP mapping validator",
                    requirement.basis_or_ecp,
                )
            )
        _compare_setting(
            findings,
            node.node_id,
            "functional",
            requirement.method,
            settings.get("functional"),
            "cmd.science.method.functional_mismatch",
        )
        _compare_setting(
            findings,
            node.node_id,
            "basis",
            requirement.basis_or_ecp,
            settings.get("basis"),
            "cmd.science.method.basis_mismatch",
        )
        if program == "gaussian" and requirement.integration_grid is not None:
            normalized_grid = _normalized(requirement.integration_grid)
            expected_route = (
                "Int=UltraFine"
                if normalized_grid in {"ultrafine", "99590"}
                else requirement.integration_grid
            )
            _compare_setting(
                findings,
                node.node_id,
                "integration_grid",
                expected_route,
                settings.get("additional_route_parameters"),
                "cmd.science.method.integration_grid_mismatch",
            )
    _compare_setting(
        findings,
        node.node_id,
        "solvent_model",
        requirement.solvent_model,
        settings.get("solvent_model"),
        "cmd.science.method.solvent_mismatch",
    )
    _compare_setting(
        findings,
        node.node_id,
        "solvent_id",
        requirement.solvent_id,
        settings.get("solvent_id"),
        "cmd.science.method.solvent_mismatch",
    )
    observed_frequency = bool(settings.get("freq"))
    if program != "xtb" and (
        requirement.frequency_required is not None
        and observed_frequency != requirement.frequency_required
    ):
        findings.append(
            _finding(
                "cmd.science.method.frequency_mismatch",
                node.node_id,
                "frequency_required",
                requirement.frequency_required,
                observed_frequency,
            )
        )


def _validate_xtb_settings(
    node: CommandNode,
    requirement: NodeScientificRequirement,
    findings: list[CommandCounterexample],
) -> None:
    values = {_parameter_name(key): value for key, value in node.parameters.items()}
    observed_method = values.get("gfn_version")
    if _normalized(observed_method) != _normalized(requirement.method):
        findings.append(
            _finding(
                "cmd.science.xtb.gfn_mismatch",
                node.node_id,
                "gfn_version",
                requirement.method,
                observed_method,
            )
        )
    _compare_setting(
        findings,
        node.node_id,
        "optimization_level",
        requirement.optimization_level,
        values.get("optimization_level"),
        "cmd.science.xtb.optimization_level_mismatch",
    )
    observed_model = values.get("solvent_model")
    observed_solvent = values.get("solvent_id")
    if (observed_model is None) != (observed_solvent is None):
        findings.append(
            _finding(
                "cmd.science.xtb.solvent_pair_incomplete",
                node.node_id,
                "solvent",
                "both solvent_model and solvent_id or neither",
                "incomplete",
            )
        )
    _compare_setting(
        findings,
        node.node_id,
        "solvent_model",
        requirement.solvent_model,
        observed_model,
        "cmd.science.xtb.solvent_mismatch",
    )
    _compare_setting(
        findings,
        node.node_id,
        "solvent_id",
        requirement.solvent_id,
        observed_solvent,
        "cmd.science.xtb.solvent_mismatch",
    )


def _validate_xtb_job_controls(
    node: CommandNode,
    requirement: NodeScientificRequirement,
    findings: list[CommandCounterexample],
) -> None:
    values = {_parameter_name(key): value for key, value in node.parameters.items()}
    if requirement.gradient_required is None:
        if "grad" in values:
            findings.append(
                _finding(
                    "cmd.science.xtb.gradient_mismatch",
                    node.node_id,
                    "gradient_required",
                    "not explicitly requested",
                    values["grad"],
                )
            )
    else:
        _compare_setting(
            findings,
            node.node_id,
            "gradient_required",
            requirement.gradient_required,
            values.get("grad", False),
            "cmd.science.xtb.gradient_mismatch",
        )
    if requirement.frequency_required is not None:
        observed_frequency = requirement.job_kind == "hess"
        if observed_frequency != requirement.frequency_required:
            findings.append(
                _finding(
                    "cmd.science.method.frequency_mismatch",
                    node.node_id,
                    "frequency_required",
                    requirement.frequency_required,
                    observed_frequency,
                )
            )


def _validate_generated_preview(
    task: ScientificTaskSpec,
    node_id: str,
    requirement: NodeScientificRequirement,
    semantic: CommandSemanticResult,
    findings: list[CommandCounterexample],
) -> None:
    generated = [item for item in semantic.generated_inputs if isinstance(item, Mapping)]
    if not generated:
        findings.append(
            _finding(
                "cmd.science.preview.generated_input_missing",
                node_id,
                "generated_inputs",
                "safe-preview generated input evidence",
                "missing",
            )
        )
        return
    if len(generated) != 1:
        findings.append(
            _finding(
                "cmd.science.preview.generated_input_cardinality",
                node_id,
                "generated_inputs",
                "exactly one generated artifact for the M2 single-frame slice",
                len(generated),
            )
        )
    matching_state = [
        item
        for item in generated
        if item.get("charge") == task.electronic_state.charge
        and item.get("multiplicity") == task.electronic_state.multiplicity
    ]
    if not matching_state:
        findings.append(
            _finding(
                "cmd.science.preview.electronic_state_mismatch",
                node_id,
                "generated_inputs",
                "matching charge and multiplicity",
                "mismatch",
            )
        )
    matching_geometry: list[Mapping[str, Any]] = []
    identity_records = matching_state
    if requirement.program in {"gaussian", "orca", "xtb"}:
        matching_geometry = [
            item
            for item in generated
            if item.get("ordered_geometry_sha256")
            == task.geometry.ordered_geometry_sha256
        ]
        if not matching_geometry:
            findings.append(
                _finding(
                    "cmd.science.preview.geometry_manifest_mismatch",
                    node_id,
                    "generated_inputs",
                    task.geometry.ordered_geometry_sha256,
                    "not_observed",
                )
            )
        identity_records = [
            item
            for item in matching_state
            if item.get("ordered_geometry_sha256")
            == task.geometry.ordered_geometry_sha256
        ]
        if matching_state and matching_geometry and not identity_records:
            findings.append(
                _finding(
                    "cmd.science.preview.identity_split_across_artifacts",
                    node_id,
                    "generated_inputs",
                    "one generated artifact with matching state and geometry",
                    "evidence split across artifacts",
                )
            )
    if requirement.program in {"gaussian", "orca"}:
        _validate_preview_route(
            node_id,
            requirement,
            identity_records,
            findings,
        )
    elif requirement.program == "xtb":
        _validate_preview_xtb_route(
            node_id,
            requirement,
            identity_records,
            findings,
        )


def _validate_preview_route(
    node_id: str,
    requirement: NodeScientificRequirement,
    generated: list[Mapping[str, Any]],
    findings: list[CommandCounterexample],
) -> None:
    if not generated:
        findings.append(
            _finding(
                "cmd.science.preview.route_identity_unbound",
                node_id,
                "generated_inputs",
                "one identity-matched generated artifact",
                "missing",
            )
        )
        return
    route_candidate_sets = tuple(
        _route_setting_candidates(str(item.get("route") or ""))
        for item in generated
    )
    required_settings = tuple(
        (field, _normalized(expected), expected)
        for field, expected in (
            ("method", requirement.method),
            ("basis_or_ecp", requirement.basis_or_ecp),
            ("solvent_model", requirement.solvent_model),
            ("solvent_id", requirement.solvent_id),
            ("integration_grid", requirement.integration_grid),
        )
        if expected is not None
    )
    def _frequency_matches(candidates: frozenset[str]) -> bool:
        if requirement.frequency_required is None:
            return True
        observed = bool(
            candidates.intersection({"freq", "frequency", "numfreq", "anfreq"})
        )
        return observed == requirement.frequency_required

    if any(
        all(normalized in candidates for _, normalized, _ in required_settings)
        and _frequency_matches(candidates)
        for candidates in route_candidate_sets
    ):
        return
    individually_observed = True
    for field, normalized_expected, expected in required_settings:
        if not any(
            normalized_expected in candidates
            for candidates in route_candidate_sets
        ):
            individually_observed = False
            findings.append(
                _finding(
                    "cmd.science.preview.route_setting_mismatch",
                    node_id,
                    field,
                    expected,
                    "not_observed",
                )
            )
    if requirement.frequency_required is not None and not any(
        _frequency_matches(candidates) for candidates in route_candidate_sets
    ):
        individually_observed = False
        findings.append(
            _finding(
                "cmd.science.preview.route_setting_mismatch",
                node_id,
                "frequency_required",
                requirement.frequency_required,
                "not_observed",
            )
        )
    if individually_observed:
        findings.append(
            _finding(
                "cmd.science.preview.route_semantics_split_across_artifacts",
                node_id,
                "generated_inputs",
                "one generated artifact containing every required route setting",
                "settings split across artifacts",
            )
        )


def _validate_preview_xtb_route(
    node_id: str,
    requirement: NodeScientificRequirement,
    generated: list[Mapping[str, Any]],
    findings: list[CommandCounterexample],
) -> None:
    """Bind xTB's generated program call to the typed scientific request."""

    if not generated:
        findings.append(
            _finding(
                "cmd.science.preview.route_identity_unbound",
                node_id,
                "generated_inputs",
                "one identity-matched xTB program call",
                "missing",
            )
        )
        return
    observations = tuple(
        _xtb_route_observation(str(item.get("route") or ""), requirement)
        for item in generated
    )
    required_fields = tuple(observations[0])
    if any(all(observation.values()) for observation in observations):
        return
    individually_observed = True
    for field in required_fields:
        if any(observation[field] for observation in observations):
            continue
        individually_observed = False
        findings.append(
            _finding(
                "cmd.science.preview.xtb_route_setting_mismatch",
                node_id,
                field,
                _xtb_expected_value(requirement, field),
                "not_observed",
            )
        )
    if individually_observed:
        findings.append(
            _finding(
                "cmd.science.preview.route_semantics_split_across_artifacts",
                node_id,
                "generated_inputs",
                "one generated artifact containing every required xTB setting",
                "settings split across artifacts",
            )
        )


def _xtb_route_observation(
    route: str,
    requirement: NodeScientificRequirement,
) -> dict[str, bool]:
    try:
        tokens = tuple(token.lower() for token in shlex.split(route))
    except ValueError:
        tokens = ()

    def _value_after(flag: str) -> str | None:
        try:
            index = tokens.index(flag)
        except ValueError:
            return None
        return tokens[index + 1] if index + 1 < len(tokens) else None

    method = requirement.method.lower()
    if method == "gfnff":
        method_matches = "--gfnff" in tokens
    elif method.startswith("gfn") and method[-1:].isdigit():
        method_matches = _value_after("--gfn") == method[-1]
    else:
        method_matches = f"--{method}" in tokens

    if requirement.job_kind == "opt":
        job_matches = "--opt" in tokens and "--hess" not in tokens
    elif requirement.job_kind == "hess":
        job_matches = "--hess" in tokens and "--opt" not in tokens
    else:
        job_matches = "--opt" not in tokens and "--hess" not in tokens

    observation = {
        "method": method_matches,
        "job_kind": job_matches,
    }
    if requirement.optimization_level is not None:
        observation["optimization_level"] = (
            _value_after("--opt") == requirement.optimization_level.lower()
        )
    if requirement.solvent_model is None:
        observation["solvent"] = not any(
            f"--{model}" in tokens for model in XTB_ALL_SOLVENT_MODELS
        )
    else:
        solvent_flag = f"--{requirement.solvent_model.lower()}"
        observation["solvent"] = (
            _value_after(solvent_flag) == str(requirement.solvent_id).lower()
        )
    if requirement.gradient_required is not None:
        observation["gradient_required"] = (
            ("--grad" in tokens) == requirement.gradient_required
        )
    if requirement.frequency_required is not None:
        observation["frequency_required"] = (
            ("--hess" in tokens) == requirement.frequency_required
        )
    return observation


def _xtb_expected_value(
    requirement: NodeScientificRequirement,
    field: str,
) -> Any:
    if field == "job_kind":
        return requirement.job_kind
    if field == "method":
        return requirement.method
    if field == "solvent":
        return {
            "model": requirement.solvent_model,
            "id": requirement.solvent_id,
        }
    return getattr(requirement, field)


def _route_setting_candidates(route: str) -> frozenset[str]:
    """Return exact normalized route atoms, never substring matches."""

    candidates: set[str] = set()
    # Preserve the complete method/basis atoms before collecting generic route
    # words.  The basis grammar commonly contains a comma-bearing polarization
    # suffix (for example ``6-31+G(d,p)``), which a plain word tokenizer would
    # otherwise split and silently reject.
    for match in re.finditer(
        r"(?P<method>[A-Za-z0-9][A-Za-z0-9+*._-]*)/"
        r"(?P<basis>[A-Za-z0-9][A-Za-z0-9+*._-]*(?:\([^)]*\))?)",
        route,
    ):
        candidates.add(_normalized(match.group("method")))
        candidates.add(_normalized(match.group("basis")))

    # Assignment values cover Gaussian constructs such as
    # ``SCRF=(SMD,Solvent=Water)`` without accepting a substring (PBE is still
    # distinct from PBE0).
    for value in re.findall(r"=\s*([A-Za-z0-9][A-Za-z0-9+*._-]*)", route):
        candidates.add(_normalized(value))

    for token in re.findall(
        r"[A-Za-z0-9][A-Za-z0-9+*._-]*(?:\([^()]*\))?",
        route,
    ):
        normalized = _normalized(token)
        if normalized:
            candidates.add(normalized)
    return frozenset(candidates)


def _compare_setting(
    findings: list[CommandCounterexample],
    node_id: str,
    field: str,
    expected: Any,
    observed: Any,
    rule_id: str,
) -> None:
    if expected is None and observed is None:
        return
    if _normalized(expected) == _normalized(observed):
        return
    findings.append(_finding(rule_id, node_id, field, expected, observed))


def _program_from_node(node: CommandNode) -> str:
    return next((part for part in node.command_path if part in _PROGRAMS), "")


def _job_from_node(node: CommandNode, program: str) -> str:
    try:
        index = node.command_path.index(program)
    except ValueError:
        return ""
    return node.command_path[index + 1] if index + 1 < len(node.command_path) else ""


def _project_job_key(job_kind: str) -> str:
    return "td" if job_kind == "td" else job_kind


def _parameter_name(key: str) -> str:
    return key.rsplit(":", 1)[-1]


def _normalized(value: Any) -> str:
    return re.sub(r"[\s_-]+", "", str(value or "").lower())


def _validation(
    task: ScientificTaskSpec,
    findings: list[CommandCounterexample],
) -> ScientificTaskValidation:
    clarification_rules = {
        "cmd.science.unresolved_fact",
        "cmd.science.node_requirement_missing",
        "cmd.science.node_requirement_unbound",
        "cmd.science.evidence.unsupported",
    }
    infeasible_rules = {
        "cmd.science.job_unverifiable",
        "cmd.science.constraint.unverifiable",
        "cmd.science.geometry.handoff_unverifiable",
        "cmd.science.basis_mapping_unverifiable",
    }
    if not findings:
        status: Literal["ok", "needs_clarification", "infeasible", "blocked"] = "ok"
    elif any(item.rule_id not in clarification_rules | infeasible_rules for item in findings):
        status = "blocked"
    elif any(item.rule_id in infeasible_rules for item in findings):
        status = "infeasible"
    else:
        status = "needs_clarification"
    return ScientificTaskValidation(
        task_spec_sha256=task_spec_sha256(task),
        status=status,
        molecule_id=task.molecule_id,
        requested_observable=task.requested_observable,
        required_evidence=task.required_evidence,
        post_execution_validation_obligations=(
            task.post_execution_validation_obligations
        ),
        findings=tuple(findings),
    )


def _finding(
    rule_id: str,
    node_id: str | None,
    failed_field: str,
    expected: Any,
    observed: Any,
) -> CommandCounterexample:
    safe_expected = _safe_value(expected)
    safe_observed = _safe_value(observed)
    payload = {
        "rule_id": rule_id,
        "node_id": node_id,
        "failed_field": failed_field,
        "expected": safe_expected,
        "observed": safe_observed,
    }
    evidence = _sha256_json(payload)
    return CommandCounterexample(
        rule_id=rule_id,
        node_id=node_id,
        failed_field=failed_field,
        expected=safe_expected,
        observed=safe_observed,
        evidence_id=f"ce-{evidence[:20]}",
    )


def _safe_value(value: Any) -> Any:
    if isinstance(value, Path):
        return "<redacted-path>"
    if isinstance(value, str):
        if "/" in value or "\\" in value or value.startswith("~"):
            return "<redacted-path>"
        return value[:256]
    if isinstance(value, Mapping):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item) for item in value]
    return value


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()


__all__ = [
    "ConstraintBinding",
    "ElectronicState",
    "GeometryIdentity",
    "NodeScientificRequirement",
    "PostExecutionValidationObligation",
    "SCIENTIFIC_TASK_SCHEMA_VERSION",
    "ScientificTaskSpec",
    "ScientificTaskValidation",
    "task_spec_sha256",
    "validate_scientific_preview",
    "validate_scientific_task_workflow",
]
