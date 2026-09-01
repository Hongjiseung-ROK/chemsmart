"""An expression that is evaluated and never claimed is not delivered.

The host computes a quantity from real program output, and no reader of
the delivery ever sees it. Measured across the recorded campaign: of 242
exported quantities, 89 were never rendered as a claim, and five goals
exported quantities and claimed none at all -- four of those settled
`achieved` with engine calls still unspent.

The sharpest instance is a completed S_N2 profile. Its executor computed
a complexation energy of -9.4376 kcal/mol and a central barrier of
+8.7144 kcal/mol from a genuine saddle, both validation verdicts passed,
and the rendered report contains two verdict rows, a delivery table, and
no numbers. The completion receipt reads passed, zero findings, zero
limitations. The goal settled achieved with four of eight engine calls
unspent.

`analysis_status` becomes "completed" when every node executed and no
required output was starved; an exported quantity that no claim node
consumes never enters that computation. The recovery route already told
sessions that an unclaimed expression is not delivered. Nothing enforced
it.
"""

from __future__ import annotations

import json

from chemsmart.agent.goal_loop import _analysis_delivery, _deliverables_record

_EXTRACT = "1" * 64
_EXPR = "2" * 64
_CLAIMS = "3" * 64
_ARTIFACT = "e" * 64


def _write(tmp_path, *events):
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    return path


def _extraction():
    return {
        "kind": "result_quantities_extracted",
        "payload": {
            "receipt_sha256": _EXTRACT,
            "artifact_sha256": _ARTIFACT,
            "record": {"artifact_id": "result.ts.1"},
        },
    }


def _expression(*output_ids):
    """One expression exporting several quantities, as a real chain does."""

    return {
        "kind": "quantity_expression_evaluated",
        "payload": {
            "receipt_sha256": _EXPR,
            "output_ids": list(output_ids),
            "record": {
                "expression_id": "expr-energetics",
                "output_dependencies": [
                    {
                        "output_id": output_id,
                        "source_receipt_sha256s": [_EXTRACT],
                    }
                    for output_id in output_ids
                ],
            },
        },
    }


def _claims(*quantity_ids):
    return {
        "kind": "analysis_claims_recorded",
        "payload": {
            "receipt_sha256": _CLAIMS,
            "record": {
                "claims": [
                    {
                        "claim_id": f"c-{quantity_id}",
                        "quantity_id": quantity_id,
                        "source_receipt_sha256": _EXPR,
                    }
                    for quantity_id in quantity_ids
                ]
            },
        },
    }


def _completion():
    return {
        "kind": "analysis_completion_evaluated",
        "payload": {
            "status": "passed",
            "receipt_sha256": "4" * 64,
            "limitation_output_ids": [],
        },
    }


def test_a_chain_that_claims_nothing_leaves_every_number_undelivered(
    tmp_path,
):
    """The observed shape: correct physics, a report with no numbers."""

    delivery = _analysis_delivery(
        _write(
            tmp_path,
            _extraction(),
            _expression("cplx_kcal", "barr_kcal", "imag_count"),
            _completion(),
        )
    )

    assert delivery.unclaimed_output_ids == (
        "barr_kcal",
        "cplx_kcal",
        "imag_count",
    )
    assert delivery.claims_rendered is False
    # The completion gate is content: every node ran, nothing was starved.
    assert delivery.completion_status == "passed"
    assert delivery.limitation_output_ids == ()


def test_a_partially_claimed_chain_names_only_what_is_missing(tmp_path):
    delivery = _analysis_delivery(
        _write(
            tmp_path,
            _extraction(),
            _expression("cplx_kcal", "barr_kcal", "imag_count"),
            _claims("barr_kcal"),
            _completion(),
        )
    )

    assert delivery.unclaimed_output_ids == ("cplx_kcal", "imag_count")
    assert delivery.delivered_quantity_ids == ("barr_kcal",)


def test_a_fully_claimed_chain_leaves_nothing_outstanding(tmp_path):
    delivery = _analysis_delivery(
        _write(
            tmp_path,
            _extraction(),
            _expression("cplx_kcal", "barr_kcal"),
            _claims("cplx_kcal", "barr_kcal"),
            _completion(),
        )
    )

    assert delivery.unclaimed_output_ids == ()
    assert delivery.delivered_quantity_ids == ("barr_kcal", "cplx_kcal")


def test_the_wake_names_the_numbers_no_reader_can_see(tmp_path):
    record = _deliverables_record(
        _analysis_delivery(
            _write(
                tmp_path,
                _extraction(),
                _expression("cplx_kcal", "barr_kcal"),
                _claims("barr_kcal"),
                _completion(),
            )
        )
    )

    assert record["unclaimed_output_ids"] == ("cplx_kcal",)
    assert record["delivered_quantity_ids"] == ("barr_kcal",)


def test_the_route_already_said_this_before_anything_enforced_it():
    from chemsmart.agent.goal_loop import _RECOVERY_ROUTE

    assert "evaluated and never claimed is not delivered" in _RECOVERY_ROUTE
