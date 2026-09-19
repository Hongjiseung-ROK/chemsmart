"""A Hessian on a reached geometry lifted in a later cycle characterises
the optimisation it came from, on that optimisation's surface only.

A woken session holds no earlier workflow, so the producer edge that
joins an optimisation to its Hessian in one run cannot be drawn after the
fact; the route the host offers is bind_reached_geometry and a new plan.
On pak-g1-formaldehyde (2026-09-19) that route ran an excited-root
Hessian at the geometry the S1 optimisation reached -- all six modes
real, gradient 3.5e-5 Eh/Bohr -- and the settlement still called every
number read from the optimisation "uncharacterised (no frequencies
printed)", because the lift writes a new file and the record joined only
producer edges. The lineage receipt now reaches the workspace record,
and the join asks the recorded surfaces, so a ground-state Hessian at an
excited geometry, or a DFT Hessian at an MP2 minimum, is still not
credited.

Every surface here was written by the host's own evaluator from an
archived result, never by this test.
"""

from __future__ import annotations

import json

import pytest

from chemsmart.agent.workspace_record import (
    read_workspace_record,
    record_run,
    uncharacterised_artifacts,
)
from chemsmart.analysis.result_readers import surfaces_agree

from .test_a_hessian_characterises_only_its_own_surface import (
    _artifacts,
    _verified_record,
)

pytestmark = pytest.mark.capability("program_jobtype:pyscf:cpu:hess")

REACHED = "c" * 64

#: producer, consumer, and whether the two recorded surfaces agree.
_PAIRS = (
    ("water_dft_opt_v6", "water_dft_hess_on_dft_geometry", True),
    # A DFT Hessian at an MP2 minimum is another surface's curvature.
    ("water_mp2_opt_v6", "water_dft_hess_on_mp2_geometry", False),
    # The excited-root optimisation was archived before results recorded
    # a surface; the root's own Hessian beside it records one. A
    # comparison that cannot be made is not a match.
    ("formaldehyde_s1_opt_planar", "formaldehyde_s1_planar_hess", None),
)


def _live_shape(case, node_id):
    """The verified record as a live stream carries it."""

    record = _verified_record(case, node_id)
    record["program"] = "pyscf"
    record["output_artifacts"] = _typed_outputs(case)
    return record


def _typed_outputs(case):
    _label, outputs = _artifacts(case)
    return [
        {"kind": artifact.kind, "sha256": artifact.sha256}
        for artifact in outputs
    ]


def _run(tmp_path, name, record):
    path = tmp_path / name / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"kind": "program_result_verified", "payload": {"record": record}}
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _session(tmp_path, source_sha256):
    """The receipt bind_reached_geometry leaves in the planning stream."""

    path = tmp_path / "session" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "kind": "reached_geometry_bound",
                "payload": {
                    "record": {
                        "reached_artifact_sha256": REACHED,
                        "source_result_sha256": source_sha256,
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _workspace(tmp_path, producer, consumer, *, lineage):
    opt = _live_shape(producer, "ex-opt")
    hess = _live_shape(consumer, "hess-ex")
    hess["input_artifact_sha256"] = REACHED
    workspace = tmp_path / "ws"
    record_run(
        workspace,
        goal_id="g",
        cycle=1,
        run_events_path=_run(tmp_path, "cycle-1", opt),
        run="goals/g/runs/cycle-1",
    )
    (opt_row,) = read_workspace_record(workspace)
    session = _session(tmp_path, opt_row["result_artifact_sha256"])
    record_run(
        workspace,
        goal_id="g",
        cycle=2,
        run_events_path=_run(tmp_path, "cycle-2", hess),
        run="goals/g/runs/cycle-2",
        lineage_events_paths=(session,) if lineage else (),
    )
    return workspace, opt_row["result_artifact_sha256"]


@pytest.mark.parametrize("producer,consumer,agree", _PAIRS)
def test_a_lifted_hessian_characterises_only_its_own_surface(
    tmp_path, producer, consumer, agree
):
    workspace, opt_result = _workspace(
        tmp_path, producer, consumer, lineage=True
    )
    opt_row, hess_row = (
        e for e in read_workspace_record(workspace) if e["kind"] == "result"
    )
    assert hess_row["geometry_source_result_sha256"] == opt_result
    assert surfaces_agree(opt_row["surface"], hess_row["surface"]) is agree
    assert (opt_result in uncharacterised_artifacts(workspace)) is (
        agree is not True
    )


def test_without_the_lineage_receipt_nothing_is_joined(tmp_path):
    workspace, opt_result = _workspace(tmp_path, *_PAIRS[0][:2], lineage=False)
    assert opt_result in uncharacterised_artifacts(workspace)
