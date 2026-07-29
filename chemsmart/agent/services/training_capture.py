"""Best-effort SFT episode capture for completed tool-loop turns."""

from __future__ import annotations

from dataclasses import replace
from enum import Enum
from typing import Any, Protocol

from chemsmart.agent.services.result_codec import json_safe


class TrainingCapturePolicy(str, Enum):
    """Host-owned policy for optional SFT episode capture."""

    CONFIGURED = "configured"
    ENABLED = "enabled"
    DISABLED = "disabled"

    @classmethod
    def parse(
        cls,
        value: "TrainingCapturePolicy | str | bool | None",
    ) -> "TrainingCapturePolicy":
        if value is None:
            return cls.CONFIGURED
        if isinstance(value, cls):
            return value
        if value is True:
            return cls.ENABLED
        if value is False:
            return cls.DISABLED
        normalized = str(value).strip().lower()
        if normalized in {"configured", "config", "default"}:
            return cls.CONFIGURED
        if normalized in {"enabled", "enable", "on", "true", "1"}:
            return cls.ENABLED
        if normalized in {"disabled", "disable", "off", "false", "0"}:
            return cls.DISABLED
        raise ValueError(f"Unsupported training capture policy: {value!r}")


class TrainingCaptureHost(Protocol):
    state: Any | None
    registry: Any
    _training_writer: Any | None
    training_capture_policy: TrainingCapturePolicy


class TrainingCapture:
    def __init__(self, session: TrainingCaptureHost) -> None:
        self.session = session

    def write_episode(
        self,
        *,
        provider_name: str,
        provider: Any,
        loop_result: dict[str, Any],
        paused: bool = False,
    ) -> None:
        try:
            self._write(
                provider_name=provider_name,
                provider=provider,
                loop_result=loop_result,
                paused=paused,
            )
        except Exception:
            # Training capture is observational and cannot break a live turn.
            return

    def _write(
        self,
        *,
        provider_name: str,
        provider: Any,
        loop_result: dict[str, Any],
        paused: bool,
    ) -> None:
        from chemsmart.agent.training_log import (
            TrainingEpisodeWriter,
            TrainingLogConfig,
            load_training_log_config,
            tool_records_from_outcomes,
        )

        session = self.session
        if session.training_capture_policy is TrainingCapturePolicy.DISABLED:
            return
        if session._training_writer is None:
            config: TrainingLogConfig | None = None
            if (
                session.training_capture_policy
                is TrainingCapturePolicy.ENABLED
            ):
                config = replace(load_training_log_config(), enabled=True)
            session._training_writer = TrainingEpisodeWriter(config=config)
        writer = session._training_writer
        if not writer.enabled or session.state is None:
            return
        outcomes = list(loop_result.get("tool_outcomes") or [])
        writer.write_episode(
            session_id=session.state.session_id,
            turn=session.state.turn_index,
            provider_name=provider_name,
            model=getattr(provider, "default_model", None),
            messages=json_safe(loop_result.get("messages") or []),
            tool_records=tool_records_from_outcomes(
                outcomes,
                requests=list(loop_result.get("tool_requests") or []),
            ),
            tool_requests=list(loop_result.get("tool_requests") or []),
            approvals_count=loop_result.get("approvals_count") or 0,
            denials_count=loop_result.get("denials_count") or 0,
            cwd=session.state.cwd,
            available_tools=registry_tool_names(session.registry),
            final_answer=str(loop_result.get("assistant_text") or ""),
            terminal_state=_terminal_state(outcomes),
            paused=paused,
        )


def registry_tool_names(registry: Any) -> list[str]:
    list_tools = getattr(registry, "list_tools", None)
    if not callable(list_tools):
        return []
    try:
        return [tool.name for tool in list_tools()]
    except Exception:
        return []


def _terminal_state(outcomes: list[Any]) -> dict[str, Any] | None:
    for outcome in reversed(outcomes):
        result = getattr(outcome, "raw_result", None)
        if isinstance(result, dict) and isinstance(
            result.get("terminal_state"), dict
        ):
            return result["terminal_state"]
    return None


__all__ = [
    "TrainingCapture",
    "TrainingCapturePolicy",
    "registry_tool_names",
]
