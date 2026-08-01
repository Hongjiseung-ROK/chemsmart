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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from chemsmart.agent.command_workflow import (
    CommandCounterexample,
    CommandNode,
    CommandWorkflowCompilation,
    CommandWorkflowSpec,
)
from chemsmart.agent.geometry_identity import xyz_geometry_manifest
from chemsmart.agent.harness.command_semantics import CommandSemanticResult

if TYPE_CHECKING:  # pragma: no cover - imports only guide static checkers
    from chemsmart.agent.workspace_bindings import WorkspaceBindings


SCIENTIFIC_TASK_SCHEMA_VERSION = "chemsmart.scientific-task.v1"
_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
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
    solvent_model: str | None = Field(default=None, max_length=80)
    solvent_id: str | None = Field(default=None, max_length=120)
    frequency_required: bool | None = None
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
        elif self.settings_source != "xtb_command":
            raise ValueError("xTB method must come from a typed command field")
        elif self.basis_or_ecp is not None:
            raise ValueError("xTB requirement must not contain basis_or_ecp")
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
    unresolved_facts: tuple[str, ...] = ()

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
            },
            "findings": [item.model_dump(mode="json") for item in self.findings],
        }


def task_spec_sha256(task: ScientificTaskSpec) -> str:
    """Return a stable identity for the complete typed scientific task."""

    return _sha256_json(task.model_dump(mode="json"))


def validate_scientific_task_workflow(
    task: ScientificTaskSpec,
    workflow: CommandWorkflowSpec,
    bindings: "WorkspaceBindings",
) -> ScientificTaskValidation:
    """Validate scientific intent before command compilation or preview."""

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
    if program in {"gaussian", "orca"}:
        _validate_project_settings(node, requirement, program, bindings, findings)
    elif program == "xtb":
        _validate_xtb_settings(node, requirement, findings)


def _validate_node_geometry(
    task: ScientificTaskSpec,
    node: CommandNode,
    findings: list[CommandCounterexample],
) -> None:
    root_bindings = [
        item for item in node.input_artifacts if item.producer_node_id is None
    ]
    if not root_bindings:
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
    if requirement.frequency_required is not None and bool(settings.get("freq")) != requirement.frequency_required:
        findings.append(
            _finding(
                "cmd.science.method.frequency_mismatch",
                node.node_id,
                "frequency_required",
                requirement.frequency_required,
                bool(settings.get("freq")),
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
    if requirement.program in {"gaussian", "orca"}:
        _validate_preview_route(node_id, requirement, generated, findings)


def _validate_preview_route(
    node_id: str,
    requirement: NodeScientificRequirement,
    generated: list[Mapping[str, Any]],
    findings: list[CommandCounterexample],
) -> None:
    route_text = "\n".join(
        str(item.get("route") or "") + "\n" + str(item.get("content_tail") or "")
        for item in generated
    )
    for field, expected in (
        ("method", requirement.method),
        ("basis_or_ecp", requirement.basis_or_ecp),
        ("solvent_id", requirement.solvent_id),
    ):
        if expected is None:
            continue
        if _normalized(expected) not in _normalized(route_text):
            findings.append(
                _finding(
                    "cmd.science.preview.route_setting_mismatch",
                    node_id,
                    field,
                    expected,
                    "not_observed",
                )
            )


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
    "SCIENTIFIC_TASK_SCHEMA_VERSION",
    "ScientificTaskSpec",
    "ScientificTaskValidation",
    "task_spec_sha256",
    "validate_scientific_preview",
    "validate_scientific_task_workflow",
]
