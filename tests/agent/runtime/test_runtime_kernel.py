from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from chemsmart.agent.harness.workflow_state import (
    current_workflow_state,
    hydrate_workflow_state,
    reset_workflow_state,
    workflow_state_scope,
)
from chemsmart.agent.runtime.contracts import (
    AgentAction,
    AgentDecision,
    ProviderRole,
    RuntimeV2Mode,
    TaskPhase,
)
from chemsmart.agent.runtime.event_store import (
    EventStoreCorruptionError,
    EventStoreIdempotencyConflictError,
    RuntimeEventStore,
)
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.runtime.lifecycle import (
    RuntimeCommandRepairViolation,
    ToolExposureViolation,
)
from chemsmart.agent.runtime.orchestrator import (
    RuntimeController,
    provider_role,
    route_initial_phase,
)
from chemsmart.agent.runtime.reducer import reduce_events
from chemsmart.agent.runtime.repair_policy import RepairAction, decide_repair
from chemsmart.agent.runtime.tool_catalog import (
    LEGACY_FRONTIER_HIDDEN_TOOL_NAMES,
    PhaseToolProfile,
    ToolCatalog,
    ToolSelection,
)
from chemsmart.agent.registry import ToolRegistry


@dataclass(frozen=True)
class _Tool:
    name: str

    def openai_tool_def(self):
        return {
            "type": "function",
            "function": {"name": self.name, "parameters": {"type": "object"}},
        }


class _Registry:
    def __init__(self):
        names = {
            "extract_project_protocol",
            "render_project_yaml",
            "validate_project_yaml",
            "critic_project_yaml",
            "write_project_yaml",
            "read_project_yaml",
            "update_project_yaml",
            "search_basis_sets",
            "inspect_command_schema",
            "inspect_command_workflow",
            "synthesize_command",
            "repair_command",
            "execute_chemsmart_command",
            "build_job",
            "dry_run_input",
        }
        self._tools = {name: _Tool(name) for name in names}

    def list_tools(self):
        return list(self._tools.values())

    def get_tool(self, name):
        return self._tools.get(name)

    def tool_defs_for_provider(self, provider_name, tools):
        del provider_name
        return [tool.openai_tool_def() for tool in tools]


def test_event_store_is_idempotent_and_replayable(tmp_path):
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    first = store.append(
        session_id="s1",
        turn_id="bootstrap",
        kind=EventKind.SESSION_STARTED,
        payload={"cwd": str(tmp_path)},
        idempotency_key="session-start",
    )
    duplicate = store.append(
        session_id="s1",
        turn_id="bootstrap",
        kind=EventKind.SESSION_STARTED,
        payload={"cwd": str(tmp_path)},
        idempotency_key="session-start",
    )
    with pytest.raises(EventStoreIdempotencyConflictError):
        store.append(
            session_id="s1",
            turn_id="bootstrap",
            kind=EventKind.SESSION_STARTED,
            payload={"cwd": "conflicting"},
            idempotency_key="session-start",
        )
    store.append(
        session_id="s1",
        turn_id="turn_0001",
        kind=EventKind.TURN_STARTED,
        payload={"request": "optimize", "phase": "synthesis"},
    )

    events = store.load()
    state = reduce_events(events)

    assert duplicate.event_id == first.event_id
    assert len(events) == 2
    assert state.session_id == "s1"
    assert state.phase is TaskPhase.SYNTHESIS


def test_event_store_detects_payload_tampering(tmp_path):
    path = tmp_path / "events.jsonl"
    store = RuntimeEventStore(path)
    store.append(
        session_id="s1",
        turn_id="bootstrap",
        kind=EventKind.SESSION_STARTED,
        payload={"cwd": str(tmp_path)},
    )
    row = json.loads(path.read_text())
    row["payload"]["cwd"] = "/tampered"
    path.write_text(json.dumps(row) + "\n")

    with pytest.raises(EventStoreCorruptionError, match="invalid hash"):
        store.load()


