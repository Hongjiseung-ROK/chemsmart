"""Typed, schema-grounded ChemSmart command workflow compilation.

This module deliberately accepts *intent data*, never a shell command or a
native Gaussian/ORCA/xTB input deck.  It resolves that data against the live
Click schema and host-owned project/artifact records before rendering a
canonical argv vector.  It is therefore suitable as the deterministic boundary
between a model tool call and the existing ChemSmart CLI.

Compilation is non-executing.  A caller must pass the resulting invocation to
the isolated safe-preview gate before it can be reported as ``previewed``.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from copy import deepcopy
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from chemsmart.agent.cli_schema import build_chemsmart_cli_schema


COMMAND_WORKFLOW_SCHEMA_VERSION = "chemsmart.command-workflow.v1"
_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_COMMAND_PART_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_PARAMETER_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_FILE_HASH_BYTES = 32 * 1024 * 1024
_COMPUTATIONAL_PROGRAMS = frozenset({"gaussian", "orca", "xtb"})
_PROJECT_OWNED_PARAMETERS = frozenset(
    {
        "ab_initio",
        "append_additional_info",
        "additional_opt_options",
        "additional_route_parameters",
        "aux_basis",
        "basis",
        "custom_solvent",
        "defgrid",
        "dieze_tag",
        "dispersion",
        "extrapolation_basis",
        "functional",
        "scf_algorithm",
        "scf_convergence",
        "scf_maxiter",
        "scf_tol",
        "semiempirical",
        "solvent_id",
        "solvent_model",
        "solvent_options",
        "solventfilename",
    }
)
_NATIVE_INPUT_PARAMETER_NAMES = frozenset(
    {
        "argv",
        "command",
        "gaussian_input",
        "input_deck",
        "native_input",
        "orca_input",
        "shell",
        "xtb_input",
    }
)
_V8_SUPPORTED_JOB_FIELDS = frozenset(
    {
        "charge",
        "execution",
        "file",
        "geom_from",
        "id",
        "kind",
        "label",
        "molecule_id",
        "mult",
        "multiplicity",
        "project",
        "record_id",
        "record_index",
        "server",
        "settings",
        "structure_id",
        "structure_index",
    }
)
_RUNTIME_CONTROL_PARAMETERS = frozenset(
    {"debug", "delete_scratch", "fake", "scratch", "stream", "test"}
)


class _Contract(BaseModel):
    """Strict, immutable public contracts returned by model-facing tools."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class _FrozenDict(dict):
    """JSON-serializable mapping which rejects post-validation mutation."""

    @staticmethod
    def _blocked(*_args: Any, **_kwargs: Any) -> None:
        raise TypeError("command contract mappings are immutable")

    __setitem__ = _blocked
    __delitem__ = _blocked
    __ior__ = _blocked
    clear = _blocked
    pop = _blocked
    popitem = _blocked
    setdefault = _blocked
    update = _blocked


def _deep_freeze(value: Any) -> Any:
    """Copy JSON-like model input into recursively immutable containers."""

    if isinstance(value, Mapping):
        return _FrozenDict(
            {
                str(key): _deep_freeze(item)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            }
        )
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(
            sorted(
                (_deep_freeze(item) for item in value),
                key=lambda item: json.dumps(item, sort_keys=True, default=str),
            )
        )
    return value


class ArtifactBinding(_Contract):
    """Opaque input artifact selected by the model, not a filesystem path."""

    artifact_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    kind: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_.-]*$",
    )
    target_parameter: str = Field(min_length=1, max_length=255)
    producer_node_id: str | None = Field(
        default=None,
        pattern=_IDENTIFIER_PATTERN,
    )

    @field_validator("target_parameter")
    @classmethod
    def _valid_target_parameter(cls, value: str) -> str:
        _validate_parameter_key(value)
        return value


class ProjectReference(_Contract):
    """Opaque, content-addressed project reference owned by the runtime."""

    project_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    sha256: str = Field(pattern=_SHA256_PATTERN)


class CommandNode(_Contract):
    """One deterministic ChemSmart invocation in an ordered workflow DAG."""

    node_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    command_path: tuple[str, ...]
    parameters: dict[str, Any] = Field(default_factory=dict)
    project_ref: ProjectReference | None = None
    input_artifacts: tuple[ArtifactBinding, ...] = ()
    charge: StrictInt | None = None
    multiplicity: StrictInt | None = Field(default=None, ge=1)
    execution_intent: Literal["preview", "local", "submit"] = "preview"
    dependencies: tuple[str, ...] = ()
    expected_artifact_classes: tuple[str, ...] = ()
    constraint_ids: tuple[str, ...] = ()

    @field_validator("command_path", mode="before")
    @classmethod
    def _normalise_command_path(
        cls, value: str | Sequence[str]
    ) -> tuple[str, ...]:
        if isinstance(value, str):
            parts = tuple(part for part in value.split("/") if part)
        elif isinstance(value, Sequence):
            parts = tuple(str(part) for part in value)
        else:
            raise ValueError("command_path must be a slash-delimited path")
        if not parts:
            raise ValueError("command_path cannot be empty")
        if parts[0] == "chemsmart":
            raise ValueError("command_path must omit the chemsmart executable")
        if any(not _COMMAND_PART_PATTERN.fullmatch(part) for part in parts):
            raise ValueError("command_path contains an invalid Click command")
        return parts

    @field_validator("parameters")
    @classmethod
    def _safe_parameter_keys(
        cls, value: dict[str, Any]
    ) -> dict[str, Any]:
        for key in value:
            _validate_parameter_key(key)
            _parameter_name_from_key(key)
        return _deep_freeze(value)

    @field_validator("dependencies")
    @classmethod
    def _valid_dependencies(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("dependencies must not contain duplicates")
        for dependency in value:
            if not re.fullmatch(_IDENTIFIER_PATTERN, dependency):
                raise ValueError("dependency is not a stable node identifier")
        return tuple(sorted(value))

    @field_validator("expected_artifact_classes")
    @classmethod
    def _valid_expected_classes(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("expected_artifact_classes must not contain duplicates")
        for artifact_class in value:
            if not re.fullmatch(r"^[a-z][a-z0-9_.-]*$", artifact_class):
                raise ValueError("expected artifact class is invalid")
        return tuple(sorted(value))

    @field_validator("constraint_ids")
    @classmethod
    def _valid_constraint_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("constraint_ids must not contain duplicates")
        for constraint_id in value:
            if not re.fullmatch(_IDENTIFIER_PATTERN, constraint_id):
                raise ValueError("constraint_ids must use stable identifiers")
        return tuple(sorted(value))


class CommandWorkflowSpec(_Contract):
    """Model-proposed workflow expressed entirely as typed command intent."""

    schema_version: Literal[COMMAND_WORKFLOW_SCHEMA_VERSION] = (
        COMMAND_WORKFLOW_SCHEMA_VERSION
    )
    workflow_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    task_spec_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    cli_schema_digest: str = Field(pattern=_SHA256_PATTERN)
    nodes: tuple[CommandNode, ...] = Field(min_length=1)

    @field_validator("nodes")
    @classmethod
    def _unique_node_ids(
        cls, value: tuple[CommandNode, ...]
    ) -> tuple[CommandNode, ...]:
        ids = [node.node_id for node in value]
        if len(set(ids)) != len(ids):
            raise ValueError("node_id values must be unique")
        return value


class ResolvedArtifact(_Contract):
    """Host-only artifact resolution record; ``path`` is never model input."""

    artifact_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    kind: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_.-]*$",
    )
    path: Path
    producer_node_id: str | None = Field(
        default=None,
        pattern=_IDENTIFIER_PATTERN,
    )


class ResolvedProject(_Contract):
    """Host-only project resolution record with a safe CLI project name."""

    project_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    program: Literal["gaussian", "orca", "xtb"]
    command_value: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    path: Path | None = None


class CompilationContext(_Contract):
    """Trusted runtime state required to ground a typed workflow."""

    workspace_root: Path
    environment_digest: str = Field(pattern=_SHA256_PATTERN)
    artifacts: dict[str, ResolvedArtifact] = Field(default_factory=dict)
    projects: dict[str, ResolvedProject] = Field(default_factory=dict)
    verify_artifact_content: bool = True
    max_artifact_bytes: int = Field(
        default=_MAX_FILE_HASH_BYTES,
        ge=1,
        le=1024 * 1024 * 1024,
    )


