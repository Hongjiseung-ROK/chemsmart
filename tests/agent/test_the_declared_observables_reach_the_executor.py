"""A declaration the executor never sees is a commitment nobody checks.

``declare_requested_observables`` tells the session, in its own return
value, that "the completion gate requires a delivered claim of matching
dimension for every declared observable". Two host methods implement
exactly that -- ``_declared_observable_completion``, which states an
unmatched declaration as a limitation on a green receipt, and
``_declared_observable_predictions``, which restates a recorded
expectation beside the number that answered it.

Both read ``requested_observable_declarations`` off the tool host. The
declarations are recorded on the *planning session's* host; both methods
run on the *provider-free executor's* host -- a different host object,
built fresh from the approval bundle rather than inherited from the
planning session, so it starts with an empty declaration set. The field was in-memory only, so both
took their empty branch on every execution ever performed here: across
61 recorded campaign runs ``declared_observable_misses`` was ``[]`` and
``declared_observable_predictions`` was ``0``, every time, including a
goal that settled achieved having declared three observables and
rendered no claim for any of them.

The review and the bundle now carry the declarations, additively: a
packet that declared none keeps its historical bytes.
"""

from __future__ import annotations

import inspect

from chemsmart.agent.execution import (
    approve_workflow_execution_review,
    build_workflow_execution_review,
    workflow_execution_approval_bundle_json,
    workflow_execution_review_json,
)
from chemsmart.agent.live_session import (
    load_workflow_execution_approval_bundle,
    load_workflow_execution_review,
)
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from tests.agent.test_exact_execution_approval_chain import _review

_BARRIER = {
    "observable_id": "central_barrier",
    "unit": "kcal/mol",
    "dimension": (1, 0, 0, 0, 0, 0),
    "meaning": "Electronic barrier from the ion-molecule complex.",
    "expectation_basis": "Identity S_N2 central barriers at hybrid DFT.",
    "expected_sign": "positive",
    "expected_low": 5.0,
    "expected_high": 15.0,
}


def _review_with_declarations(base, declarations):
    return build_workflow_execution_review(
        request=base.request,
        scientific_plan=base.scientific_plan,
        materialized_workflow=base.materialized_workflow,
        execution_resources=base.execution_resources,
        execution_envelope=base.execution_envelope,
        environment_bindings=base.environment_bindings,
        node_reviews=base.node_reviews,
        stationary_point_policy=base.stationary_point_policy,
        non_executable_node_ids=base.non_executable_node_ids,
        requested_observable_declarations=declarations,
    )


def test_the_declarations_are_displayed_and_reach_the_bundle(tmp_path):
    base = _review(tmp_path)
    review = _review_with_declarations(base, (_BARRIER,))

    # Displayed bytes: what the session promised to deliver is in the
    # packet the human reads, before the grant rather than after it.
    packet = workflow_execution_review_json(review)
    assert "central_barrier" in packet
    path = tmp_path / "review.json"
    path.write_text(packet, encoding="utf-8")
    assert load_workflow_execution_review(path) == review

    # A different declared observable is a different reviewed digest.
    other = _review_with_declarations(
        base, ({**_BARRIER, "observable_id": "complexation_energy"},)
    )
    assert other.review_sha256 != review.review_sha256

    bundle = approve_workflow_execution_review(
        review,
        approval_id="approval-decl",
        approved_review_sha256=review.review_sha256,
        actor="human",
        resolution_id="resolution-decl",
    )
    assert len(bundle.requested_observable_declarations) == 1
    assert (
        bundle.requested_observable_declarations[0]["observable_id"]
        == "central_barrier"
    )
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(
        workflow_execution_approval_bundle_json(bundle), encoding="utf-8"
    )
    assert load_workflow_execution_approval_bundle(bundle_path) == bundle


def test_a_packet_declaring_nothing_keeps_its_historical_bytes(tmp_path):
    base = _review(tmp_path)
    unchanged = _review_with_declarations(base, ())

    assert unchanged.requested_observable_declarations == ()
    assert unchanged.review_sha256 == base.review_sha256
    bundle = approve_workflow_execution_review(
        unchanged,
        approval_id="approval-none",
        approved_review_sha256=unchanged.review_sha256,
        actor="human",
        resolution_id="resolution-none",
    )
    assert bundle.requested_observable_declarations == ()
    # Digest stability is the compatibility guarantee, not field absence
    # from the serialized form: an empty additive field is dropped from
    # the canonical body and still round-trips, exactly as
    # ``non_executable_node_ids`` has since it was added.
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(
        workflow_execution_approval_bundle_json(bundle), encoding="utf-8"
    )
    assert load_workflow_execution_approval_bundle(bundle_path) == bundle


def test_the_executor_key_is_the_name_the_host_accepts():
    """The two halves of the wire, checked against each other.

    A rename on one side is the whole defect this repairs, and it fails
    silently: the host keeps its empty default and the gate keeps
    passing.
    """

    from chemsmart.agent import executor

    parameters = inspect.signature(
        CommandCompiledToolHostV1.__init__
    ).parameters
    assert "approved_requested_observable_declarations" in parameters
    source = inspect.getsource(executor._execution_inputs_from_bundle)
    assert '"approved_requested_observable_declarations"' in source


def test_a_seeded_host_states_an_undelivered_declaration(tmp_path):
    """The gate is alive once the executor's host carries declarations."""

    from chemsmart.agent.runtime.event_store import RuntimeEventStore

    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="gate"
        ),
        approved_requested_observable_declarations=(_BARRIER,),
    )
    assert set(host.requested_observable_declarations) == {"central_barrier"}

    misses, limitations = host._declared_observable_completion(
        task_spec_sha256="a" * 64
    )
    assert misses and "central_barrier" in misses[0]
    assert limitations == ("declared_observable:central_barrier",)

    # And the expectation the session recorded now has somewhere to land,
    # which is the row seven readings reported as never rendering.
    rows = host._declared_observable_predictions(task_spec_sha256="a" * 64)
    assert len(rows) == 1
    assert rows[0]["observable_id"] == "central_barrier"
    assert rows[0]["expected_sign"] == "positive"


def test_an_unseeded_host_is_the_defect_this_repairs(tmp_path):
    """Pinned so the empty branch can never be mistaken for a pass."""

    from chemsmart.agent.runtime.event_store import RuntimeEventStore

    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="gate"
        )
    )
    assert host.requested_observable_declarations == {}
    assert host._declared_observable_completion(task_spec_sha256="a" * 64) == (
        (),
        (),
    )


def test_the_reviewer_sees_the_expectation_before_granting(tmp_path):
    """The only moment a wrong premise is still cheap."""

    from chemsmart.agent.tui.review import _declared_observable_panel

    base = _review(tmp_path)
    assert _declared_observable_panel(base) is None

    review = _review_with_declarations(base, (_BARRIER,))
    panel = _declared_observable_panel(review)
    assert panel is not None
    rendered = str(panel.renderable)
    assert "central_barrier" in rendered
    assert "kcal/mol" in rendered
    # The expectation and what it rests on, not just the name.
    assert "positive" in rendered
    assert "5.0 to 15.0" in rendered
    assert "Identity S_N2 central barriers" in rendered
