"""Model-facing typed tools for the command-compiled frontier path.

These tools are deliberately provider-free.  A model proposes JSON matching
``ScientificTaskSpec`` and ``CommandWorkflowSpec``; this module owns all path
resolution, Click-schema lookup, argv rendering, safe preview, and receipt
construction.  It never accepts a raw shell command or native engine input.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from pydantic import ValidationError

from chemsmart.agent.cli_schema import build_chemsmart_cli_schema
from chemsmart.agent.command_workflow import (
    CommandCounterexample,
    CommandNode,
    CommandWorkflowCompiler,
    CommandWorkflowSpec,
    cli_schema_digest,
)
from chemsmart.agent.compact_cli_schema import compact_cli_signature
from chemsmart.agent.harness.command_semantics import evaluate_command_semantics
from chemsmart.agent.harness.command_workflow_receipt import (
    build_command_workflow_receipt,
)
from chemsmart.agent.harness.intent import IntentSpec, evaluate_intent
from chemsmart.agent.schema_prune import prune_schema_for_request, schema_variant_id
from chemsmart.agent.scientific_task import (
    ScientificTaskSpec,
    task_spec_sha256,
    validate_scientific_preview,
    validate_scientific_task_workflow,
)
from chemsmart.agent.workspace_bindings import (
    compilation_context,
    discover_workspace_bindings,
)


_SHA256 = "^[0-9a-f]{64}$"
_ID = "^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"


def inspect_command_schema(request_context: str = "") -> dict[str, Any]:
    """Expose a request-pruned, digest-bound Click signature for typed IR.

    ``request_context`` is explanatory text used only to prune the schema. It
    is never treated as a command, a path, or a scientific source of truth.
    """

    live_schema = build_chemsmart_cli_schema()
    pruned = prune_schema_for_request(live_schema, str(request_context or ""))
    return {
        "ok": True,
        "cli_schema_digest": cli_schema_digest(live_schema),
        "schema_variant": schema_variant_id(pruned),
        "compact_cli_signature": compact_cli_signature(pruned),
        "model_boundary": {
            "accepts": ["ScientificTaskSpec", "CommandWorkflowSpec"],
            "rejects": [
                "raw_shell_command",
                "native_engine_input",
                "arbitrary_path",
                "flag_alias_or_order",
            ],
        },
    }


def inspect_command_workflow(
    scientific_task: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, Any]:
    """Compile typed intent without starting the safe CLI preview process."""

    return _prepare_workflow(
        scientific_task,
        workflow,
        run_safe_preview=False,
    )


def synthesize_command(
    scientific_task: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, Any]:
    """Validate and safely preview a typed command workflow.

    The function name is retained for Runtime V2 compatibility, but its input
    is no longer a natural-language request and its output becomes
    ``previewed`` only after every deterministic gate is green.
    """

    return _prepare_workflow(
        scientific_task,
        workflow,
        run_safe_preview=True,
    )


def repair_command(
    scientific_task: dict[str, Any],
    prior_workflow: dict[str, Any],
    candidate_workflow: dict[str, Any],
    counterexample: dict[str, Any],
    repair_attempt: int,
    prior_task_spec_sha256: str,
    prior_receipt_sha256: str,
    prior_rule_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Run at most two counterexample-guided typed-IR repairs.

    Repairs may alter only the parameter identified by the supplied compiler
    counterexample. ``prior_task_spec_sha256`` and
    ``prior_receipt_sha256`` are copied from the preceding receipt; an active
    Runtime V2 turn checks both against its observed state so a changed method,
    geometry, evidence obligation, or observable cannot be relabelled as a
    repair under the same task ID. Program, geometry binding, charge,
    multiplicity, project, dependencies, constraints, and execution intent
    are immutable here.
    """

    if not isinstance(repair_attempt, int) or repair_attempt < 1 or repair_attempt > 2:
        return _repair_blocked("cmd.repair.budget_exhausted", "repair_attempt")
    try:
        task = ScientificTaskSpec.model_validate(scientific_task)
        prior = CommandWorkflowSpec.model_validate(prior_workflow)
        candidate = CommandWorkflowSpec.model_validate(candidate_workflow)
        finding = CommandCounterexample.model_validate(counterexample)
    except ValidationError as exc:
        return _invalid_contract_result(exc)
    if prior_task_spec_sha256 != task_spec_sha256(task):
        return _repair_blocked("cmd.repair.scientific_task_changed", "scientific_task")
    prior_ids = {str(item) for item in (prior_rule_ids or [])}
    if finding.rule_id in prior_ids:
        return _repair_blocked("cmd.repair.repeated_rule", "counterexample.rule_id")
    violation = _repair_violation(prior, candidate, finding)
    if violation is not None:
        return _repair_blocked(violation, "candidate_workflow")
    result = _prepare_workflow(
        task.model_dump(mode="json"),
        candidate.model_dump(mode="json"),
        run_safe_preview=True,
    )
    result["repair"] = {
        "attempt": repair_attempt,
        "counterexample_rule_id": finding.rule_id,
        "counterexample_evidence_id": finding.evidence_id,
        "bounded": True,
    }
    return result


