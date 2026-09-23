"""A name the host tells the model to use is one the host can serve.

From 2026-09-20 until this witness, the system prompt listed three
advisory documents by name, called them "carried in this prompt" and told
every session to consult them before judging a method or comparing with
experiment. One line of each was carried. The opener had been deleted
with the guide tree, the old consultation tool kept its handler and lost
its definition, and no catalogue entry held the text, so neither a call
by name nor a search could reach it. The lesson from the first time this
affordance failed (a vendor-name gate that listed no skills at all) was
kept as prose in a docstring, and prose did not stop the repeat.

This is the lesson made mechanical, for every mode a provider may be
given: read everything the host renders in front of the model -- the
system prompt as a session builds it, every catalogue entry's text, every
registered rule -- and every host handler name, advisory document id or
reference name found there must be an entry of that session's catalogue,
because the catalogue is what a call by name and a search can load. A
family written as ``name_<program>`` or ``name_*`` must match at least one
entry.
"""

from __future__ import annotations

import re

import pytest

from chemsmart.agent.exposure import EXPOSURE_MODES, build_exposure
from chemsmart.agent.live_session import _coordinator_base_messages
from chemsmart.agent.rules import POLICY_RULES
from chemsmart.agent.skills import available_skill_ids
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

pytestmark = pytest.mark.capability("skill:*", "reference:*")

_NAME = re.compile(r"[a-z][a-z0-9_\-]*[a-z0-9](?:_<|_\*)?")


def _unserved_names(text: str, served: set[str]) -> set[str]:
    handlers = set(CommandCompiledToolHostV1.TOOL_HANDLERS)
    documents = set(available_skill_ids())
    unserved: set[str] = set()
    for match in _NAME.finditer(text):
        token = match.group(0)
        if token.endswith(("_<", "_*")):
            stem = token[:-1]
            if not any(name.startswith(stem) for name in served):
                unserved.add(token)
            continue
        named = (
            token in handlers
            or token in documents
            or token.startswith("about_")
        )
        if named and token not in served:
            unserved.add(token)
    return unserved


@pytest.mark.parametrize("mode", EXPOSURE_MODES)
def test_every_name_the_rendered_surface_names_is_one_a_session_can_load(
    mode,
):
    exposure = build_exposure(mode)
    served = set(exposure.catalogue.names())
    prompt = _coordinator_base_messages(
        context={}, approved_workflow=None, exposure=exposure
    )[0]["content"]
    readings = {"system prompt": prompt}
    for entry in exposure.catalogue.entries:
        readings[f"entry {entry.name}"] = entry.description
    for rule in POLICY_RULES:
        readings[f"rule {rule.rule_id}"] = rule.text
    unserved = {
        where: sorted(names)
        for where, text in readings.items()
        if (names := _unserved_names(text, served))
    }
    assert not unserved, (
        "the model is told to use names its session cannot load: "
        f"{unserved}"
    )


def test_the_knowledge_the_prompt_names_is_in_the_catalogue_it_names():
    """The index and the entries are one answer, computed once.

    A session offered advisory knowledge is told about it exactly once,
    and every entry it is told about is a reference entry whose text is
    the document's own.
    """

    from chemsmart.agent.catalogue import KNOWLEDGE_FAMILY
    from chemsmart.agent.rules import rules_by_id
    from chemsmart.agent.skills import advertised_skill_documents

    exposure = build_exposure("host_search")
    prompt = _coordinator_base_messages(
        context={}, approved_workflow=None, exposure=exposure
    )[0]["content"]
    knowledge = [
        entry
        for entry in exposure.catalogue.entries
        if entry.family == KNOWLEDGE_FAMILY
    ]
    documents = advertised_skill_documents()
    assert documents and len(knowledge) == len(documents)
    for entry, document in zip(knowledge, documents):
        assert entry.kind == "reference"
        assert document.body.strip() in entry.description
        assert f"({entry.name}: " in prompt
    sentence = rules_by_id()["stem.knowledge_is_reference_text"].text
    assert prompt.count(sentence.strip()) == 1


def test_no_advisory_knowledge_means_no_sentence_about_it(monkeypatch):
    monkeypatch.setenv("CHEMSMART_AGENT_SKILLS", "0")
    from chemsmart.agent.catalogue import KNOWLEDGE_FAMILY
    from chemsmart.agent.rules import rules_by_id

    exposure = build_exposure("host_search")
    prompt = _coordinator_base_messages(
        context={}, approved_workflow=None, exposure=exposure
    )[0]["content"]
    assert KNOWLEDGE_FAMILY not in exposure.catalogue.families()
    sentence = rules_by_id()["stem.knowledge_is_reference_text"].text
    assert sentence.strip() not in prompt
