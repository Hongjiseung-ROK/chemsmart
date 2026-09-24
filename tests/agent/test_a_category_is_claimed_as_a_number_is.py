"""A categorical answer is delivered as a number is: claimed under its id.

A question whose answer is a word -- is the restricted reference stable,
which way did the IRC branch go -- is declared in unit ``category``. The
claim tool tells a session to give the claim that answers a declaration
that declaration's id, and for a number that is the whole act. For a word
it was refused with the number's diagnosis ("a word the program printed
has no magnitude to deliver"): in the archive that refusal fired 16 times,
and all 16 were words claimed under a declared category, in 8 of the 9
goals that declared one; 7 were the claim node of an approved chain,
which failed whole and took the requested energy with it (R10 Q23
census; ls2, CUHK 2153514). Meanwhile a 0/1 verdict of the session's own
rule, claimed under the same id, was accepted and called undelivered only
at completion, three cycles running (G-h2, CUHK 2153627).

Driven through the tool loop a provider talks to, with a real host over
the archived bytes of a PySCF 2.14.0 run of closed-shell singlet O2 --
externally unstable toward UKS, internally stable -- and through the goal
loop that settles it.
"""

from __future__ import annotations

import json

import pytest

from chemsmart.agent.delivery import observable_is_delivered
from chemsmart.agent.driver import _goal_delivered_ids

from .test_a_failed_criterion_is_a_finding_the_goal_can_deliver import (
    _goal,
    _real_session,
    _run_turns,
    _stream_rows,
)
from .test_a_partial_delivery_ends_its_session import _call, _turn
from .test_the_goal_loop_recovers_or_returns import _planning_session

pytestmark = [
    pytest.mark.capability("tool:record_analysis_claims"),
    pytest.mark.capability("selector:pyscf:sp:scf_stability_external"),
]

_QUESTION = "rks-spin-stability"
_DECLARATIONS = [
    {
        "observable_id": "rks-energy",
        "unit": "hartree",
        "meaning": "electronic energy of the closed-shell RKS reference",
    },
    {
        "observable_id": _QUESTION,
        "unit": "category",
        "meaning": (
            "whether the closed-shell RKS reference is stable to "
            "spin-symmetry-breaking (RKS -> UKS) orbital rotations"
        ),
    },
]
_RUN_ID = "live-20260925T000000000000Z-q23-category"


def _receipts(payload):
    """The receipt of every tool reply so far, in order."""

    found = []
    for message in payload.get("messages") or ():
        if message.get("role") != "tool":
            continue
        result = json.loads(message.get("content") or "{}").get("result")
        if isinstance(result, dict) and result.get("receipt_sha256"):
            found.append(result["receipt_sha256"])
    return found


def _replies(payload, tool):
    """Every reply to ``tool`` so far, whole."""

    return [
        json.loads(message.get("content") or "{}")
        for message in payload.get("messages") or ()
        if message.get("role") == "tool"
        and json.loads(message.get("content") or "{}").get("tool") == tool
    ]


def _decision(payload):
    return {
        "decision_id": "o2-rks-spin-stability",
        "assumptions": ["the restricted reference at the fixed geometry"],
        "method_rationale": "PySCF's own stability analysis answers it",
        "alternatives": ["a broken-symmetry UKS solution, not asked"],
        "uncertainties": ["none beyond the fixed level of theory"],
        "diagnostics": ["the external verdict word"],
        "stage_order": ["extract", "claim"],
        "evidence_refs": [],
        "postprocessing_receipt_sha256s": _receipts(payload)[-2:],
    }


