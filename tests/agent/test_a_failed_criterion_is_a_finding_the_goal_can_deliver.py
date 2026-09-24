"""A failed acceptance criterion is a finding the goal can deliver, once read.

A plan's ``scientific_validation`` node is the session's pre-registered
expectation about its own result. When the physics fails it, the goal has
produced a finding. Three host organs used to answer what that finding
makes of the delivery, each differently:

- the executor's walk of an approved chain certified it ``passed`` and never
  looked at the criterion;
- the session's completion named every claim standing on the criterion and
  never read a decision, so a session that cited the failed receipt and
  stood by its answer still ended partial and the goal returned to the human
  (L1, R10 Q16, CUHK Slurm 2152989: "it recorded analysis but the host
  completion gate did not pass");
- the settlement counted a verdict answered only when a decision cited that
  exact receipt, and settled an answered verdict plain ``achieved``, naming
  nothing.

One function now answers for all three (``chemsmart.agent.goal
.failed_criteria``): a verdict is answered when a recorded decision cites a
receipt that states it. Answered, the goal delivers the finding and
says so; unanswered, nothing standing on it is certified and the reason
names it.

Driven through the goal loop and the tool loop a provider talks to, with a
real host over the archived bytes of a PySCF run of closed-shell singlet O2
-- a reference that is unstable to spin symmetry breaking.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from chemsmart.agent._contracts import (
    TrustedArtifactRefV1,
    canonical_sha256,
    file_sha256,
)
from chemsmart.agent.driver import run_goal_loop
from chemsmart.agent.loop import ToolLoopRunner
from chemsmart.agent.runtime.alibaba import (
    Qwen38MaxConfigV1,
    Qwen38MaxToolSession,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

from .provider_fakes import _run_contracts
from .test_a_partial_delivery_ends_its_session import (
    _RESULT,
    _call,
    _o2r_turns,
    _turn,
)
from .test_the_goal_loop_recovers_or_returns import (
    _bundle_file,
    _envelope_file,
    _planning_session,
    _review_payload,
)

_RULE = "val-rks-stability/external_no_spin_instability"
_TASK = canonical_sha256("synthetic task")


def _stream_rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _artifact() -> TrustedArtifactRefV1:
    return TrustedArtifactRefV1(
        artifact_id=f"pyscf-result-{file_sha256(_RESULT)[:16]}",
        kind="pyscf_hdf5",
        sha256=file_sha256(_RESULT),
        size_bytes=_RESULT.stat().st_size,
        path=str(_RESULT),
        cli_value=str(_RESULT),
    )


def _run_turns(stream: Path, turns, *, session_id, scratch, workspace=None):
    """Drive a real host through the tool loop over ``turns`` into
    ``stream``; the turn factories take the registered artifact id."""

    artifact = _artifact()
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(stream, session_id=session_id),
        task_spec_sha256s=(_TASK,),
        approved_workspace=scratch / "approved",
        execute_analysis_only_plans=True,
        analysis_only_run_directory=scratch / f"analysis-{stream.parent.name}",
        analysis_only_workspace=scratch / "approved",
        # What a live session is given: the workspace its goal's recorded
        # runs live in, so a decision may cite what they minted.
        run_evidence_root=workspace,
    )
    host.artifacts[artifact.artifact_id] = artifact
    pending = iter(turns(artifact.artifact_id))
    config = Qwen38MaxConfigV1()
    session = Qwen38MaxToolSession(
        transport=lambda payload: next(pending)(payload),
        messages=[{"role": "user", "content": "Is the reference stable?"}],
        config=config,
    )
    envelope, request_context, network = _run_contracts(host, config)
    return ToolLoopRunner(host=host, event_store=host.event_store).run(
        session=session,
        envelope=envelope,
        request_context=request_context,
        provider_budget=network,
        should_stop=lambda: False,
    )


def _real_session(tmp_path, run_id, turns):
    """A goal's planning session, run for real in its own stream."""

    def step(workspace, _kwargs):
        stream = (
            workspace / ".chemsmart-agent" / "runs" / run_id / "events.jsonl"
        )
        result = _run_turns(
            stream,
            turns,
            session_id="protocol-session",
            scratch=tmp_path,
            workspace=workspace,
        )
        return SimpleNamespace(
            terminal_state=result.terminal_state,
            run_id=run_id,
            task_spec_sha256=_TASK,
            selected_execution_wave=(),
        )

    return step


