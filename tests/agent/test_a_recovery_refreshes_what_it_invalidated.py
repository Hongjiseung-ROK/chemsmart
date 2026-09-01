"""Recovering the structure does not recover the numbers.

Observed live, on the re-observation of the amide-rotamer case the
recovery cycle was built for. Cycle 1 delivered the rotamer energy gap
as a rendered claim and its strict-minimum verdict failed, because the
structure behind that number was a second-order saddle. The cycle
opened, and cycle 2 did the chemistry right: it stepped the structure
off both rotor modes, re-optimised, and both verdicts passed.

Then it delivered nothing. The corrected gap was evaluated inside an
expression receipt and never rendered as a claim, so the last
host-rendered value for the requested observable was still the one
computed from the rejected saddle, and the goal settled achieved
carrying it.

The wake record is what permitted this: it named the gap among
``delivered_quantity_ids`` in the same breath as it named the verdict
that invalidated it. True by the letter -- the claim was rendered --
and false in substance. A quantity whose receipt lineage traces to a
result a verdict rejected is stale, not delivered, and the session that
is asked to fix the structure is the one that has to be told which
numbers stopped standing.
"""

from __future__ import annotations

import json

from chemsmart.agent.goal_loop import _analysis_delivery, _deliverables_record

_EXTRACTION = "1" * 64
_EXPRESSION = "2" * 64
_VALIDATION = "3" * 64
_CLAIMS = "4" * 64
#: The optimisation the extraction read. A verdict rejects the result,
#: not the read of it, so this is what the rule keys on.
_ARTIFACT = "e" * 64


def _write(tmp_path, *events):
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    return path


def _extraction():
    """One optimisation read for its energy and its frequencies."""

    return {
        "kind": "result_quantities_extracted",
        "payload": {
            "receipt_sha256": _EXTRACTION,
            "quantity_ids": ["e-cis", "freqs-cis"],
            "artifact_sha256": _ARTIFACT,
            "record": {
                "artifact_id": "result.cis-opt.1",
                "artifact_sha256": _ARTIFACT,
            },
        },
    }


def _expression():
    """The gap, computed from that energy and the reference energy."""

    return {
        "kind": "quantity_expression_evaluated",
        "payload": {
            "receipt_sha256": _EXPRESSION,
            "output_ids": ["delta-e-kcal"],
            "record": {
                "expression_id": "expr-rel-energy",
                "output_dependencies": [
                    {
                        "output_id": "delta-e-kcal",
                        "source_receipt_sha256s": [_EXTRACTION, "9" * 64],
                    }
                ],
            },
        },
    }


def _validation(passed):
    return {
        "kind": "scientific_validation_evaluated",
        "payload": {
            "node_id": "val-cis-min",
            "receipt_sha256": _VALIDATION,
            "all_rules_passed": passed,
            "record": {
                "input_bindings": [
                    {
                        "input_id": "freqs-cis",
                        "quantity_id": "freqs-cis",
                        "source_receipt_sha256": _EXTRACTION,
                    }
                ],
                "rule_results": [
                    {
                        "rule_id": "cis-strict-min",
                        "predicate": "minimum_greater_equal",
                        "observed_value": 47.34 if passed else -114.35,
                        "input_ids": ["freqs-cis"],
                        "passed": passed,
                    }
                ],
            },
        },
    }


def _claims():
    return {
        "kind": "analysis_claims_recorded",
        "payload": {
            "receipt_sha256": _CLAIMS,
            "claim_ids": ["c-e-rel", "c-verdict-cis"],
            "record": {
                "claims": [
                    {
                        "claim_id": "c-e-rel",
                        "quantity_id": "delta-e-kcal",
                        "source_kind": "quantity_expression",
                        "source_receipt_sha256": _EXPRESSION,
                    },
                    {
                        "claim_id": "c-verdict-cis",
                        "quantity_id": "verdict-cis-strict",
                        "source_kind": "scientific_validation",
                        "source_receipt_sha256": _VALIDATION,
                    },
                ]
            },
        },
    }


def _completion():
    return {
        "kind": "analysis_completion_evaluated",
        "payload": {
            "status": "passed",
            "receipt_sha256": "5" * 64,
            "limitation_output_ids": [],
        },
    }


def test_a_number_from_a_rejected_structure_is_stale_not_delivered(tmp_path):
    delivery = _analysis_delivery(
        _write(
            tmp_path,
            _extraction(),
            _expression(),
            _validation(False),
            _claims(),
            _completion(),
        )
    )

    # The gap travelled extraction -> expression -> claim, and the rule
    # that failed read the same extraction receipt.
    assert delivery.stale_quantity_ids == ("delta-e-kcal",)
    assert "delta-e-kcal" not in delivery.delivered_quantity_ids

    # The verdict itself is not stale. It is the record of the failure,
    # and a failure record does not stop standing because the structure
    # it rejected was replaced.
    assert delivery.delivered_quantity_ids == ("verdict-cis-strict",)


