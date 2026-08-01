from __future__ import annotations

import hashlib

import pytest

from chemsmart.agent.api_access import ApiProvider
from chemsmart.agent.literature_acquisition import (
    LITERATURE_PROVIDER_ORIGINS,
    LiteratureAcquisitionAction,
    LiteratureAcquisitionClient,
    LiteratureAcquisitionRequest,
    LiteratureBudgetExhaustedError,
    LiteratureContentClass,
    LiteratureContentState,
    LiteratureDigestBasis,
    LiteratureRequestConflictError,
    LiteratureResponseStatus,
    LiteratureTransportBudget,
    LiteratureTransportRequest,
    LiteratureTransportResponse,
    PrivateStoreWriteReceipt,
    TransportSourceObservation,
    merge_literature_response_receipts,
)


SECRET = "fixture-secret-never-persist"


class StaticTransport:
    def __init__(self, response: LiteratureTransportResponse) -> None:
        self.response = response
        self.requests: list[LiteratureTransportRequest] = []
        self.credential_observed = False

    def send(
        self,
        request: LiteratureTransportRequest,
        *,
        credential: str,
    ) -> LiteratureTransportResponse:
        assert credential == SECRET
        self.credential_observed = True
        self.requests.append(request)
        return self.response


class MemoryPrivateStore:
    def __init__(self) -> None:
        self.contents: dict[str, bytes] = {}

    def put(
        self,
        *,
        source_id: str,
        content: bytes,
        media_type: str,
    ) -> PrivateStoreWriteReceipt:
        self.contents[source_id] = content
        return PrivateStoreWriteReceipt(
            private_store_ref=f"private-store:{source_id}",
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            media_type=media_type,
        )


def _response(
    provider: ApiProvider,
    *,
    status_code: int = 200,
    sources: tuple[TransportSourceObservation, ...] = (),
) -> LiteratureTransportResponse:
    return LiteratureTransportResponse(
        origin=LITERATURE_PROVIDER_ORIGINS[provider],
        status_code=status_code,
        sources=sources,
    )


def _client(
    *,
    elsevier: LiteratureTransportResponse | None = None,
    serpapi: LiteratureTransportResponse | None = None,
    tavily: LiteratureTransportResponse | None = None,
    limits: dict[ApiProvider, int] | None = None,
    private_store: MemoryPrivateStore | None = None,
) -> tuple[
    LiteratureAcquisitionClient,
    dict[ApiProvider, StaticTransport],
    LiteratureTransportBudget,
]:
    transports = {
        ApiProvider.ELSEVIER: StaticTransport(
            elsevier or _response(ApiProvider.ELSEVIER, status_code=404)
        ),
        ApiProvider.SERPAPI: StaticTransport(
            serpapi or _response(ApiProvider.SERPAPI, status_code=404)
        ),
        ApiProvider.TAVILY: StaticTransport(
            tavily or _response(ApiProvider.TAVILY, status_code=404)
        ),
    }
    budget = LiteratureTransportBudget(
        budget_id="literature-budget-1",
        provider_limits=limits
        or {
            ApiProvider.ELSEVIER: 5,
            ApiProvider.SERPAPI: 5,
            ApiProvider.TAVILY: 5,
        },
    )
    return (
        LiteratureAcquisitionClient(
            transports=transports,
            budget=budget,
            private_store=private_store,
        ),
        transports,
        budget,
    )


def _metadata_request(
    request_id: str = "elsevier-metadata-1",
    query: str = "doi:10.1000/example",
) -> LiteratureAcquisitionRequest:
    return LiteratureAcquisitionRequest(
        request_id=request_id,
        provider=ApiProvider.ELSEVIER,
        action=LiteratureAcquisitionAction.METADATA,
        query=query,
        requested_content_classes=(
            LiteratureContentClass.ARTICLE_METADATA,
        ),
        max_results=1,
    )


def _discovery_request(
    provider: ApiProvider,
    request_id: str,
    *classes: LiteratureContentClass,
    max_results: int | None = None,
) -> LiteratureAcquisitionRequest:
    return LiteratureAcquisitionRequest(
        request_id=request_id,
        provider=provider,
        action=LiteratureAcquisitionAction.DISCOVER,
        query="10.1000/example supporting information dataset code",
        requested_content_classes=classes,
        max_results=max_results or len(classes),
    )


