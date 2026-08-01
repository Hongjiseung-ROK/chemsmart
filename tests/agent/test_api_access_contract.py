"""Focused contract tests for bounded API credential access.

These tests use synthetic values only.  They must never contact a provider or
the host Keychain.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from chemsmart.agent.api_access import (
    ApiProvider,
    ApiUsageBudget,
    CANONICAL_API_ORIGINS,
    CREDENTIAL_LOCATORS,
    CredentialAccessController,
    CredentialProbeError,
    CredentialProbeObservation,
    CredentialSource,
    CredentialStatus,
    CredentialUnavailableError,
    UsageBudgetError,
)


def _keychain_reader(entries: dict[tuple[str, str], str]):
    def read(service: str, account: str) -> str | None:
        return entries.get((service, account))

    return read


def test_catalog_has_canonical_locations_and_legacy_elsevier_typo() -> None:
    assert set(CREDENTIAL_LOCATORS) == set(ApiProvider)
    elsevier = CREDENTIAL_LOCATORS[ApiProvider.ELSEVIER]
    assert elsevier.canonical_keychain.account == "elsevier_api_key"
    assert "Elsivier_api_key" in elsevier.environment_aliases
    assert any(
        location.account == "Elsivier_api_key"
        for location in elsevier.legacy_keychain
    )
    assert "DEEPSEEK-api-key" in CREDENTIAL_LOCATORS[
        ApiProvider.DEEPSEEK
    ].environment_aliases
    assert "SerpApi_api_key" in CREDENTIAL_LOCATORS[
        ApiProvider.SERPAPI
    ].environment_aliases
    assert "Tavily_api_key" in CREDENTIAL_LOCATORS[
        ApiProvider.TAVILY
    ].environment_aliases


def test_keychain_is_preferred_and_status_receipt_has_no_secret() -> None:
    locator = CREDENTIAL_LOCATORS[ApiProvider.DEEPSEEK].canonical_keychain
    controller = CredentialAccessController(
        keychain_reader=_keychain_reader(
            {(locator.service, locator.account): "keychain-test-secret"}
        ),
        environment={"DEEPSEEK_API_KEY": "environment-test-secret"},
    )

    receipt = controller.credential_status(ApiProvider.DEEPSEEK)

    assert receipt.status is CredentialStatus.AVAILABLE
    assert receipt.source is CredentialSource.KEYCHAIN
    public = receipt.to_public_dict()
    assert "keychain-test-secret" not in repr(receipt)
    assert "keychain-test-secret" not in repr(public)
    assert "environment-test-secret" not in repr(receipt)


def test_missing_credential_reports_only_missing_state() -> None:
    controller = CredentialAccessController(
        keychain_reader=_keychain_reader({}), environment={}
    )

    receipt = controller.credential_status(ApiProvider.TAVILY)

    assert receipt.status is CredentialStatus.MISSING
    assert receipt.source is CredentialSource.NONE
    with pytest.raises(CredentialUnavailableError):
        controller.prepare_status_probe(
            ApiProvider.TAVILY,
            caller="test",
            purpose="synthetic status check",
            budget=ApiUsageBudget(1),
        )


def test_legacy_elsevier_environment_alias_is_available_without_probe() -> None:
    controller = CredentialAccessController(
        keychain_reader=_keychain_reader({}),
        environment={"Elsivier_api_key": "synthetic-legacy-secret"},
    )

    receipt = controller.credential_status(ApiProvider.ELSEVIER)

    assert receipt.status is CredentialStatus.AVAILABLE
    assert receipt.source is CredentialSource.ENVIRONMENT
    assert receipt.credential_locator == "Elsivier_api_key"
    assert "synthetic-legacy-secret" not in repr(receipt.to_public_dict())


def test_probe_requires_explicit_caller_and_single_finite_budget() -> None:
    locator = CREDENTIAL_LOCATORS[ApiProvider.SERPAPI].canonical_keychain
    controller = CredentialAccessController(
        keychain_reader=_keychain_reader(
            {(locator.service, locator.account): "synthetic-serpapi-secret"}
        ),
        environment={},
    )
    budget = ApiUsageBudget(1)

    with pytest.raises(ValueError, match="caller"):
        controller.prepare_status_probe(
            ApiProvider.SERPAPI,
            caller=" ",
            purpose="literature discovery",
            budget=budget,
        )

    permit = controller.prepare_status_probe(
        ApiProvider.SERPAPI,
        caller="literature-audit",
        purpose="synthetic entitlement status",
        budget=budget,
    )

    assert permit.reserved_requests == 1
    assert permit.target_origin == CANONICAL_API_ORIGINS[ApiProvider.SERPAPI]
    assert budget.remaining_network_requests == 0
    with pytest.raises(UsageBudgetError):
        controller.prepare_status_probe(
            ApiProvider.SERPAPI,
            caller="literature-audit",
            purpose="second synthetic entitlement status",
            budget=budget,
        )


def test_authorized_probe_returns_only_typed_status_and_is_single_use() -> None:
    locator = CREDENTIAL_LOCATORS[ApiProvider.DEEPSEEK].canonical_keychain
    controller = CredentialAccessController(
        keychain_reader=_keychain_reader(
            {(locator.service, locator.account): "synthetic-deepseek-secret"}
        ),
        environment={},
    )
    permit = controller.prepare_status_probe(
        ApiProvider.DEEPSEEK,
        caller="harness-validation",
        purpose="synthetic model entitlement status",
        budget=ApiUsageBudget(1),
    )
    seen: list[tuple[str, str]] = []

    receipt = controller.invoke_authorized_probe(
        permit,
        lambda secret, origin: (
            seen.append((secret, origin)),
            CredentialProbeObservation(CredentialStatus.VALID),
        )[1],
    )

    assert seen == [
        (
            "synthetic-deepseek-secret",
            "https://api.deepseek.com",
        )
    ]
    assert receipt.status is CredentialStatus.VALID
    assert "synthetic-deepseek-secret" not in repr(receipt)
    with pytest.raises(CredentialProbeError, match="single-use"):
        controller.invoke_authorized_probe(
            permit,
            lambda secret, origin: CredentialProbeObservation(
                CredentialStatus.VALID
            ),
        )


def test_probe_rejects_an_altered_permit_before_passing_any_secret() -> None:
    locator = CREDENTIAL_LOCATORS[ApiProvider.SERPAPI].canonical_keychain
    controller = CredentialAccessController(
        keychain_reader=_keychain_reader(
            {(locator.service, locator.account): "synthetic-serpapi-secret"}
        ),
        environment={},
    )
    permit = controller.prepare_status_probe(
        ApiProvider.SERPAPI,
        caller="literature-audit",
        purpose="synthetic entitlement status",
        budget=ApiUsageBudget(1),
    )
    altered = replace(permit, caller="different-caller")

    with pytest.raises(CredentialProbeError, match="altered"):
        controller.invoke_authorized_probe(
            altered,
            lambda secret, origin: CredentialProbeObservation(
                CredentialStatus.VALID
            ),
        )


def test_probe_rejects_non_typed_return_without_reporting_secret() -> None:
    locator = CREDENTIAL_LOCATORS[ApiProvider.TAVILY].canonical_keychain
    controller = CredentialAccessController(
        keychain_reader=_keychain_reader(
            {(locator.service, locator.account): "synthetic-tavily-secret"}
        ),
        environment={},
    )
    permit = controller.prepare_status_probe(
        ApiProvider.TAVILY,
        caller="literature-audit",
        purpose="synthetic entitlement status",
        budget=ApiUsageBudget(1),
    )

    with pytest.raises(CredentialProbeError, match="must return"):
        controller.invoke_authorized_probe(
            permit,
            lambda secret, origin: secret,
        )


def test_probe_can_report_invalid_entitlement_without_error_detail() -> None:
    locator = CREDENTIAL_LOCATORS[ApiProvider.ELSEVIER].canonical_keychain
    controller = CredentialAccessController(
        keychain_reader=_keychain_reader(
            {(locator.service, locator.account): "synthetic-elsevier-secret"}
        ),
        environment={},
    )
    permit = controller.prepare_status_probe(
        ApiProvider.ELSEVIER,
        caller="literature-audit",
        purpose="synthetic entitlement status",
        budget=ApiUsageBudget(1),
    )

    receipt = controller.invoke_authorized_probe(
        permit,
        lambda secret, origin: CredentialProbeObservation(
            CredentialStatus.INVALID_ENTITLEMENT
        ),
    )

    assert receipt.status is CredentialStatus.INVALID_ENTITLEMENT
    assert "synthetic-elsevier-secret" not in repr(receipt)


@pytest.mark.parametrize(
    "target_origin",
    (
        "http://api.deepseek.com",
        "https://api.deepseek.com/v1",
        "https://api.deepseek.com?redirect=true",
        "https://api.deepseek.com.evil.example",
    ),
)
def test_probe_rejects_noncanonical_target_origins(target_origin: str) -> None:
    controller = CredentialAccessController(
        keychain_reader=_keychain_reader({}),
        environment={"DEEPSEEK_API_KEY": "synthetic-secret"},
    )

    with pytest.raises(ValueError, match="target_origin"):
        controller.prepare_status_probe(
            ApiProvider.DEEPSEEK,
            caller="harness-validation",
            purpose="synthetic origin check",
            budget=ApiUsageBudget(1),
            target_origin=target_origin,
        )


def test_pending_permit_retains_reference_but_not_secret() -> None:
    secret = "synthetic-secret-not-retained-by-permit"
    controller = CredentialAccessController(
        keychain_reader=_keychain_reader({}),
        environment={"DEEPSEEK_API_KEY": secret},
    )

    permit = controller.prepare_status_probe(
        ApiProvider.DEEPSEEK,
        caller="harness-validation",
        purpose="synthetic reference check",
        budget=ApiUsageBudget(1),
    )

    assert secret not in repr(permit)
    assert secret not in repr(controller._permits)
    assert "DEEPSEEK_API_KEY" in repr(controller._permits)


def test_probe_permit_expires_and_is_not_reusable() -> None:
    now = [10.0]
    controller = CredentialAccessController(
        keychain_reader=_keychain_reader({}),
        environment={"DEEPSEEK_API_KEY": "synthetic-secret"},
        permit_ttl_seconds=5,
        monotonic_clock=lambda: now[0],
    )
    permit = controller.prepare_status_probe(
        ApiProvider.DEEPSEEK,
        caller="harness-validation",
        purpose="synthetic expiry check",
        budget=ApiUsageBudget(1),
    )
    now[0] = 15.0

    with pytest.raises(CredentialProbeError, match="expired"):
        controller.invoke_authorized_probe(
            permit,
            lambda secret, origin: CredentialProbeObservation(
                CredentialStatus.VALID
            ),
        )
    with pytest.raises(CredentialProbeError, match="single-use"):
        controller.invoke_authorized_probe(
            permit,
            lambda secret, origin: CredentialProbeObservation(
                CredentialStatus.VALID
            ),
        )


def test_probe_permit_can_be_cancelled_and_expired_permits_cleaned() -> None:
    now = [20.0]
    controller = CredentialAccessController(
        keychain_reader=_keychain_reader({}),
        environment={"TAVILY_API_KEY": "synthetic-secret"},
        permit_ttl_seconds=2,
        monotonic_clock=lambda: now[0],
    )
    budget = ApiUsageBudget(2)
    cancelled = controller.prepare_status_probe(
        ApiProvider.TAVILY,
        caller="literature-audit",
        purpose="synthetic cancel check",
        budget=budget,
    )
    expiring = controller.prepare_status_probe(
        ApiProvider.TAVILY,
        caller="literature-audit",
        purpose="synthetic cleanup check",
        budget=budget,
    )

    assert controller.cancel_probe(cancelled) is True
    assert controller.cancel_probe(cancelled) is False
    now[0] = 22.0
    assert controller.cleanup_expired() == 1
    assert controller.cleanup_expired() == 0
    with pytest.raises(CredentialProbeError, match="single-use"):
        controller.invoke_authorized_probe(
            expiring,
            lambda secret, origin: CredentialProbeObservation(
                CredentialStatus.VALID
            ),
        )