def test_replay_preserves_inflight_tool_after_crash(tmp_path):
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    store.append(
        session_id="s1",
        turn_id="bootstrap",
        kind=EventKind.SESSION_STARTED,
        payload={"cwd": str(tmp_path)},
    )
    store.append(
        session_id="s1",
        turn_id="turn_0001",
        kind=EventKind.TURN_STARTED,
        payload={"request": "optimize", "phase": "synthesis"},
    )
    store.append(
        session_id="s1",
        turn_id="turn_0001",
        kind=EventKind.TOOL_STARTED,
        payload={"request_id": "call-1", "tool": "synthesize_command"},
    )

    state = reduce_events(RuntimeEventStore(store.path).load())

    assert state.active_tool_calls == {"call-1": "synthesize_command"}


def test_durable_project_state_hydrates_session_scoped_compatibility_store(
    tmp_path,
):
    reset_workflow_state()
    with workflow_state_scope("session-1", cwd=tmp_path):
        hydrate_workflow_state(
            {
                "cwd": str(tmp_path),
                "project": {
                    "name": "co2",
                    "program": "gaussian",
                    "path": str(tmp_path / "co2.yaml"),
                    "sha256": "abc123",
                },
                "previous_command": "chemsmart run gaussian -p co2 ...",
            },
            cwd=tmp_path,
        )
        restored = current_workflow_state(tmp_path)

    assert restored.project is not None
    assert restored.project.name == "co2"
    assert restored.previous_command.startswith("chemsmart run gaussian")
    reset_workflow_state()


def test_durable_project_state_overrides_inherited_workspace_default(tmp_path):
    reset_workflow_state()
    with workflow_state_scope("default", cwd=tmp_path):
        hydrate_workflow_state(
            {
                "cwd": str(tmp_path),
                "project": {
                    "name": "workspace-default",
                    "program": "gaussian",
                    "path": str(tmp_path / "workspace-default.yaml"),
                },
            },
            cwd=tmp_path,
            overwrite=True,
        )

    with workflow_state_scope("resumed-session", cwd=tmp_path):
        restored = hydrate_workflow_state(
            {
                "cwd": str(tmp_path),
                "project": {
                    "name": "durable-project",
                    "program": "orca",
                    "path": str(tmp_path / "durable-project.yaml"),
                    "sha256": "durable-hash",
                },
            },
            cwd=tmp_path,
            overwrite=True,
        )

    assert restored.project is not None
    assert restored.project.name == "durable-project"
    assert restored.project.program == "orca"
    assert restored.project.sha256 == "durable-hash"
    reset_workflow_state()


def test_phase_catalog_limits_controller_and_local_tool_surfaces():
    catalog = ToolCatalog(_Registry())
    controller = catalog.select(
        phase=TaskPhase.PROJECT,
        provider_role=ProviderRole.CONTROLLER,
    )
    specialist = catalog.select(
        phase=TaskPhase.PROJECT,
        provider_role=ProviderRole.SYNTHESIS_SPECIALIST,
    )

    assert len(controller.direct) == 5
    assert "write_project_yaml" not in controller.direct
    assert "read_project_yaml" in controller.direct
    assert "critic_project_yaml" in controller.deferred
    assert specialist.direct == (
        "inspect_command_schema",
        "inspect_command_workflow",
        "synthesize_command",
        "repair_command",
    )
    assert "build_job" in controller.hidden


def test_active_runtime_hides_legacy_jobs_from_custom_tool_profile(tmp_path):
    profile = PhaseToolProfile(
        {
            TaskPhase.SYNTHESIS: (
                "synthesize_command",
                "build_job",
                "dry_run_input",
            )
        },
        specialist_tools=("build_job",),
    )
    controller = RuntimeController(
        session_dir=tmp_path,
        session_id="s1",
        registry=_Registry(),
        mode=RuntimeV2Mode.ACTIVE,
        tool_profile=profile,
    )

    controller.start_turn(
        request="Prepare a Gaussian optimization.",
        turn_index=1,
        provider_name="openai",
        cwd=str(tmp_path),
    )

    assert controller.selection is not None
    assert controller.selection.direct == ("synthesize_command",)
    assert {"build_job", "dry_run_input"} <= set(
        controller.selection.hidden
    )
    assert {"build_job", "dry_run_input"} <= (
        LEGACY_FRONTIER_HIDDEN_TOOL_NAMES
    )


