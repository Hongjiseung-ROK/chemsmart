from __future__ import annotations

import pytest

from chemsmart.agent.experiment_outcomes import (
    ExpectedBehavior,
    ScientificReadiness,
    ToolDomainOutcome,
    classify_experiment_outcome,
)
from chemsmart.agent.provider_adapter import ToolOutcome


def _normalized_outcome(
    domain_status: str | None = None,
    *,
    outer_status: str = "ok",
) -> dict[str, object]:
    result: dict[str, object] = {"ok": True}
    if domain_status is not None:
        result["status"] = domain_status
    return {
        "name": "paper_tool",
        "status": outer_status,
        "error_type": None,
        "result": result,
    }


def test_completed_turn_without_tool_is_not_scientific_success() -> None:
    classification = classify_experiment_outcome(
        {
            "terminal_outcome": "completed",
            "tool_requests": [],
            "tool_outcomes": [],
        },
        expected_domain_outcomes=(ToolDomainOutcome.PREVIEWED,),
    )

    assert classification.agent_turn_outcome == "completed"
    assert classification.tool_domain_outcome is ToolDomainOutcome.NO_TOOL_CALL
    assert classification.scientific_readiness is ScientificReadiness.NOT_ESTABLISHED
    assert classification.expected_behavior is ExpectedBehavior.MISMATCHED
    assert classification.case_pass is False


@pytest.mark.parametrize(
    ("domain_status", "expected_outcome", "readiness"),
    [
        (
            "needs_clarification",
            ToolDomainOutcome.NEEDS_CLARIFICATION,
            ScientificReadiness.BLOCKED,
        ),
        ("blocked", ToolDomainOutcome.BLOCKED, ScientificReadiness.BLOCKED),
        ("infeasible", ToolDomainOutcome.INFEASIBLE, ScientificReadiness.BLOCKED),
        ("planned", ToolDomainOutcome.PLANNED, ScientificReadiness.PLANNED),
        ("previewed", ToolDomainOutcome.PREVIEWED, ScientificReadiness.PREVIEWED),
        (
            "extracted",
            ToolDomainOutcome.EXTRACTED,
            ScientificReadiness.NOT_ESTABLISHED,
        ),
        (None, ToolDomainOutcome.TOOL_OK, ScientificReadiness.NOT_ESTABLISHED),
    ],
)
def test_normalized_tool_domain_states_are_distinct(
    domain_status: str | None,
    expected_outcome: ToolDomainOutcome,
    readiness: ScientificReadiness,
) -> None:
    classification = classify_experiment_outcome(
        tool_outcomes=[_normalized_outcome(domain_status)],
        expected_domain_outcomes=(expected_outcome,),
    )

    assert classification.agent_turn_outcome == "unknown"
    assert classification.tool_domain_outcome is expected_outcome
    assert classification.scientific_readiness is readiness
    assert classification.expected_behavior is ExpectedBehavior.MATCHED
    assert classification.case_pass is True


def test_outer_tool_error_wins_over_domain_payload_and_completed_turn() -> None:
    outcome = ToolOutcome(
        request_id="request-1",
        provider_call_id="call-1",
        name="synthesize_command",
        status="error",
        raw_result={"status": "previewed", "ok": True},
        error_type="ValidationError",
        error_message="typed contract rejected",
    )
    classification = classify_experiment_outcome(
        {
            "terminal_outcome": "completed",
            "tool_requests": [{"name": "synthesize_command"}],
            "tool_outcomes": [outcome],
        },
        expected_domain_outcomes=(ToolDomainOutcome.TOOL_ERROR,),
    )

    assert classification.agent_turn_outcome == "completed"
    assert classification.tool_domain_outcome is ToolDomainOutcome.TOOL_ERROR
    assert classification.scientific_readiness is ScientificReadiness.NOT_ESTABLISHED
    assert classification.case_pass is True


def test_request_without_outcome_is_tool_error_not_no_tool_call() -> None:
    classification = classify_experiment_outcome(
        {
            "terminal_outcome": "failed",
            "tool_requests": [{"name": "render_project_yaml"}],
            "tool_outcomes": [],
        },
        expected_domain_outcomes=("tool_error",),
    )

    assert classification.tool_domain_outcome is ToolDomainOutcome.TOOL_ERROR
    assert classification.tool_request_count == 1
    assert classification.tool_outcome_count == 0
    assert classification.case_pass is True


def test_session_aggregate_does_not_hide_an_earlier_blocker() -> None:
    classification = classify_experiment_outcome(
        {
            "terminal_outcome": "completed",
            "tool_requests": [{}, {}],
            "tool_outcomes": [
                _normalized_outcome("needs_clarification"),
                _normalized_outcome("previewed"),
            ],
        },
        expected_domain_outcomes=("previewed",),
    )

    assert classification.observed_tool_domain_outcomes == (
        ToolDomainOutcome.NEEDS_CLARIFICATION,
        ToolDomainOutcome.PREVIEWED,
    )
    assert (
        classification.tool_domain_outcome
        is ToolDomainOutcome.NEEDS_CLARIFICATION
    )
    assert classification.case_pass is False


def test_unscored_observation_cannot_pass_by_default() -> None:
    classification = classify_experiment_outcome(
        tool_outcomes=[_normalized_outcome("previewed")]
    )

    assert classification.expected_behavior is ExpectedBehavior.NOT_DECLARED
    assert classification.case_pass is False
    assert classification.to_dict()["tool_domain_outcome"] == "previewed"


def test_unknown_expected_domain_outcome_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown expected domain outcome"):
        classify_experiment_outcome(
            tool_outcomes=[],
            expected_domain_outcomes=("completed",),
        )