def _claimed_word_turns(artifact_id, seen):
    """Declare, read, claim the word under the question's id, decide."""

    def claimed(payload):
        receipt = _receipts(payload)[-1]
        return {
            "claims": [
                {
                    "claim_id": "rks-energy",
                    "receipt_sha256": receipt,
                    "quantity_id": "e-rks",
                    "display_unit": "hartree",
                },
                {
                    "claim_id": _QUESTION,
                    "receipt_sha256": receipt,
                    "quantity_id": "external-word",
                    "display_unit": "1",
                },
            ]
        }

    def decided(payload):
        seen.extend(_replies(payload, "record_analysis_claims"))
        return _decision(payload)

    return [
        lambda payload: _turn(
            1,
            "Stating the questions.",
            (
                _call(
                    1,
                    "declare_requested_observable",
                    {"observables": _DECLARATIONS},
                ),
            ),
        ),
        lambda payload: _turn(
            2,
            "Reading the energy and the verdict word.",
            (
                _call(
                    2,
                    "extract_result_quantities",
                    {
                        "program": "pyscf",
                        "artifact_id": artifact_id,
                        "selectors": [
                            {"quantity_id": "e-rks", "selector": "energy"},
                            {
                                "quantity_id": "external-word",
                                "selector": "scf_stability_external",
                            },
                        ],
                    },
                ),
            ),
        ),
        lambda payload: _turn(
            3,
            "Claiming the answers under the questions' ids.",
            (_call(3, "record_analysis_claims", claimed(payload)),),
        ),
        lambda payload: _turn(
            4,
            "Recording the decision.",
            (_call(4, "record_scientific_decision", decided(payload)),),
        ),
        lambda payload: _turn(
            5, "The RKS reference is unstable toward UKS; energy claimed."
        ),
    ]


def test_a_word_claimed_under_its_question_answers_it(tmp_path):
    """The act that delivers a number delivers the word: one claim under
    the question's id, certified by the gate, carried by the record to the
    goal grain, and stated first in the settlement with what read it."""

    seen: list = []
    result = _goal(
        tmp_path,
        sessions=[
            _real_session(
                tmp_path,
                _RUN_ID,
                lambda artifact_id: _claimed_word_turns(artifact_id, seen),
            ),
            # Only a goal whose question stayed open wakes again.
            _planning_session("live-2", terminal="blocked"),
        ],
    )
    (reply,) = seen
    assert reply["status"] == "ok", reply
    (said,) = [
        row
        for row in reply.get("observations") or ()
        if row.get("answers_declared_category")
    ]
    assert said["answers_declared_category"] == _QUESTION
    assert said["word"] == "unstable"
    assert said["selector"] == "scf_stability_external"

    stream = (
        tmp_path
        / "ws"
        / ".chemsmart-agent"
        / "runs"
        / _RUN_ID
        / "events.jsonl"
    )
    completion = [
        event["payload"]
        for event in _stream_rows(stream)
        if event["kind"] == "analysis_completion_evaluated"
    ][-1]
    assert completion["status"] == "passed"
    assert not completion.get("limitation_output_ids")
    assert completion["declared_observable_join_fields"][_QUESTION] == (
        "claim_id"
    )
    ((word,),) = [completion["declared_categorical_answers"][_QUESTION]]
    assert (word["word"], word["selector"]) == (
        "unstable",
        "scf_stability_external",
    )

    assert result.settlement == "achieved", result.reasons
    assert any(
        f"{_QUESTION} = 'unstable' (read by the host: scf_stability_external"
        in reason
        and "claimed under the declared id" in reason
        for reason in result.reasons
    ), result.reasons

    # A later cycle's settlement reads the record, not this stream.
    row = _goal_delivered_ids(tmp_path / "ws", "goal-o2r")[_QUESTION]
    assert observable_is_delivered(_DECLARATIONS[1], row)
    assert not observable_is_delivered(
        {"observable_id": _QUESTION, "unit": "1"}, row
    )


def _chain_turns(artifact_id):
    """ls2's cycle-1 shape: a planned chain whose claim node names the
    category's id for the word, beside the energy."""

    workflow = "o2-rks-chain"
    extraction = {
        "workflow_id": workflow,
        "stages": [
            {
                "node_id": "extract-o2",
                "artifact_id": artifact_id,
                "dependencies": [],
                "inputs": [],
                "selectors": [
                    {"quantity_id": "e-rks", "selector": "energy"},
                    {
                        "quantity_id": "external-word",
                        "selector": "scf_stability_external",
                    },
                ],
                "outputs": [
                    {
                        "output_id": "e-rks",
                        "quantity_kind": "energy",
                        "unit": "hartree",
                    },
                    {
                        "output_id": "external-word",
                        "quantity_kind": "stability-verdict-word",
                        "unit": "category",
                    },
                ],
                "support_state": "planned",
                "blocked_reason": "",
            }
        ],
    }
    claims = {
        "workflow_id": workflow,
        "stages": [
            {
                "node_id": "claim-o2",
                "dependencies": ["extract-o2"],
                "inputs": [
                    {
                        "input_id": "rks-energy",
                        "source_kind": "analysis_output",
                        "producer_node_id": "extract-o2",
                        "producer_output_id": "e-rks",
                    },
                    {
                        "input_id": _QUESTION,
                        "source_kind": "analysis_output",
                        "producer_node_id": "extract-o2",
                        "producer_output_id": "external-word",
                    },
                ],
                "outputs": [
                    {
                        "output_id": "rks-energy",
                        "quantity_kind": "energy",
                        "unit": "hartree",
                    },
                    {
                        "output_id": _QUESTION,
                        "quantity_kind": "stability-verdict-word",
                        "unit": "category",
                    },
                ],
                "support_state": "planned",
                "blocked_reason": "",
            }
        ],
    }
    finalise = {
        "plan_id": "o2-rks-chain-plan",
        "workflow_id": workflow,
        "required_output_ids": ["rks-energy", _QUESTION],
    }
    return [
        lambda payload: _turn(
            1,
            "Stating the questions.",
            (
                _call(
                    1,
                    "declare_requested_observable",
                    {"observables": _DECLARATIONS},
                ),
            ),
        ),
        lambda payload: _turn(
            2,
            "Planning the reading of the registered result.",
            (
                _call(2, "plan_result_extraction", extraction),
                _call(3, "plan_claim_rendering", claims),
                _call(4, "plan_scientific_workflow", finalise),
            ),
        ),
        lambda payload: _turn(3, "Planned."),
    ]


