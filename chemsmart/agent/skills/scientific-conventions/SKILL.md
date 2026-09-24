---
name: scientific-conventions
version: 0.4.0
description: How computational-chemistry quantities are conventionally defined and reported — direction of every difference quantity, adiabatic versus vertical geometry, which energy terms are included, when an established spin assignment may be stated, gas and solution standard states, and what a computed value must become before it is compared with a measured one.
---

# Reporting conventions for computed quantities

Knowledge about how results are *expressed*, not about how accurate they must
be. Nothing here sets a tolerance, an error budget, or a readiness state.

These are general principles. Where an example appears it illustrates the
principle; the principle, not the example, is what applies.

Apply them as a challenging computational scientist. Treat an unexpected
number as a hypothesis-generating observation: verify geometry, electronic
state, energy definition, sign, unit, thermochemical convention and program
semantics before adding guidance. When a real calculation disproves or narrows
a rule, update the general rule and challenge it on a different chemical case.
Never learn a molecule-specific value or preferred DAG as a convention.

## 1. Every difference quantity needs a stated direction

A number that is a difference is meaningless until the reader knows which term
was subtracted. State the direction explicitly rather than relying on a
convention the reader may not share.

| Quantity class | Conventional direction | Sign that follows |
|---|---|---|
| Term value (`Te`, `T0`, an excitation energy) | upper state − ground state | non-negative when the ground state is correctly identified |
| Ionization energy | cation − neutral | positive for a bound electron |
| Electron affinity | neutral − anion (the anion's ionization energy) | positive when the anion is bound; negative for an unbound anion |
| Reaction energy / enthalpy / free energy | products − reactants | negative if exergonic |
| Activation barrier | transition state − reactants | positive |
| Interaction / binding energy | complex − separated fragments | negative if bound, but the opposite sign is also in common use — always say which |
| State-ordering gap (e.g. a singlet–triplet gap) | higher-lying state − ground state | non-negative when the ground state is correctly identified |

A term value is measured upward from the ground state — `Te` between the two
minima, `T0` between the zero-point levels, which is the band origin — and
cannot be negative. A negative term value means the two states were ordered the
wrong way round, not that the quantity is negative. An electron affinity is
different: it is an energy of detachment from the anion, and a negative value
is a physical result, an anion that is not bound, rather than a sign error.

## 2. Adiabatic versus vertical is a geometry convention

The distinction applies to any state-to-state quantity — ionization, electron
attachment, excitation, spin-state change — and it changes the shape of the
calculation, not only the number.

| | Geometry of each state | Shape of the calculation |
|---|---|---|
| **Adiabatic** | each state at **its own** relaxed geometry | relax both states, then compare |
| **Vertical** | both states at the **initial** geometry | relax the initial state only; evaluate the other state at that geometry |

A vertical quantity therefore contains **no optimization of the final state**.
Computing two independently relaxed geometries and calling the result vertical,
or using one geometry and calling the result adiabatic, reports something other
than what was asked. For the signed difference
``E_final - E_initial``, the vertical value is normally no smaller because the
final state is evaluated away from its own minimum. A positive electron
affinity is commonly defined with the opposite sign, so its numerical
inequality reverses; always state the direction before comparing values. The
vertical electron affinity is taken at the neutral's geometry and the vertical
detachment energy at the anion's, and the two bracket the adiabatic electron
affinity from below and above.

## 3. Say which energy terms are included

Distinguish, and name which one is being reported:

- **Electronic energy** — the converged SCF/post-SCF energy at a geometry.
- **Zero-point corrected (0 K)** — electronic plus harmonic zero-point energy.
  A molecular state needs its vibrational analysis, not only its electronic
  energy. A monatomic fragment has no vibrations or rotations and therefore
  has exactly zero vibrational ZPE; do not request a fictitious atomic
  optimization or frequency calculation to manufacture those modes.
- **Enthalpy / free energy at finite T** — electronic plus zero-point plus
  thermal corrections, with `G = H − TS` at the stated temperature.

Zero-point and thermal corrections belong to quantities defined at a relaxed
geometry. A vertical quantity is an energy difference at one fixed geometry and
carries no separate zero-point correction.

## 4. Established assignments may be stated as prior knowledge

Some facts — a ground-state spin multiplicity, a known point group, an
established conformer preference — are settled in the literature and do not
have to be computed before they can be stated. When one applies, state it,
mark it as prior knowledge rather than a computed result, and let the
calculation confirm or contradict it. Declining to state a settled fact is not
caution; it withholds information the requester asked for.

The reverse error matters as much: presenting an unsettled, substituent-
dependent, or method-sensitive assignment as settled. The test is whether the
assignment is established for **this** system, not for a superficially similar
one.

Two generative principles cover most ground-state spin assignments:

- Near-degenerate frontier orbitals that share atoms follow **Hund's rule** —
  the high-spin configuration lies lowest, because exchange stabilisation
  outweighs the small orbital-energy gap. When the two singly occupied orbitals
  can be confined to disjoint sets of atoms, their exchange is small and the
  singlet can lie at or below the triplet: a known exception to Hund's rule in
  diradicals, which makes such an assignment method-sensitive rather than
  settled.
- A substituent, a ligand field or a geometric distortion that **splits those
  orbitals** far enough reverses the ordering in favour of the low-spin state.
  Strong π-donation into a formally empty frontier orbital, a strong-field
  ligand set, or a distortion that lifts an orbital degeneracy does this.

Apply the principles to the system at hand rather than recalling a list.

## 5. Reference-method limitation for low-spin and stretched states

A single-determinant reference can be less balanced for low-spin,
near-degenerate, or stretched-bond states than for a corresponding high-spin
state. Open-shell singlets, diradicals, transition-metal spin states and
bond-breaking regions therefore require diagnostics rather than a universal
error direction. Depending on the system, reference, functional and amount of
exact exchange, a low-spin state may be biased upward or downward. Establish
the direction from spin diagnostics, reference stability, multireference
evidence or an applicable cited benchmark; do not infer it from spin alone.

## 6. Differences are more convergence-sensitive than absolutes

A difference of two total energies is more sensitive to convergence than either
energy alone, because the two errors cancel only when the states are converged
comparably. This applies to the SCF threshold, the integration grid, and the
geometry-optimization criteria alike. State the settings used rather than
leaving them at whatever default applies: the setting is part of what was
computed, and asymmetric settings between the two states invalidate the
cancellation the difference relies on.

## 7. Thermochemistry

- Partition functions are evaluated in the **rigid-rotor / harmonic-oscillator**
  approximation unless another treatment is named. Low-frequency modes are the
  approximation's weak point; if a quasi-harmonic treatment is used, name it.
- Rotational entropy requires the **rotational symmetry number** σ, taken from
  the molecular point group — not from the formula or the atom count. Omitting
  it inflates the entropy by `R ln σ`.

  | Point group | σ | | Point group | σ |
  |---|---|---|---|---|
  | `C1`, `Cs`, `Ci`, `C∞v` | 1 | | `D2h` | 4 |
  | `C2`, `C2v`, `C2h`, `D∞h` | 2 | | `D3h` | 6 |
  | `C3v` | 3 | | `D3` | 6 |
  | `Td` | 12 | | `Oh` | 24 |

- The modern standard state is **1 bar**. Older tables and some program defaults
  use 1 atm; the two differ by `R ln(1.01325)` in the standard entropy. When a
  request names a pressure, report the value at that pressure and say which one
  the calculation used.
- A solute's conventional standard state is **1 mol/L**, not a gas at 1 bar.
  Taking one mole of ideal gas from pressure `p°` to concentration `c°` adds
  `RT ln(c° R T / p°)` to its free energy, and a reaction in solution that
  changes the number of solute particles — an association, a dissociation, a
  binding — or that joins a gas-phase free energy to solvation free energies
  carries that term once per mole of change. A solvent that is itself a
  reactant has its own standard state, the pure liquid. Say which standard
  state each species is in.
- A reported free energy should be reconstructible from the electronic energy,
  the zero-point energy, the thermal corrections, and `G = H − TS` at the stated
  temperature.
- For a monatomic ideal-gas species confined to its ground electronic level,
  there is no rotational or vibrational contribution. Its molar enthalpy
  increment above the electronic energy is `5/2 RT`: `3/2 RT` translation plus
  `RT` from `pV`.
- Check a finite-temperature reaction enthalpy against its 0 K value by
  subtracting the per-species thermal increments with the same stoichiometric
  signs. Derive that difference from the planned quantities. A remembered
  literature number is an external comparison, not an internal consistency
  equation, unless its source and convention were supplied.
- When starting from a ZPE-corrected 0 K quantity, the increment to finite
  temperature is `H(T) - E_electronic - ZPE`. By contrast,
  `H(T) - E_electronic` already contains ZPE and belongs with an electronic
  energy difference. Do not add both corrections to the same reaction value.
- **Imaginary-mode criteria are two different questions; say which one you
  asked.** A strict criterion (`no imaginary modes, ever`) fails on any
  negative frequency. ChemSmart's thermochemistry instead treats a mode
  within **20 cm⁻¹ of zero as numerical noise**, not evidence of a saddle
  point, and reports how many such modes exist as `near_zero_mode_count`.
  When the task states a criterion — "no imaginary modes, never", or
  "imaginary modes below x are acceptable" — encode exactly that criterion
  in the validation rule. When the task states none, default to the 20 cm⁻¹
  convention (a `minimum_greater_equal` threshold of −20 cm⁻¹, or a
  `count_equals` check on `near_zero_mode_count`), and state in the report
  that the convention, not a strict zero, was applied.

## 8. A number without a unit and a convention is not a result

Report the unit explicitly and keep one unit per quantity within a document.
When converting, state the source unit. Energies computed in Hartree are
conventionally reported in kcal/mol or kJ/mol for chemical differences and in eV
for ionization, attachment, and excitation.

## 9. A computed value is compared with the quantity that was measured

An experimental number measures one specific quantity, and a computed value is
compared with it only after it has been turned into that quantity: an enthalpy
or free energy at the measurement's temperature rather than an electronic
energy; the measured phase and standard state; a vertical excitation against a
band maximum, and an adiabatic one with zero-point energies against a band
origin; a dissociation energy from the zero-point level (`D0`) against one
measured that way, never one from the minimum (`De`). Name the conversion, and
cite where the measured value comes from.
