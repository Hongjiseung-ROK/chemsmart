from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from chemsmart.agent.harness.scientific_settings import (
    SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION,
    ScientificSettingsInventoryDescriptorV2,
    ScientificSettingsInventoryV2,
    ScientificSettingsRegistryV2,
    load_scientific_settings_registry_v2,
    scientific_settings_inventory_v2_sha256,
    scientific_settings_registry_v2_sha256,
)
from chemsmart.agent.settings_registry_stress_receipts import (
    RegistryStressArm,
    RegistryStressCampaignPlanV1,
    RepositorySourceBindingV1,
)
from scripts.harness import run_registry_v2_stress_campaign as stress


ROOT = Path(__file__).resolve().parents[2]


def test_case_matrix_is_unique_and_covers_preregistered_defects():
    cases = {case.case_id: case for case in stress.CASES}

    assert len(cases) == len(stress.CASES) == 14
    assert len({case.hypothesis_family_id for case in stress.CASES}) == 14
    assert {
        "gaussian-pcseg2-materialization-gap",
        "orca-aug-mcc-pv8z-materialization-gap",
        "gaussian-fuzzy-def2-typo",
        "orca-def2-tzvp-fe-no-ecp",
        "orca-def2-tzvp-pd-28e-ecp",
        "gaussian-def2-tzvppd-missing-ce",
        "orca-def2-ecp-orbital-missing",
        "xtb-gfnff-alpb-n-hexane",
        "orca-b97m-d4-exact-compound",
        "gaussian-b3lyp-explicit-d4-unsupported",
        "orca-b3lyp-d3zero-unsupported",
        "gaussian-raw-route-functional-invalid",
        "xtb-cross-program-basis-not-applicable",
    }.issubset(cases)
    assert all(
        lookup.job_kind == case.project_accessor_job_kind
        for case in stress.CASES
        for lookup in case.lookup_expectations
    )
    assert all(
        case.project_accessor_job_kind == "opt"
        for case in stress.CASES
        if case.task_kind == "freq"
    )
    assert all(
        case.request_bound_validation_eligible is False
        and case.rule_discharge_mode == "none"
        for case in stress.CASES
    )