def _prepare_workflow(
    scientific_task: Mapping[str, Any],
    workflow: Mapping[str, Any],
    *,
    run_safe_preview: bool,
) -> dict[str, Any]:
    try:
        task = ScientificTaskSpec.model_validate(scientific_task)
        typed_workflow = CommandWorkflowSpec.model_validate(workflow)
    except ValidationError as exc:
        return _invalid_contract_result(exc)

    workspace = Path.cwd().resolve()
    try:
        bindings = discover_workspace_bindings(workspace)
    except ValueError:
        return _repair_blocked("cmd.workspace.unavailable", "workspace")
    task_preflight = validate_scientific_task_workflow(
        task,
        typed_workflow,
        bindings,
    )
    compiler = CommandWorkflowCompiler()
    compilation = compiler.compile(
        typed_workflow,
        compilation_context(bindings),
    )
    task_digest = task_spec_sha256(task)
    base = {
        "workflow_id": typed_workflow.workflow_id,
        "task_spec_id": typed_workflow.task_spec_id,
        "task_spec_sha256": task_digest,
        # This is typed, path-free scientific state rather than model
        # reasoning.  Runtime events may persist it alongside the digest so a
        # later evidence report can identify what the preview actually bound.
        "scientific_task": task.model_dump(mode="json"),
        "cli_schema_digest": compiler.schema_digest,
        "render_digest": compilation.render_digest,
        "compiler_status": compilation.status,
        "scientific_preflight": task_preflight.to_dict(),
    }

    if task_preflight.status != "ok":
        receipt = build_command_workflow_receipt(
            typed_workflow,
            compilation,
            task_spec_sha256=task_digest,
            additional_findings=task_preflight.findings,
            parser_cwd=str(workspace),
        )
        return _non_preview_result(
            base,
            status=task_preflight.status,
            compilation=compilation,
            receipt=receipt.to_dict(),
            extra_findings=task_preflight.findings,
        )

    if compilation.status != "previewable" or not run_safe_preview:
        receipt = build_command_workflow_receipt(
            typed_workflow,
            compilation,
            task_spec_sha256=task_digest,
            parser_cwd=str(workspace),
        )
        status = (
            "planned"
            if compilation.status == "planned"
            else "ready_for_safe_preview"
            if compilation.status == "previewable"
            else "blocked"
        )
        return _non_preview_result(
            base,
            status=status,
            compilation=compilation,
            receipt=receipt.to_dict(),
        )

    safe_results = {
        invocation.node_id: evaluate_command_semantics(
            invocation.display_command,
            cwd=workspace,
        )
        for invocation in compilation.invocations
    }
    intent_results = {
        invocation.node_id: evaluate_intent(
            invocation.display_command,
            _intent_spec_for_invocation(typed_workflow, invocation.node_id, bindings),
            cwd=str(workspace),
        )
        for invocation in compilation.invocations
    }
    scientific_preview = validate_scientific_preview(
        task,
        typed_workflow,
        compilation,
        safe_results,
        bindings,
    )
    receipt = build_command_workflow_receipt(
        typed_workflow,
        compilation,
        safe_preview_results=safe_results,
        intent_results=intent_results,
        parser_cwd=str(workspace),
        task_spec_sha256=task_digest,
        additional_findings=scientific_preview.findings,
    )
    base["scientific_preview"] = scientific_preview.to_dict()
    if receipt.status != "previewed":
        return _non_preview_result(
            base,
            status="blocked",
            compilation=compilation,
            receipt=receipt.to_dict(),
            extra_findings=scientific_preview.findings,
        )
    invocations = [_public_invocation(item) for item in compilation.invocations]
    primary = invocations[0] if invocations else None
    return {
        "ok": True,
        "status": "previewed",
        "cli_grounded": True,
        **base,
        "command": primary["command"] if primary is not None else "",
        "canonical_invocations": invocations,
        "receipt": receipt.to_dict(),
        "rule_ids": [],
        "execution": {
            "permitted": False,
            "reason": "M2 command-compiled path permits safe preview only",
        },
    }