class ArtifactEvidenceRef(_Contract):
    """Path-free artifact information persisted with a command invocation."""

    artifact_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    kind: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_.-]*$",
    )


class CanonicalCommandInvocation(_Contract):
    """Canonical, schema-bound argv material for one safe CLI preview."""

    workflow_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    node_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    command_path: tuple[str, ...]
    argv: tuple[str, ...]
    display_command: str
    command_sha256: str = Field(pattern=_SHA256_PATTERN)
    cli_schema_digest: str = Field(pattern=_SHA256_PATTERN)
    project_id: str | None = Field(default=None, pattern=_IDENTIFIER_PATTERN)
    project_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    input_artifacts: tuple[ArtifactEvidenceRef, ...] = ()
    environment_digest: str = Field(pattern=_SHA256_PATTERN)
    intent_projection: dict[str, Any] = Field(default_factory=dict)

    @field_validator("intent_projection")
    @classmethod
    def _immutable_intent_projection(
        cls, value: dict[str, Any]
    ) -> dict[str, Any]:
        return _deep_freeze(value)


class CommandCounterexample(_Contract):
    """Minimal structured compiler evidence supplied to a bounded repair."""

    rule_id: str = Field(pattern=r"^cmd\.[a-z0-9_.-]+$")
    node_id: str | None = Field(default=None, pattern=_IDENTIFIER_PATTERN)
    failed_field: str = Field(min_length=1, max_length=255)
    expected: Any = None
    observed: Any = None
    evidence_id: str = Field(min_length=1, max_length=128)

    @field_validator("expected", "observed")
    @classmethod
    def _immutable_evidence_values(cls, value: Any) -> Any:
        return _deep_freeze(value)


class CommandWorkflowCompilation(_Contract):
    """Pure compilation result; no CLI process or chemistry engine ran."""

    workflow_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    status: Literal["previewable", "planned", "blocked"]
    invocations: tuple[CanonicalCommandInvocation, ...] = ()
    counterexamples: tuple[CommandCounterexample, ...] = ()
    unresolved_node_ids: tuple[str, ...] = ()
    render_digest: str = Field(pattern=_SHA256_PATTERN)

    @property
    def ready_for_safe_preview(self) -> bool:
        return self.status == "previewable"

    def preflight_material(self) -> dict[str, Any]:
        """Return path-free data for later ``CommandPreflightReceipt`` binding."""

        return {
            "workflow_id": self.workflow_id,
            "status": self.status,
            "render_digest": self.render_digest,
            "invocations": [item.model_dump(mode="json") for item in self.invocations],
            "counterexamples": [
                item.model_dump(mode="json") for item in self.counterexamples
            ],
        }


class V8CompactSpecMigration(_Contract):
    """Result of a deliberately narrow migration from the legacy compact SPEC.

    ``workflow`` is absent whenever any legacy field cannot be represented as
    a typed, live-schema command node.  This is intentional: callers must not
    fall back to the old string renderer or insert an upstream-geometry
    placeholder just to obtain a command-looking result.
    """

    status: Literal["migrated", "needs_clarification", "rejected"]
    workflow: CommandWorkflowSpec | None = None
    counterexamples: tuple[CommandCounterexample, ...] = ()


@dataclass(frozen=True)
class _SchemaOption:
    scope: tuple[str, ...]
    name: str
    opts: tuple[str, ...]
    value_type: str | dict[str, Any] | None
    choices: tuple[str, ...] | None
    is_flag: bool
    multiple: bool
    required: bool
    nargs: int

    @property
    def canonical_long_flag(self) -> str | None:
        long_flags = sorted(option for option in self.opts if option.startswith("--"))
        return long_flags[0] if long_flags else None


@dataclass(frozen=True)
class _SchemaPath:
    command_path: tuple[str, ...]
    nodes: tuple[Mapping[str, Any], ...]
    options: tuple[_SchemaOption, ...]


class CommandWorkflowCompiler:
    """Compile typed workflow intent against a live Click-schema snapshot."""

    def __init__(self, schema: Mapping[str, Any] | None = None) -> None:
        # The Click schema is part of every invocation identity.  Take a full
        # snapshot so a caller retaining the source mapping cannot mutate the
        # compiler's behavior after ``schema_digest`` has been computed.
        self._schema = deepcopy(schema or build_chemsmart_cli_schema())
        self.schema_digest = cli_schema_digest(self._schema)

    def compile(
        self,
        workflow: CommandWorkflowSpec,
        context: CompilationContext,
    ) -> CommandWorkflowCompilation:
        """Compile a workflow without spawning a process or writing files."""

        # ``model_copy(update=...)`` is intentionally unchecked by Pydantic.
        # Re-enter through the public schema at this trust boundary so copied
        # mappings cannot bypass key validation, canonical ordering, or deep
        # immutability before they influence argv rendering and digests.
        workflow = CommandWorkflowSpec.model_validate(
            workflow.model_dump(mode="json")
        )

        errors: list[CommandCounterexample] = []
        if workflow.cli_schema_digest != self.schema_digest:
            errors.append(
                _counterexample(
                    "cmd.schema.digest_mismatch",
                    None,
                    "cli_schema_digest",
                    self.schema_digest,
                    workflow.cli_schema_digest,
                )
            )

        errors.extend(_validate_workflow_graph(workflow))
        invalid_nodes = {
            error.node_id for error in errors if error.node_id is not None
        }
        invocations: list[CanonicalCommandInvocation] = []
        unresolved_nodes: list[str] = []
        compiled_node_ids: set[str] = set()

        for node in workflow.nodes:
            if node.node_id in invalid_nodes:
                unresolved_nodes.append(node.node_id)
                continue
            blocked_dependencies = [
                dependency
                for dependency in node.dependencies
                if dependency not in compiled_node_ids
            ]
            if blocked_dependencies:
                errors.append(
                    _counterexample(
                        "cmd.dag.upstream_unavailable",
                        node.node_id,
                        "dependencies",
                        "compiled dependency before dependent node",
                        blocked_dependencies,
                    )
                )
                unresolved_nodes.append(node.node_id)
                continue
            invocation, node_errors = self._compile_node(
                workflow, node, context
            )
            errors.extend(node_errors)
            if invocation is None:
                unresolved_nodes.append(node.node_id)
                continue
            invocations.append(invocation)
            compiled_node_ids.add(node.node_id)

        status = _compilation_status(errors)
        return CommandWorkflowCompilation(
            workflow_id=workflow.workflow_id,
            status=status,
            invocations=tuple(invocations),
            counterexamples=tuple(errors),
            unresolved_node_ids=tuple(dict.fromkeys(unresolved_nodes)),
            render_digest=_render_digest(invocations, errors),
        )

    def _compile_node(
        self,
        workflow: CommandWorkflowSpec,
        node: CommandNode,
        context: CompilationContext,
    ) -> tuple[CanonicalCommandInvocation | None, list[CommandCounterexample]]:
        errors: list[CommandCounterexample] = []
        schema_path = _resolve_schema_path(self._schema, node.command_path)
        if isinstance(schema_path, CommandCounterexample):
            return None, [
                _with_node(schema_path, node.node_id, "command_path")
            ]

        program = _program_from_path(node.command_path)
        errors.extend(_validate_node_contract(node, program))
        if errors:
            return None, errors

        values: dict[tuple[tuple[str, ...], str], Any] = {}
        artifact_option_addresses: set[tuple[tuple[str, ...], str]] = set()
        pending_artifact_option_addresses: set[tuple[tuple[str, ...], str]] = set()
        for key, value in node.parameters.items():
            option_or_error = _resolve_option(schema_path, key)
            if isinstance(option_or_error, CommandCounterexample):
                errors.append(_with_node(option_or_error, node.node_id, key))
                continue
            option = option_or_error
            if option.name in _RUNTIME_CONTROL_PARAMETERS:
                errors.append(
                    _counterexample(
                        "cmd.ir.runtime_control",
                        node.node_id,
                        key,
                        "runtime-owned safe-preview or approval policy",
                        option.name,
                    )
                )
                continue
            if _is_artifact_parameter(option):
                errors.append(
                    _counterexample(
                        "cmd.ir.raw_artifact_path",
                        node.node_id,
                        key,
                        "an ArtifactBinding selected by stable artifact_id",
                        _safe_value(value),
                    )
                )
                continue
            if _project_owns_parameter(
                program,
                option.name,
                project_bound=node.project_ref is not None,
            ):
                errors.append(
                    _counterexample(
                        "cmd.ir.project_owned_setting",
                        node.node_id,
                        key,
                        "approved project YAML referenced by project_ref",
                        option.name,
                    )
                )
                continue
            _set_value(values, option, value, node.node_id, key, errors)

        _ground_project(
            node=node,
            program=program,
            schema_path=schema_path,
            context=context,
            values=values,
            errors=errors,
        )
        _ground_charge_and_multiplicity(
            node=node,
            program=program,
            schema_path=schema_path,
            values=values,
            errors=errors,
        )
        artifact_refs = _ground_artifacts(
            node=node,
            schema_path=schema_path,
            context=context,
            program=program,
            values=values,
            artifact_option_addresses=artifact_option_addresses,
            pending_artifact_option_addresses=pending_artifact_option_addresses,
            errors=errors,
        )

        _validate_required_options(
            schema_path,
            values,
            node.node_id,
            errors,
            pending_artifact_option_addresses=pending_artifact_option_addresses,
        )
        _validate_values(
            schema_path,
            values,
            artifact_option_addresses,
            node.node_id,
            errors,
        )
        if errors:
            return None, errors

        argv = _render_argv(node.command_path, schema_path, values)
        display_command = shlex.join(argv)
        project = (
            context.projects.get(node.project_ref.project_id)
            if node.project_ref is not None
            else None
        )
        invocation = CanonicalCommandInvocation(
            workflow_id=workflow.workflow_id,
            node_id=node.node_id,
            command_path=node.command_path,
            argv=tuple(argv),
            display_command=display_command,
            command_sha256=_sha256_text(display_command),
            cli_schema_digest=self.schema_digest,
            project_id=project.project_id if project is not None else None,
            project_sha256=project.sha256 if project is not None else None,
            input_artifacts=tuple(artifact_refs),
            environment_digest=context.environment_digest,
            intent_projection=_intent_projection(
                node,
                values,
                artifact_option_addresses,
            ),
        )
        return invocation, []


