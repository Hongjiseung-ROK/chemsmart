"""A Hessian that confirms a saddle has not failed.

ORCA runs ``OptTS Freq`` as one node, so the one imaginary mode it finds
is what ``ts`` promised. PySCF and xTB split the same physics into a
search and a Hessian, and the Hessian half was judged as though it were a
minimum's: two live goals ran a PySCF ``hess`` on the saddle a PySCF
``ts`` node had just located, and both were typed
``failed_wrong_stationary_point`` for containing exactly the one
imaginary mode they were run to find (CUHK 2141228 g2-h2co-foreign-saddle
and 2141230 g4-hooh-rotation, 2026-09-20). Neither session reached
``characterise_stationary_point``, the affordance that existed for it.

The promise was never about the Hessian. It is about the structure, and
the node that produced the structure already said what it was searching
for, so a fixed-geometry curvature node inherits it.

It reads both ways, and that is the point. A saddle search that
converges onto a minimum cannot detect that itself -- its artifact
carries no spectrum of what it reached -- and a live goal did exactly
that (g3-h2co-elimination cycle 1, a seed with one imaginary mode
relaxing 1.87 amu^1/2 bohr back to formaldehyde, ``validated``). The
Hessian on such a structure now fails the promise its producer made
instead of validating as a minimum nobody asked for.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.terminal_states import (
    FIXED_GEOMETRY_CURVATURE_JOBTYPES,
    STATIONARY_POINT_PROMISES,
    expected_imaginary_mode_count,
    stationary_point_order_finding,
)
from chemsmart.agent.tool_runtime import (
    CommandCompiledToolHostV1,
    _input_result_jobtype,
)
from tests.agent.test_every_archived_pyscf_result_reaches_its_verdict import (
    _outputs,
    _settings,
    _spec,
)

FIXTURES = (
    Path(__file__).resolve().parents[1] / "data" / "PySCFTests" / "outputs"
)

pytestmark = pytest.mark.capability("program_jobtype:pyscf:cpu:hess")


def _artifact(relative: str) -> TrustedArtifactRefV1:
    path = (FIXTURES / relative).resolve()
    return TrustedArtifactRefV1(
        artifact_id="producer",
        kind="pyscf_hdf5",
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=path.name,
    )


def test_the_promise_is_inherited_only_by_a_curvature_node():
    assert FIXED_GEOMETRY_CURVATURE_JOBTYPES == {"freq", "hess"}
    # A node that moves the structure keeps its own promise.
    assert expected_imaginary_mode_count("ts", "opt") == 1
    assert expected_imaginary_mode_count("opt", "ts") == 0
    # A curvature node takes its producer's.
    assert expected_imaginary_mode_count("hess", "ts") == 1
    assert expected_imaginary_mode_count("freq", "ts") == 1
    assert expected_imaginary_mode_count("hess", "opt") == 0
    # A bare geometry promises nothing, so the node keeps its own.
    assert expected_imaginary_mode_count("hess", "") == 0
    assert (
        expected_imaginary_mode_count("hess", "sp")
        == STATIONARY_POINT_PROMISES["hess"]
    )


def test_it_reads_both_ways():
    assert stationary_point_order_finding("hess", 1, "ts") == ""
    assert stationary_point_order_finding("hess", 0, "ts") == (
        "result.stationary_point_order"
    )
    assert stationary_point_order_finding("hess", 0, "opt") == ""
    assert stationary_point_order_finding("hess", 1, "opt") == (
        "result.stationary_point_order"
    )
    # Nothing printed makes no claim, whatever the producer promised.
    assert stationary_point_order_finding("hess", None, "ts") == ""


@pytest.mark.parametrize(
    ("case", "label", "producer", "findings"),
    [
        # The two the live goals lost.
        (
            "h2co_hcoh_ts_hess",
            "h2co_ts_hess_gas_phase",
            "h2co_hcoh_ts/h2co_ts_gas_phase.h5",
            (),
        ),
        (
            "hcn_hnc_ts_hess",
            "hcn_ts_hess_gas_phase",
            "hcn_hnc_ts/hcn_ts_gas_phase.h5",
            (),
        ),
        # An optimisation that landed on a saddle still fails, which is
        # the case the rule was built for.
        (
            "nh3_planar_hess",
            "nh3_planar_hess_gas_phase",
            "nh3_planar_opt/nh3_planar_opt_gas_phase.h5",
            ("result.stationary_point_order",),
        ),
        (
            "water_hess",
            "water_hess_gas_phase",
            "water_opt/water_opt_gas_phase.h5",
            (),
        ),
    ],
)
def test_the_evaluator_agrees_over_real_bytes(case, label, producer, findings):
    source = _artifact(producer)
    spec = _spec(case, label)
    assert _input_result_jobtype(source) in STATIONARY_POINT_PROMISES
    evaluation = CommandCompiledToolHostV1._evaluate_execution_outputs(
        program="pyscf",
        jobtype=str(spec["jobtype"]),
        charge=int(spec["charge"]),
        multiplicity=int(spec["multiplicity"]),
        expected_settings=_settings(spec),
        expected_input_artifact=source,
        output_artifacts=_outputs(case, label),
        exit_status=0,
    )
    assert evaluation.findings == findings, case


def test_a_geometry_file_promises_nothing():
    """Only a result says what it was searching for."""

    path = (FIXTURES / "inputs" / "h2co_ts_seed.xyz").resolve()
    geometry = TrustedArtifactRefV1(
        artifact_id="seed",
        kind="geometry_xyz",
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=path.name,
    )
    assert _input_result_jobtype(geometry) == ""
    assert _input_result_jobtype(None) == ""
