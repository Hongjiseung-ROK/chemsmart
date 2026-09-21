"""A plan names a stage with the CLI's word; a reader is keyed on the word
a finished log says it is. Where a hub job writes results under other
words -- ChemSmart runs one Gaussian ``irc`` as a forward and a reverse
native input, and each log's route says ``ircf`` or ``ircr`` -- the two
never met, so a Gaussian IRC was a stage that could be previewed and then
neither read nor reused: the plan-time selector gate refused any
extraction that named it as producer, and no geometry edge could leave
the node although both branch declarations carry ``reached_positions``.
The reader states the correspondence and the consumers ask it.
"""

import pytest

from chemsmart.agent.execution import _ends_on_one_reached_structure
from chemsmart.agent.scientific_toolchain import (
    AnalysisInputIntentV1,
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    AnalysisSelectorIntentV1,
    ScientificToolchainContractError,
    build_scientific_toolchain_plan,
)
from chemsmart.agent.workflows import (
    ArtifactInputIntentV1,
    ArtifactOutputIntentV1,
    CommandNodeIntentV1,
)
from chemsmart.analysis.result_readers import RESULT_READERS, reader_for

pytestmark = pytest.mark.capability("selector:*")


def _calculation(program, jobtype):
    return CommandNodeIntentV1(
        node_id="walk",
        program=program,
        jobtype=jobtype,
        project_role="r",
        dependencies=(),
        inputs=(
            ArtifactInputIntentV1(
                binding_id="geometry",
                artifact_class="geometry_xyz",
                artifact_id="saddle",
                producer_node_id="",
                producer_output_id="",
            ),
        ),
        expected_outputs=(
            ArtifactOutputIntentV1(
                output_id="walk-out", artifact_class=f"{program}_output"
            ),
        ),
        unresolved_fields=(),
    )


def _extraction(selector, quantity_kind, unit):
    return AnalysisNodeIntentV1(
        node_id="read-the-walk",
        analysis_kind="result_extraction",
        dependencies=("walk",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="raw",
                source_kind="program_output",
                producer_node_id="walk",
                producer_output_id="walk-out",
            ),
        ),
        selectors=(
            AnalysisSelectorIntentV1(quantity_id="q", selector=selector),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="q", quantity_kind=quantity_kind, unit=unit
            ),
        ),
        expression_nodes=(),
        expression_output_node_ids=(),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )


def _plan(program, jobtype, selector, quantity_kind, unit):
    return build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(_calculation(program, jobtype),),
        calculation_observables={"walk": ("q",)},
        analysis_nodes=(_extraction(selector, quantity_kind, unit),),
        required_output_ids=("q",),
    )


def test_a_stage_is_its_own_result_word_unless_a_reader_says_otherwise():
    """The correspondence is a declaration, not a rename.

    Every job type a reader declares still answers to itself, so nothing
    a program already reads changes meaning because another program's
    job writes its results under two words.
    """

    for _program, reader in sorted(RESULT_READERS.items()):
        for jobtype, selectors in reader.jobtype_selectors:
            assert reader.result_jobtypes_for_stage(jobtype) == (jobtype,)
            assert set(reader.selectors_for_stage(jobtype)) == set(selectors)
    # A stage no reader declares stays unknown rather than becoming empty
    # coverage: ``link`` is previewable and has no reader at all.
    assert reader_for("gaussian").selectors_for_stage("link") is None


def test_a_gaussian_irc_stage_is_read_under_the_branches_it_writes():
    """The stage promises what every branch it can write declares."""

    reader = reader_for("gaussian")
    assert reader.result_jobtypes_for_stage("irc") == ("ircf", "ircr")
    stage = set(reader.selectors_for_stage("irc"))
    forward = set(reader.selectors_for_jobtype("ircf"))
    reverse = set(reader.selectors_for_jobtype("ircr"))
    assert stage == forward & reverse
    # What the walk establishes: where it ended, and whether the molecular
    # graph there differs from the saddle it was handed.
    assert {
        "reached_positions",
        "trajectory_connectivity_changed",
        "trajectory_end_positions",
        "trajectory_start_positions",
    } <= stage
    # The bare word stays undeclared: a route that names no direction is
    # Gaussian's own both-direction job, one log holding two legs, and
    # that log has not been audited.
    assert reader.selectors_for_jobtype("irc") is None


