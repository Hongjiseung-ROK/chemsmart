from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from chemsmart.agent.harness.basis_sets.request_evidence import (
    build_request_bound_basis_evidence_request_v1,
    inspect_request_bound_basis_evidence_v1,
)
from chemsmart.agent.harness.scientific_settings import novel_challenge
from chemsmart.agent.harness.scientific_settings.lookup_v2 import (
    resolve_scientific_setting_v2,
)
from chemsmart.agent.harness.scientific_settings.novel_challenge import (
    NovelChallengeLifecycleState,
    load_novel_settings_challenge_v1,
    novel_settings_contract_schema_sha256,
)
from chemsmart.agent.harness.scientific_settings.registry_v2 import (
    load_populated_scientific_settings_inventories_v2,
    load_populated_scientific_settings_registry_v2,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = (
    ROOT
    / "docs/evaluation/fixtures/novel-settings-challenge-v1.json"
)
EXPECTED_CASE_IDS = (
    "g16-jkfit-as-orbital-reject",
    "g16-mn15-multifield-positive",
    "g16-wb97xd-reference-gap",
    "orca61-b97m-d4-double-dispersion",
    "orca61-bse-basis-pack-negative-control",
    "orca61-r2scan-ma-zora-native",
    "xtb671-gfn0-gbsa-extreme",
    "xtb671-gfn3-no-substitution",
)


def test_novel_settings_fixture_replays_all_content_bindings():
    challenge = load_novel_settings_challenge_v1(FIXTURE)

    assert tuple(case.case_id for case in challenge.cases) == EXPECTED_CASE_IDS
    assert challenge.maximum_lifecycle_state is (
        NovelChallengeLifecycleState.PLANNED
    )
    assert challenge.bindings.contract_schema_sha256 == (
        novel_settings_contract_schema_sha256()
    )


def test_novel_settings_cases_never_cross_the_planned_safety_ceiling():
    challenge = load_novel_settings_challenge_v1(FIXTURE)

    for case in challenge.cases:
        assert case.immutable_input.coordinate_artifact_ids == ()
        assert case.safety_ceiling.maximum_lifecycle_state is (
            NovelChallengeLifecycleState.PLANNED
        )
        boolean_controls = {
            key: value
            for key, value in case.safety_ceiling.model_dump().items()
            if isinstance(value, bool)
        }
        assert boolean_controls
        assert not any(boolean_controls.values())


def test_registry_and_request_bound_basis_oracles_match_fixture():
    challenge = load_novel_settings_challenge_v1(FIXTURE)
    registry = load_populated_scientific_settings_registry_v2()
    inventories = load_populated_scientific_settings_inventories_v2(
        repository_root=ROOT
    )

    for case in challenge.cases:
        for expected in case.immutable_input.setting_lookups:
            observed = resolve_scientific_setting_v2(
                registry=registry,
                loaded_inventories=inventories,
                program=case.immutable_input.program,
                setting_path=expected.setting_path,
                value=expected.requested_value,
                job_kind=expected.job_kind,
                allow_fuzzy_candidates=expected.allow_fuzzy_candidates,
            )
            assert observed.status is expected.expected_status
            assert observed.matched_by is expected.expected_match_kind
            assert observed.canonical_value == expected.expected_canonical_value
            expected_rules = set(expected.expected_reason_rule_ids)
            assert observed.reason_rule_id in expected_rules
            assert set(observed.applicability_rule_ids) <= expected_rules

        for index, expected in enumerate(
            case.immutable_input.basis_evidence,
            start=1,
        ):
            request = build_request_bound_basis_evidence_request_v1(
                request_id=f"{case.case_id}-basis-{index}",
                program=case.immutable_input.program.value,
                basis_literal=expected.basis_literal,
                role=expected.role,
                elements=expected.elements,
            )
            observed = inspect_request_bound_basis_evidence_v1(request)
            assert observed.state is expected.expected_state
            assert observed.catalog_role == expected.expected_catalog_role
            assert set(observed.reason_rule_ids) == set(
                expected.expected_reason_rule_ids
            )


def test_knowledge_ablation_targets_include_positive_and_negative_controls():
    challenge = load_novel_settings_challenge_v1(FIXTURE)
    cases = {case.case_id: case for case in challenge.cases}

    assert cases[
        "orca61-r2scan-ma-zora-native"
    ].expected_outcome.knowledge.selected_pack_ids == (
        "orca-explicit-native-basis-preservation",
    )
    for case_id in (
        "orca61-b97m-d4-double-dispersion",
        "orca61-bse-basis-pack-negative-control",
    ):
        expected = cases[case_id].expected_outcome.knowledge
        assert expected.expected_status.value == "no_match"
        assert expected.model_visible_exposure_requested is True
        assert expected.model_visible_exposure_expected is False

    for case_id in (
        "xtb671-gfn0-gbsa-extreme",
        "xtb671-gfn3-no-substitution",
    ):
        expected = cases[case_id].expected_outcome.knowledge
        assert expected.selected_pack_ids == (
            "xtb-explicit-method-semantics",
        )
        assert expected.can_certify_registry_validity is False
        assert expected.can_set_readiness is False


def test_novel_settings_contract_is_frozen_and_rejects_tampering(tmp_path):
    challenge = load_novel_settings_challenge_v1(FIXTURE)
    with pytest.raises(ValidationError, match="frozen"):
        challenge.cases[0].case_id = "mutated"  # type: ignore[misc]

    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["cases"][0]["novelty_reason"] += " Tampered."
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError, match="case digest mismatch"):
        load_novel_settings_challenge_v1(
            tampered,
            verify_current_bindings=False,
        )


def test_fixture_inputs_are_not_embedded_in_python_cases_tables():
    assert not hasattr(novel_challenge, "CASES")
    embedded_literals: set[str] = set()

    for source_path in (ROOT / "scripts").rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            value: ast.AST | None = None
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "CASES"
                for target in node.targets
            ):
                value = node.value
            elif (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "CASES"
            ):
                value = node.value
            if value is not None:
                embedded_literals.update(
                    child.value
                    for child in ast.walk(value)
                    if isinstance(child, ast.Constant)
                    and isinstance(child.value, str)
                )

    assert not (set(EXPECTED_CASE_IDS) & embedded_literals)
