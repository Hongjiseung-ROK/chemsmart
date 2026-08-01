from __future__ import annotations

from chemsmart.agent.settings_knowledge_experiment import (
    case_by_id,
    grade_settings_plan,
    inspect_domain_knowledge,
    inspect_scientific_setting,
)
from chemsmart.agent.settings_knowledge_ablation import (
    SettingsKnowledgeExposureV2,
)
from chemsmart.agent.loop import ToolLoop
from chemsmart.agent.permissions import RuntimePermissionMode
from scripts.harness.run_settings_knowledge_ablation import (
    _model_visible_tool_defs,
    _profile,
    _proposal_from_outcomes,
    _registry,
)


def _base(case_id: str, program: str) -> dict:
    return {
        "case_id": case_id,
        "program": program,
        "project_name": f"{case_id}-candidate",
        "charge": 0,
        "multiplicity": 1,
        "missing_fact_ids": [],
        "analysis_summary": "I preserved explicit settings and applied the host evidence ceiling.",
        "native_input_authored": False,
        "execution_requested": False,
    }


def test_orca_exact_native_setting_case_passes_deterministic_oracles() -> None:
    proposal = {
        **_base("orca-native-basis", "orca"),
        "readiness": "project_candidate",
        "functional": "B3LYP",
        "basis": "ma-def2-TZVP",
        "dispersion": "D3BJ",
    }

    grade = grade_settings_plan(case_by_id("orca-native-basis"), proposal)

    assert grade["oracle_passed"] is True
    assert grade["failed_oracle_ids"] == []
    assert grade["details"]["project_validation"]["verdict"] == "ok"
    assert grade["details"]["project_semantics"]["dispersion"] == "D3BJ"
    assert grade["details"]["project_semantic_findings"] == []


def test_gaussian_registry_gap_requires_honest_block_without_substitution() -> None:
    proposal = {
        **_base("gaussian-m08hx-grid", "gaussian"),
        "readiness": "blocked_unverified_setting",
        "functional": "M08-HX",
        "basis": "pcseg-2",
        "integration_grid": "UltraFine",
    }

    grade = grade_settings_plan(case_by_id("gaussian-m08hx-grid"), proposal)

    assert grade["oracle_passed"] is True
    statuses = {
        item["setting_path"]: item["status"]
        for item in grade["details"]["setting_resolutions"]
    }
    assert statuses["method.basis"] == "exact_registered"
    assert statuses["method.functional"] == "unknown_unverified"
    assert statuses["method.integration_grid"] == "unknown_unverified"


def test_xtb_case_rejects_invented_basis_and_false_readiness() -> None:
    proposal = {
        **_base("xtb-gfn2-alpb-water", "xtb"),
        "readiness": "project_candidate",
        "gfn_version": "gfn2",
        "basis": "def2-SVP",
        "solvent_model": "alpb",
        "solvent_id": "water",
    }

    grade = grade_settings_plan(case_by_id("xtb-gfn2-alpb-water"), proposal)

    assert grade["oracle_passed"] is False
    assert "oracle.xtb-basis-not-applicable" in grade["failed_oracle_ids"]
    assert "oracle.honest-readiness" in grade["failed_oracle_ids"]
    assert "oracle.no-cross-program-settings" in grade["failed_oracle_ids"]
    assert grade["details"]["readiness"]["classification"] == "false_ready"


def test_readiness_oracle_separates_conservative_false_block() -> None:
    proposal = {
        **_base("orca-native-basis", "orca"),
        "readiness": "blocked_missing_evidence",
        "functional": "B3LYP",
        "basis": "ma-def2-TZVP",
        "dispersion": "D3BJ",
    }

    grade = grade_settings_plan(case_by_id("orca-native-basis"), proposal)

    assert "oracle.honest-readiness" in grade["failed_oracle_ids"]
    assert grade["details"]["readiness"] == {
        "observed": "blocked_missing_evidence",
        "expected": "project_candidate",
        "classification": "false_block",
    }


def test_grader_rejects_state_drift_and_native_input_text() -> None:
    proposal = {
        **_base("orca-native-basis", "orca"),
        "readiness": "project_candidate",
        "functional": "B3LYP",
        "basis": "ma-def2-TZVP",
        "dispersion": "D3BJ",
        "charge": 1,
        "analysis_summary": "%pal nprocs 8 end",
    }

    grade = grade_settings_plan(case_by_id("orca-native-basis"), proposal)

    assert grade["oracle_passed"] is False
    assert "oracle.charge" in grade["failed_oracle_ids"]
    assert "oracle.native-input-text-prohibited" in grade["failed_oracle_ids"]


def test_exposure_tools_return_bounded_registry_and_read_only_pack_data() -> None:
    basis = inspect_scientific_setting(
        "orca", "method.basis", "ma-def2-TZVP", "freq"
    )
    xtb_basis = inspect_scientific_setting("xtb", "method.basis")
    knowledge = inspect_domain_knowledge(
        "general", "orca", "6.1", "frequency"
    )

    assert basis["status"] == "exact_registered"
    assert xtb_basis["status"] == "not_applicable"
    assert knowledge["activation_receipt"]["can_execute"] is False
    assert knowledge["activation_receipt"]["can_fill_missing_paper_facts"] is False
    assert [item["pack_id"] for item in knowledge["packs"]] == [
        "orca-explicit-native-basis-preservation"
    ]


def test_preregistered_tool_schema_matches_runtime_v2_visible_surface() -> None:
    for exposure in (
        SettingsKnowledgeExposureV2(),
        SettingsKnowledgeExposureV2(scientific_settings_registry=True),
        SettingsKnowledgeExposureV2(domain_knowledge_packs=True),
        SettingsKnowledgeExposureV2(
            scientific_settings_registry=True,
            domain_knowledge_packs=True,
        ),
    ):
        registry = _registry(exposure, case_by_id("orca-native-basis"))
        names = {tool.name for tool in registry.list_tools()}
        loop = ToolLoop(
            provider=object(),
            registry=registry,
            handle_store=None,
            decision_log=object(),
        )
        runtime_defs = loop._filter_tool_defs(
            "openai",
            loop._tool_defs_for_mode(
                "openai", RuntimePermissionMode.READ_ONLY
            ),
            names,
        )

        assert _model_visible_tool_defs(registry) == runtime_defs
        assert _profile(registry).capability_names == frozenset(names)
        assert runtime_defs[-1]["function"]["name"] == "ask_user"
        for definition in runtime_defs:
            if definition["function"]["name"].startswith("inspect_case_"):
                parameters = definition["function"]["parameters"]
                assert parameters["properties"] == {}
                assert parameters.get("required", []) == []


def test_only_successful_terminal_outcome_is_accepted_as_proposal() -> None:
    proposal = {"case_id": "orca-native-basis"}

    assert _proposal_from_outcomes(
        [
            {
                "name": "submit_settings_plan",
                "status": "skipped",
                "result": proposal,
            }
        ]
    ) is None
    assert _proposal_from_outcomes(
        [
            {
                "name": "submit_settings_plan",
                "status": "ok",
                "result": proposal,
            }
        ]
    ) == proposal
