"""A saddle search prints one thermochemistry block per Hessian.

ORCA recomputes the Hessian during a transition-state optimisation, and
prints a full thermochemistry block each time. An observed OptTS run
printed four. Accessors that scanned forward from the top of the file
and returned their first match therefore reported the *initial guess*
geometry and called it the result.

Measured on that run: the first block's electronic energy sat
36.19 kcal/mol above the converged saddle's, and its zero-point energy
was 0.97 kcal/mol out.

The sharper defect was that the accessors disagreed with one another.
``gibbs_free_energy`` already read the last block through
``_last_complete_thermochemistry_section`` while ``electronic_energy``
and ``zero_point_energy`` scanned from the top, so a single result
object returned a Gibbs energy from the saddle beside an electronic
energy from the guess. Any barrier composed from that pair silently
mixed two geometries -- and a barrier is the whole point of running a
transition-state search.

The convention this restores is the one the release already states for
solvation terms: an optimisation prints one block per step, and the
last printed block is the result.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.io.orca.output import ORCAOutput

_FIXTURE = Path("tests/data/ORCATests/outputs/water_opt.out")


def _two_block_output(tmp_path):
    """A real ORCA output concatenated with a shifted copy of itself.

    The second block stands for the converged geometry: every energy is
    displaced by a constant, so a reader taking the first block is off
    by exactly that amount and a reader taking the last is exact.
    """

    text = _FIXTURE.read_text(encoding="utf-8", errors="replace")

    def shift(line, keyword, delta, position):
        if keyword not in line:
            return line
        fields = line.split()
        try:
            value = float(fields[position])
        except (ValueError, IndexError):
            return line
        fields[position] = f"{value + delta:.8f}"
        return " ".join(fields)

    second = []
    for line in text.splitlines():
        line = shift(line, "Electronic energy", -0.05, -2)
        line = shift(line, "Zero point energy", 0.001, -4)
        line = shift(line, "Total thermal energy", -0.05, -2)
        line = shift(line, "Total Enthalpy", -0.05, -2)
        line = shift(line, "Final Gibbs free energy", -0.05, -2)
        second.append(line)

    path = tmp_path / "two_blocks.out"
    path.write_text(text + "\n" + "\n".join(second) + "\n", encoding="utf-8")
    return path


def test_the_fixture_really_has_two_sections(tmp_path):
    """Guard the probe: a one-section file would pass everything."""

    out = ORCAOutput(filename=str(_two_block_output(tmp_path)))

    assert len(out._complete_thermochemistry_sections) == 2


@pytest.mark.parametrize(
    "accessor,delta",
    [
        ("electronic_energy", -0.05),
        ("zero_point_energy", 0.001),
        ("internal_energy", -0.05),
        ("enthalpy", -0.05),
        ("gibbs_free_energy", -0.05),
    ],
)
def test_every_thermochemical_accessor_reads_the_last_block(
    tmp_path, accessor, delta
):
    single = ORCAOutput(filename=str(_FIXTURE))
    doubled = ORCAOutput(filename=str(_two_block_output(tmp_path)))

    first = getattr(single, accessor)
    last = getattr(doubled, accessor)

    assert first is not None
    assert last == pytest.approx(
        first + delta, abs=1e-6
    ), f"{accessor} returned the first block, not the last"


def test_the_accessors_agree_with_each_other(tmp_path):
    """The defect that mattered: Gibbs from one block, energy from another."""

    out = ORCAOutput(filename=str(_two_block_output(tmp_path)))

    # H = U + kB*T, so enthalpy must exceed internal energy by a small
    # positive amount -- true only if both come from the same block.
    assert out.enthalpy > out.internal_energy
    assert (out.enthalpy - out.internal_energy) < 0.01


def test_a_single_block_output_is_unchanged():
    """No complete section means fall back to the whole file, as before."""

    out = ORCAOutput(filename=str(_FIXTURE))

    assert out.electronic_energy == pytest.approx(-76.32331101)
    assert out.zero_point_energy == pytest.approx(0.02158076)
