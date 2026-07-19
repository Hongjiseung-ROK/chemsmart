"""Desktop adapter for the canonical unified-agent loop.

The adapter owns presentation-only concerns: a restricted registry, Qt-safe
stream events, cooperative cancellation, explicit approvals, recent-session
selection, and conversion of a gated command into :class:`JobDraft`. Durable
state remains the agent session, decision log, and runtime event store.
"""

from __future__ import annotations

import json
import os
import queue
import shlex
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from PySide6.QtCore import QObject, Signal

from chemsmart.agent.permissions import (
    ApprovalDecision,
    PermissionPolicy,
    RuntimePermissionMode,
)
from chemsmart.agent.provider_adapter import ToolRequest
from chemsmart.gui.application.job_draft import (
    DraftProvenance,
    JobDraft,
    ProvenanceKind,
)
from chemsmart.gui.application.runtime_projection import (
    DesktopRuntimeProjection,
    project_runtime_state,
)
from chemsmart.gui.application.task_controller import TaskContext

_DESKTOP_TOOL_GROUPS = ("synthesis", "project_yaml")
_DESKTOP_BLOCKED_TOOLS = frozenset(
    {
        "execute_chemsmart_command",
        "repair_command",
        "run_local",
        "submit_hpc",
        "write_project_yaml",
        "update_project_yaml",
        "wizard_write",
    }
)
_SENSITIVE_FIELD_MARKERS = ("api", "key", "password", "secret", "token")
_AGENT_CWD_LOCK = threading.RLock()


@dataclass(frozen=True)
class GateReceipt:
    """One bounded deterministic gate projection for the Chat surface."""

    name: str
    verdict: str = "not_run"
    rule_ids: tuple[str, ...] = ()
    notice: str = ""

    @property
    def accepted(self) -> bool:
        return self.verdict in {"ok", "warn", "pass"}


@dataclass(frozen=True)
class AgentStreamEvent:
    """Public, bounded projection of a canonical decision-log entry."""

    kind: str
    title: str
    detail: str = ""
    status: str = ""
    tool: str = ""


@dataclass(frozen=True)
class ApprovalPrompt:
    request_id: str
    tool: str
    description: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class SessionChoice:
    session_id: str
    request: str
    turn_index: int

    @property
    def label(self) -> str:
        suffix = self.session_id[-8:]
        request = " ".join(self.request.split())
        if len(request) > 52:
            request = f"{request[:49]}…"
        return f"…{suffix} · {request or 'Untitled session'}"


@dataclass(frozen=True)
class AgentTurnResult:
    request: str
    session_id: str = ""
    provider_name: str = ""
    provider_model: str = ""
    assistant_text: str = ""
    command: str = ""
    draft: JobDraft | None = None
    intent_gate: GateReceipt = GateReceipt("Intent")
    semantic_gate: GateReceipt = GateReceipt("Semantic")
    runtime_projection: DesktopRuntimeProjection | None = None
    ask_user: Mapping[str, Any] | None = None
    tool_count: int = 0
    limit_reason: str = ""
    error_message: str = ""
    deterministic_fallback: bool = False

    @property
    def can_open_draft(self) -> bool:
        return bool(
            self.draft is not None
            and not self.limit_reason
            and self.intent_gate.accepted
            and self.semantic_gate.accepted
        )


def desktop_safe_registry():
    """Return read-only agent tools with all execution/write paths absent."""

    from chemsmart.agent.registry import ToolRegistry
    from chemsmart.agent.tool_protocol import is_read_only

    grouped = ToolRegistry.default(groups=_DESKTOP_TOOL_GROUPS)
    safe_tools = [
        tool
        for tool in grouped.list_tools()
        if is_read_only(tool) and tool.name not in _DESKTOP_BLOCKED_TOOLS
    ]
    registry = ToolRegistry(safe_tools)
    names = {tool.name for tool in registry.list_tools()}
    leaked = names.intersection(_DESKTOP_BLOCKED_TOOLS)
    if leaked:
        raise RuntimeError(
            "Desktop agent registry contains blocked tools: "
            f"{', '.join(sorted(leaked))}"
        )
    return registry


