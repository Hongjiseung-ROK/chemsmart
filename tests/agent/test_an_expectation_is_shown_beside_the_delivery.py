"""A recorded expectation is restated beside the number that answers it.

Observed live: a session declared the isomerization energy it would
deliver, wrote down that it expected the sign to be negative on a
steric argument, and the physics returned the opposite sign.  The
delivered value was correct, the reasoning was not, and nothing in
the record joined them -- the falsified premise and the right answer
sat in one delivery, unreconciled.  The host now restates the
expectation beside the delivered claim of that dimension and marks
agreement by arithmetic on the sign.

What this deliberately does not do is grade.  A diverging row moves
no status, adds no finding, and adds no limitation: a wrong
expectation is a scientific result, often the interesting one, while
a finding means the chain itself broke.  A verdict is a criterion the
delivery had to meet; an expectation is what a scientist thought
beforehand, and only the first can fail.
"""

from __future__ import annotations

import pytest

from chemsmart.agent._contracts import ContractError, canonical_sha256
from chemsmart.agent.report_format import PREDICTIONS_HEADING
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

TASK_SPEC_SHA256 = canonical_sha256("expectation-task")

# The live shape this test is pinned to: the session predicted the
# trans isomer lower (negative), and B3LYP/def2-TZVP delivered
# +0.669 kcal/mol -- cis lower, the cis effect.
DELIVERED_KCAL = 0.6690137744152495


def _host(tmp_path):
    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events" / "runtime.jsonl",
            session_id="expectation-session",
        ),
        task_spec_sha256s=(TASK_SPEC_SHA256,),
        approved_workspace=tmp_path / "workspace",
    )


def _declare(host, observables):
    return host.dispatch(
        turn_id="turn-declare",
        tool_name="declare_requested_observable",
        arguments={"observables": observables},
    )["result"]


def _deliver(host, value, unit="kcal/mol", claim_id="isomerization_energy"):
    host.dispatch(
        turn_id="turn-plan",
        tool_name="plan_scientific_workflow",
        arguments={
            "plan_id": "expectation-plan",
            "workflow_id": "expectation-workflow",
            "task_spec_id": TASK_SPEC_SHA256,
            "required_output_ids": [claim_id],
            "calculation_nodes": [],
            "analysis_nodes": [
                {
                    "node_id": "derive-energy",
                    "analysis_kind": "quantity_expression",
                    "dependencies": [],
                    "inputs": [],
                    "selectors": [],
                    "outputs": [
                        {
                            "output_id": claim_id,
                            "quantity_kind": "energy",
                            "unit": unit,
                        }
                    ],
                    "expression_nodes": [
                        {
                            "node_id": claim_id,
                            "operation": "literal",
                            "literal_value": value,
                            "literal_unit": unit,
                        }
                    ],
                    "expression_output_node_ids": [claim_id],
                    "support_state": "planned",
                    "blocked_reason": "",
                    "validation_rules": [],
                }
            ],
        },
    )
    expression = host.dispatch(
        turn_id="turn-analysis",
        tool_name="evaluate_quantity_expression",
        arguments={
            "expression_id": "expectation-expression",
            "inputs": [],
            "nodes": [
                {
                    "node_id": claim_id,
                    "operation": "literal",
                    "literal_value": value,
                    "literal_unit": unit,
                }
            ],
            "output_node_ids": [claim_id],
        },
    )["result"]
    host.dispatch(
        turn_id="turn-analysis",
        tool_name="record_analysis_claims",
        arguments={
            "task_spec_sha256": TASK_SPEC_SHA256,
            "claims": [
                {
                    "claim_id": claim_id,
                    "receipt_sha256": expression["receipt_sha256"],
                    "quantity_id": claim_id,
                    "display_unit": unit,
                }
            ],
        },
    )
    return expression["receipt_sha256"]