def compile_command_workflow(
    workflow: CommandWorkflowSpec,
    context: CompilationContext,
    *,
    schema: Mapping[str, Any] | None = None,
) -> CommandWorkflowCompilation:
    """Convenience entry point for a one-shot deterministic compilation."""

    return CommandWorkflowCompiler(schema).compile(workflow, context)


def migrate_v8_compact_spec(
    compact_spec: Mapping[str, Any],
    *,
    cli_schema_digest: str,
    artifact_bindings: Mapping[str, ArtifactBinding],
    project_references: Mapping[str, ProjectReference],
    task_spec_id: str = "legacy-v8-migration",
    workflow_id: str | None = None,
    default_project_ref: ProjectReference | None = None,
    schema: Mapping[str, Any] | None = None,
) -> V8CompactSpecMigration:
    """Migrate the safe subset of the compact v8 SPEC into typed IR.

    This is a migration *reader*, not a second renderer.  It uses the live
    Click tree to resolve every path and option, and it refuses the legacy
    ``<upstream-geometry>`` convention.  ``artifact_bindings`` is deliberately
    keyed by explicit legacy aliases such as ``file:water.xyz`` and
    ``geom_from:job-1``; the source string is never copied into the resulting
    workflow.  A missing receipt leaves the migration in
    ``needs_clarification`` rather than manufacturing a path placeholder.

    Historical aliases such as ``gaussian.tddft`` and ``gaussian.freq`` are
    not silently rewritten here because their old renderer injected raw route
    text.  A caller must express their current CLI path and approved project
    settings directly in :class:`CommandWorkflowSpec`.
    """

    live_schema = dict(schema or build_chemsmart_cli_schema())
    # The public keyword ``cli_schema_digest`` is intentionally retained for
    # migration-call compatibility, so use a private helper rather than
    # accidentally calling the string parameter.
    live_digest = _live_schema_digest(live_schema)
    errors: list[CommandCounterexample] = []
    if cli_schema_digest != live_digest:
        errors.append(
            _counterexample(
                "cmd.migration.schema_digest_mismatch",
                None,
                "cli_schema_digest",
                live_digest,
                cli_schema_digest,
            )
        )
    if compact_spec.get("intent") != "workflow":
        errors.append(
            _counterexample(
                "cmd.migration.not_workflow",
                None,
                "intent",
                "workflow",
                _safe_value(compact_spec.get("intent")),
            )
        )
    raw_jobs = compact_spec.get("jobs")
    if not isinstance(raw_jobs, Sequence) or isinstance(raw_jobs, (str, bytes)):
        errors.append(
            _counterexample(
                "cmd.migration.jobs_required",
                None,
                "jobs",
                "non-empty compact SPEC jobs list",
                _safe_value(raw_jobs),
            )
        )
        return V8CompactSpecMigration(
            status="rejected", counterexamples=tuple(errors)
        )
    if not raw_jobs:
        errors.append(
            _counterexample(
                "cmd.migration.jobs_required",
                None,
                "jobs",
                "at least one compact SPEC job",
                [],
            )
        )

    nodes: list[CommandNode] = []
    seen_node_ids: set[str] = set()
    for index, raw_job in enumerate(raw_jobs):
        if not isinstance(raw_job, Mapping):
            errors.append(
                _counterexample(
                    "cmd.migration.job_type",
                    None,
                    f"jobs[{index}]",
                    "JSON object",
                    _safe_value(raw_job),
                )
            )
            continue
        node, job_errors = _migrate_v8_job(
            raw_job,
            index=index,
            schema=live_schema,
            artifact_bindings=artifact_bindings,
            project_references=project_references,
            default_project_ref=default_project_ref,
        )
        errors.extend(job_errors)
        if node is None:
            continue
        if node.node_id in seen_node_ids:
            errors.append(
                _counterexample(
                    "cmd.migration.duplicate_node_id",
                    node.node_id,
                    "id",
                    "unique compact SPEC job id",
                    node.node_id,
                )
            )
            continue
        seen_node_ids.add(node.node_id)
        nodes.append(node)

    if errors:
        return V8CompactSpecMigration(
            status=(
                "rejected"
                if any(error.rule_id == "cmd.migration.schema_digest_mismatch" for error in errors)
                else "needs_clarification"
            ),
            counterexamples=tuple(errors),
        )
    if not nodes:
        return V8CompactSpecMigration(
            status="rejected",
            counterexamples=(
                _counterexample(
                    "cmd.migration.no_nodes",
                    None,
                    "jobs",
                    "at least one migratable job",
                    [],
                ),
            ),
        )
    if workflow_id is None:
        digest = _sha256_text(
            json.dumps(compact_spec, sort_keys=True, separators=(",", ":"), default=str)
        )
        workflow_id = f"v8-{digest[:20]}"
    try:
        workflow = CommandWorkflowSpec(
            workflow_id=workflow_id,
            task_spec_id=task_spec_id,
            cli_schema_digest=live_digest,
            nodes=tuple(nodes),
        )
    except ValueError as exc:
        return V8CompactSpecMigration(
            status="rejected",
            counterexamples=(
                _counterexample(
                    "cmd.migration.invalid_contract",
                    None,
                    "compact_spec",
                    "representable CommandWorkflowSpec",
                    str(exc),
                ),
            ),
        )
    return V8CompactSpecMigration(status="migrated", workflow=workflow)


