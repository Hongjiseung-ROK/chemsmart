"""Fixture-only deterministic checks for the frozen Frontier fault suite."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from chemsmart.agent.harness.frontier_faults import (
    FaultTrace,
    FrontierFaultSuite,
    grade_fault_trace,
    load_frontier_fault_suite,
    summarize_fault_grades,
)


_FIXTURES = Path(__file__).parent / "fixtures"
_REFERENCE = _FIXTURES / "frontier_single_agent_reference_v1.json"
_PUBLIC_CASES = _FIXTURES / "frontier_single_agent_fault_cases_v1.json"
_GRADER_SEEDS = _FIXTURES / "frontier_single_agent_fault_seeds_v1.json"


@pytest.fixture(scope="module")
def suite() -> FrontierFaultSuite:
    return load_frontier_fault_suite(
        reference_path=_REFERENCE,
        public_cases_path=_PUBLIC_CASES,
        grader_seeds_path=_GRADER_SEEDS,
    )


def _passing_trace(suite: FrontierFaultSuite, case_id: str) -> FaultTrace:
    case = suite.case(case_id)
    return FaultTrace(
        case_id=case.case_id,
        reference_digest=suite.reference.digest,
        terminal_status=case.expected_terminal_status,
        rule_ids=case.required_rule_ids,
        evidence_ids=case.required_evidence_ids,
        validation_statuses=("fail",),
        claim_statuses=("unresolved",),
        approval_binding_status=(
            "invalidated"
            if case.requires_approval_invalidation
            else "not_applicable"
        ),
        provider_calls=0,
        engine_invocations=0,
    )


def test_reference_and_public_fixture_are_frozen_and_separated(
    suite: FrontierFaultSuite,
) -> None:
    reference = suite.reference
    public = json.loads(_PUBLIC_CASES.read_text(encoding="utf-8"))

    assert reference.provider_mode == "fixture_only"
    assert reference.provider_model == "not_invoked"
    assert set(reference.budget.values()) == {0}
    assert len(reference.digest) == 64
    assert len(suite.cases) == len(suite.grader_only_seeds) == 12
    assert {case.case_id for case in suite.cases} == {
        seed.case_id for seed in suite.grader_only_seeds
    }
    assert "seeds" not in public
    assert "defect_class" not in _PUBLIC_CASES.read_text(encoding="utf-8")


def test_each_seeded_fault_gets_the_declared_safe_terminal_outcome(
    suite: FrontierFaultSuite,
) -> None:
    grades = tuple(
        grade_fault_trace(suite, _passing_trace(suite, case.case_id))
        for case in suite.cases
    )
    summary = summarize_fault_grades(suite, grades)

    assert all(grade.passed for grade in grades)
    assert not any(grade.false_pass for grade in grades)
    assert summary["case_count"] == 12
    assert summary["passed_case_count"] == 12
    assert summary["false_pass_count"] == 0
    assert summary["terminal_confusion_by_domain"] == {
        "scientific": {
            "case_count": 8,
            "correct_block_or_fail": 8,
            "incorrect_terminal_or_gate": 0,
            "false_pass": 0,
        },
        "evidence": {
            "case_count": 1,
            "correct_block_or_fail": 1,
            "incorrect_terminal_or_gate": 0,
            "false_pass": 0,
        },
        "approval": {
            "case_count": 1,
            "correct_block_or_fail": 1,
            "incorrect_terminal_or_gate": 0,
            "false_pass": 0,
        },
        "parser": {
            "case_count": 1,
            "correct_block_or_fail": 1,
            "incorrect_terminal_or_gate": 0,
            "false_pass": 0,
        },
        "provider": {
            "case_count": 1,
            "correct_block_or_fail": 1,
            "incorrect_terminal_or_gate": 0,
            "false_pass": 0,
        },
    }


@pytest.mark.parametrize("case_id", ["P3-F01", "P3-F09", "P3-F10"])
def test_red_gate_cannot_be_promoted_to_a_supported_completion(
    suite: FrontierFaultSuite,
    case_id: str,
) -> None:
    trace = replace(
        _passing_trace(suite, case_id),
        terminal_status="completed",
        claim_statuses=("supported",),
    )

    grade = grade_fault_trace(suite, trace)

    assert grade.passed is False
    assert grade.false_pass is True
    assert "frontier.terminal.expected_block" in grade.rule_ids
    assert "frontier.claim.red_gate_success" in grade.rule_ids


def test_grader_rejects_missing_evidence_approval_bypass_and_live_use(
    suite: FrontierFaultSuite,
) -> None:
    trace = replace(
        _passing_trace(suite, "P3-F10"),
        evidence_ids=(),
        approval_binding_status="bypassed",
        provider_calls=1,
        engine_invocations=1,
    )

    grade = grade_fault_trace(suite, trace)

    assert grade.passed is False
    assert grade.false_pass is False
    assert set(grade.rule_ids) >= {
        "frontier.authority.provider_call",
        "frontier.authority.engine_invocation",
        "frontier.evidence.required_missing",
        "frontier.approval.invalidation_required",
        "frontier.approval.bypass",
    }


def test_public_fixture_cannot_carry_grader_only_metadata(tmp_path: Path) -> None:
    public = json.loads(_PUBLIC_CASES.read_text(encoding="utf-8"))
    public["seeds"] = []
    contaminated = tmp_path / "public.json"
    contaminated.write_text(json.dumps(public), encoding="utf-8")

    with pytest.raises(ValueError, match="grader-only"):
        load_frontier_fault_suite(
            reference_path=_REFERENCE,
            public_cases_path=contaminated,
            grader_seeds_path=_GRADER_SEEDS,
        )
