from __future__ import annotations

from chemsmart.agent.settings_knowledge_ablation import (
    SettingsKnowledgeExposureV2,
    SettingsKnowledgeFixedContextV2,
    build_settings_knowledge_run_spec,
    validate_complete_settings_knowledge_block,
)


_A = "a" * 64
_B = "b" * 64
_C = "c" * 64
_D = "d" * 64


def _context() -> SettingsKnowledgeFixedContextV2:
    return SettingsKnowledgeFixedContextV2(
        case_id="orca-urea-setting-probe",
        source_bundle_sha256=_A,
        coordinate_receipt_sha256=None,
        base_prompt_template_sha256=_B,
        host_tool_catalog_sha256=_C,
        scientific_settings_registry_sha256=_D,
        domain_knowledge_catalog_sha256=_A,
        project_schema_sha256=_B,
        cli_schema_sha256=_C,
        validator_registry_sha256=_D,
        task_order_sha256=_A,
        network_budget_sha256=_B,
        prompt_version="settings-knowledge-v2",
    )


def _run(
    suffix: str,
    exposure: SettingsKnowledgeExposureV2,
    order: int,
):
    factor = {
        "S0K0": "reference",
        "S1K0": "scientific_settings_registry",
        "S0K1": "domain_knowledge_packs",
        "S1K1": "joint_exposure",
    }[exposure.arm.value]
    return build_settings_knowledge_run_spec(
        run_id=f"run-{suffix}",
        hypothesis_id=f"hypothesis-{suffix}",
        hypothesis="Typed guidance preserves evidenced scientific settings.",
        comparator="The frozen S0K0 model-visible surface.",
        changed_factor=factor,
        expected_outcome="No unsupported substitution or false-ready state.",
        deterministic_oracle_ids=(
            "oracle.project-loader",
            "oracle.setting-preservation",
        ),
        novelty_rationale=f"First frozen observation for arm {suffix}.",
        order_ordinal=order,
        exposure=exposure,
        fixed_context=_context(),
        rendered_prompt_sha256=_C,
        exposed_tool_schema_sha256=_D,
    )


def test_four_arm_block_is_complete_and_keeps_safety_enabled() -> None:
    runs = (
        _run("S0K0", SettingsKnowledgeExposureV2(), 1),
        _run(
            "S1K0",
            SettingsKnowledgeExposureV2(scientific_settings_registry=True),
            2,
        ),
        _run(
            "S0K1",
            SettingsKnowledgeExposureV2(domain_knowledge_packs=True),
            3,
        ),
        _run(
            "S1K1",
            SettingsKnowledgeExposureV2(
                scientific_settings_registry=True,
                domain_knowledge_packs=True,
            ),
            4,
        ),
    )

    assert validate_complete_settings_knowledge_block(runs) == ()
    assert {run.exposure.arm.value for run in runs} == {
        "S0K0",
        "S1K0",
        "S0K1",
        "S1K1",
    }
    assert all(run.safety_plane.scientific_settings_validation for run in runs)
    assert all(not run.safety_plane.native_input_authoring_allowed for run in runs)


def test_four_arm_block_rejects_missing_arm_or_context_drift() -> None:
    reference = _run("S0K0", SettingsKnowledgeExposureV2(), 1)
    duplicate = _run("S0K0-copy", SettingsKnowledgeExposureV2(), 2)

    assert validate_complete_settings_knowledge_block(
        (reference, duplicate)
    ) == ("ablation.v2.four_arms_required",)