def _migrate_v8_job(
    raw_job: Mapping[str, Any],
    *,
    index: int,
    schema: Mapping[str, Any],
    artifact_bindings: Mapping[str, ArtifactBinding],
    project_references: Mapping[str, ProjectReference],
    default_project_ref: ProjectReference | None,
) -> tuple[CommandNode | None, list[CommandCounterexample]]:
    errors: list[CommandCounterexample] = []
    for field in sorted(str(key) for key in raw_job if key not in _V8_SUPPORTED_JOB_FIELDS):
        errors.append(
            _counterexample(
                "cmd.migration.unsupported_job_field",
                None,
                f"jobs[{index}].{field}",
                "an explicitly supported v8 field or a direct typed IR rewrite",
                field,
            )
        )
    raw_id = raw_job.get("id", f"v8-job-{index + 1}")
    node_id = str(raw_id)
    if not re.fullmatch(_IDENTIFIER_PATTERN, node_id):
        errors.append(
            _counterexample(
                "cmd.migration.node_id",
                None,
                f"jobs[{index}].id",
                "stable node identifier",
                _safe_value(raw_id),
            )
        )
        return None, errors
    kind = raw_job.get("kind")
    if not isinstance(kind, str) or "." not in kind:
        errors.append(
            _counterexample(
                "cmd.migration.kind",
                node_id,
                "kind",
                "'<program>.<live CLI job>'",
                _safe_value(kind),
            )
        )
        return None, errors
    program, suffix = kind.split(".", 1)
    execution = raw_job.get("execution")
    action = "sub" if execution == "submit" else "run"
    settings = raw_job.get("settings", {})
    if not isinstance(settings, Mapping):
        errors.append(
            _counterexample(
                "cmd.migration.settings_type",
                node_id,
                "settings",
                "object of canonical CLI parameter names",
                _safe_value(settings),
            )
        )
        return None, errors
    command_path, path_error = _v8_live_command_path(
        schema,
        action=action,
        program=program,
        suffix=suffix,
        settings=settings,
        node_id=node_id,
    )
    if path_error is not None:
        return None, [path_error]
    schema_path = _resolve_schema_path(schema, command_path)
    if isinstance(schema_path, CommandCounterexample):
        return None, [_with_node(schema_path, node_id, "kind")]

    parameters: dict[str, Any] = {}
    for key, value in settings.items():
        if key == "parent_job" and suffix == "qmmm":
            continue
        if not isinstance(key, str):
            errors.append(
                _counterexample(
                    "cmd.migration.setting_name",
                    node_id,
                    "settings",
                    "canonical string parameter name",
                    _safe_value(key),
                )
            )
            continue
        try:
            _validate_parameter_key(key)
        except ValueError:
            errors.append(
                _counterexample(
                    "cmd.migration.setting_name",
                    node_id,
                    f"settings.{key}",
                    "canonical CLI parameter name",
                    _safe_value(key),
                )
            )
            continue
        option_or_error = _resolve_option(schema_path, key)
        if isinstance(option_or_error, CommandCounterexample):
            errors.append(_with_node(option_or_error, node_id, f"settings.{key}"))
            continue
        option = option_or_error
        if option.name in _RUNTIME_CONTROL_PARAMETERS:
            errors.append(
                _counterexample(
                    "cmd.migration.runtime_control",
                    node_id,
                    f"settings.{key}",
                    "runtime-owned safe-preview or approval policy",
                    option.name,
                )
            )
            continue
        if _is_artifact_parameter(option):
            errors.append(
                _counterexample(
                    "cmd.migration.artifact_binding_required",
                    node_id,
                    f"settings.{key}",
                    "ArtifactBinding rather than a raw path setting",
                    _safe_value(value),
                )
            )
            continue
        if _project_owns_parameter(program, option.name):
            errors.append(
                _counterexample(
                    "cmd.migration.project_owned_setting",
                    node_id,
                    f"settings.{key}",
                    "approved project YAML represented by project_ref",
                    option.name,
                )
            )
            continue
        parameters[key] = value

    for key in (
        "server",
        "label",
        "record_index",
        "record_id",
        "structure_index",
        "structure_id",
        "molecule_id",
    ):
        if key not in raw_job or raw_job[key] is None:
            continue
        parameter_key = f"{action}:{key}" if key == "server" else key
        option_or_error = _resolve_option(schema_path, parameter_key)
        if isinstance(option_or_error, CommandCounterexample):
            errors.append(_with_node(option_or_error, node_id, key))
            continue
        parameters[parameter_key] = raw_job[key]

    input_artifacts = _v8_artifact_bindings(
        raw_job,
        node_id=node_id,
        artifact_bindings=artifact_bindings,
        errors=errors,
    )
    project_ref = _v8_project_reference(
        raw_job,
        node_id=node_id,
        project_references=project_references,
        default_project_ref=default_project_ref,
        errors=errors,
    )
    if program in {"gaussian", "orca"} and project_ref is None:
        errors.append(
            _counterexample(
                "cmd.migration.project_reference",
                node_id,
                "project",
                "registered approved project reference",
                None,
            )
        )
    dependencies = ()
    geom_from = raw_job.get("geom_from")
    if geom_from is not None:
        producer = str(geom_from)
        if not re.fullmatch(_IDENTIFIER_PATTERN, producer):
            errors.append(
                _counterexample(
                    "cmd.migration.geom_from",
                    node_id,
                    "geom_from",
                    "stable producer node id",
                    _safe_value(geom_from),
                )
            )
        else:
            dependencies = (producer,)
    if errors:
        return None, errors
    charge = raw_job.get("charge", 0)
    multiplicity = raw_job.get("mult", raw_job.get("multiplicity", 1))
    try:
        node = CommandNode(
            node_id=node_id,
            command_path=command_path,
            parameters=parameters,
            project_ref=project_ref,
            input_artifacts=tuple(input_artifacts),
            charge=charge if program in _COMPUTATIONAL_PROGRAMS else None,
            multiplicity=(
                multiplicity if program in _COMPUTATIONAL_PROGRAMS else None
            ),
            execution_intent="submit" if action == "sub" else "preview",
            dependencies=dependencies,
        )
    except ValueError as exc:
        errors.append(
            _counterexample(
                "cmd.migration.invalid_node",
                node_id,
                "job",
                "typed CommandNode",
                str(exc),
            )
        )
        return None, errors
    return node, errors


def _v8_live_command_path(
    schema: Mapping[str, Any],
    *,
    action: str,
    program: str,
    suffix: str,
    settings: Mapping[str, Any],
    node_id: str,
) -> tuple[tuple[str, ...], CommandCounterexample | None]:
    action_node = schema.get("subcommands", {}).get(action)
    if not isinstance(action_node, Mapping):
        return (), _counterexample(
            "cmd.migration.action_unavailable",
            node_id,
            "execution",
            "live run or sub command",
            action,
        )
    program_node = action_node.get("subcommands", {}).get(program)
    if not isinstance(program_node, Mapping):
        return (), _counterexample(
            "cmd.migration.program_unavailable",
            node_id,
            "kind",
            "program present in the live Click schema",
            program,
        )
    subcommands = program_node.get("subcommands", {})
    if not isinstance(subcommands, Mapping):
        return (), _counterexample(
            "cmd.migration.kind_unavailable",
            node_id,
            "kind",
            "live CLI subcommand",
            suffix,
        )
    if suffix == "qmmm":
        parent = settings.get("parent_job")
        if not isinstance(parent, str) or parent not in subcommands:
            return (), _counterexample(
                "cmd.migration.qmmm_parent_required",
                node_id,
                "settings.parent_job",
                "live parent job name for qmmm",
                _safe_value(parent),
            )
        parent_node = subcommands.get(parent)
        if not isinstance(parent_node, Mapping) or "qmmm" not in parent_node.get(
            "subcommands", {}
        ):
            return (), _counterexample(
                "cmd.migration.qmmm_path_unavailable",
                node_id,
                "settings.parent_job",
                "live <parent>/qmmm path",
                parent,
            )
        return (action, program, parent, "qmmm"), None
    if suffix not in subcommands:
        return (), _counterexample(
            "cmd.migration.kind_unrepresentable",
            node_id,
            "kind",
            "exact live CLI job subcommand; rewrite aliases and route-level jobs as typed IR",
            suffix,
        )
    return (action, program, suffix), None


