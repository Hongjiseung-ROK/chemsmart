"""A delivery with stated limitations and a full delivery shared one
word. The completion gate knowingly admits a required output whose
producer the approved plan declared blocked_unsupported -- that is the
qualified delivered-with-stated-limitation behavior -- but the receipt
said only "passed", so the one live session that refused an
unreachable observable with receipts settled as if it had delivered
everything. The receipt now names the blocked required outputs.
"""

import json

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.analysis_completion import AnalysisCompletionReceiptV1
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.scientific_toolchain import (
    AnalysisInputIntentV1,
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    AnalysisSelectorIntentV1,
    RegisteredResultInputIntentV1,
    build_scientific_toolchain_plan,
)
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.agent.workflows import build_command_workflow_draft


def _analysis_only_plan(*, blocked_thermochemistry, draft_sha256="9" * 64):
    extraction = AnalysisNodeIntentV1(
        node_id="extract-e",
        analysis_kind="result_extraction",
        dependencies=(),
        inputs=(
            RegisteredResultInputIntentV1(
                input_id="raw", artifact_id="registered-sp"
            ),
        ),
        selectors=(
            AnalysisSelectorIntentV1(quantity_id="e", selector="energy"),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="e", quantity_kind="energy", unit="hartree"
            ),
        ),
        expression_nodes=(),
        expression_output_node_ids=(),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )
    claim = AnalysisNodeIntentV1(
        node_id="claim-e",
        analysis_kind="claim_rendering",
        dependencies=("extract-e",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="value",
                source_kind="analysis_output",
                producer_node_id="extract-e",
                producer_output_id="e",
            ),
        ),
        selectors=(),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="e_claim", quantity_kind="energy", unit="hartree"
            ),
        ),
        expression_nodes=(),
        expression_output_node_ids=(),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )
    nodes = [extraction, claim]
    required = ["e"]
    if blocked_thermochemistry:
        nodes.append(
            AnalysisNodeIntentV1(
                node_id="derive-dg",
                analysis_kind="thermochemistry",
                dependencies=(),
                inputs=(
                    RegisteredResultInputIntentV1(
                        input_id="freq", artifact_id="registered-sp"
                    ),
                ),
                selectors=(),
                outputs=(
                    AnalysisOutputIntentV1(
                        output_id="dg",
                        quantity_kind="gibbs_free_energy",
                        unit="hartree",
                    ),
                ),
                expression_nodes=(),
                expression_output_node_ids=(),
                temperature_k=298.15,
                pressure_atm=1.0,
                support_state="blocked_unsupported",
                blocked_reason=(
                    "the required frequency-bearing producer is not "
                    "executable under a zero engine-call grant"
                ),
            )
        )
        required.append("dg")
    return build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256=draft_sha256,
        calculation_nodes=(),
        calculation_observables={},
        analysis_nodes=tuple(nodes),
        required_output_ids=tuple(required),
    )


def _empty_draft():
    return build_command_workflow_draft(
        workflow_id="w", task_spec_id="a" * 64, nodes=()
    )


def _claims_record(*, source_receipt_sha256, quantity_id="e"):
    from chemsmart.agent.analysis_claims import (
        AnalysisReportedQuantityV1,
        build_analysis_claim_record,
    )

    return build_analysis_claim_record(
        task_spec_sha256="a" * 64,
        claims=(
            AnalysisReportedQuantityV1(
                claim_id="claim-1",
                source_kind="quantity_extraction",
                source_receipt_sha256=source_receipt_sha256,
                quantity_id=quantity_id,
                quantity_value_sha256="1" * 64,
                display_value=-76.4,
                display_unit="hartree",
                canonical_value=-76.4,
                canonical_unit="hartree",
                dimension=(2, 1, -2, 0, 0, 0),
                data_kind="scalar",
            ),
        ),
    )


def _decision_record(*, evidence_refs):
    from chemsmart.agent.execution import build_scientific_decision_record

    return build_scientific_decision_record(
        decision_id="decision-1",
        task_spec_sha256="a" * 64,
        stage_order=("analysis",),
        assumptions=(),
        method_rationale="recorded for the doubt-binding test",
        alternatives=(),
        uncertainties=("the extraction may not describe this species",),
        diagnostics=(),
        evidence_refs=tuple(evidence_refs),
    )