def test_elsevier_metadata_uses_exact_origin_and_public_receipts() -> None:
    metadata = b'{"title":"A private normalized metadata record"}'
    client, transports, budget = _client(
        elsevier=_response(
            ApiProvider.ELSEVIER,
            sources=(
                TransportSourceObservation(
                    source_locator="doi:10.1000/EXAMPLE",
                    content_class=LiteratureContentClass.ARTICLE_METADATA,
                    content_state=LiteratureContentState.METADATA_ONLY,
                    media_type="application/json",
                    content=metadata,
                ),
            ),
        )
    )

    result = client.acquire(_metadata_request(), credential=SECRET)

    request = transports[ApiProvider.ELSEVIER].requests[0]
    assert request.origin == "https://api.elsevier.com"
    assert request.endpoint_url == (
        "https://api.elsevier.com/content/article/doi/10.1000%2Fexample"
    )
    assert request.method == "GET"
    assert request.parameters == (("view", "META_ABS"),)
    assert transports[ApiProvider.ELSEVIER].credential_observed is True
    assert budget.remaining(ApiProvider.ELSEVIER) == 4

    receipt = result.response_receipt
    source = receipt.source_receipts[0]
    assert receipt.status is LiteratureResponseStatus.VALID
    assert source.source_locator == "doi:10.1000/example"
    assert source.sha256 == hashlib.sha256(metadata).hexdigest()
    assert source.size_bytes == len(metadata)
    assert source.content_state is LiteratureContentState.METADATA_ONLY
    assert source.private_store_ref is None
    public_json = result.model_dump_json()
    assert SECRET not in public_json
    assert metadata.decode() not in public_json
    assert "query" not in result.request_receipt.model_dump(mode="json")


def test_elsevier_full_text_is_hashed_and_written_only_to_private_store() -> None:
    full_text = b"<article>licensed computational methods</article>"
    store = MemoryPrivateStore()
    client, transports, _ = _client(
        elsevier=_response(
            ApiProvider.ELSEVIER,
            sources=(
                TransportSourceObservation(
                    source_locator="doi:10.1000/example",
                    content_class=LiteratureContentClass.ARTICLE_FULL_TEXT,
                    content_state=LiteratureContentState.RETRIEVED,
                    media_type="application/xml",
                    content=full_text,
                ),
            ),
        ),
        private_store=store,
    )
    request = LiteratureAcquisitionRequest(
        request_id="elsevier-full-text-1",
        provider=ApiProvider.ELSEVIER,
        action=LiteratureAcquisitionAction.FULL_TEXT,
        query="doi:10.1000/example",
        requested_content_classes=(
            LiteratureContentClass.ARTICLE_FULL_TEXT,
        ),
        max_results=1,
    )

    result = client.acquire(request, credential=SECRET)

    transport_request = transports[ApiProvider.ELSEVIER].requests[0]
    assert transport_request.parameters == (("view", "FULL"),)
    source = result.response_receipt.source_receipts[0]
    assert source.content_state is LiteratureContentState.RETRIEVED
    assert source.digest_basis is LiteratureDigestBasis.CONTENT_BYTES
    assert source.private_store_ref == f"private-store:{source.source_id}"
    assert store.contents[source.source_id] == full_text
    assert full_text.decode() not in result.model_dump_json()
    assert SECRET not in result.model_dump_json()


