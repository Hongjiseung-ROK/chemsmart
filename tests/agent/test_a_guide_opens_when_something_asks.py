"""The surface is a tree: a stem every session reads, and leaves the host
opens from four signals or the model opens itself. Opening a leaf changes
what the model can express and how much it reads, never what the host
approves; every activation is an event carrying the new schema digest.
"""

from __future__ import annotations

import json

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.guides import (
    GUIDES,
    LEAF_OPERATIONS,
    LEAF_TOOLS,
    guides_from_plan,
    guides_from_states,
    guides_from_text,
    guides_from_workspace,
)
from chemsmart.agent.rules import POLICY_RULES
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.agent.tool_specs import build_command_compiled_tool_surface

pytestmark = pytest.mark.capability("guide:*")


def _names(surface):
    return {item["function"]["name"] for item in surface.tool_definitions}


def _operations(surface):
    evaluator = next(
        item["function"]
        for item in surface.tool_definitions
        if item["function"]["name"] == "evaluate_quantity_expression"
    )
    return set(
        evaluator["parameters"]["properties"]["nodes"]["items"]["properties"][
            "operation"
        ]["enum"]
    )


def test_the_stem_hides_every_leaf_tool_and_operation():
    stem = build_command_compiled_tool_surface()
    assert not (set(LEAF_TOOLS) & _names(stem))
    assert not (set(LEAF_OPERATIONS) & _operations(stem))
    assert "open_guide" in _names(stem)
    assert len(json.dumps(stem.tool_definitions)) < 90_000


def test_every_guide_adds_exactly_its_tools_and_operations():
    stem = build_command_compiled_tool_surface()
    for guide in GUIDES:
        opened = build_command_compiled_tool_surface(guides=(guide.guide_id,))
        assert _names(opened) - _names(stem) == set(
            guide.tools
        ), guide.guide_id
        assert _operations(opened) - _operations(stem) == set(
            guide.operations
        ), guide.guide_id
        assert opened.tool_schema_sha256 != stem.tool_schema_sha256 or (
            not guide.tools and not guide.operations
        )


def test_the_four_signals():
    assert "scan" in guides_from_text("Run a relaxed torsional scan of butane")
    assert "saddle" in guides_from_text("locate the transition state and IRC")
    assert guides_from_workspace(("chemsmart_db",)) == ("database",)
    assert guides_from_plan(jobtypes=("irc",)) == ("saddle",)
    assert guides_from_plan(operations=("gibbs_to_pka",)) == ("constants",)
    assert guides_from_plan(tools=("edit_molecular_geometry",)) == (
        "structure",
    )
    assert set(guides_from_states(("failed_wrong_stationary_point",))) == {
        "recovery",
        "saddle",
        "structure",
    }
    assert guides_from_states(("timeout_terminated",)) == ("recovery",)
    assert guides_from_states(("validated",)) == ()


def _host(tmp_path, **kwargs):
    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="guide-session"
        ),
        artifacts={},
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
        **kwargs,
    )


def test_opening_a_guide_extends_the_surface_and_records_the_digest(tmp_path):
    host = _host(tmp_path)
    before = host.surface.tool_schema_sha256
    assert "compose_molecular_arrangement" not in _names(host.surface)
    reply = host.dispatch(
        turn_id="t1",
        tool_name="open_guide",
        arguments={"guide_id": "structure"},
    )
    record = reply["result"]
    assert record["guide_id"] == "structure"
    assert "compose_molecular_arrangement" in record["tools_now_available"]
    assert "compose_molecular_arrangement" in _names(host.surface)
    assert host.surface.tool_schema_sha256 != before
    events = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text().splitlines()
    ]
    activated = [
        e for e in events if e["kind"] == EventKind.GUIDE_ACTIVATED.value
    ]
    assert len(activated) == 1
    assert activated[0]["payload"]["signal"] == "model"
    assert activated[0]["payload"]["tool_schema_sha256"] == (
        host.surface.tool_schema_sha256
    )
    # Opening it again is idempotent: no second event, same digest.
    host.dispatch(
        turn_id="t2",
        tool_name="open_guide",
        arguments={"guide_id": "structure"},
    )
    events = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text().splitlines()
    ]
    assert (
        len(
            [e for e in events if e["kind"] == EventKind.GUIDE_ACTIVATED.value]
        )
        == 1
    )


def test_a_leaf_tool_called_by_name_opens_its_guide_first(tmp_path):
    host = _host(tmp_path)
    with pytest.raises(ContractError) as failure:
        host.dispatch(
            turn_id="t1",
            tool_name="inspect_database_records",
            arguments={"artifact_id": "db.missing"},
        )
    # The guide opened on the model's own call; the refusal is the
    # handler's (no such artifact), not "tool is not exposed".
    assert "not exposed" not in str(failure.value)
    assert "database" in host.active_guides


def test_a_session_started_with_guides_reads_them(tmp_path):
    host = _host(tmp_path, active_guides=("scan",))
    assert "bind_scan_point_geometry" in _names(host.surface)
    assert "coordinate_at_minimum" in _operations(host.surface)


def test_an_unknown_guide_names_what_exists(tmp_path):
    host = _host(tmp_path)
    with pytest.raises(ContractError, match="guides:.*skills:"):
        host._open_guide("t1", {"guide_id": "kinetics"})


def test_a_skill_is_still_reachable_through_open_guide(tmp_path):
    host = _host(tmp_path)
    reply = host._open_guide("t1", {"guide_id": "method-adequacy"})
    assert reply["skill_id"] == "method-adequacy"


def test_no_rule_is_placed_on_a_leaf_that_does_not_exist():
    guide_ids = {guide.guide_id for guide in GUIDES}
    for rule in POLICY_RULES:
        if rule.placement.startswith("leaf:"):
            assert rule.placement.split(":", 1)[1] in guide_ids, rule.rule_id