class AgentWorker(QObject):
    """Run canonical agent turns while exposing presentation-safe Qt signals."""

    step = Signal(object)
    approval_requested = Signal(object)
    session_changed = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        session_root: Path | None = None,
        *,
        provider_factory: Callable[[], Any] | None = None,
        registry_factory: Callable[[], Any] = desktop_safe_registry,
    ) -> None:
        super().__init__()
        if session_root is None:
            from chemsmart.agent.core import _default_session_root

            session_root = Path(_default_session_root())
        self.session_root = Path(session_root).expanduser()
        self._provider_factory = provider_factory
        self._registry_factory = registry_factory
        self._session: Any | None = None
        self._session_mode = ""
        self._resume_id = ""
        self._active_registry: Any | None = None
        self._approval_lock = threading.Lock()
        self._approval_waiters: dict[
            str, queue.Queue[ApprovalDecision]
        ] = {}

    @property
    def active_session_id(self) -> str:
        state = getattr(self._session, "state", None)
        return str(getattr(state, "session_id", "") or self._resume_id)

    @property
    def active_session_mode(self) -> str:
        """Return the presentation-safe mode bound to the active session."""

        return self._session_mode

    def next_session_boundary(self, request: str) -> str | None:
        """Predict a new canonical mode before dispatch, without needing an ID."""

        if _direct_run_command(request.strip()) is not None:
            return "deterministic"
        if self._session_mode == "deterministic":
            return "ai"
        if self._session is None and not self._resume_id:
            return "ai"
        return None

    def new_session(self) -> None:
        self._session = None
        self._session_mode = ""
        self._resume_id = ""
        self.session_changed.emit("")

    def select_session(self, session_id: str) -> None:
        root = self.session_root.resolve()
        unresolved = root / session_id
        candidate = unresolved.resolve()
        if (
            not session_id
            or Path(session_id).name != session_id
            or candidate.parent != root
            or unresolved.is_symlink()
            or not (candidate / "session.json").is_file()
        ):
            raise ValueError("Choose a current ChemSmart agent session.")
        self._session = None
        self._session_mode = ""
        self._resume_id = session_id
        self.session_changed.emit(session_id)

    def recent_sessions(self, limit: int = 10) -> tuple[SessionChoice, ...]:
        """Return bounded current-schema choices without reading log payloads."""

        if limit < 1:
            return ()
        from chemsmart.agent.services.session_store import (
            current_session_dirs,
            load_current_session_state,
        )

        choices: list[SessionChoice] = []
        for directory in current_session_dirs(self.session_root)[:limit]:
            try:
                state = load_current_session_state(directory, required=True)
            except Exception:
                continue
            if state is None:
                continue
            choices.append(
                SessionChoice(
                    session_id=state.session_id,
                    request=str(state.request or ""),
                    turn_index=int(state.turn_index),
                )
            )
        return tuple(choices)

    def resolve_approval(
        self,
        request_id: str,
        decision: ApprovalDecision,
    ) -> bool:
        with self._approval_lock:
            waiter = self._approval_waiters.get(request_id)
        if waiter is None:
            return False
        try:
            waiter.put_nowait(decision)
        except queue.Full:
            return False
        return True

    def run_request(
        self,
        request: str,
        context: TaskContext,
        *,
        workspace: Path,
    ) -> AgentTurnResult:
        """Run one request; only explicit ``chemsmart run`` bypasses AI."""

        normalized = request.strip()
        if not normalized:
            raise ValueError("Agent request must not be empty.")
        workspace = Path(workspace).expanduser().resolve()
        if not workspace.is_dir():
            raise ValueError("The selected ChemSmart workspace is unavailable.")

        context.report_indeterminate("Preparing the safe agent session")
        context.raise_if_cancelled()
        direct = _direct_run_command(normalized)
        if direct is not None:
            # The deterministic provider is a canonical receipt generator, not
            # a conversational model. Isolate it from an AI-backed session so
            # a later natural-language turn cannot reuse the wrong provider.
            self._session = None
            self._session_mode = ""
            self._resume_id = ""
            result = self._run_deterministic_command(
                normalized,
                direct,
                context,
                workspace=workspace,
            )
            self.finished.emit(result)
            return result

        if self._session_mode == "deterministic":
            self._session = None
            self._session_mode = ""
            self._resume_id = ""
        provider = (
            getattr(self._session, "_provider", None)
            if self._session_mode == "ai" and self._session is not None
            else None
        )
        try:
            provider = provider or self._make_provider()
        except Exception as exc:
            result = AgentTurnResult(
                request=normalized,
                error_message=(
                    "AI assistance is not configured or could not be opened. "
                    "Job builder remains fully available; connect a provider "
                    f"in Settings and retry. ({type(exc).__name__})"
                ),
            )
            self.finished.emit(result)
            return result

        context.report_indeterminate("Waiting for the configured AI provider")
        registry = (
            self._session.registry
            if self._session_mode == "ai" and self._session is not None
            else self._registry_factory()
        )
        result = self._run_session(
            normalized,
            context,
            workspace=workspace,
            provider=provider,
            registry=registry,
            deterministic_fallback=False,
        )
        self.finished.emit(result)
        return result

    def _run_deterministic_command(
        self,
        command: str,
        tokens: tuple[str, ...],
        context: TaskContext,
        *,
        workspace: Path,
    ) -> AgentTurnResult:
        from chemsmart.agent.harness.command_semantics import (
            evaluate_command_semantics,
        )
        from chemsmart.agent.harness.intent import IntentSpec, evaluate_intent

        context.report_indeterminate("Running deterministic safety gates")
        try:
            _parse_desktop_run_draft(tokens)
        except (TypeError, ValueError) as exc:
            payload = _desktop_preflight_rejection(command, exc)
        else:
            semantic = evaluate_command_semantics(
                command,
                cwd=workspace,
                timeout_s=30.0,
            )
            context.raise_if_cancelled()
            intent = evaluate_intent(
                command,
                IntentSpec.from_request(command),
                cwd=str(workspace),
            )
            payload = {
                "ok": (
                    semantic.verdict != "reject" and intent.verdict != "reject"
                ),
                "status": (
                    "ready"
                    if semantic.verdict != "reject"
                    and intent.verdict != "reject"
                    else "infeasible"
                ),
                "command": command,
                "explanation": (
                    "The explicit command was checked locally without an AI "
                    "provider. Review it in Job builder before safe preview."
                ),
                "confidence": "high",
                "semantic": semantic.to_dict(),
                "intent": intent.to_dict(),
            }
        provider = _DeterministicCommandProvider(
            command,
            accepted=bool(payload["ok"]),
        )
        registry = _DeterministicRegistry(self._registry_factory(), payload)
        return self._run_session(
            command,
            context,
            workspace=workspace,
            provider=provider,
            registry=registry,
            deterministic_fallback=True,
        )

    def _run_session(
        self,
        request: str,
        context: TaskContext,
        *,
        workspace: Path,
        provider: Any,
        registry: Any,
        deterministic_fallback: bool,
    ) -> AgentTurnResult:
        from chemsmart.agent.core import AgentSession

        self._active_registry = registry
        with _agent_working_directory(workspace):
            if self._session is None:
                kwargs = {
                    "provider": provider,
                    "registry": registry,
                    "session_root": str(self.session_root),
                    "stage_prompt": "unified_agent.md",
                    "runtime_v2": "active",
                    "decision_listener": self._on_decision,
                }
                if self._resume_id:
                    self._session = AgentSession.load(
                        self._resume_id,
                        cwd_override=str(workspace),
                        **kwargs,
                    )
                else:
                    self._session = AgentSession(**kwargs)
                self._session_mode = (
                    "deterministic" if deterministic_fallback else "ai"
                )
            policy = PermissionPolicy(mode=RuntimePermissionMode.READ_ONLY)
            result = self._session.run_loop(
                request,
                policy=policy,
                approver=lambda tool_request: self._request_approval(
                    tool_request,
                    context,
                ),
                cancellation_check=lambda: context.token.cancelled,
            )
        session_id = str(result.get("session_id") or "")
        self._resume_id = session_id
        self.session_changed.emit(session_id)
        context.raise_if_cancelled()
        projected = _project_agent_result(
            request,
            result,
            deterministic_fallback=deterministic_fallback,
        )
        controller = getattr(self._session, "_runtime_controller", None)
        runtime_projection = (
            project_runtime_state(controller.state)
            if controller is not None
            else None
        )
        provider_name = str(getattr(provider, "name", "") or "")
        provider_model = str(
            getattr(provider, "default_model", "") or ""
        )
        error_message = projected.error_message
        if result.get("limit_reason") == "provider_errors":
            error_message = (
                "The AI provider did not complete this turn after bounded "
                "retries. No command was accepted; Job builder is unchanged."
            )
        return AgentTurnResult(
            **{
                **projected.__dict__,
                "session_id": session_id,
                "provider_name": provider_name,
                "provider_model": provider_model,
                "runtime_projection": runtime_projection,
                "error_message": error_message,
            }
        )

    def _make_provider(self) -> Any:
        if self._provider_factory is not None:
            return self._provider_factory()
        from chemsmart.agent.providers import get_provider

        return get_provider()

    def _request_approval(
        self,
        request: ToolRequest,
        context: TaskContext,
    ) -> ApprovalDecision:
        if request.name in _DESKTOP_BLOCKED_TOOLS:
            return ApprovalDecision.DENY
        waiter: queue.Queue[ApprovalDecision] = queue.Queue(maxsize=1)
        with self._approval_lock:
            self._approval_waiters[request.request_id] = waiter
        registry = self._active_registry
        describe = getattr(registry, "describe_tool", None)
        description = (
            describe(request.name)
            if callable(describe)
            else request.name.replace("_", " ")
        )
        prompt = ApprovalPrompt(
            request_id=request.request_id,
            tool=request.name,
            description=description,
            arguments=_redact_mapping(request.arguments),
        )
        self.approval_requested.emit(prompt)
        deadline = time.monotonic() + 120
        try:
            while True:
                if context.token.cancelled or time.monotonic() >= deadline:
                    return ApprovalDecision.DENY
                try:
                    return waiter.get(timeout=0.05)
                except queue.Empty:
                    continue
        finally:
            with self._approval_lock:
                self._approval_waiters.pop(request.request_id, None)

    def _on_decision(self, entry: dict[str, Any]) -> None:
        event = _public_stream_event(entry)
        if event is not None:
            self.step.emit(event)


