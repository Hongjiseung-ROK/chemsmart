"""A toolchain refusal carries its cause and the next legal route.

One sentence in a refusal message ended the scan-workaround class
live; this systematizes that finding. Refusals from the plan-time
gates whose loss classes are on record carry a typed cause from a
closed vocabulary and a next-legal-route directive, and both ride the
tool rejection as structured fields -- steering as a field the
session can act on, with the cause countable by class in the durable
event. A route without a cause is refused, and an unlisted cause is
refused: the vocabulary grows only when a new loss class has taught
us its shape.
"""

from __future__ import annotations

import json

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.loop import ToolLoopRunner
from chemsmart.agent.runtime.alibaba import (
    Qwen38MaxConfigV1,
    Qwen38MaxToolSession,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.scientific_toolchain import (
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    AnalysisSelectorIntentV1,
    RegisteredResultInputIntentV1,
    ScientificToolchainContractError,
    build_scientific_toolchain_plan,
)
from tests.agent.test_provider_protocol_failure_evidence import (
    _DispatchSpyHost,
    _run_contracts,
)

_TOOL_TURN = {
    "id": "refusal-turn",
    "model": "qwen3.8-max",
    "choices": [
        {
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": "",
                "reasoning_content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "plan_scientific_workflow",
                            "arguments": "{}",
                        },
                    }
                ],
            },
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
}

_FINAL = {
    "id": "final-turn",
    "model": "qwen3.8-max",
    "choices": [
        {
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": "Stopping after the refusal.",
                "reasoning_content": "",
            },
        }
    ],
    "usage": {"prompt_tokens": 12, "completion_tokens": 6},
}


def test_the_c5_shaped_refusal_carries_cause_and_route():
    """The dimensional gate that C5 earned now steers structurally."""

    node = AnalysisNodeIntentV1(
        node_id="ext-scan",
        analysis_kind="result_extraction",
        dependencies=(),
        inputs=(
            RegisteredResultInputIntentV1(
                input_id="raw", artifact_id="registered-scan"
            ),
        ),
        selectors=(
            AnalysisSelectorIntentV1(
                quantity_id="coords", selector="scan_coordinate_values"
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="coords",
                quantity_kind="scan_coordinate",
                unit="angstrom",
            ),
        ),
        expression_nodes=(),
        expression_output_node_ids=(),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )
    with pytest.raises(ScientificToolchainContractError) as excinfo:
        build_scientific_toolchain_plan(
            plan_id="p",
            workflow_id="w",
            command_workflow_draft_sha256="9" * 64,
            calculation_nodes=(),
            calculation_observables={},
            analysis_nodes=(node,),
            required_output_ids=("coords",),
        )
    assert excinfo.value.cause == "extraction_unit_dimension"
    assert "distance/angle/dihedral" in excinfo.value.next_legal_route


def test_the_read_order_refusal_carries_cause_and_route():
    with pytest.raises(ScientificToolchainContractError) as excinfo:
        AnalysisNodeIntentV1(
            node_id="expr",
            analysis_kind="quantity_expression",
            dependencies=(),
            inputs=(),
            selectors=(),
            outputs=(
                AnalysisOutputIntentV1(
                    output_id="value", quantity_kind="energy", unit="hartree"
                ),
            ),
            expression_nodes=(
                {
                    "node_id": "value",
                    "operation": "abs",
                    "input_ids": ["missing_name"],
                },
            ),
            expression_output_node_ids=("value",),
            temperature_k=None,
            pressure_atm=None,
            support_state="planned",
            blocked_reason="",
        )
    assert excinfo.value.cause == "expression_read_order"
    assert "reorder" in excinfo.value.next_legal_route


def test_a_route_without_a_cause_is_refused():
    with pytest.raises(ContractError, match="names its cause"):
        ScientificToolchainContractError(
            "message", next_legal_route="do it differently"
        )
    with pytest.raises(ContractError, match="unknown toolchain refusal"):
        ScientificToolchainContractError(
            "message", cause="vibes", next_legal_route="anything"
        )
    bare = ScientificToolchainContractError("plain message")
    assert bare.cause == ""
    assert bare.next_legal_route == ""


class _RefusingHost(_DispatchSpyHost):
    def dispatch(self, *, tool_name: str, arguments: dict, **_kwargs):
        raise ScientificToolchainContractError(
            "extraction output declares angstrom over a dimensionless "
            "selector",
            cause="extraction_unit_dimension",
            next_legal_route=(
                "declare the output in the selector's own dimension, or "
                "measure the coordinate from the delivered geometry with "
                "the distance/angle/dihedral operations"
            ),
        )


def test_the_rejection_on_the_wire_carries_the_fields(tmp_path):
    responses = iter((_TOOL_TURN, _FINAL))
    session = Qwen38MaxToolSession(
        transport=lambda _payload: next(responses),
        messages=[{"role": "user", "content": "Plan the workflow."}],
        config=Qwen38MaxConfigV1(),
    )
    store = RuntimeEventStore(
        tmp_path / "events" / "runtime.jsonl", session_id="protocol-session"
    )
    host = _RefusingHost()
    envelope, request_context, network = _run_contracts(
        host, Qwen38MaxConfigV1()
    )
    ToolLoopRunner(host=host, event_store=store).run(
        session=session,
        envelope=envelope,
        request_context=request_context,
        provider_budget=network,
    )
    tool_messages = [
        message
        for message in session.public_history()
        if message.get("role") == "tool"
    ]
    assert len(tool_messages) == 1
    rejection = json.loads(tool_messages[0]["content"])
    assert rejection["status"] == "rejected"
    assert rejection["cause"] == "extraction_unit_dimension"
    assert "distance/angle/dihedral" in rejection["next_legal_route"]
    failed = [
        event
        for event in store.read_events()
        if event.kind == EventKind.TOOL_FAILED.value
    ]
    assert len(failed) == 1
    assert failed[0].payload["cause"] == "extraction_unit_dimension"