def test_source_binding_requires_clean_exact_remote_commit(tmp_path):
    repository = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    repository.mkdir()
    _run("git", "init", "--initial-branch", stress.REQUIRED_BRANCH, repository)
    _run("git", "config", "user.email", "stress@example.invalid", repository)
    _run("git", "config", "user.name", "Stress Test", repository)
    (repository / "tracked.txt").write_text("frozen\n", encoding="utf-8")
    _run("git", "add", "tracked.txt", repository)
    _run("git", "commit", "-m", "test: freeze source", repository)
    subprocess.run(
        ("git", "init", "--bare", str(remote)),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _run("git", "remote", "add", stress.REQUIRED_REMOTE, str(remote), repository)
    _run(
        "git",
        "push",
        "--set-upstream",
        stress.REQUIRED_REMOTE,
        stress.REQUIRED_BRANCH,
        repository,
    )
    head = _run("git", "rev-parse", "HEAD", repository).strip()

    binding = stress.capture_repository_binding(
        repository,
        base_checkpoint_sha=head,
        required_remote_url=str(remote),
    )

    assert binding.transport_eligible is True
    assert binding.dirty is False
    assert binding.remote_tracking_sha == binding.head_sha == head
    stress.assert_transport_source_ready(repository, binding)

    (repository / "untracked.txt").write_text("drift\n", encoding="utf-8")
    dirty = stress.capture_repository_binding(
        repository,
        base_checkpoint_sha=head,
        required_remote_url=str(remote),
    )
    assert dirty.transport_eligible is False
    with pytest.raises(RuntimeError, match="clean worktree"):
        stress.assert_transport_source_ready(repository, dirty)


def test_repository_source_binding_rejects_inconsistent_eligibility():
    body = stress.capture_repository_binding(ROOT).model_dump(mode="json")
    body["transport_eligible"] = not body["transport_eligible"]
    body["binding_sha256"] = stress.repository_source_binding_sha256(body)

    with pytest.raises(ValidationError, match="eligibility"):
        RepositorySourceBindingV1.model_validate(body)


def test_source_binding_rejects_a_remote_name_retarget(tmp_path):
    repository = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    repository.mkdir()
    remote.mkdir()
    _run("git", "init", "--initial-branch", stress.REQUIRED_BRANCH, repository)
    _run("git", "config", "user.email", "stress@example.invalid", repository)
    _run("git", "config", "user.name", "Stress Test", repository)
    (repository / "tracked.txt").write_text("frozen\n", encoding="utf-8")
    _run("git", "add", "tracked.txt", repository)
    _run("git", "commit", "-m", "test: freeze source", repository)
    _run("git", "remote", "add", stress.REQUIRED_REMOTE, str(remote), repository)

    with pytest.raises(RuntimeError, match="wrong remote"):
        stress.capture_repository_binding(
            repository,
            base_checkpoint_sha="0" * 40,
        )


def test_live_runner_fails_before_credential_on_empty_v2(monkeypatch, tmp_path):
    credential_accessed = False

    def credential_forbidden(_path):
        nonlocal credential_accessed
        credential_accessed = True
        raise AssertionError("credential access must not occur")

    monkeypatch.setattr(
        stress,
        "load_populated_scientific_settings_registry_v2",
        load_scientific_settings_registry_v2,
    )
    monkeypatch.setattr(stress, "_credential_environment", credential_forbidden)

    with pytest.raises(RuntimeError, match="empty skeleton"):
        stress.run_campaign(
            repository_root=ROOT,
            api_env=tmp_path / "unused.env",
            run_root=tmp_path / "runs",
            output_dir=tmp_path / "outputs",
        )
    assert credential_accessed is False


def test_tiny_v2_fixture_builds_typed_minimal_v1_v2_arms(tmp_path):
    bundle = _tiny_bundle(tmp_path)
    source = stress.capture_repository_binding(ROOT)
    selected = tuple(
        _case(case_id)
        for case_id in (
            "gaussian-pcseg2-materialization-gap",
            "gaussian-fuzzy-def2-typo",
            "xtb-cross-program-basis-not-applicable",
        )
    )

    plan = stress.prepare_campaign(
        repository_root=ROOT,
        bundle=bundle,
        source_binding=source,
        network_budget_sha256="a" * 64,
        cases=selected,
    )

    assert isinstance(plan, RegistryStressCampaignPlanV1)
    assert len(plan.runs) == 9
    assert plan.registry_binding.v2_fallback_to_v1_allowed is False
    for case in selected:
        assert {
            run.arm for run in plan.runs if run.case_id == case.case_id
        } == {
            RegistryStressArm.MINIMAL,
            RegistryStressArm.REGISTRY_V1,
            RegistryStressArm.REGISTRY_V2,
        }
    v2 = stress.build_arm_registry(
        selected[0],
        RegistryStressArm.REGISTRY_V2,
        bundle,
    )
    names = {tool.name for tool in v2.list_tools()}
    assert "resolve_scientific_setting_v2" in names
    assert "list_scientific_settings_v2" in names
    assert not any(name.endswith("_v1") for name in names)


def test_v2_tool_schema_is_typed_and_never_exposes_v1(tmp_path):
    bundle = _tiny_bundle(tmp_path)
    registry = stress.build_arm_registry(
        _case("gaussian-pcseg2-materialization-gap"),
        RegistryStressArm.REGISTRY_V2,
        bundle,
    )
    definitions = stress.model_visible_tool_defs(registry)
    by_name = {item["function"]["name"]: item["function"] for item in definitions}
    parameters = by_name["resolve_scientific_setting_v2"]["parameters"]

    assert set(parameters["properties"]) == {
        "program",
        "setting_path",
        "value",
        "job_kind",
        "allow_fuzzy_candidates",
        "candidate_limit",
    }
    assert parameters["properties"]["program"]["enum"] == [
        "gaussian",
        "orca",
        "xtb",
    ]
    assert "resolve_scientific_setting_v1" not in by_name


def test_explicit_settings_are_case_scoped_lookup_values():
    case = _case("orca-ma-def2-tzvp-cross-field-blocked")

    stress._validate_lookup_scope(
        case,
        "orca",
        "method.functional",
        "opt",
        "B3LYP",
    )
    with pytest.raises(ValueError, match="outside the case scope"):
        stress._validate_lookup_scope(
            case,
            "orca",
            "method.functional",
            "opt",
            "PBE0",
        )


def test_advisory_tool_exists_only_in_preregistered_advisory_arm(tmp_path):
    bundle = _tiny_bundle(tmp_path)
    eligible = _case("orca-def2-tzvp-pd-28e-ecp")
    ordinary = stress.build_arm_registry(
        eligible,
        RegistryStressArm.REGISTRY_V2,
        bundle,
    )
    advisory = stress.build_arm_registry(
        eligible,
        RegistryStressArm.REGISTRY_V2_ADVISORY,
        bundle,
    )

    assert "inspect_case_knowledge_advisory" not in {
        item.name for item in ordinary.list_tools()
    }
    assert "inspect_case_knowledge_advisory" in {
        item.name for item in advisory.list_tools()
    }
    with pytest.raises(ValueError, match="not preregistered"):
        stress.build_arm_registry(
            _case("gaussian-fuzzy-def2-typo"),
            RegistryStressArm.REGISTRY_V2_ADVISORY,
            bundle,
        )


def test_fuzzy_candidate_cannot_be_silently_substituted():
    case = _case("gaussian-fuzzy-def2-typo")
    payload = {
        "case_id": case.case_id,
        "program": "gaussian",
        "project_name": "stress-fuzzy",
        "readiness": "blocked_unverified_setting",
        "settings": {
            "functional": "B3LYP",
            "basis": "def2-TZVP",
            "freq": True,
        },
        "blocking_rule_ids": [
            "scientific_settings.v2.candidate_requires_selection"
        ],
        "analysis_summary": "The nearest candidate was selected.",
        "native_input_authored": False,
        "command_authored": False,
        "project_written": False,
        "execution_requested": False,
    }

    grade = stress.grade_proposal(case, payload)

    assert grade["oracle_passed"] is False
    assert "oracle.fuzzy-no-substitution" in grade["failed_oracle_ids"]
    assert "oracle.setting-preservation" in grade["failed_oracle_ids"]


def test_plain_v2_baseline_keeps_request_bound_validator_hidden():
    bundle = stress.load_registry_v2_bundle(ROOT)
    case = _case("orca-def2-tzvp-pd-28e-ecp")
    registry = stress.build_arm_registry(
        case,
        RegistryStressArm.REGISTRY_V2,
        bundle,
    )
    assert case.request_bound_validation_eligible is False
    assert "inspect_basis_elements_v2" not in {
        tool.name for tool in registry.list_tools()
    }
    with pytest.raises(ValueError, match="not preregistered"):
        stress.build_arm_registry(
            case,
            RegistryStressArm.REGISTRY_V2_VALIDATED,
            bundle,
        )


def test_host_preflight_retains_raw_resolution_and_hidden_basis_receipt():
    bundle = stress.load_registry_v2_bundle(ROOT)
    case = _case("orca-def2-tzvp-pd-28e-ecp")

    receipt = stress.build_case_preflight(case, bundle)

    assert receipt.raw_v2_resolutions[0]["status"] == (
        "blocked_validation_coverage"
    )
    assert receipt.raw_v2_resolutions[0]["entry_evidence_sha256"]
    assert receipt.basis_element_receipt["receipt_sha256"]
    assert receipt.basis_element_receipt["elements"][1]["ecp_electrons"] == 28


def test_plain_v2_rejects_host_only_pd_promotion():
    case = _case("orca-def2-tzvp-pd-28e-ecp")
    false_ready = _proposal(case)
    false_ready["readiness"] = "project_candidate"
    false_ready["element_findings"] = [
        item.model_dump(mode="json")
        for item in case.basis_element_expectation.expected_findings
    ]

    grade = stress.grade_proposal(
        case,
        false_ready,
        arm=RegistryStressArm.REGISTRY_V2,
    )

    assert grade["oracle_passed"] is False
    assert "oracle.honest-readiness" in grade["failed_oracle_ids"]
    assert "oracle.basis-element-semantics" in grade["failed_oracle_ids"]


def test_xtb_solvent_pair_stays_blocked_without_compatibility_validator():
    bundle = stress.load_registry_v2_bundle(ROOT)
    case = _case("xtb-gfnff-alpb-n-hexane")
    registry = stress.build_arm_registry(
        case,
        RegistryStressArm.REGISTRY_V2,
        bundle,
    )
    outcomes = tuple(
        _outcome(
            "resolve_scientific_setting_v2",
            registry.call(
                "resolve_scientific_setting_v2",
                {
                    "program": item.program,
                    "setting_path": item.setting_path,
                    "value": item.requested_value,
                    "job_kind": item.job_kind,
                },
            ),
        )
        for item in case.lookup_expectations
    )

    blocked = stress.grade_proposal(
        case,
        _proposal(case),
        arm=RegistryStressArm.REGISTRY_V2,
        tool_outcomes=outcomes,
    )
    false_ready = _proposal(case)
    false_ready["readiness"] = "project_candidate"
    rejected = stress.grade_proposal(
        case,
        false_ready,
        arm=RegistryStressArm.REGISTRY_V2,
        tool_outcomes=outcomes,
    )

    assert blocked["oracle_passed"] is True
    assert rejected["oracle_passed"] is False


def test_tool_only_turn_retains_typed_english_summary():
    public, assistant, typed = stress._public_english_response(
        result={"assistant_output": ""},
        proposal_payload={
            "analysis_summary": "The basis remains blocked pending evidence."
        },
    )

    assert assistant == ""
    assert typed == public == (
        "The basis remains blocked pending evidence."
    )


@pytest.mark.parametrize(
    ("public_text", "failed_oracle"),
    (
        ("! B3LYP def2-SVP", "oracle.native-input-prohibited"),
        ("Run chemsmart run orca opt.", "oracle.command-prohibited"),
    ),
)
def test_public_assistant_text_cannot_bypass_typed_safety_oracles(
    public_text,
    failed_oracle,
):
    case = _case("orca-b97m-d4-exact-compound")

    grade = stress.grade_proposal(
        case,
        _proposal(case),
        arm=RegistryStressArm.REGISTRY_V2,
        public_text=public_text,
    )

    assert grade["oracle_passed"] is False
    assert failed_oracle in grade["failed_oracle_ids"]


def test_exactly_one_successful_typed_submission_is_required():
    payload = _proposal(_case("orca-b97m-d4-exact-compound"))
    outcome = _outcome("submit_registry_stress_plan", payload)

    assert stress._proposal_from_outcomes((outcome,)) == (
        payload,
        1,
        None,
        payload,
    )
    assert stress._proposal_from_outcomes((outcome, outcome)) == (
        None,
        2,
        None,
        None,
    )


def test_submission_normalizer_fills_omission_and_sorts_sets():
    case = _case("orca-ma-def2-tzvp-cross-field-blocked")
    payload = _proposal(case)
    payload["settings"]["freq"] = None
    payload["blocking_rule_ids"] = ["z.rule", "a.rule", "z.rule"]

    normalized, receipt = stress._normalize_case_bound_submission(
        case,
        payload,
    )

    assert normalized["settings"]["freq"] is True
    assert normalized["blocking_rule_ids"] == ["a.rule", "z.rule"]
    assert receipt.filled_explicit_setting_fields == ("settings.freq",)
    assert receipt.canonicalized_set_fields == ("blocking_rule_ids",)
    assert receipt.conflicting_explicit_setting_fields == ()
    assert receipt.raw_contract_valid is False
    assert receipt.raw_contract_error_paths == ("blocking_rule_ids",)
    assert receipt.normalization_applied is True


def test_submission_normalizer_never_overwrites_a_contradiction():
    case = _case("gaussian-pcseg2-materialization-gap")
    payload = _proposal(case)
    payload["settings"]["functional"] = "PBE0"

    normalized, receipt = stress._normalize_case_bound_submission(
        case,
        payload,
    )
    grade = stress.grade_proposal(
        case,
        normalized,
        arm=RegistryStressArm.REGISTRY_V2,
        normalization_receipt=receipt.model_dump(mode="json"),
    )

    assert normalized["settings"]["functional"] == "PBE0"
    assert receipt.conflicting_explicit_setting_fields == (
        "settings.functional",
    )
    assert receipt.raw_contract_valid is True
    assert "oracle.setting-preservation" in grade["failed_oracle_ids"]


def test_submission_normalizer_rejects_a_missing_settings_object():
    case = _case("gaussian-pcseg2-materialization-gap")
    payload = _proposal(case)
    payload.pop("settings")

    with pytest.raises(ValueError, match="settings must be an object"):
        stress._normalize_case_bound_submission(case, payload)


def test_submission_normalizer_is_idempotent_and_rejects_unknown_fields():
    case = _case("orca-ma-def2-tzvp-cross-field-blocked")
    payload = _proposal(case)
    payload["settings"]["freq"] = None

    once, first_receipt = stress._normalize_case_bound_submission(case, payload)
    twice, second_receipt = stress._normalize_case_bound_submission(case, once)
    assert once == twice
    assert first_receipt.normalization_applied is True
    assert second_receipt.normalization_applied is False

    invalid = dict(payload)
    invalid["unregistered_field"] = "forbidden"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        stress._normalize_case_bound_submission(case, invalid)


@pytest.mark.parametrize("explicit_empty", ([], {}))
def test_submission_normalizer_does_not_fill_explicit_empty_values(
    explicit_empty,
):
    case = _case("gaussian-pcseg2-materialization-gap")
    payload = _proposal(case)
    payload["settings"]["basis"] = explicit_empty

    with pytest.raises(ValidationError):
        stress._normalize_case_bound_submission(case, payload)


@pytest.mark.parametrize(
    "payload",
    (
        {"reasoning_content": "private"},
        {"type": "analysis", "text": "private"},
        {"nested": [{"thinking": "private"}]},
        {"content": "<think>private</think>public"},
    ),
)
def test_private_reasoning_detector_matches_runtime_sanitizer_shapes(payload):
    assert stress._contains_private_reasoning(payload) is True


def _case(case_id: str):
    return next(case for case in stress.CASES if case.case_id == case_id)


def _proposal(case):
    return {
        "case_id": case.case_id,
        "program": case.program,
        "project_name": f"stress-{case.case_id}",
        "readiness": case.expected_readiness.value,
        "settings": case.expected_settings.model_dump(mode="json"),
        "blocking_rule_ids": list(case.expected_blocking_rule_ids),
        "element_findings": [],
        "analysis_summary": "The typed evidence was evaluated conservatively.",
        "native_input_authored": False,
        "command_authored": False,
        "project_written": False,
        "execution_requested": False,
    }


def _outcome(name: str, result: dict[str, object]):
    return {"name": name, "status": "ok", "result": result}


def _run(*arguments):
    *command, repository = arguments
    completed = subprocess.run(
        tuple(str(item) for item in command),
        cwd=repository,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout


def _tiny_bundle(tmp_path: Path) -> stress.LoadedRegistryV2Bundle:
    entries = tuple(
        sorted(
            (
                _entry(
                    "entry.gaussian.def2-tzvp",
                    "gaussian",
                    "method.basis",
                    "def2-TZVP",
                ),
                _entry(
                    "entry.gaussian.pcseg-2",
                    "gaussian",
                    "method.basis",
                    "pcseg-2",
                    rules=(
                        "scientific_settings.basis.bse_materialization_required",
                    ),
                ),
            ),
            key=lambda item: str(item["entry_id"]),
        )
    )
    source = {
        "source_id": "source.one",
        "source_kind": "checked_in_loader_renderer",
        "locator": "tests/fixtures/scientific-settings.json",
        "artifact_sha256": "3" * 64,
        "source_revision": "fixture-v1",
    }
    inventory_body = {
        "schema_version": "chemsmart.scientific-settings-inventory.v2",
        "inventory_id": "inventory.stress-fixture",
        "inventory_version": "2.1.0-test",
        "normalization_version": (
            SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION
        ),
        "sources": (source,),
        "entries": entries,
        "evidence_ceiling": (
            load_scientific_settings_registry_v2()
            .evidence_ceiling.model_dump(mode="json")
        ),
    }
    inventory_body["inventory_sha256"] = (
        scientific_settings_inventory_v2_sha256(inventory_body)
    )
    inventory = ScientificSettingsInventoryV2.model_validate(inventory_body)
    artifact_bytes = json.dumps(
        inventory.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    (tmp_path / "inventory.json").write_bytes(artifact_bytes)
    counts = Counter(
        (entry.program.value, entry.setting_path) for entry in inventory.entries
    )
    descriptor = ScientificSettingsInventoryDescriptorV2.model_validate(
        {
            "schema_version": (
                "chemsmart.scientific-settings-inventory-descriptor.v2"
            ),
            "inventory_schema_version": (
                "chemsmart.scientific-settings-inventory.v2"
            ),
            "normalization_version": (
                SCIENTIFIC_SETTING_NORMALIZATION_POPULATED_VERSION
            ),
            "inventory_id": inventory.inventory_id,
            "inventory_version": inventory.inventory_version,
            "inventory_sha256": inventory.inventory_sha256,
            "artifact_locator": "inventory.json",
            "artifact_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
            "entry_count": len(entries),
            "scopes": tuple(
                {
                    "program": program,
                    "setting_path": path,
                    "entry_count": count,
                }
                for (program, path), count in sorted(counts.items())
            ),
        }
    )
    registry_body = load_scientific_settings_registry_v2().model_dump(
        mode="json"
    )
    registry_body.update(
        {
            "registry_id": "chemsmart.scientific-settings.stress-fixture",
            "registry_version": "2.1.0-test",
            "inventories": (descriptor.model_dump(mode="json"),),
            "inventory_population_state": "populated",
        }
    )
    registry_body["registry_sha256"] = (
        scientific_settings_registry_v2_sha256(registry_body)
    )
    registry = ScientificSettingsRegistryV2.model_validate(registry_body)
    return stress.LoadedRegistryV2Bundle(
        registry=registry,
        inventories=(inventory,),
    )


def _entry(
    entry_id: str,
    program: str,
    setting_path: str,
    value: str,
    *,
    rules: tuple[str, ...] = (),
):
    return {
        "entry_id": entry_id,
        "program": program,
        "setting_path": setting_path,
        "canonical_value": value,
        "aliases": (),
        "applicable_job_kinds": ("opt",),
        "applicability_rule_ids": rules,
        "validator_enforced": False,
        "source_ids": ("source.one",),
        "loader_observation": "accepted",
        "renderer_observation": "preserved",
        "observation_note": "Deterministic tiny-fixture observation.",
        "engine_executed": False,
        "combination_verified": False,
    }
