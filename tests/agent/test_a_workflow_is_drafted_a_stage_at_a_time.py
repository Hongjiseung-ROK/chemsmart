"""A workflow is built stage by stage and checked as a whole, once.

The aggregate `plan_scientific_workflow` asked for calculation nodes,
producer edges, extraction intents, thermochemistry conditions,
expression DAGs, validation rules, claim intents and required outputs in
one payload, so a rejected call recorded nothing and every repair
resubmitted the DAG. Constructors build a host-owned draft; the
finaliser is the same handler it always was, fed by the host.

The property everything else rests on: a workflow drafted stage by stage
and the same nodes sent in one payload are the same workflow, byte for
byte. Resume and the plan-reproduction rule key on those digests.
"""

from __future__ import annotations

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.exposure import build_exposure
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.scientific_toolchain import ANALYSIS_INTENT_KINDS
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from tests.agent.neutral_workflow_fixture import (
    build_neutral_workflow_fixture,
)

pytestmark = pytest.mark.capability("tool:plan_scientific_workflow")


def _host(tmp_path, *, exposure=True):
    fixture = build_neutral_workflow_fixture(tmp_path / "fixture")
    store = RuntimeEventStore(
        tmp_path / "events" / "runtime.jsonl", session_id="session"
    )
    host = CommandCompiledToolHostV1(
        event_store=store,
        task_spec_sha256s=(fixture.public_context.task_spec_sha256,),
        approved_workspace=tmp_path / "preview",
        run_evidence_root=tmp_path / "ws",
        exposure=build_exposure("eager") if exposure else None,
        **fixture.host_inputs,
    )
    payload = dict(
        next(
            item
            for item in fixture.public_context.next_actions
            if item.tool_name == "plan_scientific_workflow"
        ).fields
    )
    return host, store, payload


def _digests(result):
    """The three whole-plan digests approval and resume key on."""

    plan = result["scientific_toolchain_plan"]
    command = result["calculation_plan"]
    return (
        plan.plan_sha256,
        command["workflow_draft"].draft_sha256,
        command["scientific_workflow_plan"].plan_sha256,
    )


def test_the_same_nodes_give_the_same_plan_whichever_surface_authored_them(
    tmp_path,
):
    """If this were not true the round would be a blocker, not a design.

    ``chemsmart agent wake`` resumes from a recorded plan digest and
    ``plan_reproduction_rule`` requires a resumed session to reproduce
    the approved one exactly, so a decomposed surface that produced a
    different digest for the same science would break resume.
    """

    aggregate_host, _, payload = _host(tmp_path / "aggregate")
    aggregate = aggregate_host._plan_scientific_workflow_from_values(
        "turn-1", payload
    )

    drafted_host, _, _ = _host(tmp_path / "drafted")
    drafted_host.dispatch(
        turn_id="turn-1",
        tool_name="plan_calculation_stages",
        arguments={
            "workflow_id": payload["workflow_id"],
            "stages": payload["calculation_nodes"],
        },
    )
    # Both sides at the same level: the constructors went through the
    # public dispatch above, and these two return the canonical objects
    # whose digests approval, materialisation and resume key on.
    drafted = drafted_host._plan_scientific_workflow(
        "turn-1",
        {
            "plan_id": payload["plan_id"],
            "workflow_id": payload["workflow_id"],
            "task_spec_id": payload["task_spec_id"],
            "required_output_ids": payload["required_output_ids"],
        },
    )

    assert _digests(drafted) == _digests(aggregate)