def test_serpapi_and_tavily_discover_si_data_code_without_claiming_content() -> None:
    discoveries = (
        TransportSourceObservation(
            source_locator="https://EXAMPLE.org/si.pdf?b=2&a=1",
            content_class=LiteratureContentClass.SUPPORTING_INFORMATION,
            content_state=LiteratureContentState.DISCOVERED,
            media_type="application/pdf",
        ),
        TransportSourceObservation(
            source_locator="https://example.org/data/",
            content_class=LiteratureContentClass.DATASET,
            content_state=LiteratureContentState.DISCOVERED,
            media_type="application/json",
        ),
        TransportSourceObservation(
            source_locator="https://github.com/example/repository",
            content_class=LiteratureContentClass.CODE,
            content_state=LiteratureContentState.DISCOVERED,
            media_type="text/html",
        ),
    )
    tavily_discovery = TransportSourceObservation(
        source_locator="https://example.org/protocol",
        content_class=LiteratureContentClass.CITED_PROTOCOL,
        content_state=LiteratureContentState.DISCOVERED,
        media_type="text/html",
    )
    client, transports, _ = _client(
        serpapi=_response(ApiProvider.SERPAPI, sources=discoveries),
        tavily=_response(ApiProvider.TAVILY, sources=(tavily_discovery,)),
    )

    serp_result = client.acquire(
        _discovery_request(
            ApiProvider.SERPAPI,
            "serp-discovery-1",
            LiteratureContentClass.SUPPORTING_INFORMATION,
            LiteratureContentClass.DATASET,
            LiteratureContentClass.CODE,
        ),
        credential=SECRET,
    )
    tavily_result = client.acquire(
        _discovery_request(
            ApiProvider.TAVILY,
            "tavily-discovery-1",
            LiteratureContentClass.CITED_PROTOCOL,
        ),
        credential=SECRET,
    )

    serp_request = transports[ApiProvider.SERPAPI].requests[0]
    tavily_request = transports[ApiProvider.TAVILY].requests[0]
    assert serp_request.endpoint_url == "https://serpapi.com/search"
    assert serp_request.method == "GET"
    assert tavily_request.endpoint_url == "https://api.tavily.com/search"
    assert tavily_request.method == "POST"
    assert serp_result.response_receipt.status is LiteratureResponseStatus.VALID
    assert tavily_result.response_receipt.status is LiteratureResponseStatus.VALID
    si = next(
        item
        for item in serp_result.response_receipt.source_receipts
        if item.content_class is LiteratureContentClass.SUPPORTING_INFORMATION
    )
    assert si.source_locator == "https://example.org/si.pdf?a=1&b=2"
    assert si.digest_basis is LiteratureDigestBasis.CANONICAL_LOCATOR
    assert si.private_store_ref is None
    assert all(
        item.content_state is LiteratureContentState.DISCOVERED
        for item in serp_result.response_receipt.source_receipts
    )


def test_tavily_extract_writes_full_text_only_to_private_store() -> None:
    article_url = "https://example.org/articles/complete-paper"
    full_text = b"Complete licensed article text returned by Tavily extract"
    store = MemoryPrivateStore()
    source = TransportSourceObservation(
        source_locator=article_url,
        content_class=LiteratureContentClass.ARTICLE_FULL_TEXT,
        content_state=LiteratureContentState.RETRIEVED,
        media_type="text/plain",
        content=full_text,
    )
    client, transports, _ = _client(
        tavily=_response(ApiProvider.TAVILY, sources=(source,)),
        private_store=store,
    )
    request = LiteratureAcquisitionRequest(
        request_id="tavily-full-text-1",
        provider=ApiProvider.TAVILY,
        action=LiteratureAcquisitionAction.FULL_TEXT,
        query=article_url,
        requested_content_classes=(
            LiteratureContentClass.ARTICLE_FULL_TEXT,
        ),
        max_results=1,
    )

    result = client.acquire(request, credential=SECRET)

    transport_request = transports[ApiProvider.TAVILY].requests[0]
    assert transport_request.endpoint_url == "https://api.tavily.com/extract"
    assert transport_request.method == "POST"
    assert transport_request.parameters == (("url", article_url),)
    receipt = result.response_receipt.source_receipts[0]
    assert receipt.private_store_ref == f"private-store:{receipt.source_id}"
    assert store.contents[receipt.source_id] == full_text
    assert full_text.decode() not in result.model_dump_json()
    assert SECRET not in result.model_dump_json()


