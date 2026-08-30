"""A declared observable commits the delivery to its kind and unit.

The session restates what the task asks for -- identifier, reporting
unit, one sentence of meaning -- as a typed act before planning. The
host checks only what a host can honestly check: the unit parses at
declaration, and at completion every declared observable has a
delivered claim of matching dimension. Kind and unit, never value.
An undelivered declared observable joins the completion receipt's
limitations exactly like a plan output the chain could not fulfil,
so the existing settlement vocabulary carries the consequence.
"""

from __future__ import annotations

import pytest

from chemsmart.agent._contracts import ContractError, canonical_sha256
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

TASK_SPEC_SHA256 = canonical_sha256("declared-observable-task")


def _host(tmp_path):
    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events" / "runtime.jsonl",
            session_id="declared-observable-session",
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


def _delivered_energy_claim(host):
    """Drive the real analysis path to one recorded kcal/mol claim."""

    host.dispatch(
        turn_id="turn-plan",
        tool_name="plan_scientific_workflow",
        arguments={
            "plan_id": "declared-observable-plan",
            "workflow_id": "declared-observable-workflow",
            "task_spec_id": TASK_SPEC_SHA256,
            "required_output_ids": ["binding_energy"],
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
                            "output_id": "binding_energy",
                            "quantity_kind": "energy",
                            "unit": "kcal/mol",
                        }
                    ],
                    "expression_nodes": [
                        {
                            "node_id": "binding_energy",
                            "operation": "literal",
                            "literal_value": -9.0,
                            "literal_unit": "kcal/mol",
                        }
                    ],
                    "expression_output_node_ids": ["binding_energy"],
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
            "expression_id": "binding-energy-expression",
            "inputs": [],
            "nodes": [
                {
                    "node_id": "binding_energy",
                    "operation": "literal",
                    "literal_value": -9.0,
                    "literal_unit": "kcal/mol",
                }
            ],
            "output_node_ids": ["binding_energy"],
        },
    )["result"]
    host.dispatch(
        turn_id="turn-analysis",
        tool_name="record_analysis_claims",
        arguments={
            "task_spec_sha256": TASK_SPEC_SHA256,
            "claims": [
                {
                    "claim_id": "binding_energy",
                    "receipt_sha256": expression["receipt_sha256"],
                    "quantity_id": "binding_energy",
                    "display_unit": "kcal/mol",
                }
            ],
        },
    )
    return expression["receipt_sha256"]


def _completion_receipt(host, source_receipt_sha256):
    plan = next(iter(host.scientific_toolchain_plans.values()))
    (receipt_sha256,) = host._record_toolchain_completion(
        plan,
        task_spec_sha256=TASK_SPEC_SHA256,
        source_receipt_sha256s=(source_receipt_sha256,),
    )
    return host.analysis_completion_receipts[receipt_sha256]


def test_an_unknown_unit_is_refused_naming_the_vocabulary(tmp_path):
    host = _host(tmp_path)
    with pytest.raises(ContractError) as excinfo:
        _declare(
            host,
            [
                {
                    "observable_id": "separation",
                    "unit": "furlongs",
                    "meaning": "the O...H separation at the minimum",
                }
            ],
        )
    message = str(excinfo.value)
    assert "typed unit vocabulary" in message
    assert "kcal/mol" in message


def test_a_declaration_is_durable_and_cannot_rebind(tmp_path):
    host = _host(tmp_path)
    first = _declare(
        host,
        [
            {
                "observable_id": "binding_energy",
                "unit": "kcal/mol",
                "meaning": "counterpoise-uncorrected dimer binding energy",
            }
        ],
    )
    assert first["declared_total"] == 1
    events = [
        event
        for event in host.event_store.read_events()
        if event.kind == EventKind.REQUESTED_OBSERVABLE_DECLARED.value
    ]
    assert len(events) == 1
    assert (
        events[0].payload["observables"][0]["observable_id"]
        == "binding_energy"
    )
    with pytest.raises(ContractError) as excinfo:
        _declare(
            host,
            [
                {
                    "observable_id": "binding_energy",
                    "unit": "angstrom",
                    "meaning": "now suddenly a distance",
                }
            ],
        )
    assert "already bound" in str(excinfo.value)
    # Adding a new observable later stays legal; the commitment is
    # per-identifier, not one-shot.
    second = _declare(
        host,
        [
            {
                "observable_id": "separation",
                "unit": "angstrom",
                "meaning": "the O...H separation at the minimum",
            }
        ],
    )
    assert second["declared_total"] == 2


def test_an_undelivered_declaration_is_a_named_limitation(tmp_path):
    host = _host(tmp_path)
    _declare(
        host,
        [
            {
                "observable_id": "binding_energy",
                "unit": "kJ/mol",
                "meaning": "dimer binding energy",
            },
            {
                "observable_id": "separation",
                "unit": "angstrom",
                "meaning": "the O...H separation at the minimum",
            },
        ],
    )
    source = _delivered_energy_claim(host)
    receipt = _completion_receipt(host, source)
    # The kJ/mol declaration is satisfied by the kcal/mol claim --
    # kind and unit means dimension, not a string match -- while the
    # length declaration went undelivered and is named.
    assert receipt.limitation_output_ids == ("declared_observable:separation",)
    # The receipt stays green: a delivery with a stated limitation is
    # not a broken chain, and findings mean the chain broke.
    assert receipt.status == "passed"
    assert receipt.findings == ()
    events = [
        event
        for event in host.event_store.read_events()
        if event.kind == EventKind.ANALYSIS_COMPLETION_EVALUATED.value
    ]
    assert list(events[-1].payload["limitation_output_ids"]) == [
        "declared_observable:separation"
    ]
    misses = events[-1].payload["declared_observable_misses"]
    assert len(misses) == 1
    assert "separation" in misses[0] and "matching dimension" in misses[0]
    assert not any("binding_energy" in miss for miss in misses)


def test_without_a_declaration_the_gate_is_unchanged(tmp_path):
    host = _host(tmp_path)
    source = _delivered_energy_claim(host)
    receipt = _completion_receipt(host, source)
    assert receipt.limitation_output_ids == ()
    assert receipt.findings == ()