class _DeterministicRegistry:
    def __init__(self, registry: Any, payload: dict[str, Any]) -> None:
        self._registry = registry
        self._payload = payload

    def call(self, name: str, args: dict[str, Any] | None = None) -> Any:
        if name == "synthesize_command":
            return dict(self._payload)
        return self._registry.call(name, args)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._registry, name)


class _DeterministicCommandProvider:
    name = "desktop-local"
    wire_protocol = "openai"
    default_model = "deterministic-command-parser"

    def __init__(self, command: str, *, accepted: bool) -> None:
        self._command = command
        self._accepted = accepted
        self._turn = 0

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        timeout_s: float = 30,
    ) -> dict[str, Any]:
        del messages, tools, timeout_s
        self._turn += 1
        if self._turn == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "desktop-direct-command",
                                    "type": "function",
                                    "function": {
                                        "name": "synthesize_command",
                                        "arguments": json.dumps(
                                            {"request": self._command},
                                            sort_keys=True,
                                        ),
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": (
                            (
                                "The command passed the local deterministic "
                                "handoff gates. Review it in Job builder."
                            )
                            if self._accepted
                            else (
                                "The explicit command did not pass the local "
                                "deterministic handoff gates. Review the gate "
                                "receipts; no draft was accepted."
                            )
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }


