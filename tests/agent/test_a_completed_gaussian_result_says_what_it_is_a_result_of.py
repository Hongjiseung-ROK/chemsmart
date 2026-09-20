"""What a finished Gaussian log is a result *of*, and what it then answers.

A result reader gates every selector on the job type, so the job type a
completed log reports is what decides whether the host can read the run at
all.  Gaussian's route line cannot say it on its own: one keyword,
``opt=modredundant``, is written for both a relaxed scan and a constrained
optimisation, and a fixed-geometry response calculation is activated by a
keyword the route-word chain never looked at.  The archived logs below are
real program output this repository already holds; each is read here for
the job it actually was and then for the quantities that job establishes.

Every assertion was red before the reader was taught these answers: the
scan log classified as a single point, the constrained optimisation and the
response calculation were unreadable or read under another job's semantics,
no Gaussian selector carried a structural state, and the populations the
parser had carried for years had no accessor at all.
"""

import math
import pathlib

import pytest

from chemsmart.analysis.result_readers import RESULT_READERS
from chemsmart.io.gaussian.output import Gaussian16Output

pytestmark = pytest.mark.capability("selector:gaussian:*")

_DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "GaussianTests"
_SCAN = _DATA / "outputs" / "cationic_failed_scan.log"
_MODRED = _DATA / "outputs" / "cage_free_failed_modred.log"
_TD = _DATA / "tddft" / "tddft_r1s50_gas_radical_anion.log"
_OPT = _DATA / "outputs" / "collidine_opt.log"
_HIRSHFELD = (
    _DATA / "outputs" / "oxetane_rc_hirshfeld_sp_smd_n_n-DiMethylFormamide.log"
)


@pytest.mark.parametrize(
    "path,jobtype",
    [
        # Driven coordinate: ``B 1 19 S 10 -0.100``.  Its route spells the
        # keyword ``opt=(modredundant,maxstep=10)``, which the route-word
        # chain matched only as the literal ``opt=modred``.
        (_SCAN, "scan"),
        # Frozen coordinates only: three ``B i j F`` rows, no step count.
        (_MODRED, "modred"),
        # ``TD(singlets,nstates=50,root=1)`` on a fixed geometry.
        (_TD, "td"),
        (_OPT, "opt"),
    ],
)
def test_the_log_says_which_job_produced_it(path, jobtype):
    assert Gaussian16Output(filename=str(path)).jobtype == jobtype


@pytest.mark.parametrize(
    "path,jobtype", [(_SCAN, "scan"), (_MODRED, "modred")]
)
def test_a_job_type_the_program_can_produce_is_a_job_type_the_reader_reads(
    path, jobtype
):
    """A declaration exists for what these runs are, not only for their word.

    ``selectors_for_jobtype`` answering ``None`` is the reader saying it
    knows nothing about this kind of result, and extraction then refuses
    every selector.  Both of these were in that state.
    """

    del path
    assert RESULT_READERS["gaussian"].selectors_for_jobtype(jobtype)


@pytest.mark.capability("tool:bind_reached_geometry")
@pytest.mark.capability("selector:gaussian:opt:reached_positions")
@pytest.mark.capability("selector:gaussian:opt:positions")
def test_an_optimisation_offers_the_structure_it_reached_as_that_role():
    """The geometry lift asks for a role, and this reader now has one.

    ``selectors_in_state_for_output(..., "as_reached")`` is what
    ``build_reached_geometry`` intersects against, so a reader declaring no
    structural state cannot hand any structure forward however many
    coordinates it can print.
    """

    reader = RESULT_READERS["gaussian"]
    output = reader.open_output(_OPT)
    assert "reached_positions" in reader.selectors_in_state_for_output(
        output, "as_reached"
    )
    reached, unit = reader.read(output, "reached_positions")
    assert unit == "Angstrom"
    # For Gaussian the spectrum is taken at the converged geometry, so the
    # two roles agree here -- which is a fact about this program's log and
    # not about the roles being the same question.
    positions, _ = reader.read(output, "positions")
    assert reached == positions


