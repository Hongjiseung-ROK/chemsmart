from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from importlib import metadata
from unittest.mock import patch

import basis_set_exchange as bse
import pytest

from chemsmart.agent.harness.basis_sets import (
    BasisCatalogIdentityCollisionError,
    check_basis_intent,
    inspect_basis_elements,
    load_basis_catalog,
    normalize_basis_identity,
    resolve_basis_name,
    search_basis_sets,
)
from chemsmart.agent.harness.basis_sets import catalog as basis_catalog


FROZEN_CATALOG_ARTIFACT_SHA256 = (
    "ed4ef918fb80e8ad3c2396c237d2120c31892cfaa2a61fb61af52965dc723c0b"
)
FROZEN_CATALOG_CONTENT_SHA256 = (
    "a4c39327851ed653ec849c2109549cad4f0ee4e4207ea20143a368d25b2e2732"
)


def test_bse_catalog_has_program_splits_and_known_basis_names():
    catalog = load_basis_catalog()

    assert catalog["metadata"]["source_package"] == "basis_set_exchange"
    assert catalog["metadata"]["basis_set_count"] >= 700
    assert (
        catalog["metadata"]["renderability_verification"]
        == "all_declared_elements"
    )
    assert catalog["programs"]["gaussian"]["format"] == "gaussian94"
    assert catalog["programs"]["orca"]["format"] == "orca"
    assert "def2-SVP" in catalog["programs"]["gaussian"]["basis_names"]
    assert "def2-SVP" in catalog["programs"]["orca"]["basis_names"]


def test_bse_catalog_default_loads_are_isolated_from_caller_mutation():
    first = load_basis_catalog()
    first["aliases"]["invented-alias"] = "def2-tzvp"

    second = load_basis_catalog()

    assert first is not second
    assert "invented-alias" not in second["aliases"]


def test_resolve_basis_name_accepts_user_spelling_variants():
    result = resolve_basis_name("def2 TZVP", program="gaussian")

    assert result.verdict == "ok"
    assert result.canonical_name == "def2-TZVP"
    assert result.evidence
    assert result.evidence["family"] == "ahlrichs"


@pytest.mark.parametrize(
    ("literal", "expected_key", "expected_name"),
    (
        ("6-31G", "6-31g", "6-31G"),
        ("6-31+G", "6-31+g", "6-31+G"),
        ("6-31G*", "6-31g_st_", "6-31G*"),
        ("def2-SVP", "def2-svp", "def2-SVP"),
        ("def2-SV(P)", "def2-sv(p)", "def2-SV(P)"),
    ),
)
def test_exact_resolution_preserves_scientific_punctuation(
    literal: str,
    expected_key: str,
    expected_name: str,
):
    result = resolve_basis_name(literal, program="orca")

    assert result.verdict == "ok"
    assert result.catalog_key == expected_key
    assert result.canonical_name == expected_name
    assert result.evidence
    assert result.evidence["identity"] == normalize_basis_identity(literal)


def test_exact_resolution_ignores_unsafe_frozen_alias_collision():
    catalog = load_basis_catalog()

    assert catalog["aliases"]["def2svp"] == "def2-sv(p)"
    result = resolve_basis_name("def2-SVP", program="orca", catalog=catalog)

    assert result.verdict == "ok"
    assert result.catalog_key == "def2-svp"
    assert result.canonical_name == "def2-SVP"


def test_exact_identity_retains_parentheses_commas_stars_and_pluses():
    assert normalize_basis_identity("6-31+G*") == "631+g*"
    assert normalize_basis_identity("6-311G(2d,2p)") == "6311g(2d,2p)"
    assert normalize_basis_identity("6-311G(2d,2p)") != (
        normalize_basis_identity("6-311G(2d2p)")
    )


def test_exact_resolution_fails_closed_on_trusted_identity_collision():
    catalog = load_basis_catalog()
    catalog["basis_sets"]["def2-svp"]["display_name"] = "def2-SV(P)"

    with pytest.raises(BasisCatalogIdentityCollisionError):
        resolve_basis_name("def2-SVP", program="orca", catalog=catalog)


def test_check_basis_intent_distinguishes_concrete_from_qualitative():
    concrete = check_basis_intent(
        "Use M06-2X with def2-TZVP and SMD acetonitrile.",
        program="orca",
    )
    qualitative = check_basis_intent(
        "Use a good Karlsruhe triple-zeta basis for this system.",
        program="gaussian",
    )

    assert concrete.verdict == "ok"
    assert concrete.canonical_name == "def2-TZVP"
    assert qualitative.verdict == "ask_user"
    assert qualitative.candidates


def test_unknown_basis_name_is_rejected_with_candidates():
    result = resolve_basis_name("def2-not-real", program="gaussian")

    assert result.verdict == "reject"
    assert result.candidates == ()


def test_search_basis_sets_returns_top_k_only_for_qualitative_basis():
    result = search_basis_sets(
        "Karlsruhe triple zeta diffuse basis",
        program="gaussian",
        limit=4,
    )

    assert result["ok"] is True
    assert result["verdict"] in {"ask_user", "warn", "ok"}
    assert result["result_count"] <= 4
    assert (
        result["token_policy"] == "top_k_only; full catalog is never returned"
    )
    assert any(
        candidate["name"] == "def2-TZVPD" for candidate in result["candidates"]
    )


