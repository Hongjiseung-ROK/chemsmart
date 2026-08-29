"""PySCF writes its own typed account of a death -- the stage that
raised, and per-stage convergence flags for the quiet failures that
raise nothing -- and nothing read it: the native-failure consumer
iterated a "pyscf" branch no producer ever fed, so every PySCF death
collapsed to the generic bucket, indistinguishable across SCF,
optimizer, and driver failures.
"""

import json

import pytest

from chemsmart.agent.terminal_states import _classify_failure, _native_failure
from chemsmart.io.native_failure import summarize_pyscf_native_failure


def test_an_exception_is_classified_by_its_recorded_stage():
    summary = summarize_pyscf_native_failure(
        {
            "normal_termination": False,
            "failure": {
                "type": "RuntimeError",
                "message": "SCF did not converge after 200 cycles",
                "stage": "scf",
            },
        }
    )
    assert summary is not None
    assert summary.error_class == "scf_convergence"
    assert summary.termination_state == "error_termination"
    assert summary.engine_lines == (
        "RuntimeError: SCF did not converge after 200 cycles",
    )


def test_a_quiet_unconverged_scf_is_incomplete_not_silent():
    summary = summarize_pyscf_native_failure(
        {
            "normal_termination": False,
            "stages": {"scf": {"converged": False}},
        }
    )
    assert summary is not None
    assert summary.error_class == "scf_convergence"
    assert summary.termination_state == "incomplete"


def test_the_optimizer_and_its_final_scf_are_different_deaths():
    optimizer = summarize_pyscf_native_failure(
        {
            "normal_termination": False,
            "stages": {
                "opt": {
                    "optimizer_converged": False,
                    "final_scf_converged": True,
                }
            },
        }
    )
    assert optimizer is not None
    assert optimizer.error_class == "geometry_optimization"

    final_scf = summarize_pyscf_native_failure(
        {
            "normal_termination": False,
            "stages": {
                "opt": {
                    "optimizer_converged": False,
                    "final_scf_converged": False,
                }
            },
        }
    )
    assert final_scf is not None
    assert final_scf.error_class == "scf_convergence"


def test_a_normal_termination_needs_no_account():
    assert summarize_pyscf_native_failure({"normal_termination": True}) is (
        None
    )
    assert summarize_pyscf_native_failure({}) is None
    assert summarize_pyscf_native_failure(None) is None


def test_the_dead_consumer_branch_is_alive():
    """terminal_states iterated ("orca","xtb","gaussian","pyscf") but
    no producer ever fed the pyscf key; with the account recorded, the
    stage flows through to the typed ending."""

    observations = {
        "pyscf": {
            "native_failure": {
                "error_class": "scf_convergence",
                "engine_lines": ("RuntimeError: SCF did not converge",),
            }
        }
    }
    native_class, engine_lines = _native_failure(observations)
    assert native_class == "scf_convergence"
    assert engine_lines

    assert (
        _classify_failure(
            findings=("pyscf.native_failure.scf_convergence",),
            native_class=native_class,
            converged=None,
            reached=None,
            planned=None,
            jobtype="sp",
        )
        == "failed_nonconverged_scf"
    )


def test_the_evaluator_records_the_account_from_the_artifact(tmp_path):
    h5py = pytest.importorskip("h5py")
    import hashlib as _hashlib

    from chemsmart.agent.execution import TrustedArtifactRefV1
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    path = tmp_path / "job.h5"
    with h5py.File(path, "w") as handle:
        handle.attrs["schema_version"] = "1.0"
        handle.create_dataset(
            "spec", data=json.dumps({"program": "pyscf", "engine": "cpu"})
        )
        handle.create_dataset("provenance", data=json.dumps({}))
        handle.create_dataset(
            "status",
            data=json.dumps(
                {
                    "normal_termination": False,
                    "failure": {
                        "type": "RuntimeError",
                        "message": "SCF did not converge",
                        "stage": "scf",
                    },
                }
            ),
        )
        handle.create_group("results")
    from chemsmart.agent._contracts import canonical_sha256

    receipt_body = {
        "schema_version": "chemsmart.pyscf-run.v1",
        "child_returncode": 1,
        "fake": False,
    }
    receipt_path = tmp_path / "pyscf-run-receipt.json"
    receipt_path.write_text(
        json.dumps(
            dict(
                receipt_body, receipt_sha256=canonical_sha256(receipt_body)
            )
        ),
        encoding="utf-8",
    )

    def _artifact(artifact_id, kind, file_path):
        return TrustedArtifactRefV1(
            artifact_id=artifact_id,
            kind=kind,
            sha256=_hashlib.sha256(file_path.read_bytes()).hexdigest(),
            size_bytes=file_path.stat().st_size,
            path=str(file_path),
            cli_value=str(file_path),
        )

    evaluation = CommandCompiledToolHostV1._evaluate_execution_outputs(
        program="pyscf",
        jobtype="sp",
        charge=0,
        multiplicity=1,
        output_artifacts=(
            _artifact("receipt.pyscf.1", "json", receipt_path),
            _artifact("result.pyscf.1", "pyscf_hdf5", path),
        ),
        exit_status=1,
    )
    assert "pyscf.native_failure.scf_convergence" in evaluation.findings
    pyscf_observation = evaluation.observations.get("pyscf") or {}
    account = pyscf_observation.get("native_failure") or {}
    assert account.get("error_class") == "scf_convergence"
