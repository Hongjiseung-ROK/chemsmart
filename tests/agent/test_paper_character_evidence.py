from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from chemsmart.agent.adaptive_api_campaign import (
    build_adaptive_network_budget_v1,
)
from chemsmart.agent.paper_character_evidence import (
    RequiredCharacterEvidenceGroupV1,
    build_character_case_adaptive_hypothesis,
    build_character_selection_binding,
    build_paper_character_case_v1,
    build_paper_character_manifest_v1,
    build_paper_character_prompt,
    character_evidence_scope,
    grade_character_evidence_case,
    report_bound_character_evidence_gap,
    select_bound_evidence_characters,
    verify_paper_character_manifest_source,
)
from chemsmart.agent.paper_evidence_experiment import (
    EvidenceExpectedOutcome,
    EvidenceGapReason,
    EvidenceViewMode,
)
from chemsmart.agent.source_spans import build_evidence_character_range_v2


_POINTER = "/article/text"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _artifact() -> bytes:
    return json.dumps(
        {
            "article": {
                "text": (
                    "Context. All calculations were performed with ORCA 5.0.4. "
                    "The B3LYP functional with D3(BJ) dispersion and the "
                    "ma-def2-TZVP basis was used. Frequency calculations "
                    "confirmed stationary points. IRC is not reported."
                )
            }
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _text() -> str:
    return json.loads(_artifact().decode("utf-8"))["article"]["text"]


def _range(fragment: str, *, pad: int = 0):
    text = _text()
    start = max(0, text.index(fragment) - pad)
    end = min(len(text), text.index(fragment) + len(fragment) + pad)
    return build_evidence_character_range_v2(
        _artifact(),
        json_pointer=_POINTER,
        unicode_start=start,
        unicode_end=end,
    )


def _extracted_case(*, mode: EvidenceViewMode = EvidenceViewMode.TARGETED):
    allowed = _range("All calculations were performed with ORCA 5.0.4.", pad=9)
    required = _range("ORCA 5.0.4")
    return build_paper_character_case_v1(
        case_id=f"urea.program.{mode.value}",
        claim_id="urea.program",
        claim_question="Which program and version are explicitly reported?",
        purpose="localize the exact program and version",
        comparator_id=(
            "urea.program.full_source"
            if mode is EvidenceViewMode.TARGETED
            else "urea.program.targeted"
        ),
        changed_factor_value=mode,
        expected_outcome=EvidenceExpectedOutcome.EXTRACTED,
        view_mode=mode,
        view_ranges=(allowed,) if mode is EvidenceViewMode.TARGETED else (),
        allowed_evidence_ranges=(allowed,),
        required_evidence_groups=(
            RequiredCharacterEvidenceGroupV1(
                group_id="program_version",
                alternatives=(required,),
            ),
        ),
        novelty_rationale=(
            "Tests exact Unicode evidence replay when a provider stores the full "
            "article in one JSON string."
        ),
    )


def _blocked_case():
    return build_paper_character_case_v1(
        case_id="urea.irc.full_source",
        claim_id="urea.irc.protocol",
        claim_question="Which IRC protocol is explicitly reported?",
        purpose="test honest blocking when an IRC protocol is absent",
        comparator_id="urea.irc.targeted",
        changed_factor_value=EvidenceViewMode.FULL_SOURCE,
        expected_outcome=EvidenceExpectedOutcome.BLOCKED_MISSING_EVIDENCE,
        expected_gap_reason=EvidenceGapReason.NOT_PRESENT_IN_VIEW,
        view_mode=EvidenceViewMode.FULL_SOURCE,
        novelty_rationale="Negative control for absent protocol evidence.",
    )


def _manifest(*cases):
    return build_paper_character_manifest_v1(
        artifact_bytes=_artifact(),
        source_json_pointer=_POINTER,
        campaign_id="urea-character-evidence-v1",
        paper_id="doi:10.1016-j.icarus.2023.115848",
        source_id="elsevier:urea-w18:full-text-json-v1",
        source_bundle_sha256=_digest("source-bundle"),
        prompt_template_version="paper-character-evidence-v1",
        cases=cases,
    )


def _tool_exchange(name: str, result: dict[str, object]):
    return (
        ({"name": name, "arguments": {}},),
        ({"name": name, "status": "ok", "result": result},),
    )


def test_manifest_replays_exact_json_pointer_unicode_ranges_and_prompt() -> None:
    case = _extracted_case()
    manifest = _manifest(case)

    assert verify_paper_character_manifest_source(_artifact(), manifest) == _text()
    prompt = build_paper_character_prompt(_artifact(), manifest, case)
    assert "<CHARACTERS" in prompt
    assert "ORCA 5.0.4" in prompt
    assert "state only the evidence-local outcome" in prompt
    assert manifest.source_artifact_sha256 == hashlib.sha256(_artifact()).hexdigest()


def test_host_bound_selector_returns_replayable_content_addressed_locator() -> None:
    case = _extracted_case()
    manifest = _manifest(case)
    binding = build_character_selection_binding(manifest, case)
    required = case.required_evidence_groups[0].alternatives[0]

    with character_evidence_scope(artifact_bytes=_artifact(), binding=binding):
        result = select_bound_evidence_characters(
            [
                {
                    "unicode_start": required.unicode_start,
                    "unicode_end": required.unicode_end,
                }
            ]
        )

    requests, outcomes = _tool_exchange(
        "select_bound_evidence_characters", result
    )
    grade = grade_character_evidence_case(
        manifest=manifest,
        case=case,
        tool_requests=requests,
        tool_outcomes=outcomes,
    )
    assert result["ok"] is True
    assert grade["oracle_passed"] is True
    assert grade["scientific_outcome"] == "evidence_localized"
    assert grade["maximum_state"] == "validated_source_evidence"


def test_selector_rejects_a_range_outside_targeted_view() -> None:
    case = _extracted_case()
    manifest = _manifest(case)
    binding = build_character_selection_binding(manifest, case)
    start = _text().index("Frequency")

    with character_evidence_scope(artifact_bytes=_artifact(), binding=binding):
        result = select_bound_evidence_characters(
            [{"unicode_start": start, "unicode_end": start + len("Frequency")}]
        )

    assert result["ok"] is False
    assert result["blocking_issues"][0]["rule_id"] == (
        "paper.character.range_invalid"
    )


def test_grader_rejects_one_character_overlap_and_overlapping_locators() -> None:
    case = _extracted_case(mode=EvidenceViewMode.FULL_SOURCE)
    manifest = _manifest(case)
    binding = build_character_selection_binding(manifest, case)
    required = case.required_evidence_groups[0].alternatives[0]
    with character_evidence_scope(artifact_bytes=_artifact(), binding=binding):
        one_character = select_bound_evidence_characters(
            [
                {
                    "unicode_start": required.unicode_start,
                    "unicode_end": required.unicode_start + 1,
                }
            ]
        )
        first = required.unicode_start
        overlapping = select_bound_evidence_characters(
            [
                {"unicode_start": first, "unicode_end": required.unicode_end},
                {
                    "unicode_start": first + 1,
                    "unicode_end": required.unicode_end + 1,
                },
            ]
        )

    requests, outcomes = _tool_exchange(
        "select_bound_evidence_characters", one_character
    )
    grade = grade_character_evidence_case(
        manifest=manifest,
        case=case,
        tool_requests=requests,
        tool_outcomes=outcomes,
    )
    assert grade["oracle_passed"] is False
    assert "experiment.character.required_group_missing.program_version" in (
        grade["rule_ids"]
    )
    assert overlapping["ok"] is False


def test_blocked_case_requires_exact_reason_and_no_locator() -> None:
    case = _blocked_case()
    manifest = _manifest(case)
    binding = build_character_selection_binding(manifest, case)
    with character_evidence_scope(artifact_bytes=_artifact(), binding=binding):
        result = report_bound_character_evidence_gap("not_present_in_view")

    requests, outcomes = _tool_exchange(
        "report_bound_character_evidence_gap", result
    )
    grade = grade_character_evidence_case(
        manifest=manifest,
        case=case,
        tool_requests=requests,
        tool_outcomes=outcomes,
    )
    assert grade["oracle_passed"] is True
    assert grade["scientific_outcome"] == "blocked_missing_evidence"
    assert grade["absence_scope"] == "presented_source_view_only"


def test_manifest_fails_closed_on_artifact_mutation() -> None:
    case = _extracted_case()
    manifest = _manifest(case)
    mutated = _artifact().replace(b"ORCA", b"orca", 1)

    with pytest.raises(ValueError, match="artifact digest mismatch"):
        verify_paper_character_manifest_source(mutated, manifest)


def test_blocked_case_cannot_smuggle_gold_character_ranges() -> None:
    with pytest.raises(
        ValidationError,
        match="blocked case cannot preregister evidence ranges",
    ):
        build_paper_character_case_v1(
            case_id="urea.invalid.blocked",
            claim_id="urea.invalid",
            claim_question="Is a missing claim present?",
            purpose="test the negative contract",
            comparator_id="urea.invalid.control",
            changed_factor_value=EvidenceViewMode.FULL_SOURCE,
            expected_outcome=EvidenceExpectedOutcome.BLOCKED_MISSING_EVIDENCE,
            expected_gap_reason=EvidenceGapReason.NOT_PRESENT_IN_VIEW,
            view_mode=EvidenceViewMode.FULL_SOURCE,
            allowed_evidence_ranges=(_range("ORCA 5.0.4"),),
            novelty_rationale="Must fail closed.",
        )


def test_case_builds_adaptive_hypothesis_bound_to_manifest_and_budget() -> None:
    case = _extracted_case()
    manifest = _manifest(case)
    prompt = build_paper_character_prompt(_artifact(), manifest, case)
    budget = build_adaptive_network_budget_v1(
        max_context_tokens_per_request=32_000,
        max_output_tokens_per_request=2_048,
        task_wall_time_seconds=600,
    )
    hypothesis = build_character_case_adaptive_hypothesis(
        manifest=manifest,
        case=case,
        prompt_sha256=_digest(prompt),
        tool_schema_sha256=_digest("character-tools"),
        configuration_sha256=_digest("deepseek-v4-flash-thinking-high"),
        network_budget=budget,
    )

    assert hypothesis.hypothesis_id == f"hypothesis:{case.case_id}"
    assert hypothesis.prompt_sha256 == _digest(prompt)
    assert manifest.source_artifact_sha256 in hypothesis.precondition_sha256s
    assert budget.budget_sha256 in hypothesis.precondition_sha256s