def test_search_basis_sets_preserves_ri_fit_role():
    result = search_basis_sets(
        "RI fit auxiliary basis for def2 TZVP",
        program="orca",
        limit=5,
    )

    assert result["ok"] is True
    assert result["requested_role"] == "rifit"
    assert result["result_count"] <= 5
    assert result["candidates"][0]["role"] == "rifit"
    assert any(
        candidate["name"] == "def2-TZVP-RIFIT"
        for candidate in result["candidates"]
    )


def test_search_basis_sets_handles_spoken_pople_style_query():
    result = search_basis_sets(
        "Pople split-valence basis with polarization, like six thirty one star",
        program="gaussian",
        limit=6,
    )

    assert result["ok"] is True
    assert result["result_count"] <= 6
    assert any(
        candidate["name"] in {"6-31G*", "6-31G(d)"}
        for candidate in result["candidates"]
    )


def test_element_inspection_distinguishes_fe_and_pd_ecp_semantics():
    iron = inspect_basis_elements(
        "def2-TZVP",
        program="orca",
        elements=("Cl", "Fe"),
    )
    palladium = inspect_basis_elements(
        "def2-TZVP",
        program="orca",
        elements=("Cl", "Pd"),
    )

    assert iron.verdict == "ok"
    assert iron.status == "all_elements_covered"
    assert iron.source_version_matches_catalog is True
    assert iron.missing_atomic_numbers == ()
    iron_by_symbol = {item.symbol: item for item in iron.elements}
    assert iron_by_symbol["Fe"].orbital_present is True
    assert iron_by_symbol["Fe"].ecp_present is False
    assert iron_by_symbol["Fe"].ecp_electrons is None
    assert iron_by_symbol["Cl"].ecp_present is False

    assert palladium.verdict == "ok"
    palladium_by_symbol = {item.symbol: item for item in palladium.elements}
    assert palladium_by_symbol["Pd"].orbital_present is True
    assert palladium_by_symbol["Pd"].ecp_present is True
    assert palladium_by_symbol["Pd"].ecp_electrons == 28
    assert palladium_by_symbol["Pd"].ecp_potential_count == 4
    assert palladium.definition_sha256 is not None
    assert len(palladium.definition_sha256) == 64
    assert len(palladium.receipt_sha256) == 64
    assert palladium.receipt_sha256_is_valid() is True
    assert palladium.catalog_artifact_sha256 == (
        FROZEN_CATALOG_ARTIFACT_SHA256
    )
    assert palladium.catalog_content_sha256 == FROZEN_CATALOG_CONTENT_SHA256
    assert palladium.catalog_authority == "frozen_default"
    assert palladium.catalog_authoritative is True
    assert palladium.orbital_basis_usable is True
    assert palladium.ecp_definition_coherent is True
    assert palladium.error_class is None
    assert palladium.hash_semantics == "content_identity_not_authentication"
    assert palladium.native_engine_verified is False
    assert palladium.safe_preview_executed is False
    assert palladium.engine_executed is False


def test_element_inspection_rejects_missing_basis_coverage():
    result = inspect_basis_elements(
        "def2-TZVPPD",
        program="gaussian",
        elements=("Pd", "Ce"),
    )

    assert result.verdict == "reject"
    assert result.status == "element_coverage_missing"
    assert result.missing_atomic_numbers == (58,)
    assert result.rule_ids == (
        "basis.element_inspection.element_coverage_missing",
    )
    by_symbol = {item.symbol: item for item in result.elements}
    assert by_symbol["Pd"].covered is True
    assert by_symbol["Pd"].ecp_present is True
    assert by_symbol["Pd"].ecp_electrons == 28
    assert by_symbol["Ce"].covered is False
    assert by_symbol["Ce"].orbital_present is False
    assert by_symbol["Ce"].ecp_present is False


def test_element_inspection_hashes_are_stable_and_detect_tampering():
    first = inspect_basis_elements(
        "def2-TZVP",
        program="orca",
        elements=("Pd", "Cl", "Pd"),
    )
    reordered = inspect_basis_elements(
        "def2-TZVP",
        program="orca",
        elements=("Cl", "Pd"),
    )

    assert first.definition_sha256 == reordered.definition_sha256
    assert first.receipt_sha256 == reordered.receipt_sha256
    assert first.definition_sha256 == (
        "f5fbd0f114cbe9709bb114f5e4e26dfc7822e72c3617e75e65dc3a81668a7f55"
    )
    assert first.receipt_sha256 == (
        "239e7ed2e53b911cadaddf5812d5e7b1a3e19658e7e659d3d991cbbaabce8f45"
    )
    assert first.receipt_sha256_is_valid() is True
    tampered = replace(first, definition_sha256="0" * 64)
    assert tampered.receipt_sha256_is_valid() is False


