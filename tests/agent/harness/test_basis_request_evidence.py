from __future__ import annotations

import socket
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from chemsmart.agent.harness.basis_sets import (
    BasisEvidenceState,
    RequestBoundBasisEvidenceReceiptV1,
    basis_evidence_receipt_sha256,
    basis_evidence_ref_sha256,
    basis_evidence_request_sha256,
    build_request_bound_basis_evidence_request_v1,
    inspect_request_bound_basis_evidence_v1,
)
from chemsmart.agent.harness.scientific_settings import (
    load_populated_scientific_settings_inventories_v2,
    load_populated_scientific_settings_registry_v2,
)


FROZEN_POPULATED_V2_REGISTRY_SHA256 = (
    "3331cd8a74b1343e31da2b7df4530f50fcbaa9bf4894aad7abf9b7257f36ee7f"
)
FROZEN_POPULATED_V2_INVENTORY_SHA256 = (
    "cb6eaa89f210eb82743045472d5fcd16e3935d0abbe218468c90d33a8523a1fe"
)
FROZEN_CATALOG_ARTIFACT_SHA256 = (
    "ed4ef918fb80e8ad3c2396c237d2120c31892cfaa2a61fb61af52965dc723c0b"
)
FROZEN_CATALOG_CONTENT_SHA256 = (
    "a4c39327851ed653ec849c2109549cad4f0ee4e4207ea20143a368d25b2e2732"
)


def test_request_bound_orbital_evidence_is_exact_offline_and_deterministic():
    registry_before = load_populated_scientific_settings_registry_v2()
    inventory_before = load_populated_scientific_settings_inventories_v2()[0]
    first_request = build_request_bound_basis_evidence_request_v1(
        request_id="basis-request:orca-def2-tzvp-cl-pd",
        program="orca",
        basis_literal="def2-TZVP",
        role="orbital",
        elements=("Pd", "Cl", "Pd"),
    )
    reordered_request = build_request_bound_basis_evidence_request_v1(
        request_id="basis-request:orca-def2-tzvp-cl-pd",
        program="orca",
        basis_literal="def2-TZVP",
        role="orbital",
        elements=("Cl", "Pd"),
    )

    with patch.object(
        socket,
        "create_connection",
        side_effect=AssertionError("network access is forbidden"),
    ):
        first = inspect_request_bound_basis_evidence_v1(first_request)
        repeated = inspect_request_bound_basis_evidence_v1(reordered_request)

    evidence_ref = first.evidence_ref()
    registry_after = load_populated_scientific_settings_registry_v2()
    inventory_after = load_populated_scientific_settings_inventories_v2()[0]

    assert first_request.atomic_numbers == (17, 46)
    assert first_request.request_sha256 == reordered_request.request_sha256
    assert first_request.request_sha256 == basis_evidence_request_sha256(
        first_request
    )
    assert first.state is BasisEvidenceState.VERIFIED
    assert first.receipt_sha256 == repeated.receipt_sha256
    assert first.receipt_sha256 == basis_evidence_receipt_sha256(first)
    assert first.canonical_basis_name == "def2-TZVP"
    assert first.requested_basis_identity == first.canonical_basis_identity
    assert first.catalog_role == "orbital"
    assert first.definition_sha256 == (
        "f5fbd0f114cbe9709bb114f5e4e26dfc7822e72c3617e75e65dc3a81668a7f55"
    )
    assert first.catalog_artifact_sha256 == FROZEN_CATALOG_ARTIFACT_SHA256
    assert first.catalog_content_sha256 == FROZEN_CATALOG_CONTENT_SHA256
    assert tuple(value.symbol for value in first.elements) == ("Cl", "Pd")
    assert all(value.state is BasisEvidenceState.VERIFIED for value in first.elements)
    assert first.elements[1].ecp_present is True
    assert first.elements[1].ecp_electrons == 28
    assert first.substitution_performed is False
    assert first.model_confidence_used is False
    assert first.network_accessed is False
    assert first.native_engine_verified is False
    assert first.safe_preview_executed is False
    assert first.engine_executed is False
    assert first.scientific_suitability_verified is False
    assert evidence_ref.artifact_sha256 == first.receipt_sha256
    assert evidence_ref.request_sha256 == first.request.request_sha256
    assert evidence_ref.ref_sha256 == basis_evidence_ref_sha256(evidence_ref)
    assert registry_before.registry_sha256 == registry_after.registry_sha256 == (
        FROZEN_POPULATED_V2_REGISTRY_SHA256
    )
    assert inventory_before.inventory_sha256 == inventory_after.inventory_sha256 == (
        FROZEN_POPULATED_V2_INVENTORY_SHA256
    )