def test_stages_accumulate_without_resubmission(tmp_path):
    """Three calls, one draft, and the earlier stages are the host's."""

    host, store, payload = _host(tmp_path)
    stages = payload["calculation_nodes"]
    assert len(stages) >= 2

    first = host.dispatch(
        turn_id="turn-1",
        tool_name="plan_calculation_stages",
        arguments={"workflow_id": "w", "stages": stages[:1]},
    )["result"]
    assert first["calculation_node_ids"] == [stages[0]["node_id"]]

    second = host.dispatch(
        turn_id="turn-1",
        tool_name="plan_calculation_stages",
        arguments={"workflow_id": "w", "stages": stages[1:]},
    )["result"]
    assert second["calculation_node_ids"] == [
        item["node_id"] for item in stages
    ]
    assert [item["action"] for item in second["revisions"]] == [
        "added",
        "added",
    ]
    assert (
        second["revisions"][1]["parent_draft_sha256"] == first["draft_sha256"]
    )
    assert second["draft_sha256"] != first["draft_sha256"]

    revised = [
        event
        for event in store.read_events()
        if event.kind == EventKind.PLAN_DRAFT_REVISED.value
    ]
    assert [item.payload["constructor"] for item in revised] == [
        "plan_calculation_stages",
        "plan_calculation_stages",
    ]


def test_reissuing_a_node_id_replaces_that_stage_and_nothing_else(tmp_path):
    """Repair costs one stage, which is what the draft is for."""

    host, _, payload = _host(tmp_path)
    stages = payload["calculation_nodes"]
    host.dispatch(
        turn_id="turn-1",
        tool_name="plan_calculation_stages",
        arguments={"workflow_id": "w", "stages": stages},
    )
    repaired = {**stages[0], "project_role": "opt"}
    reply = host.dispatch(
        turn_id="turn-1",
        tool_name="plan_calculation_stages",
        arguments={"workflow_id": "w", "stages": [repaired]},
    )["result"]

    assert reply["calculation_node_ids"] == [
        item["node_id"] for item in stages
    ], "a replacement keeps its position"
    assert reply["revisions"][-1]["action"] == "replaced"
    assert reply["revisions"][-1]["node_ids"] == [stages[0]["node_id"]]


def test_a_stage_leaves_a_draft_only_by_being_named(tmp_path):
    host, _, payload = _host(tmp_path)
    stages = payload["calculation_nodes"]
    host.dispatch(
        turn_id="turn-1",
        tool_name="plan_calculation_stages",
        arguments={"workflow_id": "w", "stages": stages},
    )
    reply = host.dispatch(
        turn_id="turn-1",
        tool_name="withdraw_planned_stage",
        arguments={"workflow_id": "w", "node_id": stages[-1]["node_id"]},
    )["result"]
    assert reply["calculation_node_ids"] == [
        item["node_id"] for item in stages[:-1]
    ]
    assert reply["revisions"][-1]["action"] == "removed"

    with pytest.raises(ContractError, match="is not a stage of this draft"):
        host.dispatch(
            turn_id="turn-1",
            tool_name="withdraw_planned_stage",
            arguments={"workflow_id": "w", "node_id": "never-drafted"},
        )


def test_a_local_gate_refuses_at_the_constructor_and_stores_nothing(
    tmp_path,
):
    """A stage the node-local gate refuses never enters the draft."""

    host, _, _ = _host(tmp_path)
    with pytest.raises(ContractError):
        host.dispatch(
            turn_id="turn-1",
            tool_name="plan_thermochemistry",
            arguments={
                "workflow_id": "w",
                "stages": [
                    {
                        "node_id": "thermo",
                        "dependencies": [],
                        "inputs": [],
                        "outputs": [],  # refused: at least one output
                        "support_state": "planned",
                        "blocked_reason": "",
                        "temperature_k": 298.15,
                        "pressure_atm": 1.0,
                    }
                ],
            },
        )
    draft = host.dispatch(
        turn_id="turn-1",
        tool_name="inspect_workflow_draft",
        arguments={"workflow_id": "w"},
    )["result"]
    assert draft["analysis_node_ids"] == []
    assert draft["revisions"] == []