def test_the_wake_record_names_the_numbers_that_stopped_standing(tmp_path):
    delivery = _analysis_delivery(
        _write(
            tmp_path,
            _extraction(),
            _expression(),
            _validation(False),
            _claims(),
            _completion(),
        )
    )
    record = _deliverables_record(delivery)

    assert record["stale_quantity_ids"] == ("delta-e-kcal",)
    assert record["unanswered_failed_verdicts"] == (
        "val-cis-min/cis-strict-min",
    )
    # The two must not contradict each other in the same record: this is
    # exactly the pairing a live session read as "the number is done,
    # only the verdict is open".
    assert "delta-e-kcal" not in record["delivered_quantity_ids"]


def test_a_passing_verdict_leaves_every_quantity_delivered(tmp_path):
    delivery = _analysis_delivery(
        _write(
            tmp_path,
            _extraction(),
            _expression(),
            _validation(True),
            _claims(),
            _completion(),
        )
    )

    assert delivery.stale_quantity_ids == ()
    assert delivery.delivered_quantity_ids == (
        "delta-e-kcal",
        "verdict-cis-strict",
    )
    assert delivery.unanswered_verdicts == ()


def test_staleness_does_not_reach_past_the_receipts_that_were_read(tmp_path):
    """A verdict rejects a result, not the whole run."""

    other = {
        "kind": "quantity_expression_evaluated",
        "payload": {
            "receipt_sha256": "6" * 64,
            "output_ids": ["trans-torsion"],
            "record": {
                "expression_id": "expr-trans-torsion",
                "output_dependencies": [
                    {
                        "output_id": "trans-torsion",
                        "source_receipt_sha256s": ["9" * 64],
                    }
                ],
            },
        },
    }
    claims = {
        "kind": "analysis_claims_recorded",
        "payload": {
            "receipt_sha256": _CLAIMS,
            "claim_ids": ["c-tau-trans"],
            "record": {
                "claims": [
                    {
                        "claim_id": "c-tau-trans",
                        "quantity_id": "trans-torsion",
                        "source_kind": "quantity_expression",
                        "source_receipt_sha256": "6" * 64,
                    }
                ]
            },
        },
    }
    delivery = _analysis_delivery(
        _write(
            tmp_path,
            _extraction(),
            other,
            _validation(False),
            claims,
            _completion(),
        )
    )

    assert delivery.stale_quantity_ids == ()
    assert delivery.delivered_quantity_ids == ("trans-torsion",)


def test_the_route_says_an_unclaimed_expression_is_not_delivered():
    """The live loss was a value computed and never rendered."""

    from chemsmart.agent.goal_loop import _RECOVERY_ROUTE

    assert "stale quantity" in _RECOVERY_ROUTE
    assert "render it as a claim" in _RECOVERY_ROUTE
    # It must name the action, never assert what the physics was.
    assert "Re-derive" in _RECOVERY_ROUTE


def test_a_sibling_output_of_the_same_expression_is_not_stale(tmp_path):
    """A verdict rejects a result, and results are not receipts.

    Observed in the S_N2 case: one expression computed the complexation
    energy and the central barrier together, and the rule that failed
    read an imaginary-mode count out of that same expression. Seeding
    the whole receipt would have called the complexation energy stale
    -- and it was right, agreeing with an independent reference to
    0.04 kcal/mol. Only the barrier stood on the structure the verdict
    rejected.
    """

    complex_extract = "a" * 64
    ts_extract = "b" * 64
    reagent_extract = "c" * 64
    shared = "d" * 64

    events = [
        {
            "kind": "result_quantities_extracted",
            "payload": {
                "receipt_sha256": complex_extract,
                "artifact_sha256": "1" * 63 + "a",
                "record": {"artifact_id": "result.complex-opt.1"},
            },
        },
        {
            "kind": "result_quantities_extracted",
            "payload": {
                "receipt_sha256": ts_extract,
                "artifact_sha256": "1" * 63 + "b",
                "record": {"artifact_id": "result.ts-opt.1"},
            },
        },
        {
            "kind": "result_quantities_extracted",
            "payload": {
                "receipt_sha256": reagent_extract,
                "artifact_sha256": "1" * 63 + "c",
                "record": {"artifact_id": "result.reagent-sp.1"},
            },
        },
        {
            "kind": "quantity_expression_evaluated",
            "payload": {
                "receipt_sha256": shared,
                "record": {
                    "expression_id": "expr-energetics",
                    "output_dependencies": [
                        {
                            "output_id": "complexation-kcal",
                            "source_receipt_sha256s": [
                                complex_extract,
                                reagent_extract,
                            ],
                        },
                        {
                            "output_id": "barrier-kcal",
                            "source_receipt_sha256s": [
                                complex_extract,
                                ts_extract,
                            ],
                        },
                        {
                            "output_id": "ts-imag-count",
                            "source_receipt_sha256s": [ts_extract],
                        },
                    ],
                },
            },
        },
        {
            "kind": "scientific_validation_evaluated",
            "payload": {
                "node_id": "validate-stationary-points",
                "receipt_sha256": _VALIDATION,
                "all_rules_passed": False,
                "record": {
                    "input_bindings": [
                        {
                            "input_id": "in_ts_count",
                            "quantity_id": "ts-imag-count",
                            "source_receipt_sha256": shared,
                        }
                    ],
                    "rule_results": [
                        {
                            "rule_id": "ts-exactly-one-imaginary",
                            "predicate": "count_equals",
                            "observed_value": 0,
                            "expected_count": 1,
                            "input_ids": ["in_ts_count"],
                            "passed": False,
                        }
                    ],
                },
            },
        },
        {
            "kind": "analysis_claims_recorded",
            "payload": {
                "receipt_sha256": _CLAIMS,
                "record": {
                    "claims": [
                        {
                            "claim_id": "c-barrier",
                            "quantity_id": "barrier-kcal",
                            "source_receipt_sha256": shared,
                        },
                        {
                            "claim_id": "c-complexation",
                            "quantity_id": "complexation-kcal",
                            "source_receipt_sha256": shared,
                        },
                    ]
                },
            },
        },
        _completion(),
    ]

    delivery = _analysis_delivery(_write(tmp_path, *events))

    assert delivery.stale_quantity_ids == ("barrier-kcal",)
    assert delivery.delivered_quantity_ids == ("complexation-kcal",)


