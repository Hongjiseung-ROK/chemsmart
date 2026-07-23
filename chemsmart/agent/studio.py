"""Studio-owned agent tools delegated through explicit host adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from chemsmart.agent.registry import ToolSpec, build_tool_spec
from chemsmart.agent.runtime.contracts import TaskPhase
from chemsmart.agent.runtime.tool_catalog import PhaseToolProfile
from chemsmart.agent.tool_protocol import RuntimeToolMetadata


class StudioHostAdapter(Protocol):
    def get_studio_context(self, arguments: dict[str, Any]) -> Any: ...

    def analyze_current_molecule(self, arguments: dict[str, Any]) -> Any: ...


class CalculationExecutionAdapter(Protocol):
    def prepare_molecule_optimization(
        self, arguments: dict[str, Any]
    ) -> Any: ...

    def validate_prepared_optimization(
        self, arguments: dict[str, Any]
    ) -> Any: ...

    def start_prepared_optimization(
        self, arguments: dict[str, Any]
    ) -> Any: ...

    def get_optimization_status(self, arguments: dict[str, Any]) -> Any: ...

    def get_optimization_replay(self, arguments: dict[str, Any]) -> Any: ...

    def compare_optimization_frames(
        self, arguments: dict[str, Any]
    ) -> Any: ...

    def import_completed_calculation(
        self, arguments: dict[str, Any]
    ) -> Any: ...


class StudioArtifactAdapter(Protocol):
    def list_calculation_artifacts(self, arguments: dict[str, Any]) -> Any: ...

    def read_calculation_artifact(self, arguments: dict[str, Any]) -> Any: ...


class StudioApprovalAdapter(Protocol):
    def require_approval(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None: ...


@dataclass(frozen=True)
class StudioToolAdapters:
    host: StudioHostAdapter
    execution: CalculationExecutionAdapter
    artifacts: StudioArtifactAdapter
    approvals: StudioApprovalAdapter


STUDIO_TOOL_NAMES = (
    "get_studio_context",
    "analyze_current_molecule",
    "prepare_molecule_optimization",
    "validate_prepared_optimization",
    "start_prepared_optimization",
    "get_optimization_status",
    "list_calculation_artifacts",
    "read_calculation_artifact",
    "get_optimization_replay",
    "compare_optimization_frames",
    "import_completed_calculation",
)

_RISKY_STUDIO_TOOLS = frozenset(
    {
        "start_prepared_optimization",
        "import_completed_calculation",
    }
)

_TOOL_DESCRIPTIONS = {
    "get_studio_context": (
        "Read the current Studio session, document, revision, and trusted "
        "workflow context."
    ),
    "analyze_current_molecule": (
        "Analyze the current committed Studio molecule without changing it."
    ),
    "prepare_molecule_optimization": (
        "Prepare a revision-bound optimization plan without starting an engine."
    ),
    "validate_prepared_optimization": (
        "Validate a prepared optimization plan and its canonical digest."
    ),
    "start_prepared_optimization": (
        "Start an already prepared and validated optimization after approval."
    ),
    "get_optimization_status": "Read controlled optimization status.",
    "list_calculation_artifacts": (
        "List bounded opaque artifacts for a controlled calculation."
    ),
    "read_calculation_artifact": (
        "Read bounded content through an opaque artifact identifier."
    ),
    "get_optimization_replay": (
        "Read the durable optimization replay timeline."
    ),
    "compare_optimization_frames": (
        "Compare two recorded optimization frames without changing geometry."
    ),
    "import_completed_calculation": (
        "Import a validated completed calculation after explicit approval."
    ),
}

_TOOL_TARGETS = {
    "get_studio_context": ("host", "get_studio_context"),
    "analyze_current_molecule": ("host", "analyze_current_molecule"),
    "prepare_molecule_optimization": (
        "execution",
        "prepare_molecule_optimization",
    ),
    "validate_prepared_optimization": (
        "execution",
        "validate_prepared_optimization",
    ),
    "start_prepared_optimization": (
        "execution",
        "start_prepared_optimization",
    ),
    "get_optimization_status": ("execution", "get_optimization_status"),
    "list_calculation_artifacts": (
        "artifacts",
        "list_calculation_artifacts",
    ),
    "read_calculation_artifact": (
        "artifacts",
        "read_calculation_artifact",
    ),
    "get_optimization_replay": ("execution", "get_optimization_replay"),
    "compare_optimization_frames": (
        "execution",
        "compare_optimization_frames",
    ),
    "import_completed_calculation": (
        "execution",
        "import_completed_calculation",
    ),
}


def _bound_tool_handler(
    adapters: StudioToolAdapters,
    method: Any,
    tool_name: str,
    requires_approval: bool,
) -> Any:
    def invoke(**arguments: Any) -> Any:
        if requires_approval:
            adapters.approvals.require_approval(tool_name, arguments)
        return method(arguments)

    invoke.__name__ = tool_name
    invoke.__doc__ = _TOOL_DESCRIPTIONS[tool_name]
    return invoke


def build_studio_tool_specs(
    adapters: StudioToolAdapters,
    input_schemas: Mapping[str, dict[str, Any]],
) -> tuple[ToolSpec, ...]:
    """Bind Studio schemas and host adapters into deterministic tool specs."""

    expected = set(STUDIO_TOOL_NAMES)
    provided = set(input_schemas)
    missing = sorted(expected - provided)
    unknown = sorted(provided - expected)
    if missing or unknown:
        raise ValueError(
            "Studio tool schemas must exactly match the supported tools; "
            f"missing={missing!r}, unknown={unknown!r}"
        )

    specs: list[ToolSpec] = []
    for tool_name in STUDIO_TOOL_NAMES:
        adapter_name, method_name = _TOOL_TARGETS[tool_name]
        adapter = getattr(adapters, adapter_name)
        method = getattr(adapter, method_name)
        requires_approval = tool_name in _RISKY_STUDIO_TOOLS
        invoke = _bound_tool_handler(
            adapters,
            method,
            tool_name,
            requires_approval,
        )
        specs.append(
            build_tool_spec(
                invoke,
                registered_name=tool_name,
                description=_TOOL_DESCRIPTIONS[tool_name],
                metadata=RuntimeToolMetadata(
                    read_only=not requires_approval,
                    side_effect=(
                        None
                        if not requires_approval
                        else (
                            "starts a controlled calculation"
                            if tool_name == "start_prepared_optimization"
                            else "imports a completed calculation"
                        )
                    ),
                ),
                input_json_schema=input_schemas[tool_name],
            )
        )
    return tuple(specs)


STUDIO_TOOL_PROFILE = PhaseToolProfile(
    {
        TaskPhase.ROUTE: (
            "get_studio_context",
            "analyze_current_molecule",
        ),
        TaskPhase.PROJECT: (
            "get_studio_context",
            "analyze_current_molecule",
            "prepare_molecule_optimization",
            "validate_prepared_optimization",
        ),
        TaskPhase.PROJECT_READ: (
            "get_studio_context",
            "analyze_current_molecule",
            "get_optimization_status",
            "get_optimization_replay",
            "compare_optimization_frames",
        ),
        TaskPhase.PROJECT_WRITE: (
            "get_studio_context",
            "list_calculation_artifacts",
            "read_calculation_artifact",
            "import_completed_calculation",
            "get_optimization_status",
        ),
        TaskPhase.SYNTHESIS: (
            "get_studio_context",
            "analyze_current_molecule",
            "prepare_molecule_optimization",
            "validate_prepared_optimization",
        ),
        TaskPhase.VALIDATION: (
            "analyze_current_molecule",
            "validate_prepared_optimization",
            "get_optimization_status",
            "get_optimization_replay",
            "compare_optimization_frames",
        ),
        TaskPhase.REPAIR: (
            "get_studio_context",
            "analyze_current_molecule",
            "prepare_molecule_optimization",
            "validate_prepared_optimization",
            "get_optimization_status",
        ),
        TaskPhase.EXECUTION: (
            "validate_prepared_optimization",
            "start_prepared_optimization",
            "get_optimization_status",
            "get_optimization_replay",
            "compare_optimization_frames",
        ),
        TaskPhase.DIAGNOSTICS: (
            "get_optimization_status",
            "list_calculation_artifacts",
            "read_calculation_artifact",
            "get_optimization_replay",
            "import_completed_calculation",
        ),
    },
    specialist_tools=(
        "get_studio_context",
        "analyze_current_molecule",
        "prepare_molecule_optimization",
        "validate_prepared_optimization",
    ),
)


__all__ = [
    "CalculationExecutionAdapter",
    "STUDIO_TOOL_NAMES",
    "STUDIO_TOOL_PROFILE",
    "StudioApprovalAdapter",
    "StudioArtifactAdapter",
    "StudioHostAdapter",
    "StudioToolAdapters",
    "build_studio_tool_specs",
]