def _non_preview_result(
    base: dict[str, Any],
    *,
    status: str,
    compilation: Any,
    receipt: dict[str, Any],
    extra_findings: tuple[CommandCounterexample, ...] | list[CommandCounterexample] = (),
) -> dict[str, Any]:
    findings = [*compilation.counterexamples, *extra_findings]
    result = {
        "ok": status in {"planned", "ready_for_safe_preview"},
        "status": status,
        "cli_grounded": False,
        **base,
        "invocation_summaries": [
            {
                "node_id": item.node_id,
                "click_path": list(item.command_path),
                "command_sha256": item.command_sha256,
                "project_id": item.project_id,
                "project_sha256": item.project_sha256,
            }
            for item in compilation.invocations
        ],
        "counterexamples": [item.model_dump(mode="json") for item in _unique_findings(findings)],
        "receipt": receipt,
        "execution": {
            "permitted": False,
            "reason": "command is not a previewed approval candidate",
        },
    }
    if status == "needs_clarification":
        result["missing_info"] = _clarification_slots(findings)
    return result


def _intent_spec_for_invocation(
    workflow: CommandWorkflowSpec,
    node_id: str,
    bindings: Any,
) -> IntentSpec:
    node = next(node for node in workflow.nodes if node.node_id == node_id)
    program = next((part for part in node.command_path if part in {"gaussian", "orca", "xtb"}), None)
    job = None
    if program is not None:
        index = node.command_path.index(program)
        if index + 1 < len(node.command_path):
            job = node.command_path[index + 1]
    project = None
    if node.project_ref is not None:
        binding = bindings.projects.get(node.project_ref.project_id)
        project = binding.command_value if binding is not None else None
    chemistry: dict[str, Any] = {}
    parameter_values = {
        key.rsplit(":", 1)[-1]: value for key, value in node.parameters.items()
    }
    if program == "xtb":
        for key in ("gfn_version", "solvent_model", "solvent_id", "optimization_level"):
            if parameter_values.get(key) is not None:
                chemistry[key] = parameter_values[key]
    input_path = _bound_input_path(node, bindings)
    resources = {
        key: parameter_values[key]
        for key in ("num_cores", "num_gpus", "mem_gb", "time_hours", "queue")
        if parameter_values.get(key) is not None
    }
    return IntentSpec(
        action=node.command_path[0],
        program=program,
        kind=("gaussian.tddft" if program == "gaussian" and job == "td" else f"{program}.{job}" if program and job else None),
        project=project,
        server=(
            str(parameter_values["server"])
            if parameter_values.get("server") is not None
            else None
        ),
        input_path=input_path,
        charge=node.charge,
        multiplicity=node.multiplicity,
        execution_mode="local" if node.command_path[0] == "run" else "submit",
        chemistry=chemistry,
        resources=resources,
    )


def _bound_input_path(node: CommandNode, bindings: Any) -> str | None:
    """Give the independent parser one host-derived relative input assertion."""

    candidates = [
        binding
        for binding in node.input_artifacts
        if binding.target_parameter.rsplit(":", 1)[-1] in {"filename", "filenames"}
    ]
    if len(candidates) != 1:
        return None
    resolved = bindings.artifacts.get(candidates[0].artifact_id)
    if resolved is None:
        return None
    try:
        return resolved.path.relative_to(bindings.workspace_root).as_posix()
    except ValueError:
        return None


def _public_invocation(invocation: Any) -> dict[str, Any]:
    return {
        "node_id": invocation.node_id,
        "click_path": list(invocation.command_path),
        "command": invocation.display_command,
        "argv": list(invocation.argv),
        "command_sha256": invocation.command_sha256,
        "cli_schema_digest": invocation.cli_schema_digest,
        "project_id": invocation.project_id,
        "project_sha256": invocation.project_sha256,
        "input_artifacts": [item.model_dump(mode="json") for item in invocation.input_artifacts],
        "environment_digest": invocation.environment_digest,
    }