def test_active_runtime_hides_raw_executor_even_in_execution_phase(tmp_path):
    profile = PhaseToolProfile(
        {
            TaskPhase.EXECUTION: (
                "synthesize_command",
                "execute_chemsmart_command",
            )
        }
    )
    controller = RuntimeController(
        session_dir=tmp_path,
        session_id="s1",
        registry=_Registry(),
        mode=RuntimeV2Mode.ACTIVE,
        tool_profile=profile,
    )

    controller.start_turn(
        request="Run an xTB calculation.",
        turn_index=1,
        provider_name="openai",
        cwd=str(tmp_path),
    )

    assert controller.selection is not None
    assert controller.selection.direct == ("synthesize_command",)
    assert "execute_chemsmart_command" in controller.selection.hidden
    assert "execute_chemsmart_command" in LEGACY_FRONTIER_HIDDEN_TOOL_NAMES


def test_active_typed_command_profile_requires_a_green_preview_receipt(tmp_path):
    registry = ToolRegistry.default(groups=["synthesis"])
    controller = RuntimeController(
        session_dir=tmp_path,
        session_id="s1",
        registry=registry,
        mode=RuntimeV2Mode.ACTIVE,
    )
    controller.selection = ToolSelection(
        phase=TaskPhase.SYNTHESIS,
        provider_role=ProviderRole.CONTROLLER,
        direct=("synthesize_command",),
        deferred=(),
        hidden=(),
    )
    controller.state = controller.state.model_copy(
        update={"phase": TaskPhase.SYNTHESIS, "completed_tool_receipts": []}
    )

    assert controller.completion_rule_ids() == (
        "runtime.command.preview_required",
    )

    controller.state = controller.state.model_copy(
        update={
            "completed_tool_receipts": [
                {
                    "tool": "synthesize_command",
                    "verdict": "",
                    "typed_command_status": "previewed",
                    "typed_receipt_status": "previewed",
                }
            ]
        }
    )

    assert controller.completion_rule_ids() == ()


def test_custom_profile_requires_its_designated_green_terminal_tool(tmp_path):
    registry = ToolRegistry.default(groups=["synthesis"])
    profile = PhaseToolProfile(
        {TaskPhase.SYNTHESIS: ("synthesize_command",)},
        required_completion_tools={
            TaskPhase.SYNTHESIS: ("synthesize_command",),
        },
        trusted_initial_phase=TaskPhase.SYNTHESIS,
    )
    controller = RuntimeController(
        session_dir=tmp_path,
        session_id="s1",
        registry=registry,
        mode=RuntimeV2Mode.ACTIVE,
        tool_profile=profile,
    )
    controller.selection = ToolSelection(
        phase=TaskPhase.SYNTHESIS,
        provider_role=ProviderRole.CONTROLLER,
        direct=("synthesize_command",),
        deferred=(),
        hidden=(),
    )
    controller.state = controller.state.model_copy(
        update={"phase": TaskPhase.SYNTHESIS, "completed_tool_receipts": []}
    )

    assert controller.completion_rule_ids() == (
        "runtime.tool.required.synthesize_command",
    )

    controller.state = controller.state.model_copy(
        update={
            "completed_tool_receipts": [
                {
                    "tool": "synthesize_command",
                    "verdict": "warn",
                    "typed_command_status": "",
                    "typed_receipt_status": "",
                }
            ]
        }
    )
    assert controller.completion_rule_ids() == (
        "runtime.tool.required_not_green.synthesize_command",
    )

    controller.start_turn(
        request="Inspect project-readiness before execution.",
        turn_index=1,
        provider_name="openai",
        cwd=str(tmp_path),
    )
    assert controller.selection is not None
    assert controller.selection.phase is TaskPhase.SYNTHESIS
    events = controller.store.load()
    turn_started = next(
        event for event in events if event.kind is EventKind.TURN_STARTED
    )
    assert turn_started.payload["phase_source"] == "trusted_profile"


