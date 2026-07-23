"""Phase-scoped tool exposure independent of model provider syntax."""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, ConfigDict

from chemsmart.agent.runtime.contracts import ProviderRole, TaskPhase


class ToolExposure(str, Enum):
    DIRECT = "direct"
    DEFERRED = "deferred"
    HIDDEN = "hidden"


class ToolSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    phase: TaskPhase
    provider_role: ProviderRole
    direct: tuple[str, ...]
    deferred: tuple[str, ...]
    hidden: tuple[str, ...]


_PHASE_TOOLS: dict[TaskPhase, tuple[str, ...]] = {
    TaskPhase.PROJECT: (
        "extract_project_protocol",
        "read_project_yaml",
        "render_project_yaml",
        "validate_project_yaml",
        "search_basis_sets",
    ),
    TaskPhase.PROJECT_READ: (
        "read_project_yaml",
        "validate_project_yaml",
        "critic_project_yaml",
        "search_basis_sets",
    ),
    TaskPhase.PROJECT_WRITE: (
        "read_project_yaml",
        "validate_project_yaml",
        "critic_project_yaml",
        "write_project_yaml",
        "update_project_yaml",
    ),
    TaskPhase.SYNTHESIS: (
        "read_project_yaml",
        "synthesize_command",
        "repair_command",
    ),
    TaskPhase.VALIDATION: (
        "read_project_yaml",
        "validate_project_yaml",
        "critic_project_yaml",
        "synthesize_command",
        "repair_command",
    ),
    TaskPhase.REPAIR: (
        "repair_command",
        "read_project_yaml",
        "validate_project_yaml",
        "search_basis_sets",
        "synthesize_command",
    ),
    TaskPhase.EXECUTION: (
        "synthesize_command",
        "repair_command",
        "execute_chemsmart_command",
        "read_project_yaml",
    ),
    TaskPhase.DIAGNOSTICS: (
        "inspect_calculation",
        "read_project_yaml",
        "log_tail",
        "scheduler_query",
    ),
}
_SPECIALIST_TOOLS = ("synthesize_command", "repair_command")


class PhaseToolProfile:
    """Validated injectable direct-tool selections for runtime phases."""

    def __init__(
        self,
        phases: Mapping[TaskPhase | str, Iterable[str]],
        *,
        specialist_tools: Iterable[str] = (),
    ) -> None:
        normalized: dict[TaskPhase, tuple[str, ...]] = {}
        for phase_value, names_value in phases.items():
            phase = TaskPhase(phase_value)
            names = tuple(names_value)
            self._validate_names(names, context=phase.value)
            normalized[phase] = names
        specialist = tuple(specialist_tools)
        self._validate_names(specialist, context="synthesis_specialist")
        self._phases = MappingProxyType(normalized)
        self._specialist_tools = specialist

    @staticmethod
    def _validate_names(names: tuple[str, ...], *, context: str) -> None:
        if len(names) > 5:
            raise ValueError(
                f"runtime phase {context!r} may expose at most five real tools"
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


DEFAULT_TOOL_PROFILE = PhaseToolProfile(
    _PHASE_TOOLS,
    specialist_tools=_SPECIALIST_TOOLS,
)


class ToolCatalog:
    def __init__(
        self,
        registry: Any,
        *,
        profile: PhaseToolProfile | None = None,
    ) -> None:
        self.registry = registry
        self.profile = profile or DEFAULT_TOOL_PROFILE

    def select(
        self,
        *,
        phase: TaskPhase,
        provider_role: ProviderRole,
    ) -> ToolSelection:
        available = tuple(tool.name for tool in self.registry.list_tools())
        requested = self.profile.tools_for(phase, provider_role)
        direct = tuple(name for name in requested if name in available)
        if len(direct) > 5:
            raise ValueError(
                "runtime phases may expose at most five real tools"
            )
        phase_capabilities = self.profile.capability_names
        deferred = tuple(
            name
            for name in available
            if name not in direct and name in phase_capabilities
        )
        hidden = tuple(
            name
            for name in available
            if name not in direct and name not in deferred
        )
        return ToolSelection(
            phase=phase,
            provider_role=provider_role,
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
    "PhaseToolProfile",
    "ToolCatalog",
    "ToolExposure",
    "ToolSelection",
    "filter_tool_names",
]