def _v8_artifact_bindings(
    raw_job: Mapping[str, Any],
    *,
    node_id: str,
    artifact_bindings: Mapping[str, ArtifactBinding],
    errors: list[CommandCounterexample],
) -> tuple[ArtifactBinding, ...]:
    source: str | None = None
    legacy_key: str | None = None
    if raw_job.get("file") is not None:
        raw_file = raw_job.get("file")
        if not isinstance(raw_file, str) or not _safe_legacy_artifact_alias(raw_file):
            errors.append(
                _counterexample(
                    "cmd.migration.placeholder_or_path",
                    node_id,
                    "file",
                    "registered file:<legacy-alias> ArtifactBinding",
                    _safe_value(raw_file),
                )
            )
            return ()
        source = raw_file
        legacy_key = f"file:{source}"
    elif raw_job.get("geom_from") is not None:
        raw_producer = raw_job.get("geom_from")
        producer = str(raw_producer)
        source = producer
        legacy_key = f"geom_from:{producer}"
    else:
        errors.append(
            _counterexample(
                "cmd.migration.artifact_binding_required",
                node_id,
                "file",
                "file:<legacy-alias> or geom_from:<node-id> binding",
                None,
            )
        )
        return ()
    binding = artifact_bindings.get(legacy_key)
    if binding is None:
        errors.append(
            _counterexample(
                "cmd.migration.artifact_binding_required",
                node_id,
                "file" if raw_job.get("file") is not None else "geom_from",
                "registered ArtifactBinding for the legacy source",
                "<legacy-source-redacted>" if source else None,
            )
        )
        return ()
    if raw_job.get("geom_from") is not None and binding.producer_node_id is None:
        binding = binding.model_copy(update={"producer_node_id": str(raw_job["geom_from"])})
    return (binding,)


def _v8_project_reference(
    raw_job: Mapping[str, Any],
    *,
    node_id: str,
    project_references: Mapping[str, ProjectReference],
    default_project_ref: ProjectReference | None,
    errors: list[CommandCounterexample],
) -> ProjectReference | None:
    raw_project = raw_job.get("project")
    if raw_project is None:
        return default_project_ref
    if not isinstance(raw_project, str):
        errors.append(
            _counterexample(
                "cmd.migration.project_reference",
                node_id,
                "project",
                "registered project reference key",
                _safe_value(raw_project),
            )
        )
        return None
    reference = project_references.get(raw_project)
    if reference is None:
        errors.append(
            _counterexample(
                "cmd.migration.project_reference",
                node_id,
                "project",
                "registered project reference key",
                "<legacy-project-redacted>",
            )
        )
    return reference


def cli_schema_digest(schema: Mapping[str, Any]) -> str:
    """Return the same stable digest used by ``schema_with_metadata``."""

    body = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    return _sha256_text(body)


def _validate_workflow_graph(
    workflow: CommandWorkflowSpec,
) -> list[CommandCounterexample]:
    errors: list[CommandCounterexample] = []
    node_ids = {node.node_id for node in workflow.nodes}
    index_by_id = {node.node_id: index for index, node in enumerate(workflow.nodes)}
    for index, node in enumerate(workflow.nodes):
        for dependency in node.dependencies:
            if dependency == node.node_id:
                errors.append(
                    _counterexample(
                        "cmd.dag.self_dependency",
                        node.node_id,
                        "dependencies",
                        "a different earlier node_id",
                        dependency,
                    )
                )
            elif dependency not in node_ids:
                errors.append(
                    _counterexample(
                        "cmd.dag.unknown_dependency",
                        node.node_id,
                        "dependencies",
                        "known node_id",
                        dependency,
                    )
                )
            elif index_by_id[dependency] >= index:
                errors.append(
                    _counterexample(
                        "cmd.dag.order",
                        node.node_id,
                        "dependencies",
                        "dependency appears before dependent node",
                        dependency,
                    )
                )
        for artifact in node.input_artifacts:
            producer = artifact.producer_node_id
            if producer is None:
                continue
            if producer == node.node_id:
                errors.append(
                    _counterexample(
                        "cmd.dag.artifact_self_reference",
                        node.node_id,
                        "input_artifacts",
                        "a different producer node_id",
                        producer,
                    )
                )
            elif producer not in node_ids:
                errors.append(
                    _counterexample(
                        "cmd.dag.unknown_artifact_producer",
                        node.node_id,
                        "input_artifacts",
                        "known producer node_id",
                        producer,
                    )
                )
            elif producer not in node.dependencies:
                errors.append(
                    _counterexample(
                        "cmd.dag.artifact_dependency_missing",
                        node.node_id,
                        "input_artifacts",
                        "producer listed in dependencies",
                        producer,
                    )
                )
            elif index_by_id[producer] >= index:
                errors.append(
                    _counterexample(
                        "cmd.dag.artifact_order",
                        node.node_id,
                        "input_artifacts",
                        "producer appears before consumer",
                        producer,
                    )
                )
            else:
                producer_node = workflow.nodes[index_by_id[producer]]
                if artifact.kind not in producer_node.expected_artifact_classes:
                    errors.append(
                        _counterexample(
                            "cmd.dag.expected_artifact_class",
                            node.node_id,
                            "input_artifacts",
                            "producer expected_artifact_classes includes bound kind",
                            artifact.kind,
                        )
                    )
    return errors


def _validate_node_contract(
    node: CommandNode, program: str | None
) -> list[CommandCounterexample]:
    errors: list[CommandCounterexample] = []
    action = node.command_path[0]
    if action not in {"run", "sub"}:
        errors.append(
            _counterexample(
                "cmd.path.unsupported_action",
                node.node_id,
                "command_path",
                "a run or sub command path",
                action,
            )
        )
    if node.execution_intent == "local" and action != "run":
        errors.append(
            _counterexample(
                "cmd.intent.action_mismatch",
                node.node_id,
                "execution_intent",
                "run for local execution",
                action,
            )
        )
    if node.execution_intent == "submit" and action != "sub":
        errors.append(
            _counterexample(
                "cmd.intent.action_mismatch",
                node.node_id,
                "execution_intent",
                "sub for submission intent",
                action,
            )
        )
    if program in _COMPUTATIONAL_PROGRAMS:
        if node.charge is None:
            errors.append(
                _counterexample(
                    "cmd.science.charge_required",
                    node.node_id,
                    "charge",
                    "explicit integer charge",
                    None,
                )
            )
        if node.multiplicity is None:
            errors.append(
                _counterexample(
                    "cmd.science.multiplicity_required",
                    node.node_id,
                    "multiplicity",
                    "explicit positive integer multiplicity",
                    None,
                )
            )
        if not node.input_artifacts:
            errors.append(
                _counterexample(
                    "cmd.science.input_artifact_required",
                    node.node_id,
                    "input_artifacts",
                    "at least one ArtifactBinding",
                    [],
                )
            )
        if program in {"gaussian", "orca"} and node.project_ref is None:
            errors.append(
                _counterexample(
                    "cmd.project.required",
                    node.node_id,
                    "project_ref",
                    "approved content-addressed project reference",
                    None,
                )
            )
    return errors


def _resolve_schema_path(
    schema: Mapping[str, Any], command_path: tuple[str, ...]
) -> _SchemaPath | CommandCounterexample:
    node: Mapping[str, Any] = schema
    nodes: list[Mapping[str, Any]] = [node]
    for command in command_path:
        subcommands = node.get("subcommands")
        if not isinstance(subcommands, Mapping) or command not in subcommands:
            return _counterexample(
                "cmd.schema.command_path",
                None,
                "command_path",
                "live Click command path",
                "/".join(command_path),
            )
        candidate = subcommands[command]
        if not isinstance(candidate, Mapping):
            return _counterexample(
                "cmd.schema.command_path",
                None,
                "command_path",
                "JSON command node",
                "/".join(command_path),
            )
        node = candidate
        nodes.append(node)
    options: list[_SchemaOption] = []
    for depth, current in enumerate(nodes):
        scope = command_path[:depth]
        raw_options = current.get("options", [])
        if not isinstance(raw_options, Sequence):
            continue
        for raw_option in raw_options:
            if not isinstance(raw_option, Mapping):
                continue
            name = raw_option.get("name")
            opts = raw_option.get("opts")
            if not isinstance(name, str) or not isinstance(opts, Sequence):
                continue
            options.append(
                _SchemaOption(
                    scope=scope,
                    name=name,
                    opts=tuple(str(option) for option in opts),
                    value_type=raw_option.get("type"),
                    choices=(
                        tuple(str(choice) for choice in raw_option["choices"])
                        if isinstance(raw_option.get("choices"), Sequence)
                        and not isinstance(raw_option.get("choices"), str)
                        else None
                    ),
                    is_flag=bool(raw_option.get("is_flag", False)),
                    multiple=bool(raw_option.get("multiple", False)),
                    required=bool(raw_option.get("required", False)),
                    nargs=int(raw_option.get("nargs", 1) or 1),
                )
            )
    return _SchemaPath(
        command_path=command_path,
        nodes=tuple(nodes),
        options=tuple(options),
    )