def _repair_violation(
    prior: CommandWorkflowSpec,
    candidate: CommandWorkflowSpec,
    finding: CommandCounterexample,
) -> str | None:
    if (
        prior.workflow_id != candidate.workflow_id
        or prior.task_spec_id != candidate.task_spec_id
        or prior.cli_schema_digest != candidate.cli_schema_digest
    ):
        return "cmd.repair.workflow_identity_changed"
    prior_nodes = {node.node_id: node for node in prior.nodes}
    candidate_nodes = {node.node_id: node for node in candidate.nodes}
    if set(prior_nodes) != set(candidate_nodes) or finding.node_id not in prior_nodes:
        return "cmd.repair.node_identity_changed"
    changed: list[tuple[str, set[str]]] = []
    immutable_fields = (
        "command_path",
        "project_ref",
        "input_artifacts",
        "charge",
        "multiplicity",
        "execution_intent",
        "dependencies",
        "expected_artifact_classes",
        "constraint_ids",
    )
    for node_id, before in prior_nodes.items():
        after = candidate_nodes[node_id]
        if any(getattr(before, field) != getattr(after, field) for field in immutable_fields):
            return "cmd.repair.scientific_binding_changed"
        names = {
            name
            for name in set(before.parameters) | set(after.parameters)
            if before.parameters.get(name) != after.parameters.get(name)
        }
        if names:
            changed.append((node_id, names))
    if len(changed) != 1 or changed[0][0] != finding.node_id:
        return "cmd.repair.scope_not_minimal"
    target = finding.failed_field.rsplit(".", 1)[-1].rsplit(":", 1)[-1]
    if target == "parameters" or changed[0][1] != {target}:
        return "cmd.repair.field_not_counterexample_scoped"
    return None


def _repair_blocked(rule_id: str, field: str) -> dict[str, Any]:
    finding = _tool_finding(rule_id, field)
    return {
        "ok": False,
        "status": "blocked",
        "cli_grounded": False,
        "counterexamples": [finding.model_dump(mode="json")],
        "rule_ids": [rule_id],
    }


def _invalid_contract_result(
    validation_error: ValidationError | None = None,
) -> dict[str, Any]:
    finding = _tool_finding("cmd.ir.invalid_typed_contract", "typed_payload")
    details = _validation_error_findings(validation_error)
    findings = [finding, *details]
    return {
        "ok": False,
        "status": "needs_clarification",
        "cli_grounded": False,
        "counterexamples": [item.model_dump(mode="json") for item in findings],
        "rule_ids": [item.rule_id for item in findings],
    }


def _validation_error_findings(
    validation_error: ValidationError | None,
) -> list[CommandCounterexample]:
    """Expose bounded field-local repair evidence without echoing model input."""

    if validation_error is None:
        return []
    findings: list[CommandCounterexample] = []
    for error in validation_error.errors(include_url=False)[:5]:
        error_type = str(error.get("type") or "invalid").lower()
        normalized_type = "".join(
            character if character.isalnum() or character in "_.-" else "-"
            for character in error_type
        ).strip("-.") or "invalid"
        location = error.get("loc") or ("typed_payload",)
        field = ".".join(str(item) for item in location)[:255]
        if not field:
            field = "typed_payload"
        rule_id = f"cmd.ir.contract.{normalized_type}"[:196].rstrip("-.")
        message = str(error.get("msg") or "typed field accepted")[:200]
        evidence = hashlib.sha256(
            f"{rule_id}:{field}:{message}".encode("utf-8")
        ).hexdigest()
        findings.append(
            CommandCounterexample(
                rule_id=rule_id,
                node_id=None,
                failed_field=field,
                expected=message,
                observed=f"rejected:{normalized_type}",
                evidence_id=f"ce-{evidence[:20]}",
            )
        )
    return findings


def _tool_finding(rule_id: str, field: str) -> CommandCounterexample:
    digest = hashlib.sha256(f"{rule_id}:{field}".encode("utf-8")).hexdigest()
    return CommandCounterexample(
        rule_id=rule_id,
        node_id=None,
        failed_field=field,
        expected="typed JSON contract",
        observed="rejected",
        evidence_id=f"ce-{digest[:20]}",
    )


def _unique_findings(
    findings: list[CommandCounterexample] | tuple[CommandCounterexample, ...],
) -> list[CommandCounterexample]:
    by_key: dict[tuple[str, str | None, str, str], CommandCounterexample] = {}
    for item in findings:
        key = (item.rule_id, item.node_id, item.failed_field, item.evidence_id)
        by_key[key] = item
    return list(by_key.values())


