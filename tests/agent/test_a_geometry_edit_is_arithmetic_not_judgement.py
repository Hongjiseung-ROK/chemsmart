"""A model could measure a torsion and never change one.

Composition placed two fragments, derivation removed atoms, extraction copied
a record -- and between them nothing could reshape a molecule the session
already had. A conformer on the far side of a rotational barrier, a
deliberately stretched bond, the cis form of an amide: every one of them is a
structure a plain optimisation cannot reach from the geometry in hand, because
optimisation walks downhill and these live over a hill.

The host now owns that arithmetic. The model names an internal coordinate, a
value, and which side of the coordinate moves; the host performs the rigid
motion, measures the coordinate before and after, and enumerates the atoms it
touched. No energy exists at edit time, so nothing here judges whether the
requested value is a good one. That is the point: the value the model asked
for is recorded next to the value an optimiser later returns, and the
difference is the observation.
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

#: trans N-methylacetamide.  Atoms 1-5 are C(methyl), C(carbonyl), O, N,
#: C(methyl); atom 9 is the amide hydrogen.
_NMA = (
    "12\ntrans N-methylacetamide\n"
    "C   -1.9600  -0.2500   0.0000\n"
    "C   -0.5000   0.1400   0.0000\n"
    "O   -0.1700   1.3200   0.0000\n"
    "N    0.4000  -0.8500   0.0000\n"
    "C    1.8300  -0.6600   0.0000\n"
    "H   -2.5700   0.6500   0.0000\n"
    "H   -2.2000  -0.8500   0.8800\n"
    "H   -2.2000  -0.8500  -0.8800\n"
    "H    0.0700  -1.8000   0.0000\n"
    "H    2.2500  -1.1700   0.8700\n"
    "H    2.2500  -1.1700  -0.8700\n"
    "H    2.1000   0.4000   0.0000\n"
)

#: A six-membered carbon ring, for the coordinates a rigid motion cannot set.
_RING_ATOMS = 6


def _ring_text() -> str:
    import math

    lines = [str(_RING_ATOMS), "carbocycle"]
    for index in range(_RING_ATOMS):
        angle = 2.0 * math.pi * index / _RING_ATOMS
        lines.append(
            f"C {1.46 * math.cos(angle):.6f} {1.46 * math.sin(angle):.6f} "
            f"{0.25 * (-1) ** index:.6f}"
        )
    return "\n".join(lines) + "\n"


def _host_with(tmp_path, text: str, artifact_id: str, bind_identity=True):
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="s1"
        ),
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )
    (tmp_path / "workspace").mkdir(exist_ok=True)
    path = tmp_path / f"{artifact_id}.xyz"
    path.write_text(text)
    artifact = TrustedArtifactRefV1(
        artifact_id=artifact_id,
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


def _edit(host, turn_id, **arguments):
    return host.dispatch(
        turn_id=turn_id,
        tool_name="edit_molecular_geometry",
        arguments=arguments,
    )["result"]


def test_a_torsion_reaches_the_value_asked_for_and_moves_one_side(tmp_path):
    host = _host_with(tmp_path, _NMA, "nma")
    parent = Molecule.from_filepath(str(tmp_path / "nma.xyz"))

    result = _edit(
        host,
        "t1",
        edited_artifact_id="nma-cis",
        input_artifact_id="nma",
        operation="set_dihedral",
        atoms=[1, 2, 4, 5],
        moving_side_atom=5,
        target_value=0.0,
    )

    edit = result["geometry_edit"]
    edited_path = Path(
        str(tmp_path / "workspace" / "artifacts" / "nma-cis.xyz")
    )
    assert edited_path.exists()
    assert edit["operation"] == "set_dihedral"
    assert list(edit["coordinate_atoms"]) == [1, 2, 4, 5]
    # The elements are recorded beside the indices: a torsion named over the
    # wrong quadruple reads as nonsense once its atoms are spelled out, and
    # that is how a wrong-atom edit is caught at review.
    assert list(edit["coordinate_symbols"]) == ["C", "C", "N", "C"]
    assert edit["value_unit"] == "degree"
    assert edit["value_before"] == pytest.approx(180.0, abs=1e-3)
    assert edit["value_requested"] == pytest.approx(0.0)
    assert edit["value_achieved"] == pytest.approx(0.0, abs=1e-6)

    # Re-measuring the written bytes agrees with the receipt.
    edited = Molecule.from_filepath(str(edited_path))
    assert edited.get_dihedral(1, 2, 4, 5) == pytest.approx(0.0, abs=1e-6)

    # One side moved; every other atom kept its coordinates exactly.
    moved = set(edit["moved_atoms"])
    assert moved == {4, 5, 9, 10, 11, 12}
    still = [index for index in range(1, 13) if index not in moved]
    assert np.allclose(
        np.asarray(parent.positions)[[index - 1 for index in still]],
        np.asarray(edited.positions)[[index - 1 for index in still]],
    )

    # An edit changes shape, never composition or atom order.
    assert edit["formula"] == "C3H7NO"
    assert edit["atom_count"] == 12
    assert "parent atom i is edited atom i" in edit["atom_order_note"]
    assert edit["connectivity_changed"] is False
    assert "starting structure" in edit["starting_structure_role"]
    assert "electronic state deliberately unbound" in edited_path.read_text()

    kinds = [event.kind for event in host.event_store.read_events()]
    assert EventKind.MOLECULAR_GEOMETRY_EDITED.value in kinds

    # The edited geometry carries NO identity: an edit does not change the
    # electronic state, and it does not inherit one either.
    assert not any(
        binding.geometry_artifact_sha256 == result["artifact"]["sha256"]
        for binding in host.scientific_identities.values()
    )


def test_naming_the_other_side_is_a_different_molecule(tmp_path):
    """Both choices reach the requested value, and they are not the same."""

    host = _host_with(tmp_path, _NMA, "nma")

    far = _edit(
        host,
        "t1",
        edited_artifact_id="turn-the-n-side",
        input_artifact_id="nma",
        operation="set_dihedral",
        atoms=[1, 2, 4, 5],
        moving_side_atom=5,
        target_value=0.0,
    )
    near = _edit(
        host,
        "t2",
        edited_artifact_id="turn-the-acetyl-side",
        input_artifact_id="nma",
        operation="set_dihedral",
        atoms=[1, 2, 4, 5],
        moving_side_atom=1,
        target_value=0.0,
    )

    assert far["geometry_edit"]["value_achieved"] == pytest.approx(
        near["geometry_edit"]["value_achieved"], abs=1e-6
    )
    assert set(far["geometry_edit"]["moved_atoms"]) == {4, 5, 9, 10, 11, 12}
    assert set(near["geometry_edit"]["moved_atoms"]) == {1, 2, 3, 6, 7, 8}
    # Same coordinate, different bytes: which side moves is a scientific
    # choice, which is why it is named rather than defaulted.
    assert far["artifact"]["sha256"] != near["artifact"]["sha256"]


def test_a_bond_length_and_an_angle_are_set_exactly(tmp_path):
    host = _host_with(tmp_path, _NMA, "nma")

    bond = _edit(
        host,
        "t1",
        edited_artifact_id="long-amide-cn",
        input_artifact_id="nma",
        operation="set_bond_length",
        atoms=[2, 4],
        moving_side_atom=4,
        target_value=1.47,
    )["geometry_edit"]
    assert bond["value_unit"] == "angstrom"
    assert bond["value_before"] == pytest.approx(1.338, abs=1e-3)
    assert bond["value_achieved"] == pytest.approx(1.47, abs=1e-6)

    angle = _edit(
        host,
        "t2",
        edited_artifact_id="wide-cnc",
        input_artifact_id="nma",
        operation="set_angle",
        atoms=[2, 4, 5],
        moving_side_atom=5,
        target_value=130.0,
    )["geometry_edit"]
    assert angle["value_unit"] == "degree"
    assert angle["value_achieved"] == pytest.approx(130.0, abs=1e-6)

    edited = Molecule.from_filepath(
        str(tmp_path / "workspace" / "artifacts" / "wide-cnc.xyz")
    )
    assert edited.get_angle(2, 4, 5) == pytest.approx(130.0, abs=1e-6)


def test_a_close_contact_is_observed_and_the_edit_still_happens(tmp_path):
    """The host measures the consequence; it does not veto the chemistry.

    Driving two atoms together may be the whole point of an edit or the
    mistake in it, and only a scientist reading the review can tell which.
    """

    host = _host_with(tmp_path, _NMA, "nma")

    edit = _edit(
        host,
        "t1",
        edited_artifact_id="squashed",
        input_artifact_id="nma",
        operation="set_bond_length",
        atoms=[2, 4],
        moving_side_atom=4,
        target_value=0.6,
    )["geometry_edit"]

    assert edit["value_achieved"] == pytest.approx(0.6, abs=1e-6)
    assert edit["min_interatomic_distance_angstrom"] < 1.0
    assert edit["close_contact_pairs"]
    # Nothing in the receipt calls this wrong; it is measured and shown.
    assert edit["status"] == "edited"


def test_a_ring_coordinate_is_refused_per_coordinate(tmp_path):
    """A rigid motion cannot set a ring coordinate without tearing the ring.

    Which bond traps the coordinate differs: a bond length by its own bond, a
    torsion by its central bond, an angle only when both of its bonds are in
    the ring.
    """

    host = _host_with(tmp_path, _ring_text(), "ring")

    with pytest.raises(ContractError, match="lies in a ring"):
        _edit(
            host,
            "t1",
            edited_artifact_id="ring-bond",
            input_artifact_id="ring",
            operation="set_bond_length",
            atoms=[1, 2],
            moving_side_atom=2,
            target_value=1.6,
        )
    with pytest.raises(ContractError, match="central bond"):
        _edit(
            host,
            "t2",
            edited_artifact_id="ring-torsion",
            input_artifact_id="ring",
            operation="set_dihedral",
            atoms=[1, 2, 3, 4],
            moving_side_atom=4,
            target_value=60.0,
        )
    with pytest.raises(ContractError, match="both bonds of the angle"):
        _edit(
            host,
            "t3",
            edited_artifact_id="ring-angle",
            input_artifact_id="ring",
            operation="set_angle",
            atoms=[1, 2, 3],
            moving_side_atom=3,
            target_value=100.0,
        )


def test_the_refusal_points_at_the_route_that_works(tmp_path):
    host = _host_with(tmp_path, _ring_text(), "ring")

    with pytest.raises(ContractError) as caught:
        _edit(
            host,
            "t1",
            edited_artifact_id="ring-bond",
            input_artifact_id="ring",
            operation="set_bond_length",
            atoms=[1, 2],
            moving_side_atom=2,
            target_value=1.6,
        )
    message = str(caught.value)
    assert "modred" in message and "scan" in message


def test_structural_refusals_name_what_is_wrong(tmp_path):
    host = _host_with(tmp_path, _NMA, "nma")

    with pytest.raises(ContractError, match="not bonded"):
        _edit(
            host,
            "t1",
            edited_artifact_id="unbonded",
            input_artifact_id="nma",
            operation="set_bond_length",
            atoms=[1, 5],
            moving_side_atom=5,
            target_value=2.0,
        )
    with pytest.raises(ContractError, match="one of the coordinate's own"):
        _edit(
            host,
            "t2",
            edited_artifact_id="foreign-side",
            input_artifact_id="nma",
            operation="set_dihedral",
            atoms=[1, 2, 4, 5],
            moving_side_atom=7,
            target_value=0.0,
        )
    with pytest.raises(ContractError, match="must lie in 1.."):
        _edit(
            host,
            "t3",
            edited_artifact_id="out-of-range",
            input_artifact_id="nma",
            operation="set_dihedral",
            atoms=[1, 2, 4, 99],
            moving_side_atom=1,
            target_value=0.0,
        )
    with pytest.raises(ContractError, match="same atom twice"):
        _edit(
            host,
            "t4",
            edited_artifact_id="repeated",
            input_artifact_id="nma",
            operation="set_angle",
            atoms=[1, 2, 1],
            moving_side_atom=1,
            target_value=100.0,
        )
    with pytest.raises(ContractError, match="strictly between 0 and 180"):
        _edit(
            host,
            "t5",
            edited_artifact_id="flat-angle",
            input_artifact_id="nma",
            operation="set_angle",
            atoms=[2, 4, 5],
            moving_side_atom=5,
            target_value=180.0,
        )
    with pytest.raises(ContractError, match=r"\[-180, 180\]"):
        _edit(
            host,
            "t6",
            edited_artifact_id="over-turned",
            input_artifact_id="nma",
            operation="set_dihedral",
            atoms=[1, 2, 4, 5],
            moving_side_atom=5,
            target_value=270.0,
        )


def test_an_unidentified_parent_cannot_be_edited(tmp_path):
    host = _host_with(tmp_path, _NMA, "nma", bind_identity=False)

    with pytest.raises(ContractError, match="carries no scientific identity"):
        _edit(
            host,
            "t1",
            edited_artifact_id="nma-cis",
            input_artifact_id="nma",
            operation="set_dihedral",
            atoms=[1, 2, 4, 5],
            moving_side_atom=5,
            target_value=0.0,
        )


def test_the_advertised_operations_are_the_ones_the_host_implements(tmp_path):
    """The tool surface cannot name an operation with no arithmetic behind it."""

    from chemsmart.agent.execution import EDITABLE_COORDINATE_OPERATIONS
    from chemsmart.agent.tool_specs import (
        build_command_compiled_tool_surface,
    )

    surface = build_command_compiled_tool_surface()
    definition = next(
        item
        for item in surface.tool_definitions
        if item["function"]["name"] == "edit_molecular_geometry"
    )
    advertised = definition["function"]["parameters"]["properties"][
        "operation"
    ]["enum"]
    assert set(advertised) == set(EDITABLE_COORDINATE_OPERATIONS)

    # An operation with no arithmetic behind it is refused at the argument
    # boundary, naming the set that does exist.
    host = _host_with(tmp_path, _NMA, "nma")
    with pytest.raises(ContractError, match="not one of"):
        _edit(
            host,
            "t1",
            edited_artifact_id="improper",
            input_artifact_id="nma",
            operation="set_improper",
            atoms=[1, 2, 4, 5],
            moving_side_atom=5,
            target_value=0.0,
        )


def _duck_review(node_reviews):
    from types import SimpleNamespace

    return SimpleNamespace(
        scientific_plan=SimpleNamespace(nodes=(), edges=()),
        node_reviews=node_reviews,
    )


def _rendered(renderable):
    from rich.console import Console

    console = Console(record=True, width=200)
    console.print(renderable)
    return console.export_text()


def test_the_edit_reaches_the_decision_surface_with_its_elements(tmp_path):
    """What a human needs to catch a wrong edit, on the page they approve."""

    from types import SimpleNamespace

    from chemsmart.agent.tui.review import _geometry_edit_panels

    host = _host_with(tmp_path, _NMA, "nma")
    edit = _edit(
        host,
        "t1",
        edited_artifact_id="nma-cis",
        input_artifact_id="nma",
        operation="set_dihedral",
        atoms=[1, 2, 4, 5],
        moving_side_atom=5,
        target_value=0.0,
    )["geometry_edit"]

    review = _duck_review(
        (
            SimpleNamespace(
                node_id="opt-cis",
                molecular_identity={
                    "charge": 0,
                    "multiplicity": 1,
                    "geometry_edit": edit,
                },
            ),
        )
    )
    panels = _geometry_edit_panels(review)
    assert len(panels) == 1
    text = _rendered(panels[0])

    # The atoms carry their elements: a torsion named over the wrong
    # quadruple is caught by reading it.
    assert "C1 - C2 - N4 - C5" in text
    assert "set_dihedral" in text
    # All three values, so the requested one survives next to the achieved.
    assert "before 180.0 degree" in text
    assert "requested 0.0 degree" in text
    assert "achieved 0.0 degree" in text
    assert "moved the side of atom 5" in text
    assert "observations, not verdicts" in text
    assert "starting structure" in text
    assert "binds charge 0, multiplicity 1 explicitly" in text


def test_every_atom_of_a_coordinate_names_a_side(tmp_path):
    """The side that moves decides the motion, not which atom named it.

    An angle's vertex and a torsion's inner atoms each sit on a side without
    being its outer atom, and pointing at a side by one of them is legal.
    Deriving the sense of the rotation from the named atom instead of the
    moved component sent the vertex case the wrong way: the host's own
    verification caught it, but a legal input must not be a host error.
    """

    host = _host_with(tmp_path, _NMA, "nma")

    reached = {}
    for named in (2, 4, 5):
        edit = _edit(
            host,
            f"t-angle-{named}",
            edited_artifact_id=f"angle-named-{named}",
            input_artifact_id="nma",
            operation="set_angle",
            atoms=[2, 4, 5],
            moving_side_atom=named,
            target_value=130.0,
        )["geometry_edit"]
        assert edit["value_achieved"] == pytest.approx(130.0, abs=1e-6)
        reached[named] = tuple(edit["moved_atoms"])
    # The vertex points at the same side as the far atom does.
    assert reached[4] == reached[5]
    assert reached[2] != reached[5]

    for named in (1, 2, 4, 5):
        edit = _edit(
            host,
            f"t-dihedral-{named}",
            edited_artifact_id=f"dihedral-named-{named}",
            input_artifact_id="nma",
            operation="set_dihedral",
            atoms=[1, 2, 4, 5],
            moving_side_atom=named,
            target_value=0.0,
        )["geometry_edit"]
        assert edit["value_achieved"] == pytest.approx(0.0, abs=1e-6)

    for named in (2, 4):
        edit = _edit(
            host,
            f"t-bond-{named}",
            edited_artifact_id=f"bond-named-{named}",
            input_artifact_id="nma",
            operation="set_bond_length",
            atoms=[2, 4],
            moving_side_atom=named,
            target_value=1.47,
        )["geometry_edit"]
        assert edit["value_achieved"] == pytest.approx(1.47, abs=1e-6)
