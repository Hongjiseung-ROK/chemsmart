from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from chemsmart.agent.adaptive_api_campaign import (
    adaptive_public_literature_hypothesis_sha256,
    build_adaptive_public_literature_hypothesis_v1,
)
from chemsmart.agent.literature_acquisition import (
    BibliographicAuthorV1,
    BibliographicConcordanceStatus,
    BibliographicCorrectionRelationV1,
    CrossrefRepresentation,
    CrossrefResponseStatus,
    build_bibliographic_concordance_receipt_v1,
    build_bibliographic_observation_v1,
    build_crossref_metadata_request_v1,
    build_crossref_response_receipt_v1,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hypothesis(representation: str):
    return build_adaptive_public_literature_hypothesis_v1(
        hypothesis_id=f"h.crossref.{representation}",
        representation=representation,
        prompt_sha256=_digest(f"{representation}:prompt"),
        input_state_sha256=_digest(f"{representation}:input"),
        expected_observation_sha256=_digest(f"{representation}:expected"),
        precondition_sha256s=(_digest(f"{representation}:precondition"),),
    )


def _crossref_json_body(
    *,
    doi: str = "10.1000/example",
    relation: dict[str, object] | None = None,
) -> bytes:
    return json.dumps(
        {
            "status": "ok",
            "message": {
                "DOI": doi,
                "title": ["A Reproducible Test Paper"],
                "author": [
                    {"given": "Ada", "family": "Lovelace"},
                    {"given": "Alan M.", "family": "Turing"},
                ],
                "published-online": {"date-parts": [[2025, 2, 3]]},
                "license": [
                    {
                        "URL": (
                            "http://creativecommons.org/licenses/by/4.0/"
                        )
                    }
                ],
                "relation": relation or {},
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _json_receipt(*, body: bytes | None = None):
    hypothesis = _hypothesis("json")
    request = build_crossref_metadata_request_v1(
        request_id="crossref-json-1",
        adaptive_hypothesis_sha256=hypothesis.hypothesis_sha256,
        doi="https://doi.org/10.1000/EXAMPLE",
        representation=CrossrefRepresentation.JSON,
    )
    receipt = build_crossref_response_receipt_v1(
        request,
        http_status=200,
        body=body or _crossref_json_body(),
        media_type="application/json; charset=utf-8",
    )
    return hypothesis, request, receipt


def _publisher_observation(**overrides):
    values = {
        "observation_id": "publisher-metadata:1",
        "source_provider": "publisher-metadata",
        "source_artifact_sha256": _digest("publisher metadata bytes"),
        "doi": "10.1000/example",
        "title": "A reproducible test paper",
        "authors": (
            BibliographicAuthorV1(given="A.", family="Lovelace"),
            BibliographicAuthorV1(given="A. M.", family="Turing"),
        ),
        "publication_year": 2025,
        "license_reported": True,
        "license_urls": (
            "https://creativecommons.org/licenses/by/4.0/",
        ),
        "correction_relations_checked": True,
        "correction_relations": (),
    }
    values.update(overrides)
    return build_bibliographic_observation_v1(**values)


def test_public_crossref_request_is_hypothesis_bound_without_credential_lease() -> None:
    hypothesis, request, _ = _json_receipt()

    assert hypothesis.hypothesis_sha256 == (
        adaptive_public_literature_hypothesis_sha256(hypothesis)
    )
    assert hypothesis.credential_lease_required is False
    assert hypothesis.transport_attempt_limit is None
    assert request.adaptive_hypothesis_sha256 == hypothesis.hypothesis_sha256
    assert request.credential_lease_required is False
    assert request.endpoint_url == (
        "https://api.crossref.org/works/10.1000%2Fexample"
    )
    assert "credential" not in request.model_dump(mode="json")


def test_crossref_json_receipt_hashes_bytes_and_normalizes_metadata() -> None:
    body = _crossref_json_body()
    _, _, receipt = _json_receipt(body=body)

    assert receipt.status is CrossrefResponseStatus.VALID
    assert receipt.credential_lease_used is False
    assert receipt.body_sha256 == hashlib.sha256(body).hexdigest()
    assert receipt.body_size_bytes == len(body)
    assert receipt.observation is not None
    assert receipt.observation.doi == "10.1000/example"
    assert receipt.observation.publication_year == 2025
    assert receipt.observation.license_urls == (
        "https://creativecommons.org/licenses/by/4.0",
    )
    assert receipt.observation.correction_relations_checked is True
    assert body.decode("utf-8") not in receipt.model_dump_json()


def test_crossref_bibtex_receipt_is_typed_but_does_not_invent_coverage() -> None:
    hypothesis = _hypothesis("bibtex")
    request = build_crossref_metadata_request_v1(
        request_id="crossref-bibtex-1",
        adaptive_hypothesis_sha256=hypothesis.hypothesis_sha256,
        doi="10.1000/example",
        representation=CrossrefRepresentation.BIBTEX,
    )
    body = b"""@article{example,
 title={A {Reproducible} Test Paper},
 author={Lovelace, Ada and Turing, Alan M.},
 year={2025},
 doi={10.1000/EXAMPLE}
}
"""

    receipt = build_crossref_response_receipt_v1(
        request,
        http_status=200,
        body=body,
        media_type="application/x-bibtex",
    )

    assert request.endpoint_url.endswith("/transform/application/x-bibtex")
    assert receipt.status is CrossrefResponseStatus.VALID
    assert receipt.observation is not None
    assert receipt.observation.doi == "10.1000/example"
    assert receipt.observation.license_reported is False
    assert receipt.observation.correction_relations_checked is False


def test_bibliographic_concordance_accepts_normalized_independent_sources() -> None:
    _, _, crossref = _json_receipt()
    assert crossref.observation is not None

    receipt = build_bibliographic_concordance_receipt_v1(
        (crossref.observation, _publisher_observation()),
        concordance_id="concordance:valid",
    )

    assert receipt.status is BibliographicConcordanceStatus.VALID
    assert receipt.rule_ids == ()
    assert receipt.canonical_record is not None
    assert receipt.canonical_record.authors == (
        "lovelace|a",
        "turing|am",
    )


@pytest.mark.parametrize(
    ("overrides", "rule_id"),
    (
        ({"doi": "10.1000/different"}, "bibliography.concordance.doi_mismatch"),
        ({"title": "A different paper"}, "bibliography.concordance.title_mismatch"),
        (
            {
                "authors": (
                    BibliographicAuthorV1(given="Grace", family="Hopper"),
                )
            },
            "bibliography.concordance.authors_mismatch",
        ),
        ({"publication_year": 2024}, "bibliography.concordance.year_mismatch"),
        (
            {"license_urls": ("https://creativecommons.org/licenses/by-nc/4.0",)},
            "bibliography.concordance.license_mismatch",
        ),
        (
            {"license_reported": False, "license_urls": ()},
            "bibliography.concordance.license_missing",
        ),
        (
            {"correction_relations_checked": False},
            "bibliography.concordance.correction_relation_unchecked",
        ),
    ),
)
def test_bibliographic_concordance_fails_closed_per_field(
    overrides: dict[str, object],
    rule_id: str,
) -> None:
    _, _, crossref = _json_receipt()
    assert crossref.observation is not None

    receipt = build_bibliographic_concordance_receipt_v1(
        (crossref.observation, _publisher_observation(**overrides)),
        concordance_id="concordance:invalid",
    )

    assert receipt.status is BibliographicConcordanceStatus.INVALID
    assert receipt.canonical_record is None
    assert rule_id in receipt.rule_ids


def test_correction_or_retraction_relation_prevents_valid_concordance() -> None:
    relation = BibliographicCorrectionRelationV1(
        relation_type="is-corrected-by",
        identifier_type="doi",
        identifier="10.1000/correction",
    )
    body = _crossref_json_body(
        relation={
            "is-corrected-by": [
                {"id-type": "doi", "id": "10.1000/correction"}
            ]
        }
    )
    _, _, crossref = _json_receipt(body=body)
    assert crossref.observation is not None
    publisher = _publisher_observation(correction_relations=(relation,))

    receipt = build_bibliographic_concordance_receipt_v1(
        (crossref.observation, publisher),
        concordance_id="concordance:corrected",
    )

    assert receipt.status is BibliographicConcordanceStatus.INVALID
    assert receipt.rule_ids == (
        "bibliography.concordance.correction_relation_present",
    )


def test_request_and_concordance_digests_detect_tampering() -> None:
    _, request, crossref = _json_receipt()
    request_body = request.model_dump(mode="python")
    request_body["doi"] = "10.1000/tampered"
    with pytest.raises(ValidationError, match="path is not canonical|digest mismatch"):
        type(request).model_validate(request_body)

    assert crossref.observation is not None
    concordance = build_bibliographic_concordance_receipt_v1(
        (crossref.observation, _publisher_observation()),
        concordance_id="concordance:tamper",
    )
    concordance_body = concordance.model_dump(mode="python")
    concordance_body["status"] = "invalid"
    with pytest.raises(ValidationError, match="not replayable"):
        type(concordance).model_validate(concordance_body)