def _clarification_slots(
    findings: list[CommandCounterexample]
    | tuple[CommandCounterexample, ...],
) -> list[str]:
    """Return only typed facts a user could resolve, never internal paths."""

    resolvable = {
        "cmd.science.unresolved_fact",
        "cmd.science.node_requirement_missing",
        "cmd.science.node_requirement_unbound",
        "cmd.science.evidence.unsupported",
    }
    return sorted(
        {
            item.failed_field
            for item in findings
            if item.rule_id in resolvable and item.failed_field
        }
    )


def tool_input_json_schema(name: str) -> dict[str, Any]:
    """Return an inlined JSON Schema; no dangling Pydantic ``$ref`` values."""

    workflow = _workflow_schema()
    task = _scientific_task_schema()
    if name == "inspect_command_schema":
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "request_context": {"type": "string", "maxLength": 2000}
            },
        }
    if name in {"inspect_command_workflow", "synthesize_command"}:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["scientific_task", "workflow"],
            "properties": {"scientific_task": task, "workflow": workflow},
        }
    if name == "repair_command":
        return {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "scientific_task",
                "prior_workflow",
                "candidate_workflow",
                "counterexample",
                "repair_attempt",
                "prior_task_spec_sha256",
                "prior_receipt_sha256",
            ],
            "properties": {
                "scientific_task": task,
                "prior_workflow": workflow,
                "candidate_workflow": workflow,
                "counterexample": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["rule_id", "failed_field", "evidence_id"],
                    "properties": {
                        "rule_id": {"type": "string", "pattern": "^cmd\\.[a-z0-9_.-]+$"},
                        "node_id": {"type": ["string", "null"], "pattern": _ID},
                        "failed_field": {"type": "string", "maxLength": 255},
                        "expected": {},
                        "observed": {},
                        "evidence_id": {"type": "string", "maxLength": 128},
                    },
                },
                "repair_attempt": {"type": "integer", "minimum": 1, "maximum": 2},
                "prior_task_spec_sha256": {"type": "string", "pattern": _SHA256},
                "prior_receipt_sha256": {"type": "string", "pattern": _SHA256},
                "prior_rule_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^cmd\\.[a-z0-9_.-]+$"},
                    "maxItems": 2,
                },
            },
        }
    raise ValueError(f"unknown command-workflow tool: {name}")


