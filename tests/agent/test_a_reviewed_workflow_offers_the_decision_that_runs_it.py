"""A session that may run calculations is offered the decision that runs them.

`select_execution_wave` left the always-loaded set when the tool surface became
searchable, and bounded loading stopped it arriving by accident.  Four live
goals then previewed, validated and preflighted every node with zero findings,
built the execution review, and settled `execution_wave_decision_pending`
(CUHK 2142385, 2142394, 2142397 and one more): the tool that decides a wave was
in no session's callable set, and the word a model searches with -- "execute"
-- returned a draft inspector and a PySCF reference.

The host already states when the decision is pending: an undecided wave
with ready calculations, which is what its closing notice reads.  That typed
fact surfaces the acts that answer it, the way a plan naming a transition
state surfaces the saddle reference.  The first key tried was "this session
holds execution resources"; a session without them was then still told a
decision was pending that it could not make, so the two are one predicate.
"""

from __future__ import annotations

import pytest

from chemsmart.agent.exposure import build_exposure
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from tests.agent.neutral_workflow_fixture import build_neutral_workflow_fixture
from tests.agent.plan_through_draft import plan_workflow
from tests.agent.test_a_plan_beyond_the_engine_budget_is_refused_when_planned import (
    _envelope,
)

pytestmark = pytest.mark.capability("tool:select_execution_wave")

_DECISION_TOOLS = ("select_execution_wave", "continue_execution_reasoning")


def _host(tmp_path, **extra):
    fixture = build_neutral_workflow_fixture(tmp_path / "fixture")
    store = RuntimeEventStore(
        tmp_path / "events" / "runtime.jsonl", session_id="session"
    )
    # The constructors are pinned the way typed session-start state pins an
    # entry, so the helper's single dispatch drafts instead of loading.
    exposure = build_exposure("host_search").with_pinned(
        ("plan_calculation_stages",)
    )
    host = CommandCompiledToolHostV1(
        event_store=store,
        task_spec_sha256s=(fixture.public_context.task_spec_sha256,),
        approved_workspace=tmp_path / "preview",
        exposure=exposure,
        **fixture.host_inputs,
        **extra,
    )
    payload = dict(
        next(
            item
            for item in fixture.public_context.next_actions
            if item.tool_name == "plan_scientific_workflow"
        ).fields
    )
    return host, payload


def test_finalising_a_workflow_that_may_run_surfaces_the_wave_decision(
    tmp_path,
):
    envelope = _envelope(tmp_path, max_engine_calls=2)
    host, payload = _host(
        tmp_path,
        execution_resources=envelope.resources,
        bounded_execution_envelope=envelope,
    )
    for name in _DECISION_TOOLS:
        assert not host.exposure.is_available(name), name

    plan_workflow(host, "turn-1", payload)

    for name in _DECISION_TOOLS:
        assert host.exposure.is_available(name), name


def _told_a_decision_is_pending(host) -> bool:
    notice = host.termination_notice() or {}
    return notice.get("kind") == "execution_wave_decision_pending"


def test_what_the_host_says_is_pending_the_host_offers(tmp_path):
    """With or without execution resources, the notice and the offer agree."""

    host, payload = _host(tmp_path)
    assert not _told_a_decision_is_pending(host)
    for name in _DECISION_TOOLS:
        assert not host.exposure.is_available(name), name

    plan_workflow(host, "turn-1", payload)

    assert _told_a_decision_is_pending(host)
    for name in _DECISION_TOOLS:
        assert host.exposure.is_available(name), name
