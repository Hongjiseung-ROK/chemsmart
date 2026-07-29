"""Deterministic program capabilities used by the agent harness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EngineCapability:
    """Project-configuration requirements for one chemistry program."""

    program: str
    requires_project_configuration: bool
    supports_project_configuration: bool


ENGINE_CAPABILITIES: dict[str, EngineCapability] = {
    "gaussian": EngineCapability(
        program="gaussian",
        requires_project_configuration=True,
        supports_project_configuration=True,
    ),
    "orca": EngineCapability(
        program="orca",
        requires_project_configuration=True,
        supports_project_configuration=True,
    ),
    "xtb": EngineCapability(
        program="xtb",
        requires_project_configuration=False,
        supports_project_configuration=True,
    ),
}


def engine_capability(program: str | None) -> EngineCapability | None:
    """Return the capability for a known program."""

    return ENGINE_CAPABILITIES.get(str(program or "").strip().lower())


def requires_project_configuration(program: str | None) -> bool:
    """Return whether the agent must load a project before synthesis."""

    capability = engine_capability(program)
    return bool(
        capability is not None
        and capability.requires_project_configuration
    )


__all__ = [
    "ENGINE_CAPABILITIES",
    "EngineCapability",
    "engine_capability",
    "requires_project_configuration",
]
