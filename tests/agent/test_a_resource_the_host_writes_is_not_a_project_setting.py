"""ORCA's cores and memory are the grant's, and a project cannot restate them.

CHEMSMART writes ``%pal nprocs <cores>`` and ``%maxcore <MB per core>``
into every ORCA input from the resources the run is granted. The tool
sentence said so ("CPU count and memory belong to the ChemSmart
run/server layer, not project additional_route_parameters") and so did
the stem rule that hardware is the host's. It did not hold: a DLPNO
triples step died asking ORCA's own question -- "Please increase
MaxCore", 1416.5 MB needed against 1044.7 MB available at
``%maxcore 1500`` -- and the revision wrote ``MaxCore 1800`` into
``additional_route_parameters``. The preview verifier found those tokens
on the ``!`` line and passed it; ORCA refused the keyword line and the
engine call was spent (R10 Q6 pair3-b, CUHK Slurm 2150179, cycle 3;
deepseek-v4-flash-0731). A resource is not a method: the refusal belongs
where the project is loaded, and it says whose number that is.

Driven through ``validate_project_yaml``, the session's own tool.
"""

from __future__ import annotations

import pytest

from .gaussian_fake_preview import validate


def _sections(route: str) -> dict:
    return {
        "gas": {
            "ab_initio": "dlpno-ccsd(t)",
            "basis": "def2-tzvp",
            "aux_basis": "def2-tzvp/c",
            "additional_route_parameters": route,
        }
    }


@pytest.mark.capability("setting:orca:additional_route_parameters")
@pytest.mark.parametrize(
    "route",
    [
        "MaxCore 1800",
        "%maxcore 1800",
        "TightPNO maxcore=2000",
        "PAL8",
        "%pal nprocs 16 end",
    ],
)
def test_a_resource_on_the_route_is_refused_naming_whose_it_is(
    tmp_path, route
):
    _project, receipt = validate(tmp_path, "orca", _sections(route), "sp")

    assert receipt.status == "invalid"
    assert receipt.rule_ids == ("project.loader.rejected",)
    diagnostic = receipt.diagnostic
    assert "%maxcore" in diagnostic and "%pal" in diagnostic
    assert "granted" in diagnostic


@pytest.mark.capability("setting:orca:additional_route_parameters")
def test_a_scientific_token_on_the_route_still_loads(tmp_path):
    """The refusal is the grant's vocabulary and nothing wider."""

    _project, receipt = validate(
        tmp_path, "orca", _sections("TightPNO Hirshfeld"), "sp"
    )

    assert receipt.status == "valid", receipt.diagnostic
    assert dict(receipt.settings)["additional_route_parameters"] == (
        "TightPNO Hirshfeld"
    )