def test_element_inspection_ignores_unsafe_custom_legacy_alias():
    custom = deepcopy(load_basis_catalog())
    custom["aliases"]["def2notreal"] = "def2-tzvp"

    result = inspect_basis_elements(
        "def2-not-real",
        program="orca",
        elements=("Pd",),
        catalog=custom,
    )

    assert result.canonical_name is None
    assert result.verdict == "reject"
    assert result.status == "basis_unresolved"
    assert result.catalog_authority == "custom_non_authoritative"
    assert result.catalog_authoritative is False
    assert result.catalog_artifact_sha256 is None
    assert result.catalog_content_sha256 is not None
    assert result.rule_ids == (
        "basis.element_inspection.custom_catalog_non_authoritative",
        "basis.element_inspection.basis_unresolved",
    )
    assert result.orbital_basis_usable is None


def test_element_inspection_custom_catalog_is_bound_but_non_authoritative():
    custom = deepcopy(load_basis_catalog())

    result = inspect_basis_elements(
        "def2-SVP",
        program="orca",
        elements=("H",),
        catalog=custom,
    )

    assert result.canonical_name == "def2-SVP"
    assert result.catalog_key == "def2-svp"
    assert result.verdict == "reject"
    assert result.status == "catalog_non_authoritative"
    assert result.rule_ids == (
        "basis.element_inspection.custom_catalog_non_authoritative",
    )
    assert result.orbital_basis_usable is True


def test_element_inspection_empty_custom_catalog_does_not_fall_back():
    result = inspect_basis_elements(
        "def2-TZVP",
        program="orca",
        elements=("Pd",),
        catalog={},
    )

    assert result.verdict == "reject"
    assert result.status == "catalog_unavailable"
    assert result.catalog_authority == "custom_non_authoritative"
    assert result.rule_ids == (
        "basis.element_inspection.custom_catalog_non_authoritative",
        "basis.element_inspection.catalog_unavailable",
    )
    assert result.error_class == "ValueError"


def test_element_inspection_version_mismatch_short_circuits_observation():
    with patch.object(
        basis_catalog.importlib_metadata,
        "version",
        return_value="9.9",
    ), patch.object(bse, "get_basis") as get_basis:
        result = inspect_basis_elements(
            "def2-TZVP",
            program="orca",
            elements=("Pd",),
        )

    assert result.verdict == "reject"
    assert result.status == "source_version_mismatch"
    assert result.rule_ids == (
        "basis.element_inspection.source_version_mismatch",
    )
    assert result.elements == ()
    assert result.definition_sha256 is None
    assert result.orbital_basis_usable is None
    assert result.error_class == "SourceVersionMismatch"
    get_basis.assert_not_called()


def test_element_inspection_dependency_failure_returns_typed_receipt():
    with patch.object(
        basis_catalog.importlib_metadata,
        "version",
        side_effect=metadata.PackageNotFoundError("basis_set_exchange"),
    ):
        result = inspect_basis_elements(
            "def2-TZVP",
            program="orca",
            elements=("Pd",),
        )

    assert result.verdict == "reject"
    assert result.status == "bse_data_unavailable"
    assert result.error_class == "PackageNotFoundError"
    assert result.definition_sha256 is None
    assert result.receipt_sha256_is_valid() is True


def test_element_inspection_data_failures_return_typed_receipts():
    with patch.object(bse, "get_basis", side_effect=OSError("unavailable")):
        unavailable = inspect_basis_elements(
            "def2-TZVP",
            program="orca",
            elements=("Pd",),
        )
    with patch.object(bse, "get_basis", return_value=None):
        malformed = inspect_basis_elements(
            "def2-TZVP",
            program="orca",
            elements=("Pd",),
        )

    assert unavailable.verdict == "reject"
    assert unavailable.status == "bse_data_unavailable"
    assert unavailable.error_class == "OSError"
    assert malformed.verdict == "reject"
    assert malformed.status == "bse_data_unavailable"
    assert malformed.error_class == "InvalidBSEPayloadError"


def test_element_inspection_rejects_incoherent_ecp_definition():
    inconsistent_data = {
        "elements": {
            "46": {
                "electron_shells": [{"fixture": "orbital"}],
                "ecp_potentials": [],
                "ecp_electrons": 28,
            }
        }
    }
    with patch.object(bse, "get_basis", return_value=inconsistent_data):
        result = inspect_basis_elements(
            "def2-TZVP",
            program="orca",
            elements=("Pd",),
        )

    assert result.verdict == "reject"
    assert result.status == "ecp_definition_inconsistent"
    assert result.ecp_definition_coherent is False
    assert result.rule_ids == (
        "basis.element_inspection.ecp_definition_inconsistent",
    )


def test_element_inspection_rejects_ecp_only_as_orbital_basis():
    result = inspect_basis_elements(
        "def2-ECP",
        program="orca",
        elements=("Pd",),
    )

    assert result.verdict == "reject"
    assert result.status == "orbital_functions_missing"
    assert result.orbital_basis_usable is False
    assert result.ecp_definition_coherent is True
    assert result.elements[0].orbital_present is False
    assert result.elements[0].ecp_present is True
    assert result.rule_ids == (
        "basis.element_inspection.orbital_functions_missing",
    )