def _project_agent_result(
    request: str,
    result: Mapping[str, Any],
    *,
    deterministic_fallback: bool,
) -> AgentTurnResult:
    command = ""
    draft: JobDraft | None = None
    intent = GateReceipt("Intent")
    semantic = GateReceipt("Semantic")
    error_message = ""
    tool_outcomes = list(result.get("tool_outcomes") or [])
    receipt_ref = str(result.get("session_id") or "")

    for outcome in reversed(tool_outcomes):
        if getattr(outcome, "name", "") not in {
            "synthesize_command",
            "repair_command",
        }:
            continue
        if getattr(outcome, "status", "") != "ok":
            semantic = GateReceipt(
                "Semantic",
                "reject",
                ("desktop.agent.latest_command_tool_failed",),
                "The latest command synthesis or repair did not complete.",
            )
            error_message = (
                "The latest command correction did not complete, so no earlier "
                "draft was accepted for handoff."
            )
            break
        payload = getattr(outcome, "raw_result", None)
        if not isinstance(payload, dict):
            semantic = GateReceipt(
                "Semantic",
                "reject",
                ("desktop.agent.latest_command_receipt_missing",),
                "The latest command tool returned no structured receipt.",
            )
            error_message = (
                "The latest command correction returned no usable receipt, so "
                "no earlier draft was accepted for handoff."
            )
            break
        command = str(payload.get("command") or "").strip()
        intent = _gate_from_payload("Intent", payload.get("intent"))
        semantic = _gate_from_payload("Semantic", payload.get("semantic"))
        synthesis_ready = (
            payload.get("ok") is True and payload.get("status") == "ready"
        )
        if command and intent.accepted and semantic.accepted and synthesis_ready:
            try:
                from chemsmart.gui.services.cli_schema_service import (
                    draft_from_command,
                )

                draft = draft_from_command(
                    shlex.split(command),
                    provenance=DraftProvenance(
                        kind=ProvenanceKind.AGENT_RECEIPT,
                        receipt_ref=(
                            f"{receipt_ref}:{getattr(outcome, 'request_id', '')}"
                        ),
                    ),
                )
            except (ValueError, TypeError) as exc:
                semantic = GateReceipt(
                    "Semantic",
                    "reject",
                    ("desktop.job_draft.parse",),
                    f"Typed Job builder handoff rejected: {type(exc).__name__}",
                )
        elif command and intent.accepted and semantic.accepted:
            semantic = GateReceipt(
                "Semantic",
                "reject",
                ("desktop.agent.ready_status",),
                "The agent did not mark this command ready for handoff.",
            )
        break

    assistant_text = str(
        result.get("assistant_output") or result.get("final_message") or ""
    ).strip()
    limit_reason = str(result.get("limit_reason") or "")
    if limit_reason:
        # A command emitted before a provider/budget/cancellation safety stop is
        # useful diagnostic evidence, but it is not a completed handoff.
        draft = None
        error_message = (
            "The agent stopped at a bounded safety limit. No command was "
            f"accepted for handoff. ({limit_reason})"
        )
    ask_user = result.get("ask_user_question")
    if not assistant_text and ask_user:
        assistant_text = str(ask_user.get("question") or "")
    if not assistant_text and not command and not result.get("limit_reason"):
        error_message = (
            "The agent returned no public answer or gated command. "
            "Nothing was changed."
        )
    return AgentTurnResult(
        request=request,
        assistant_text=assistant_text,
        command=command,
        draft=draft,
        intent_gate=intent,
        semantic_gate=semantic,
        ask_user=ask_user if isinstance(ask_user, dict) else None,
        tool_count=len(tool_outcomes),
        limit_reason=limit_reason,
        error_message=error_message,
        deterministic_fallback=deterministic_fallback,
    )


