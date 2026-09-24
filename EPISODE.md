# EPISODE q21 -- what a number means when it is combined

- Round: R10. Specialist Q21.
- Base SHA: 7904d6a37a2af108823b66cf4a7b2772900c3c41 (verified with `git rev-parse HEAD` at start).
- Brief: scratchpad/q21/BRIEF.md, sha256 e23b44adee969db9a850a1ed63771c398592f61882e7484c1c721d5f8b8ea47b.

## Question (as currently understood)

Does every number the host derives or combines carry the physical meaning the
operation needs beyond its dimension -- its kind (total energy, energy
difference, curvature, frequency), its sign convention, its normalisation, and
whether its structure is a stationary point? Where an operation is dimensionally
legal and physically meaningless, does the host refuse it with a route, or state
what the result is?

## Census (provider-free, step 1) -- denominators

Sources: CUHK `/project/xlzhang/jiseung/` campaign roots r8, r9, the named
2026-09-16..21 campaign directories, and r10 episodes q1-q5, q7-q20 named one
by one (excluded: r10/q6/goals, r10/q3/sealed*, r10/q3/plans/sealed*,
r10/q17/sealed1 -- a sealed study still running -- and every r10/m*); plus the
ax41 mirror (`~/developer/chemsmart-hetzner-mirror`). 1,243 CUHK files
(398 unique streams) and 1,522 mirror streams (1,029 unique). Events
de-duplicated by event_hash. Scripts: scratchpad/q21/census/*.py.

| record | CUHK | ax41 |
|---|---|---|
| thermochemistry derivations (unique receipts) | 59 | 425 |
| quantity expressions (unique receipts) | 273 (269 matched to their request) | 1,108 (all matched) |
| energy-combining expression outputs (linear, expanded recursively) | 72 | 456 |
| analysis-claim records | 148 | 409 |

### Stationarity (thermochemistry derivations, by producer job and convergence)

| class | CUHK (claimed) | ax41 (claimed) |
|---|---|---|
| optimisation converged in the same job | 43 (34) | 409 (299) |
| fixed-geometry Hessian (freq/hess/sp+freq; stationarity unmeasured unless a gradient reader) | 15 (3) | 5 (5) |
| optimisation did not converge | 1 (1: an H atom, stationary by construction) | 11 (5) |
| constrained optimisation (modred/scan) | 0 | 0 |

- po3-r19 (ax41, 2026-09-12): ORCA OptTS `ts-esterc4` did not converge
  (`orca.result.optimization_not_converged`); thermochemistry was derived from
  its last Hessian and delivered dG(act) 23.194 kcal/mol, ddG 0.614 kcal/mol
  (cycle-2 executor and two sessions).
- e3-phenol-a / e3-aniline (ax41 standing round): G derived at a force-field
  geometry (sp+freq), claimed (-192637.995 kcal/mol); stationarity unmeasured.
- Probed on the base tree (scratchpad/q21/probe_thermo.py): G is derived from a
  Gaussian `modred` result (tests/data .../h2o2_b3lyp_def2svp_hooh90.log,
  G = -151.41696 Eh), from the unconverged po3-r19 ORCA TS (G = -1075.92317 Eh),
  and from the PySCF `water_stretched_hess` Hessian at max|g| = 0.0185 Eh/Bohr
  (41x criterion) -- the same artifact the characterisation refuses an order on.
  Two organs, one question, two answers.

### Kind / normalisation (curvature)

Operand-kind census over all 1,381 expressions: the only combinations whose
operands' kinds make the result meaningless are R10 Q13's dans goal:
`min(internal, external, real->complex)` over three differently normalised
stability eigenvalues (claimed `rks-stability-lowest-eig` = 0.042085 Eh, twice)
and `|minstab-cam - minstab-pbe0|` (claimed `stabspread` 0.00515 Eh), read in
the session's prose as "~3.2 kcal/mol" and "~ +110 kJ/mol". No orbital energy,
excitation energy or curvature was ever added to a total energy.

### Sign / direction (per-structure layer consistency)

Every energy output expanded to one coefficient per (species, layer) where
layers are E_el, ZPE, thermal above ZPE, pV, -TS: exactly one output enters a
species with different coefficients on its own layers -- R10 Q14 G2 cycle 3,
`d0-oh = [E(OH) - E(O) - E(H)] - ZPE(OH)`, claimed -105.90 kcal/mol (OH: E +1,
ZPE -1). 20 of 58 archived ax41 bond/binding-energy claims are negative under
conventions nobody stated (binding energies, solvation dE, BDE differences).

## Premise verdict (so far)

The premise holds but is narrow: the meaningless combinations that reached a
delivered claim are the brief's instances (dans, Q14 G2) plus one the brief did
not list -- a free energy from an unconverged TS (po3-r19). Constrained
(modred/scan) free energies never occurred in the archive but are reachable.

## Plan

1. One stationarity function in the analysis plane; thermochemistry refuses a
   free energy at a structure that is not stationary (measured gradient above
   criterion, constrained optimisation, optimiser's own non-convergence) with a
   route, and states the stationarity it stands on in every receipt.
2. Energy combinations state their direction (the reaction the coefficients
   describe) and name a species whose own layers enter with different signs.
3. Curvature selectors carry kind and normalisation in the vocabulary; an
   expression combining them across normalisations says so.

## Status

- Step 1 (census) done; implementation starting.
