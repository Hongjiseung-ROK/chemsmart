from __future__ import annotations

import pytest
from pydantic import ValidationError

from chemsmart.agent.experiment_campaign import (
    CampaignPhaseBudget,
    ExperimentCampaign,
    ExperimentProgress,
    build_default_experiment_campaign,
    experiment_campaign_sha256,
    experiment_progress_id,
)


def test_default_campaign_freezes_agreed_transport_caps() -> None:
    campaign = build_default_experiment_campaign()

    assert campaign.deepseek_transport_hard_cap == 128
    assert sum(
        item.max_deepseek_transport_attempts
        for item in campaign.phase_budgets
    ) == 128
    assert {
        item.provider: item.max_transport_attempts
        for item in campaign.literature_budgets
    } == {"elsevier": 24, "serpapi": 24, "tavily": 24}
    assert campaign.thinking_mode == "enabled"
    assert campaign.sdk_max_retries == 0
    assert len(experiment_campaign_sha256(campaign)) == 64


def test_campaign_rejects_phase_budget_overstatement() -> None:
    campaign = build_default_experiment_campaign()
    budgets = list(campaign.phase_budgets)
    first = budgets[0]
    budgets[0] = CampaignPhaseBudget(
        phase_id=first.phase_id,
        max_deepseek_transport_attempts=(
            first.max_deepseek_transport_attempts + 1
        ),
    )

    with pytest.raises(ValidationError, match="sum to hard cap"):
        ExperimentCampaign.model_validate(
            {**campaign.model_dump(mode="python"), "phase_budgets": budgets}
        )


def test_progress_rejects_literature_provider_overrun() -> None:
    body = {
        "schema_version": "chemsmart.experiment-progress.v1",
        "campaign_sha256": "a" * 64,
        "completed_case_ids": (),
        "receipt_ids": (),
        "deepseek_transport_attempts": 0,
        "literature_transport_attempts": {
            "elsevier": 25,
            "serpapi": 0,
            "tavily": 0,
        },
        "stopped": False,
        "stop_rule_ids": (),
    }
    body["progress_id"] = experiment_progress_id(body)

    with pytest.raises(ValidationError, match="literature provider hard cap exceeded"):
        ExperimentProgress.model_validate(body)
