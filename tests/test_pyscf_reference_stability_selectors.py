"""A PySCF result says whether the reference its numbers stand on is stable.

A converged SCF is not necessarily a minimum in orbital-rotation space, and
result contract v7 has recorded PySCF's own answer since it shipped. One
organ read it: the host's sensor step, which raises
``scf.reference_unstable``. Nothing could extract it, so a session could not
state -- or put in a claim -- that the orbitals its energy came from are a
saddle, and could not report a stable reference at all. That is the same
shape as the two applied permittivities: a value the host records and the
reader does not serve.

The verdicts are not served under Gaussian's ``wavefunction_stability_*``
names. Gaussian prints one word about one unnamed question; PySCF answers
two questions separately and names the rotation space of each, and the
archived triplet-dioxygen run below answers ``external`` about
``UHF/UKS -> GHF/GKS`` where the singlet answers it about
``RHF/RKS -> UHF/UKS``. One name over both would make two programs look
comparable where only one of them says which question it answered.

The fixtures are real PySCF 2.14.0 runs through the ordinary CLI.
"""

from pathlib import Path

import pytest

from chemsmart.analysis.result_quantities import supported_selectors
from chemsmart.analysis.result_readers import (
    MissingQuantityError,
    reader_for,
)

FIXTURES = Path(__file__).resolve().parent / "data" / "PySCFTests" / "outputs"

INTERNAL = "scf_stability_internal"
EXTERNAL = "scf_stability_external"
SPACE = "scf_stability_external_rotation_space"

#: case -> (artifact, internal, external, rotation space). The rows are the
#: answers that differ: a stable closed shell; a closed shell that wants to
#: break symmetry; the same molecule at HF; a triplet asked about a
#: different rotation entirely; and an unconverged run, where PySCF answers
#: about orbitals that are not stationary at all.
ANSWERED = {
    "water_sp_stability": (
        "water_sp_stability_gas_phase.h5",
        "stable",
        "stable",
        "RHF/RKS -> UHF/UKS",
    ),
    "o2_singlet_sp_stability": (
        "o2_singlet_sp_stability_gas_phase.h5",
        "stable",
        "unstable",
        "RHF/RKS -> UHF/UKS",
    ),
    "o2_singlet_hf_sp_stability": (
        "o2_singlet_hf_sp_stability_gas_phase.h5",
        "stable",
        "unstable",
        "RHF/RKS -> UHF/UKS",
    ),
    "o2_triplet_sp_stability": (
        "o2_triplet_sp_stability_gas_phase.h5",
        "stable",
        "unstable",
        "UHF/UKS -> GHF/GKS",
    ),
    "o2_singlet_sp_unconverged_stability": (
        "o2_singlet_sp_unconverged_stability_gas_phase.h5",
        "unstable",
        "unstable",
        "RHF/RKS -> UHF/UKS",
    ),
}


def _open(case, artifact):
    return reader_for("pyscf").open_output(FIXTURES / case / artifact)


@pytest.mark.capability("selector:pyscf:sp:scf_stability_internal")
@pytest.mark.capability("selector:pyscf:sp:scf_stability_external")
@pytest.mark.capability(
    "selector:pyscf:sp:scf_stability_external_rotation_space"
)
@pytest.mark.parametrize("case", sorted(ANSWERED))
def test_each_question_is_answered_with_the_rotation_it_is_about(case):
    """Two questions, answered separately, each naming its own rotation."""

    artifact, internal, external, space = ANSWERED[case]
    reader = reader_for("pyscf")
    output = _open(case, artifact)

    assert reader.read(output, INTERNAL) == (internal, "")
    assert reader.read(output, EXTERNAL) == (external, "")
    assert reader.read(output, SPACE) == (space, "")
    # An answer about the density the final SCF converged, not a setup
    # identity: it belongs to a structure and to the reference.
    for selector in (INTERNAL, EXTERNAL, SPACE):
        assert reader.structural_state(selector) == "as_reached"
        assert reader.electronic_provenance(selector) == "reference"


@pytest.mark.capability("selector:pyscf:sp:scf_stability_external")
def test_one_word_over_both_references_would_have_been_false():
    """The singlet and the triplet are not answered about one rotation.

    Both come back ``unstable`` and the two words mean different things:
    the closed shell can lower its energy by letting alpha and beta
    differ, the open shell only by letting the spinors mix. A reader that
    served one verdict without its space would report those as the same
    finding.
    """

    reader = reader_for("pyscf")
    singlet = _open(
        "o2_singlet_sp_stability", ANSWERED["o2_singlet_sp_stability"][0]
    )
    triplet = _open(
        "o2_triplet_sp_stability", ANSWERED["o2_triplet_sp_stability"][0]
    )

    assert (
        reader.read(singlet, EXTERNAL)[0] == reader.read(triplet, EXTERNAL)[0]
    )
    assert reader.read(singlet, SPACE)[0] != reader.read(triplet, SPACE)[0]


@pytest.mark.capability("selector:pyscf:sp:scf_stability_external")
def test_a_reference_pyscf_cannot_answer_about_refuses_by_name():
    """An ROHF reference has no external answer, and says so.

    The internal question is still answered, so the absence is one
    question's and not the analysis's.
    """

    reader = reader_for("pyscf")
    output = _open(
        "hydrogen_atom_sp_stability", "hydrogen_atom_sp_stability_gas_phase.h5"
    )
    assert reader.read(output, INTERNAL)[0] == "stable"
    for selector in (EXTERNAL, SPACE):
        with pytest.raises(MissingQuantityError) as absent:
            reader.read(output, selector)
        assert "rohf" in str(absent.value)
        assert "could not answer" in str(absent.value)


@pytest.mark.capability("selector:pyscf:sp:scf_stability_internal")
@pytest.mark.parametrize(
    "case,artifact,phrase",
    [
        (
            "water_sp_no_stability",
            "water_sp_no_stability_gas_phase.h5",
            "not asked for a stability analysis",
        ),
        ("water_sp", "water_sp_gas_phase.h5", "records no stability analysis"),
    ],
)
def test_an_absent_analysis_is_never_a_stable_reference(
    case, artifact, phrase
):
    """Not asked, and written before the contract, are two facts and
    neither of them is stability."""

    reader = reader_for("pyscf")
    output = _open(case, artifact)
    for selector in (INTERNAL, EXTERNAL, SPACE):
        with pytest.raises(MissingQuantityError) as absent:
            reader.read(output, selector)
        assert phrase in str(absent.value)
        assert "stable" not in str(absent.value).replace(
            "is not a stable reference", ""
        ).replace("says the reference is stable", "")


@pytest.mark.capability("selector:pyscf:sp:scf_stability_internal")
def test_the_verdicts_are_asked_wherever_an_scf_converges():
    """Declared for every job type, as the spin diagnostic is: any stage
    that converges a reference can be asked about it."""

    reader = reader_for("pyscf")
    declared = dict(reader.jobtype_selectors)
    assert set(declared) == {"hess", "irc", "opt", "sp", "td", "ts"}
    for jobtype, selectors in declared.items():
        for selector in (INTERNAL, EXTERNAL, SPACE):
            assert selector in selectors, (jobtype, selector)

    requestable = supported_selectors()
    for selector in (INTERNAL, EXTERNAL, SPACE):
        assert selector in requestable
    # Gaussian's one-word verdict stays Gaussian's: this reader does not
    # answer it, and nothing here folds two vocabularies into one name.
    assert "wavefunction_stability_verdict" not in reader.accessors
