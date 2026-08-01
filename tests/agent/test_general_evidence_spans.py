from __future__ import annotations

from chemsmart.agent.source_spans import (
    EvidenceSelectionBinding,
    ImmutableSourceDocument,
    evidence_selection_scope,
    report_bound_evidence_gap,
    select_bound_evidence_spans,
    select_evidence_spans,
    source_document_scope,
    tool_input_json_schema,
)


def test_general_evidence_selector_returns_hashes_not_source_prose() -> None:
    document = ImmutableSourceDocument.from_text(
        "paper-main",
        "Architecture evidence.\nFailure evidence.\nUnrelated prose.\n",
    )
    with source_document_scope((document,)):
        result = select_evidence_spans(
            source_id=document.source_id,
            source_sha256=document.sha256,
            spans=(
                {"start_line": 1, "end_line": 1},
                {"start_line": 2, "end_line": 2},
            ),
            claim_ids=("claim.architecture", "claim.failure"),
            purpose="frontier harness evidence",
        )

    assert result["status"] == "extracted"
    assert result["source_evidence"]["aggregate_line_count"] == 2
    assert "Architecture evidence" not in str(result)
    assert len(result["source_evidence"]["aggregate_excerpt_sha256"]) == 64


def test_general_evidence_selector_rejects_reordered_claim_ids() -> None:
    document = ImmutableSourceDocument.from_text("paper-main", "Evidence.\n")
    with source_document_scope((document,)):
        result = select_evidence_spans(
            source_id=document.source_id,
            source_sha256=document.sha256,
            spans=({"start_line": 1, "end_line": 1},),
            claim_ids=("claim.z", "claim.a"),
            purpose="audit",
        )

    assert result["status"] == "blocked_missing_evidence"
    assert result["blocking_issues"][0]["rule_id"] == (
        "paper.claim.claim_ids_invalid"
    )


def test_general_selector_has_closed_tool_schema() -> None:
    schema = tool_input_json_schema("select_evidence_spans")

    assert schema is not None
    assert schema["additionalProperties"] is False
    assert schema["properties"]["spans"]["maxItems"] == 8


def test_bound_selector_keeps_claim_contract_out_of_model_arguments() -> None:
    document = ImmutableSourceDocument.from_text(
        "paper-main",
        "Architecture evidence.\nFailure evidence.\n",
    )
    binding = EvidenceSelectionBinding(
        source_id=document.source_id,
        source_sha256=document.sha256,
        claim_ids=("claim.architecture", "claim.failure"),
        purpose="bounded specialist evidence",
    )
    with source_document_scope((document,)), evidence_selection_scope(binding):
        result = select_bound_evidence_spans(
            spans=(
                {"start_line": 1, "end_line": 1},
                {"start_line": 2, "end_line": 2},
            )
        )

    assert result["status"] == "extracted"
    assert result["claim_ids"] == ["claim.architecture", "claim.failure"]
    schema = tool_input_json_schema("select_bound_evidence_spans")
    assert schema is not None
    assert set(schema["properties"]) == {"spans"}


def test_bound_selector_fails_closed_without_host_binding() -> None:
    result = select_bound_evidence_spans(
        spans=({"start_line": 1, "end_line": 1},)
    )

    assert result["status"] == "blocked_missing_evidence"
    assert result["blocking_issues"][0]["rule_id"] == (
        "paper.claim.binding_missing"
    )


def test_bound_gap_report_preserves_claims_without_fabricated_locator() -> None:
    document = ImmutableSourceDocument.from_text("paper-main", "Unrelated.\n")
    binding = EvidenceSelectionBinding(
        source_id=document.source_id,
        source_sha256=document.sha256,
        claim_ids=("claim.missing",),
        purpose="honest missing-evidence stop",
    )
    with evidence_selection_scope(binding):
        result = report_bound_evidence_gap("not_present_in_view")

    assert result["status"] == "blocked_missing_evidence"
    assert result["claim_ids"] == ["claim.missing"]
    assert result["source_evidence"]["locators"] == []
    schema = tool_input_json_schema("report_bound_evidence_gap")
    assert schema is not None
    assert schema["properties"]["reason"]["enum"] == [
        "not_present_in_view",
        "source_conflict",
        "source_unreadable",
    ]
