"""Versioned append-only runtime event definitions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class EventKind(str, Enum):
    SESSION_STARTED = "session_started"
    TURN_STARTED = "turn_started"
    EXPOSURE_PLANNED = "exposure_planned"
    TOOL_STARTED = "tool_started"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"
    PERMISSION_RESOLVED = "permission_resolved"
    PROJECT_SELECTED = "project_selected"
    COMMAND_SYNTHESIZED = "command_synthesized"
    CLARIFICATION_REQUESTED = "clarification_requested"
    ARTIFACT_RECORDED = "artifact_recorded"
    SHADOW_VIOLATION = "shadow_violation"
    TURN_COMPLETED = "turn_completed"
    TURN_BLOCKED = "turn_blocked"
    RESEARCH_STAGE_CHANGED = "research_stage_changed"
    PLAN_REVISION_ADOPTED = "plan_revision_adopted"
    PAPER_SOURCE_FROZEN = "paper_source_frozen"
    PROTOCOL_CLAIM_RECORDED = "protocol_claim_recorded"
    MOLECULAR_SYSTEM_SPECIFIED = "molecular_system_specified"
    PROJECT_CONFIG_SPECIFIED = "project_config_specified"
    DOMAIN_KNOWLEDGE_BOUND = "domain_knowledge_bound"
    PAPER_PLAN_VALIDATED = "paper_plan_validated"
    SPECIALIST_TASK_DISPATCHED = "specialist_task_dispatched"
    SPECIALIST_TASKS_JOINED = "specialist_tasks_joined"
    COMMAND_WORKFLOW_PREVIEWED = "command_workflow_previewed"
    REVIEW_FINDING_RECORDED = "review_finding_recorded"
    REVIEW_GATE_RECORDED = "review_gate_recorded"
    REPORT_GRAPH_RECORDED = "report_graph_recorded"
    RESEARCH_BUDGET_RECORDED = "research_budget_recorded"
    RESEARCH_PAUSED = "research_paused"
    RESEARCH_RESUMED = "research_resumed"
    RESEARCH_TERMINATED = "research_terminated"


class RuntimeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    sequence: int = Field(ge=1)
    event_id: str
    session_id: str
    turn_id: str
    kind: EventKind
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = ""
    previous_hash: str = ""
    event_hash: str

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        session_id: str,
        turn_id: str,
        kind: EventKind,
        payload: dict[str, Any],
        previous_hash: str,
        idempotency_key: str = "",
    ) -> "RuntimeEvent":
        # Import lazily to keep the legacy envelope independent while ensuring
        # every newly constructed research event is canonical and reducible.
        from chemsmart.agent.runtime.research_events import (
            validate_research_event_payload,
        )

        normalized_payload = validate_research_event_payload(kind, payload)
        body = {
            "schema_version": 1,
            "sequence": sequence,
            "event_id": uuid4().hex,
            "session_id": session_id,
            "turn_id": turn_id,
            "kind": kind.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": normalized_payload,
            "idempotency_key": idempotency_key,
            "previous_hash": previous_hash,
        }
        event_hash = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return cls(**body, event_hash=event_hash)

    def verify_hash(self) -> bool:
        body = self.model_dump(exclude={"event_hash"}, mode="json")
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return digest == self.event_hash


__all__ = ["EventKind", "RuntimeEvent"]
