from __future__ import annotations

import hashlib
import json

import pytest

from chemsmart.agent.source_spans import (
    EvidenceCharacterRangeV2,
    ImmutableSourceDocument,
    RULE_HASH_MISMATCH,
    RULE_RANGE_INVALID,
    RULE_REGISTRY_MISSING,
    RULE_SOURCE_MISSING,
    build_evidence_character_range_v2,
    extract_project_protocol_spans,
    source_document_scope,
    tool_input_json_schema,
    verify_evidence_character_range_v2,
)


def _document() -> ImmutableSourceDocument:
    return ImmutableSourceDocument.from_text(
        "paper-main-v1",
        "Unrelated B3LYP/6-31G(d) comparison.\n"
        "An ultrafine (99,590) integration grid was used.\n"
        "All target structures were optimized with M08-HX.\n"
        "Unrelated discussion.\n"
        "The pcseg-2 basis set and harmonic frequency analysis were used.\n",
    )


def _extract(
    document: ImmutableSourceDocument,
    *,
    source_id: str | None = None,
    source_sha256: str | None = None,
    spans: list[dict[str, int]] | None = None,
) -> dict[str, object]:
    return extract_project_protocol_spans(
        source_id=source_id or document.source_id,
        source_sha256=source_sha256 or document.sha256,
        spans=(
            spans
            if spans is not None
            else [
                {"start_line": 2, "end_line": 3},
                {"start_line": 5, "end_line": 5},
            ]
        ),
        project_name="azide_allene",
        program="gaussian",
        profile="paper",
    )


def test_resolves_non_contiguous_exact_spans_without_returning_source_text() -> None:
    document = _document()

    with source_document_scope([document]):
        result = _extract(document)

    assert result["ok"] is True
    assert result["status"] == "extracted"
    assert "source_excerpt" not in result
    assert result["method"] == {
        "functional": "m08hx",
        "dispersion": None,
        "functional_route": "m08hx",
        "basis": "pcseg-2",
        "heavy_elements": [],
        "heavy_elements_basis": None,
        "light_elements_basis": None,
        "solvent_model": None,
        "solvent_id": None,
        "freq": True,
        "integration_grid": "ultrafine",
    }
    evidence = result["source_evidence"]
    assert evidence["source_id"] == document.source_id
    assert evidence["document_sha256"] == document.sha256
    assert evidence["aggregate_line_count"] == 3
    assert len(evidence["locators"]) == 2

    exact_spans = (
        "An ultrafine (99,590) integration grid was used.\n"
        "All target structures were optimized with M08-HX.\n"
        "The pcseg-2 basis set and harmonic frequency analysis were used.\n"
    )
    assert evidence["aggregate_excerpt_sha256"] == hashlib.sha256(
        exact_spans.encode("utf-8")
    ).hexdigest()
    assert evidence["aggregate_byte_count"] == len(exact_spans.encode("utf-8"))
    assert evidence["aggregation_rule"] == "utf8_spans_lf_join_v1"


def test_column_locator_isolates_one_method_from_a_shared_pdf_text_line() -> None:
    line = "M08-HX, target functional; and wB97X-D, comparison functional."
    document = ImmutableSourceDocument.from_text("shared-line", line + "\n")
    with source_document_scope([document]):
        result = _extract(
            document,
            spans=[
                {
                    "start_line": 1,
                    "end_line": 1,
                    "start_column": 1,
                    "end_column": len("M08-HX"),
                }
            ],
        )

    assert result["status"] == "extracted"
    assert result["method"]["functional"] == "m08hx"
    assert result["method_candidates"]["functional"] == ["m08hx"]
    locator = result["source_evidence"]["locators"][0]
    assert locator["kind"] == "line_column_range"
    assert locator["start_column"] == 1
    assert locator["end_column"] == len("M08-HX")


def test_pdf_form_feed_remains_content_not_a_synthetic_line_boundary() -> None:
    document = ImmutableSourceDocument.from_text(
        "pdf-text",
        "page-one\n\fM08-HX/pcseg-2\n",
    )
    with source_document_scope([document]):
        result = _extract(
            document,
            spans=[{"start_line": 2, "end_line": 2}],
        )

    assert result["status"] == "extracted"
    assert result["method"]["functional"] == "m08hx"
    assert result["method"]["basis"] == "pcseg-2"
    assert result["source_evidence"]["locators"][0]["start_line"] == 2


def test_provider_schema_contains_only_opaque_selector_and_project_fields() -> None:
    schema = tool_input_json_schema("extract_project_protocol_spans")

    assert schema is not None
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {
        "source_id",
        "source_sha256",
        "spans",
        "project_name",
        "program",
        "profile",
    }
    assert set(schema["required"]) == set(schema["properties"])
    serialized = json.dumps(schema, sort_keys=True)
    assert '"text"' not in serialized
    assert '"path"' not in serialized
    assert schema["properties"]["spans"]["minItems"] == 1
    assert schema["properties"]["spans"]["maxItems"] == 8


def test_missing_registry_fails_closed() -> None:
    document = _document()

    result = _extract(document)

    assert result["ok"] is False
    assert result["blocking_issues"][0]["rule_id"] == RULE_REGISTRY_MISSING