def _completion_via_gate(
    tmp_path, *, blocked_thermochemistry, doubt_ref="", claim_source=""
):
    draft = _empty_draft()
    plan = _analysis_only_plan(
        blocked_thermochemistry=blocked_thermochemistry,
        draft_sha256=draft.draft_sha256,
    )
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="s1"
        ),
        artifacts={},
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )
    host.scientific_toolchain_plans[plan.plan_sha256] = plan
    host.workflow_drafts[draft.draft_sha256] = draft
    host._scientific_toolchain_command_results[plan.plan_sha256] = {
        "workflow_draft": draft
    }
    matched = {"extract-e": ("b" * 64,), "claim-e": ("c" * 64,)}
    host._scientific_toolchain_analysis_receipts = (
        lambda _plan, task_spec_sha256: matched
    )
    if claim_source:
        record = _claims_record(source_receipt_sha256=claim_source)
        host.analysis_claim_records[record.receipt_sha256] = record
    if doubt_ref:
        decision = _decision_record(evidence_refs=("doubt:" + doubt_ref,))
        host.scientific_decisions[decision.record_sha256] = decision
    receipts = host._completion_receipts_for_latest_analysis_toolchain()
    (digest,) = receipts
    return host.analysis_completion_receipts[digest], host


def test_a_passed_completion_names_blocked_required_outputs(tmp_path):
    completion, host = _completion_via_gate(
        tmp_path, blocked_thermochemistry=True
    )
    assert completion.status == "passed"
    assert completion.findings == ()
    assert completion.limitation_output_ids == ("dg",)

    stream = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    (event,) = [
        row
        for row in map(json.loads, stream.splitlines())
        if row.get("kind") == "analysis_completion_evaluated"
    ]
    assert event["payload"]["limitation_output_ids"] == ["dg"]
    assert event["payload"]["record"]["limitation_output_ids"] == ["dg"]


def test_a_full_delivery_carries_no_limitations(tmp_path):
    completion, _host = _completion_via_gate(
        tmp_path, blocked_thermochemistry=False
    )
    assert completion.status == "passed"
    assert completion.limitation_output_ids == ()


def test_limitations_are_not_findings():
    from chemsmart.agent._contracts import canonical_sha256

    base = {
        "schema_version": "chemsmart.analysis-completion-receipt.v1",
        "policy_sha256": "d" * 64,
        "task_spec_sha256": "a" * 64,
        "source_receipt_sha256s": ("b" * 64,),
        "status": "passed",
        "findings": (),
    }
    limited_body = dict(base, limitation_output_ids=("dg",))
    passed = AnalysisCompletionReceiptV1(
        **limited_body, receipt_sha256=canonical_sha256(limited_body)
    )
    assert passed.limitation_output_ids == ("dg",)
    with pytest.raises(ContractError, match="sorted"):
        AnalysisCompletionReceiptV1(
            **dict(base, limitation_output_ids=("dg", "dg")),
            receipt_sha256=canonical_sha256(base),
        )
    # A durable record minted before the field existed verifies under
    # the same digest arithmetic and rehydrates with no limitations.
    legacy = AnalysisCompletionReceiptV1(
        **base, receipt_sha256=canonical_sha256(base)
    )
    assert legacy.limitation_output_ids == ()


def test_a_doubted_claim_downgrades_the_certification(tmp_path):
    """The r3 residue closed: the session doubted the receipt its own
    claim stands on, in typed form. The gate no longer certifies past
    it -- passed becomes partial, naming the doubted quantity."""

    completion, _host = _completion_via_gate(
        tmp_path,
        blocked_thermochemistry=False,
        claim_source="e" * 64,
        doubt_ref="e" * 64,
    )
    assert completion.status == "partial"
    assert completion.findings == (
        "analysis.claim_under_recorded_doubt.e",
    )


def test_a_doubt_about_an_unclaimed_receipt_keeps_the_pass(tmp_path):
    completion, _host = _completion_via_gate(
        tmp_path,
        blocked_thermochemistry=False,
        claim_source="e" * 64,
        doubt_ref="9" * 64,
    )
    assert completion.status == "passed"
    assert completion.findings == ()


def test_a_prose_only_doubt_keeps_the_prior_behavior(tmp_path):
    """An uncertainty kept in free text binds to nothing: the host
    cannot know which claim prose points at, and does not guess."""

    completion, _host = _completion_via_gate(
        tmp_path,
        blocked_thermochemistry=False,
        claim_source="e" * 64,
    )
    assert completion.status == "passed"