@pytest.mark.capability("tool:extract_result_quantities")
@pytest.mark.capability("selector:gaussian:opt:mulliken_atomic_charges")
@pytest.mark.capability("selector:gaussian:td:mulliken_atomic_charges")
@pytest.mark.capability("selector:gaussian:sp:mulliken_atomic_charges")
@pytest.mark.capability("selector:gaussian:sp:hirshfeld_atomic_charges")
@pytest.mark.capability("selector:gaussian:opt:symbols")
@pytest.mark.capability("selector:gaussian:opt:charge")
@pytest.mark.parametrize(
    "path,selector",
    [
        (_OPT, "mulliken_atomic_charges"),
        (_TD, "mulliken_atomic_charges"),
        (_HIRSHFELD, "mulliken_atomic_charges"),
        (_HIRSHFELD, "hirshfeld_atomic_charges"),
    ],
)
def test_a_population_vector_closes_on_the_formal_charge(path, selector):
    """The physical checksum, which is also the completeness check.

    A partition of all the electrons sums to the molecule's charge; a
    vector that dropped, duplicated or reordered an atom would not.  The
    tolerance is loose enough for a basin partition on a numerical grid,
    which closes two orders of magnitude further out than a basis
    partition does.
    """

    reader = RESULT_READERS["gaussian"]
    output = reader.open_output(path)
    charges, unit = reader.read(output, selector)
    symbols, _ = reader.read(output, "symbols")
    total, _ = reader.read(output, "charge")
    assert unit == "e"
    assert len(charges) == len(symbols)
    assert sum(charges) == pytest.approx(float(total), abs=1e-3)


@pytest.mark.capability("selector:gaussian:opt:ir_intensities")
@pytest.mark.capability("selector:gaussian:opt:vibrational_frequencies")
def test_an_intensity_index_names_the_mode_its_frequency_names():
    """Both columns come from one frequency step, so both have one length.

    They did not: every per-mode column but the frequencies themselves was
    read from the whole file behind a ``continue``/``break`` pair that
    could never fire, so a log with two frequency steps answered with two
    steps' intensities against one step's frequencies.
    """

    reader = RESULT_READERS["gaussian"]
    output = reader.open_output(_OPT)
    frequencies, _ = reader.read(output, "vibrational_frequencies")
    intensities, unit = reader.read(output, "ir_intensities")
    assert unit == "km/mol"
    assert len(intensities) == len(frequencies)
    assert all(math.isfinite(value) and value >= 0.0 for value in intensities)


def test_a_fixed_geometry_result_reaches_no_structure():
    """A refusal that names the invariant and a route onward.

    A single point is handed a geometry and returns an energy on it; a
    reader that answered ``reached_positions`` there would hand a recovery
    route the seed it was trying to escape.
    """

    from chemsmart.analysis.result_readers import MissingQuantityError

    reader = RESULT_READERS["gaussian"]
    output = reader.open_output(_HIRSHFELD)
    with pytest.raises(MissingQuantityError) as refusal:
        reader.read(output, "reached_positions")
    assert "reaches no structure" in str(refusal.value)


_ERROR_TERMINATED_OPT = (
    _DATA
    / "outputs"
    / "dppeFeCl2_phenyldioxazolone_opt_triplet_opt_error_termination_link.log"
)


@pytest.mark.capability("tool:bind_reached_geometry")
def test_an_optimisation_that_stopped_short_still_reached_a_structure():
    """ "Reached" is where the optimiser stopped, not where it converged.

    ORCA and PySCF both mean the last printed structure, and the route
    that consumes it is the one the repair menu offers after a run that
    did *not* converge; refusing there returns the session its own seed.
    This archived triplet optimisation error-terminated after seven
    complete frames, having carried 72 atoms 0.3777 angstrom from where
    they started, and the host could not offer a single one of them.

    Convergence is asked elsewhere: by ``converged``, by the spectrum, by
    the validity verdict, and by the producer edge inside an approval,
    which feeds a calculation a human agreed to and keeps its own test.
    """

    reader = RESULT_READERS["gaussian"]
    output = reader.open_output(_ERROR_TERMINATED_OPT)
    assert output.normal_termination is False
    reached, unit = reader.read(output, "reached_positions")
    assert unit == "Angstrom"

    frames = output.all_structures
    assert len(frames) > 1
    assert reached == [
        [float(value) for value in row] for row in frames[-1].positions
    ]
    # Not the seed: the whole point is the distance the optimiser covered.
    supplied = [[float(value) for value in row] for row in frames[0].positions]
    assert (
        max(
            abs(a - b)
            for row, other in zip(reached, supplied)
            for a, b in zip(row, other)
        )
        > 0.1
    )