def _resolve_option(
    schema_path: _SchemaPath, parameter_key: str
) -> _SchemaOption | CommandCounterexample:
    scope_text, name = _split_parameter_key(parameter_key)
    matches = [option for option in schema_path.options if option.name == name]
    if scope_text is not None:
        scope = () if scope_text == "chemsmart" else tuple(scope_text.split("/"))
        matches = [option for option in matches if option.scope == scope]
    if not matches:
        return _counterexample(
            "cmd.schema.unknown_option",
            None,
            parameter_key,
            "option defined in the live Click schema",
            name,
        )
    if len(matches) > 1:
        return _counterexample(
            "cmd.schema.ambiguous_option",
            None,
            parameter_key,
            "a scope-qualified parameter key",
            ["/".join(option.scope) or "chemsmart" for option in matches],
        )
    return matches[0]


def _ground_project(
    *,
    node: CommandNode,
    program: str | None,
    schema_path: _SchemaPath,
    context: CompilationContext,
    values: dict[tuple[tuple[str, ...], str], Any],
    errors: list[CommandCounterexample],
) -> None:
    if node.project_ref is None:
        return
    project = context.projects.get(node.project_ref.project_id)
    if project is None:
        errors.append(
            _counterexample(
                "cmd.project.unresolved",
                node.node_id,
                "project_ref.project_id",
                "registered project_id",
                node.project_ref.project_id,
            )
        )
        return
    if project.project_id != node.project_ref.project_id:
        errors.append(
            _counterexample(
                "cmd.project.id_mismatch",
                node.node_id,
                "project_ref.project_id",
                node.project_ref.project_id,
                project.project_id,
            )
        )
        return
    if project.sha256 != node.project_ref.sha256:
        errors.append(
            _counterexample(
                "cmd.project.hash_mismatch",
                node.node_id,
                "project_ref.sha256",
                project.sha256,
                node.project_ref.sha256,
            )
        )
        return
    if program in _COMPUTATIONAL_PROGRAMS and project.program != program:
        errors.append(
            _counterexample(
                "cmd.project.program_mismatch",
                node.node_id,
                "project_ref",
                program,
                project.program,
            )
        )
        return
    if project.path is not None:
        project_error = _verify_host_file(
            project.path,
            context.workspace_root,
            project.sha256,
            context.max_artifact_bytes,
            verify_content=context.verify_artifact_content,
            rule_prefix="cmd.project",
            node_id=node.node_id,
            field="project_ref",
        )
        if project_error is not None:
            errors.append(project_error)
            return
    option_or_error = _resolve_option(schema_path, "project")
    if isinstance(option_or_error, CommandCounterexample):
        errors.append(_with_node(option_or_error, node.node_id, "project_ref"))
        return
    _set_value(
        values,
        option_or_error,
        project.command_value,
        node.node_id,
        "project_ref",
        errors,
    )


def _ground_charge_and_multiplicity(
    *,
    node: CommandNode,
    program: str | None,
    schema_path: _SchemaPath,
    values: dict[tuple[tuple[str, ...], str], Any],
    errors: list[CommandCounterexample],
) -> None:
    if program not in _COMPUTATIONAL_PROGRAMS:
        return
    for name, value in (("charge", node.charge), ("multiplicity", node.multiplicity)):
        if value is None:
            continue
        option_or_error = _resolve_option(schema_path, name)
        if isinstance(option_or_error, CommandCounterexample):
            errors.append(_with_node(option_or_error, node.node_id, name))
            continue
        _set_value(values, option_or_error, value, node.node_id, name, errors)


def _ground_artifacts(
    *,
    node: CommandNode,
    schema_path: _SchemaPath,
    context: CompilationContext,
    program: str | None,
    values: dict[tuple[tuple[str, ...], str], Any],
    artifact_option_addresses: set[tuple[tuple[str, ...], str]],
    pending_artifact_option_addresses: set[tuple[tuple[str, ...], str]],
    errors: list[CommandCounterexample],
) -> list[ArtifactEvidenceRef]:
    grouped: dict[tuple[tuple[str, ...], str], list[tuple[ArtifactBinding, str]]] = defaultdict(list)
    evidence: list[ArtifactEvidenceRef] = []
    for binding in node.input_artifacts:
        option_or_error = _resolve_option(schema_path, binding.target_parameter)
        if isinstance(option_or_error, CommandCounterexample):
            errors.append(
                _with_node(option_or_error, node.node_id, binding.target_parameter)
            )
            continue
        option = option_or_error
        if not _is_artifact_parameter(option):
            errors.append(
                _counterexample(
                    "cmd.artifact.target_not_path",
                    node.node_id,
                    "input_artifacts",
                    "a filename or Click path option",
                    binding.target_parameter,
                )
            )
            continue
        resolved = context.artifacts.get(binding.artifact_id)
        if resolved is None:
            rule_id = (
                "cmd.artifact.dependency_not_ready"
                if binding.producer_node_id is not None
                else "cmd.artifact.unresolved"
            )
            errors.append(
                _counterexample(
                    rule_id,
                    node.node_id,
                    "input_artifacts",
                    "registered content-addressed artifact receipt",
                    binding.artifact_id,
                )
            )
            if binding.producer_node_id is not None:
                pending_artifact_option_addresses.add((option.scope, option.name))
            continue
        if resolved.artifact_id != binding.artifact_id:
            errors.append(
                _counterexample(
                    "cmd.artifact.id_mismatch",
                    node.node_id,
                    "input_artifacts",
                    binding.artifact_id,
                    resolved.artifact_id,
                )
            )
            continue
        if resolved.sha256 != binding.sha256:
            errors.append(
                _counterexample(
                    "cmd.artifact.hash_mismatch",
                    node.node_id,
                    "input_artifacts",
                    resolved.sha256,
                    binding.sha256,
                )
            )
            continue
        if resolved.kind != binding.kind:
            errors.append(
                _counterexample(
                    "cmd.artifact.class_mismatch",
                    node.node_id,
                    "input_artifacts",
                    resolved.kind,
                    binding.kind,
                )
            )
            continue
        if (
            program in _COMPUTATIONAL_PROGRAMS
            and not _is_geometry_artifact_kind(resolved.kind)
        ):
            errors.append(
                _counterexample(
                    "cmd.artifact.geometry_required",
                    node.node_id,
                    "input_artifacts",
                    "a geometry artifact for a computational command",
                    resolved.kind,
                )
            )
            continue
        if (
            binding.producer_node_id is not None
            and binding.producer_node_id != resolved.producer_node_id
        ):
            errors.append(
                _counterexample(
                    "cmd.artifact.producer_mismatch",
                    node.node_id,
                    "input_artifacts",
                    binding.producer_node_id,
                    resolved.producer_node_id,
                )
            )
            continue
        file_error = _verify_host_file(
            resolved.path,
            context.workspace_root,
            resolved.sha256,
            context.max_artifact_bytes,
            verify_content=context.verify_artifact_content,
            rule_prefix="cmd.artifact",
            node_id=node.node_id,
            field="input_artifacts",
        )
        if file_error is not None:
            errors.append(file_error)
            continue
        try:
            rendered_path = _workspace_relative_path(
                resolved.path, context.workspace_root
            )
        except ValueError:
            errors.append(
                _counterexample(
                    "cmd.artifact.outside_workspace",
                    node.node_id,
                    "input_artifacts",
                    "artifact path under workspace_root",
                    "outside_workspace",
                )
            )
            continue
        grouped[(option.scope, option.name)].append((binding, rendered_path))
        evidence.append(
            ArtifactEvidenceRef(
                artifact_id=binding.artifact_id,
                sha256=binding.sha256,
                kind=binding.kind,
            )
        )

    for address, bound_values in grouped.items():
        option = next(
            candidate
            for candidate in schema_path.options
            if (candidate.scope, candidate.name) == address
        )
        paths = [path for _binding, path in bound_values]
        if option.multiple:
            _set_value(
                values,
                option,
                paths,
                node.node_id,
                "input_artifacts",
                errors,
            )
        elif len(paths) == 1:
            _set_value(
                values,
                option,
                paths[0],
                node.node_id,
                "input_artifacts",
                errors,
            )
        else:
            errors.append(
                _counterexample(
                    "cmd.artifact.cardinality",
                    node.node_id,
                    "input_artifacts",
                    f"one artifact for --{option.name.replace('_', '-')}",
                    [binding.artifact_id for binding, _path in bound_values],
                )
            )
        artifact_option_addresses.add(address)
    return evidence


