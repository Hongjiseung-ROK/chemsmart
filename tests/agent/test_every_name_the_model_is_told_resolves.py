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
name the host serves: a catalogue entry, or a word of an act's own
vocabulary -- a result selector the extraction act reads, an operation
the expression act evaluates. (A rule naming the ``singlet_*`` and
``triplet_*`` selector blocks is served by the extraction act, and the
first version of this witness, which asked only the catalogue, called it
unserved.)
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


def _served_vocabulary(exposure) -> set[str]:
    """Every name a session can reach: catalogue entries and act vocabularies."""

    from chemsmart.analysis.quantity_expressions import OPERATION_DESCRIPTIONS
    from chemsmart.analysis.result_quantities import supported_selectors

    return (
        set(exposure.catalogue.names())
        | set(supported_selectors())
        | set(OPERATION_DESCRIPTIONS)
    )


@pytest.mark.parametrize("knowledge", ("1", "0"))
@pytest.mark.parametrize("mode", EXPOSURE_MODES)
def test_every_name_the_rendered_surface_names_is_one_a_session_can_load(
    monkeypatch, mode, knowledge
):
    monkeypatch.setenv("CHEMSMART_AGENT_SKILLS", knowledge)
    exposure = build_exposure(mode)
    served = _served_vocabulary(exposure)
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


def test_the_knowledge_the_prompt_names_is_in_the_catalogue_it_names(
    monkeypatch,
):
    """The index and the entries are one answer, computed once.

    A session offered advisory knowledge is told about it exactly once,
    and every entry it is told about is a reference entry whose text is
    the document's own.
    """

    from chemsmart.agent.catalogue import KNOWLEDGE_FAMILY
    from chemsmart.agent.rules import rules_by_id
    from chemsmart.agent.skills import advertised_skill_documents

    monkeypatch.setenv("CHEMSMART_AGENT_SKILLS", "1")
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


@pytest.mark.parametrize("enabled", ("1", "0"))
def test_a_skill_is_advertised_exactly_when_a_session_can_load_it(
    monkeypatch, enabled
):
    """The ladder's rung is the catalogue's answer, not a constant.

    It read "system prompt skill index" for every skill, so the ladder
    reported all three advertised through the days no session could open
    one, and with the knowledge switched off.
    """

    from chemsmart.agent.capability_registry import build_capability_registry

    monkeypatch.setenv("CHEMSMART_AGENT_SKILLS", enabled)
    served = set(build_exposure("host_search").catalogue.names())
    skills = [
        item
        for item in build_capability_registry(tests_root=None, host_store=None)
        if item.kind == "skill"
    ]
    assert skills
    for item in skills:
        loadable = f"about_{item.id.replace('-', '_')}" in served
        assert (item.status == "advertised") is loadable, item.key


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


def _tagged_requests() -> tuple[list[str], list[str]]:
    """Drive the terminal's own /skills, /skill and submit handlers.

    Returns the request texts the terminal handed to planning after each
    advisory document was tagged, and everything it wrote for the human.
    Nothing is planned: the stub controller records the text and stops.
    """

    from types import SimpleNamespace

    from chemsmart.agent._contracts import ContractError
    from chemsmart.agent.tui.app import ChemSmartAgentApp

    requests: list[str] = []

    class _Controller:
        def begin_planning(self, text: str) -> str:
            requests.append(text)
            raise ContractError("stopped after the request was composed")

    import io

    from rich.console import Console

    def plain(renderable) -> str:
        buffer = io.StringIO()
        Console(file=buffer, width=200, color_system=None).print(renderable)
        return buffer.getvalue()

    app = ChemSmartAgentApp(_Controller())
    written: list[str] = []
    app._write = lambda renderable: written.append(plain(renderable))
    app._usage = lambda message: written.append(str(message))
    app._operation_failed = lambda label, exc: None
    app._sync_phase = lambda *args, **kwargs: None
    app.notify = lambda *args, **kwargs: None
    app._dispatch_command("/skills")
    for skill_id in available_skill_ids():
        app._dispatch_command(f"/skill {skill_id}")
        event = SimpleNamespace(
            value="Plan a calculation.", input=SimpleNamespace(value="")
        )
        app.submit(event)
    return requests, written


@pytest.mark.parametrize("knowledge", ("1", "0"))
def test_a_tag_the_human_puts_on_a_request_names_what_the_session_can_load(
    monkeypatch, knowledge
):
    """The terminal's /skill tag reaches the model beside the request.

    It named the advisory document by its id, which no call or search
    serves, and it still offered every document with the knowledge
    switched off -- the prompt's old failure reached through the human's
    path instead of the prompt. Off, the terminal says the knowledge is
    off and how to turn it on, and tags nothing.
    """

    pytest.importorskip("textual")
    monkeypatch.setenv("CHEMSMART_AGENT_SKILLS", knowledge)
    served = _served_vocabulary(build_exposure("host_search"))
    requests, written = _tagged_requests()
    assert requests, "the terminal handed no request to planning"
    unserved = {
        text[:80]: sorted(names)
        for text in requests
        if (names := _unserved_names(text, served))
    }
    assert not unserved, (
        "a tagged request names what the session cannot load: " f"{unserved}"
    )
    if knowledge == "0":
        assert all(text == "Plan a calculation." for text in requests)
        assert any("CHEMSMART_AGENT_SKILLS=1" in text for text in written)
    else:
        assert all(text != "Plan a calculation." for text in requests)
