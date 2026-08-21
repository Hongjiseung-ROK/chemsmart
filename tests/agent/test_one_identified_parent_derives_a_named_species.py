"""Composition could join two fragments; nothing could derive one.

A methanol bond-dissociation session planned all four species correctly --
methanol, both radicals, the hydrogen atom -- previewed the parent green, and
then declined: the radical geometries were not in the workspace and no tool
could make them from the parent, which the model may not edit. Two more
sessions in the same campaign hit the same wall from different directions.
Homolysis, deprotonation and pulling a fragment out of a structure are one
operation on the atom list, and the host now owns it.

The separation is composition's, mirrored: the host owns the selection
arithmetic, the bytes and the lineage; the model owns which atoms and why,
and binds the resulting electronic state explicitly afterwards.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.agent._contracts import (
    ContractError,
    TrustedArtifactRefV1,
    file_sha256,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

#: Methanol, atom 6 being the hydroxyl hydrogen.
_METHANOL = (
    "6\nmethanol\n"
    "C  -0.0475  0.6650  0.0000\n"
    "H  -1.0793  1.0056  0.0000\n"
    "H   0.4448  1.0616  0.8894\n"
    "H   0.4448  1.0616 -0.8894\n"
    "O  -0.0475 -0.7580  0.0000\n"
    "H   0.8595 -1.0524  0.0000\n"
)


def _host_with_methanol(tmp_path, bind_identity=True):
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="s1"
        ),
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )
    (tmp_path / "workspace").mkdir(exist_ok=True)
    path = tmp_path / "methanol.xyz"
    path.write_text(_METHANOL)
    artifact = TrustedArtifactRefV1(
        artifact_id="geometry-methanol",
        kind="geometry_xyz",
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=str(path),
    )
    host.artifacts[artifact.artifact_id] = artifact
    if bind_identity:
        host.dispatch(
            turn_id="t0",
            tool_name="bind_scientific_identity",
            arguments={
                "input_artifact_id": artifact.artifact_id,
                "charge": 0,
                "multiplicity": 1,
            },
        )
    return host


def test_removing_the_hydroxyl_hydrogen_lands_a_species_with_lineage(tmp_path):
    host = _host_with_methanol(tmp_path)

    result = host.dispatch(
        turn_id="t1",
        tool_name="derive_molecular_species",
        arguments={
            "derived_artifact_id": "methoxy-radical-geometry",
            "parent_artifact_id": "geometry-methanol",
            "removed_atoms": [6],
        },
    )["result"]

    derivation = result["derivation"]
    artifact = result["artifact"]
    derived_path = Path(
        str(
            tmp_path
            / "workspace"
            / "artifacts"
            / "methoxy-radical-geometry.xyz"
        )
    )
    assert derived_path.exists()
    assert derivation["parent_formula"] == "CH4O"
    assert derivation["formula"] == "CH3O"
    assert derivation["parent_atom_count"] == 6
    assert derivation["atom_count"] == 5
    assert list(derivation["kept_atoms"]) == [1, 2, 3, 4, 5]
    assert list(derivation["removed_atoms"]) == [6]
    assert derivation["selection_mode"] == "removed"
    # Taking one hydrogen off methanol leaves one connected species; the
    # count is observed so the review can see when it does not.
    assert derivation["fragment_count"] == 1
    assert derivation["parent_artifact_id"] == "geometry-methanol"
    assert derivation["atom_order_note"].startswith("parent order")
    assert "electronic state deliberately unbound" in derived_path.read_text()
    assert "bind charge and multiplicity explicitly" in result["next_action"]
    assert artifact["kind"] == "geometry_xyz"

    kinds = [event.kind for event in host.event_store.read_events()]
    assert EventKind.MOLECULAR_SPECIES_DERIVED.value in kinds

    # CH3O- and CH3O* share this geometry and differ in charge and spin, so
    # the derived artifact carries NO identity until the model binds one.
    assert not any(
        binding.geometry_artifact_sha256 == artifact["sha256"]
        for binding in host.scientific_identities.values()
    )


def test_keeping_and_removing_describe_the_same_species(tmp_path):
    host = _host_with_methanol(tmp_path)

    removed = host.dispatch(
        turn_id="t1",
        tool_name="derive_molecular_species",
        arguments={
            "derived_artifact_id": "by-removal",
            "parent_artifact_id": "geometry-methanol",
            "removed_atoms": [6],
        },
    )["result"]
    kept = host.dispatch(
        turn_id="t2",
        tool_name="derive_molecular_species",
        arguments={
            "derived_artifact_id": "by-keeping",
            "parent_artifact_id": "geometry-methanol",
            "kept_atoms": [1, 2, 3, 4, 5],
        },
    )["result"]

    # Same atoms in the same order, so the bytes match: which way the question
    # was asked is recorded, and changes nothing about the species.
    assert removed["artifact"]["sha256"] == kept["artifact"]["sha256"]
    assert removed["derivation"]["selection_mode"] == "removed"
    assert kept["derivation"]["selection_mode"] == "kept"
    assert (
        removed["derivation"]["kept_atoms"] == kept["derivation"]["kept_atoms"]
    )


def test_extracting_a_hydrogen_atom_is_the_same_operation(tmp_path):
    host = _host_with_methanol(tmp_path)

    result = host.dispatch(
        turn_id="t1",
        tool_name="derive_molecular_species",
        arguments={
            "derived_artifact_id": "hydrogen-atom-geometry",
            "parent_artifact_id": "geometry-methanol",
            "kept_atoms": [6],
        },
    )["result"]

    assert result["derivation"]["formula"] == "H"
    assert result["derivation"]["atom_count"] == 1
    assert list(result["derivation"]["removed_atoms"]) == [1, 2, 3, 4, 5]


def test_a_derivation_that_separates_the_parent_records_the_pieces(tmp_path):
    host = _host_with_methanol(tmp_path)

    # Carbon and the hydroxyl oxygen with no bridging atoms: two pieces. The
    # host does not refuse this -- extracting a fragment pair is legitimate --
    # but it records what it made so the review sees it.
    result = host.dispatch(
        turn_id="t1",
        tool_name="derive_molecular_species",
        arguments={
            "derived_artifact_id": "separated-pieces",
            "parent_artifact_id": "geometry-methanol",
            "kept_atoms": [2, 6],
        },
    )["result"]

    assert result["derivation"]["fragment_count"] == 2


def test_keeping_every_atom_is_a_copy_not_a_derivation(tmp_path):
    host = _host_with_methanol(tmp_path)

    with pytest.raises(ContractError, match="copy the parent"):
        host.dispatch(
            turn_id="t1",
            tool_name="derive_molecular_species",
            arguments={
                "derived_artifact_id": "not-a-derivation",
                "parent_artifact_id": "geometry-methanol",
                "kept_atoms": [1, 2, 3, 4, 5, 6],
            },
        )


@pytest.mark.parametrize(
    ("arguments", "expected"),
    (
        ({}, "exactly one of kept_atoms or removed_atoms"),
        (
            {"kept_atoms": [1], "removed_atoms": [6]},
            "exactly one of kept_atoms or removed_atoms",
        ),
        ({"removed_atoms": [7]}, "must lie in 1..6"),
        ({"removed_atoms": [3, 3]}, "names the same atom twice"),
        ({"removed_atoms": [1, 2, 3, 4, 5, 6]}, "at least one atom"),
    ),
)
def test_a_selection_that_does_not_name_one_species_is_refused(
    tmp_path, arguments, expected
):
    host = _host_with_methanol(tmp_path)

    with pytest.raises(ContractError, match=expected):
        host.dispatch(
            turn_id="t1",
            tool_name="derive_molecular_species",
            arguments={
                "derived_artifact_id": "refused",
                "parent_artifact_id": "geometry-methanol",
                **arguments,
            },
        )


def test_an_unidentified_parent_cannot_be_derived_from(tmp_path):
    host = _host_with_methanol(tmp_path, bind_identity=False)

    with pytest.raises(ContractError) as refusal:
        host.dispatch(
            turn_id="t1",
            tool_name="derive_molecular_species",
            arguments={
                "derived_artifact_id": "methoxy-radical-geometry",
                "parent_artifact_id": "geometry-methanol",
                "removed_atoms": [6],
            },
        )

    message = str(refusal.value)
    assert "carries no scientific identity" in message
    assert "bind_scientific_identity" in message