def test_a_global_gate_refuses_at_the_finaliser_and_the_draft_survives(
    tmp_path,
):
    """The refusal names the node; the repair re-issues that one stage.

    A required output nobody produces is a whole-workflow fact: no stage
    can know it, and it is exactly the class of refusal that used to
    cost a resubmission of the entire DAG.
    """

    host, _, payload = _host(tmp_path)
    host.dispatch(
        turn_id="turn-1",
        tool_name="plan_calculation_stages",
        arguments={
            "workflow_id": payload["workflow_id"],
            "stages": payload["calculation_nodes"],
        },
    )
    with pytest.raises(ContractError):
        host.dispatch(
            turn_id="turn-1",
            tool_name="plan_scientific_workflow",
            arguments={
                "plan_id": payload["plan_id"],
                "workflow_id": payload["workflow_id"],
                "task_spec_id": payload["task_spec_id"],
                "required_output_ids": ["nobody-produces-this"],
            },
        )
    survived = host.dispatch(
        turn_id="turn-1",
        tool_name="inspect_workflow_draft",
        arguments={"workflow_id": payload["workflow_id"]},
    )["result"]
    assert survived["calculation_node_ids"] == [
        item["node_id"] for item in payload["calculation_nodes"]
    ]
    assert not survived["closed_plan_sha256"]

    # And the same draft finalises once the required output is dropped.
    host.dispatch(
        turn_id="turn-1",
        tool_name="plan_scientific_workflow",
        arguments={
            "plan_id": payload["plan_id"],
            "workflow_id": payload["workflow_id"],
            "task_spec_id": payload["task_spec_id"],
            "required_output_ids": [],
        },
    )


def test_a_finalised_workflow_is_amended_not_redrafted(tmp_path):
    """After finalise the draft is closed and today's rules apply.

    A reviewed plan is revised through ``amend_scientific_workflow``,
    which refuses a science change as a new workflow needing its own
    review. Nothing here loosens that.
    """

    host, _, payload = _host(tmp_path)
    host.dispatch(
        turn_id="turn-1",
        tool_name="plan_calculation_stages",
        arguments={
            "workflow_id": payload["workflow_id"],
            "stages": payload["calculation_nodes"],
        },
    )
    host.dispatch(
        turn_id="turn-1",
        tool_name="plan_scientific_workflow",
        arguments={
            "plan_id": payload["plan_id"],
            "workflow_id": payload["workflow_id"],
            "task_spec_id": payload["task_spec_id"],
            "required_output_ids": [],
        },
    )
    with pytest.raises(ContractError, match="amend_scientific_workflow"):
        host.dispatch(
            turn_id="turn-1",
            tool_name="plan_calculation_stages",
            arguments={
                "workflow_id": payload["workflow_id"],
                "stages": payload["calculation_nodes"][:1],
            },
        )


def test_finalising_an_empty_draft_says_how_to_fill_it(tmp_path):
    host, _, payload = _host(tmp_path)
    with pytest.raises(ContractError, match="plan_calculation_stages"):
        host.dispatch(
            turn_id="turn-1",
            tool_name="plan_scientific_workflow",
            arguments={
                "plan_id": payload["plan_id"],
                "workflow_id": "empty",
                "required_output_ids": [],
            },
        )


def _minimal_stage(kind: str) -> dict:
    """The smallest payload of one kind the local gate accepts."""

    stage = {
        "node_id": f"n-{kind.replace('_', '-')}",
        "dependencies": [],
        "inputs": [
            {
                "input_id": "x",
                "source_kind": "analysis_output",
                "producer_node_id": "upstream",
                "producer_output_id": "y",
            }
        ],
        "outputs": [
            {"output_id": "x", "quantity_kind": "energy", "unit": "hartree"}
        ],
        "support_state": "planned",
        "blocked_reason": "",
    }
    if kind == "result_extraction":
        stage["selectors"] = [{"quantity_id": "x", "selector": "total_energy"}]
        stage["inputs"] = [
            {
                "input_id": "x",
                "source_kind": "program_output",
                "producer_node_id": "upstream",
                "producer_output_id": "y",
            }
        ]
    if kind == "thermochemistry":
        stage["temperature_k"] = 298.15
        stage["pressure_atm"] = 1.0
        stage["outputs"] = [
            {
                "output_id": "x",
                "quantity_kind": "gibbs_free_energy",
                "unit": "hartree",
            }
        ]
        stage["inputs"] = [
            {
                "input_id": "x",
                "source_kind": "program_output",
                "producer_node_id": "upstream",
                "producer_output_id": "y",
            }
        ]
    if kind == "quantity_expression":
        stage["expression_nodes"] = [
            {"node_id": "x", "operation": "ref", "reference": "x"}
        ]
        stage["expression_output_node_ids"] = ["x"]
    if kind == "scientific_validation":
        stage["outputs"] = [
            {"output_id": "x", "quantity_kind": "verdict", "unit": "1"}
        ]
        stage["validation_rules"] = [
            {
                "rule_id": "r",
                "predicate": "integer_equals",
                "input_ids": ["x"],
                "expected_count": 1,
            }
        ]
    return stage


