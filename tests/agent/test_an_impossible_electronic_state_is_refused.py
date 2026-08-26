"""A state no molecule can have is refused where the human decides.

The rule is arithmetic, not preference. A species cannot hold a negative
number of electrons, cannot have more unpaired electrons than electrons, and
cannot pair an even electron count with an odd number of unpaired electrons.
Everything the arithmetic permits stays permitted: a singlet and a triplet of
the same species are both admitted here, because which one is right is what
the calculation is for.

It was already written correctly twice -- in the xTB and PySCF job-settings
layers -- and nowhere for ORCA or Gaussian, and nowhere at all before a
workflow had been materialized. A check that runs after a human approves a
plan cannot stop the plan being approved.

The discrimination that matters for a hydrogen-transfer series is the last
test here: one derived geometry, two legal states and two impossible ones.
Taking a hydrogen off phenol gives the phenoxide anion or the phenoxyl radical
depending on where the electron went, and nothing about the resulting atoms
says which.
"""

from __future__ import annotations

import pytest

from chemsmart.agent._contracts import (
    ContractError,
    TrustedArtifactRefV1,
    file_sha256,
)
from chemsmart.agent.identity import refuse_impossible_electronic_state
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.utils.periodictable import electron_count

#: Phenol, planar, atom 7 is the hydroxyl oxygen and atom 8 its hydrogen.
_PHENOL = (
    "13\nphenol\n"
    "C    0.0000   1.3900   0.0000\n"
    "C    1.2040   0.6950   0.0000\n"
    "C    1.2040  -0.6950   0.0000\n"
    "C    0.0000  -1.3900   0.0000\n"
    "C   -1.2040  -0.6950   0.0000\n"
    "C   -1.2040   0.6950   0.0000\n"
    "O    0.0000   2.7500   0.0000\n"
    "H    0.9130   3.0470   0.0000\n"
    "H    2.1390   1.2350   0.0000\n"
    "H    2.1390  -1.2350   0.0000\n"
    "H    0.0000  -2.4700   0.0000\n"
    "H   -2.1390  -1.2350   0.0000\n"
    "H   -2.1390   1.2350   0.0000\n"
)

_WATER = ("O", "H", "H")
#: Phenol and the phenoxyl fragment left when atom 8 is removed.
_PHOH = tuple("C" * 6) + ("O",) + tuple("H" * 6)
_PHO = tuple("C" * 6) + ("O",) + tuple("H" * 5)


def test_the_electron_count_is_the_all_electron_count():
    assert electron_count(_WATER, 0) == 10
    assert electron_count(_WATER, -1) == 11
    assert electron_count(_PHOH, 0) == 50
    assert electron_count(_PHO, 0) == 49


@pytest.mark.parametrize(
    "charge,multiplicity",
    [(0, 1), (0, 3), (-1, 2), (1, 2), (-2, 1)],
)
def test_a_possible_state_is_admitted(charge, multiplicity):
    """Possible is not the same as sensible, and only possible is tested."""

    refuse_impossible_electronic_state(
        _WATER, charge, multiplicity, context="test"
    )


@pytest.mark.parametrize(
    "charge,multiplicity",
    [(0, 2), (0, 4), (-1, 1), (-1, 3), (1, 1)],
)
def test_an_impossible_state_is_refused(charge, multiplicity):
    with pytest.raises(ContractError) as excinfo:
        refuse_impossible_electronic_state(
            _WATER, charge, multiplicity, context="test"
        )
    # The refusal has to name both numbers, or a session cannot tell which
    # of the two it got wrong.
    assert str(charge) in str(excinfo.value) or f"{charge:+d}" in str(
        excinfo.value
    )
    assert str(multiplicity) in str(excinfo.value)


def test_more_unpaired_electrons_than_electrons_is_refused():
    with pytest.raises(ContractError, match="only 2"):
        refuse_impossible_electronic_state(("H", "H"), 0, 4, context="test")


def test_a_negative_electron_count_is_refused():
    with pytest.raises(ContractError, match="negative electron count"):
        refuse_impossible_electronic_state(("H",), 3, 1, context="test")


def test_an_unreadable_symbol_invents_no_verdict():
    """Declining to check beats inventing a verdict from a bad symbol."""

    refuse_impossible_electronic_state(("Xx", "H"), 0, 2, context="test")


def test_one_derived_geometry_admits_two_states_and_refuses_two():
    """The discrimination a hydrogen-transfer series turns on.

    Removing phenol's hydroxyl hydrogen leaves one set of atoms. Binding it
    at charge -1 gives phenoxide, a closed-shell anion; binding the identical
    atoms at charge 0 gives the phenoxyl radical. Both are legal and the host
    picks neither. The two refusals are the states that look plausible if the
    fragment's atoms are read as if they determined the electron count.
    """

    refuse_impossible_electronic_state(_PHO, -1, 1, context="phenoxide")
    refuse_impossible_electronic_state(_PHO, 0, 2, context="phenoxyl")

    with pytest.raises(ContractError):
        refuse_impossible_electronic_state(_PHO, 0, 1, context="test")
    with pytest.raises(ContractError):
        refuse_impossible_electronic_state(_PHO, -1, 2, context="test")


@pytest.mark.parametrize(
    "charge,multiplicity",
    [(0, 1), (1, 2)],
)
def test_the_phenol_corners_are_admitted(charge, multiplicity):
    """The intact-phenol corners of a square scheme must pass."""

    refuse_impossible_electronic_state(
        _PHOH, charge, multiplicity, context="phenol"
    )


def _host(tmp_path):
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="s1"
        ),
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )
    (tmp_path / "workspace").mkdir(exist_ok=True)
    path = tmp_path / "phenol.xyz"
    path.write_text(_PHENOL)
    artifact = TrustedArtifactRefV1(
        artifact_id="phenol",
        kind="geometry_xyz",
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=str(path),
    )
    host.artifacts[artifact.artifact_id] = artifact
    return host


def _bind(host, turn_id, charge, multiplicity):
    return host.dispatch(
        turn_id=turn_id,
        tool_name="bind_scientific_identity",
        arguments={
            "input_artifact_id": "phenol",
            "charge": charge,
            "multiplicity": multiplicity,
        },
    )


def test_the_binding_tool_refuses_an_impossible_state(tmp_path):
    """Through the real session tool, not the predicate alone."""

    host = _host(tmp_path)

    result = _bind(host, "t0", 0, 1)["result"]
    assert result["geometry"]["formula"] == "C6H6O"
    assert host.scientific_identities

    before = len(host.scientific_identities)
    with pytest.raises(ContractError, match="impossible"):
        _bind(host, "t1", 0, 2)
    # A refused binding leaves nothing behind.
    assert len(host.scientific_identities) == before


def test_the_binding_tool_admits_the_radical_cation(tmp_path):
    """Phenol's one-electron oxidation product is a legal doublet."""

    host = _host(tmp_path)
    _bind(host, "t0", 1, 2)
    assert any(
        binding.charge == 1 and binding.multiplicity == 2
        for binding in host.scientific_identities.values()
    )