def _workflow_schema() -> dict[str, Any]:
    artifact = {
        "type": "object",
        "additionalProperties": False,
        "required": ["artifact_id", "sha256", "kind", "target_parameter"],
        "properties": {
            "artifact_id": {"type": "string", "pattern": _ID},
            "sha256": {"type": "string", "pattern": _SHA256},
            "kind": {"type": "string", "pattern": "^[a-z][a-z0-9_.-]*$"},
            "target_parameter": {"type": "string", "pattern": "^[a-z][a-z0-9_]*(?::[a-z][a-z0-9_/:-]*)?$"},
            "producer_node_id": {"type": ["string", "null"], "pattern": _ID},
        },
    }
    project = {
        "type": "object",
        "additionalProperties": False,
        "required": ["project_id", "sha256"],
        "properties": {
            "project_id": {"type": "string", "pattern": _ID},
            "sha256": {"type": "string", "pattern": _SHA256},
        },
    }
    node = {
        "type": "object",
        "additionalProperties": False,
        "required": ["node_id", "command_path"],
        "properties": {
            "node_id": {"type": "string", "pattern": _ID},
            "command_path": {
                "oneOf": [
                    {"type": "string", "pattern": "^[a-z0-9][a-z0-9_/-]*$"},
                    {"type": "array", "minItems": 1, "items": {"type": "string", "pattern": "^[a-z0-9][a-z0-9_-]*$"}},
                ]
            },
            "parameters": {"type": "object", "additionalProperties": True},
            "project_ref": {"type": ["object", "null"], "properties": project.get("properties"), "required": project.get("required"), "additionalProperties": False},
            "input_artifacts": {"type": "array", "items": artifact},
            "charge": {"type": ["integer", "null"]},
            "multiplicity": {"type": ["integer", "null"], "minimum": 1},
            "execution_intent": {"type": "string", "enum": ["preview", "local", "submit"]},
            "dependencies": {"type": "array", "items": {"type": "string", "pattern": _ID}, "uniqueItems": True},
            "expected_artifact_classes": {"type": "array", "items": {"type": "string", "pattern": "^[a-z][a-z0-9_.-]*$"}, "uniqueItems": True},
            "constraint_ids": {"type": "array", "items": {"type": "string", "pattern": _ID}, "uniqueItems": True},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["workflow_id", "task_spec_id", "cli_schema_digest", "nodes"],
        "properties": {
            "schema_version": {"type": "string", "const": "chemsmart.command-workflow.v1"},
            "workflow_id": {"type": "string", "pattern": _ID},
            "task_spec_id": {"type": "string", "pattern": _ID},
            "cli_schema_digest": {"type": "string", "pattern": _SHA256},
            "nodes": {"type": "array", "minItems": 1, "items": node},
        },
    }


def _scientific_task_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "task_spec_id",
            "molecule_id",
            "geometry",
            "electronic_state",
            "requested_observable",
            "node_requirements",
        ],
        "properties": {
            "schema_version": {"type": "string", "const": "chemsmart.scientific-task.v1"},
            "task_spec_id": {"type": "string", "pattern": _ID},
            "molecule_id": {"type": "string", "pattern": _ID},
            "geometry": {
                "type": "object",
                "additionalProperties": False,
                "required": ["frame_id", "artifact_id", "sha256", "ordered_geometry_sha256"],
                "properties": {
                    "frame_id": {"type": "string", "pattern": _ID},
                    "artifact_id": {"type": "string", "pattern": _ID},
                    "sha256": {"type": "string", "pattern": _SHA256},
                    "kind": {"type": "string", "const": "geometry.xyz"},
                    "coordinate_units": {"type": "string", "const": "angstrom"},
                    "ordered_geometry_sha256": {"type": "string", "pattern": _SHA256},
                },
            },
            "electronic_state": {
                "type": "object",
                "additionalProperties": False,
                "required": ["charge", "multiplicity"],
                "properties": {
                    "charge": {"type": "integer"},
                    "multiplicity": {"type": "integer", "minimum": 1},
                },
            },
            "requested_observable": {"type": "string", "minLength": 1, "maxLength": 240},
            "node_requirements": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["node_id", "program", "job_kind", "settings_source", "method"],
                    "properties": {
                        "node_id": {"type": "string", "pattern": _ID},
                        "program": {"type": "string", "enum": ["gaussian", "orca", "xtb"]},
                        "job_kind": {"type": "string", "pattern": "^[a-z][a-z0-9_-]*$"},
                        "settings_source": {"type": "string", "enum": ["project", "xtb_command"]},
                        "method": {"type": "string", "minLength": 1, "maxLength": 160},
                        "basis_or_ecp": {"type": ["string", "null"], "maxLength": 200},
                        "optimization_level": {"type": ["string", "null"], "maxLength": 80},
                        "solvent_model": {"type": ["string", "null"], "maxLength": 80},
                        "solvent_id": {"type": ["string", "null"], "maxLength": 120},
                        "integration_grid": {"type": ["string", "null"], "maxLength": 80},
                        "frequency_required": {"type": ["boolean", "null"]},
                        "gradient_required": {"type": ["boolean", "null"]},
                        "constraints_sha256": {"type": ["string", "null"], "pattern": _SHA256},
                    },
                },
            },
            "constraints": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["constraint_id", "kind", "definition_sha256"],
                    "properties": {
                        "constraint_id": {"type": "string", "pattern": _ID},
                        "kind": {
                            "type": "string",
                            "enum": [
                                "bond",
                                "angle",
                                "dihedral",
                                "freeze",
                                "qmmm_region",
                                "neb",
                            ],
                        },
                        "definition_sha256": {"type": "string", "pattern": _SHA256},
                    },
                },
            },
            "required_evidence": {"type": "array", "items": {"type": "string", "maxLength": 160}},
            "post_execution_validation_obligations": {
                "type": "array",
                "items": {
                    "type": "string",
                    "pattern": "^[a-z][a-z0-9_]{0,127}$",
                },
                "uniqueItems": True,
            },
            "unresolved_facts": {"type": "array", "items": {"type": "string", "maxLength": 160}},
        },
    }


__all__ = [
    "inspect_command_schema",
    "inspect_command_workflow",
    "repair_command",
    "synthesize_command",
    "tool_input_json_schema",
]
