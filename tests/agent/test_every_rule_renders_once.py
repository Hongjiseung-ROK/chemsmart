"""A natural-language rule is a capability: it has an id, a placement,
and a provenance, and it renders exactly once where it is placed. The
system prompt, the goal wake, and the tool descriptions are views of
the registry, so adding or retiring a rule is one edit and nothing
lingers as an orphan sentence.
"""

from __future__ import annotations

import json

import pytest

from chemsmart.agent import driver
from chemsmart.agent.live_session import _system_prompt
from chemsmart.agent.rules import POLICY_RULES, rules_by_id, rules_for
from chemsmart.agent.tool_specs import build_command_compiled_tool_surface

pytestmark = pytest.mark.capability("rule:*")


def test_rule_ids_are_unique_and_placements_valid():
    ids = [rule.rule_id for rule in POLICY_RULES]
    assert len(ids) == len(set(ids))
    assert set(rules_by_id()) == set(ids)


def test_every_rule_renders_once_where_it_was_placed(
    tmp_path,
):
    """A placed rule renders exactly once, where it was placed.

    A leaf rule used to render in the stem of every session whether or
    not its guide was open; it then rendered inside its guide's body.
    There are no guides: a rule placed on a reference entry renders
    inside that entry's text, and a rule placed on a tool inside that
    tool's description -- which is read at the one moment that matters,
    because the schema is loaded before any argument is composed for it.

    Read off the real catalogue rather than a hand-built record: the
    registry-owned tokens in a body resolve against the session's own
    capability registry.
    """

    from chemsmart.agent.catalogue import build_tool_catalogue

    catalogue = build_tool_catalogue()
    prompt = _system_prompt({})
    for rule in POLICY_RULES:
        if rule.placement == "stem":
            assert prompt.count(rule.text.strip()) == 1, rule.rule_id
        else:
            assert rule.text.strip() not in prompt, rule.rule_id
        kind, _, target = rule.placement.partition(":")
        if kind not in {"reference", "tool"}:
            continue
        entry = catalogue.entry(target)
        assert entry is not None, rule.rule_id
        assert entry.description.count(rule.text.strip()) == 1, rule.rule_id


def test_the_owners_policing_rules_are_in_the_stem():
    prompt = _system_prompt({})
    for rule_id in (
        "stem.no_conclusion_without_result",
        "stem.no_engine_before_approval",
        "stem.no_failure_as_success",
        "stem.state_limitations",
    ):
        assert rules_by_id()[rule_id].placement == "stem"
        assert rules_by_id()[rule_id].text in prompt


def test_the_retired_sentences_are_gone():
    prompt = _system_prompt({})
    assert "workflow node IDs may separately express" not in prompt
    assert "semantic_role is optional" not in prompt


def test_wake_rules_render_in_the_wake_and_not_the_prompt():
    prompt = _system_prompt({})
    wake_text = (
        driver._GOAL_AUTHORITY
        + driver._OBSERVABLE_RESTATEMENT_ASK
        + driver._ADVERSARIAL_CLOSE
        + driver._REFUSAL_AFFORDANCE
        + driver._RECOVERY_ROUTE
        + driver._DISPOSITION_BRANCH
        + driver._APPROACHES_TRIED
        + driver._MENU_DISPOSITIONS
        + driver._FAILED_VALIDATION_CITATION
        + driver._CLAIM_BY_ID
        + driver._WORKSPACE_RECORD_RULE
        + driver._EXCURSION_REPLICATION
        + driver._COHORT_EVIDENCE
    )
    for rule in rules_for("wake") + rules_for("wake:recovery"):
        assert rule.text.strip() in wake_text, rule.rule_id
        assert rule.text.strip() not in prompt, rule.rule_id


def test_tool_placed_rules_reach_their_tool_once():
    text_by_tool = {
        item["function"]["name"]: item["function"]["description"]
        for item in build_command_compiled_tool_surface().tool_definitions
    }
    for rule in POLICY_RULES:
        if not rule.placement.startswith("tool:"):
            continue
        tool = rule.placement.split(":", 1)[1]
        assert text_by_tool[tool].count(rule.text.strip()) == 1, rule.rule_id
    surface_json = json.dumps(
        build_command_compiled_tool_surface().tool_definitions
    )
    for rule in rules_for("stem"):
        assert rule.text.strip() not in surface_json, rule.rule_id