def _complete(host, source_receipt_sha256):
    plan = next(iter(host.scientific_toolchain_plans.values()))
    (receipt_sha256,) = host._record_toolchain_completion(
        plan,
        task_spec_sha256=TASK_SPEC_SHA256,
        source_receipt_sha256s=(source_receipt_sha256,),
    )
    return host.analysis_completion_receipts[receipt_sha256]


def _last_completion_payload(host):
    events = [
        event
        for event in host.event_store.read_events()
        if event.kind == EventKind.ANALYSIS_COMPLETION_EVALUATED.value
    ]
    return events[-1].payload


def test_a_falsified_expectation_is_shown_and_settles_nothing(tmp_path):
    """The live case: predicted negative, delivered positive."""

    host = _host(tmp_path)
    _declare(
        host,
        [
            {
                "observable_id": "isomerization_energy",
                "unit": "kcal/mol",
                "meaning": "E(trans) - E(cis) of 1,2-difluoroethylene",
                "expected_sign": "negative",
                "expectation_basis": (
                    "the trans isomer holds the fluorines apart, so sterics "
                    "put it lower"
                ),
            }
        ],
    )
    source = _deliver(host, DELIVERED_KCAL)
    receipt = _complete(host, source)

    payload = _last_completion_payload(host)
    (row,) = payload["declared_observable_predictions"]
    assert row["observable_id"] == "isomerization_energy"
    assert row["expected_sign"] == "negative"
    assert row["agreement"] == "diverged"
    assert row["delivered_claim_id"] == "isomerization_energy"
    assert "sterics" in row["expectation_basis"]

    # Divergence moves nothing: no finding, no limitation, still green.
    assert receipt.status == "passed"
    assert receipt.findings == ()
    assert receipt.limitation_output_ids == ()
    assert list(payload["declared_observable_misses"]) == []


def test_an_agreeing_expectation_reads_as_agreed(tmp_path):
    host = _host(tmp_path)
    _declare(
        host,
        [
            {
                "observable_id": "isomerization_energy",
                "unit": "kcal/mol",
                "meaning": "E(trans) - E(cis) of 1,2-difluoroethylene",
                "expected_sign": "positive",
                "expectation_basis": (
                    "the cis effect places the cis isomer lower in "
                    "1,2-dihaloethylenes"
                ),
            }
        ],
    )
    source = _deliver(host, DELIVERED_KCAL)
    _complete(host, source)
    (row,) = _last_completion_payload(host)["declared_observable_predictions"]
    assert row["agreement"] == "agreed"
    assert row["delivered_value"] == pytest.approx(DELIVERED_KCAL)


def test_the_declared_identifier_resolves_a_shared_dimension(tmp_path):
    """Three potentials in volts are three questions, not one.

    Pinned to the first live use: a session declared a sign for each of
    three volt-valued observables and named its claims after them. Every
    row came back "not comparable" on dimension matching alone, with the
    matching identifiers sitting right there.
    """

    host = _host(tmp_path)
    _declare(
        host,
        [
            {
                "observable_id": "e_benzoquinone_vs_she",
                "unit": "V",
                "meaning": "one-electron reduction potential vs SHE",
                "expected_sign": "positive",
                "expectation_basis": (
                    "measured aqueous potentials place the quinone couple "
                    "near or above 0 V vs SHE"
                ),
            }
        ],
    )
    source = _deliver(
        host, -0.351771717213137, unit="V", claim_id="e_benzoquinone_vs_she"
    )
    _deliver(host, -1.1101, unit="V", claim_id="e_nitrobenzene_vs_she")
    _complete(host, source)
    (row,) = _last_completion_payload(host)["declared_observable_predictions"]
    # Two volt claims exist; the identifier says which one was predicted.
    assert row["delivered_claim_id"] == "e_benzoquinone_vs_she"
    assert row["agreement"] == "diverged"