@pytest.mark.parametrize("kind", list(ANALYSIS_INTENT_KINDS))
def test_every_projected_field_is_admitted_and_no_other_is(kind, tmp_path):
    """The schema projection and the node-local gate cannot drift.

    ``analysis_intent_fields`` declares what one kind may carry and
    ``AnalysisNodeIntentV1.__post_init__`` is the authority. This drives
    both directions against the gate itself: every field the projection
    offers is admitted for that kind, and every field it withholds is
    refused. A projection that quietly offered a field the gate forbids
    would be a schema promising something no payload can use.
    """

    from chemsmart.agent.scientific_toolchain import (
        ANALYSIS_INTENT_KIND_FIELDS,
        analysis_intent_fields,
    )
    from chemsmart.agent.tool_specs import _analysis_intent_node_schema

    host, _, _ = _host(tmp_path)
    offered = set(_analysis_intent_node_schema(kind=kind)["properties"])
    assert offered == set(analysis_intent_fields(kind))

    accepted = _minimal_stage(kind)
    host._analysis_intent_from_payload({**accepted, "analysis_kind": kind})

    # Every field this kind does not own is refused by the gate, so the
    # projection is right to withhold it.
    for other, fields in ANALYSIS_INTENT_KIND_FIELDS.items():
        if other == kind:
            continue
        for field in fields:
            if field in offered:
                continue  # two kinds may share one, e.g. artifact_id
            probe = {**accepted, "analysis_kind": kind}
            probe[field] = _FORBIDDEN_PROBE[field]
            with pytest.raises(ContractError):
                host._analysis_intent_from_payload(probe)


#: A value for each per-kind field that is unmistakably "present", so a
#: refusal is about the field belonging to another kind and not about
#: the value being malformed.
_FORBIDDEN_PROBE = {
    "artifact_id": "registered-result",
    "selectors": [{"quantity_id": "q", "selector": "total_energy"}],
    "temperature_k": 298.15,
    "pressure_atm": 1.0,
    "concentration_mol_l": 1.0,
    "entropy_method": "quasi_rrho",
    "entropy_cutoff_cm1": 100.0,
    "enthalpy_cutoff_cm1": 100.0,
    "alpha": 3,
    "use_weighted_mass": True,
    "frequency_scale_factor": 0.99,
    "expression_nodes": [
        {"node_id": "e", "operation": "ref", "reference": "x"}
    ],
    "expression_output_node_ids": ["e"],
    "validation_rules": [
        {
            "rule_id": "r",
            "predicate": "integer_equals",
            "input_ids": ["x"],
            "expected_count": 1,
        }
    ],
}