def test_rejected_typed_repair_invalidates_prior_preview_for_this_turn(tmp_path):
    registry = ToolRegistry.default(groups=["synthesis"])
    controller = RuntimeController(
        session_dir=tmp_path,
        session_id="s1",
        registry=registry,
        mode=RuntimeV2Mode.ACTIVE,
    )
    controller.start_turn(
        request="Optimize water with xTB.",
        turn_index=1,
        provider_name="openai",
        cwd=str(tmp_path),
    )
    controller.selection = ToolSelection(
        phase=TaskPhase.SYNTHESIS,
        provider_role=ProviderRole.CONTROLLER,
        direct=("synthesize_command", "repair_command"),
        deferred=(),
        hidden=(),
    )
    controller.state = controller.state.model_copy(
        update={"phase": TaskPhase.SYNTHESIS, "completed_tool_receipts": []}
    )
    lifecycle = controller.lifecycle()
    task_digest = "a" * 64
    receipt_digest = "b" * 64
    lifecycle.after_tool(
        request_id="synth",
        tool_name="synthesize_command",
        result={
            "status": "previewed",
            "task_spec_sha256": task_digest,
            "receipt": {
                "status": "previewed",
                "receipt_sha256": receipt_digest,
            },
        },
    )
    repair_args = {
        "prior_task_spec_sha256": task_digest,
        "prior_receipt_sha256": receipt_digest,
        "repair_attempt": 1,
        "counterexample": {"rule_id": "cmd.test.counterexample"},
    }
    lifecycle.before_tool(
        request_id="repair-1",
        tool_name="repair_command",
        arguments=repair_args,
    )
    lifecycle.after_tool(
        request_id="repair-1",
        tool_name="repair_command",
        result={
            "ok": False,
            "status": "blocked",
            "counterexamples": [
                {"rule_id": "cmd.repair.scientific_binding_changed"}
            ],
        },
    )

    assert controller.completion_rule_ids() == (
        "runtime.command.preview_not_green",
    )
    with pytest.raises(RuntimeCommandRepairViolation, match="prior_repair_blocked"):
        lifecycle.before_tool(
            request_id="repair-2",
            tool_name="repair_command",
            arguments=repair_args,
        )


def test_router_preserves_local_specialist_and_write_boundary():
    assert provider_role("local-mlx") is ProviderRole.SYNTHESIS_SPECIALIST
    assert (
        route_initial_phase(
            "Write the validated project YAML now.",
            role=ProviderRole.CONTROLLER,
        )
        is TaskPhase.PROJECT_WRITE
    )
    assert (
        route_initial_phase(
            "Write a new Gaussian project YAML with B3LYP/def2-SVP.",
            role=ProviderRole.CONTROLLER,
        )
        is TaskPhase.PROJECT
    )
    assert (
        route_initial_phase(
            "Create a project YAML from this method section.",
            role=ProviderRole.CONTROLLER,
        )
        is TaskPhase.PROJECT
    )
    assert (
        route_initial_phase(
            "Read project YAML co2 and explain the settings.",
            role=ProviderRole.CONTROLLER,
        )
        is TaskPhase.PROJECT_READ
    )
    assert (
        route_initial_phase(
            "Read the workspace project YAML named co2 and validate it.",
            role=ProviderRole.CONTROLLER,
        )
        is TaskPhase.PROJECT_READ
    )
    assert (
        route_initial_phase(
            "Create a project YAML.",
            role=ProviderRole.SYNTHESIS_SPECIALIST,
        )
        is TaskPhase.SYNTHESIS
    )


@pytest.mark.parametrize(
    "user_input",
    [
        "Commit both molecule previews.",
        "Commit both previews.",
        "Discard preview-1.",
        "Accept the final geometry.",
        "Reject the final geometry.",
        "분자 preview를 commit하세요.",
        "최종 구조를 reject하세요.",
    ],
)
def test_router_maps_studio_revision_decisions_to_project_write(user_input):
    assert (
        route_initial_phase(user_input, role=ProviderRole.CONTROLLER)
        is TaskPhase.PROJECT_WRITE
    )


@pytest.mark.parametrize(
    "user_input",
    [
        "Inspect the current Studio context.",
        "Show the Studio context.",
        "스튜디오 컨텍스트를 확인하세요.",
    ],
)
def test_router_maps_studio_context_reads_to_route(user_input):
    assert (
        route_initial_phase(user_input, role=ProviderRole.CONTROLLER)
        is TaskPhase.ROUTE
    )


