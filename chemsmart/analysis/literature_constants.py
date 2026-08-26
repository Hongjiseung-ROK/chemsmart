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

Constants that look independent are often matched pairs.  An absolute
electrode potential is only meaningful beside the proton solvation free
energy determined on the same scale, and the literature circulates the two
halves separately: both members of a mismatched pair are individually
correct published values, the units are right, the magnitudes are
plausible, nothing fails to converge, and the answer is simply wrong by
more than the method error.  ``convention_family`` names the set an entry
belongs to so that a plan drawing on two families shows it on the page.

It is displayed, never refused.  Choosing a convention set is a
scientist's judgement -- a mixed selection can be deliberate, and it is
sometimes the only way to reproduce a published cycle -- so the host makes
the mixture visible in the review and leaves the decision where it
belongs.  That is the opposite of the electron-count parity rule, which
refuses, because an impossible state is arithmetic rather than judgement.
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
    #: The set of mutually consistent constants this entry belongs to.  Two
    #: entries sharing a family may be combined without further thought; two
    #: families combined in one expression is a fact the review displays.
    #: ``"independent"`` marks a value that belongs to no pairing -- a
    #: measured property of one substance, such as a reference acid's pKa.
    convention_family: str = "independent"
    note: str = ""


_ENTRIES: tuple[LiteratureConstantV1, ...] = (
    # Tissandier et al. 1998, cluster-pair approximation.
    LiteratureConstantV1(
        name="proton_hydration_gibbs_tissandier1998",
        convention_family=("tissandier1998_cluster_pair_proton_scale"),
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
        convention_family=("tissandier1998_cluster_pair_proton_scale"),
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
        convention_family=("tissandier1998_cluster_pair_proton_scale"),
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
    # Marenich, Ho, Coote, Cramer and Truhlar, Phys. Chem. Chem. Phys. 2014,
    # Table 2, attributing the value to Kelly, Cramer and Truhlar,
    # J. Phys. Chem. B 2006, 110, 16066.  This is the electrode potential
    # that belongs with the cluster-pair proton scale above.
    LiteratureConstantV1(
        name="standard_hydrogen_electrode_absolute_potential_kelly2006",
        value=4.28,
        unit="V",
        convention_family=("tissandier1998_cluster_pair_proton_scale"),
        convention=(
            "absolute potential of the standard hydrogen electrode, 298.15 "
            "K, solutes at 1 mol/L and ideal gases at 1 bar, proton and "
            "electron on Boltzmann statistics; consistent with an intrinsic "
            "proton solvation free energy of -1105 kJ/mol, from which the "
            "surface potential is absent"
        ),
        note=(
            "pairs only with the cluster-pair proton scale in this family; "
            "substituting an electrode potential determined on the real "
            "solvation scale raised the mean unsigned error on seven "
            "one-electron aqueous couples from 0.08 V to 0.20 V"
        ),
    ),
    # The competing determination, registered so that the pair it belongs
    # with is nameable rather than merely warned about.  Fawcett, Langmuir
    # 2008, 24, 9868, as tabulated by Marenich et al. 2014.
    LiteratureConstantV1(
        name="standard_hydrogen_electrode_absolute_potential_fawcett2008",
        value=4.42,
        unit="V",
        convention_family="fawcett2008_real_solvation_proton_scale",
        convention=(
            "absolute potential of the standard hydrogen electrode, 298.15 "
            "K, solutes at 1 mol/L and ideal gases at 1 bar; consistent "
            "with a real proton solvation free energy of -1091 kJ/mol, "
            "which includes the surface potential of water"
        ),
        note=(
            "real and intrinsic solvation free energies differ by the "
            "surface-potential term zFchi, estimated near 0.145 V for a "
            "singly charged ion in water though reported values range "
            "widely; the term cancels in a charge-balanced reaction within "
            "one phase"
        ),
    ),
    LiteratureConstantV1(
        name="proton_real_solvation_gibbs_fawcett2008",
        value=-1091.0,
        unit="kJ/mol",
        convention_family="fawcett2008_real_solvation_proton_scale",
        convention=(
            "real standard-state solvation free energy of the proton in "
            "water, ideal gas at 1 bar to 1 mol/L ideal solution, 298.15 K, "
            "including the surface potential"
        ),
        note=(
            "registered beside its electrode potential so the pair is "
            "selectable as a pair; do not combine with the cluster-pair "
            "family's electrode value"
        ),
    ),
    # Wise, Agarwal and Mayer, J. Am. Chem. Soc. 2020, 142, 10681.
    LiteratureConstantV1(
        name="acetonitrile_hydrogen_atom_formation_constant_wise2020",
        value=52.6,
        unit="kcal/mol",
        convention_family="wise2020_acetonitrile_ferrocene_scale",
        convention=(
            "the C_G term of the Bordwell relation "
            "BDFE = 1.37 pKa + 23.06 E + C_G in acetonitrile at 298 K, "
            "associated with reduction of the proton to the hydrogen atom "
            "in that solvent"
        ),
        note=(
            "the sources that state this value use it beside potentials "
            "referenced to ferrocenium/ferrocene in acetonitrile, but none "
            "read here declares that pairing as a property of the constant, "
            "and the full term composition was not read from a primary "
            "source; no C_G for water is registered because no primary "
            "source for one could be obtained"
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
