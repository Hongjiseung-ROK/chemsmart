"""Phase-scoped tool exposure independent of model provider syntax."""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, ConfigDict

from chemsmart.agent.harness.engine_capabilities import (
    requires_project_configuration,
)
from chemsmart.agent.runtime.contracts import ProviderRole, TaskPhase


#: Most direct tools a single runtime phase may offer the model at once.
#:
#: The cap exists because routing reliability falls off as the menu grows — a small
#: local model asked to choose among many similar tools picks the wrong one. It is a
#: guardrail on menu size, not a statement that five is the right number for every
#: embedding of the harness.
#:
#: Raised from 5 to 10 so a host can expose the execution and diagnostics tools
#: alongside the per-phase essentials without displacing them. Per-phase menus are
#: still curated deliberately; nothing should fill this budget just because it is
#: available.
MAX_DIRECT_TOOLS_PER_PHASE = 10


# Retain these in ``ToolRegistry`` for compatibility fixtures and the explicit
# ``harness_jobs`` profile, but never let an active Frontier Runtime V2 turn
# advertise or execute them. The command compiler is the only preparation
# authority in that path; it must not fall back to native-input construction.
LEGACY_HARNESS_JOB_TOOL_NAMES = frozenset(
    {
        "build_molecule",
        "recommend_method",
        "build_gaussian_settings",
        "build_orca_settings",
        "build_xtb_settings",
        "build_job",
        "dry_run_input",
        "validate_runtime",
        "extract_optimized_geometry",
        "save_geometry",
    }
)
LEGACY_FRONTIER_HIDDEN_TOOL_NAMES = (
    LEGACY_HARNESS_JOB_TOOL_NAMES
    | {"execute_chemsmart_command", "run_local", "submit_hpc"}
)


class ToolExposure(str, Enum):
    DIRECT = "direct"
    DEFERRED = "deferred"
    HIDDEN = "hidden"


class ToolSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    phase: TaskPhase
    provider_role: ProviderRole
    program: str = ""
    direct: tuple[str, ...]
    deferred: tuple[str, ...]
    hidden: tuple[str, ...]


_FRONTIER_COMMAND_PHASE_TOOLS: dict[TaskPhase, tuple[str, ...]] = {
    TaskPhase.ROUTE: ("list_workspace",),
    TaskPhase.PROJECT: (
        "list_workspace",
        "extract_project_protocol",
        "read_project_yaml",
        "render_project_yaml",
        "validate_project_yaml",
        "search_basis_sets",
    ),
    TaskPhase.PROJECT_READ: (
        "list_workspace",
        "read_project_yaml",
        "validate_project_yaml",
        "critic_project_yaml",
        "search_basis_sets",
    ),
    TaskPhase.PROJECT_WRITE: (
        "list_workspace",
        "read_project_yaml",
        "validate_project_yaml",
        "critic_project_yaml",
        "write_project_yaml",
        "update_project_yaml",
    ),
    TaskPhase.SYNTHESIS: (
        "list_workspace",
        "read_project_yaml",
        "inspect_command_schema",
        "inspect_command_workflow",
        "synthesize_command",
        "repair_command",
    ),
    TaskPhase.VALIDATION: (
        "list_workspace",
        "read_project_yaml",
        "validate_project_yaml",
        "critic_project_yaml",
        "inspect_command_schema",
        "inspect_command_workflow",
        "synthesize_command",
        "repair_command",
    ),
    TaskPhase.REPAIR: (
        "list_workspace",
        "repair_command",
        "read_project_yaml",
        "validate_project_yaml",
        "search_basis_sets",
        "inspect_command_schema",
        "inspect_command_workflow",
        "synthesize_command",
    ),
    TaskPhase.EXECUTION: (
        "list_workspace",
        "read_project_yaml",
        "inspect_command_schema",
        "inspect_command_workflow",
        "synthesize_command",
        "repair_command",
    ),
    TaskPhase.DIAGNOSTICS: (
        "inspect_calculation",
        "read_project_yaml",
        "log_tail",
        "scheduler_query",
    ),
}
_FRONTIER_COMMAND_SPECIALIST_TOOLS = (
    "inspect_command_schema",
    "inspect_command_workflow",
    "synthesize_command",
    "repair_command",
)