def _goal(tmp_path, *, sessions, executes=(), goal_id="goal-o2r"):
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True, exist_ok=True)
    session_iter = iter(sessions)
    execute_iter = iter(executes)

    def plan_session(**kwargs):
        return next(session_iter)(workspace, kwargs)

    def resolve_review(**_kwargs):
        return ("d" * 64, _bundle_file(tmp_path))

    def execute_bundle(*, approval_file, workspace, run_directory):
        return next(execute_iter)(run_directory)

    return run_goal_loop(
        task="Is the restricted reference of singlet O2 stable?",
        workspace=workspace,
        execution_envelope_file=_envelope_file(tmp_path),
        goal_id=goal_id,
        granted_by="claude-researcher-q19-owner-delegated",
        max_revisions=2,
        plan_session=plan_session,
        resolve_review=resolve_review,
        execute_bundle=execute_bundle,
    )


def _completions(stream: Path):
    return [
        event["payload"]
        for event in _stream_rows(stream)
        if event["kind"] == "analysis_completion_evaluated"
    ]


def _o2r_stream(tmp_path) -> Path:
    return (
        tmp_path
        / "ws"
        / ".chemsmart-agent"
        / "runs"
        / "live-20260925T000000000000Z-q19-o2r"
        / "events.jsonl"
    )


def _o2r_goal(tmp_path, *, cite_verdict):
    return _goal(
        tmp_path,
        sessions=[
            _real_session(
                tmp_path,
                "live-20260925T000000000000Z-q19-o2r",
                lambda artifact_id: _o2r_turns(
                    artifact_id, cite_verdict=cite_verdict
                ),
            )
        ],
    )


@pytest.mark.capability("rule:wake.failed_validation_receipt_answers_verdict")
def test_a_criterion_the_session_answered_is_delivered_with_its_finding(
    tmp_path,
):
    result = _o2r_goal(tmp_path, cite_verdict=True)
    completions = _completions(_o2r_stream(tmp_path))
    # The executor's walk at plan time: the chain ran, the criterion
    # failed, and no decision existed yet, so the claims standing on it
    # are named -- the same answer the session's completion gives.
    walked = completions[0]
    assert walked["status"] == "partial"
    assert any(
        finding.startswith("analysis.claim_on_failed_criterion.")
        for finding in walked["record"]["findings"]
    )
    # The session evaluated the criterion again, over the same number,
    # and cited that second receipt. The finding was read: the session's
    # completion certifies the delivery and carries the verdict.
    certified = completions[-1]
    assert certified["status"] == "passed"
    assert any(
        item.startswith(f"failed_criterion:{_RULE}:answered:")
        for item in certified["anomaly_output_ids"]
    )
    assert [
        event["payload"]["terminal_state"]
        for event in _stream_rows(_o2r_stream(tmp_path))
        if event["kind"] == "runtime_terminated"
    ] == ["complete"]
    # The goal delivers the finding under the word that never hides one,
    # and the reason names the verdict, its number and the decision.
    assert result.settlement == "achieved_with_observations"
    assert any(
        f"failed_criterion:{_RULE}:answered" in r for r in result.reasons
    )
    assert any(
        _RULE in reason and "-0.0926" in reason and "cites" in reason
        for reason in result.reasons
    )


@pytest.mark.capability("rule:wake.failed_validation_receipt_answers_verdict")
def test_a_criterion_nobody_answered_holds_the_delivery_and_is_named(
    tmp_path,
):
    result = _o2r_goal(tmp_path, cite_verdict=False)
    certified = _completions(_o2r_stream(tmp_path))[-1]
    assert certified["status"] == "partial"
    assert any(
        item.startswith(f"failed_criterion:{_RULE}:unanswered:")
        for item in certified["anomaly_output_ids"]
    )
    assert result.settlement == "returned_to_human"
    # The reason says which finding the goal is waiting on, not only
    # that a gate did not pass.
    assert any(
        _RULE in reason and "no recorded decision cites" in reason
        for reason in result.reasons
    )


def _engine_prefix(tmp_path, target):
    """One validated engine node, recorded the way a run records it, in
    the session the chain below it then writes into."""

    from chemsmart.agent.execution import build_program_execution_receipt

    from .test_runtime_v2_launch_fence import _reserve

    build = tmp_path / "engine-build"
    store = RuntimeEventStore(
        build / "events.jsonl", session_id="protocol-session"
    )
    _, plan, _m, _a, invocation = _reserve(store, build)
    store.record_program_execution_receipt(
        turn_id="turn-1",
        workflow_id=plan.workflow_id,
        run_id="run.water-approval",
        receipt=build_program_execution_receipt(
            invocation,
            execution_state="engine_complete",
            exit_status=0,
            child_exit_status=0,
            engine_complete=True,
            validated=False,
            findings=(),
            started_at="2026-09-25T00:00:00+00:00",
            finished_at="2026-09-25T00:00:05+00:00",
        ),
    )
    target.mkdir(parents=True, exist_ok=True)
    (target / "events.jsonl").write_bytes(
        (build / "events.jsonl").read_bytes()
    )


