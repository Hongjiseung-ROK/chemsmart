"""A claim descending from a failed acceptance criterion says so.

REACH-1 po3 (2026-09-06) planned exactly the right criteria -- exactly
one imaginary mode per transition state, the scan ridge at or above the
barrier it brackets -- and their verdicts reached nothing: the claim
would have been delivered whatever they said. The join needs no new
model surface, because the approved plan already declares which
producers a claim reads and which a criterion judges.

Nothing is refused and no number is dropped: the completion turns
partial and names the claim, exactly as it does for a claim under a
recorded doubt.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1


def _input(producer, output_id="out"):
    return SimpleNamespace(
        input_id=f"in-{producer}",
        producer_node_id=producer,
        producer_output_id=output_id,
        artifact_id="",
    )


def _node(node_id, kind, inputs, outputs=()):
    return SimpleNamespace(
        node_id=node_id,
        analysis_kind=kind,
        inputs=tuple(inputs),
        outputs=tuple(SimpleNamespace(output_id=item) for item in outputs),
    )


def _plan():
    return SimpleNamespace(
        analysis_nodes=(
            _node("extr-c4", "result_extraction", [_input("ts-c4")], ["e-c4"]),
            _node("extr-c5", "result_extraction", [_input("ts-c5")], ["e-c5"]),
            _node(
                "expr-ddg",
                "quantity_expression",
                [_input("extr-c4", "e-c4"), _input("extr-c5", "e-c5")],
                ["ddg"],
            ),
            _node(
                "vld-c4",
                "scientific_validation",
                [_input("extr-c4", "e-c4")],
                ["c4-verdict"],
            ),
            _node(
                "claim-ddg",
                "claim_rendering",
                [_input("expr-ddg", "ddg")],
                ["ddg-activation"],
            ),
        )
    )


def _receipt(node_id, *, passed):
    """A real validation receipt, rehydrated the way a restored host reads
    one from its stream: the join reads the receipt's own record."""

    from chemsmart.agent._contracts import canonical_data, canonical_sha256
    from chemsmart.agent.scientific_validation import (
        scientific_validation_receipt_from_record,
    )
    from chemsmart.analysis.result_quantities import (
        DIMENSIONLESS,
        make_quantity_value,
    )

    source = canonical_sha256({"extraction": node_id})
    record = {
        "schema_version": "chemsmart.scientific-validation-receipt.v1",
        "workflow_id": "wf",
        "plan_sha256": canonical_sha256("plan"),
        "node_id": node_id,
        "input_bindings": [
            {
                "input_id": "in",
                "source_receipt_sha256": source,
                "quantity_id": "imag-count",
                "quantity_value_sha256": canonical_sha256({"value": 1}),
            }
        ],
        "source_receipt_sha256s": [source],
        "rule_results": [
            {
                "rule_id": "one-imaginary-mode",
                "predicate": "count_equals",
                "input_ids": ["in"],
                "passed": passed,
                "observed_value": 1 if passed else 2,
                "threshold": None,
                "expected_count": 1,
                "unit": "1",
            }
        ],
        "outputs": [
            canonical_data(
                make_quantity_value(
                    quantity_id="verdict",
                    source_value=int(passed),
                    source_unit="1",
                    value=int(passed),
                    unit="1",
                    dimension=DIMENSIONLESS,
                    evidence_ref="scientific-validation:test",
                    data_kind="integer",
                )
            )
        ],
        "all_rules_passed": passed,
        "status": "evaluated",
    }
    return scientific_validation_receipt_from_record(
        record, receipt_sha256=canonical_sha256(record)
    )


def _host(receipts):
    host = object.__new__(CommandCompiledToolHostV1)
    host.scientific_validation_receipts = {
        receipt.receipt_sha256: receipt for receipt in receipts.values()
    }
    # No decision stands beside these receipts: every failed verdict is
    # unanswered, which is the state this join names claims under.
    host.scientific_decisions = {}
    host.quantity_extractions = {}
    host.quantity_expression_receipts = {}
    return host


@pytest.mark.capability("rule:plan.claim_carries_declared_id")
def test_a_passing_criterion_names_nothing():
    host = _host({"r1": _receipt("vld-c4", passed=True)})
    assert (
        host._claims_on_a_failed_criterion(_plan(), task_spec_sha256="a" * 64)
        == ()
    )


@pytest.mark.capability("rule:plan.claim_carries_declared_id")
def test_a_failed_criterion_names_the_claim_that_descends_from_it():
    host = _host({"r1": _receipt("vld-c4", passed=False)})
    assert host._claims_on_a_failed_criterion(
        _plan(), task_spec_sha256="a" * 64
    ) == ("ddg-activation",)


@pytest.mark.capability("rule:plan.claim_carries_declared_id")
def test_a_criterion_on_another_chain_leaves_the_claim_alone():
    plan = SimpleNamespace(
        analysis_nodes=(
            _node("extr-a", "result_extraction", [_input("opt-a")], ["e-a"]),
            _node("extr-b", "result_extraction", [_input("opt-b")], ["e-b"]),
            _node(
                "vld-b",
                "scientific_validation",
                [_input("extr-b", "e-b")],
                ["b-verdict"],
            ),
            _node(
                "claim-a", "claim_rendering", [_input("extr-a", "e-a")], ["a"]
            ),
        )
    )
    host = _host({"r1": _receipt("vld-b", passed=False)})
    assert (
        host._claims_on_a_failed_criterion(plan, task_spec_sha256="b" * 64)
        == ()
    )
