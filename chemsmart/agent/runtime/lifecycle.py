"""Tool lifecycle hooks that emit compact public runtime evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

from chemsmart.agent.runtime.calculations import (
    CalculationContext,
    reset_calculation_context,
    set_calculation_context,
)
from chemsmart.agent.runtime.contracts import RuntimeV2Mode
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.runtime.receipts import collect_artifact_refs
from chemsmart.agent.runtime.tool_catalog import ToolSelection


class EventEmitter(Protocol):
    def emit(
        self,
        kind: EventKind,
        payload: dict[str, Any],
        *,
        idempotency_key: str = "",
    ) -> Any: ...


class ToolExposureViolation(RuntimeError):
    pass


class RuntimeCommandRepairViolation(RuntimeError):
    """Raised before a forged or over-budget typed repair reaches a tool."""


class RuntimeLifecycle:
    def __init__(
        self,
        *,
        emitter: EventEmitter,
        selection: ToolSelection,
        mode: RuntimeV2Mode,
    ) -> None:
        self.emitter = emitter
        self.selection = selection
        self.mode = mode
        self._calculation_context_token = None
        self._typed_repair_task_sha256 = ""
        self._typed_repair_receipt_sha256 = ""
        self._typed_repair_attempt = 0
        self._typed_repair_rule_ids: set[str] = set()
        self._typed_repair_blocked = False

    def preflight_active_exposure(self, *, tool_name: str) -> None:
        """Reject an unexposed active-runtime tool before approval handling.

        A provider may still emit a forged function call even though the tool
        definition was withheld. In active mode that request must fail before
        it can consume an approval or reach a compatibility implementation.
        Shadow mode deliberately keeps its observational behavior.
        """

        if self.mode is RuntimeV2Mode.ACTIVE:
            self._check_exposure(tool_name)

    def before_tool(
        self,
        *,
        request_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        self._check_exposure(tool_name)
        if tool_name == "repair_command" and self.mode is RuntimeV2Mode.ACTIVE:
            self._check_typed_repair(arguments)
        canonical = json.dumps(arguments, sort_keys=True, default=str)
        self.emitter.emit(
            EventKind.TOOL_STARTED,
            {
                "request_id": request_id,
                "tool": tool_name,
                "arg_keys": sorted(arguments),
                "signature_hash": hashlib.sha256(
                    canonical.encode()
                ).hexdigest(),
            },
            idempotency_key=f"tool-start:{request_id}",
        )
        if tool_name == "execute_chemsmart_command":
            session_dir = getattr(self.emitter, "session_dir", None)
            session_id = str(getattr(self.emitter, "session_id", ""))
            turn_id = str(getattr(self.emitter, "turn_id", ""))
            self._calculation_context_token = set_calculation_context(
                CalculationContext(
                    session_dir=session_dir,
                    session_id=session_id,
                    turn_id=turn_id,
                )
            )

    def _check_exposure(self, tool_name: str) -> None:
        if tool_name in self.selection.direct:
            return
        payload = {
            "rule_id": "runtime.tool.not_exposed",
            "tool": tool_name,
            "phase": self.selection.phase.value,
        }
        self.emitter.emit(EventKind.SHADOW_VIOLATION, payload)
        if self.mode is RuntimeV2Mode.ACTIVE:
            raise ToolExposureViolation(
                f"tool {tool_name!r} is not exposed in "
                f"phase {self.selection.phase.value!r}"
            )

    def permission(
        self,
        *,
        request_id: str,
        tool_name: str,
        decision: str,
        reason: str,
    ) -> None:
        self.emitter.emit(
            EventKind.PERMISSION_RESOLVED,
            {
                "request_id": request_id,
                "tool": tool_name,
                "decision": decision,
                "reason": reason,
            },
            idempotency_key=f"permission:{request_id}:{decision}",
        )

    def after_tool(
        self,
        *,
        request_id: str,
        tool_name: str,
        result: Any,
    ) -> None:
        payload = _success_payload(request_id, tool_name, result)
        self.emitter.emit(
            EventKind.TOOL_SUCCEEDED,
            payload,
            idempotency_key=f"tool-result:{request_id}",
        )
        if isinstance(result, dict):
            self._record_typed_repair_state(tool_name, result)
            _emit_state_delta(self.emitter, tool_name, result)
        for receipt in collect_artifact_refs(result, producer_tool=tool_name):
            self.emitter.emit(
                EventKind.ARTIFACT_RECORDED,
                receipt.model_dump(mode="json"),
                idempotency_key=f"artifact:{receipt.sha256}",
            )
        self._reset_calculation_context()

    def tool_failed(
        self,
        *,
        request_id: str,
        tool_name: str,
        error_type: str,
        error_message: str,
        result: Any = None,
    ) -> None:
        rule_ids = list(_rule_ids(result))
        runtime_rule = _runtime_error_rule(error_type)
        if runtime_rule and runtime_rule not in rule_ids:
            rule_ids.append(runtime_rule)
        self.emitter.emit(
            EventKind.TOOL_FAILED,
            {
                "request_id": request_id,
                "tool": tool_name,
                "error_type": error_type,
                "message": error_message[:500],
                "rule_ids": rule_ids,
            },
            idempotency_key=f"tool-result:{request_id}",
        )
        self._reset_calculation_context()

    def _reset_calculation_context(self) -> None:
        if self._calculation_context_token is None:
            return
        reset_calculation_context(self._calculation_context_token)
        self._calculation_context_token = None

    def _check_typed_repair(self, arguments: dict[str, Any]) -> None:
        """Bind a same-turn CEGIS repair to the preceding typed receipt.

        The public tool also compares the provided task digest.  This runtime
        state closes the model-controlled-field loophole within a turn: a
        caller cannot reset attempt=1, omit a previously failed rule, or swap
        the scientific task after an observed receipt. M3 will persist the
        same binding as an approval/event-store object across turns.
        """

        if self._typed_repair_blocked:
            raise RuntimeCommandRepairViolation(
                "cmd.repair.prior_repair_blocked"
            )
        if not self._typed_repair_task_sha256:
            raise RuntimeCommandRepairViolation(
                "cmd.repair.no_prior_typed_receipt"
            )
        supplied_digest = str(arguments.get("prior_task_spec_sha256") or "")
        if supplied_digest != self._typed_repair_task_sha256:
            raise RuntimeCommandRepairViolation(
                "cmd.repair.scientific_task_changed"
            )
        supplied_receipt = str(arguments.get("prior_receipt_sha256") or "")
        if supplied_receipt != self._typed_repair_receipt_sha256:
            raise RuntimeCommandRepairViolation("cmd.repair.receipt_mismatch")
        attempt = arguments.get("repair_attempt")
        if attempt != self._typed_repair_attempt + 1 or attempt > 2:
            raise RuntimeCommandRepairViolation("cmd.repair.budget_exhausted")
        counterexample = arguments.get("counterexample")
        rule_id = (
            str(counterexample.get("rule_id") or "")
            if isinstance(counterexample, dict)
            else ""
        )
        if not rule_id:
            raise RuntimeCommandRepairViolation("cmd.repair.counterexample_required")
        if rule_id in self._typed_repair_rule_ids:
            raise RuntimeCommandRepairViolation("cmd.repair.repeated_rule")

    def _record_typed_repair_state(
        self,
        tool_name: str,
        result: dict[str, Any],
    ) -> None:
        if tool_name not in {"synthesize_command", "repair_command"}:
            return
        if tool_name == "repair_command" and result.get("status") == "blocked":
            # A rejected repair has no new receipt by design.  It remains a
            # terminal safety outcome for this turn and must not be retried by
            # simply reusing the prior green preview.
            self._typed_repair_blocked = True
            return
        receipt = result.get("receipt")
        task_sha256 = str(result.get("task_spec_sha256") or "")
        if not isinstance(receipt, dict) or not task_sha256:
            return
        receipt_sha256 = str(receipt.get("receipt_sha256") or "")
        if not receipt_sha256:
            return
        if tool_name == "synthesize_command":
            self._typed_repair_task_sha256 = task_sha256
            self._typed_repair_receipt_sha256 = receipt_sha256
            self._typed_repair_attempt = 0
            self._typed_repair_rule_ids = set(_rule_ids(result))
            self._typed_repair_blocked = False
            return
        repair = result.get("repair")
        if not isinstance(repair, dict):
            return
        attempt = repair.get("attempt")
        if not isinstance(attempt, int):
            return
        rule_id = str(repair.get("counterexample_rule_id") or "")
        if rule_id:
            self._typed_repair_rule_ids.add(rule_id)
        self._typed_repair_attempt = attempt
        self._typed_repair_receipt_sha256 = receipt_sha256


def _success_payload(
    request_id: str,
    tool_name: str,
    result: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "request_id": request_id,
        "tool": tool_name,
        "status": "ok",
        "rule_ids": list(_rule_ids(result)),
    }
    if isinstance(result, dict):
        payload["result_keys"] = sorted(str(key) for key in result)
        verdict = _result_verdict(result)
        if verdict:
            payload["verdict"] = verdict
        if isinstance(result.get("state_delta"), dict):
            payload["state_delta"] = result["state_delta"]
        if tool_name in {"synthesize_command", "repair_command"}:
            payload["typed_command_status"] = str(result.get("status") or "")
            typed_receipt = result.get("receipt")
            # A model must receive structured compiler evidence to repair a
            # proposal, so a rejected typed tool result is not raised as a
            # generic tool exception.  Still persist its non-green terminal
            # state: otherwise a rejected repair after a previous green
            # preview could be ignored by the completion gate.
            payload["typed_receipt_status"] = str(
                typed_receipt.get("status")
                if isinstance(typed_receipt, dict)
                else result.get("status") or ""
            )
    return payload


def _emit_state_delta(
    emitter: EventEmitter,
    tool_name: str,
    result: dict[str, Any],
) -> None:
    state_delta = result.get("state_delta")
    project = (
        state_delta.get("project") if isinstance(state_delta, dict) else None
    )
    if isinstance(project, dict) and project.get("selected"):
        emitter.emit(
            EventKind.PROJECT_SELECTED,
            {
                "name": str(project.get("project") or ""),
                "program": str(project.get("program") or ""),
                "path": str(project.get("path") or ""),
                "sha256": str(project.get("sha256") or ""),
            },
            idempotency_key=(
                f"project:{project.get('sha256') or project.get('path')}"
            ),
        )
    if tool_name in {
        "synthesize_command",
        "repair_command",
        "dry_run_input",
    }:
        command = str(result.get("command") or "").strip()
        cli_grounded = result.get("cli_grounded")
        typed_receipt = result.get("receipt")
        preview_is_green = (
            not isinstance(typed_receipt, dict)
            or result.get("status") == "previewed"
        )
        if command and cli_grounded is not False and preview_is_green:
            payload = {
                "command": command,
                "semantic_verdict": _nested_value(
                    result, "semantic", "verdict"
                ),
                "intent_verdict": _nested_value(
                    result, "intent", "verdict"
                ),
            }
            if isinstance(typed_receipt, dict):
                # Additive payload only: older reducers retain their command
                # replay behavior, while newer evidence consumers can bind a
                # preview to task/workflow/schema/project/artifact hashes.
                payload.update(
                    {
                        "workflow_id": str(result.get("workflow_id") or ""),
                        "task_spec_id": str(result.get("task_spec_id") or ""),
                        "task_spec_sha256": str(
                            result.get("task_spec_sha256") or ""
                        ),
                        "render_digest": str(result.get("render_digest") or ""),
                        "scientific_task": (
                            result.get("scientific_task")
                            if isinstance(result.get("scientific_task"), dict)
                            else {}
                        ),
                        "command_workflow_receipt": typed_receipt,
                    }
                )
            emitter.emit(
                EventKind.COMMAND_SYNTHESIZED,
                payload,
                idempotency_key=f"command:{hashlib.sha256(command.encode()).hexdigest()}",
            )
        if (
            tool_name in {"synthesize_command", "repair_command"}
            and result.get("status") == "needs_clarification"
        ):
            emitter.emit(
                EventKind.CLARIFICATION_REQUESTED,
                {"slots": list(result.get("missing_info") or [])},
            )


def _rule_ids(value: Any) -> tuple[str, ...]:
    found: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if key == "rule_id" and isinstance(child, str):
                    found.append(child)
                elif key in {"failed_rule_ids", "rule_ids"} and isinstance(
                    child, (list, tuple)
                ):
                    found.extend(str(item) for item in child)
                elif key in {
                    "semantic",
                    "intent",
                    "validation",
                    "error",
                    "receipt",
                    "counterexamples",
                    "scientific_preflight",
                    "scientific_preview",
                }:
                    visit(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                visit(child)

    visit(value)
    return tuple(dict.fromkeys(found))


def _nested_value(value: dict[str, Any], key: str, child: str) -> Any:
    nested = value.get(key)
    return nested.get(child) if isinstance(nested, dict) else None


def _result_verdict(result: dict[str, Any]) -> str:
    direct = str(result.get("verdict") or "").strip().lower()
    if direct:
        return direct
    validation = result.get("validation")
    if isinstance(validation, dict):
        return str(validation.get("verdict") or "").strip().lower()
    return ""


def _runtime_error_rule(error_type: str) -> str:
    return {
        "ToolExposureViolation": "runtime.tool.not_exposed",
        "RuntimeCommandRepairViolation": "runtime.command.repair_binding",
        "UnknownHandle": "runtime.handle.unknown",
        "ValidationError": "runtime.tool.schema_validation",
        "TimeoutError": "runtime.tool.timeout",
    }.get(str(error_type), "runtime.tool.execution_error")


__all__ = [
    "RuntimeCommandRepairViolation",
    "RuntimeLifecycle",
    "ToolExposureViolation",
]