def _doubted_and_unanswered(artifact_id):
    """o2r's acts, with a decision that doubts the extraction its claims
    stand on and does not cite the failed verdict."""

    turns = _o2r_turns(artifact_id, cite_verdict=False)

    def doubted(payload):
        results = [
            json.loads(message.get("content") or "{}").get("result")
            for message in payload["messages"]
            if message.get("role") == "tool"
        ]
        # The extraction, the verdict and the claims, as o2r's own
        # decision reads them.
        extraction, _verdict, claim_record = [
            result["receipt_sha256"]
            for result in results
            if isinstance(result, dict) and result.get("receipt_sha256")
        ][-3:]
        return _turn(
            4,
            "Recording the decision.",
            (
                _call(
                    8,
                    "record_scientific_decision",
                    {
                        "decision_id": "o2-rks-doubt",
                        "assumptions": ["the restricted reference"],
                        "method_rationale": "the task fixed the level",
                        "alternatives": ["a broken-symmetry solution"],
                        "uncertainties": ["whether this extraction holds"],
                        "diagnostics": ["the external eigenvalue"],
                        "stage_order": ["extract", "validate", "claim"],
                        "evidence_refs": [f"doubt:{extraction}"],
                        "postprocessing_receipt_sha256s": [claim_record],
                    },
                ),
            ),
        )

    return turns[:3] + [doubted] + turns[4:]


@pytest.mark.capability("rule:wake.failed_validation_receipt_answers_verdict")
def test_a_doubt_does_not_erase_the_criterion_a_claim_stands_under(tmp_path):
    """A completion names every finding it holds: the doubt branch used to
    rebind the findings, so a claim both doubted and standing on an
    unanswered criterion was named only as doubted."""

    stream = tmp_path / "doubt" / "events.jsonl"
    _run_turns(
        stream,
        _doubted_and_unanswered,
        session_id="protocol-session",
        scratch=tmp_path,
    )
    findings = _completions(stream)[-1]["record"]["findings"]
    assert any("claim_under_recorded_doubt" in item for item in findings)
    assert any("claim_on_failed_criterion" in item for item in findings)


def _decided_citing_only_the_extraction(artifact_id):
    """o2r's acts, with a decision that cites the extraction alone -- so
    the delivery is certified from its claims, not from the plan."""

    turns = _o2r_turns(artifact_id, cite_verdict=False)

    def decided(payload):
        results = [
            json.loads(message.get("content") or "{}").get("result")
            for message in payload["messages"]
            if message.get("role") == "tool"
        ]
        extraction = [
            result["receipt_sha256"]
            for result in results
            if isinstance(result, dict) and result.get("receipt_sha256")
        ][-3]
        return _turn(
            4,
            "Recording the decision.",
            (
                _call(
                    8,
                    "record_scientific_decision",
                    {
                        "decision_id": "o2-rks-read",
                        "assumptions": ["the restricted reference"],
                        "method_rationale": "the task fixed the level",
                        "alternatives": ["a broken-symmetry solution"],
                        "uncertainties": ["SCF convergence precision"],
                        "diagnostics": ["the external eigenvalue"],
                        "stage_order": ["extract", "validate", "claim"],
                        "evidence_refs": [],
                        "postprocessing_receipt_sha256s": [extraction],
                    },
                ),
            ),
        )

    return turns[:3] + [decided] + turns[4:]


@pytest.mark.capability("rule:wake.failed_validation_receipt_answers_verdict")
def test_a_delivery_certified_from_its_claims_reads_the_criterion_too(
    tmp_path,
):
    """The certificate for a delivery made from registered results was
    minted passed over claims whose own stream held a failed criterion
    nobody had cited; it now names them as every other completion does."""

    stream = tmp_path / "claims-only" / "events.jsonl"
    result = _run_turns(
        stream,
        _decided_citing_only_the_extraction,
        session_id="protocol-session",
        scratch=tmp_path,
    )
    certified = _completions(stream)[-1]
    assert certified["status"] == "partial"
    assert any(
        item.startswith("analysis.claim_on_failed_criterion.")
        for item in certified["record"]["findings"]
    )
    assert result.terminal_state != "complete"