@pytest.mark.parametrize(
    ("http_status", "expected"),
    (
        (401, LiteratureResponseStatus.INVALID),
        (403, LiteratureResponseStatus.INVALID_ENTITLEMENT),
        (404, LiteratureResponseStatus.NOT_FOUND),
        (429, LiteratureResponseStatus.RATE_LIMITED),
    ),
)
def test_http_outcomes_distinguish_invalid_entitlement_rate_limit_and_not_found(
    http_status: int,
    expected: LiteratureResponseStatus,
) -> None:
    client, _, _ = _client(
        elsevier=_response(ApiProvider.ELSEVIER, status_code=http_status)
    )

    result = client.acquire(_metadata_request(), credential=SECRET)

    assert result.response_receipt.status is expected
    assert result.response_receipt.http_status == http_status
    assert result.response_receipt.rule_ids
    assert result.response_receipt.source_receipts == ()
    assert SECRET not in result.model_dump_json()


def test_provider_budgets_are_independent_finite_and_have_no_top_up() -> None:
    metadata_source = TransportSourceObservation(
        source_locator="doi:10.1000/example",
        content_class=LiteratureContentClass.ARTICLE_METADATA,
        content_state=LiteratureContentState.METADATA_ONLY,
        media_type="application/json",
        content=b"{}",
    )
    protocol_source = TransportSourceObservation(
        source_locator="https://example.org/protocol",
        content_class=LiteratureContentClass.CITED_PROTOCOL,
        content_state=LiteratureContentState.DISCOVERED,
        media_type="text/html",
    )
    limits = {
        ApiProvider.ELSEVIER: 1,
        ApiProvider.SERPAPI: 1,
        ApiProvider.TAVILY: 1,
    }
    client, transports, budget = _client(
        elsevier=_response(ApiProvider.ELSEVIER, sources=(metadata_source,)),
        tavily=_response(ApiProvider.TAVILY, sources=(protocol_source,)),
        limits=limits,
    )
    client.acquire(_metadata_request(), credential=SECRET)

    with pytest.raises(LiteratureBudgetExhaustedError, match="elsevier"):
        client.acquire(
            _metadata_request("elsevier-metadata-2", "doi:10.1000/other"),
            credential=SECRET,
        )

    tavily = client.acquire(
        _discovery_request(
            ApiProvider.TAVILY,
            "tavily-independent-budget",
            LiteratureContentClass.CITED_PROTOCOL,
        ),
        credential=SECRET,
    )
    assert tavily.response_receipt.status is LiteratureResponseStatus.VALID
    assert len(transports[ApiProvider.ELSEVIER].requests) == 1
    assert budget.remaining(ApiProvider.ELSEVIER) == 0
    assert budget.remaining(ApiProvider.TAVILY) == 0
    assert not hasattr(budget, "top_up")


def test_exact_request_replay_is_free_but_request_id_rebinding_is_rejected() -> None:
    source = TransportSourceObservation(
        source_locator="doi:10.1000/example",
        content_class=LiteratureContentClass.ARTICLE_METADATA,
        content_state=LiteratureContentState.METADATA_ONLY,
        media_type="application/json",
        content=b"{}",
    )
    client, transports, budget = _client(
        elsevier=_response(ApiProvider.ELSEVIER, sources=(source,))
    )
    request = _metadata_request()

    first = client.acquire(request, credential=SECRET)
    replay = client.acquire(request, credential=SECRET)

    assert replay == first
    assert len(transports[ApiProvider.ELSEVIER].requests) == 1
    assert budget.remaining(ApiProvider.ELSEVIER) == 4
    with pytest.raises(LiteratureRequestConflictError, match="immutable intent"):
        client.acquire(
            _metadata_request(query="doi:10.1000/substituted"),
            credential=SECRET,
        )


