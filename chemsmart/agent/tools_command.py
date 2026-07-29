"""Command-synthesis tools for the unified agent loop."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from chemsmart.agent.cli_schema import build_chemsmart_cli_schema
from chemsmart.agent.harness.command_semantics import (
    CommandSemanticResult,
    evaluate_command_semantics,
    inspect_command_semantics,
)
from chemsmart.agent.harness.intent import (
    INTENT_CORE_FIELDS,
    IntentResult,
    IntentSpec,
    evaluate_intent,
)
from chemsmart.agent.harness.preflight_receipt import (
    build_command_preflight_receipt,
)
from chemsmart.agent.harness.workflow_state import (
    clear_resolved_slots,
    current_workflow_scope,
    current_workflow_state,
    record_clarification_slots,
    record_command,
    reset_workflow_state,
    select_workspace_project,
)
from chemsmart.agent.model_command_parser import parse_model_command
from chemsmart.agent.public_visibility import sanitize_public_payload
from chemsmart.agent.runtime.calculations import (
    CalculationContext,
    CalculationEvent,
    execute_observed_process,
)
from chemsmart.agent.schema_prune import (
    prune_schema_for_request,
    schema_variant_id,
)
from chemsmart.agent.services.command_terminal import (
    execution_terminal_state,
    submit_script_fingerprints,
)
from chemsmart.agent.synthesis import (
    SynthesisSession,
    quiet_chemsmart_argv,
    resolve_default_project,
)
from chemsmart.agent.tool_protocol import RuntimeToolMetadata
from chemsmart.settings.workspace_project import (
    PROJECT_PROGRAMS,
    iter_workspace_project_yaml,
    resolve_workspace_project,
)

JsonDict = dict[str, Any]
WorkspaceFingerprint = tuple[tuple[str, int, int], ...]

_SCHEMA: JsonDict | None = None
_SESSION: "_SessionSlot | None" = None
# Gate evidence is keyed by (cwd, command, workspace fingerprint) so an edit to
# any workspace project YAML between gating and execution invalidates the
# cached verdict and forces a fresh deterministic re-validation.
_GATE_CACHE: dict[
    tuple[str, str, WorkspaceFingerprint], CommandSemanticResult
] = {}
_INTENT_CACHE: dict[tuple[str, str, str], IntentResult] = {}
_GATE_CACHE_MAX = 256


@dataclass(frozen=True)
class _SessionSlot:
    cwd: str
    provider_name: str
    workflow_scope: str
    session: SynthesisSession


def reset_command_tools_state() -> None:
    """Reset module caches for tests."""

    global _SCHEMA, _SESSION
    _SCHEMA = None
    _SESSION = None
    _GATE_CACHE.clear()
    _INTENT_CACHE.clear()
    reset_workflow_state()


class CommandSynthesisSession:
    """Host-bound command tools that never discover a provider from user config.

    Embedders such as ChemSmart Studio own provider credentials and model
    selection. Requiring the provider here keeps command synthesis on that
    authority path instead of falling back to ``providers.get_provider()``.
    """

    def __init__(
        self,
        provider: Any,
        *,
        default_project: str | None = None,
        semantic_timeout_s: float = 30.0,
        working_directory: str | Path | None = None,
    ) -> None:
        if provider is None:
            raise ValueError("provider is required for a bound command session")
        self._lock = RLock()
        self._working_directory = (
            Path(working_directory).resolve()
            if working_directory is not None
            else None
        )
        if (
            self._working_directory is not None
            and not self._working_directory.is_dir()
        ):
            raise ValueError("working_directory must be an existing directory")
        self._resolve_default_project = default_project is None
        self._session = SynthesisSession(
            provider=provider,
            schema=_command_schema(),
            semantic_timeout_s=semantic_timeout_s,
            default_project=default_project,
            enable_intent_router=False,
        )

    def synthesize_command(self, request: str) -> JsonDict:
        """Synthesize through the provider injected when this session was built."""

        with self._lock, _command_session_directory(self._working_directory):
            self._refresh_default_project()
            return _host_visible_command_result(
                _synthesize_command_with_session(self._session, request)
            )

    def repair_command(
        self,
        command: str,
        failure: str = "",
        request: str = "",
    ) -> JsonDict:
        """Repair through the provider injected when this session was built."""

        with self._lock, _command_session_directory(self._working_directory):
            self._refresh_default_project()
            return _host_visible_command_result(
                _repair_command_with_session(
                    self._session,
                    command,
                    failure=failure,
                    request=request,
                )
            )

    def tool_specs(self) -> list[Any]:
        """Return explicit registry specs bound to this host-owned session."""

        from chemsmart.agent.registry import build_tool_spec

        return [
            build_tool_spec(
                self.synthesize_command,
                registered_name="synthesize_command",
                metadata=RuntimeToolMetadata(read_only=True),
            ),
            build_tool_spec(
                self.repair_command,
                registered_name="repair_command",
                metadata=RuntimeToolMetadata(read_only=True),
            ),
        ]

    def _refresh_default_project(self) -> None:
        if self._resolve_default_project:
            self._session.default_project = (
                resolve_default_project() or ""
            ).strip()


_COMMAND_SESSION_DIRECTORY_LOCK = RLock()


@contextmanager
def _command_session_directory(directory: Path | None):
    if directory is None:
        yield
        return
    with _COMMAND_SESSION_DIRECTORY_LOCK:
        previous = Path.cwd()
        os.chdir(directory)
        try:
            yield
        finally:
            os.chdir(previous)


def _host_visible_command_result(payload: JsonDict) -> JsonDict:
    """Project a command-tool answer onto observable, path-sanitized evidence."""

    visible = {
        key: payload[key]
        for key in (
            "ok",
            "status",
            "command",
            "original_command",
            "repaired",
            "explanation",
            "confidence",
            "project",
            "missing_info",
            "action",
            "semantic",
            "intent",
            "preflight",
            "issues",
            "reasoning",
            "reasoning_provenance",
        )
        if key in payload
    }
    return sanitize_public_payload(visible)


def synthesize_command(request: str) -> JsonDict:
    """Synthesize one grounded chemsmart CLI command from a user request."""

    return _synthesize_command_with_session(_session_for_cwd(), request)


def _synthesize_command_with_session(
    session: SynthesisSession,
    request: str,
) -> JsonDict:
    full_schema = session.schema
    pruned = prune_schema_for_request(
        full_schema, request, workspace_program=_workspace_program()
    )
    variant = schema_variant_id(pruned)
    try:
        session.schema = pruned
        result = session.prepare_command(request)
        # Full-schema retries are intentionally forbidden here. They exceed
        # the synthesis budget and cannot become positive SFT examples. An
        # infeasible scoped result should ask for a clearer intent instead.
    finally:
        session.schema = full_schema
    semantic = session._last_semantic_result
    expected_intent = IntentSpec.from_request(request)
    command = str(result.get("command") or "").strip()
    intent = evaluate_intent(command, expected_intent) if command else None
    if command:
        record_command(command)
        clear_resolved_slots()
        if intent is not None:
            _record_intent_result(command, intent)
    elif result.get("status") == "needs_clarification":
        missing = [str(item) for item in result.get("missing_info") or []]
        new_slots = record_clarification_slots(missing)
        if missing and not new_slots:
            result = dict(result)
            result["status"] = "infeasible"
            result["explanation"] = (
                "The same required information was requested twice without "
                "a state change; the workflow stopped to avoid a retry loop."
            )
            result["failure_class"] = "repeated_clarification"
    public_reasoning = _public_synthesis_trace(result, semantic)
    payload = {
        "schema_variant": variant,
        "ok": result.get("status")
        in {
            "ready",
            "informational",
            "needs_clarification",
        },
        "status": result.get("status"),
        "command": result.get("command") or "",
        "explanation": result.get("explanation") or "",
        "confidence": result.get("confidence") or "low",
        "project": result.get("project") or "",
        "missing_info": result.get("missing_info") or [],
        "alternatives": result.get("alternatives") or [],
        "action": result.get("action") or "synthesize_command",
        "decision_trace": result.get("decision_trace") or {},
        "semantic": semantic.to_dict() if semantic is not None else None,
        "intent": intent.to_dict() if intent is not None else None,
        "preflight": (
            build_command_preflight_receipt(
                command,
                semantic,
                intent,
            ).to_dict()
            if command and semantic is not None
            else None
        ),
        "workflow_state": current_workflow_state().to_dict(),
        "raw_response": session._last_raw_response,
        # Provider chain-of-thought is only an ephemeral parser aid. The
        # training ledger receives observable synthesis evidence instead.
        "reasoning": public_reasoning,
        "reasoning_provenance": "public_decision_trace",
    }
    command = str(payload["command"]).strip()
    if intent is not None and intent.verdict == "reject":
        payload["ok"] = False
        payload["status"] = "intent_reject"
        payload["missing_info"] = intent.failed_rule_ids
        payload["explanation"] = (
            "The synthesized command is executable but does not preserve all "
            "explicit user intent. Repair the failed intent fields first."
        )
    if command and semantic is not None:
        _record_gate_result(_cache_key(command), semantic)
    return payload


def _public_synthesis_trace(
    result: JsonDict,
    semantic: CommandSemanticResult | None,
) -> str:
    """Build short user-auditable evidence without provider private CoT."""

    lines: list[str] = []
    trace = result.get("decision_trace")
    if isinstance(trace, dict):
        summary = str(trace.get("decision_summary") or "").strip()
        if summary:
            lines.append(summary)
        evidence = trace.get("evidence")
        if isinstance(evidence, list):
            lines.extend(
                str(item).strip() for item in evidence[:3] if str(item).strip()
            )

    command = str(result.get("command") or "").strip()
    if command:
        parsed = parse_model_command(command)
        if parsed.program and parsed.job:
            lines.append(f"Selected {parsed.program} {parsed.job} command.")
        if semantic is not None:
            lines.append(
                f"Deterministic semantic gate verdict: {semantic.verdict}."
            )
        if parsed.filename:
            lines.append(f"Input structure: {parsed.filename}.")
        if parsed.project:
            lines.append(f"Workspace project: {parsed.project}.")
    else:
        status = str(result.get("status") or "").strip()
        if status:
            lines.append(f"Command synthesis status: {status}.")

    if semantic is not None and not command:
        lines.append(
            f"Deterministic semantic gate verdict: {semantic.verdict}."
        )

    unique: list[str] = []
    for line in lines:
        if line not in unique:
            unique.append(line)
    return "\n".join(unique[:5])


def repair_command(
    command: str,
    failure: str = "",
    request: str = "",
) -> JsonDict:
    """Repair a failed chemsmart CLI command and re-run semantic validation."""

    return _repair_command_with_session(
        _session_for_cwd(),
        command,
        failure=failure,
        request=request,
    )


def _repair_command_with_session(
    session: SynthesisSession,
    command: str,
    *,
    failure: str = "",
    request: str = "",
) -> JsonDict:
    original = command.strip()
    original_semantic = _gate_command(original)
    expected_intent = _expected_intent_for_repair(original, request)
    if original_semantic.verdict in {"ok", "warn"}:
        intent = (
            evaluate_intent(original, expected_intent)
            if expected_intent is not None
            else _INTENT_CACHE.get(_intent_cache_key(original))
        )
        if intent is not None:
            _record_intent_result(original, intent)
        intent_rejected = intent is not None and intent.verdict == "reject"
        return {
            "ok": not intent_rejected,
            "status": "intent_reject" if intent_rejected else "ready",
            "command": original,
            "original_command": original,
            "repaired": False,
            "semantic": original_semantic.to_dict(),
            "intent": intent.to_dict() if intent is not None else None,
            "preflight": build_command_preflight_receipt(
                original,
                original_semantic,
                intent,
            ).to_dict(),
            "issues": intent.failed_rule_ids if intent_rejected else [],
        }

    repair_request = request.strip() or "Repair this chemsmart command."
    if failure.strip():
        repair_request = f"{repair_request}\nFailure: {failure.strip()}"
    result = {
        "status": "ready",
        "command": original,
        "explanation": "Repair this chemsmart command.",
        "confidence": "medium",
        "missing_info": [],
        "alternatives": [],
    }
    # Repairs are rare and correctness-critical: always run them against the
    # full schema, never a request-pruned one.
    session.schema = _command_schema()
    repaired = session._repair_ready_result(repair_request, result)
    if repaired is None:
        return {
            "ok": False,
            "status": "infeasible",
            "command": "",
            "original_command": original,
            "repaired": False,
            "semantic": (
                session._last_semantic_result.to_dict()
                if session._last_semantic_result is not None
                else original_semantic.to_dict()
            ),
            "issues": original_semantic.failed_rule_ids,
        }
    repaired_command = str(repaired.get("command") or "").strip()
    semantic = session._last_semantic_result or _gate_command(repaired_command)
    intent = (
        evaluate_intent(repaired_command, expected_intent)
        if expected_intent is not None and repaired_command
        else None
    )
    if intent is not None:
        _record_intent_result(repaired_command, intent)
    intent_rejected = intent is not None and intent.verdict == "reject"
    _record_gate_result(_cache_key(repaired_command), semantic)
    return {
        "ok": semantic.verdict in {"ok", "warn"} and not intent_rejected,
        "status": (
            "intent_reject"
            if intent_rejected
            else repaired.get("status") or "ready"
        ),
        "command": repaired_command,
        "original_command": original,
        "repaired": repaired_command != original,
        "semantic": semantic.to_dict(),
        "intent": intent.to_dict() if intent is not None else None,
        "preflight": build_command_preflight_receipt(
            repaired_command,
            semantic,
            intent,
        ).to_dict(),
        "issues": [
            *semantic.failed_rule_ids,
            *(intent.failed_rule_ids if intent_rejected else []),
        ],
    }


def register_command_intent(
    command: str,
    expected: IntentSpec | JsonDict,
) -> IntentResult:
    """Register deterministic request intent for later execution receipts.

    This is an internal harness hook, not a registered model tool. Controlled
    evaluations use it when the gold intent comes from a frozen case fixture.
    """

    spec = (
        expected
        if isinstance(expected, IntentSpec)
        else IntentSpec.from_dict(expected)
    )
    result = evaluate_intent(command, spec, cwd=str(Path.cwd()))
    _record_intent_result(command, result)
    if spec.project and spec.program in PROJECT_PROGRAMS:
        select_workspace_project(spec.project, spec.program)
    return result


def inspect_chemsmart_command(
    command: str,
    request: str,
    *,
    cwd: str | Path | None = None,
) -> JsonDict:
    """Inspect a ChemSmart command without launching a process.

    The public result intentionally omits argv, workspace paths, raw evidence,
    and provider reasoning. A successful static inspection is never presented
    as runtime semantic proof; it remains ready only for a separate dry run.
    """

    normalized = command.strip()
    base_cwd = str(Path(cwd or Path.cwd()).resolve())
    parsed = parse_model_command(normalized, cwd=base_cwd)
    semantic = inspect_command_semantics(normalized, cwd=base_cwd)
    intent = (
        evaluate_intent(
            normalized,
            IntentSpec.from_request(request),
            cwd=base_cwd,
        )
        if request.strip()
        else None
    )
    intent_available = intent is not None and bool(intent.assertions)

    if semantic.verdict == "reject":
        status = "rejected"
    elif not intent_available:
        status = "needs_clarification"
    elif intent.verdict == "reject":
        status = "intent_reject"
    else:
        status = "ready_for_dry_run"

    return {
        "schema_version": "1",
        "status": status,
        "command_digest": hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest(),
        "parse": {
            "accepted": parsed.parse_error is None,
            "action": parsed.action,
            "program": parsed.program,
            "job": parsed.job,
            "project": parsed.project,
            "input_name": _display_input_name(parsed.filename),
            "charge": parsed.charge,
            "multiplicity": parsed.multiplicity,
            "method": {
                "functional": parsed.functional,
                "ab_initio": parsed.ab_initio,
                "basis": parsed.basis,
                "aux_basis": parsed.aux_basis,
                "solvent_model": parsed.solvent_model,
                "solvent_id": parsed.solvent_id,
            },
        },
        "intent": {
            "verdict": intent.verdict if intent_available else "unavailable",
            "failed_rule_ids": (
                intent.failed_rule_ids if intent_available else []
            ),
            "assertions": [
                {"id": row.id, "status": row.status}
                for row in (intent.assertions if intent_available else ())
            ],
        },
        "semantic": {
            "verdict": semantic.verdict,
            "complete": False,
            "failed_rule_ids": semantic.failed_rule_ids,
            "missing_info": semantic.missing_info,
            "issues": [
                {
                    "rule_id": issue.rule_id,
                    "severity": issue.severity,
                    "message": issue.message,
                }
                for issue in semantic.issues
            ],
        },
        "dry_run": {
            "state": "required",
            "process_started": False,
        },
        "missing_info": (
            ["explicit research intent"] if not request.strip() else []
        )
        or (["extractable research intent"] if not intent_available else []),
    }


def _display_input_name(filename: str | None) -> str | None:
    if not filename:
        return None
    return re.split(r"[/\\]", filename)[-1] or None


def _expected_intent_for_repair(
    command: str,
    request: str,
) -> IntentSpec | None:
    cached = _INTENT_CACHE.get(_intent_cache_key(command))
    if cached is not None:
        return cached.expected
    if not request.strip():
        return None
    spec = IntentSpec.from_request(request)
    values = spec.to_dict()
    if (
        not any(values.get(name) for name in INTENT_CORE_FIELDS)
        and not spec.chemistry
    ):
        return None
    return spec


def _intent_cache_key(command: str) -> tuple[str, str, str]:
    return (
        current_workflow_scope(),
        str(Path.cwd().resolve()),
        command,
    )


def _record_intent_result(command: str, result: IntentResult) -> None:
    _INTENT_CACHE[_intent_cache_key(command)] = result


def _sub_expected_intent(spec: IntentSpec) -> JsonDict:
    expected: JsonDict = {}
    for source, target in (
        ("program", "program"),
        ("kind", "kind"),
        ("project", "project"),
        ("server", "server"),
        ("input_path", "filename"),
        ("charge", "charge"),
        ("multiplicity", "multiplicity"),
    ):
        value = getattr(spec, source)
        if value is not None:
            expected[target] = value
    expected.update(
        {
            key: value
            for key, value in spec.chemistry.items()
            if value is not None
        }
    )
    return expected


def execute_chemsmart_command(
    command: str,
    test: bool = False,
    timeout_s: int = 3600,
) -> JsonDict:
    """Execute a semantic-gated command after approval.

    Set ``test=False`` for an explicit run or submission approved by the user.
    ``test=True`` adds the CLI's safe fake/test flags and can satisfy a harness
    receipt, but never represents a real scheduler submission outcome.
    """

    return execute_chemsmart_command_observed(
        command,
        test=test,
        timeout_s=timeout_s,
    )


def execute_chemsmart_command_observed(
    command: str,
    *,
    test: bool = False,
    timeout_s: int = 3600,
    calculation_context: CalculationContext | None = None,
    event_sink: Callable[[CalculationEvent], None] | None = None,
) -> JsonDict:
    """Execute a command while optionally publishing calculation events.

    The observer and persistence context are internal runtime concerns and are
    deliberately absent from the model-facing tool schema.
    """

    normalized = command.strip()
    semantic = _gate_command(normalized)
    if semantic.verdict == "reject":
        return {
            "ok": False,
            "status": "rejected",
            "command": normalized,
            "semantic": semantic.to_dict(),
            "error": "semantic gate rejected command; repair before execution",
        }

    try:
        tokens = shlex.split(normalized)
    except ValueError as exc:
        return {
            "ok": False,
            "status": "rejected",
            "command": normalized,
            "error": f"command could not be tokenized: {exc}",
            "semantic": semantic.to_dict(),
        }

    argv = _test_argv(tokens) if test else list(tokens)
    argv = quiet_chemsmart_argv(argv)
    submit_scripts_before = submit_script_fingerprints(Path.cwd())
    observed = execute_observed_process(
        argv,
        command=normalized,
        timeout_s=timeout_s,
        context=calculation_context,
        event_sink=event_sink,
    )
    calculation = dict(observed.get("calculation") or {})
    returncode = calculation.get("returncode")
    calculation_status = str(calculation.get("status") or "process_failed")
    stdout = str(observed.get("stdout_tail") or "")
    stderr = str(observed.get("stderr_tail") or "")
    ok = calculation_status == "completed" and returncode == 0
    return {
        "ok": ok,
        "status": "ok" if ok else calculation_status,
        "command": normalized,
        "executed_argv": argv,
        "test": test,
        "returncode": returncode,
        "stdout_tail": stdout,
        "stderr_tail": stderr,
        "semantic": semantic.to_dict(),
        "calculation": calculation,
        "terminal_state": execution_terminal_state(
            normalized,
            returncode=int(returncode) if isinstance(returncode, int) else 1,
            test=test,
            cwd=Path.cwd(),
            workflow_scope=current_workflow_scope(),
            intent_expected=(
                _sub_expected_intent(cached_intent.expected)
                if (
                    cached_intent := _INTENT_CACHE.get(
                        _intent_cache_key(normalized)
                    )
                )
                is not None
                else None
            ),
            selected_project=current_workflow_state().project,
            submit_scripts_before=submit_scripts_before,
        ),
        **(
            {"error": calculation.get("error") or calculation.get("stage")}
            if not ok
            else {}
        ),
    }


def _session_for_cwd() -> SynthesisSession:
    global _SESSION
    cwd = str(Path.cwd().resolve())
    workflow_scope = current_workflow_scope()
    provider_name = _provider_name()
    if (
        _SESSION is None
        or _SESSION.cwd != cwd
        or _SESSION.provider_name != provider_name
        or _SESSION.workflow_scope != workflow_scope
    ):
        _SESSION = _SessionSlot(
            cwd=cwd,
            provider_name=provider_name,
            workflow_scope=workflow_scope,
            session=SynthesisSession(
                schema=_command_schema(),
                enable_intent_router=False,
            ),
        )
    # The workspace project can appear or change mid-session (e.g. the loop
    # just wrote a new YAML via write_project_yaml). Re-resolve on every call
    # so -p injection and the yaml_check gate always see current state.
    _SESSION.session.default_project = (
        resolve_default_project() or ""
    ).strip()
    return _SESSION.session


def _command_schema() -> JsonDict:
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = build_chemsmart_cli_schema()
    return _SCHEMA


def _workspace_program() -> str | None:
    """Program (gaussian/orca) of the loaded workspace project, if any."""

    selected = current_workflow_state().project
    if selected is not None:
        return selected.program
    try:
        status = resolve_workspace_project()
    except Exception:
        return None
    program = str(getattr(status, "program", "") or "").strip()
    return program or None


def _provider_name() -> str:
    try:
        from chemsmart.agent.providers import get_provider

        provider = get_provider()
    except Exception:
        return "unavailable"
    return str(getattr(provider, "name", None) or provider.__class__.__name__)


def _gate_command(command: str) -> CommandSemanticResult:
    key = _cache_key(command)
    cached = _GATE_CACHE.get(key)
    if cached is not None:
        return cached
    result = evaluate_command_semantics(command)
    _record_gate_result(key, result)
    return result


def _record_gate_result(
    key: tuple[str, str, WorkspaceFingerprint],
    result: CommandSemanticResult,
) -> None:
    if len(_GATE_CACHE) >= _GATE_CACHE_MAX:
        _GATE_CACHE.clear()
    _GATE_CACHE[key] = result


def _cache_key(command: str) -> tuple[str, str, WorkspaceFingerprint]:
    return (
        str(Path.cwd().resolve()),
        command,
        _workspace_fingerprint(),
    )


def _workspace_fingerprint() -> WorkspaceFingerprint:
    """Fingerprint every workspace project YAML by path/mtime/size.

    A gate verdict is only reusable while the workspace settings it was
    validated against are byte-for-byte the same files; any write (e.g.
    update_project_yaml) changes the fingerprint and forces a re-gate.
    """

    entries: list[tuple[str, int, int]] = []
    try:
        paths = iter_workspace_project_yaml()
    except Exception:
        return ()
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            continue
        entries.append((str(path), stat.st_mtime_ns, stat.st_size))
    return tuple(sorted(entries))


def _test_argv(tokens: list[str]) -> list[str]:
    if len(tokens) < 2 or tokens[0] != "chemsmart":
        return list(tokens)
    argv = list(tokens)
    try:
        top_index = next(
            index
            for index, token in enumerate(argv[1:], start=1)
            if token not in {"--verbose", "--no-verbose"}
        )
    except StopIteration:
        return argv
    if argv[top_index] == "sub":
        if "--test" not in argv[top_index + 1 :]:
            argv.insert(top_index + 1, "--test")
        if "--fake" not in argv[top_index + 1 :]:
            argv.insert(top_index + 1, "--fake")
    elif argv[top_index] == "run":
        scoped = argv[top_index + 1 :]
        if "--fake" not in scoped and "--no-fake" not in scoped:
            argv.insert(top_index + 1, "--fake")
        if "--no-scratch" not in scoped:
            argv.insert(top_index + 1, "--no-scratch")
    return argv


def _tail(text: str | bytes | None, *, limit: int = 4000) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode(errors="replace")
    text = str(text)
    return text[-limit:] if len(text) > limit else text