def _run_with_the_failed_criterion(tmp_path):
    """Cycle 1's run: an engine node, then the approved chain over the
    registered O2 result -- the criterion fails, the energy is claimed,
    and a run's stream holds no decision."""

    def step(run_directory):
        _engine_prefix(tmp_path, run_directory)
        turns = lambda artifact_id: [  # noqa: E731
            turn
            for index, turn in enumerate(
                _o2r_turns(artifact_id, cite_verdict=False)
            )
            if index != 3
        ]
        _run_turns(
            run_directory / "events.jsonl",
            turns,
            session_id="protocol-session",
            scratch=tmp_path,
        )
        return SimpleNamespace(status="completed", analysis_status="completed")

    return step


def _claim_again(artifact_id, *, cite_run=None):
    """The woken cycle: read the energy again from the same result and
    claim it -- without evaluating the criterion again. ``cite_run`` names
    the run stream whose failed receipt the decision cites, the route the
    wake prescribes."""

    def replies(payload):
        return [
            json.loads(message["content"])["result"]["receipt_sha256"]
            for message in payload["messages"]
            if message.get("role") == "tool"
        ]

    def extracted(payload):
        return _call(
            1,
            "extract_result_quantities",
            {
                "program": "pyscf",
                "artifact_id": artifact_id,
                "selectors": [
                    {"quantity_id": "ref-energy", "selector": "energy"}
                ],
            },
        )

    def claimed(payload):
        return _call(
            2,
            "record_analysis_claims",
            {
                "claims": [
                    {
                        "claim_id": "ref-energy-hartree",
                        "receipt_sha256": replies(payload)[-1],
                        "quantity_id": "ref-energy",
                        "display_unit": "hartree",
                    }
                ]
            },
        )

    def decided(payload):
        cited = list(replies(payload)[-2:])
        if cite_run is not None:
            cited += [
                row["payload"]["receipt_sha256"]
                for row in _stream_rows(cite_run())
                if row["kind"] == "scientific_validation_evaluated"
                and not row["payload"]["all_rules_passed"]
            ][-1:]
        return _call(
            3,
            "record_scientific_decision",
            {
                "decision_id": "o2-rks-energy",
                "assumptions": ["the restricted reference at the geometry"],
                "method_rationale": "the task fixed B3LYP/def2-SVP",
                "alternatives": ["a broken-symmetry solution, not asked"],
                "uncertainties": ["SCF convergence precision"],
                "diagnostics": ["the energy is the unstable reference's"],
                "stage_order": ["extract", "claim"],
                "evidence_refs": [],
                "postprocessing_receipt_sha256s": cited,
            },
        )

    return [
        lambda payload: _turn(1, "Reading the energy.", (extracted(payload),)),
        lambda payload: _turn(2, "Claiming it.", (claimed(payload),)),
        lambda payload: _turn(3, "Deciding.", (decided(payload),)),
        lambda payload: _turn(4, "The energy is claimed by its id."),
    ]


def _run_then_claim(tmp_path, *, cite):
    goal_id = "goal-o2r-run"
    run_stream = (
        tmp_path
        / "ws"
        / ".chemsmart-agent"
        / "goals"
        / goal_id
        / "runs"
        / "cycle-1"
        / "events.jsonl"
    )
    return _goal(
        tmp_path,
        goal_id=goal_id,
        sessions=[
            _planning_session(
                "live-20260925T000000000000Z-q19-plan",
                review=_review_payload(),
            ),
            _real_session(
                tmp_path,
                "live-20260925T010000000000Z-q19-woken",
                lambda artifact_id: _claim_again(
                    artifact_id,
                    cite_run=(lambda: run_stream) if cite else None,
                ),
            ),
        ],
        executes=[_run_with_the_failed_criterion(tmp_path)],
    )


@pytest.mark.capability("rule:wake.failed_validation_receipt_answers_verdict")
def test_a_woken_decision_may_cite_the_failed_receipt_its_run_minted(
    tmp_path,
):
    """The wake tells a session to cite the failed validation receipt, and
    after a run that receipt is the run's. The host accepted a recorded
    run's receipts only when the stream spelled its JSON with a space the
    event store never writes, so the prescribed citation was refused."""

    _run_then_claim(tmp_path, cite=True)
    woken = (
        tmp_path
        / "ws"
        / ".chemsmart-agent"
        / "runs"
        / "live-20260925T010000000000Z-q19-woken"
        / "events.jsonl"
    )
    kinds = [row["kind"] for row in _stream_rows(woken)]
    assert "scientific_decision_recorded" in kinds
    assert not [
        row
        for row in _stream_rows(woken)
        if row["kind"] == "tool_failed"
        and "receipt_is_one_the_host_minted" in json.dumps(row)
    ]
