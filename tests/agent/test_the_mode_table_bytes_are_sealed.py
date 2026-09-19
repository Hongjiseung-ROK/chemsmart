"""A delivered mode row names every native table it stood on.

xTB writes the vibrational spectrum and the normal coordinates to two
different sidecars: ``vibspectrum`` carries the frequency and IR columns,
``g98.out`` carries the displacement vectors.  The reader serves
``vibrational_frequencies`` and ``ir_intensities`` from the first and
``vibrational_mode_atom_participation`` from the second.  The IR repair
sealed the spectrum table into its receipts; the two mode selectors were
left sealing nothing, so their delivered rows stood on bytes no receipt
named.

What is NOT witnessed here, because it was looked for and not found: seven
real GFN2 Hessians -- formamide, HCN (linear), tetrahedral methane and
pyramidal ammonia (degenerate sets), planar ammonia, square-planar methane
and a distorted ethane (one, two and five imaginary modes) -- agree between
the two tables row for row to at most 0.0050 cm^-1, which is two-decimal
against four-decimal printing.  No row-identity guard was earned by that
evidence, and none is pinned.

The two results here were computed for that question on CUHK Charles with
xTB 6.7.1 through the ordinary ChemSmart CLI (GFN2, ``xtb ... hess``), and
are the first archived xTB results carrying imaginary modes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.postprocessing import (
    extract_trusted_result_quantities,
    typed_result_artifact_kind,
)
from chemsmart.analysis.result_quantities import QuantitySelectorV1

_PARTICIPATION = "vibrational_mode_atom_participation"
_DEGENERACY = "vibrational_mode_degeneracy_group"
_FREQUENCIES = "vibrational_frequencies"

_OUTPUTS = Path("tests/data/XTBTests/outputs")
_MINIMUM = _OUTPUTS / "methane_td_hess" / "methane_td_hess.out"
_SADDLE = _OUTPUTS / "methane_planar_hess" / "methane_planar_hess.out"


def _artifact(path: Path) -> TrustedArtifactRefV1:
    resolved = path.resolve()
    return TrustedArtifactRefV1(
        artifact_id="xtb-hess",
        kind=typed_result_artifact_kind("xtb"),
        sha256=file_sha256(resolved),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )


def _extract(path: Path, *selectors: str):
    return extract_trusted_result_quantities(
        artifact=_artifact(path),
        program="xtb",
        selectors=tuple(
            QuantitySelectorV1(quantity_id=name, selector=name)
            for name in selectors
        ),
    )


@pytest.mark.capability(
    "selector:xtb:hess:vibrational_mode_atom_participation"
)
@pytest.mark.capability("selector:xtb:hess:vibrational_mode_degeneracy_group")
def test_the_mode_table_bytes_are_sealed_where_the_rows_are_read():
    receipt = _extract(_MINIMUM, _PARTICIPATION, _DEGENERACY)
    sealed = {
        (selector, filename)
        for selector, filename, _ in receipt.native_evidence
    }

    # Participation reads the displacement vectors of one table and shares
    # its row index with the frequency list of another, so both are sealed.
    assert (_PARTICIPATION, "g98.out") in sealed
    assert (_PARTICIPATION, "vibspectrum") in sealed
    # The degeneracy grouping reads only the frequency column.
    assert (_DEGENERACY, "vibspectrum") in sealed
    assert (_DEGENERACY, "g98.out") not in sealed

    digests = {
        filename: digest for _, filename, digest in receipt.native_evidence
    }
    assert digests["g98.out"] == file_sha256(_MINIMUM.parent / "g98.out")
    assert digests["vibspectrum"] == file_sha256(
        _MINIMUM.parent / "vibspectrum"
    )


@pytest.mark.parametrize(
    ("artifact", "imaginary"), ((_MINIMUM, 0), (_SADDLE, 2))
)
def test_a_real_hessian_delivers_every_mode_row(artifact, imaginary):
    """The saddle is the harder half: both sidecars carry its two imaginary
    modes as negative wave numbers, first and in the same order."""

    receipt = _extract(artifact, _FREQUENCIES, _PARTICIPATION, _DEGENERACY)
    delivered = {item.quantity_id: item.value for item in receipt.quantities}

    assert set(delivered) == {_FREQUENCIES, _PARTICIPATION, _DEGENERACY}
    assert len(delivered[_FREQUENCIES]) == 9
    assert sum(1 for nu in delivered[_FREQUENCIES] if nu < 0) == imaginary
    assert len(delivered[_PARTICIPATION]) == len(delivered[_FREQUENCIES])
    assert len(delivered[_DEGENERACY]) == len(delivered[_FREQUENCIES])
    for row in delivered[_PARTICIPATION]:
        assert len(row) == 5
        assert sum(row) == pytest.approx(1.0, abs=1e-9)
