"""A session whose own criterion failed ends on the word its delivery supports.

o2r (R10 Q13, CUHK Slurm 2152079) read and claimed its whole answer from a
registered PySCF result: the reference energy of closed-shell singlet O2 and
PySCF's stability verdicts. Its analysis plan carried a criterion -- the
lowest external eigenvalue is not negative -- that the physics failed,
because that reference is unstable to spin symmetry breaking. The completion
finalisation minted was therefore partial; the loop ended the session
``planned`` bound to that completion receipt, the event store admits
``planned`` only over the stream's latest workflow draft, terminate raised,
the stream was left open, and the goal returned to the human on "planned
termination requires the latest workflow draft". A scientific finding reached
the human as a host error, and the same class had cost three earlier goals
under the word "a required completion gate is red".

Driven through the loop a provider talks to, with a real host over the
archived bytes of a PySCF run of the same molecule.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chemsmart.agent._contracts import (
    TrustedArtifactRefV1,
    canonical_sha256,
    file_sha256,
)
from chemsmart.agent.loop import ToolLoopRunner
from chemsmart.agent.runtime.alibaba import (
    Qwen38MaxConfigV1,
    Qwen38MaxToolSession,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from tests.agent.provider_fakes import _run_contracts

_RESULT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "PySCFTests"
    / "outputs"
    / "o2_singlet_sp_stability_heard"
    / "o2_singlet_sp_stability_heard_gas_phase.h5"
)
_WORKFLOW = "o2-rks-stability"


def _host(tmp_path):
    artifact = TrustedArtifactRefV1(
        artifact_id=f"pyscf-result-{file_sha256(_RESULT)[:16]}",
        kind="pyscf_hdf5",
        sha256=file_sha256(_RESULT),
        size_bytes=_RESULT.stat().st_size,
        path=str(_RESULT),
        cli_value=str(_RESULT),
    )
    host = CommandCompiledToolHostV1(
        # The session id the shared run contracts name.
        event_store=RuntimeEventStore(
            tmp_path / "run" / "events.jsonl", session_id="protocol-session"
        ),
        task_spec_sha256s=(canonical_sha256("synthetic task"),),
        approved_workspace=tmp_path / "workspace",
        # What a woken cycle's host is given: a plan with no calculation
        # node is walked when it is planned.
        execute_analysis_only_plans=True,
        analysis_only_run_directory=tmp_path / "run",
        analysis_only_workspace=tmp_path / "workspace",
    )
    host.artifacts[artifact.artifact_id] = artifact
    return host, artifact.artifact_id


def _call(ordinal, name, arguments):
    return {
        "id": f"call-{ordinal}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def _turn(ordinal, content, tool_calls=()):
    message = {
        "role": "assistant",
        "content": content,
        "reasoning_content": "",
    }
    if tool_calls:
        message["tool_calls"] = list(tool_calls)
    return {
        "id": f"turn-{ordinal}",
        "model": "qwen3.8-max",
        "choices": [
            {
                "finish_reason": "tool_calls" if tool_calls else "stop",
                "message": message,
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def _o2r_turns(artifact_id):
    """The acts o2r's woken session made, in the order it made them."""

    extraction = {
        "workflow_id": _WORKFLOW,
        "stages": [
            {
                "node_id": "extract-o2-rks",
                "artifact_id": artifact_id,
                "dependencies": [],
                "inputs": [],
                "selectors": [
                    {"quantity_id": "ref-energy", "selector": "energy"},
                    {
                        "quantity_id": "eig-external-lowest",
                        "selector": "scf_stability_external_lowest_eigenvalue",
                    },
                ],
                "outputs": [
                    {
                        "output_id": "ref-energy",
                        "quantity_kind": "energy",
                        "unit": "hartree",
                    },
                    {
                        "output_id": "eig-external-lowest",
                        "quantity_kind": "eigenvalue",
                        "unit": "hartree",
                    },
                ],
                "support_state": "planned",
                "blocked_reason": "",
            }
        ],
    }
    validation = {
        "workflow_id": _WORKFLOW,
        "stages": [
            {
                "node_id": "val-rks-stability",
                "dependencies": [],
                "inputs": [
                    {
                        "input_id": "eig-external-in",
                        "source_kind": "analysis_output",
                        "producer_node_id": "extract-o2-rks",
                        "producer_output_id": "eig-external-lowest",
                    }
                ],
                "outputs": [
                    {
                        "output_id": "external-spin-verdict",
                        "quantity_kind": "verdict",
                        "unit": "1",
                    }
                ],
                "validation_rules": [
                    {
                        "rule_id": "external_no_spin_instability",
                        "predicate": "minimum_greater_equal",
                        "input_ids": ["eig-external-in"],
                        "threshold": 0,
                        "unit": "hartree",
                    }
                ],
                "support_state": "planned",
                "blocked_reason": "",
            }
        ],
    }
    claims = {
        "workflow_id": _WORKFLOW,
        "stages": [
            {
                "node_id": "claim-o2-rks",
                "dependencies": [],
                "inputs": [
                    {
                        "input_id": "ref-energy",
                        "source_kind": "analysis_output",
                        "producer_node_id": "extract-o2-rks",
                        "producer_output_id": "ref-energy",
                    },
                    {
                        "input_id": "rks-external-eigenvalue",
                        "source_kind": "analysis_output",
                        "producer_node_id": "extract-o2-rks",
                        "producer_output_id": "eig-external-lowest",
                    },
                ],
                "outputs": [
                    {
                        "output_id": "ref-energy",
                        "quantity_kind": "energy",
                        "unit": "hartree",
                    },
                    {
                        "output_id": "rks-external-eigenvalue",
                        "quantity_kind": "eigenvalue",
                        "unit": "hartree",
                    },
                ],
                "support_state": "planned",
                "blocked_reason": "",
            }
        ],
    }
    finalise = {
        "plan_id": "o2-rks-verdict-plan",
        "workflow_id": _WORKFLOW,
        "required_output_ids": [
            "ref-energy",
            "rks-external-eigenvalue",
            "external-spin-verdict",
        ],
    }
    selectors = extraction["stages"][0]["selectors"]

    def replies(payload):
        """The receipt of every tool reply so far, in order."""

        found = []
        for message in payload.get("messages") or ():
            if message.get("role") != "tool":
                continue
            result = json.loads(message.get("content") or "{}").get("result")
            if isinstance(result, dict) and result.get("receipt_sha256"):
                found.append(result["receipt_sha256"])
        return found

    def extracted(payload):
        return {
            "program": "pyscf",
            "artifact_id": artifact_id,
            "selectors": selectors,
        }

    def judged_and_claimed(payload):
        receipt = replies(payload)[-1]
        return (
            {
                "workflow_id": _WORKFLOW,
                "node_id": "val-rks-stability",
                "inputs": [
                    {
                        "input_id": "eig-external-in",
                        "receipt_sha256": receipt,
                        "quantity_id": "eig-external-lowest",
                    }
                ],
            },
            {
                "claims": [
                    {
                        "claim_id": output,
                        "receipt_sha256": receipt,
                        "quantity_id": quantity,
                        "display_unit": "hartree",
                    }
                    for output, quantity in (
                        ("ref-energy", "ref-energy"),
                        ("rks-external-eigenvalue", "eig-external-lowest"),
                    )
                ]
            },
        )

    def decided(payload):
        extraction_receipt, validation, claim_record = replies(payload)[-3:]
        return {
            "decision_id": "o2-rks-stability-verdict",
            "assumptions": ["the restricted reference at the fixed geometry"],
            "method_rationale": "the task fixed B3LYP/def2-SVP and PySCF",
            "alternatives": ["a broken-symmetry UKS solution, not asked"],
            "uncertainties": ["SCF convergence precision"],
            "diagnostics": ["the external eigenvalue is negative"],
            "stage_order": ["extract", "validate", "claim"],
            "evidence_refs": [],
            "postprocessing_receipt_sha256s": [
                extraction_receipt,
                validation,
                claim_record,
            ],
        }

    def second(payload):
        rule, claim = judged_and_claimed(payload)
        return (
            _call(6, "evaluate_scientific_validation", rule),
            _call(7, "record_analysis_claims", claim),
        )

    return [
        lambda payload: _turn(
            1,
            "Reading the answer from the registered result.",
            (
                _call(1, "plan_result_extraction", extraction),
                _call(2, "plan_scientific_validation", validation),
                _call(3, "plan_claim_rendering", claims),
                _call(4, "plan_scientific_workflow", finalise),
            ),
        ),
        lambda payload: _turn(
            2,
            "Reading the verdict quantities directly.",
            (_call(5, "extract_result_quantities", extracted(payload)),),
        ),
        lambda payload: _turn(3, "Judging and claiming.", second(payload)),
        lambda payload: _turn(
            4,
            "Recording the decision.",
            (_call(8, "record_scientific_decision", decided(payload)),),
        ),
        lambda payload: _turn(
            5,
            "The restricted reference is unstable to spin symmetry "
            "breaking; its energy and the eigenvalue are claimed.",
        ),
    ]