def _gate_from_payload(name: str, payload: Any) -> GateReceipt:
    if not isinstance(payload, dict):
        return GateReceipt(name)
    verdict = str(payload.get("verdict") or "not_run").lower()
    rule_ids = payload.get("failed_rule_ids") or []
    if not isinstance(rule_ids, (list, tuple)):
        rule_ids = []
    return GateReceipt(
        name=name,
        verdict=verdict,
        rule_ids=tuple(str(item) for item in rule_ids[:24]),
        notice=str(payload.get("notice") or "")[:320],
    )


def _public_stream_event(
    entry: Mapping[str, Any],
) -> AgentStreamEvent | None:
    kind = str(entry.get("kind") or "")
    payload = entry.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    if kind == "request":
        return AgentStreamEvent(kind, "Request recorded", "Session receipt opened")
    if kind == "mode_change":
        return AgentStreamEvent(
            kind,
            "Desktop safety profile active",
            str(payload.get("to_mode") or "read_only"),
            status="safe",
        )
    if kind == "assistant_turn":
        text = _bounded_text(payload.get("assistant_text"), 320)
        return AgentStreamEvent(kind, "Agent response", text)
    if kind == "tool_use_request":
        tool = str(payload.get("tool") or "")
        return AgentStreamEvent(
            kind,
            f"Tool requested · {tool}",
            _bounded_json(_redact_mapping(payload.get("normalized_args") or {})),
            status="pending",
            tool=tool,
        )
    if kind in {"tool_use_approved", "tool_use_denied"}:
        tool = str(payload.get("tool") or "")
        approved = kind.endswith("approved")
        return AgentStreamEvent(
            kind,
            f"Tool {'allowed' if approved else 'blocked'} · {tool}",
            _bounded_text(payload.get("source") or payload.get("reason"), 160),
            status="ok" if approved else "blocked",
            tool=tool,
        )
    if kind == "tool_use_result":
        tool = str(payload.get("tool") or "")
        status = str(payload.get("status") or "")
        return AgentStreamEvent(
            kind,
            f"Receipt · {tool}",
            f"Deterministic tool status: {status or 'recorded'}",
            status=status,
            tool=tool,
        )
    if kind == "provider_turn_error":
        return AgentStreamEvent(
            kind,
            "Provider retry",
            f"Attempt {payload.get('attempt') or '?'} failed safely",
            status="warning",
        )
    if kind == "loop_limit_exceeded":
        return AgentStreamEvent(
            kind,
            "Agent stopped at a safety limit",
            str(payload.get("limit_reason") or "bounded limit"),
            status="blocked",
        )
    if kind == "session_summary":
        blocked = bool(payload.get("blocked"))
        reason = _bounded_text(payload.get("block_reason"), 120)
        return AgentStreamEvent(
            kind,
            "Session receipt sealed with a safety stop"
            if blocked
            else "Session receipt sealed",
            (
                f"Durable evidence saved · {reason or 'blocked'}"
                if blocked
                else "Durable decision and runtime evidence saved"
            ),
            status="blocked" if blocked else "ok",
        )
    return None


