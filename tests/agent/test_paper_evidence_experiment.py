from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from chemsmart.agent.adaptive_api_campaign import (
    build_adaptive_network_budget_v1,
)
from chemsmart.agent.paper_evidence_experiment import (
    EvidenceExpectedOutcome,
    EvidenceGapReason,
    EvidenceLineRange,
    EvidenceViewMode,
    RequiredEvidenceGroup,
    build_case_adaptive_hypothesis,
    build_paper_evidence_case_v1,
    build_paper_evidence_manifest_v1,
    build_paper_evidence_prompt,
    grade_bound_evidence_case,
)
from chemsmart.agent.source_spans import ImmutableSourceDocument


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _document() -> ImmutableSourceDocument:
    return ImmutableSourceDocument.from_text(
        "elsevier:urea-w18:article-view-v1",
        "Context only.\n"
        "All calculations used ORCA.\n"
        "The B3LYP-D3(BJ) method was applied.\n"
        "No electronic state is stated in this test view.\n",
    )


def _extracted_case():
    return build_paper_evidence_case_v1(
        case_id="urea.method.program.targeted",
        claim_id="urea.method.program",
        claim_question="Which quantum-chemistry program is explicitly reported?",
        purpose="localize the reported program",
        comparator_id="urea.method.program.full",
        changed_factor="evidence_window",
        changed_factor_value="targeted",
        expected_outcome=EvidenceExpectedOutcome.EXTRACTED,
        view_mode=EvidenceViewMode.TARGETED,
        view_ranges=(EvidenceLineRange(start_line=1, end_line=3),),
        allowed_evidence_ranges=(EvidenceLineRange(start_line=2, end_line=2),),
        required_evidence_groups=(
            RequiredEvidenceGroup(
                group_id="program",
                alternatives=(EvidenceLineRange(start_line=2, end_line=2),),
            ),
        ),
        novelty_rationale=(
            "Tests one claim with an exact host-owned locator rather than an "
            "aggregate multi-claim locator set."
        ),
    )


def _blocked_case():
    return build_paper_evidence_case_v1(
        case_id="urea.state.multiplicity.full",
        claim_id="urea.state.multiplicity",
        claim_question="Is the structure multiplicity explicit in this source view?",
        purpose="check whether multiplicity is explicitly reported",
        comparator_id="urea.state.multiplicity.no-model-reference",
        changed_factor="evidence_selector",
        changed_factor_value="host_bound_model",
        expected_outcome=EvidenceExpectedOutcome.BLOCKED_MISSING_EVIDENCE,
        expected_gap_reason=EvidenceGapReason.NOT_PRESENT_IN_VIEW,
        view_mode=EvidenceViewMode.FULL_SOURCE,
        novelty_rationale=(
            "Measures honest view-local blocking for a consequential electronic "
            "state field."
        ),
    )


def _manifest(*cases):
    document = _document()
    return build_paper_evidence_manifest_v1(
        campaign_id="prp10:urea-w18:development-evidence-v1",
        paper_id="doi:10.1016-j.icarus.2023.115848",
        source_id=document.source_id,
        source_sha256=document.sha256,
        source_bundle_sha256=_digest("source-bundle"),
        prompt_template_version="urea-bound-evidence-v1",
        cases=cases,
    )


def test_case_builds_real_adaptive_hypothesis_with_all_runtime_hashes() -> None:
    document = _document()
    case = _extracted_case()
    manifest = _manifest(case)
    prompt = build_paper_evidence_prompt(manifest, case, document)
    budget = build_adaptive_network_budget_v1(
        max_context_tokens_per_request=16_000,
        max_output_tokens_per_request=2_048,
        task_wall_time_seconds=600,
    )

    hypothesis = build_case_adaptive_hypothesis(
        manifest=manifest,
        case=case,
        prompt_sha256=_digest(prompt),
        tool_schema_sha256=_digest("closed-tool-schema"),
        configuration_sha256=_digest("deepseek-v4-flash-thinking-high"),
        network_budget=budget,
    )

    assert hypothesis.hypothesis_id == f"hypothesis:{case.case_id}"
    assert hypothesis.prompt_sha256 == _digest(prompt)
    assert len(hypothesis.hypothesis_sha256) == 64
    assert hypothesis.hypothesis_sha256 not in hypothesis.precondition_sha256s
    assert "All calculations used ORCA." in prompt
    assert "exactly one claim" in prompt


