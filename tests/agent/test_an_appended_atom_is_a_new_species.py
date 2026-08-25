"""Derivation could take a hydrogen off; nothing could put one on.

Four acids were deprotonated through the composed pKa cycle and not one base
could be protonated, because adding an atom needs an atom to add and no tool
could make one: composition joins two artifacts that already exist, and the
model may not author coordinates. So the whole of protonation, hydrogenation,
radical capping and deuteration sat outside the surface.

Appending is derivation's mirror, and it inherits derivation's discipline
exactly. The host owns the placement arithmetic -- the three internal
coordinates that say where the atom sits -- and the bytes; the model owns the
element, the anchors and the geometry. It never infers an electronic state:
taking a hydrogen off gives a radical or an anion depending on where its
electron went, and putting one on gives a cation or a radical depending on
whether it brought one.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from chemsmart.agent._contracts import (
    ContractError,
    TrustedArtifactRefV1,
    file_sha256,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.io.molecules.structure import Molecule

#: Methylamine; atom 1 is nitrogen, the site a proton would go on.
_METHYLAMINE = (
    "7\nmethylamine\n"
    "N   -0.7000   0.0300   0.0000\n"
    "C    0.7300  -0.1600   0.0000\n"
    "H   -1.1600  -0.6900   0.5400\n"
    "H   -1.0400   0.9000   0.4000\n"
    "H    1.1800   0.6000   0.6400\n"
    "H    0.9900  -1.1300   0.4300\n"
    "H    1.1400  -0.1000  -1.0100\n"
)


def _host(tmp_path, bind_identity=True):
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="s1"
        ),
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )
    (tmp_path / "workspace").mkdir(exist_ok=True)
    path = tmp_path / "methylamine.xyz"
    path.write_text(_METHYLAMINE)
    artifact = TrustedArtifactRefV1(
        artifact_id="methylamine",
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


def _append(host, turn_id, **arguments):
    return host.dispatch(
        turn_id=turn_id,
        tool_name="append_molecular_atom",
        arguments=arguments,
    )["result"]


def test_protonating_the_nitrogen_lands_a_species_with_lineage(tmp_path):
    host = _host(tmp_path)
    parent = Molecule.from_filepath(str(tmp_path / "methylamine.xyz"))

    result = _append(
        host,
        "t1",
        appended_artifact_id="methylammonium-geometry",
        input_artifact_id="methylamine",
        element="H",
        anchor_atom=1,
        angle_atom=2,
        dihedral_atom=5,
        bond_length_angstrom=1.02,
        angle_degrees=109.5,
        dihedral_degrees=60.0,
    )

    append = result["atom_append"]
    appended_path = Path(
        str(
            tmp_path
            / "workspace"
            / "artifacts"
            / "methylammonium-geometry.xyz"
        )
    )
    assert appended_path.exists()
    assert append["element"] == "H"
    assert append["parent_formula"] == "CH5N"
    assert append["formula"] == "CH6N"
    assert append["parent_atom_count"] == 7
    assert append["atom_count"] == 8
    assert append["appended_atom_index"] == 8
    assert list(append["anchor_atoms"]) == [1, 2, 5]
    assert list(append["anchor_symbols"]) == ["N", "C", "H"]
    assert append["fragment_count"] == 1

    # The atom sits exactly where the three coordinates put it.
    appended = Molecule.from_filepath(str(appended_path))
    assert appended.get_distance(8, 1) == pytest.approx(1.02, abs=1e-6)
    assert appended.get_angle(8, 1, 2) == pytest.approx(109.5, abs=1e-6)
    assert appended.get_dihedral(8, 1, 2, 5) == pytest.approx(60.0, abs=1e-6)
    assert append["achieved_bond_length_angstrom"] == pytest.approx(1.02)
    assert append["achieved_angle_degrees"] == pytest.approx(109.5)
    assert append["achieved_dihedral_degrees"] == pytest.approx(60.0)

    # Parent atoms keep their indices and their coordinates.
    assert np.allclose(
        np.asarray(parent.positions), np.asarray(appended.positions)[:7]
    )
    assert "parent atom indices are unchanged" in append["atom_order_note"]
    assert "electronic state deliberately unbound" in appended_path.read_text()
    assert "bind charge and multiplicity explicitly" in result["next_action"]

    kinds = [event.kind for event in host.event_store.read_events()]
    assert EventKind.MOLECULAR_ATOM_APPENDED.value in kinds

    # CH3NH3+ and CH3NH3* share this geometry and differ in charge and spin,
    # so the appended artifact carries NO identity until the model binds one.
    assert not any(
        binding.geometry_artifact_sha256 == result["artifact"]["sha256"]
        for binding in host.scientific_identities.values()
    )


def test_the_appended_species_binds_its_own_state(tmp_path):
    """Adding a proton makes a cation only because the model says so."""

    host = _host(tmp_path)
    result = _append(
        host,
        "t1",
        appended_artifact_id="methylammonium-geometry",
        input_artifact_id="methylamine",
        element="H",
        anchor_atom=1,
        angle_atom=2,
        dihedral_atom=5,
        bond_length_angstrom=1.02,
        angle_degrees=109.5,
        dihedral_degrees=60.0,
    )

    host.dispatch(
        turn_id="t2",
        tool_name="bind_scientific_identity",
        arguments={
            "input_artifact_id": "methylammonium-geometry",
            "charge": 1,
            "multiplicity": 1,
        },
    )
    assert any(
        binding.geometry_artifact_sha256 == result["artifact"]["sha256"]
        and binding.charge == 1
        for binding in host.scientific_identities.values()
    )


def test_placement_refusals_name_what_is_wrong(tmp_path):
    host = _host(tmp_path)
    common = {
        "input_artifact_id": "methylamine",
        "element": "H",
        "anchor_atom": 1,
        "angle_atom": 2,
        "dihedral_atom": 5,
        "bond_length_angstrom": 1.02,
        "angle_degrees": 109.5,
        "dihedral_degrees": 60.0,
    }

    with pytest.raises(ContractError, match="not a chemical element"):
        _append(
            host,
            "t1",
            **{**common, "appended_artifact_id": "a", "element": "Xx"},
        )
    with pytest.raises(ContractError, match="must lie in 1.."):
        _append(
            host,
            "t2",
            **{**common, "appended_artifact_id": "b", "anchor_atom": 99},
        )
    with pytest.raises(ContractError, match="same anchor atom twice"):
        _append(
            host,
            "t3",
            **{**common, "appended_artifact_id": "c", "angle_atom": 1},
        )


def test_an_unidentified_parent_cannot_be_appended_to(tmp_path):
    host = _host(tmp_path, bind_identity=False)

    with pytest.raises(ContractError, match="carries no scientific identity"):
        _append(
            host,
            "t1",
            appended_artifact_id="cation",
            input_artifact_id="methylamine",
            element="H",
            anchor_atom=1,
            angle_atom=2,
            dihedral_atom=5,
            bond_length_angstrom=1.02,
            angle_degrees=109.5,
            dihedral_degrees=60.0,
        )


def test_an_atom_placed_far_away_is_observed_not_refused(tmp_path):
    """Two separated pieces is a fact about the geometry, not a verdict."""

    host = _host(tmp_path)

    append = _append(
        host,
        "t1",
        appended_artifact_id="distant-hydrogen",
        input_artifact_id="methylamine",
        element="H",
        anchor_atom=1,
        angle_atom=2,
        dihedral_atom=5,
        bond_length_angstrom=4.5,
        angle_degrees=109.5,
        dihedral_degrees=60.0,
    )["atom_append"]

    assert append["achieved_bond_length_angstrom"] == pytest.approx(4.5)
    assert append["fragment_count"] == 2
    assert append["status"] == "appended"
