"""A failed validation verdict is not a settlement.

Observed across the whole campaign: exactly three validation verdicts
ever failed, and none of them opened a recovery cycle. Two settled
`achieved` in one cycle with four engine calls unspent each -- a
transition-state search that had found a minimum, and an amide rotamer
that was not the strict minimum the task demanded. Both reports said
"failed" in their own verdict tables while the goal said achieved, and
no session was ever asked whether it wanted to answer the failure.

A failed verdict is the host stating that a delivered structure is not
what the task required. It never made a chain partial -- correctly, a
failed verdict is a scientific result and not a broken chain -- but it
also never reached the settlement, which is where it belongs. A
decision that cites the validation receipt has answered it and stands
by the delivery; one that does not has left it open.
"""

from __future__ import annotations

import json

from chemsmart.agent.goal_loop import _analysis_delivery


def _write(tmp_path, *events):
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    return path


def _validation(passed, receipt="a" * 64, node_id="validate-stationary"):
    return {
        "kind": "scientific_validation_evaluated",
        "payload": {
            "node_id": node_id,
            "receipt_sha256": receipt,
            "all_rules_passed": passed,
            "record": {
                "rule_results": [
                    {
                        "rule_id": "ts-exactly-one-imaginary",
                        "predicate": "count_equals",
                        "observed_value": 1 if passed else 0,
                        "expected_count": 1,
                        "passed": passed,
                    }
                ]
            },
        },
    }


def _claims(receipt="b" * 64):
    return {
        "kind": "analysis_claims_recorded",
        "payload": {
            "receipt_sha256": receipt,
            "record": {
                "claims": [
                    {
                        "source_receipt_sha256": "c" * 64,
                        "quantity_id": "central_barrier",
                    }
                ]
            },
        },
    }


def _completion(status="passed"):
    return {
        "kind": "analysis_completion_evaluated",
        "payload": {
            "status": status,
            "receipt_sha256": "d" * 64,
            "limitation_output_ids": [],
        },
    }


def _decision(evidence_refs=()):
    return {
        "kind": "scientific_decision_recorded",
        "payload": {
            "receipt_sha256": "e" * 64,
            "record": {"evidence_refs": list(evidence_refs)},
        },
    }


def test_a_failed_verdict_is_carried_into_the_delivery_facts(tmp_path):
    """The S12 shape: every output delivered, one verdict failed."""

    delivery = _analysis_delivery(
        _write(tmp_path, _validation(False), _claims(), _completion())
    )
    assert delivery.completion_status == "passed"
    assert delivery.claims == 1
    assert delivery.unanswered_verdicts == (
        "validate-stationary/ts-exactly-one-imaginary",
    )


def test_a_passing_verdict_leaves_nothing_unanswered(tmp_path):
    delivery = _analysis_delivery(
        _write(tmp_path, _validation(True), _claims(), _completion())
    )
    assert delivery.unanswered_verdicts == ()


def test_citing_the_validation_receipt_answers_it(tmp_path):
    """Standing by the delivery is an answer, made the typed way.

    The session is not forced to recover -- forcing success after a
    failure is how an agent learns to manufacture one. It is required
    only to say, in a record that cites the receipt, that it looked.
    """

    receipt = "a" * 64
    delivery = _analysis_delivery(
        _write(
            tmp_path,
            _validation(False, receipt=receipt),
            _claims(),
            _completion(),
            _decision(evidence_refs=[f"receipt:{receipt}"]),
        )
    )
    assert delivery.unanswered_verdicts == ()


def test_an_unrelated_citation_does_not_answer_it(tmp_path):
    delivery = _analysis_delivery(
        _write(
            tmp_path,
            _validation(False),
            _claims(),
            _completion(),
            _decision(evidence_refs=["receipt:" + "f" * 64]),
        )
    )
    assert delivery.unanswered_verdicts == (
        "validate-stationary/ts-exactly-one-imaginary",
    )


def test_the_wake_names_the_verdict_and_the_route():
    """A woken session must be told what failed and what is legal."""

    from chemsmart.agent.goal_loop import (
        _RECOVERY_ROUTE,
        _AnalysisDelivery,
        _deliverables_record,
    )

    record = _deliverables_record(
        _AnalysisDelivery(
            completion_status="passed",
            limitation_output_ids=(),
            claims=1,
            decisions=0,
            receipt_sha256s=(),
            unanswered_verdicts=("validate-stationary/ts-one-imaginary",),
        )
    )
    assert record["unanswered_failed_verdicts"] == (
        "validate-stationary/ts-one-imaginary",
    )
    # The route names actions that exist, and refuses to name a cause.
    assert "displace_along_vibrational_mode" in _RECOVERY_ROUTE
    assert "edit_molecular_geometry" in _RECOVERY_ROUTE
    assert "citing that validation receipt" in _RECOVERY_ROUTE
    assert "the physics does that" in _RECOVERY_ROUTE