def test_a_second_read_of_the_rejected_result_is_also_stale(tmp_path):
    """A verdict rejects a result, not the read of it.

    Observed live: one eclipsed-ethane saddle was read by two extraction
    calls -- frequencies in one, coordinates in the other. The failed
    strict-minimum rule touched only the first, so the zero-point energy
    was correctly withheld while the HCCH torsion of the same rejected
    structure -- the task's own requested observable -- was reported as
    delivered. Keying the seed on the receipt let every other read of one
    result escape.
    """

    other_receipt = "7" * 64
    events = [
        _extraction(),
        {
            "kind": "result_quantities_extracted",
            "payload": {
                "receipt_sha256": other_receipt,
                "quantity_ids": ["pos-cis"],
                # The same optimisation, read a second time.
                "artifact_sha256": _ARTIFACT,
                "record": {"artifact_id": "result.cis-opt.1"},
            },
        },
        {
            "kind": "quantity_expression_evaluated",
            "payload": {
                "receipt_sha256": "8" * 64,
                "record": {
                    "expression_id": "expr-torsion",
                    "output_dependencies": [
                        {
                            "output_id": "tau-cis",
                            "source_receipt_sha256s": [other_receipt],
                        }
                    ],
                },
            },
        },
        _validation(False),
        {
            "kind": "analysis_claims_recorded",
            "payload": {
                "receipt_sha256": _CLAIMS,
                "record": {
                    "claims": [
                        {
                            "claim_id": "c-tau",
                            "quantity_id": "tau-cis",
                            "source_receipt_sha256": "8" * 64,
                        }
                    ]
                },
            },
        },
        _completion(),
    ]

    delivery = _analysis_delivery(_write(tmp_path, *events))

    # The failed rule never read `other_receipt`; it read the frequencies.
    assert delivery.stale_quantity_ids == ("tau-cis",)
    assert delivery.delivered_quantity_ids == ()
    assert delivery.rejected_artifact_sha256s == (_ARTIFACT,)


def test_a_later_cycle_may_rename_the_number_it_replaces(tmp_path):
    """Staleness clears on a delivery, not on a repeated identifier.

    Observed live on the round's own flagship recovery: the session fixed
    the structure and re-derived the torsion under a new id
    (`cis-torsion` -> `amide-torsion`). A rule that waits for the old id
    to reappear holds a correct goal open forever over a number it has
    already replaced -- so what stands is whatever the most recent
    claim-rendering cycle said.
    """

    cycle_one = tmp_path / "cycle-1"
    cycle_one.mkdir()
    first = _analysis_delivery(
        _write(
            cycle_one,
            _extraction(),
            _expression(),
            _validation(False),
            _claims(),
            _completion(),
        )
    )
    assert first.stale_quantity_ids == ("delta-e-kcal",)
    assert first.claims_rendered is True

    # A later cycle on a different result, claiming under new names.
    clean_artifact = "f" * 64
    clean_receipt = "9" * 64
    cycle_two = tmp_path / "cycle-2"
    cycle_two.mkdir()
    second = _analysis_delivery(
        _write(
            cycle_two,
            {
                "kind": "result_quantities_extracted",
                "payload": {
                    "receipt_sha256": clean_receipt,
                    "artifact_sha256": clean_artifact,
                    "record": {"artifact_id": "result.cis-reopt.1"},
                },
            },
            {
                "kind": "analysis_claims_recorded",
                "payload": {
                    "receipt_sha256": "b" * 64,
                    "record": {
                        "claims": [
                            {
                                "claim_id": "c-gap",
                                "quantity_id": "amide-gap",
                                "source_receipt_sha256": clean_receipt,
                            }
                        ]
                    },
                },
            },
            _completion(),
        ),
        inherited_rejected_artifacts=first.rejected_artifact_sha256s,
    )

    # The rejection is carried forward, and still nothing here stands on
    # it, so the standing delivery is clean under a different name.
    assert second.claims_rendered is True
    assert second.stale_quantity_ids == ()
    assert second.delivered_quantity_ids == ("amide-gap",)
