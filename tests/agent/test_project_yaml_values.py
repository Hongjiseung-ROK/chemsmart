"""Focused regression coverage for project-YAML value normalization."""

from __future__ import annotations

import pytest

from chemsmart.agent.project_yaml import render_project_yaml
from chemsmart.agent.project_yaml_values import normalize_solvent_id
from chemsmart.io.xtb import XTB_ALL_SOLVENT_IDS


def test_xtb_solvent_inventory_is_identity_preserved() -> None:
    assert len(XTB_ALL_SOLVENT_IDS) == 27
    assert len(set(XTB_ALL_SOLVENT_IDS)) == 27
    assert {
        solvent_id: normalize_solvent_id(solvent_id)
        for solvent_id in XTB_ALL_SOLVENT_IDS
    } == {solvent_id: solvent_id for solvent_id in XTB_ALL_SOLVENT_IDS}


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        ("N-HEXANE", "n-hexane"),
        ("n hexane", "n-hexane"),
        ("n_hexane", "n-hexane"),
        ("nhexane", "n-hexane"),
        ("tetrahydrofuran", "thf"),
        ("Tetrahydrofuran", "thf"),
        ("H2O", "h2o"),
        ("CH2CL2", "ch2cl2"),
    ),
)
def test_common_xtb_solvent_aliases_are_canonicalized(
    raw: str,
    expected: str,
) -> None:
    assert normalize_solvent_id(raw) == expected


def test_all_xtb_solvents_survive_paper_render_and_loader_validation() -> None:
    for solvent_id in XTB_ALL_SOLVENT_IDS:
        rendered = render_project_yaml(
            {
                "program": "xtb",
                "method": {
                    "gfn_version": "gfn2",
                    "optimization_level": "normal",
                    "solvent_model": "gbsa",
                    "solvent_id": solvent_id,
                },
            },
            project_name=f"xtb-solvent-{solvent_id}",
            program="xtb",
            profile="paper",
            required_job_kinds=("sp", "opt", "hess"),
        )

        assert rendered["validation"]["verdict"] == "ok", solvent_id
        for job_kind in ("sp", "opt", "hess"):
            assert (
                rendered["validation"]["parsed"][job_kind]["solvent_id"]
                == solvent_id
            )
            assert (
                rendered["validation"]["runtime_summary"][job_kind][
                    "solvent_id"
                ]
                == solvent_id
            )