@pytest.mark.parametrize(
    ("elements", "basis", "expected_state", "expected_rule"),
    (
        (
            ("Pd",),
            "def2-TZVP",
            BasisEvidenceState.VERIFIED,
            "basis.request.exact_local_bse_evidence",
        ),
        (
            ("Fe",),
            "def2-TZVP",
            BasisEvidenceState.NOT_APPLICABLE,
            "basis.request.ecp_definition_not_applicable",
        ),
        (
            ("Fe", "Pd"),
            "def2-TZVP",
            BasisEvidenceState.CONFLICT,
            "basis.request.ecp_role_conflict",
        ),
        (
            ("Pd",),
            "def2-ECP",
            BasisEvidenceState.VERIFIED,
            "basis.request.exact_local_bse_evidence",
        ),
    ),
)
def test_request_bound_ecp_role_has_explicit_states(
    elements,
    basis,
    expected_state,
    expected_rule,
):
    request = build_request_bound_basis_evidence_request_v1(
        request_id=f"basis-request:ecp-{basis}-{expected_state.value}",
        program="orca",
        basis_literal=basis,
        role="ecp",
        elements=elements,
    )

    receipt = inspect_request_bound_basis_evidence_v1(request)

    assert receipt.state is expected_state
    assert receipt.reason_rule_ids == (expected_rule,)
    assert receipt.receipt_sha256 == basis_evidence_receipt_sha256(receipt)
    if basis == "def2-ECP":
        assert receipt.elements[0].orbital_present is False
        assert receipt.elements[0].ecp_present is True
        assert receipt.elements[0].ecp_electrons == 28


def test_unknown_basis_and_role_mismatch_fail_without_substitution():
    unknown_request = build_request_bound_basis_evidence_request_v1(
        request_id="basis-request:unknown",
        program="gaussian",
        basis_literal="def2-not-real",
        role="orbital",
        elements=("H",),
    )
    role_conflict_request = build_request_bound_basis_evidence_request_v1(
        request_id="basis-request:role-conflict",
        program="orca",
        basis_literal="def2-TZVP-RIFIT",
        role="orbital",
        elements=("Pd",),
    )

    unknown = inspect_request_bound_basis_evidence_v1(unknown_request)
    role_conflict = inspect_request_bound_basis_evidence_v1(
        role_conflict_request
    )

    assert unknown.state is BasisEvidenceState.UNKNOWN
    assert unknown.reason_rule_ids == ("basis.request.basis_unknown",)
    assert unknown.canonical_basis_name is None
    assert unknown.elements[0].covered is None
    assert unknown.substitution_performed is False
    assert role_conflict.state is BasisEvidenceState.CONFLICT
    assert role_conflict.reason_rule_ids == ("basis.request.role_conflict",)
    assert role_conflict.catalog_role == "rifit"
    assert role_conflict.elements[0].state is BasisEvidenceState.CONFLICT


def test_xtb_basis_is_typed_not_applicable_without_bse_inspection():
    request = build_request_bound_basis_evidence_request_v1(
        request_id="basis-request:xtb-not-applicable",
        program="xtb",
        basis_literal="def2-TZVP",
        role="orbital",
        elements=("H", "C"),
    )

    with patch(
        "chemsmart.agent.harness.basis_sets.request_evidence.inspect_basis_elements",
        side_effect=AssertionError("xTB must not invoke BSE inspection"),
    ):
        receipt = inspect_request_bound_basis_evidence_v1(request)

    assert receipt.state is BasisEvidenceState.NOT_APPLICABLE
    assert receipt.evidence_scope == "typed_program_not_applicable"
    assert receipt.inspection_receipt_sha256 is None
    assert receipt.definition_sha256 is None
    assert all(
        value.state is BasisEvidenceState.NOT_APPLICABLE
        for value in receipt.elements
    )


def test_receipt_contract_rejects_basis_substitution_even_if_rehashed():
    request = build_request_bound_basis_evidence_request_v1(
        request_id="basis-request:substitution-rejection",
        program="orca",
        basis_literal="def2-TZVP",
        role="orbital",
        elements=("Pd",),
    )
    receipt = inspect_request_bound_basis_evidence_v1(request)
    payload = receipt.model_dump(mode="json")
    payload["canonical_basis_name"] = "def2-SVP"
    payload["canonical_basis_identity"] = "def2svp"
    payload["receipt_sha256"] = basis_evidence_receipt_sha256(payload)

    with pytest.raises(ValidationError, match="substituted a basis"):
        RequestBoundBasisEvidenceReceiptV1.model_validate(payload)


