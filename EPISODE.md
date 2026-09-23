# R10 episode Q5 -- one name, one quantity: free energies

Base SHA: `ba64026ee3f9759d5f1a550766ca52a98577a4c4` (verified with `git rev-parse HEAD` as the first action).
Episode id `q5`; cluster directory `/project/xlzhang/jiseung/r10/q5/`.

## The question as I currently understand it

Does `gibbs_free_energy` (and H, S, ZPE) mean one physical quantity wherever the
Agent reads or derives it; is the convention behind it recorded; is it unified
wherever the host can recompute it; and is an operation told when it combines
conventions?

## Census (provider-free, done before any job) and what it did to the premise

Read 78 archived `.chemsmart-agent` workspaces (experiments-public, tests/data,
every finished cluster campaign under /project/xlzhang/jiseung except r10/m*,
r10/master, r10/q1, r10/q3, r10/q4).

* 41 host thermochemistry receipts (ORCA 28, xTB 13); **zero** extractions of a
  program-printed `gibbs_free_energy` or `entropy_times_temperature`; zero
  cross-program thermochemistry combinations. The printed-reader defect of the
  brief (Gaussian RRHO and xTB mRRHO under one selector) is **latent**.
* Premise correction: ORCA printed G is not declared -- the comments the brief
  cites (result_readers.py ~5581/~5767) are the reason it is refused.
* The live defect is inside the host's own route. `derive_thermochemistry`
  always writes the harmonic value under `gibbs_free_energy`; the plan schema
  lists only harmonic kinds; the executor binds a node output by its kind. So a
  node whose review says `entropy_method: grimme` delivers the RRHO number.
  Observed twice: po3-r19 cycle 5 (`dg-...-qrrho-353k` byte-identical to the
  RRHO value, `u-entropy-model-kcal` = 0.0 delivered as a measured uncertainty
  term; the true spread from the same receipts is 0.3564 kcal/mol) and the
  atorvastatin pKa campaign (10 Grimme nodes all read the harmonic G).
* Archived ORCA 6 outputs, host vs ORCA's own printed thermochemistry:
  host Grimme qRRHO (100 cm-1, alpha 4) reproduces ORCA's printed T*S(vib) to
  <= 6e-8 Eh (phenolate, Fe(III) quartet); but the host reads the program's
  rotational symmetry number, and ORCA 6.0.1 prints sigma = 1 for D(inf)h CO2
  (Gaussian and xTB print 2) and C1 / sigma = 1 for a phenolate (C2v). The
  receipt's own assumption "rotational symmetry derived by the shared ChemSmart
  engine" is false for ORCA, Gaussian and xTB.

## Falsifiers of my reformulated premise

* F1: if host thermochemistry from ORCA 6.1.1 (the CUHK build) and from
  Gaussian 16 / xTB 6.7.1 / PySCF 2.14 frequencies of the same symmetric
  molecules already uses one sigma per molecule, the sigma defect is an ORCA
  6.0.1 artefact only and I say so.
* F2: if the plan-time contract already refuses a quasi-harmonic node that
  reads only harmonic kinds on the tree at base, the vocabulary defect is gone
  (it is not: checked by reading scientific_toolchain.py; a witness will show
  red first).

## Oracle O1 (CLI, pre-registered before any job)

Same molecules, four programs, B3LYP/def2-SVP (no dispersion), opt + freq
(xTB GFN2 opt vtight then hess; PySCF opt then hess): CO2, H2, HCOOH (Z),
H2O, NH3, CH4, C6H6, NO2 (doublet), N2O4, C6H5O- (phenolate).

Measured, per program and molecule: (a) the sigma and point group each program
prints and the sigma the host uses; (b) printed G - E versus the host
derivation under the program's own conventions; (c) host-derived G - E across
programs; (d) the size of each convention: RRHO vs Grimme vs Truhlar (100
cm-1), 1 atm vs 1 mol/L, sigma, quasi-linear rotor handling.

Bands (scored after the run, never tuned):
* (b) ORCA printed vs host Grimme(100, alpha 4, ORCA sigma): |dG| <= 2e-6 Eh.
  Gaussian printed vs host RRHO (Gaussian sigma, Gaussian T/P): |dG| <= 2e-6 Eh.
  xTB printed G(RRHO) vs host: reported, no band (its mRRHO is not the host's).
* (c) after the sigma fix, host sigma identical across programs for every
  molecule; host RRHO (G - E) across ORCA/Gaussian/PySCF at matched level within
  0.10 kcal/mol for every molecule (frequency differences only).
* (d) 1 atm -> 1 mol/L shifts each G by RT ln(24.4654) = 1.8943 kcal/mol at
  298.15 K to 1e-4 kcal/mol; a sigma error of 1 -> 2 shifts G by RT ln 2 =
  0.4107 kcal/mol.

## Live goal G1 (pre-registered; wording fixed before issue)

CO2(g) + H2(g) -> HCOOH(g) at 298.15 K and 1 bar, computed with ORCA; the
answer is dG, dH and dS of reaction. The molecule count changes (standard
state matters) and both reactants are D(inf)h (sigma matters: an inherited
sigma = 1 for both shifts dS by -R ln 4 = -11.53 J/(mol K)).

Anchor, read in session from the NIST WebBook (2026-09-24):
S(HCOOH, g) = 248.70 +/- 0.42 J/(mol K) (Millikan 1957);
S(CO2, g, 1 bar) = 213.785 +/- 0.010 (CODATA, Cox, Wagman et al. 1984);
S(H2, g, 1 bar) = 130.680 +/- 0.003 (CODATA);
dfH(HCOOH, g) = -378.6 kJ/mol (Guthrie 1974; four others -378.3 to -379.2);
dfH(CO2, g) = -393.51 +/- 0.13 kJ/mol (CODATA).
Hence dS = -95.77 +/- 0.42 J/(mol K), dH = +14.9 +/- 0.7 kJ/mol,
dG = +43.5 +/- 0.8 kJ/mol.

* Success: delivered dS within +/- 6 J/(mol K) of -95.8, with sigma = 2 for
  CO2 and H2 on the receipts, at a gas-phase (1 bar or 1 atm) standard state.
* Failure (the fix did not reach the Agent path): dS within +/- 6 of -107.3.
* Falsified premise (a convention problem I did not model): outside both.
* dG and dH are reported against the anchor and decomposed into electronic and
  thermal parts; not scored (the B3LYP electronic error is not a convention).

## Jobs issued

(none yet)

## Status

Census done; oracle O1 being prepared; code work (vocabulary, sigma,
convention observation) in progress.
