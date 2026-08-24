"""Host-owned literature constants for typed analysis chains.

A literature constant is a number a scientist takes from the record rather
than computes: the aqueous proton's free energy, a standard-state
correction, a reference acid's measured pKa.  A session may only *select*
one of these entries by its registered name through the ``constant``
expression operation; the value, its unit, and its standard-state
convention are owned here, in reviewed code.  The contrast with the
``literal`` operation is the point: a literal is recorded as
model-authored, a constant is host-owned.

Names are version-pinned (author-year), so a revised value enters as a new
entry and two constant sets can never silently mix — the same number under
a "current best" name would drift underneath old approvals.  Each entry's
``convention`` string states the standard-state bookkeeping that gives the
number its meaning: the two aqueous-proton values in circulation differ
only by which gas standard state they assume, and dropping that sentence
is the documented way published thermodynamic cycles go wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class LiteratureConstantV1:
    """One host-owned literature value with its standard-state meaning."""

    name: str
    value: float
    unit: str
    convention: str
    note: str = ""


_ENTRIES: tuple[LiteratureConstantV1, ...] = (
    # Tissandier et al. 1998, cluster-pair approximation.
    LiteratureConstantV1(
        name="proton_hydration_gibbs_tissandier1998",
        value=-1104.5,
        unit="kJ/mol",
        convention=(
            "hydration free energy of the proton, ideal gas at 1 atm to "
            "aqueous 1 mol/L, 298.15 K; -264.0 kcal/mol"
        ),
        note="cluster-pair extrapolation; stated esd 0.3 kJ/mol",
    ),
    # Kelly, Cramer & Truhlar 2006 restatement of the same physics with a
    # 1 mol/L gas reference.
    LiteratureConstantV1(
        name="proton_solvation_gibbs_kelly2006",
        value=-265.9,
        unit="kcal/mol",
        convention=(
            "solvation free energy of the proton, ideal gas at 1 mol/L to "
            "aqueous 1 mol/L, 298.15 K; equals the 1 atm hydration value "
            "-264.0 kcal/mol minus RT ln(24.4654)"
        ),
    ),
    # Classical ideal-gas proton: H = 5/2 RT, S from Sackur-Tetrode.
    LiteratureConstantV1(
        name="proton_gas_gibbs_sackur_tetrode_298K",
        value=-6.28,
        unit="kcal/mol",
        convention=(
            "gas-phase free energy of the proton, ideal gas at 1 atm and "
            "298.15 K; H = 5/2 RT = 1.48 kcal/mol, S = 26.04 cal/(mol K)"
        ),
        note=(
            "the 2014 quantum-statistical revision (-6.296 kcal/mol at "
            "1 bar) shifts a pKa by under 0.015 units"
        ),
    ),
    LiteratureConstantV1(
        name="standard_state_correction_1atm_to_1M_298K",
        value=1.894,
        unit="kcal/mol",
        convention=(
            "free-energy change of compressing an ideal gas from 1 atm to "
            "1 mol/L at 298.15 K; RT ln(24.4654)"
        ),
    ),
    # Experimental datum for relative (proton-exchange) constructions,
    # where the reference acid's measured value anchors the scale and the
    # absolute proton free energy cancels identically.
    LiteratureConstantV1(
        name="acetic_acid_experimental_pka_298K",
        value=4.756,
        unit="1",
        convention=(
            "measured aqueous pKa of acetic acid at 298.15 K, infinite "
            "dilution; dimensionless"
        ),
        note="reference anchor for proton-exchange pKa constructions",
    ),
    # The composite that actually enters a direct-cycle deprotonation.
    LiteratureConstantV1(
        name="aqueous_proton_gibbs_298K",
        value=-270.3,
        unit="kcal/mol",
        convention=(
            "absolute free energy of the aqueous proton at 1 mol/L and "
            "298.15 K; gas-phase proton free energy (1 atm) plus the "
            "1 atm to 1 mol/L correction plus the 1 mol/L to 1 mol/L "
            "solvation free energy"
        ),
        note=(
            "invariant under the two bookkeeping routes: "
            "(-6.28 + 1.894) + (-265.9) and (-6.28) + (-264.0)"
        ),
    ),
)

LITERATURE_CONSTANTS: MappingProxyType[str, LiteratureConstantV1] = (
    MappingProxyType({entry.name: entry for entry in _ENTRIES})
)


class UnknownLiteratureConstantError(KeyError):
    """A requested name is not in the registry; the message names what is."""


def literature_constant(name: str) -> LiteratureConstantV1:
    """Return the registered entry, or refuse naming the available set."""

    try:
        return LITERATURE_CONSTANTS[str(name)]
    except KeyError as exc:
        available = ", ".join(sorted(LITERATURE_CONSTANTS))
        raise UnknownLiteratureConstantError(
            f"unknown literature constant {name!r}; registered constants: "
            f"{available}"
        ) from exc


__all__ = [
    "LITERATURE_CONSTANTS",
    "LiteratureConstantV1",
    "UnknownLiteratureConstantError",
    "literature_constant",
]
