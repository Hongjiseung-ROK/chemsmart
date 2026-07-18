"""Machine-readable preservation contract checks for the desktop project."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "docs/design/chemsmart_desktop_feature_contract.yaml"


def _contract() -> dict:
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


def test_feature_contract_has_unique_policy_and_surface_ids() -> None:
    contract = _contract()
    policy_ids = [policy["id"] for policy in contract["policies"]]
    surface_ids = [surface["id"] for surface in contract["surfaces"]]

    assert len(policy_ids) == len(set(policy_ids)) == 6
    assert len(surface_ids) == len(set(surface_ids)) == 17


def test_feature_contract_sources_exist_and_every_surface_has_gates() -> None:
    for surface in _contract()["surfaces"]:
        assert surface["gates"], surface["id"]
        if not surface["sources"]:
            assert surface["desktop_v1"] == "planned_missing_backend"
        for source in surface["sources"]:
            assert (REPO_ROOT / source).exists(), (surface["id"], source)


def test_every_surface_has_an_explicit_desktop_disposition() -> None:
    allowed = {
        "expose",
        "expose_fake_only",
        "expose_safe_profile",
        "expose_project_defer_environment_wizard",
        "expose_interactive_optional_pymol",
        "preserve_backend_block_ui",
        "preserve_backend_defer_ui",
        "planned_missing_backend",
        "selected_pyinstaller",
    }

    for surface in _contract()["surfaces"]:
        assert surface["desktop_v1"] in allowed, surface["id"]


def test_macos_packaging_decision_is_pinned_to_retained_p1_evidence() -> None:
    packaging = next(
        surface
        for surface in _contract()["surfaces"]
        if surface["id"] == "macos_packaging"
    )

    assert packaging["desktop_v1"] == "selected_pyinstaller"
    assert packaging["selected_candidate"] == "pyinstaller"
    assert packaging["fallback_candidate"] == "pyside6-deploy"
    assert packaging["fallback_status"] == (
        "red_code_data_layout_in_contents_macos"
    )
    assert {
        "pyinstaller_decision_receipt_retained",
        "pyside_structural_failure_receipts_retained",
    } <= set(packaging["gates"])