class PhaseToolProfile:
    """Validated injectable direct-tool selections for runtime phases."""

    def __init__(
        self,
        phases: Mapping[TaskPhase | str, Iterable[str]],
        *,
        specialist_tools: Iterable[str] = (),
        required_completion_tools: Mapping[
            TaskPhase | str, Iterable[str]
        ] | None = None,
        trusted_initial_phase: TaskPhase | str | None = None,
    ) -> None:
        normalized: dict[TaskPhase, tuple[str, ...]] = {}
        for phase_value, names_value in phases.items():
            phase = TaskPhase(phase_value)
            names = tuple(names_value)
            self._validate_names(names, context=phase.value)
            normalized[phase] = names
        specialist = tuple(specialist_tools)
        self._validate_names(specialist, context="synthesis_specialist")
        required: dict[TaskPhase, tuple[str, ...]] = {}
        for phase_value, names_value in (
            required_completion_tools or {}
        ).items():
            phase = TaskPhase(phase_value)
            names = tuple(names_value)
            self._validate_names(names, context=f"{phase.value}:completion")
            if not set(names).issubset(set(normalized.get(phase, ()))):
                raise ValueError(
                    "required completion tools must be exposed in their phase"
                )
            required[phase] = names
        self._phases = MappingProxyType(normalized)
        self._specialist_tools = specialist
        self._required_completion_tools = MappingProxyType(required)
        self._trusted_initial_phase = (
            TaskPhase(trusted_initial_phase)
            if trusted_initial_phase is not None
            else None
        )
        if (
            self._trusted_initial_phase is not None
            and self._trusted_initial_phase not in self._phases
        ):
            raise ValueError(
                "trusted initial phase must have an explicit tool profile"
            )

    @staticmethod
    def _validate_names(names: tuple[str, ...], *, context: str) -> None:
        if len(names) > MAX_DIRECT_TOOLS_PER_PHASE:
            raise ValueError(
                f"runtime phase {context!r} may expose at most "
                f"{MAX_DIRECT_TOOLS_PER_PHASE} real tools"
            )
        if len(names) != len(set(names)):
            raise ValueError(
                f"runtime phase {context!r} contains duplicate tool names"
            )
        if any(
            not isinstance(name, str) or not name.strip() for name in names
        ):
            raise ValueError(
                f"runtime phase {context!r} contains an invalid tool name"
            )

    @property
    def capability_names(self) -> frozenset[str]:
        return frozenset(
            name for names in self._phases.values() for name in names
        ) | frozenset(self._specialist_tools)

    def tools_for(
        self,
        phase: TaskPhase,
        provider_role: ProviderRole,
    ) -> tuple[str, ...]:
        if (
            provider_role is ProviderRole.SYNTHESIS_SPECIALIST
            and self._specialist_tools
        ):
            return self._specialist_tools
        return self._phases.get(phase, ())

    def required_completion_tools_for(
        self,
        phase: TaskPhase,
    ) -> tuple[str, ...]:
        """Return host-declared green receipts required to finish a phase."""

        return self._required_completion_tools.get(phase, ())

    @property
    def trusted_initial_phase(self) -> TaskPhase | None:
        """Return a host-bound phase override, never a model-provided value."""

        return self._trusted_initial_phase


FRONTIER_COMMAND_TOOL_PROFILE = PhaseToolProfile(
    _FRONTIER_COMMAND_PHASE_TOOLS,
    specialist_tools=_FRONTIER_COMMAND_SPECIALIST_TOOLS,
)
# Backward-compatible name for hosts that rely on the implicit Runtime V2
# profile. It is intentionally command-first rather than a compatibility
# profile: legacy jobs remain available only by explicitly selecting their
# registry group outside the active frontier runtime.
DEFAULT_TOOL_PROFILE = FRONTIER_COMMAND_TOOL_PROFILE


class ToolCatalog:
    def __init__(
        self,
        registry: Any,
        *,
        profile: PhaseToolProfile | None = None,
        forbidden_direct_tools: Iterable[str] = (),
    ) -> None:
        self.registry = registry
        self.profile = profile or DEFAULT_TOOL_PROFILE
        self._forbidden_direct_tools = frozenset(forbidden_direct_tools)

    def select(
        self,
        *,
        phase: TaskPhase,
        provider_role: ProviderRole,
        program: str | None = None,
    ) -> ToolSelection:
        available = tuple(tool.name for tool in self.registry.list_tools())
        requested = tuple(
            name
            for name in self.profile.tools_for(phase, provider_role)
            if name not in self._forbidden_direct_tools
        )
        if program and not requires_project_configuration(program):
            requested = tuple(
                name for name in requested if name != "read_project_yaml"
            )
        direct = tuple(name for name in requested if name in available)
        if len(direct) > MAX_DIRECT_TOOLS_PER_PHASE:
            raise ValueError(
                "runtime phases may expose at most "
                f"{MAX_DIRECT_TOOLS_PER_PHASE} real tools"
            )
        phase_capabilities = self.profile.capability_names
        deferred = tuple(
            name
            for name in available
            if (
                name not in direct
                and name not in self._forbidden_direct_tools
                and name in phase_capabilities
            )
        )
        hidden = tuple(
            name
            for name in available
            if name not in direct and name not in deferred
        )
        return ToolSelection(
            phase=phase,
            provider_role=provider_role,
            program=str(program or ""),
            direct=direct,
            deferred=deferred,
            hidden=hidden,
        )

    def provider_tool_defs(
        self,
        provider_name: str,
        selection: ToolSelection,
    ) -> list[dict[str, Any]]:
        tools = [
            tool
            for name in selection.direct
            if (tool := self.registry.get_tool(name)) is not None
        ]
        return self.registry.tool_defs_for_provider(provider_name, tools)

    @staticmethod
    def exposure_for(
        name: str,
        selection: ToolSelection,
    ) -> ToolExposure:
        if name in selection.direct:
            return ToolExposure.DIRECT
        if name in selection.deferred:
            return ToolExposure.DEFERRED
        return ToolExposure.HIDDEN


def filter_tool_names(
    names: Iterable[str],
    selection: ToolSelection,
) -> tuple[str, ...]:
    allowed = set(selection.direct)
    return tuple(name for name in names if name in allowed)


__all__ = [
    "DEFAULT_TOOL_PROFILE",
    "FRONTIER_COMMAND_TOOL_PROFILE",
    "LEGACY_FRONTIER_HIDDEN_TOOL_NAMES",
    "LEGACY_HARNESS_JOB_TOOL_NAMES",
    "PhaseToolProfile",
    "ToolCatalog",
    "ToolExposure",
    "ToolSelection",
    "filter_tool_names",
]
