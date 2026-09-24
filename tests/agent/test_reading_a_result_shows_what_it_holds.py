"""Reading a finished result shows what each of its selectors holds.

``inspect_run`` with a program and an artifact probes every accessor to
learn which selectors the result resolves, and used to discard the value
it had just read: a session saw the name of a printed stability
eigenvalue or <S^2> and never the number unless it thought to ask. With
``CHEMSMART_AGENT_INSPECTION_VALUES`` on (a research setting, off by
default), the reply carries each requestable selector's value as the
extraction tool would return it. These pin the one invariant that makes
the reply evidence rather than a second reading of the file: a value shown
on inspection is the value the extraction receipt carries, through the
same function, on real archived output of three programs.
"""

from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]

REAL_RESULTS = (
    (
        "pyscf",
        "pyscf_hdf5",
        "tests/data/PySCFTests/outputs/o2_singlet_sp_stability_heard/"
        "o2_singlet_sp_stability_heard_gas_phase.h5",
    ),
    ("orca", "orca_output", "tests/data/ORCATests/outputs/fe3_doublet.out"),
    (
        "gaussian",
        "gaussian_output",
        "tests/data/GaussianTests/stability/g_o2_singlet_stable_gas_phase.log",
    ),
)


def _host(tmp_path):
    from chemsmart.agent.runtime.event_store import RuntimeEventStore
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="inspection-values"
        ),
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )


def _bind(host, artifact_id, kind, relative):
    from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256

    path = ROOT / relative
    host.artifacts[artifact_id] = TrustedArtifactRefV1(
        artifact_id=artifact_id,
        kind=kind,
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=str(path),
    )


@pytest.mark.capability("tool:inspect_run")
@pytest.mark.parametrize("program,kind,relative", REAL_RESULTS)
def test_a_value_shown_on_inspection_is_the_value_extraction_returns(
    tmp_path, monkeypatch, program, kind, relative
):
    from chemsmart.agent.tool_runtime import _inspection_value

    monkeypatch.setenv("CHEMSMART_AGENT_INSPECTION_VALUES", "1")
    host = _host(tmp_path)
    _bind(host, "result", kind, relative)

    inspected = host._inspect_run(
        "t1", {"program": program, "artifact_id": "result"}
    )
    shown = inspected["values"]
    requestable = tuple(inspected["requestable_selectors"])
    assert requestable and set(shown) == set(requestable)

    receipt = host._extract_result_quantities(
        "t2",
        {
            "program": program,
            "artifact_id": "result",
            "selectors": [
                {"quantity_id": selector, "selector": selector}
                for selector in requestable
            ],
        },
    )
    from chemsmart.agent._contracts import canonical_data

    extracted = {
        quantity.quantity_id: quantity for quantity in receipt.quantities
    }
    assert set(extracted) == set(requestable)
    for selector in requestable:
        assert shown[selector]["unit"] == extracted[selector].unit, selector
        assert shown[selector]["value"] == _inspection_value(
            canonical_data(extracted[selector].value)
        ), selector


@pytest.mark.capability("tool:inspect_run")
def test_the_number_that_says_a_result_is_unsound_is_on_the_reply(
    tmp_path, monkeypatch
):
    """The quantities a reviewer reads first reach the reply as numbers:
    the unstable rotation spaces of a closed-shell singlet O2 and their
    eigenvalues, and the <S^2> of a spin-contaminated Fe(III) doublet
    beside its target and its unconverged optimisation."""

    monkeypatch.setenv("CHEMSMART_AGENT_INSPECTION_VALUES", "1")
    host = _host(tmp_path)
    for index, (_program, kind, relative) in enumerate(REAL_RESULTS):
        _bind(host, f"r{index}", kind, relative)

    o2 = host._inspect_run("t1", {"program": "pyscf", "artifact_id": "r0"})[
        "values"
    ]
    assert o2["scf_stability_external"]["value"] == "unstable"
    assert o2["scf_stability_real_to_complex"]["value"] == "unstable"
    assert o2["scf_stability_internal"]["value"] == "stable"
    assert (
        -0.0927
        < o2["scf_stability_external_lowest_eigenvalue"]["value"]
        < -0.0925
    )

    fe = host._inspect_run("t2", {"program": "orca", "artifact_id": "r1"})[
        "values"
    ]
    assert fe["spin_square"]["value"] == pytest.approx(1.70473)
    assert fe["spin_square_target"]["value"] == pytest.approx(0.75)
    assert fe["converged"]["value"] == 0
    # a matrix past the printed size is shown by its shape, never cut
    # silently: 13 atoms make a 169-cell connectivity matrix
    assert fe["connectivity"]["value"]["cells"] == 169


@pytest.mark.capability("tool:inspect_run")
def test_off_the_reply_names_selectors_and_shows_no_value(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("CHEMSMART_AGENT_INSPECTION_VALUES", raising=False)
    host = _host(tmp_path)
    _bind(host, "result", *REAL_RESULTS[0][1:])
    inspected = host._inspect_run(
        "t1", {"program": "pyscf", "artifact_id": "result"}
    )
    assert "values" not in inspected
    assert "scf_stability_external" in inspected["requestable_selectors"]
