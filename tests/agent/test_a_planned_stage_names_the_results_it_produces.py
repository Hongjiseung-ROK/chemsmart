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


def test_an_extraction_may_read_the_stage_a_program_splits():
    """The plan-time gate asks the reader what the stage will produce."""

    plan = _plan(
        "gaussian", "irc", "trajectory_connectivity_changed", "count", "1"
    )
    assert "read-the-walk" in plan.node_order
    # A selector no branch declares is still refused while the plan is
    # built, which is the whole point of the gate: an IRC runs no
    # frequency step, so it has no free energy to give.
    with pytest.raises(ScientificToolchainContractError):
        _plan("gaussian", "irc", "gibbs_free_energy", "energy", "hartree")


def test_a_path_that_reaches_a_structure_may_hand_it_on():
    """A producer edge follows the declaration, on either spelling.

    ORCA's IRC log prints only where the path started, so its reader
    declares no reached structure and its node stays no producer. The
    fact the predicate reads is the declaration, not the program.
    """

    assert _ends_on_one_reached_structure("gaussian", "irc")
    assert not _ends_on_one_reached_structure("orca", "irc")
    assert _ends_on_one_reached_structure("gaussian", "ts")