def test_extracted_oracle_requires_preregistered_claim_specific_line() -> None:
    case = _extracted_case()
    manifest = _manifest(case)
    result = {
        "status": "extracted",
        "claim_ids": [case.claim_id],
        "purpose_sha256": _digest(case.purpose),
        "source_evidence": {
            "source_id": manifest.source_id,
            "document_sha256": manifest.source_sha256,
            "locators": [{"start_line": 2, "end_line": 2}],
        },
    }

    grade = grade_bound_evidence_case(
        manifest=manifest,
        case=case,
        tool_requests=(
            {"name": "select_bound_evidence_spans", "arguments": {"spans": []}},
        ),
        tool_outcomes=(
            {
                "name": "select_bound_evidence_spans",
                "status": "ok",
                "result": result,
            },
        ),
    )

    assert grade["oracle_passed"] is True
    assert grade["scientific_outcome"] == "evidence_localized"
    assert grade["scientific_readiness"] == "not_established"

    result["source_evidence"]["locators"] = [
        {"start_line": 3, "end_line": 3}
    ]
    wrong_line = grade_bound_evidence_case(
        manifest=manifest,
        case=case,
        tool_requests=({"name": "select_bound_evidence_spans"},),
        tool_outcomes=(
            {
                "name": "select_bound_evidence_spans",
                "status": "ok",
                "result": result,
            },
        ),
    )
    assert wrong_line["oracle_passed"] is False
    assert "experiment.oracle.evidence_outside_preregistered_lines" in (
        wrong_line["rule_ids"]
    )


def test_blocked_oracle_preserves_view_local_scope_and_zero_locators() -> None:
    case = _blocked_case()
    manifest = _manifest(case)
    result = {
        "status": "blocked_missing_evidence",
        "claim_ids": [case.claim_id],
        "blocking_issues": [
            {
                "rule_id": "paper.claim.model_reported_gap",
                "reason": "not_present_in_view",
            }
        ],
        "source_evidence": {
            "source_id": manifest.source_id,
            "document_sha256": manifest.source_sha256,
            "locators": [],
        },
    }

    grade = grade_bound_evidence_case(
        manifest=manifest,
        case=case,
        tool_requests=(
            {
                "name": "report_bound_evidence_gap",
                "arguments": {"reason": "not_present_in_view"},
            },
        ),
        tool_outcomes=(
            {
                "name": "report_bound_evidence_gap",
                "status": "ok",
                "result": result,
            },
        ),
    )

    assert grade == {
        "oracle_passed": True,
        "rule_ids": [],
        "scientific_outcome": "blocked_missing_evidence",
        "scientific_readiness": "not_established",
        "absence_scope": "presented_source_view_only",
        "selected_lines": [],
    }


def test_blocked_case_cannot_smuggle_expected_evidence_lines() -> None:
    with pytest.raises(
        ValidationError,
        match="blocked case cannot preregister evidence lines",
    ):
        build_paper_evidence_case_v1(
            case_id="urea.invalid.blocked",
            claim_id="urea.state.charge",
            claim_question="Is charge present?",
            purpose="check charge",
            comparator_id="urea.invalid.control",
            changed_factor="evidence_selector",
            changed_factor_value="host_bound_model",
            expected_outcome=EvidenceExpectedOutcome.BLOCKED_MISSING_EVIDENCE,
            expected_gap_reason=EvidenceGapReason.NOT_PRESENT_IN_VIEW,
            view_mode=EvidenceViewMode.FULL_SOURCE,
            allowed_evidence_ranges=(
                EvidenceLineRange(start_line=1, end_line=1),
            ),
            novelty_rationale="Negative contract case.",
        )