def test_verified_receipt_rejects_incoherent_source_and_role_facts_after_rehash():
    request = build_request_bound_basis_evidence_request_v1(
        request_id="basis-request:verified-coherence",
        program="orca",
        basis_literal="def2-TZVP",
        role="orbital",
        elements=("H",),
    )
    receipt = inspect_request_bound_basis_evidence_v1(request)

    source_drift = receipt.model_dump(mode="json")
    source_drift["source_version_matches_catalog"] = False
    source_drift["inspection_receipt_sha256"] = None
    source_drift["catalog_artifact_sha256"] = None
    source_drift["error_class"] = "SourceVersionMismatch"
    source_drift["receipt_sha256"] = basis_evidence_receipt_sha256(source_drift)
    with pytest.raises(ValidationError, match="authoritative local BSE"):
        RequestBoundBasisEvidenceReceiptV1.model_validate(source_drift)

    role_drift = receipt.model_dump(mode="json")
    role_drift["elements"][0]["orbital_present"] = False
    role_drift["elements"][0]["electron_shell_count"] = 0
    role_drift["receipt_sha256"] = basis_evidence_receipt_sha256(role_drift)
    with pytest.raises(ValidationError, match="observed functions"):
        RequestBoundBasisEvidenceReceiptV1.model_validate(role_drift)


def test_receipt_rejects_rehashed_role_mismatch_and_false_not_applicable():
    fit_request = build_request_bound_basis_evidence_request_v1(
        request_id="basis-request:rifit-role-coherence",
        program="orca",
        basis_literal="def2-TZVP-RIFIT",
        role="rifit",
        elements=("H",),
    )
    fit_receipt = inspect_request_bound_basis_evidence_v1(fit_request)
    role_mismatch = fit_receipt.model_dump(mode="json")
    role_mismatch["request"]["role"] = "orbital"
    role_mismatch["request"]["request_sha256"] = basis_evidence_request_sha256(
        role_mismatch["request"]
    )
    role_mismatch["receipt_sha256"] = basis_evidence_receipt_sha256(
        role_mismatch
    )
    with pytest.raises(ValidationError, match="wrong catalog role"):
        RequestBoundBasisEvidenceReceiptV1.model_validate(role_mismatch)

    ecp_request = build_request_bound_basis_evidence_request_v1(
        request_id="basis-request:false-na-role",
        program="orca",
        basis_literal="def2-TZVP",
        role="ecp",
        elements=("Fe",),
    )
    ecp_receipt = inspect_request_bound_basis_evidence_v1(ecp_request)
    false_not_applicable = ecp_receipt.model_dump(mode="json")
    false_not_applicable["request"]["role"] = "orbital"
    false_not_applicable["request"]["request_sha256"] = (
        basis_evidence_request_sha256(false_not_applicable["request"])
    )
    false_not_applicable["receipt_sha256"] = basis_evidence_receipt_sha256(
        false_not_applicable
    )
    with pytest.raises(ValidationError, match="must be ECP absence"):
        RequestBoundBasisEvidenceReceiptV1.model_validate(false_not_applicable)


def test_conflict_cannot_be_rewritten_as_verified_after_rehash():
    request = build_request_bound_basis_evidence_request_v1(
        request_id="basis-request:ce-conflict-replay",
        program="gaussian",
        basis_literal="def2-TZVPPD",
        role="orbital",
        elements=("Pd", "Ce"),
    )
    receipt = inspect_request_bound_basis_evidence_v1(request)
    assert receipt.state is BasisEvidenceState.CONFLICT
    payload = receipt.model_dump(mode="json")
    payload["state"] = "verified"
    payload["reason_rule_ids"] = ["basis.request.exact_local_bse_evidence"]
    for element in payload["elements"]:
        element["state"] = "verified"
        element["reason_rule_ids"] = [
            "basis.request.orbital_functions_observed"
        ]
        if element["symbol"] == "Ce":
            element["covered"] = True
            element["orbital_present"] = True
            element["electron_shell_count"] = 1
    payload["receipt_sha256"] = basis_evidence_receipt_sha256(payload)

    with pytest.raises(ValidationError, match="pinned local BSE observation"):
        RequestBoundBasisEvidenceReceiptV1.model_validate(payload)


def test_element_symbol_must_match_atomic_number_even_after_rehash():
    request = build_request_bound_basis_evidence_request_v1(
        request_id="basis-request:element-symbol-coherence",
        program="orca",
        basis_literal="def2-TZVP",
        role="orbital",
        elements=("H",),
    )
    receipt = inspect_request_bound_basis_evidence_v1(request)
    payload = receipt.model_dump(mode="json")
    payload["elements"][0]["symbol"] = "He"
    payload["receipt_sha256"] = basis_evidence_receipt_sha256(payload)

    with pytest.raises(ValidationError, match="symbol does not match"):
        RequestBoundBasisEvidenceReceiptV1.model_validate(payload)