def _events(host):
    return [
        json.loads(line)
        for line in host.event_store.path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


@pytest.mark.capability("gate:terminal_state_vocabulary")
def test_a_partial_completion_ends_the_session_planned_on_its_draft(
    tmp_path,
):
    host, artifact_id = _host(tmp_path)
    turns = iter(_o2r_turns(artifact_id))
    config = Qwen38MaxConfigV1()
    session = Qwen38MaxToolSession(
        transport=lambda payload: next(turns)(payload),
        messages=[{"role": "user", "content": "Is the reference stable?"}],
        config=config,
    )
    envelope, request_context, network = _run_contracts(host, config)

    result = ToolLoopRunner(host=host, event_store=host.event_store).run(
        session=session,
        envelope=envelope,
        request_context=request_context,
        provider_budget=network,
        should_stop=lambda: False,
    )

    events = _events(host)
    kinds = [event["kind"] for event in events]
    # The physics failed the session's own criterion, so what
    # finalisation certified is a delivery with a stated limitation.
    completions = [
        event["payload"]
        for event in events
        if event["kind"] == "analysis_completion_evaluated"
    ]
    assert completions[-1]["status"] == "partial"
    assert any(
        finding.startswith("analysis.claim_on_failed_criterion.")
        for finding in completions[-1]["record"]["findings"]
    )
    # ...and the session ends on it, instead of raising out of run().
    assert result.terminal_state == "planned"
    assert kinds[-1] == "runtime_terminated"
    terminal = events[-1]["payload"]
    drafts = [
        event["payload"]["receipt_sha256"]
        for event in events
        if event["kind"] == "command_workflow_planned"
    ]
    assert terminal["plan_receipt_sha256"] == drafts[-1]
    assert terminal["reason"].startswith("the analysis completion is partial")
    # The claims the session made are in the stream the settlement reads.
    assert "analysis_claims_recorded" in kinds