def test_duplicate_sources_collapse_and_conflicting_content_fails_closed() -> None:
    first = TransportSourceObservation(
        source_locator="doi:10.1000/example",
        content_class=LiteratureContentClass.ARTICLE_METADATA,
        content_state=LiteratureContentState.METADATA_ONLY,
        media_type="application/json",
        content=b'{"title":"same"}',
    )
    duplicate_client, _, _ = _client(
        elsevier=_response(ApiProvider.ELSEVIER, sources=(first, first))
    )
    duplicate_request = LiteratureAcquisitionRequest(
        **{
            **_metadata_request().model_dump(mode="json"),
            "max_results": 2,
        }
    )
    duplicate = duplicate_client.acquire(duplicate_request, credential=SECRET)
    assert duplicate.response_receipt.status is LiteratureResponseStatus.VALID
    assert len(duplicate.response_receipt.source_receipts) == 1

    conflict = TransportSourceObservation(
        source_locator="doi:10.1000/example",
        content_class=LiteratureContentClass.ARTICLE_METADATA,
        content_state=LiteratureContentState.METADATA_ONLY,
        media_type="application/json",
        content=b'{"title":"conflict"}',
    )
    conflict_client, _, _ = _client(
        elsevier=_response(ApiProvider.ELSEVIER, sources=(first, conflict))
    )
    rejected = conflict_client.acquire(duplicate_request, credential=SECRET)
    assert rejected.response_receipt.status is LiteratureResponseStatus.INVALID
    assert rejected.response_receipt.source_receipts == ()
    assert "literature.source.conflict" in rejected.response_receipt.rule_ids

    secret_locator = TransportSourceObservation(
        source_locator="https://example.org/si?access_token=must-not-persist",
        content_class=LiteratureContentClass.SUPPORTING_INFORMATION,
        content_state=LiteratureContentState.DISCOVERED,
        media_type="text/html",
    )
    secret_client, _, _ = _client(
        serpapi=_response(ApiProvider.SERPAPI, sources=(secret_locator,))
    )
    secret_result = secret_client.acquire(
        _discovery_request(
            ApiProvider.SERPAPI,
            "serp-secret-locator",
            LiteratureContentClass.SUPPORTING_INFORMATION,
        ),
        credential=SECRET,
    )
    assert secret_result.response_receipt.status is LiteratureResponseStatus.INVALID
    assert "must-not-persist" not in secret_result.model_dump_json()
    assert secret_result.response_receipt.rule_ids == (
        "literature.source.invalid_locator",
    )


def test_cross_provider_merge_deduplicates_and_detects_conflicts() -> None:
    locator = "https://example.org/supporting-information.pdf"
    serp_source = TransportSourceObservation(
        source_locator=locator,
        content_class=LiteratureContentClass.SUPPORTING_INFORMATION,
        content_state=LiteratureContentState.DISCOVERED,
        media_type="application/pdf",
    )
    tavily_same = TransportSourceObservation(
        source_locator=locator,
        content_class=LiteratureContentClass.SUPPORTING_INFORMATION,
        content_state=LiteratureContentState.DISCOVERED,
        media_type="application/pdf",
    )
    client, _, _ = _client(
        serpapi=_response(ApiProvider.SERPAPI, sources=(serp_source,)),
        tavily=_response(ApiProvider.TAVILY, sources=(tavily_same,)),
    )
    serp = client.acquire(
        _discovery_request(
            ApiProvider.SERPAPI,
            "serp-merge",
            LiteratureContentClass.SUPPORTING_INFORMATION,
        ),
        credential=SECRET,
    )
    tavily = client.acquire(
        _discovery_request(
            ApiProvider.TAVILY,
            "tavily-merge",
            LiteratureContentClass.SUPPORTING_INFORMATION,
        ),
        credential=SECRET,
    )
    merged = merge_literature_response_receipts(
        (serp.response_receipt, tavily.response_receipt),
        merge_id="merge-discovery",
    )
    assert merged.status is LiteratureResponseStatus.VALID
    assert len(merged.source_receipts) == 1

    tavily_conflict = TransportSourceObservation(
        source_locator=locator,
        content_class=LiteratureContentClass.SUPPORTING_INFORMATION,
        content_state=LiteratureContentState.DISCOVERED,
        media_type="text/html",
    )
    conflict_client, _, _ = _client(
        tavily=_response(ApiProvider.TAVILY, sources=(tavily_conflict,)),
    )
    conflicting_tavily = conflict_client.acquire(
        _discovery_request(
            ApiProvider.TAVILY,
            "tavily-merge-conflict",
            LiteratureContentClass.SUPPORTING_INFORMATION,
        ),
        credential=SECRET,
    )
    rejected = merge_literature_response_receipts(
        (serp.response_receipt, conflicting_tavily.response_receipt),
        merge_id="merge-discovery-conflict",
    )
    assert rejected.status is LiteratureResponseStatus.INVALID
    assert rejected.source_receipts == ()
    assert rejected.rule_ids == ("literature.source.conflict",)
