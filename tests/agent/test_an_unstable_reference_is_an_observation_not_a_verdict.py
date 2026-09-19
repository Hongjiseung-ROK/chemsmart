"""A reference PySCF itself calls unstable reaches somebody who decides.

Result contract v7 let a PySCF run record whether the converged SCF is a
minimum in orbital-rotation space, and nothing read the record: no
selector, no host sensor, no settlement word.  So a validated result
whose every receipt is green could deliver an energy, an orbital energy,
a population, a spin expectation, a gradient or a frequency that
describes a saddle in orbital space, and no organ of this host said so.

It is an observation and never a verdict: a broken-symmetry or
deliberately constrained solution is sometimes exactly what a scientist
asked for.  Silence is never stability -- a program whose reader answers
nothing, an artifact older than the record, a run nobody asked, and an
analysis that raised all arrive as no diagnostics at all.

Driven through ``_evaluate_execution_outputs``, the step the provider-free
executor calls on every finished node, over archived real bytes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.execution import (
    ANOMALY_SIGNALS,
    build_anomaly_observation,
)
from chemsmart.agent.tool_runtime import (
    CommandCompiledToolHostV1,
    _output_artifact_kind,
)
from chemsmart.analysis.result_readers import reader_for

_DATA = Path(__file__).resolve().parents[1] / "data"
_PYSCF = _DATA / "PySCFTests" / "outputs"
_GAUSSIAN = _DATA / "GaussianTests" / "outputs"
_ORCA = _DATA / "ORCATests" / "outputs"

SIGNAL = "scf.reference_unstable"


#: label suffix and the bound state each archived run was launched with
_CASES = {
    "o2_singlet_sp_stability": ("gas_phase", 1, "dioxygen.xyz"),
    "o2_singlet_hf_sp_stability": ("gas_phase", 1, "dioxygen.xyz"),
    "o2_triplet_sp_stability": ("gas_phase", 3, "dioxygen.xyz"),
    "o2_singlet_hess_stability": ("gas_phase", 1, "dioxygen.xyz"),
    "o2_singlet_sp_unconverged_stability": ("gas_phase", 1, "dioxygen.xyz"),
    "water_sp_stability": ("gas_phase", 1, "water_relaxed.xyz"),
    "water_sp_no_stability": ("gas_phase", 1, "water_relaxed.xyz"),
    "water_sp": ("gas_phase", 1, "water_distorted.xyz"),
    "water_sp_stability_cpcm": ("cpcm_water", 1, "water_relaxed.xyz"),
    "hydrogen_atom_sp_stability": ("gas_phase", 2, "hydrogen_atom.xyz"),
}


def _artifacts(case: str, label: str) -> tuple[TrustedArtifactRefV1, ...]:
    found = []
    for path in sorted((_PYSCF / case).glob(f"{label}*")):
        if path.suffix == ".json" and "reference" in path.name:
            continue
        kind = (
            "pyscf_hdf5"
            if path.suffix == ".h5"
            else _output_artifact_kind("pyscf", path)
        )
        found.append(
            TrustedArtifactRefV1(
                artifact_id=f"result.{path.name}",
                kind=kind,
                sha256=file_sha256(path),
                size_bytes=path.stat().st_size,
                path=str(path),
                cli_value=str(path),
            )
        )
    return tuple(found)


def _input(name: str) -> TrustedArtifactRefV1:
    path = _PYSCF / "inputs" / name
    return TrustedArtifactRefV1(
        artifact_id=f"geometry.{name}",
        kind="geometry_xyz",
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=str(path),
    )


def _evaluate(case: str, *, jobtype: str = "sp"):
    suffix, multiplicity, geometry = _CASES[case]
    return CommandCompiledToolHostV1._evaluate_execution_outputs(
        program="pyscf",
        jobtype=jobtype,
        charge=0,
        multiplicity=multiplicity,
        expected_input_artifact=_input(geometry),
        output_artifacts=_artifacts(case, f"{case}_{suffix}"),
        exit_status=0,
    )


def _signals(evaluation) -> dict[str, dict]:
    return {item["signal_id"]: item for item in evaluation.anomalies}


def _block(evaluation) -> dict:
    return evaluation.observations["pyscf"]


def test_the_signal_is_declared_where_every_sensor_declares_itself():
    assert SIGNAL in ANOMALY_SIGNALS


# ----------------------------------------------------------------------
# what the sensor says, and what it deliberately does not
# ----------------------------------------------------------------------


@pytest.mark.capability("signal:scf.reference_unstable")
def test_an_unstable_closed_shell_reference_names_the_space_it_falls_in():
    """ "Externally unstable" is not one question.  A restricted reference
    is searched RHF/RKS -> UHF/UKS, and the observation carries that name
    rather than a boolean a reader would take for the other question."""

    evaluation = _evaluate("o2_singlet_sp_stability")
    anomaly = _signals(evaluation)[SIGNAL]
    assert anomaly["unstable_questions"] == ["external"]
    assert anomaly["unstable_rotation_spaces"] == ["RHF/RKS -> UHF/UKS"]
    assert anomaly["stable_rotation_spaces"] == ["internal"]
    # The question PySCF solves and returns only to its log stays named
    # as undetermined; it is neither an answer nor an absence.
    assert anomaly["not_determined_rotation_spaces"] == ["real -> complex"]
    assert anomaly["reference_family"] == "rks"
    assert anomaly["reference_converged"] is True
    assert anomaly["applies_to"] == "reference"
    # Never a verdict: no finding moves, and the same observation stands
    # on the HF reference, so it is not an artifact of the functional.
    assert not [item for item in evaluation.findings if "stab" in item]
    at_hf = _signals(_evaluate("o2_singlet_hf_sp_stability"))[SIGNAL]
    assert at_hf["unstable_rotation_spaces"] == ["RHF/RKS -> UHF/UKS"]
    assert at_hf["reference_family"] == "rhf"


@pytest.mark.capability("signal:scf.reference_unstable")
def test_an_open_shell_reference_falls_in_a_different_space():
    anomaly = _signals(_evaluate("o2_triplet_sp_stability"))[SIGNAL]
    assert anomaly["unstable_rotation_spaces"] == ["UHF/UKS -> GHF/GKS"]
    assert anomaly["reference_family"] == "uks"


@pytest.mark.capability("signal:scf.reference_unstable")
def test_a_delivered_frequency_can_stand_on_an_unstable_reference():
    """The case the sensor exists for: a Hessian whose receipt is
    `validated` with no finding, whose one real mode is a real number,
    computed on a reference that is not a minimum of its own method."""

    evaluation = _evaluate("o2_singlet_hess_stability", jobtype="hess")
    block = _block(evaluation)
    assert block["vibrational_mode_count"] == 1
    assert block["consequential_imaginary_mode_count"] == 0
    assert not evaluation.findings
    anomaly = _signals(evaluation)[SIGNAL]
    assert anomaly["unstable_rotation_spaces"] == ["RHF/RKS -> UHF/UKS"]
    assert anomaly["reference_converged"] is True


@pytest.mark.capability("signal:scf.reference_unstable")
def test_an_unconverged_reference_says_so_beside_its_answer():
    """PySCF answers about orbitals that are not stationary at all, and
    the observation carries that fact rather than letting a reader weigh
    this "unstable" like the converged one above."""

    anomaly = _signals(_evaluate("o2_singlet_sp_unconverged_stability"))[
        SIGNAL
    ]
    assert anomaly["reference_converged"] is False
    assert sorted(anomaly["unstable_questions"]) == ["external", "internal"]
    assert "internal" in anomaly["unstable_rotation_spaces"]


# ----------------------------------------------------------------------
# silence is never stability
# ----------------------------------------------------------------------


@pytest.mark.capability("signal:scf.reference_unstable")
@pytest.mark.parametrize(
    "case, has_record",
    (
        # asked, and every determined answer is stable
        ("water_sp_stability", True),
        ("water_sp_stability_cpcm", True),
        # asked, and PySCF has no external answer for an ROHF reference
        ("hydrogen_atom_sp_stability", True),
        # not asked: `not_requested`, which no reader takes for stable
        ("water_sp_no_stability", False),
        # written before the record existed: no field at all
        ("water_sp", False),
    ),
)
def test_four_different_silences_are_all_silent_and_none_is_stability(
    case, has_record
):
    evaluation = _evaluate(case)
    assert SIGNAL not in _signals(evaluation)
    record = _block(evaluation).get("reference_stability")
    assert (record is not None) is has_record, case
    if case == "hydrogen_atom_sp_stability":
        # The unavailable answer is named as unavailable, and the
        # internal answer that one combined call would have destroyed
        # survives beside it.
        assert [item["question"] for item in record["unavailable"]] == [
            "external"
        ]
        assert [item["question"] for item in record["stable"]] == ["internal"]
        assert record["unstable"] == []


def test_a_reader_that_cannot_say_says_nothing():
    """Every organ that asks reads one reader function.  A program with
    no such analysis answers None, which is not a stable reference."""

    for program, path in (
        ("orca", _ORCA / "phenol_pka_B.out"),
        (
            "xtb",
            _DATA
            / "XTBTests"
            / "outputs"
            / "acetaldehyde_hess"
            / "acetaldehyde_hess.out",
        ),
    ):
        reader = reader_for(program)
        assert reader.resolve_reference_diagnostics is None, program
        output = reader.open_output(path)
        assert reader.reference_diagnostics_for_output(output) is None


def test_a_gaussian_instability_that_was_repaired_is_history_not_state():
    """Gaussian's stability analysis is a *history*: a linked job finds an
    instability, reoptimises the wavefunction and ends stable.  The last
    verdict is the state of the reference the run delivered, and reading
    any earlier one would flag a reference Gaussian had already fixed."""

    reader = reader_for("gaussian")
    repaired = reader.reference_diagnostics_for_output(
        reader.open_output(str(_GAUSSIAN / "link" / "dna_link_sp.log"))
    )
    assert repaired["history"] == (
        "internal_instability",
        "stable_under_considered_perturbations",
    )
    assert repaired["unstable"] == ()
    assert repaired["stable"] == ({"question": "considered_perturbations"},)
    # And Gaussian names no rotation space, so the record invents none:
    # one program's "external" is two questions and the other's is one.
    assert "rotation_space" not in repaired["stable"][0]
    # A run that printed no verdict at all says nothing.
    assert (
        reader.reference_diagnostics_for_output(
            reader.open_output(str(_GAUSSIAN / "link" / "failed_link_job.log"))
        )
        is None
    )
    # And the same one step carries it into the second program's
    # observation block, so the sensor is not wired per program.
    path = (_GAUSSIAN / "link" / "dna_link_sp.log").resolve()
    evaluation = CommandCompiledToolHostV1._evaluate_execution_outputs(
        program="gaussian",
        jobtype="link",
        charge=0,
        multiplicity=1,
        output_artifacts=(
            TrustedArtifactRefV1(
                artifact_id="result.dna",
                kind="gaussian_output",
                sha256=file_sha256(path),
                size_bytes=path.stat().st_size,
                path=str(path),
                cli_value=str(path),
            ),
        ),
        exit_status=0,
    )
    carried = evaluation.observations["gaussian"]["reference_stability"]
    assert carried["verdict"] == "stable_under_considered_perturbations"
    assert SIGNAL not in _signals(evaluation)


# ----------------------------------------------------------------------
# and a number standing on it is named where a human reads one word
# ----------------------------------------------------------------------


@pytest.mark.capability("signal:scf.reference_unstable")
def test_a_number_standing_on_an_unstable_reference_is_named_at_settlement(
    tmp_path,
):
    """The anomaly flags the node's own artifacts, and the delivery walk
    that already names numbers standing on a flagged result carries the
    word into the settlement.  No second mechanism: the sensor is the
    whole of the change, and this is what it buys."""

    from chemsmart.agent.driver import (
        _achieved_word,
        _analysis_delivery,
        _flagged_artifact_sha256s,
    )

    evaluation = _evaluate("o2_singlet_hess_stability", jobtype="hess")
    (artifact,) = [
        item
        for item in _artifacts(
            "o2_singlet_hess_stability",
            "o2_singlet_hess_stability_gas_phase",
        )
        if item.kind == "pyscf_hdf5"
    ]
    observation = build_anomaly_observation(
        node_id="hess-o2",
        program="pyscf",
        jobtype="hess",
        signal_id=SIGNAL,
        values={
            key: value
            for key, value in _signals(evaluation)[SIGNAL].items()
            if key != "signal_id"
        },
        source_receipt_sha256="a" * 64,
        flagged_artifact_sha256s=(artifact.sha256,),
    )
    rows = [
        {
            "kind": "result_quantities_extracted",
            "payload": {
                "receipt_sha256": "1" * 64,
                "artifact_sha256": artifact.sha256,
                "record": {},
            },
        },
        {
            "kind": "analysis_claims_recorded",
            "payload": {
                "receipt_sha256": "2" * 64,
                "record": {
                    "claims": [
                        {
                            "claim_id": "o2_stretch_cm1",
                            "quantity_id": "o2_stretch_cm1",
                            "source_receipt_sha256": "1" * 64,
                        }
                    ]
                },
            },
        },
    ]
    stream = tmp_path / "events.jsonl"
    stream.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    records = [json.loads(json.dumps(observation, default=vars))]
    flagged = _flagged_artifact_sha256s(records)
    assert flagged == (artifact.sha256,)
    delivery = _analysis_delivery(stream, flagged_artifact_sha256s=flagged)
    assert delivery.flagged_quantity_ids == ("o2_stretch_cm1",)
    word, reasons = _achieved_word(delivery, records)
    assert word == "achieved_with_observations"
    assert any(
        "delivered from the flagged result: o2_stretch_cm1" in reason
        for reason in reasons
    )
    assert any(SIGNAL in reason for reason in reasons)