@pytest.mark.parametrize(
    "user_input",
    [
        "Start the validated controlled plan.",
        "Start the prepared optimization.",
        "Cancel the optimization.",
        "준비된 최적화를 시작하세요.",
        "최적화 실행을 취소하세요.",
    ],
)
def test_router_maps_studio_run_controls_to_execution(user_input):
    assert (
        route_initial_phase(user_input, role=ProviderRole.CONTROLLER)
        is TaskPhase.EXECUTION
    )


def test_router_uses_structured_xtb_execution_intent() -> None:
    assert (
        route_initial_phase(
            "Run an xTB single-point calculation on water.xyz.",
            role=ProviderRole.CONTROLLER,
        )
        is TaskPhase.EXECUTION
    )
    assert (
        route_initial_phase(
            "현재 water.xyz에 xTB를 실행해",
            role=ProviderRole.CONTROLLER,
        )
        is TaskPhase.EXECUTION
    )


def test_xtb_execution_surface_withholds_project_yaml() -> None:
    catalog = ToolCatalog(_Registry())

    selection = catalog.select(
        phase=TaskPhase.EXECUTION,
        provider_role=ProviderRole.CONTROLLER,
        program="xtb",
    )

    assert "read_project_yaml" not in selection.direct
    assert selection.program == "xtb"


def test_active_lifecycle_rejects_unexposed_internal_tool(tmp_path):
    controller = RuntimeController(
        session_dir=tmp_path,
        session_id="s1",
        registry=_Registry(),
        mode=RuntimeV2Mode.ACTIVE,
    )
    controller.start_turn(
        request="Optimize water with Gaussian.",
        turn_index=1,
        provider_name="openai",
        cwd=str(tmp_path),
    )

    with pytest.raises(ToolExposureViolation, match="not exposed"):
        controller.lifecycle().before_tool(
            request_id="call-1",
            tool_name="build_job",
            arguments={},
        )


def test_shadow_lifecycle_records_violation_without_blocking(tmp_path):
    controller = RuntimeController(
        session_dir=tmp_path,
        session_id="s1",
        registry=_Registry(),
        mode=RuntimeV2Mode.SHADOW,
    )
    controller.start_turn(
        request="Optimize water with Gaussian.",
        turn_index=1,
        provider_name="openai",
        cwd=str(tmp_path),
    )

    controller.lifecycle().before_tool(
        request_id="call-1",
        tool_name="build_job",
        arguments={},
    )

    assert controller.state.shadow_violations == ["runtime.tool.not_exposed"]
    assert controller.state.active_tool_calls == {"call-1": "build_job"}


def test_lifecycle_records_command_project_and_artifact_receipts(tmp_path):
    project = tmp_path / "demo.yaml"
    project.write_text("gas:\n  functional: b3lyp\n")
    generated = tmp_path / "water.com"
    generated.write_text("# b3lyp/6-31g(d) opt\n")
    controller = RuntimeController(
        session_dir=tmp_path / "session",
        session_id="s1",
        registry=_Registry(),
        mode=RuntimeV2Mode.ACTIVE,
    )
    controller.start_turn(
        request="Prepare a Gaussian optimization.",
        turn_index=1,
        provider_name="openai",
        cwd=str(tmp_path),
    )
    lifecycle = controller.lifecycle()
    lifecycle.before_tool(
        request_id="call-1",
        tool_name="synthesize_command",
        arguments={"request": "optimize"},
    )
    lifecycle.after_tool(
        request_id="call-1",
        tool_name="synthesize_command",
        result={
            "command": "chemsmart run gaussian -p demo -f water.xyz -c 0 -m 1 opt",
            "semantic": {"verdict": "ok"},
            "generated_input": str(generated),
            "state_delta": {
                "project": {
                    "selected": True,
                    "project": "demo",
                    "program": "gaussian",
                    "path": str(project),
                    "sha256": "abc123",
                }
            },
        },
    )
    controller.complete()

    replayed = RuntimeController(
        session_dir=tmp_path / "session",
        session_id="s1",
        registry=_Registry(),
        mode=RuntimeV2Mode.ACTIVE,
    )

    assert replayed.state.previous_command.startswith("chemsmart run gaussian")
    assert replayed.state.active_project is not None
    assert replayed.state.active_project.name == "demo"
    assert replayed.state.artifacts[0].sha256
    assert replayed.state.phase is TaskPhase.COMPLETE


