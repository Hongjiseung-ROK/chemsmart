from __future__ import annotations

from chemsmart.agent.runtime.contracts import ArtifactRef, TaskPhase
from chemsmart.agent.runtime.reducer import RuntimeState
from chemsmart.gui.application.runtime_projection import project_runtime_state


def test_projection_summarizes_receipts_and_artifacts_without_payload_details():
    secret = "never-render-this-provider-secret"
    state = RuntimeState(
        session_id="session_1234567890",
        turn_id="turn_0001",
        phase=TaskPhase.COMPLETE,
        request=f"optimize using {secret}",
        previous_command=f"chemsmart --token={secret}",
        completed_tool_receipts=[
            {"tool": "synthesize_command", "verdict": "ok"}
        ],
        artifacts=[
            ArtifactRef(
                artifact_id="artifact-1",
                kind="generated_input",
                path=f"/private/{secret}/job.com",
                sha256="a" * 64,
                size_bytes=42,
                metadata={"provider_key": secret},
            )
        ],
    )

    projection = project_runtime_state(state)
    rendered = "\n".join(
        (
            projection.session_label,
            projection.activity_label,
            projection.evidence_label,
            projection.recovery_message,
        )
    )

    assert projection.session_label == "Session …34567890 · active turn"
    assert projection.activity_label == "Agent: Complete"
    assert projection.evidence_label == "Evidence: 1 receipt · 1 artifact"
    assert secret not in rendered
    assert "chemsmart" not in rendered
    assert "/private" not in rendered
    assert "artifact-1" not in rendered
    assert "a" * 64 not in rendered


def test_projection_reports_running_and_recovery_states_without_raw_reasons():
    running = RuntimeState(
        session_id="s1",
        phase=TaskPhase.EXECUTION,
        active_tool_calls={"request-with-secret": "execute_chemsmart_command"},
    )
    blocked = RuntimeState(
        session_id="s2",
        phase=TaskPhase.BLOCKED,
        blocked_reason="provider-secret-should-not-render",
        last_failure_rule_ids=["rule-with-sensitive-value"],
    )

    running_projection = project_runtime_state(running)
    blocked_projection = project_runtime_state(blocked)

    assert running_projection.activity_label == "Agent: 1 task running"
    assert not running_projection.needs_recovery
    assert blocked_projection.activity_label == "Agent: Recovery needed"
    assert blocked_projection.needs_recovery
    assert "provider-secret" not in blocked_projection.recovery_message
    assert "rule-with-sensitive" not in blocked_projection.recovery_message


def test_projection_treats_permission_as_a_recoverable_pause():
    projection = project_runtime_state(
        RuntimeState(
            session_id="opaque-session",
            phase=TaskPhase.EXECUTION,
            pending_approval="submit_hpc",
        )
    )

    assert projection.activity_label == "Agent: permission needed"
    assert projection.needs_recovery
    assert "submit_hpc" not in projection.recovery_message
