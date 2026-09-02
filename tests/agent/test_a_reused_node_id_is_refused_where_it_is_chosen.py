"""A node id that names a workspace holding outputs is refused at plan time.

Every node runs in ``<workspace>/nodes/<node_id>`` and the launch guard
never overwrites evidence. A revision that reused a failed node's id
passed admission and met that guard only at launch, after the one-shot
bundle was spent; the plan is where the id is chosen, so the plan is
where the refusal names the route.
"""

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from tests.agent.neutral_workflow_fixture import (
    build_neutral_workflow_fixture,
)


def _plan(tmp_path, *, occupied: bool):
    fixture = build_neutral_workflow_fixture(tmp_path / "fixture")
    workspace = tmp_path / "ws"
    if occupied:
        node_dir = workspace / "nodes" / "node.hess"
        node_dir.mkdir(parents=True)
        (node_dir / "earlier.out").write_text("evidence\n")
    store = RuntimeEventStore(
        tmp_path / "events" / "runtime.jsonl", session_id="session"
    )
    host = CommandCompiledToolHostV1(
        event_store=store,
        task_spec_sha256s=(fixture.public_context.task_spec_sha256,),
        approved_workspace=tmp_path / "preview",
        run_evidence_root=workspace,
        **fixture.host_inputs,
    )
    action = next(
        item
        for item in fixture.public_context.next_actions
        if item.tool_name == "plan_scientific_workflow"
    )
    return host.dispatch(
        turn_id="turn-1",
        tool_name="plan_scientific_workflow",
        arguments=dict(action.fields),
    )


@pytest.mark.capability("tool:plan_scientific_workflow")
def test_a_node_id_whose_workspace_holds_outputs_is_refused(tmp_path):
    with pytest.raises(ContractError, match="already holds outputs"):
        _plan(tmp_path, occupied=True)
    assert _plan(tmp_path / "fresh", occupied=False) is not None
