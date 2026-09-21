"""A plan names a stage with the CLI's word; a reader is keyed on the word
a finished log says it is. Where a hub job writes results under other
words -- ChemSmart runs one Gaussian ``irc`` as a forward and a reverse
native input, and each log's route says ``ircf`` or ``ircr`` -- the two
never met, so a Gaussian IRC was a stage that could be previewed and then
neither read nor reused: the plan-time selector gate refused any
extraction that named it as producer, and no geometry edge could leave
the node although both branch declarations carry ``reached_positions``.
The reader states the correspondence.
"""

import pytest

from chemsmart.analysis.result_readers import RESULT_READERS, reader_for

pytestmark = pytest.mark.capability("selector:*")


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