def test_a_planned_claim_node_delivers_the_category_beside_the_number(
    tmp_path,
):
    """ls2's approved chain claimed the word under the category's id and
    the whole claim node failed, the energy with it. The same chain now
    renders both, and its completion certifies the category."""

    stream = tmp_path / "chain" / "events.jsonl"
    _run_turns(
        stream, _chain_turns, session_id="protocol-session", scratch=tmp_path
    )
    rows = _stream_rows(stream)
    settled = {
        event["payload"]["node_id"]: event["payload"]
        for event in rows
        if event["kind"] == "workflow_analysis_node_settled"
    }
    assert settled["claim-o2"]["state"] == "executed", settled["claim-o2"]
    completion = [
        event["payload"]
        for event in rows
        if event["kind"] == "analysis_completion_evaluated"
    ][-1]
    assert completion["status"] == "passed", completion
    assert not completion.get("limitation_output_ids")
    ((word,),) = [completion["declared_categorical_answers"][_QUESTION]]
    assert word["word"] == "unstable"


def _verdict_turns(artifact_id, seen, *, door):
    """G-h2's shape: the answer to a yes/no question carried by a
    validation rule of the session's own. Through the claim door its 0/1
    verdict is claimed under the category's id; through the finding door
    it is claimed under a name of its own and a finding answering the
    category rests on it."""

    workflow = "o2-rks-verdict"
    extraction = {
        "workflow_id": workflow,
        "stages": [
            {
                "node_id": "extract-o2",
                "artifact_id": artifact_id,
                "dependencies": [],
                "inputs": [],
                "selectors": [
                    {
                        "quantity_id": "eig-external",
                        "selector": "scf_stability_external_lowest_eigenvalue",
                    }
                ],
                "outputs": [
                    {
                        "output_id": "eig-external",
                        "quantity_kind": "eigenvalue",
                        "unit": "hartree",
                    }
                ],
                "support_state": "planned",
                "blocked_reason": "",
            }
        ],
    }
    validation = {
        "workflow_id": workflow,
        "stages": [
            {
                "node_id": "val-external",
                "dependencies": [],
                "inputs": [
                    {
                        "input_id": "eig-in",
                        "source_kind": "analysis_output",
                        "producer_node_id": "extract-o2",
                        "producer_output_id": "eig-external",
                    }
                ],
                "outputs": [
                    {
                        "output_id": "external-verdict",
                        "quantity_kind": "verdict",
                        "unit": "1",
                    }
                ],
                "validation_rules": [
                    {
                        "rule_id": "external-stable",
                        "predicate": "minimum_greater_equal",
                        "input_ids": ["eig-in"],
                        "threshold": 0,
                        "unit": "hartree",
                    }
                ],
                "support_state": "planned",
                "blocked_reason": "",
            }
        ],
    }
    finalise = {
        "plan_id": "o2-rks-verdict-plan",
        "workflow_id": workflow,
        "required_output_ids": ["external-verdict"],
    }

    def judged(payload):
        return {
            "workflow_id": workflow,
            "node_id": "val-external",
            "inputs": [
                {
                    "input_id": "eig-in",
                    "receipt_sha256": _receipts(payload)[-1],
                    "quantity_id": "eig-external",
                }
            ],
        }

    def claimed(payload):
        return {
            "claims": [
                {
                    "claim_id": (
                        _QUESTION if door == "claim" else "external-verdict"
                    ),
                    "receipt_sha256": _receipts(payload)[-1],
                    "quantity_id": "external-verdict",
                    "display_unit": "1",
                }
            ]
        }

    def decided(payload):
        seen.extend(_replies(payload, "record_analysis_claims"))
        return {
            **_decision(payload),
            "findings": [
                {
                    "finding_id": "external-rule-failed",
                    "statement": "Unstable: my external rule did not hold.",
                    "answers_observable_id": _QUESTION,
                    "rests_on": [
                        {
                            "claim_id": "external-verdict",
                            "relation": "==",
                            "value": 0,
                        }
                    ],
                }
            ],
        }

    def ended(payload):
        seen.extend(_replies(payload, "record_analysis_claims"))
        return _turn(5, "Done.")

    turns = [
        lambda payload: _turn(
            1,
            "Stating the question and the rule that answers it.",
            (
                _call(
                    1,
                    "declare_requested_observable",
                    {"observables": [_DECLARATIONS[1]]},
                ),
                _call(2, "plan_result_extraction", extraction),
                _call(3, "plan_scientific_validation", validation),
                _call(4, "plan_scientific_workflow", finalise),
            ),
        ),
        lambda payload: _turn(
            2,
            "Reading the eigenvalue.",
            (
                _call(
                    5,
                    "extract_result_quantities",
                    {
                        "program": "pyscf",
                        "artifact_id": artifact_id,
                        "selectors": extraction["stages"][0]["selectors"],
                    },
                ),
            ),
        ),
        lambda payload: _turn(
            3,
            "Judging.",
            (_call(6, "evaluate_scientific_validation", judged(payload)),),
        ),
        lambda payload: _turn(
            4,
            "Claiming the verdict.",
            (_call(7, "record_analysis_claims", claimed(payload)),),
        ),
    ]
    if door == "claim":
        return turns + [ended]
    return turns + [
        lambda payload: _turn(
            5,
            "Answering with the verdict.",
            (_call(8, "record_scientific_decision", decided(payload)),),
        ),
        lambda payload: _turn(6, "Done."),
    ]


