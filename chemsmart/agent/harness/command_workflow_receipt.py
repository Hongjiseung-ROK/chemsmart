"""Path-free evidence for a typed command-workflow safe preview.

This module is the narrow integration point between the command compiler and
the existing semantic/intent gates.  It deliberately has no execution API:
its most affirmative status is ``previewed`` and it never represents a real
engine run, scheduler submission, reproduction, or scientific result.

Call :func:`build_command_workflow_receipt` after the caller has compiled a
``CommandWorkflowSpec`` and run the existing isolated safe-preview and intent
comparison gates for every previewable invocation.  The resulting receipt is
safe to attach to a Runtime V2 event because it contains identifiers, hashes,
and structured observations rather than command strings, filesystem paths,
provider payloads, native-input text, stdout/stderr, credentials, or hidden
reasoning.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from chemsmart.agent.command_models import ParsedModelCommand
from chemsmart.agent.command_workflow import (
    CanonicalCommandInvocation,
    CommandCounterexample,
    CommandWorkflowCompilation,
    CommandWorkflowSpec,
)
from chemsmart.agent.harness.command_semantics import CommandSemanticResult
from chemsmart.agent.harness.intent import IntentResult
from chemsmart.agent.model_command_parser import parse_model_command


COMMAND_WORKFLOW_RECEIPT_SCHEMA_VERSION = "chemsmart.command-workflow-receipt.v1"
WorkflowReceiptStatus = Literal["planned", "previewed", "blocked"]
PreviewVerdict = Literal["ok", "warn", "reject", "not_run"]
PreviewMode = Literal[
    "run_fake_no_scratch",
    "sub_test_fake",
    "not_run",
    "unsafe_or_unverified",
]
IntentReceiptVerdict = Literal["ok", "reject", "not_checked"]

_SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SAFE_RULE_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,191}$")
_SAFE_ELEMENT = re.compile(r"^[A-Z][a-z]?$|^X$")
_COMPUTATIONAL_PROGRAMS = frozenset({"gaussian", "orca", "xtb"})


@dataclass(frozen=True)
class ReceiptFinding:
    """A path-free gate failure or compiler finding."""

    rule_id: str
    node_id: str | None
    evidence_id: str

    def to_dict(self) -> dict[str, str | None]:
        return {
            "rule_id": self.rule_id,
            "node_id": self.node_id,
            "evidence_id": self.evidence_id,
        }


@dataclass(frozen=True)
class PreviewArtifactObservation:
    """Sanitized generated-input observation from an isolated safe preview."""

    ordinal: int
    program: str | None
    route_sha256: str | None
    content_observation_sha256: str | None
    charge: int | None
    multiplicity: int | None
    element_counts: dict[str, int]
    ordered_geometry_sha256: str | None
    observation_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "program": self.program,
            "route_sha256": self.route_sha256,
            "content_observation_sha256": self.content_observation_sha256,
            "charge": self.charge,
            "multiplicity": self.multiplicity,
            "element_counts": dict(self.element_counts),
            "ordered_geometry_sha256": self.ordered_geometry_sha256,
            "observation_sha256": self.observation_sha256,
        }


@dataclass(frozen=True)
class SafePreviewEvidence:
    """Outcome of the existing fake/test-only semantic preview gate."""

    verdict: PreviewVerdict
    mode: PreviewMode
    command_matches_invocation: bool
    rule_ids: tuple[str, ...]
    generated_artifacts: tuple[PreviewArtifactObservation, ...]
    generated_artifact_observations_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "mode": self.mode,
            "command_matches_invocation": self.command_matches_invocation,
            "rule_ids": list(self.rule_ids),
            "generated_artifacts": [
                artifact.to_dict() for artifact in self.generated_artifacts
            ],
            "generated_artifact_observations_sha256": (
                self.generated_artifact_observations_sha256
            ),
        }


@dataclass(frozen=True)
class ParserObservationReceipt:
    """Path-free independent observation of a canonical invocation."""

    verdict: Literal["ok", "reject"]
    action: str | None
    program: str | None
    job: str | None
    matches_invocation: bool
    parse_error_sha256: str | None
    observation_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "action": self.action,
            "program": self.program,
            "job": self.job,
            "matches_invocation": self.matches_invocation,
            "parse_error_sha256": self.parse_error_sha256,
            "observation_sha256": self.observation_sha256,
        }


@dataclass(frozen=True)
class IntentComparisonReceipt:
    """Sanitized result of an independent intent round-trip comparison."""

    verdict: IntentReceiptVerdict
    failed_rule_ids: tuple[str, ...]
    assertion_summary_sha256: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "failed_rule_ids": list(self.failed_rule_ids),
            "assertion_summary_sha256": self.assertion_summary_sha256,
        }


@dataclass(frozen=True)
class InvocationPreviewReceipt:
    """All path-free evidence bound to one compiler-owned invocation."""

    node_id: str
    click_path: tuple[str, ...]
    command_sha256: str
    cli_schema_digest: str
    project_id: str | None
    project_sha256: str | None
    input_artifacts: tuple[dict[str, str], ...]
    environment_digest: str
    intent_projection_sha256: str
    expected_artifact_classes: tuple[str, ...]
    parser: ParserObservationReceipt
    intent: IntentComparisonReceipt
    safe_preview: SafePreviewEvidence
    status: WorkflowReceiptStatus
    findings: tuple[ReceiptFinding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "click_path": list(self.click_path),
            "command_sha256": self.command_sha256,
            "cli_schema_digest": self.cli_schema_digest,
            "project_id": self.project_id,
            "project_sha256": self.project_sha256,
            "input_artifacts": [dict(item) for item in self.input_artifacts],
            "environment_digest": self.environment_digest,
            "intent_projection_sha256": self.intent_projection_sha256,
            "expected_artifact_classes": list(self.expected_artifact_classes),
            "parser": self.parser.to_dict(),
            "intent": self.intent.to_dict(),
            "safe_preview": self.safe_preview.to_dict(),
            "status": self.status,
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class CommandWorkflowReceipt:
    """Deterministic receipt for a command workflow before real execution.

    ``status`` is intentionally restricted to ``planned``, ``previewed``, and
    ``blocked``.  A separate future execution receipt may link to this record;
    it must not mutate this preview evidence into an execution claim.
    """

    schema_version: str
    workflow_id: str
    task_spec_id: str
    task_spec_sha256: str | None
    workflow_spec_sha256: str
    compilation_status: Literal["previewable", "planned", "blocked"]
    render_digest: str
    cli_schema_digest: str
    status: WorkflowReceiptStatus
    compiler_findings: tuple[ReceiptFinding, ...]
    invocations: tuple[InvocationPreviewReceipt, ...]
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "task_spec_id": self.task_spec_id,
            "task_spec_sha256": self.task_spec_sha256,
            "workflow_spec_sha256": self.workflow_spec_sha256,
            "compilation_status": self.compilation_status,
            "render_digest": self.render_digest,
            "cli_schema_digest": self.cli_schema_digest,
            "status": self.status,
            "compiler_findings": [
                finding.to_dict() for finding in self.compiler_findings
            ],
            "invocations": [item.to_dict() for item in self.invocations],
            "receipt_sha256": self.receipt_sha256,
        }


def build_command_workflow_receipt(
    workflow: CommandWorkflowSpec,
    compilation: CommandWorkflowCompilation,
    *,
    safe_preview_results: Mapping[str, CommandSemanticResult] | None = None,
    intent_results: Mapping[str, IntentResult] | None = None,
    parser_observations: Mapping[str, ParsedModelCommand] | None = None,
    parser_cwd: str | None = None,
    task_spec_sha256: str | None = None,
    additional_findings: Sequence[CommandCounterexample] = (),
) -> CommandWorkflowReceipt:
    """Bind compiler, parser, intent, and fake/test-preview evidence.

    The Runtime V2 command tool should invoke this function *after*
    ``compile_command_workflow`` and the isolated ``evaluate_command_semantics``
    / ``evaluate_intent`` calls, then append ``receipt.to_dict()`` to its
    command-preflight event.  This function itself starts no process, creates
    no native input, and has no approval or execution authority.

    A ``previewed`` outcome requires a previewable compiler result, a matching
    independent parser observation, an accepted intent comparison, and an
    ``ok`` safe result whose argv proves the required fake/test safeguards.
    Missing evidence is fail-closed as ``blocked``.  A workflow with an
    unavailable upstream artifact remains ``planned`` instead of pretending
    that its dependent command was previewed.
    """

    if compilation.workflow_id != workflow.workflow_id:
        raise ValueError("compilation does not belong to the supplied workflow")
    if task_spec_sha256 is not None and re.fullmatch(r"[0-9a-f]{64}", task_spec_sha256) is None:
        raise ValueError("task_spec_sha256 must be a SHA-256 digest")

    previews = dict(safe_preview_results or {})
    comparisons = dict(intent_results or {})
    supplied_parsers = dict(parser_observations or {})
    nodes_by_id = {node.node_id: node for node in workflow.nodes}
    invocation_ids = {item.node_id for item in compilation.invocations}
    compiler_findings = _compiler_findings(compilation)
    compiler_findings.extend(
        ReceiptFinding(
            rule_id=_safe_rule_id(counterexample.rule_id),
            node_id=_safe_optional_label(counterexample.node_id),
            evidence_id=_safe_evidence_id(counterexample.evidence_id),
        )
        for counterexample in additional_findings
    )
    compiler_findings.extend(
        _unbound_evidence_findings(
            known_node_ids=set(nodes_by_id),
            previews=previews,
            comparisons=comparisons,
            parsers=supplied_parsers,
        )
    )
    if compilation.status == "previewable":
        for node_id in sorted(set(nodes_by_id).difference(invocation_ids)):
            compiler_findings.append(
                _finding("receipt.compiler.node_not_compiled", node_id)
            )

    invocation_receipts: list[InvocationPreviewReceipt] = []
    for invocation in compilation.invocations:
        node = nodes_by_id.get(invocation.node_id)
        if node is None:
            # A compiler result with an unknown node cannot safely become an
            # agent-visible preview.  Keep a minimal receipt rather than
            # leaking any invocation material while recording the invariant.
            compiler_findings.append(
                _finding("receipt.compiler.unknown_invocation", invocation.node_id)
            )
            continue
        parsed = supplied_parsers.get(invocation.node_id)
        if parsed is None:
            parsed = parse_model_command(
                invocation.display_command,
                cwd=parser_cwd,
            )
        parser_receipt = _parser_receipt(invocation, parsed)
        intent_receipt = _intent_receipt(comparisons.get(invocation.node_id))
        preview_receipt = _safe_preview_receipt(
            invocation,
            previews.get(invocation.node_id),
        )
        findings = _invocation_findings(
            invocation=invocation,
            parser=parser_receipt,
            intent=intent_receipt,
            preview=preview_receipt,
            compilation_status=compilation.status,
        )
        node_status = _node_status(compilation.status, findings)
        invocation_receipts.append(
            InvocationPreviewReceipt(
                node_id=invocation.node_id,
                click_path=tuple(invocation.command_path),
                command_sha256=invocation.command_sha256,
                cli_schema_digest=invocation.cli_schema_digest,
                project_id=invocation.project_id,
                project_sha256=invocation.project_sha256,
                input_artifacts=tuple(
                    {
                        "artifact_id": artifact.artifact_id,
                        "sha256": artifact.sha256,
                        "kind": artifact.kind,
                    }
                    for artifact in invocation.input_artifacts
                ),
                environment_digest=invocation.environment_digest,
                intent_projection_sha256=_sha256_json(
                    invocation.intent_projection
                ),
                expected_artifact_classes=tuple(
                    _safe_label(value) for value in node.expected_artifact_classes
                ),
                parser=parser_receipt,
                intent=intent_receipt,
                safe_preview=preview_receipt,
                status=node_status,
                findings=tuple(findings),
            )
        )

    status = _workflow_status(
        compilation.status,
        compiler_findings,
        invocation_receipts,
    )
    receipt_body = {
        "schema_version": COMMAND_WORKFLOW_RECEIPT_SCHEMA_VERSION,
        "workflow_id": workflow.workflow_id,
        "task_spec_id": workflow.task_spec_id,
        "task_spec_sha256": task_spec_sha256,
        "workflow_spec_sha256": _sha256_json(workflow.model_dump(mode="json")),
        "compilation_status": compilation.status,
        "render_digest": compilation.render_digest,
        "cli_schema_digest": workflow.cli_schema_digest,
        "status": status,
        "compiler_findings": [item.to_dict() for item in compiler_findings],
        "invocations": [item.to_dict() for item in invocation_receipts],
    }
    receipt = CommandWorkflowReceipt(
        schema_version=COMMAND_WORKFLOW_RECEIPT_SCHEMA_VERSION,
        workflow_id=workflow.workflow_id,
        task_spec_id=workflow.task_spec_id,
        task_spec_sha256=task_spec_sha256,
        workflow_spec_sha256=_sha256_json(workflow.model_dump(mode="json")),
        compilation_status=compilation.status,
        render_digest=compilation.render_digest,
        cli_schema_digest=workflow.cli_schema_digest,
        status=status,
        compiler_findings=tuple(compiler_findings),
        invocations=tuple(invocation_receipts),
        receipt_sha256=_sha256_json(receipt_body),
    )
    _assert_path_free(receipt.to_dict())
    return receipt


def _compiler_findings(
    compilation: CommandWorkflowCompilation,
) -> list[ReceiptFinding]:
    return [
        ReceiptFinding(
            rule_id=_safe_rule_id(counterexample.rule_id),
            node_id=_safe_optional_label(counterexample.node_id),
            evidence_id=_safe_evidence_id(counterexample.evidence_id),
        )
        for counterexample in compilation.counterexamples
    ]


def _unbound_evidence_findings(
    *,
    known_node_ids: set[str],
    previews: Mapping[str, CommandSemanticResult],
    comparisons: Mapping[str, IntentResult],
    parsers: Mapping[str, ParsedModelCommand],
) -> list[ReceiptFinding]:
    findings: list[ReceiptFinding] = []
    for label, mapping in (
        ("preview", previews),
        ("intent", comparisons),
        ("parser", parsers),
    ):
        for node_id in sorted(set(mapping).difference(known_node_ids)):
            findings.append(
                _finding(
                    f"receipt.{label}.unbound_node_evidence",
                    _safe_optional_label(node_id),
                )
            )
    return findings


def _parser_receipt(
    invocation: CanonicalCommandInvocation,
    parsed: ParsedModelCommand,
) -> ParserObservationReceipt:
    expected_action = invocation.command_path[0] if invocation.command_path else None
    expected_program = _program_from_path(invocation.command_path)
    expected_job = _expected_job(invocation.command_path, expected_program)
    action = _safe_optional_label(parsed.action)
    program = _safe_optional_label(parsed.program)
    job = _safe_optional_label(parsed.job)
    matches = (
        parsed.parse_error is None
        and action == expected_action
        and program == expected_program
        and (expected_job is None or job == expected_job)
    )
    error_hash = (
        _sha256_text(parsed.parse_error) if parsed.parse_error is not None else None
    )
    observation = {
        "action": action,
        "program": program,
        "job": job,
        "matches_invocation": matches,
        "parse_error_sha256": error_hash,
    }
    return ParserObservationReceipt(
        verdict="ok" if matches else "reject",
        action=action,
        program=program,
        job=job,
        matches_invocation=matches,
        parse_error_sha256=error_hash,
        observation_sha256=_sha256_json(observation),
    )


def _intent_receipt(result: IntentResult | None) -> IntentComparisonReceipt:
    if result is None:
        return IntentComparisonReceipt(
            verdict="not_checked",
            failed_rule_ids=(),
            assertion_summary_sha256=None,
        )
    summary = [
        {
            "id": _safe_rule_id(assertion.id),
            "status": assertion.status,
        }
        for assertion in result.assertions
    ]
    failed = tuple(
        _safe_rule_id(rule_id) for rule_id in result.failed_rule_ids
    )
    return IntentComparisonReceipt(
        verdict=result.verdict,
        failed_rule_ids=failed,
        assertion_summary_sha256=_sha256_json(summary),
    )


def _safe_preview_receipt(
    invocation: CanonicalCommandInvocation,
    semantic: CommandSemanticResult | None,
) -> SafePreviewEvidence:
    if semantic is None:
        empty_hash = _sha256_json([])
        return SafePreviewEvidence(
            verdict="not_run",
            mode="not_run",
            command_matches_invocation=False,
            rule_ids=(),
            generated_artifacts=(),
            generated_artifact_observations_sha256=empty_hash,
        )

    program = _program_from_path(invocation.command_path)
    artifacts = tuple(
        _preview_artifact_observation(item, ordinal=index, program=program)
        for index, item in enumerate(semantic.generated_inputs)
        if isinstance(item, Mapping)
    )
    artifact_hash = _sha256_json(
        [artifact.to_dict() for artifact in artifacts]
    )
    return SafePreviewEvidence(
        verdict=semantic.verdict,
        mode=_preview_mode(invocation, semantic),
        command_matches_invocation=(
            _command_sha256(semantic.command) == invocation.command_sha256
        ),
        rule_ids=tuple(_safe_rule_id(rule_id) for rule_id in semantic.failed_rule_ids),
        generated_artifacts=artifacts,
        generated_artifact_observations_sha256=artifact_hash,
    )


def _preview_artifact_observation(
    generated: Mapping[str, Any],
    *,
    ordinal: int,
    program: str | None,
) -> PreviewArtifactObservation:
    route = generated.get("route")
    content = generated.get("content_tail")
    payload = {
        "ordinal": ordinal,
        "program": _safe_optional_label(program),
        "route_sha256": _sha256_text(route) if isinstance(route, str) else None,
        "content_observation_sha256": (
            _sha256_text(content) if isinstance(content, str) else None
        ),
        "charge": _safe_int(generated.get("charge")),
        "multiplicity": _safe_int(generated.get("multiplicity")),
        "element_counts": _element_counts(generated.get("element_counts")),
        "ordered_geometry_sha256": _safe_sha256(
            generated.get("ordered_geometry_sha256")
        ),
    }
    return PreviewArtifactObservation(
        **payload,
        observation_sha256=_sha256_json(payload),
    )


def _invocation_findings(
    *,
    invocation: CanonicalCommandInvocation,
    parser: ParserObservationReceipt,
    intent: IntentComparisonReceipt,
    preview: SafePreviewEvidence,
    compilation_status: str,
) -> list[ReceiptFinding]:
    if compilation_status != "previewable":
        return []
    findings: list[ReceiptFinding] = []
    if parser.verdict != "ok":
        findings.append(_finding("receipt.parser.rejected", invocation.node_id))
    if intent.verdict == "not_checked":
        findings.append(_finding("receipt.intent.not_checked", invocation.node_id))
    elif intent.verdict != "ok":
        findings.append(_finding("receipt.intent.rejected", invocation.node_id))
    if preview.verdict == "not_run":
        findings.append(_finding("receipt.preview.not_run", invocation.node_id))
    elif preview.verdict != "ok":
        findings.append(_finding("receipt.preview.rejected", invocation.node_id))
    if not preview.command_matches_invocation:
        findings.append(
            _finding("receipt.preview.command_mismatch", invocation.node_id)
        )
    expected_mode = _expected_preview_mode(invocation)
    if preview.mode != expected_mode:
        findings.append(
            _finding("receipt.preview.safeguard_missing", invocation.node_id)
        )
    if (
        _program_from_path(invocation.command_path) in _COMPUTATIONAL_PROGRAMS
        and not preview.generated_artifacts
    ):
        findings.append(
            _finding("receipt.preview.generated_artifact_missing", invocation.node_id)
        )
    return findings


def _node_status(
    compilation_status: str,
    findings: list[ReceiptFinding],
) -> WorkflowReceiptStatus:
    if compilation_status == "planned":
        return "planned"
    if compilation_status == "previewable" and not findings:
        return "previewed"
    return "blocked"


def _workflow_status(
    compilation_status: str,
    compiler_findings: list[ReceiptFinding],
    invocations: list[InvocationPreviewReceipt],
) -> WorkflowReceiptStatus:
    if compilation_status == "planned":
        # The compiler uses ``planned`` solely for a verified missing upstream
        # artifact.  Any separately detected binding problem (for example
        # evidence supplied for an unknown node) must still fail closed.
        return (
            "planned"
            if all(
                finding.rule_id == "cmd.artifact.dependency_not_ready"
                for finding in compiler_findings
            )
            else "blocked"
        )
    if compilation_status != "previewable" or compiler_findings:
        return "blocked"
    if not invocations or any(item.status != "previewed" for item in invocations):
        return "blocked"
    return "previewed"


def _preview_mode(
    invocation: CanonicalCommandInvocation,
    semantic: CommandSemanticResult,
) -> PreviewMode:
    checked = set(semantic.checked_argv)
    expected = _expected_preview_mode(invocation)
    if expected == "run_fake_no_scratch":
        return (
            "run_fake_no_scratch"
            if {"--fake", "--no-scratch"}.issubset(checked)
            else "unsafe_or_unverified"
        )
    if expected == "sub_test_fake":
        return (
            "sub_test_fake"
            if {"--test", "--fake"}.issubset(checked)
            else "unsafe_or_unverified"
        )
    return "unsafe_or_unverified"


def _expected_preview_mode(
    invocation: CanonicalCommandInvocation,
) -> PreviewMode:
    action = invocation.command_path[0] if invocation.command_path else ""
    if action == "run":
        return "run_fake_no_scratch"
    if action == "sub":
        return "sub_test_fake"
    return "unsafe_or_unverified"


def _program_from_path(command_path: tuple[str, ...]) -> str | None:
    for part in command_path:
        if part in _COMPUTATIONAL_PROGRAMS:
            return part
    return None


def _expected_job(
    command_path: tuple[str, ...], program: str | None
) -> str | None:
    if program is None:
        return None
    try:
        index = command_path.index(program)
    except ValueError:  # defensive: program came from this tuple
        return None
    # The independent parser observes the immediate program job.  Nested Click
    # paths retain their full identity in ``click_path`` and are not weakened
    # by requiring a parser implementation detail it cannot express.
    return command_path[index + 1] if index + 1 < len(command_path) else None


def _element_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    counts: dict[str, int] = {}
    for symbol, count in value.items():
        if (
            isinstance(symbol, str)
            and _SAFE_ELEMENT.fullmatch(symbol)
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count >= 0
        ):
            counts[symbol] = count
    return dict(sorted(counts.items()))


def _safe_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _safe_sha256(value: Any) -> str | None:
    if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
        return value
    return None


def _finding(rule_id: str, node_id: str | None) -> ReceiptFinding:
    safe_rule = _safe_rule_id(rule_id)
    safe_node = _safe_optional_label(node_id)
    evidence = _sha256_json({"rule_id": safe_rule, "node_id": safe_node})
    return ReceiptFinding(
        rule_id=safe_rule,
        node_id=safe_node,
        evidence_id=f"rf-{evidence[:20]}",
    )


def _safe_rule_id(value: Any) -> str:
    text = str(value)
    if _SAFE_RULE_ID.fullmatch(text):
        return text
    return f"redacted-{_sha256_text(text)[:20]}"


def _safe_label(value: Any) -> str:
    text = str(value)
    if _SAFE_LABEL.fullmatch(text):
        return text
    return f"redacted-{_sha256_text(text)[:20]}"


def _safe_optional_label(value: Any) -> str | None:
    return None if value is None else _safe_label(value)


def _safe_evidence_id(value: Any) -> str:
    return _safe_label(value)


def _command_sha256(command: str) -> str:
    try:
        normalized = shlex.join(shlex.split(command))
    except ValueError:
        normalized = command.strip()
    return _sha256_text(normalized)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_text(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    )


def _assert_path_free(value: Any) -> None:
    """Defend the receipt boundary against accidental raw runtime evidence."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in {"command", "argv", "cwd", "stdout", "stderr", "route"}:
                raise ValueError(f"receipt leaked forbidden field: {key}")
            _assert_path_free(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _assert_path_free(item)
        return
    if isinstance(value, str) and ("/" in value or "\\" in value or "\n" in value):
        raise ValueError("receipt must not contain a filesystem path or raw text")


__all__ = [
    "COMMAND_WORKFLOW_RECEIPT_SCHEMA_VERSION",
    "CommandWorkflowReceipt",
    "IntentComparisonReceipt",
    "InvocationPreviewReceipt",
    "ParserObservationReceipt",
    "PreviewArtifactObservation",
    "ReceiptFinding",
    "SafePreviewEvidence",
    "build_command_workflow_receipt",
]
