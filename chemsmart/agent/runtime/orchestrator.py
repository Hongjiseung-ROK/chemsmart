"""Provider-independent runtime controller and state-transition authority."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from chemsmart.agent.harness.intent import IntentSpec
from chemsmart.agent.harness.workflow_state import WorkflowState
from chemsmart.agent.runtime.contracts import (
    AgentDecision,
    ExecutionMode,
    ProviderRole,
    RuntimeV2Mode,
    TaskEnvelope,
    TaskPhase,
    WorkspaceRef,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind, RuntimeEvent
from chemsmart.agent.runtime.lifecycle import RuntimeLifecycle
from chemsmart.agent.runtime.reducer import apply_event, reduce_events
from chemsmart.agent.runtime.scientific_contracts import (
    ClaimRecord,
    ClaimStatus,
    ClaimType,
    PhaseCloseReceipt,
    ResourceBudget,
    ScientificTaskSpec,
    TaskGraph,
    ValidationStatus,
)
from chemsmart.agent.runtime.tool_catalog import (
    PhaseToolProfile,
    ToolCatalog,
    ToolSelection,
)

_LOCAL_PROVIDER_MARKERS = ("local", "mlx", "vllm")
_SAFE_PREFLIGHT_MODE_RE = re.compile(
    r"\b(?:dry|fake)[-\s]?run\b"
    r"|\bpre[-\s]?flight\b"
    r"|(?:^|\s)--(?:test|fake)(?:\s|=|$)",
    re.IGNORECASE,
)
_TRANSITIONS: dict[TaskPhase, frozenset[TaskPhase]] = {
    TaskPhase.ROUTE: frozenset(
        {
            TaskPhase.PROJECT,
            TaskPhase.PROJECT_READ,
            TaskPhase.PROJECT_WRITE,
            TaskPhase.SYNTHESIS,
            TaskPhase.REPAIR,
            TaskPhase.EXECUTION,
            TaskPhase.DIAGNOSTICS,
            TaskPhase.COMPLETE,
            TaskPhase.WAITING_USER,
        }
    ),
    TaskPhase.PROJECT: frozenset(
        {
            TaskPhase.PROJECT_WRITE,
            TaskPhase.SYNTHESIS,
            TaskPhase.COMPLETE,
            TaskPhase.WAITING_USER,
        }
    ),
    TaskPhase.PROJECT_READ: frozenset(
        {
            TaskPhase.PROJECT_WRITE,
            TaskPhase.SYNTHESIS,
            TaskPhase.COMPLETE,
            TaskPhase.WAITING_USER,
        }
    ),
    TaskPhase.PROJECT_WRITE: frozenset(
        {TaskPhase.SYNTHESIS, TaskPhase.COMPLETE, TaskPhase.WAITING_USER}
    ),
    TaskPhase.SYNTHESIS: frozenset(
        {
            TaskPhase.VALIDATION,
            TaskPhase.REPAIR,
            TaskPhase.EXECUTION,
            TaskPhase.COMPLETE,
            TaskPhase.WAITING_USER,
        }
    ),
    TaskPhase.VALIDATION: frozenset(
        {
            TaskPhase.REPAIR,
            TaskPhase.EXECUTION,
            TaskPhase.COMPLETE,
            TaskPhase.WAITING_USER,
        }
    ),
    TaskPhase.REPAIR: frozenset(
        {
            TaskPhase.VALIDATION,
            TaskPhase.EXECUTION,
            TaskPhase.COMPLETE,
            TaskPhase.WAITING_USER,
        }
    ),
    TaskPhase.EXECUTION: frozenset(
        {
            TaskPhase.COMPLETE,
            TaskPhase.REPAIR,
            TaskPhase.DIAGNOSTICS,
            TaskPhase.WAITING_USER,
        }
    ),
    TaskPhase.DIAGNOSTICS: frozenset(
        {TaskPhase.COMPLETE, TaskPhase.REPAIR, TaskPhase.WAITING_USER}
    ),
    TaskPhase.WAITING_USER: frozenset(
        {
            TaskPhase.PROJECT,
            TaskPhase.PROJECT_READ,
            TaskPhase.SYNTHESIS,
            TaskPhase.REPAIR,
            TaskPhase.EXECUTION,
            TaskPhase.DIAGNOSTICS,
        }
    ),
    TaskPhase.COMPLETE: frozenset({TaskPhase.ROUTE}),
    TaskPhase.BLOCKED: frozenset({TaskPhase.ROUTE}),
}


class RuntimeController:
    def __init__(
        self,
        *,
        session_dir: str | Path,
        session_id: str,
        registry: Any,
        mode: RuntimeV2Mode,
        tool_profile: PhaseToolProfile | None = None,
    ) -> None:
        self.session_dir = Path(session_dir)
        self.session_id = session_id
        self.registry = registry
        self.mode = mode
        self.store = RuntimeEventStore(
            self.session_dir / "runtime_events.jsonl"
        )
        events = self.store.load()
        self.state = reduce_events(events)
        self.turn_id = self.state.turn_id
        self.catalog = ToolCatalog(registry, profile=tool_profile)
        self.selection: ToolSelection | None = None

    def bind_tool_profile(self, tool_profile: PhaseToolProfile) -> None:
        """Replace transient tool exposure without resetting durable state."""

        self.catalog = ToolCatalog(self.registry, profile=tool_profile)
        self.selection = None

    def ensure_session(self, *, cwd: str) -> None:
        if self.state.session_id:
            return
        self.turn_id = "bootstrap"
        self.emit(
            EventKind.SESSION_STARTED,
            {"cwd": str(Path(cwd).resolve()), "runtime_mode": self.mode.value},
            idempotency_key="session-started",
        )

    def start_turn(
        self,
        *,
        request: str,
        turn_index: int,
        provider_name: str,
        cwd: str,
        workflow_state: WorkflowState | None = None,
        scientific_task: ScientificTaskSpec | None = None,
        scientific_task_graph: TaskGraph | None = None,
        scientific_resource_budget: ResourceBudget | None = None,
    ) -> TaskEnvelope:
        self.ensure_session(cwd=cwd)
        role = provider_role(provider_name)
        intent = IntentSpec.from_request(request)
        phase = route_initial_phase(request, role=role, intent=intent)
        self.turn_id = f"turn_{turn_index:04d}"
        turn_payload: dict[str, Any] = {
            "request": request,
            "phase": phase.value,
            "provider_role": role.value,
        }
        scientific_records: dict[str, Any] = {}
        if scientific_task is not None:
            scientific_records["task_spec"] = scientific_task.model_dump(
                mode="json"
            )
        if scientific_task_graph is not None:
            scientific_records["task_graph"] = scientific_task_graph.model_dump(
                mode="json"
            )
        if scientific_resource_budget is not None:
            scientific_records["resource_budget"] = (
                scientific_resource_budget.model_dump(mode="json")
            )
        if scientific_records:
            turn_payload["scientific_v1"] = {
                "version": 1,
                **scientific_records,
            }
        self.emit(
            EventKind.TURN_STARTED,
            turn_payload,
            idempotency_key=f"turn-start:{self.turn_id}",
        )
        self.selection = self.catalog.select(
            phase=phase,
            provider_role=role,
            program=intent.program,
        )
        self.emit(
            EventKind.EXPOSURE_PLANNED,
            {
                "phase": phase.value,
                "tools": list(self.selection.direct),
                "deferred_count": len(self.selection.deferred),
                "hidden_count": len(self.selection.hidden),
            },
            idempotency_key=f"exposure:{self.turn_id}:{phase.value}",
        )
        project = (
            _workspace_ref(workflow_state.project) if workflow_state else None
        )
        server = (
            _workspace_ref(workflow_state.server) if workflow_state else None
        )
        return TaskEnvelope(
            task_id=f"task_{uuid4().hex[:12]}",
            session_id=self.session_id,
            turn_id=self.turn_id,
            request=request,
            cwd=str(Path(cwd).resolve()),
            provider_role=role,
            phase=phase,
            execution_mode=execution_mode_from_request(request),
            project=project,
            server=server,
            previous_command=(
                workflow_state.previous_command if workflow_state else ""
            ),
            unresolved_slots=(
                workflow_state.unresolved_slots if workflow_state else ()
            ),
        )

    def lifecycle(self) -> RuntimeLifecycle:
        if self.selection is None:
            raise RuntimeError("start_turn must be called before lifecycle")
        return RuntimeLifecycle(
            emitter=self,
            selection=self.selection,
            mode=self.mode,
        )

    def tool_defs(self, provider_name: str) -> list[dict[str, Any]]:
        if self.selection is None:
            raise RuntimeError("start_turn must be called before tool_defs")
        return self.catalog.provider_tool_defs(provider_name, self.selection)

    def validate_decision(self, decision: AgentDecision) -> None:
        current = self.state.phase
        if decision.phase == current:
            return
        if decision.phase not in _TRANSITIONS.get(current, frozenset()):
            raise ValueError(
                f"invalid runtime transition {current.value} -> {decision.phase.value}"
            )

    def complete(
        self,
        *,
        status: str = "ok",
        phase_close: PhaseCloseReceipt | None = None,
        claim: ClaimRecord | None = None,
    ) -> bool:
        rule_ids = self.completion_rule_ids(
            phase_close=phase_close,
            claim=claim,
        )
        if rule_ids:
            self.block(reason=rule_ids[0], rule_ids=rule_ids)
            return False
        payload: dict[str, Any] = {"status": status}
        scientific_records: dict[str, Any] = {}
        if claim is not None:
            scientific_records["claim"] = claim.model_dump(mode="json")
        if phase_close is not None:
            scientific_records["phase_close"] = phase_close.model_dump(
                mode="json"
            )
        if scientific_records:
            payload["scientific_v1"] = {
                "version": 1,
                **scientific_records,
            }
        self.emit(
            EventKind.TURN_COMPLETED,
            payload,
            idempotency_key=f"turn-complete:{self.turn_id}",
        )
        return True

    def completion_rule_ids(
        self,
        *,
        phase_close: PhaseCloseReceipt | None = None,
        claim: ClaimRecord | None = None,
    ) -> tuple[str, ...]:
        phase = (
            self.selection.phase
            if self.selection is not None
            else self.state.phase
        )
        receipts = self.state.completed_tool_receipts
        rule_ids: list[str] = []
        if phase is TaskPhase.PROJECT and _project_authoring_requested(
            self.state.request
        ):
            rendered = [
                item
                for item in receipts
                if item.get("tool") == "render_project_yaml"
            ]
            if not rendered:
                rule_ids.append("runtime.project.render_required")
            elif rendered[-1].get("verdict") not in {"ok", "warn"}:
                rule_ids.append("runtime.project.validation_required")
        if phase is TaskPhase.PROJECT_READ:
            reads = [
                item
                for item in receipts
                if item.get("tool") == "read_project_yaml"
            ]
            if not reads:
                rule_ids.append("runtime.project.read_required")
            elif reads[-1].get("verdict") == "reject":
                rule_ids.append("runtime.project.read_invalid")
        if phase is TaskPhase.PROJECT_WRITE and not any(
            item.get("tool") in {"write_project_yaml", "update_project_yaml"}
            for item in receipts
        ):
            rule_ids.append("runtime.project.write_required")
        if phase is TaskPhase.DIAGNOSTICS and not any(
            item.get("tool") == "inspect_calculation" for item in receipts
        ):
            rule_ids.append("runtime.calculation.inspection_required")
        rule_ids.extend(
            self.scientific_completion_rule_ids(
                phase_close=phase_close,
                claim=claim,
            )
        )
        return tuple(rule_ids)

    def scientific_completion_rule_ids(
        self,
        *,
        phase_close: PhaseCloseReceipt | None = None,
        claim: ClaimRecord | None = None,
    ) -> tuple[str, ...]:
        """Apply scientific completion gates only to an explicit opt-in task."""

        spec = self.state.scientific_task_spec
        if spec is None:
            return ()
        rule_ids: list[str] = []
        if spec.unresolved_facts:
            rule_ids.append("runtime.science.spec_unresolved")
        required_evidence_ids = {
            requirement.requirement_id
            for requirement in spec.expected_evidence
            if requirement.required
        }
        if required_evidence_ids - set(self.state.evidence_records):
            rule_ids.append("runtime.science.evidence_required")
        validation_statuses = {
            receipt.status for receipt in self.state.validation_receipts.values()
        }
        if not validation_statuses:
            rule_ids.append("runtime.science.validation_required")
        elif ValidationStatus.FAIL in validation_statuses:
            rule_ids.append("runtime.science.validation_failed")
        elif ValidationStatus.UNKNOWN in validation_statuses:
            rule_ids.append("runtime.science.validation_unresolved")
        if self.state.scientific_resource_budget is not None and any(
            exhaustion.budget_id == self.state.scientific_resource_budget.budget_id
            for exhaustion in self.state.budget_exhaustions.values()
        ):
            rule_ids.append("runtime.science.budget_exhausted")
        if any(
            (
                request := self.state.approval_requests.get(
                    invalidation.approval_id
                )
            ) is not None
            and request.task_spec_id == spec.task_spec_id
            for invalidation in self.state.approval_invalidations
        ):
            rule_ids.append("runtime.science.approval_invalidated")

        claims = list(self.state.claim_records.values())
        if claim is not None:
            claims.append(claim)
        known_evidence_ids = set(self.state.evidence_records)
        known_validation_ids = set(self.state.validation_receipts)
        for candidate in claims:
            if set(candidate.evidence_ids) - known_evidence_ids or set(
                candidate.validation_receipt_ids
            ) - known_validation_ids:
                rule_ids.append("runtime.science.claim_evidence_unresolved")
            if (
                candidate.claim_type is ClaimType.COMPUTED_RESULT
                and candidate.status is ClaimStatus.SUPPORTED
            ):
                validations = [
                    self.state.validation_receipts[receipt_id]
                    for receipt_id in candidate.validation_receipt_ids
                    if receipt_id in self.state.validation_receipts
                ]
                if not validations or any(
                    receipt.status is not ValidationStatus.PASS
                    for receipt in validations
                ):
                    rule_ids.append(
                        "runtime.science.claim_validation_not_green"
                    )

        if phase_close is None:
            rule_ids.append("runtime.science.phase_close_required")
        else:
            if phase_close.outcome != "passed" or phase_close.gate_status != "green":
                rule_ids.append("runtime.science.phase_close_not_green")
            known_claim_ids = {record.claim_id for record in claims}
            if set(phase_close.claim_ids) - known_claim_ids:
                rule_ids.append("runtime.science.phase_close_claim_unresolved")
        return tuple(dict.fromkeys(rule_ids))

    def completion_notice(self) -> str:
        phase = (
            self.selection.phase
            if self.selection is not None
            else self.state.phase
        )
        if (
            phase is TaskPhase.PROJECT
            and _project_authoring_requested(self.state.request)
            and not self.completion_rule_ids()
        ):
            return (
                "The project YAML candidate was validated, but no workspace "
                "file was written. Use /write-project to review and approve "
                "the write explicitly."
            )
        return ""

    def block(self, *, reason: str, rule_ids: tuple[str, ...] = ()) -> None:
        self.emit(
            EventKind.TURN_BLOCKED,
            {"reason": reason, "rule_ids": list(rule_ids)},
            idempotency_key=f"turn-blocked:{self.turn_id}:{reason}",
        )

    def emit(
        self,
        kind: EventKind,
        payload: dict[str, Any],
        *,
        idempotency_key: str = "",
    ) -> RuntimeEvent:
        event = self.store.append(
            session_id=self.session_id,
            turn_id=self.turn_id or "bootstrap",
            kind=kind,
            payload=payload,
            idempotency_key=(
                f"{self.turn_id or 'bootstrap'}:{idempotency_key}"
                if idempotency_key
                else ""
            ),
        )
        if event.sequence > self.state.latest_sequence:
            self.state = apply_event(self.state, event)
            self.store.write_snapshot(
                self.state.model_dump(mode="json"),
                self.session_dir / "runtime_state.json",
            )
        return event


def provider_role(provider_name: str) -> ProviderRole:
    normalized = str(provider_name or "").strip().lower()
    if any(marker in normalized for marker in _LOCAL_PROVIDER_MARKERS):
        return ProviderRole.SYNTHESIS_SPECIALIST
    return ProviderRole.CONTROLLER


def route_initial_phase(
    request: str,
    *,
    role: ProviderRole,
    intent: IntentSpec | None = None,
) -> TaskPhase:
    if role is ProviderRole.SYNTHESIS_SPECIALIST:
        return TaskPhase.SYNTHESIS
    text = str(request or "").lower()
    intent = intent or IntentSpec.from_request(request)
    if _is_studio_project_write(text):
        return TaskPhase.PROJECT_WRITE
    execution_mode = execution_mode_from_request(request, intent=intent)
    if (
        intent.program == "xtb"
        and execution_mode is ExecutionMode.TEST_FAKE
    ):
        return TaskPhase.SYNTHESIS
    if _is_studio_execution(text):
        return TaskPhase.EXECUTION
    if _is_direct_project_write(text):
        return TaskPhase.PROJECT_WRITE
    if _is_studio_context_read(text):
        return TaskPhase.ROUTE
    if (
        _matches(
            text,
            r"(?:read|show|inspect|check).{0,48}(?:project|ya?ml)",
        )
        or _matches(
            text,
            r"(?:project|ya?ml).{0,48}(?:read|show|inspect|check)",
        )
        or any(
            marker in text
            for marker in (
                "read project",
                "show project",
                "inspect project",
                "check project yaml",
                "yaml 조회",
                "yaml 확인",
                "프로젝트 읽",
                "查看项目",
                "读取项目",
            )
        )
    ):
        return TaskPhase.PROJECT_READ
    if any(
        marker in text
        for marker in (
            "diagnose the result",
            "inspect the result",
            "analyze the result",
            "check the calculation",
            "calculation result",
            "output result",
            "결과를 진단",
            "계산 결과",
            "결과 분석",
            "출력 파일 확인",
            "诊断结果",
            "分析计算结果",
        )
    ):
        return TaskPhase.DIAGNOSTICS
    if any(
        marker in text
        for marker in (
            "yaml",
            "project settings",
            "project configuration",
            "프로젝트",
            "项目配置",
        )
    ):
        return TaskPhase.PROJECT
    if any(
        marker in text
        for marker in (
            "repair",
            "fix this command",
            "failed command",
            "고쳐",
            "복구",
            "修复命令",
        )
    ):
        return TaskPhase.REPAIR
    if intent.action in {"run", "sub"}:
        return TaskPhase.EXECUTION
    return TaskPhase.SYNTHESIS


def execution_mode_from_request(
    request: str,
    *,
    intent: IntentSpec | None = None,
) -> ExecutionMode:
    text = str(request or "").lower()
    intent = intent or IntentSpec.from_request(request)
    if _SAFE_PREFLIGHT_MODE_RE.search(text):
        return ExecutionMode.TEST_FAKE
    if intent.action == "sub":
        return ExecutionMode.HPC
    if intent.action == "run":
        return ExecutionMode.LOCAL
    return ExecutionMode.NONE


def _workspace_ref(value: Any) -> WorkspaceRef | None:
    if value is None:
        return None
    return WorkspaceRef(
        name=str(value.name),
        program=str(value.program),
        path=str(value.path),
        sha256=str(value.sha256),
    )


def _matches(value: str, pattern: str) -> bool:
    return re.search(pattern, value, flags=re.IGNORECASE) is not None


def _is_direct_project_write(text: str) -> bool:
    updates_existing = (
        _matches(
            text,
            r"(?:overwrite|update|patch).{0,32}(?:ya?ml|project)",
        )
        or _matches(
            text,
            r"(?:yaml|project).{0,32}(?:overwrite|update|patch)",
        )
        or any(
            marker in text
            for marker in ("프로젝트 수정", "更新项目", "覆盖项目")
        )
    )
    if updates_existing:
        return True

    writes_candidate = (
        _matches(
            text,
            r"(?:write|save).{0,48}(?:ya?ml|project)",
        )
        or _matches(
            text,
            r"(?:yaml|project).{0,48}(?:write|save)",
        )
        or any(marker in text for marker in ("yaml 저장", "写入", "保存"))
    )
    candidate_exists = any(
        marker in text
        for marker in (
            "validated",
            "candidate",
            "latest yaml",
            "already rendered",
            "검증된",
            "후보 yaml",
            "그대로 저장",
            "已验证",
            "候选",
        )
    )
    return writes_candidate and candidate_exists


def _is_studio_project_write(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "commit preview",
            "commit the preview",
            "commit both molecule previews",
            "commit both previews",
            "discard preview",
            "discard the preview",
            "accept final geometry",
            "accept the final geometry",
            "reject final geometry",
            "reject the final geometry",
            "preview를 commit",
            "preview를 discard",
            "최종 구조를 accept",
            "최종 구조를 reject",
            "최종 구조 수락",
            "최종 구조 거절",
        )
    )


def _is_studio_context_read(text: str) -> bool:
    return (
        _matches(
            text,
            r"(?:read|show|inspect|check|get).{0,48}studio context",
        )
        or _matches(
            text,
            r"studio context.{0,48}(?:read|show|inspect|check|get)",
        )
        or any(
            marker in text
            for marker in (
                "studio context 조회",
                "studio context 확인",
                "스튜디오 컨텍스트 조회",
                "스튜디오 컨텍스트 확인",
                "스튜디오 컨텍스트를 확인",
                "查看 studio 上下文",
                "读取 studio 上下文",
            )
        )
    )


def _is_studio_execution(text: str) -> bool:
    return _matches(
        text,
        r"(?:start|cancel).{0,48}(?:prepared|validated|controlled)?"
        r".{0,32}(?:plan|optimization)",
    ) or any(
        marker in text
        for marker in (
            "start optimization",
            "start the optimization",
            "cancel optimization",
            "cancel the optimization",
            "최적화를 시작",
            "최적화 시작",
            "최적화 실행을 취소",
            "최적화를 취소",
        )
    )


def _project_authoring_requested(request: str) -> bool:
    text = str(request or "").lower()
    return (
        _matches(
            text,
            r"(?:create|build|make|render|set up|write).{0,48}(?:ya?ml|project)",
        )
        or _matches(
            text,
            r"(?:yaml|project).{0,48}(?:create|build|make|render|set up|write)",
        )
        or any(
            marker in text
            for marker in (
                "프로젝트 생성",
                "yaml 생성",
                "yaml 작성",
                "创建项目",
                "生成 yaml",
            )
        )
    )


__all__ = [
    "RuntimeController",
    "execution_mode_from_request",
    "provider_role",
    "route_initial_phase",
]