def _direct_run_command(request: str) -> tuple[str, ...] | None:
    try:
        tokens = tuple(shlex.split(request))
    except ValueError:
        return None
    if len(tokens) >= 4 and tokens[:2] == ("chemsmart", "run"):
        return tokens
    return None


def _parse_desktop_run_draft(tokens: tuple[str, ...]) -> JobDraft:
    """Purely parse an explicit command through the reviewed desktop schema."""

    from chemsmart.gui.services.cli_schema_service import draft_from_command

    return draft_from_command(tokens)


def _desktop_preflight_rejection(command: str, exc: Exception) -> dict[str, Any]:
    notice = (
        "Desktop Chat only checks Gaussian, ORCA, or xTB run commands that can "
        "be represented as a typed JobDraft. No command process was started."
    )
    return {
        "ok": False,
        "status": "infeasible",
        "command": command,
        "explanation": notice,
        "confidence": "high",
        "semantic": {
            "verdict": "reject",
            "failed_rule_ids": ["desktop.command.unsupported_shape"],
            "notice": f"{notice} ({type(exc).__name__})",
        },
        "intent": {
            "verdict": "not_run",
            "failed_rule_ids": [],
            "notice": "Intent was not evaluated after desktop preflight failed.",
        },
        "issues": ["desktop.command.unsupported_shape"],
    }


def _redact_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    redacted: dict[str, Any] = {}
    for key, item in value.items():
        normalized = str(key).lower()
        if any(marker in normalized for marker in _SENSITIVE_FIELD_MARKERS):
            redacted[str(key)] = "<redacted>"
        elif isinstance(item, Mapping):
            redacted[str(key)] = _redact_mapping(item)
        elif isinstance(item, (list, tuple)):
            redacted[str(key)] = [
                _redact_mapping(child) if isinstance(child, Mapping) else child
                for child in item[:24]
            ]
        else:
            redacted[str(key)] = item
    return redacted


def _bounded_json(value: Any, limit: int = 480) -> str:
    try:
        rendered = json.dumps(value, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        rendered = "{}"
    return rendered if len(rendered) <= limit else f"{rendered[: limit - 1]}…"


def _bounded_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


@contextmanager
def _agent_working_directory(path: Path) -> Iterator[None]:
    """Bind legacy cwd-based agent tools to the selected desktop workspace."""

    with _AGENT_CWD_LOCK:
        original = Path.cwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(original)


__all__ = [
    "AgentStreamEvent",
    "AgentTurnResult",
    "AgentWorker",
    "ApprovalPrompt",
    "GateReceipt",
    "SessionChoice",
    "desktop_safe_registry",
]