def test_a_stage_that_writes_several_results_is_no_producer():
    """What the plan admits, the walk can carry.

    The host binds a producer node's result by node id and result kind,
    both where a geometry travels and where an extraction reads. A stage
    whose job writes more than one such result therefore has no "the"
    result, and admitting one while the plan is built would move the
    refusal to after the engines had finished -- for a reaction path, the
    most expensive job in the workflow.

    Which end of a path travels is a statement the displayed plan has to
    make, and a plan cannot yet make it per node: ``direction`` reaches
    the route through the project section, but it is not a field of
    ``CommandNodeIntentV1``, so a plan that has not fixed one expresses a
    Gaussian IRC that walks both ways and writes two logs.
    """

    for _program, reader in sorted(RESULT_READERS.items()):
        for stage, _selectors in reader.jobtype_selectors:
            if _ends_on_one_reached_structure(_program, stage):
                assert len(reader.result_jobtypes_for_stage(stage)) == 1
    assert reader_for("gaussian").result_jobtypes_for_stage("irc") == (
        "ircf",
        "ircr",
    )
    assert not _ends_on_one_reached_structure("gaussian", "irc")
    with pytest.raises(ScientificToolchainContractError) as refusal:
        _plan(
            "gaussian", "irc", "trajectory_connectivity_changed", "count", "1"
        )
    assert "ircf" in str(refusal.value) and "ircr" in str(refusal.value)


def test_a_path_that_reaches_one_structure_may_hand_it_on():
    """A producer edge follows the declaration, not the program.

    ORCA walks one direction per node, so its IRC is single-resulted --
    and still hands nothing on, because its log prints only where the
    path started and its reader declares no reached structure. The two
    reasons a node may not be a producer are different facts and the
    predicate holds both.
    """

    orca = reader_for("orca")
    assert orca.result_jobtypes_for_stage("irc") == ("irc",)
    assert "reached_positions" not in orca.selectors_for_jobtype("irc")
    assert not _ends_on_one_reached_structure("orca", "irc")
    assert _ends_on_one_reached_structure("gaussian", "ts")
    assert _ends_on_one_reached_structure("gaussian", "opt")


def test_an_empty_appended_field_keeps_the_record_it_had():
    """A cell that states nothing new keeps the digest evidence cites.

    ``result_jobtypes`` was appended to a v1 record whose receipts are
    already quoted as the evidence behind recorded runs. Carrying it into
    the canonical body unconditionally moved the receipt digest of every
    cell of every program -- measured 38 of 38 against the frozen base --
    which is a track reaching into three other programs' surfaces to say
    nothing about them. Empty leaves the body exactly as it was, so only
    the cell whose fact changed moves; the execution review holds every
    one of its appended fields to the same rule.
    """

    from chemsmart.agent.capabilities import (
        CapabilityQueryV1,
        query_capability,
    )
    from chemsmart.settings.capabilities import PROGRAM_CAPABILITIES

    carrying = []
    for program, capability in sorted(PROGRAM_CAPABILITIES.items()):
        for jobtype in sorted(capability.jobtypes):
            # Constructing the receipt re-derives its own digest from the
            # canonical body and raises on a mismatch, so reaching here
            # is the statement that the digest follows the body below.
            receipt = query_capability(
                CapabilityQueryV1(program, jobtype, "cpu")
            )
            coverage = receipt.job_result_selector_coverage
            if coverage is None:
                continue
            body = coverage.canonical_body()
            assert ("result_jobtypes" in body) == bool(
                coverage.result_jobtypes
            )
            if coverage.result_jobtypes:
                carrying.append((program, jobtype))
    # One stage in the product spells its results differently from itself.
    assert carrying == [("gaussian", "irc")]
