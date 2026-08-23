"""What a session consulted must reach the reviewer without a transcript.

A behavioural audit of a 63-run campaign found the host recording consulted
skills into session RAM that nothing downstream ever read: a reviewer could
not see what advisory knowledge a session worked under without re-reading
raw provider transcripts. Consultation is now a durable event, rehydrates
with the rest of the typed state, and travels into the review packet as
pure provenance -- id, version, and digests, nothing else. It grants no
authority and no gate consumes it; where the record and a receipt disagree,
the receipt is what happened.
"""

from __future__ import annotations

import pytest

from chemsmart.agent.execution import build_workflow_execution_review
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from tests.agent.test_exact_execution_approval_chain import _review

_SKILL = "method-adequacy"


@pytest.fixture()
def store_path(tmp_path):
    return tmp_path / "events" / "runtime.jsonl"


def _host(store_path):
    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(store_path, session_id="s1")
    )


def _consult(host, skill_id=_SKILL):
    envelope = host.dispatch(
        turn_id="t1",
        tool_name="consult_domain_skill",
        arguments={"skill_id": skill_id},
    )
    assert envelope["status"] == "ok"
    return envelope["result"]


def test_a_consultation_is_a_durable_event(store_path):
    host = _host(store_path)
    payload = _consult(host)

    events = [
        event
        for event in host.event_store.read_events()
        if event.kind == EventKind.DOMAIN_SKILL_CONSULTED.value
    ]
    assert len(events) == 1
    record = events[0].payload["record"]
    assert record["skill_id"] == _SKILL
    assert record["document_sha256"] == payload["document_sha256"]
    # Provenance only: the durable record must not carry the body, or the
    # event stream becomes a second distribution channel for advisory text.
    assert "body" not in record


def test_a_new_host_rehydrates_the_provenance(store_path):
    _consult(_host(store_path))

    successor = _host(store_path)

    records = tuple(successor.consulted_skill_records.values())
    assert len(records) == 1
    assert records[0]["skill_id"] == _SKILL


def test_the_review_carries_it_as_provenance_without_authority(tmp_path):
    base = _review(tmp_path)
    record = {
        "skill_id": _SKILL,
        "skill_version": "0.1.0",
        "origin": "builtin",
        "body_sha256": "a" * 64,
        "document_sha256": "b" * 64,
    }

    review = build_workflow_execution_review(
        request=base.request,
        scientific_plan=base.scientific_plan,
        materialized_workflow=base.materialized_workflow,
        execution_resources=base.execution_resources,
        execution_envelope=base.execution_envelope,
        environment_bindings=base.environment_bindings,
        node_reviews=base.node_reviews,
        stationary_point_policy=base.stationary_point_policy,
        consulted_domain_knowledge=(record,),
    )

    assert review.consulted_domain_knowledge[0]["skill_id"] == _SKILL
    # A consultation changes the displayed bytes, so the single /approve
    # covers a packet that names it.
    assert review.review_sha256 != base.review_sha256


def test_an_empty_consultation_keeps_the_historical_bytes(tmp_path):
    """Additive-field discipline: old packets keep their exact digest."""

    base = _review(tmp_path)
    rebuilt = build_workflow_execution_review(
        request=base.request,
        scientific_plan=base.scientific_plan,
        materialized_workflow=base.materialized_workflow,
        execution_resources=base.execution_resources,
        execution_envelope=base.execution_envelope,
        environment_bindings=base.environment_bindings,
        node_reviews=base.node_reviews,
        stationary_point_policy=base.stationary_point_policy,
        consulted_domain_knowledge=(),
    )
    assert rebuilt.review_sha256 == base.review_sha256


def test_the_panel_states_it_grants_no_authority(tmp_path):
    from chemsmart.agent.tui.review import _advisory_knowledge_panel

    base = _review(tmp_path)
    assert _advisory_knowledge_panel(base) is None

    review = build_workflow_execution_review(
        request=base.request,
        scientific_plan=base.scientific_plan,
        materialized_workflow=base.materialized_workflow,
        execution_resources=base.execution_resources,
        execution_envelope=base.execution_envelope,
        environment_bindings=base.environment_bindings,
        node_reviews=base.node_reviews,
        stationary_point_policy=base.stationary_point_policy,
        consulted_domain_knowledge=(
            {
                "skill_id": _SKILL,
                "skill_version": "0.1.0",
                "origin": "builtin",
                "body_sha256": "a" * 64,
                "document_sha256": "b" * 64,
            },
        ),
    )
    panel = _advisory_knowledge_panel(review)
    assert panel is not None
    assert "no readiness or accuracy authority" in str(panel.title)
