"""What an xTB result's solvent cost, and what the solvent was.

The plan could already switch ALPB or GBSA on -- ``solvent_model`` and
``solvent_id`` are advertised xTB settings -- while no finished xTB result
could say which model had run, in what, or what it was worth.  This pins
the whole path on archived real output:

    real solvated xTB output artifact
        ↓
    xTB result reader (SUMMARY block + SETUP block)
        ↓
    public selectors (solvation_free_energy and its parts, model, solvent)
        ↓
    typed extraction receipt with units and structural state
        ↓
    the Agent's own inspect_run / extract_result_quantities surface
"""

import shutil
from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.postprocessing import (
    extract_trusted_result_quantities,
    typed_result_artifact_kind,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.analysis.result_quantities import (
    QuantityExtractionError,
    QuantitySelectorV1,
    supported_selectors,
)

_BENZYNE_SP = (
    "tests/data/XTBTests/outputs/p_benzyne_sp_alpb_toluene/"
    "p_benzyne_sp_alpb_toluene.out"
)
_BENZYNE_OPT = (
    "tests/data/XTBTests/outputs/p_benzyne_opt_alpb_toluene/"
    "p_benzyne_opt_alpb_toluene.out"
)
_WATER_OHESS = "tests/data/XTBTests/outputs/water_ohess/water_ohess.out"

#: The total and the four parts whose sum it is.
_TOTAL = "solvation_free_energy"
_PARTS = (
    "solvation_electrostatic_energy",
    "xtb_solvation_sasa_energy",
    "xtb_solvation_hydrogen_bond_energy",
    "xtb_solvation_shift_energy",
)
_TERMS = (_TOTAL,) + _PARTS
_NAMES = _TERMS + ("solvation_model", "solvent")


def _artifact(
    path: str | Path, artifact_id: str = "art-1"
) -> TrustedArtifactRefV1:
    resolved = Path(path).resolve()
    return TrustedArtifactRefV1(
        artifact_id=artifact_id,
        kind=typed_result_artifact_kind("xtb"),
        sha256=file_sha256(resolved),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )


def _extract(path, artifact_id, selectors=_NAMES):
    return extract_trusted_result_quantities(
        artifact=_artifact(path, artifact_id),
        program="xtb",
        selectors=tuple(
            QuantitySelectorV1(quantity_id=name, selector=name)
            for name in selectors
        ),
    )


@pytest.mark.capability("selector:xtb:sp:solvation_free_energy")
@pytest.mark.capability("selector:xtb:sp:solvation_electrostatic_energy")
@pytest.mark.capability("selector:xtb:sp:xtb_solvation_sasa_energy")
@pytest.mark.capability("selector:xtb:sp:xtb_solvation_hydrogen_bond_energy")
@pytest.mark.capability("selector:xtb:sp:xtb_solvation_shift_energy")
@pytest.mark.capability("selector:xtb:sp:solvation_model")
@pytest.mark.capability("selector:xtb:sp:solvent")
def test_a_solvated_result_reports_the_model_the_solvent_and_the_cost():
    """Every declared term resolves, in Hartree, from one real ALPB run."""

    receipt = _extract(_BENZYNE_SP, "benzyne-sp")
    assert receipt.status == "extracted"
    delivered = {item.quantity_id: item for item in receipt.quantities}

    assert delivered["solvation_model"].value == "alpb"
    assert delivered["solvent"].value == "toluene"
    for name in _TERMS:
        assert delivered[name].unit == "hartree"
        assert delivered[name].source_unit == "Eh"
        assert (
            delivered[name].evidence_ref
            == f"artifact:{receipt.artifact_id}#{receipt.artifact_sha256}"
        )

    # The identity the model itself defines, read off the delivered values
    # rather than pinned: Gsolv is the sum of its four parts.
    total = delivered[_TOTAL].value
    assert total == pytest.approx(
        sum(delivered[name].value for name in _PARTS), abs=1e-9
    )
    # Solvation is stabilising here, and the cavity term carries it.
    assert total < 0.0
    assert delivered["xtb_solvation_sasa_energy"].value < 0.0


@pytest.mark.capability("selector:xtb:opt:solvation_free_energy")
@pytest.mark.capability("selector:xtb:opt:solvent")
def test_an_optimisation_reports_the_solvation_it_reached():
    """The terms follow the last SUMMARY block, not the first."""

    receipt = _extract(_BENZYNE_OPT, "benzyne-opt")
    assert receipt.status == "extracted"
    delivered = {item.quantity_id: item.value for item in receipt.quantities}
    assert delivered["solvent"] == "toluene"
    assert delivered[_TOTAL] == pytest.approx(
        sum(delivered[name] for name in _PARTS), abs=1e-9
    )
    # A converged optimisation's last block is not its first: the single
    # point at the same level differs in the sixth decimal of Gelec.
    sp_receipt = _extract(
        _BENZYNE_SP,
        "benzyne-sp",
        ("solvation_electrostatic_energy",),
    )
    assert delivered["solvation_electrostatic_energy"] != pytest.approx(
        sp_receipt.quantities[0].value, abs=1e-12
    )


@pytest.mark.capability("selector:xtb:hess:solvation_model")
def test_a_gas_phase_result_says_gas_phase_and_offers_no_terms():
    """Absence is meaning: no solvent is an answer, not a missing number."""

    receipt = _extract(_WATER_OHESS, "water-hess")
    assert receipt.status == "partial"
    delivered = {item.quantity_id: item.value for item in receipt.quantities}
    assert delivered["solvation_model"] == "gas_phase"
    absent = {selector for _qid, selector, _reason in receipt.absent}
    assert absent == set(_TERMS) | {"solvent"}
    for _qid, _selector, reason in receipt.absent:
        assert "gas phase" in reason


def test_terms_that_do_not_add_up_are_refused(tmp_path):
    """A SUMMARY block whose parts miss its total is a misread block.

    Each term is resolved by its own keyword scan, so nothing in a single
    read proves five numbers came from one block.  The model's identity
    does, and it is checked on every read.
    """

    copied = tmp_path / "benzyne"
    shutil.copytree(Path(_BENZYNE_SP).parent, copied)
    main = copied / Path(_BENZYNE_SP).name
    text = main.read_text()
    assert "-> Gsasa               -0.008487964543" in text
    main.write_text(
        text.replace(
            "-> Gsasa               -0.008487964543",
            "-> Gsasa               -0.007487964543",
        )
    )
    with pytest.raises(QuantityExtractionError, match="do not close"):
        _extract(main, "doctored", (_TOTAL,))


def test_a_result_that_names_no_model_cannot_charge_for_one(tmp_path):
    """Solvation terms with nothing claiming a solvent are refused."""

    copied = tmp_path / "benzyne"
    shutil.copytree(Path(_BENZYNE_SP).parent, copied)
    main = copied / Path(_BENZYNE_SP).name
    text = main.read_text()
    assert "Solvation model:" in text and "GBSA solvation" in text
    main.write_text(
        text.replace("Solvation model:", "Xxxxxxxxx xxxxx:").replace(
            "GBSA solvation", "XXXX solvation"
        )
    )
    with pytest.raises(QuantityExtractionError, match="disagree"):
        _extract(main, "doctored", (_TOTAL,))


def test_a_result_whose_setup_block_omits_the_field_is_still_solvated(
    tmp_path,
):
    """The model line, not one Hamiltonian's setup field, says solvated.

    Only the SCC Hamiltonians print ``GBSA solvation`` in the setup
    block. A live GFN-FF/ALPB(water) single point printed the model, the
    solvent and the decomposition without it, and a reader keyed on that
    one field called the run gas phase while its own energy summary
    charged it for a solvent.
    """

    copied = tmp_path / "benzyne"
    shutil.copytree(Path(_BENZYNE_SP).parent, copied)
    main = copied / Path(_BENZYNE_SP).name
    text = main.read_text()
    assert "GBSA solvation" in text
    main.write_text(
        "\n".join(
            line for line in text.splitlines() if "GBSA solvation" not in line
        )
    )
    receipt = _extract(main, "no-setup-field", _NAMES)
    assert receipt.status == "extracted"
    delivered = {item.quantity_id: item.value for item in receipt.quantities}
    assert delivered["solvation_model"] == "alpb"
    assert delivered["solvent"] == "toluene"
    assert delivered[_TOTAL] == pytest.approx(
        sum(delivered[name] for name in _PARTS), abs=1e-9
    )


def test_the_solvation_terms_are_requestable_and_reach_inspect_run(tmp_path):
    """The Agent's own surface offers them on a finished xTB result."""

    assert set(_NAMES) <= supported_selectors()
    artifact = _artifact(_BENZYNE_SP, "benzyne-sp")
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="test-xtb-solv"
        ),
        artifacts={artifact.artifact_id: artifact},
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )
    inspected = host._inspect_run(
        "t1", {"program": "xtb", "artifact_id": artifact.artifact_id}
    )
    assert set(_NAMES) <= set(inspected["requestable_selectors"])

    reply = host.dispatch(
        turn_id="t2",
        tool_name="extract_result_quantities",
        arguments={
            "program": "xtb",
            "artifact_id": artifact.artifact_id,
            "selectors": [
                {"quantity_id": "g_solv", "selector": _TOTAL},
                {"quantity_id": "model", "selector": "solvation_model"},
            ],
        },
    )
    values = {
        item["quantity_id"]: item["value"]
        for item in reply["result"]["quantities"]
    }
    assert values["model"] == "alpb"
    assert values["g_solv"] == pytest.approx(-0.006398929092, abs=1e-9)


def test_the_catalogue_names_the_solvation_selectors_for_xtb():
    """A selector nobody can find is a capability nobody has."""

    from chemsmart.agent.catalogue import build_tool_catalogue

    entry = {item.name: item for item in build_tool_catalogue().entries}[
        "about_result_selectors_xtb"
    ]
    text = str(entry.definition)
    for name in _TERMS:
        assert name in text