def test_unknown_source_and_hash_mismatch_fail_closed() -> None:
    document = _document()
    with source_document_scope([document]):
        unknown = _extract(document, source_id="unknown-source")
        mismatched = _extract(document, source_sha256="0" * 64)

    assert unknown["blocking_issues"][0]["rule_id"] == RULE_SOURCE_MISSING
    assert mismatched["blocking_issues"][0]["rule_id"] == RULE_HASH_MISMATCH


@pytest.mark.parametrize(
    "spans",
    [
        [],
        [{"start_line": 0, "end_line": 1}],
        [{"start_line": 3, "end_line": 2}],
        [{"start_line": 1, "end_line": 6}],
        [
            {"start_line": 3, "end_line": 3},
            {"start_line": 2, "end_line": 2},
        ],
        [
            {"start_line": 2, "end_line": 3},
            {"start_line": 3, "end_line": 4},
        ],
        [{"start_line": 1, "end_line": 1, "text": 1}],
        [
            {
                "start_line": 1,
                "end_line": 1,
                "start_column": 1,
            }
        ],
        [
            {
                "start_line": 1,
                "end_line": 2,
                "start_column": 1,
                "end_column": 2,
            }
        ],
        [
            {
                "start_line": 1,
                "end_line": 1,
                "start_column": 1,
                "end_column": 10_000,
            }
        ],
    ],
)
def test_invalid_ranges_fail_closed(spans: list[dict[str, int]]) -> None:
    document = _document()
    with source_document_scope([document]):
        result = _extract(document, spans=spans)

    assert result["ok"] is False
    assert result["blocking_issues"][0]["rule_id"] == RULE_RANGE_INVALID


def test_registration_rejects_wrong_digest_and_invalid_utf8_text() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        ImmutableSourceDocument(
            source_id="paper-main-v1",
            text="exact text",
            sha256="0" * 64,
        )
    with pytest.raises(ValueError, match="valid UTF-8"):
        ImmutableSourceDocument.from_text("paper-main-v1", "bad-surrogate-\ud800")


def test_scope_is_removed_after_context_exit() -> None:
    document = _document()
    with source_document_scope([document]):
        assert _extract(document)["ok"] is True

    assert _extract(document)["blocking_issues"][0]["rule_id"] == (
        RULE_REGISTRY_MISSING
    )


def test_character_range_binds_json_pointer_unicode_offsets_and_exact_bytes() -> None:
    artifact = json.dumps(
        {"article": {"sections": ["alpha β 🧪 omega"]}},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    target = "alpha β 🧪 omega"
    selected = "β 🧪"
    start = target.index(selected)

    evidence_range = build_evidence_character_range_v2(
        artifact,
        json_pointer="/article/sections/0",
        unicode_start=start,
        unicode_end=start + len(selected),
    )

    assert evidence_range.artifact_sha256 == hashlib.sha256(artifact).hexdigest()
    assert evidence_range.selected_text_sha256 == hashlib.sha256(
        selected.encode("utf-8")
    ).hexdigest()
    assert evidence_range.rendered_locator == (
        f"sha256:{evidence_range.artifact_sha256}"
        "#json-pointer=%2Farticle%2Fsections%2F0&unicode=6:9"
    )
    verify_evidence_character_range_v2(artifact, evidence_range)


def test_character_range_supports_canonical_json_pointer_escapes() -> None:
    artifact = b'{"a/b":{"~key":"exact evidence"}}'

    evidence_range = build_evidence_character_range_v2(
        artifact,
        json_pointer="/a~1b/~0key",
        unicode_start=0,
        unicode_end=5,
    )

    assert evidence_range.json_pointer == "/a~1b/~0key"
    verify_evidence_character_range_v2(artifact, evidence_range)


def test_character_range_rejects_artifact_and_receipt_tampering() -> None:
    artifact = b'{"text":"selected evidence"}'
    evidence_range = build_evidence_character_range_v2(
        artifact,
        json_pointer="/text",
        unicode_start=0,
        unicode_end=8,
    )

    with pytest.raises(ValueError, match="does not replay"):
        verify_evidence_character_range_v2(
            b'{"text":"selected Evidence"}',
            evidence_range,
        )

    tampered = evidence_range.model_dump(mode="python")
    tampered["selected_text_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="digest mismatch"):
        EvidenceCharacterRangeV2.model_validate(tampered)


@pytest.mark.parametrize(
    ("artifact", "pointer", "start", "end", "message"),
    (
        (b'{"text":"abc"}', "/missing", 0, 1, "does not exist"),
        (b'{"text":"abc"}', "/bad~2escape", 0, 1, "non-canonical escape"),
        (b'{"text":"abc"}', "/text", 0, 4, "outside"),
        (b'{"text":"abc","text":"def"}', "/text", 0, 1, "duplicate"),
    ),
)
def test_character_range_fails_closed_on_ambiguous_or_invalid_selection(
    artifact: bytes,
    pointer: str,
    start: int,
    end: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_evidence_character_range_v2(
            artifact,
            json_pointer=pointer,
            unicode_start=start,
            unicode_end=end,
        )