def test_the_initial_surface_carries_no_node_schema_at_all():
    """What a first request costs, measured against what it replaced.

    The aggregate planner was 27,920 bytes of the 45,150 a first request
    carried -- 62% of it -- and deferring it behind search would have
    made search a formality, because a model had to load all of it to
    plan anything. The finaliser is 3,488 bytes and carries no node
    array; the node schemas are constructors, found one at a time.
    """

    import json as _json

    from chemsmart.agent.catalogue import build_tool_catalogue
    from chemsmart.agent.exposure import build_exposure

    initial = list(build_exposure("host_search").tool_definitions())
    text = _json.dumps(initial)
    assert len(text) < 25_000, len(text)

    finaliser = next(
        item
        for item in initial
        if item["function"]["name"] == "plan_scientific_workflow"
    )
    properties = finaliser["function"]["parameters"]["properties"]
    assert set(properties) == {
        "plan_id",
        "workflow_id",
        "task_spec_id",
        "required_output_ids",
    }
    assert "expression_nodes" not in text
    assert "validation_rules" not in text
    assert "temperature_k" not in text

    # And every constructor is in the catalogue, deferred and findable.
    catalogue = build_tool_catalogue()
    for kind in ANALYSIS_INTENT_KINDS:
        entry = catalogue.entry(f"plan_{kind}")
        assert entry is not None and entry.loading == "deferred"


def test_one_analysis_kind_loads_only_its_own_schema(tmp_path):
    """The property this leg exists for.

    A task that needs thermochemistry must not read the expression-node
    schema, the validation-rule schema or the selector schema to plan
    it. Under the aggregate tool it read all of them, in one payload.
    """

    import json as _json

    from chemsmart.agent.catalogue import SEARCH_TOOL_NAME
    from chemsmart.agent.exposure import build_exposure
    from chemsmart.agent.runtime.event_store import RuntimeEventStore

    store = RuntimeEventStore(
        tmp_path / "events.jsonl", session_id="thermo-session"
    )
    host = CommandCompiledToolHostV1(
        event_store=store, exposure=build_exposure("host_search")
    )
    host.dispatch(
        turn_id="t1",
        tool_name=SEARCH_TOOL_NAME,
        arguments={
            "query": (
                "plan a Gibbs free energy from frequencies at a "
                "temperature and pressure"
            )
        },
    )
    # The search itself loaded it: the floor keeps the head of the
    # ranking, and a thermochemistry query ranks its constructor first.
    assert host.exposure.is_available("plan_thermochemistry")

    visible = _json.dumps(list(host.exposure.tool_definitions()))
    assert "temperature_k" in visible
    for absent in (
        "plan_quantity_expression",
        "plan_scientific_validation",
        "plan_result_extraction",
        "plan_claim_rendering",
    ):
        assert not host.exposure.is_available(absent), absent


def test_an_unfinalised_draft_never_becomes_a_workflow(tmp_path):
    """A draft is not a plan, and nothing downstream can read it as one.

    It holds no canonical object, so there is nothing for review,
    approval, materialisation or resume to key on. A session that ends
    mid-draft leaves its stages in the event stream as revisions and
    leaves no workflow behind; the next session drafts again.
    """

    host, store, payload = _host(tmp_path)
    host.dispatch(
        turn_id="turn-1",
        tool_name="plan_calculation_stages",
        arguments={
            "workflow_id": payload["workflow_id"],
            "stages": payload["calculation_nodes"],
        },
    )
    assert not host.scientific_toolchain_plans
    assert not host.workflow_drafts
    draft = host.workflow_plan_drafts[payload["workflow_id"]]
    assert not draft.closed_plan_sha256

    # The revisions are in the stream, so a reader can say what the
    # session had drafted when it stopped.
    revised = [
        event
        for event in store.read_events()
        if event.kind == EventKind.PLAN_DRAFT_REVISED.value
    ]
    assert revised and revised[-1].payload["calculation_node_ids"]


def test_discovery_and_drafting_move_neither_review_nor_execution(tmp_path):
    """Constructors grant nothing. They are the same claim as leg one."""

    from chemsmart.agent.tool_specs import (
        build_approved_execution_tool_surface,
    )

    before = build_approved_execution_tool_surface().tool_schema_sha256
    host, _, payload = _host(tmp_path)
    host.dispatch(
        turn_id="turn-1",
        tool_name="plan_calculation_stages",
        arguments={
            "workflow_id": payload["workflow_id"],
            "stages": payload["calculation_nodes"],
        },
    )
    assert build_approved_execution_tool_surface().tool_schema_sha256 == (
        before
    )
    assert host.workflow_execution_approval is None