@pytest.mark.capability("tool:evaluate_scientific_validation")
def test_a_rules_verdict_claimed_under_a_category_is_refused_naming_the_word(
    tmp_path,
):
    """A 0/1 verdict of the session's own rule says whether that rule held,
    and the answer would not carry which way the rule reads: the host
    would certify "'0', selector unrecorded" where the question asked for
    a word. Accepted here and called undelivered only at completion, it
    was claimed under G-h2's three category ids in three cycles. Refused
    at the claim now, naming the word route."""

    seen: list = []
    stream = tmp_path / "verdict" / "events.jsonl"
    _run_turns(
        stream,
        lambda artifact_id: _verdict_turns(artifact_id, seen, door="claim"),
        session_id="protocol-session",
        scratch=tmp_path,
    )
    (under_id,) = seen
    assert under_id["status"] != "ok", under_id
    said = json.dumps(under_id)
    assert "claim.a_category_is_answered_by_a_word_the_host_read" in said
    assert "validation rule" in said
    assert "scf_stability_external" in said


@pytest.mark.capability("tool:evaluate_scientific_validation")
def test_a_finding_on_a_rules_verdict_answers_no_category(tmp_path):
    """The other door into the same question: a finding answering the
    category and resting on the verdict. One rule answers for both doors,
    so it answers nothing here either and the refusal says why."""

    seen: list = []
    stream = tmp_path / "verdict" / "events.jsonl"
    _run_turns(
        stream,
        lambda artifact_id: _verdict_turns(artifact_id, seen, door="finding"),
        session_id="protocol-session",
        scratch=tmp_path,
    )
    (elsewhere,) = seen
    assert elsewhere["status"] == "ok", elsewhere
    failures = [
        event["payload"]
        for event in _stream_rows(stream)
        if event["kind"] == "tool_failed"
        and event["payload"]["tool"] == "record_scientific_decision"
    ]
    assert failures, "the finding resting on the verdict was accepted"
    said = json.dumps(failures[-1])
    assert "finding.answers_through_a_word_the_host_read" in said
    assert "validation rule" in said