def test_lifecycle_records_cli_grounded_direct_dry_run_command(tmp_path):
    command = (
        "chemsmart run gaussian -p water_demo -f h2o.xyz -c 0 -m 1 "
        "scan --coordinates '[[1,2]]' --num-steps 10 --step-size 0.05"
    )
    controller = RuntimeController(
        session_dir=tmp_path / "session",
        session_id="s1",
        registry=_Registry(),
        mode=RuntimeV2Mode.SHADOW,
    )
    controller.start_turn(
        request="Prepare a Gaussian scan.",
        turn_index=1,
        provider_name="openai",
        cwd=str(tmp_path),
    )
    lifecycle = controller.lifecycle()
    lifecycle.before_tool(
        request_id="call-1",
        tool_name="dry_run_input",
        arguments={"job": "job_1"},
    )
    lifecycle.after_tool(
        request_id="call-1",
        tool_name="dry_run_input",
        result={"command": command, "cli_grounded": True},
    )

    assert controller.state.previous_command == command


@pytest.mark.parametrize(
    ("rules", "repeat", "action"),
    [
        (["cmd.runtime.project_not_found"], 1, RepairAction.ASK_USER),
        (["cmd.runtime.dependency_missing"], 1, RepairAction.TERMINATE),
        (["cmd.semantic.option_order"], 1, RepairAction.DETERMINISTIC_REPAIR),
        (["input.gaussian.tddft.root"], 1, RepairAction.REVIEW),
        (["cmd.semantic.option_order"], 2, RepairAction.TERMINATE),
    ],
)
def test_repair_policy_respects_scientific_ownership(rules, repeat, action):
    assert decide_repair(rules, repeated_count=repeat).action is action


def test_controller_rejects_invalid_phase_transition(tmp_path):
    controller = RuntimeController(
        session_dir=tmp_path,
        session_id="s1",
        registry=_Registry(),
        mode=RuntimeV2Mode.ACTIVE,
    )
    controller.start_turn(
        request="Optimize water.",
        turn_index=1,
        provider_name="openai",
        cwd=str(tmp_path),
    )
    decision = AgentDecision(
        action=AgentAction.BUILD_PROJECT,
        phase=TaskPhase.PROJECT,
        summary="Switch to project authoring.",
    )

    with pytest.raises(ValueError, match="invalid runtime transition"):
        controller.validate_decision(decision)


def test_project_authoring_completion_requires_validated_render(tmp_path):
    controller = RuntimeController(
        session_dir=tmp_path,
        session_id="s1",
        registry=_Registry(),
        mode=RuntimeV2Mode.ACTIVE,
    )
    controller.start_turn(
        request="Create a Gaussian project YAML for water.",
        turn_index=1,
        provider_name="openai",
        cwd=str(tmp_path),
    )

    assert controller.complete() is False
    assert controller.state.phase is TaskPhase.BLOCKED
    assert controller.state.blocked_reason == "runtime.project.render_required"


def test_project_authoring_completion_accepts_validated_render(tmp_path):
    controller = RuntimeController(
        session_dir=tmp_path,
        session_id="s1",
        registry=_Registry(),
        mode=RuntimeV2Mode.ACTIVE,
    )
    controller.start_turn(
        request="Create a Gaussian project YAML for water.",
        turn_index=1,
        provider_name="openai",
        cwd=str(tmp_path),
    )
    lifecycle = controller.lifecycle()
    lifecycle.before_tool(
        request_id="call-1",
        tool_name="render_project_yaml",
        arguments={"protocol": {}},
    )
    lifecycle.after_tool(
        request_id="call-1",
        tool_name="render_project_yaml",
        result={
            "ok": True,
            "yaml_text": "gas: {}",
            "validation": {"verdict": "ok"},
        },
    )

    assert controller.complete() is True
    assert controller.state.phase is TaskPhase.COMPLETE
    assert "no workspace file was written" in controller.completion_notice()
    assert "/write-project" in controller.completion_notice()
