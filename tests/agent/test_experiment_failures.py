from __future__ import annotations

import pytest
from pydantic import ValidationError

from chemsmart.agent.experiment_failures import (
    FailureCategory,
    FailureDisposition,
    FailureObservationV1,
    FailureSeverity,
    FailureStage,
    Recoverability,
    summarize_failures,
)


def _observation(observation_id: str, **updates) -> FailureObservationV1:
    body = {
        "observation_id": observation_id,
        "run_id": "run-1",
        "case_id": "case-1",
        "rule_id": "paper.state.false_ready",
        "category": FailureCategory.FALSE_TERMINAL,
        "stage": FailureStage.TERMINAL,
        "severity": FailureSeverity.CRITICAL,
        "disposition": FailureDisposition.ARCHITECTURAL_CHANGE,
        "recoverability": Recoverability.CAPABILITY_CHANGE_REQUIRED,
        "evidence_sha256": "a" * 64,
    }
    body.update(updates)
    return FailureObservationV1(**body)


def test_summary_prioritizes_repeated_unrecovered_critical_failure() -> None:
    observations = (
        _observation("failure-1"),
        _observation("failure-2", run_id="run-2"),
        _observation(
            "failure-3",
            category=FailureCategory.PROVIDER_OR_CONTEXT,
            stage=FailureStage.PROVIDER,
            severity=FailureSeverity.WARNING,
            disposition=FailureDisposition.REPAIR,
            recoverability=Recoverability.BOUNDED_REPAIR,
            recovered=True,
            repair_count=1,
        ),
    )

    summary = summarize_failures(observations)

    assert summary.total_observations == 3
    assert summary.highest_value_categories == (FailureCategory.FALSE_TERMINAL,)
    assert len(summary.summary_sha256) == 64


def test_failure_claims_are_fail_closed() -> None:
    with pytest.raises(ValidationError, match="cannot claim recovered"):
        _observation("failure-1", recovered=True)
    with pytest.raises(ValidationError, match="repair count"):
        _observation("failure-2", repair_count=1)


def test_summary_rejects_duplicate_observation_ids() -> None:
    observation = _observation("failure-1")
    with pytest.raises(ValueError, match="must be unique"):
        summarize_failures((observation, observation))
