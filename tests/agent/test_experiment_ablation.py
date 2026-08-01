from __future__ import annotations

import pytest

from chemsmart.agent.experiment_ablation import (
    AblationConfigurationV1,
    AblationFixedContextV1,
    ExperimentEventKind,
    build_ablation_run_spec,
    build_experiment_event,
    pair_ablation_runs,
    validate_experiment_event_chain,
)


_A = "a" * 64
_B = "b" * 64
_C = "c" * 64
_D = "d" * 64


def _context(**updates) -> AblationFixedContextV1:
    body = {
        "paper_id": "paper-1",
        "source_bundle_sha256": _A,
        "coordinate_receipt_sha256": _B,
        "base_prompt_template_sha256": _C,
        "available_tool_catalog_sha256": _D,
        "project_schema_sha256": _A,
        "validator_registry_sha256": _B,
        "task_order_sha256": _C,
        "network_budget_sha256": _D,
        "model": "deepseek-v4-flash",
        "provider": "deepseek",
        "endpoint_origin": "https://api.deepseek.com",
        "prompt_version": "prp10-v1",
    }
    body.update(updates)
    return AblationFixedContextV1(**body)


def _run(run_id, arm, config, **updates):
    body = {
        "run_id": run_id,
        "case_id": "case-1",
        "hypothesis_id": "hypothesis-1",
        "hypothesis": "Structured evidence preserves source-localized facts.",
        "expected_outcome": "Fact preservation improves without a false ready state.",
        "deterministic_oracle_ids": ("oracle.claim-source-binding",),
        "novelty_rationale": "No prior run changed only structured documentation.",
        "configuration": config,
        "fixed_context": _context(),
        "rendered_prompt_sha256": _A,
        "exposed_tool_schema_sha256": _B,
        "comparison_id": "comparison-1",
        "arm": arm,
    }
    body.update(updates)
    return build_ablation_run_spec(**body)


def test_pair_changes_one_switch_and_keeps_safety_invariant() -> None:
    baseline = _run("run-baseline", "baseline", AblationConfigurationV1())
    treatment = _run(
        "run-treatment",
        "treatment",
        AblationConfigurationV1(structured_documentation=True),
    )

    receipt = pair_ablation_runs(baseline, treatment)

    assert receipt.changed_switch == "structured_documentation"
    assert baseline.safety_plane.deterministic_safety_oracle is True
    assert treatment.safety_plane.chemistry_engine_execution_allowed is False


def test_pair_rejects_multiple_changes_or_context_drift() -> None:
    baseline = _run("run-baseline", "baseline", AblationConfigurationV1())
    treatment = _run(
        "run-treatment",
        "treatment",
        AblationConfigurationV1(
            task_decomposition=True,
            structured_documentation=True,
        ),
    )
    with pytest.raises(ValueError, match="exactly one"):
        pair_ablation_runs(baseline, treatment)

    one_change = _run(
        "run-treatment",
        "treatment",
        AblationConfigurationV1(structured_documentation=True),
        fixed_context=_context(base_prompt_template_sha256=_A),
    )
    with pytest.raises(ValueError, match="fixed experiment context"):
        pair_ablation_runs(baseline, one_change)


def test_all_component_switches_can_be_isolated() -> None:
    specialist_only = AblationConfigurationV1(specialist_roles=True)
    cross_examination_only = AblationConfigurationV1(
        adversarial_cross_examination=True
    )

    assert sum(specialist_only.switch_values().values()) == 1
    assert sum(cross_examination_only.switch_values().values()) == 1


def test_pair_allows_component_owned_prompt_and_tool_surface_change() -> None:
    baseline = _run("run-baseline", "baseline", AblationConfigurationV1())
    treatment = _run(
        "run-treatment",
        "treatment",
        AblationConfigurationV1(evidence_retrieval=True),
        rendered_prompt_sha256=_C,
        exposed_tool_schema_sha256=_D,
    )

    receipt = pair_ablation_runs(baseline, treatment)

    assert receipt.changed_switch == "evidence_retrieval"


def test_experiment_event_chain_is_separate_and_terminal() -> None:
    first = build_experiment_event(
        sequence=1,
        event_id="event-1",
        run_id="run-1",
        kind=ExperimentEventKind.RUN_PREREGISTERED,
        observed_at="2026-08-01T00:00:00Z",
        payload={"run_spec_sha256": _A},
    )
    second = build_experiment_event(
        sequence=2,
        event_id="event-2",
        run_id="run-1",
        kind=ExperimentEventKind.RUN_TERMINATED,
        observed_at="2026-08-01T00:01:00Z",
        payload={"terminal_state": "blocked"},
        previous_hash=first.event_hash,
    )

    assert validate_experiment_event_chain((first, second)) == ()
    assert validate_experiment_event_chain((first,)) == (
        "experiment.event_chain.terminal_missing",
    )
