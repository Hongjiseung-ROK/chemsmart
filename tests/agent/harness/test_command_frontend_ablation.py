from __future__ import annotations

from chemsmart.agent.harness.command_frontend_ablation import (
    compare_frontends,
    observe_direct_command,
    observe_typed_workflow,
)
from chemsmart.agent.harness.command_semantics import CommandSemanticResult
from chemsmart.agent.harness.intent import IntentSpec, evaluate_intent


def test_m2_frontend_comparison_is_path_free_and_non_adoptive(tmp_path) -> None:
    command = (
        "chemsmart run xtb --filename water.xyz --charge 0 "
        "--multiplicity 1 opt"
    )
    direct = observe_direct_command(
        fixture_id="water-xtb-opt",
        fixture_sha256="a" * 64,
        semantic=CommandSemanticResult(verdict="ok", command=command),
        intent=evaluate_intent(
            command,
            IntentSpec(
                action="run",
                program="xtb",
                kind="xtb.opt",
                input_path="water.xyz",
                charge=0,
                multiplicity=1,
            ),
            cwd=str(tmp_path),
        ),
        parser_cwd=str(tmp_path),
    )
    typed = observe_typed_workflow(
        fixture_id="water-xtb-opt",
        fixture_sha256="a" * 64,
        receipt={
            "status": "previewed",
            "compilation_status": "previewable",
            "cli_schema_digest": "b" * 64,
            "render_digest": "c" * 64,
            "compiler_findings": [],
            "invocations": [
                {
                    "parser": {
                        "verdict": "ok",
                        "matches_invocation": True,
                    },
                    "intent": {"verdict": "ok", "failed_rule_ids": []},
                    "safe_preview": {"verdict": "ok", "rule_ids": []},
                    "findings": [],
                }
            ],
        },
    )

    comparison = compare_frontends(direct, typed)
    payload = comparison.to_dict()

    assert direct.status == "accepted"
    assert typed.status == "accepted"
    assert comparison.efficacy_decision == "experimental_not_adopted"
    assert "M5" in comparison.decision_reason
    assert command not in repr(payload)
    assert str(tmp_path) not in repr(payload)


def test_missing_typed_receipt_is_not_compared_as_a_success() -> None:
    observation = observe_typed_workflow(
        fixture_id="water-xtb-opt",
        fixture_sha256="a" * 64,
        receipt={"status": "blocked", "invocations": []},
    )

    assert observation.status == "not_observed"
    assert observation.rule_ids == ("cmd.ablation.typed_receipt_missing",)
