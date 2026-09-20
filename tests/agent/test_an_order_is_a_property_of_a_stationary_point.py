"""An order is a claim about a geometry, on a surface, from a Hessian
taken there, at a gradient that says the point is stationary at all.

``characterise_stationary_point`` checked one of those four -- the count
of imaginary modes -- and so certified structures that are stationary
points of nothing: the archived ``water_stretched_hess``, three real
modes at max|g| = 0.0185 Eh/Bohr and forty-one times geomeTRIC's own
criterion, came back "a minimum" on the very artifact the host's sensor
flags; live, a UHF/3-21G methoxy saddle read on the B3LYP/def2-SVP
surface at 0.0485 Eh/Bohr came back order 1 (CUHK g5-methoxy,
2026-09-20).

This module is also here because the repair went missing once. It was
verified with a throwaway probe and pinned by no test, a later rebase of
the working tree reverted the file, and the whole suite stayed green over
a commit message describing code that was not in the tree. A witness that
was never red witnesses nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.agent._contracts import (
    ContractError,
    TrustedArtifactRefV1,
    canonical_sha256,
    file_sha256,
)
from chemsmart.agent.execution import (
    StationaryPointCharacterisationV1,
    build_stationary_point_characterisation,
)
from chemsmart.agent.terminal_states import (
    HESS_STATIONARITY_GRADIENT_EH_PER_BOHR,
)
from chemsmart.analysis.result_readers import reader_for

FIXTURES = (
    Path(__file__).resolve().parents[1] / "data" / "PySCFTests" / "outputs"
)

pytestmark = pytest.mark.capability("tool:characterise_stationary_point")


def _artifact(relative: str) -> TrustedArtifactRefV1:
    path = (FIXTURES / relative).resolve()
    return TrustedArtifactRefV1(
        artifact_id="pyscf-result-probe",
        kind="pyscf_hdf5",
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=path.name,
    )


@pytest.mark.capability("policy:hess_stationarity_gradient")
def test_a_non_stationary_geometry_has_no_order():
    """The real artifact this organ used to call a minimum."""

    relative = "water_stretched_hess/water_stretched_hess_gas_phase.h5"
    output = reader_for("pyscf").open_output(FIXTURES / relative)
    gradient = reader_for("pyscf").stationarity_gradient_for_output(output)
    assert gradient > HESS_STATIONARITY_GRADIENT_EH_PER_BOHR
    # Its spectrum is entirely real: a mode count alone says "minimum".
    assert all(float(value) > 0 for value in output.vibrational_frequencies)

    with pytest.raises(ContractError) as refusal:
        build_stationary_point_characterisation(
            result_artifact=_artifact(relative),
            program="pyscf",
            order_claimed=0,
        )
    report = getattr(refusal.value, "failure_report", {})
    assert report.get("gate") == "result.order_needs_a_stationary_point"
    # The refusal names both numbers and leaves the science reachable.
    assert f"{gradient:.4g}" in report["diagnosis"]
    assert f"{HESS_STATIONARITY_GRADIENT_EH_PER_BOHR:g}" in report["diagnosis"]
    assert "readable and deliverable" in report["route"]
    assert "relax the structure on this same surface" in report["route"]


@pytest.mark.parametrize(
    ("relative", "order", "surface_recorded"),
    [
        ("h2co_hcoh_ts_hess/h2co_ts_hess_gas_phase.h5", 1, True),
        ("hcn_hnc_ts_hess/hcn_ts_hess_gas_phase.h5", 1, True),
        # A contract older than the surface record: the order still
        # certifies and the receipt simply carries no surface token.
        ("nh3_planar_hess/nh3_planar_hess_gas_phase.h5", 1, False),
        ("water_hess/water_hess_gas_phase.h5", 0, False),
    ],
)
def test_a_stationary_point_certifies_and_names_what_it_stands_on(
    relative, order, surface_recorded
):
    receipt = build_stationary_point_characterisation(
        result_artifact=_artifact(relative),
        program="pyscf",
        order_claimed=order,
    )
    assert receipt.order_claimed == order
    assert receipt.stationarity == "stationary"
    assert (
        0.0
        <= receipt.max_abs_gradient_eh_per_bohr
        <= HESS_STATIONARITY_GRADIENT_EH_PER_BOHR
    )
    # Which structure the order is about.
    assert len(receipt.geometry_sha256) == 64
    assert bool(receipt.surface_id) is surface_recorded
    # And every field the host determined is inside the digest.
    assert receipt.receipt_sha256 == canonical_sha256(receipt._body())


def test_a_receipt_minted_before_this_round_still_verifies():
    """The three fields enter the body only where the host determined
    them, so an ORCA characterisation carrying none of them -- every one
    ever minted -- reconstructs under the same arithmetic."""

    body = {
        "schema_version": "chemsmart.stationary-point-characterisation.v1",
        "result_artifact_sha256": "a" * 64,
        "program": "orca",
        "node_id": "ts",
        "order_claimed": 1,
        "observed_imaginary_modes": 1,
        "anomaly_sha256": "",
        "lowest_imaginary_cm_1": -1121.05,
    }
    receipt = StationaryPointCharacterisationV1(
        **body, receipt_sha256=canonical_sha256(body)
    )
    assert receipt.stationarity == ""
    assert receipt.surface_id == "" and receipt.geometry_sha256 == ""


def test_a_program_that_cannot_bind_a_gradient_says_unmeasured():
    """ORCA's and Gaussian's ``forces`` are the gradient at every
    optimisation step, so a maximum over them belongs to no single
    geometry. Those readers answer nothing here rather than a number read
    from the wrong structure, and nothing reads that as stationarity."""

    for program in ("orca", "gaussian", "xtb"):
        assert (
            reader_for(program).resolve_stationarity_gradient is None
        ), program
    assert reader_for("pyscf").resolve_stationarity_gradient is not None


def test_the_word_is_one_of_two_and_never_invented():
    body = {
        "schema_version": "chemsmart.stationary-point-characterisation.v1",
        "result_artifact_sha256": "a" * 64,
        "program": "pyscf",
        "node_id": "",
        "order_claimed": 1,
        "observed_imaginary_modes": 1,
        "anomaly_sha256": "",
        "stationarity": "above_optimizer_criterion",
    }
    with pytest.raises(ContractError, match="stationary' or 'unmeasured"):
        StationaryPointCharacterisationV1(
            **body, receipt_sha256=canonical_sha256(body)
        )