def _set_value(
    values: dict[tuple[tuple[str, ...], str], Any],
    option: _SchemaOption,
    value: Any,
    node_id: str,
    field: str,
    errors: list[CommandCounterexample],
) -> None:
    address = (option.scope, option.name)
    if address in values and values[address] != value:
        errors.append(
            _counterexample(
                "cmd.ir.conflicting_value",
                node_id,
                field,
                _safe_value(values[address]),
                _safe_value(value),
            )
        )
        return
    values[address] = value


def _validate_required_options(
    schema_path: _SchemaPath,
    values: Mapping[tuple[tuple[str, ...], str], Any],
    node_id: str,
    errors: list[CommandCounterexample],
    *,
    pending_artifact_option_addresses: set[tuple[tuple[str, ...], str]],
) -> None:
    for option in schema_path.options:
        address = (option.scope, option.name)
        if (
            option.required
            and address not in values
            and address not in pending_artifact_option_addresses
        ):
            errors.append(
                _counterexample(
                    "cmd.schema.required_option",
                    node_id,
                    option.name,
                    "required option value",
                    None,
                )
            )
    for depth, schema_node in enumerate(schema_path.nodes):
        semantic = schema_node.get("semantic")
        if not isinstance(semantic, Mapping):
            continue
        required_options = semantic.get("required_options")
        if not isinstance(required_options, Sequence):
            continue
        # ``nodes`` includes the root at index zero.
        scope = schema_path.command_path[:depth]
        for item in required_options:
            if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
                continue
            name = item["name"]
            address = (scope, name)
            if address not in values and address not in pending_artifact_option_addresses:
                errors.append(
                    _counterexample(
                        "cmd.schema.semantic_required_option",
                        node_id,
                        name,
                        item.get("label", "semantic required option"),
                        None,
                    )
                )


def _validate_values(
    schema_path: _SchemaPath,
    values: Mapping[tuple[tuple[str, ...], str], Any],
    artifact_option_addresses: set[tuple[tuple[str, ...], str]],
    node_id: str,
    errors: list[CommandCounterexample],
) -> None:
    by_address = {(option.scope, option.name): option for option in schema_path.options}
    for address, value in values.items():
        option = by_address[address]
        error = _validate_option_value(
            option,
            value,
            is_artifact=address in artifact_option_addresses,
        )
        if error is not None:
            errors.append(_with_node(error, node_id, option.name))


def _validate_option_value(
    option: _SchemaOption,
    value: Any,
    *,
    is_artifact: bool,
) -> CommandCounterexample | None:
    if option.is_flag:
        if not isinstance(value, bool):
            return _counterexample(
                "cmd.schema.option_type",
                None,
                option.name,
                "boolean",
                _safe_value(value),
            )
        return _boolean_flag_error(option, value)
    if option.multiple:
        if not isinstance(value, (list, tuple)) or not value:
            return _counterexample(
                "cmd.schema.option_type",
                None,
                option.name,
                "non-empty list for a Click multiple option",
                _safe_value(value),
            )
        for item in value:
            error = _validate_scalar_value(option, item, is_artifact=is_artifact)
            if error is not None:
                return error
        return None
    if option.nargs > 1:
        if not isinstance(value, (list, tuple)) or len(value) != option.nargs:
            return _counterexample(
                "cmd.schema.option_arity",
                None,
                option.name,
                f"sequence of {option.nargs} values",
                _safe_value(value),
            )
        for item in value:
            error = _validate_scalar_value(option, item, is_artifact=is_artifact)
            if error is not None:
                return error
        return None
    return _validate_scalar_value(option, value, is_artifact=is_artifact)


def _validate_scalar_value(
    option: _SchemaOption, value: Any, *, is_artifact: bool
) -> CommandCounterexample | None:
    if isinstance(value, str) and _unsafe_shell_value(value):
        return _counterexample(
            "cmd.ir.shell_syntax",
            None,
            option.name,
            "a shell-free typed value",
            _safe_value(value),
        )
    value_type = option.value_type
    if isinstance(value_type, Mapping):
        type_name = value_type.get("type")
    else:
        type_name = value_type
    if type_name == "int" and (not isinstance(value, int) or isinstance(value, bool)):
        return _counterexample(
            "cmd.schema.option_type",
            None,
            option.name,
            "integer",
            _safe_value(value),
        )
    if type_name == "float" and (
        not isinstance(value, (int, float)) or isinstance(value, bool)
    ):
        return _counterexample(
            "cmd.schema.option_type",
            None,
            option.name,
            "number",
            _safe_value(value),
        )
    if type_name == "choice":
        choices = option.choices or ()
        if not isinstance(value, str) or value not in choices:
            return _counterexample(
                "cmd.schema.choice",
                None,
                option.name,
                list(choices),
                _safe_value(value),
            )
    elif type_name == "path" and not is_artifact:
        return _counterexample(
            "cmd.ir.raw_artifact_path",
            None,
            option.name,
            "ArtifactBinding for a Click path option",
            _safe_value(value),
        )
    elif type_name == "str" and not isinstance(value, (str, list, tuple, dict)):
        return _counterexample(
            "cmd.schema.option_type",
            None,
            option.name,
            "string or structured value rendered as canonical JSON",
            _safe_value(value),
        )
    return None


def _boolean_flag_error(
    option: _SchemaOption, value: bool
) -> CommandCounterexample | None:
    canonical = _boolean_flag(option, value)
    if canonical is not None:
        return None
    return _counterexample(
        "cmd.schema.boolean_flag",
        None,
        option.name,
        "a matching positive/negative long Click option",
        {"opts": list(option.opts), "value": value},
    )


def _render_argv(
    command_path: tuple[str, ...],
    schema_path: _SchemaPath,
    values: Mapping[tuple[tuple[str, ...], str], Any],
) -> list[str]:
    argv = ["chemsmart"]
    for depth in range(len(command_path) + 1):
        scope = command_path[:depth]
        scope_options = sorted(
            (
                option
                for option in schema_path.options
                if option.scope == scope
                and (option.scope, option.name) in values
            ),
            key=lambda option: (option.canonical_long_flag or "", option.name),
        )
        for option in scope_options:
            argv.extend(_render_option(option, values[(option.scope, option.name)]))
        if depth < len(command_path):
            argv.append(command_path[depth])
    return argv


def _render_option(option: _SchemaOption, value: Any) -> list[str]:
    if option.is_flag:
        flag = _boolean_flag(option, value)
        if flag is None:  # Defensive; _validate_values already proved this.
            raise ValueError(f"cannot render boolean option {option.name}")
        return [flag]
    flag = option.canonical_long_flag
    if flag is None:
        raise ValueError(f"option {option.name} has no long flag")
    if option.multiple:
        rendered: list[str] = []
        for item in value:
            rendered.extend((flag, _render_scalar(item)))
        return rendered
    if option.nargs > 1:
        return [flag, *(_render_scalar(item) for item in value)]
    return [flag, _render_scalar(value)]


def _render_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _boolean_flag(option: _SchemaOption, value: bool) -> str | None:
    stem = option.name.replace("_", "-")
    target = f"--{stem}" if value else f"--no-{stem}"
    if target in option.opts:
        return target
    # For unusual Click flags without the conventional pair, only a single
    # long form is safe to render; false would silently change semantics.
    long_flags = sorted(flag for flag in option.opts if flag.startswith("--"))
    if value and len(long_flags) == 1:
        return long_flags[0]
    return None