def test_an_ambiguous_dimension_is_not_guessed(tmp_path):
    """No matching identifier, two claims of the dimension: no guess."""

    host = _host(tmp_path)
    _declare(
        host,
        [
            {
                "observable_id": "isomerization_energy",
                "unit": "kcal/mol",
                "meaning": "E(trans) - E(cis)",
                "expected_sign": "negative",
                "expectation_basis": "sterics",
            }
        ],
    )
    source = _deliver(host, DELIVERED_KCAL, claim_id="delivered_gap")
    expression = host.dispatch(
        turn_id="turn-analysis",
        tool_name="evaluate_quantity_expression",
        arguments={
            "expression_id": "second-energy",
            "inputs": [],
            "nodes": [
                {
                    "node_id": "other_energy",
                    "operation": "literal",
                    "literal_value": -3.0,
                    "literal_unit": "kcal/mol",
                }
            ],
            "output_node_ids": ["other_energy"],
        },
    )["result"]
    host.dispatch(
        turn_id="turn-analysis",
        tool_name="record_analysis_claims",
        arguments={
            "task_spec_sha256": TASK_SPEC_SHA256,
            "claims": [
                {
                    "claim_id": "other_energy",
                    "receipt_sha256": expression["receipt_sha256"],
                    "quantity_id": "other_energy",
                    "display_unit": "kcal/mol",
                }
            ],
        },
    )
    _complete(host, source)
    (row,) = _last_completion_payload(host)["declared_observable_predictions"]
    assert row["agreement"] == "not_comparable"
    assert "delivered_gap" in row["delivered_claim_id"]
    assert "other_energy" in row["delivered_claim_id"]


def test_a_sign_without_a_reason_is_refused(tmp_path):
    host = _host(tmp_path)
    with pytest.raises(ContractError) as excinfo:
        _declare(
            host,
            [
                {
                    "observable_id": "isomerization_energy",
                    "unit": "kcal/mol",
                    "meaning": "E(trans) - E(cis)",
                    "expected_sign": "negative",
                }
            ],
        )
    assert "coin flip" in str(excinfo.value)
    with pytest.raises(ContractError) as excinfo:
        _declare(
            host,
            [
                {
                    "observable_id": "isomerization_energy",
                    "unit": "kcal/mol",
                    "meaning": "E(trans) - E(cis)",
                    "expected_sign": "downward",
                    "expectation_basis": "a hunch",
                }
            ],
        )
    assert "positive" in str(excinfo.value)


def test_without_an_expectation_nothing_is_rendered(tmp_path):
    host = _host(tmp_path)
    _declare(
        host,
        [
            {
                "observable_id": "isomerization_energy",
                "unit": "kcal/mol",
                "meaning": "E(trans) - E(cis)",
            }
        ],
    )
    source = _deliver(host, DELIVERED_KCAL)
    _complete(host, source)
    assert (
        list(_last_completion_payload(host)["declared_observable_predictions"])
        == []
    )
    assert (
        host._declared_observable_predictions(
            task_spec_sha256=TASK_SPEC_SHA256
        )
        == ()
    )


def test_the_report_shows_the_expectation_beside_the_delivery(tmp_path):
    host = _host(tmp_path)
    _declare(
        host,
        [
            {
                "observable_id": "isomerization_energy",
                "unit": "kcal/mol",
                "meaning": "E(trans) - E(cis) of 1,2-difluoroethylene",
                "expected_sign": "negative",
                "expectation_basis": "sterics put the trans isomer lower",
            }
        ],
    )
    source = _deliver(host, DELIVERED_KCAL)
    completion = _complete(host, source)
    plan = next(iter(host.scientific_toolchain_plans.values()))
    report = host._render_toolchain_analysis_report(
        completion=completion,
        toolchain=plan,
        claim_records=tuple(host.analysis_claim_records.values()),
        decision=None,
    )
    assert PREDICTIONS_HEADING in report
    assert "diverged" in report
    assert "sterics put the trans isomer lower" in report
    assert "displayed, never scored" in report
