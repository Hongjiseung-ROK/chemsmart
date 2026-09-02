"""More executable nodes than engine calls remain is refused at plan time.

The review builder refused this at session end, into a log line, after
a woken session had planned twelve engine nodes against five remaining
calls and the frontier had called the plan approvable. The plan alone
proves the count, so the plan is where it is refused, against the
smaller of the envelope and what the goal has left.
"""

import pytest
import yaml

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.execution_envelope import (
    load_bounded_execution_envelope,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from tests.agent.neutral_workflow_fixture import (
    build_neutral_workflow_fixture,
)


def _envelope(tmp_path, *, max_engine_calls):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "envelope.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "chemsmart.bounded-execution-envelope.v1",
                "mode": "bounded-local",
                "allowed_program_engines": {"orca": ["cpu"]},
                "resources": {
                    "execution_target": "run",
                    "cores": 2,
                    "memory_gb": 8,
                    "gpu_count": 0,
                    "scratch_policy": "server",
                    "node_timeout_seconds": 600,
                },
                "episode_wall_time_seconds": 3600,
                "postprocess_reserve_seconds": 60,
                "max_engine_calls": max_engine_calls,
                "scratch_root": str(tmp_path / "scratch"),
            }
        ),
        encoding="utf-8",
    )
    return load_bounded_execution_envelope(path)


def _plan(tmp_path, **host_extra):
    fixture = build_neutral_workflow_fixture(tmp_path / "fixture")
    store = RuntimeEventStore(
        tmp_path / "events" / "runtime.jsonl", session_id="session"
    )
    host = CommandCompiledToolHostV1(
        event_store=store,
        task_spec_sha256s=(fixture.public_context.task_spec_sha256,),
        approved_workspace=tmp_path / "preview",
        **fixture.host_inputs,
        **host_extra,
    )
    action = next(
        item
        for item in fixture.public_context.next_actions
        if item.tool_name == "plan_scientific_workflow"
    )
    fields = dict(action.fields)
    assert len(fields["calculation_nodes"]) == 2
    return host.dispatch(
        turn_id="turn-1",
        tool_name="plan_scientific_workflow",
        arguments=fields,
    )


@pytest.mark.capability("tool:plan_scientific_workflow")
def test_the_envelope_bounds_a_first_cycle(tmp_path):
    envelope = _envelope(tmp_path, max_engine_calls=1)
    with pytest.raises(ContractError, match="2 executable nodes for 1"):
        _plan(
            tmp_path / "a",
            execution_resources=envelope.resources,
            bounded_execution_envelope=envelope,
        )
    envelope = _envelope(tmp_path / "b", max_engine_calls=2)
    assert (
        _plan(
            tmp_path / "b",
            execution_resources=envelope.resources,
            bounded_execution_envelope=envelope,
        )
        is not None
    )


@pytest.mark.capability("tool:plan_scientific_workflow")
def test_what_the_goal_has_left_bounds_a_woken_cycle(tmp_path):
    with pytest.raises(ContractError, match="2 executable nodes for 1"):
        _plan(tmp_path / "a", engine_calls_remaining=1)
    assert _plan(tmp_path / "b", engine_calls_remaining=2) is not None