def _is_artifact_parameter(option: _SchemaOption) -> bool:
    type_name = (
        option.value_type.get("type")
        if isinstance(option.value_type, Mapping)
        else option.value_type
    )
    return (
        option.name in {"filename", "filenames"}
        or option.name.endswith("filename")
        or type_name == "path"
    )


def _is_geometry_artifact_kind(kind: str) -> bool:
    """Accept legacy geometry aliases only in the compatibility compiler.

    The model-facing scientific task contract is stricter and accepts only
    ``geometry.xyz``. Retaining these old aliases here preserves receipt and
    migration fixtures while still rejecting native engine inputs.
    """

    return kind.startswith("geometry.") or kind in {
        "xyz_geometry",
        "sdf_geometry",
        "pdb_geometry",
    }


def _project_owns_parameter(
    program: str | None,
    parameter: str,
    *,
    project_bound: bool = False,
) -> bool:
    if program in {"gaussian", "orca"}:
        return parameter in _PROJECT_OWNED_PARAMETERS
    return bool(
        program == "xtb"
        and project_bound
        and parameter
        in {
            "gfn_version",
            "optimization_level",
            "solvent_model",
            "solvent_id",
        }
    )


def _program_from_path(command_path: tuple[str, ...]) -> str | None:
    for part in command_path:
        if part in _COMPUTATIONAL_PROGRAMS:
            return part
    return None


def _intent_projection(
    node: CommandNode,
    values: Mapping[tuple[tuple[str, ...], str], Any],
    artifact_addresses: set[tuple[tuple[str, ...], str]],
) -> dict[str, Any]:
    rendered_parameters: dict[str, Any] = {}
    for (scope, name), value in sorted(values.items()):
        key = f"{'/'.join(scope) if scope else 'chemsmart'}:{name}"
        rendered_parameters[key] = (
            "<artifact-bound>" if (scope, name) in artifact_addresses else value
        )
    return {
        "command_path": list(node.command_path),
        "charge": node.charge,
        "multiplicity": node.multiplicity,
        "execution_intent": node.execution_intent,
        "parameters": rendered_parameters,
        "dependencies": list(node.dependencies),
        "constraint_ids": list(node.constraint_ids),
    }


def _verify_host_file(
    path: Path,
    workspace_root: Path,
    expected_hash: str,
    max_bytes: int,
    *,
    verify_content: bool,
    rule_prefix: str,
    node_id: str,
    field: str,
) -> CommandCounterexample | None:
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return _counterexample(
            f"{rule_prefix}.missing",
            node_id,
            field,
            "existing host-owned file",
            "missing",
        )
    try:
        resolved.relative_to(workspace_root.resolve(strict=True))
    except ValueError:
        return _counterexample(
            f"{rule_prefix}.outside_workspace",
            node_id,
            field,
            "path under workspace_root",
            "outside_workspace",
        )
    if not resolved.is_file():
        return _counterexample(
            f"{rule_prefix}.not_file",
            node_id,
            field,
            "regular file",
            "not_file",
        )
    if not verify_content:
        return None
    try:
        size = resolved.stat().st_size
    except OSError:
        return _counterexample(
            f"{rule_prefix}.missing",
            node_id,
            field,
            "existing host-owned file",
            "missing",
        )
    if size > max_bytes:
        return _counterexample(
            f"{rule_prefix}.too_large_to_verify",
            node_id,
            field,
            f"file no larger than {max_bytes} bytes",
            size,
        )
    actual_hash = _sha256_file(resolved)
    if actual_hash != expected_hash:
        return _counterexample(
            f"{rule_prefix}.content_hash_mismatch",
            node_id,
            field,
            expected_hash,
            actual_hash,
        )
    return None


def _workspace_relative_path(path: Path, workspace_root: Path) -> str:
    return path.resolve(strict=True).relative_to(
        workspace_root.resolve(strict=True)
    ).as_posix()


def _compilation_status(
    errors: Sequence[CommandCounterexample],
) -> Literal["previewable", "planned", "blocked"]:
    if not errors:
        return "previewable"
    planned_rules = {"cmd.artifact.dependency_not_ready"}
    if all(error.rule_id in planned_rules for error in errors):
        return "planned"
    return "blocked"


def _live_schema_digest(schema: Mapping[str, Any]) -> str:
    """Avoid shadowing the legacy migration argument of the same name."""

    return cli_schema_digest(schema)


def _render_digest(
    invocations: Sequence[CanonicalCommandInvocation],
    errors: Sequence[CommandCounterexample],
) -> str:
    payload = {
        "invocations": [item.model_dump(mode="json") for item in invocations],
        "counterexamples": [item.model_dump(mode="json") for item in errors],
    }
    return _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _counterexample(
    rule_id: str,
    node_id: str | None,
    failed_field: str,
    expected: Any,
    observed: Any,
) -> CommandCounterexample:
    safe_expected = _safe_value(expected)
    safe_observed = _safe_value(observed)
    evidence = json.dumps(
        {
            "rule_id": rule_id,
            "node_id": node_id,
            "failed_field": failed_field,
            "expected": safe_expected,
            "observed": safe_observed,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return CommandCounterexample(
        rule_id=rule_id,
        node_id=node_id,
        failed_field=failed_field,
        expected=safe_expected,
        observed=safe_observed,
        evidence_id=f"ce-{_sha256_text(evidence)[:20]}",
    )


def _with_node(
    counterexample: CommandCounterexample, node_id: str, failed_field: str
) -> CommandCounterexample:
    return _counterexample(
        counterexample.rule_id,
        node_id,
        failed_field,
        counterexample.expected,
        counterexample.observed,
    )


def _safe_value(value: Any) -> Any:
    if isinstance(value, Path):
        return "<redacted-path>"
    if isinstance(value, str):
        if "/" in value or "\\" in value or value.startswith("~"):
            return "<redacted-path>"
        return value[:512]
    if isinstance(value, Mapping):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item) for item in value]
    return value


def _validate_parameter_key(value: str) -> None:
    scope, name = _split_parameter_key(value)
    if scope is not None:
        if scope != "chemsmart" and any(
            not _COMMAND_PART_PATTERN.fullmatch(part)
            for part in scope.split("/")
        ):
            raise ValueError("parameter scope is not a Click command path")
    if not _PARAMETER_NAME_PATTERN.fullmatch(name):
        raise ValueError("parameter name must use canonical snake_case")


def _split_parameter_key(value: str) -> tuple[str | None, str]:
    if value.count(":") > 1:
        raise ValueError("parameter key can contain at most one scope separator")
    if ":" not in value:
        return None, value
    scope, name = value.split(":", 1)
    if not scope or not name:
        raise ValueError("scoped parameter key must be '<scope>:<name>'")
    return scope, name


def _parameter_name_from_key(value: str) -> str:
    _scope, name = _split_parameter_key(value)
    if name in _NATIVE_INPUT_PARAMETER_NAMES:
        raise ValueError("native input and raw command fields are forbidden")
    return name


def _unsafe_shell_value(value: str) -> bool:
    stripped = value.strip()
    if "\x00" in value or "\n" in value or "\r" in value:
        return True
    if stripped in {"|", "||", "&", "&&", ";", ">", ">>", "<", "`", "$"}:
        return True
    if any(
        marker in value
        for marker in (";", "\n", "\r", "$", "&", "`", "|", ">", "<")
    ):
        return True
    return False


def _safe_legacy_artifact_alias(value: str) -> bool:
    """Permit only relative lookup aliases while reading an old compact SPEC."""

    candidate = value.strip()
    if not candidate or candidate.startswith("<") or candidate.endswith(">"):
        return False
    path = Path(candidate)
    return not path.is_absolute() and ".." not in path.parts


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "ArtifactBinding",
    "ArtifactEvidenceRef",
    "CanonicalCommandInvocation",
    "CommandCounterexample",
    "CommandNode",
    "CommandWorkflowCompilation",
    "CommandWorkflowCompiler",
    "CommandWorkflowSpec",
    "COMMAND_WORKFLOW_SCHEMA_VERSION",
    "CompilationContext",
    "ProjectReference",
    "ResolvedArtifact",
    "ResolvedProject",
    "V8CompactSpecMigration",
    "cli_schema_digest",
    "compile_command_workflow",
    "migrate_v8_compact_spec",
]
