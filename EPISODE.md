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

**G1 withdrawn before issue (2026-09-24, after O1 stage A, before any goal).**
O1 showed ORCA 6.1.1 prints sigma = 2 for CO2 and H2 (the sigma = 1 for CO2
is an ORCA 6.0.1 artefact), so G1 cannot tell the host's sigma from ORCA's:
it would pass on the base tree too. It is replaced by G1', chosen from the
same O1 evidence: Gaussian 16 printed "Full point group CS", sigma = 1, for
an NH3 built C3v to 1e-4 A (G_nh3.log), while ORCA printed C3v / 3.

## Live goal G1' (pre-registered before issue; replaces G1)

N2(g) + 3 H2(g) -> 2 NH3(g) at 298.15 K and 1 bar, computed with Gaussian 16
(B3LYP-D3(BJ)/def2-TZVP, optimisation and frequencies per species); the
answer is dG, dH, dS of reaction and Kp. The molecule count changes by -2
(1 bar -> 1 mol/L moves dG by 2 x 1.894 kcal/mol) and every species has a
symmetry number above 1 (N2 2, H2 2, NH3 3). Workspace geometries: n2.xyz,
h2.xyz, nh3.xyz (the same C3v NH3 as O1). TASK.md (verbatim, fixed now):

> At 298.15 K and a standard pressure of 1 bar, what are the standard
> reaction Gibbs energy, enthalpy and entropy of ammonia synthesis in the
> gas phase, N2(g) + 3 H2(g) -> 2 NH3(g), and the equilibrium constant Kp
> they imply? Compute them with Gaussian 16 at B3LYP-D3(BJ)/def2-TZVP, with
> an optimisation and frequencies for each species. The workspace holds
> starting geometries for dinitrogen (n2.xyz), dihydrogen (h2.xyz) and
> ammonia (nh3.xyz); all three are closed-shell neutral singlets. Report each
> quantity with its unit, the standard state and the thermochemical
> treatment it rests on, and say which parts of the result you would trust.

Anchor, read in session from the NIST WebBook (2026-09-24, CODATA, Cox,
Wagman et al. 1984): S(NH3, g, 1 bar) = 192.77 +/- 0.05; S(N2) = 191.609 +/-
0.004; S(H2) = 130.680 +/- 0.003 J/(mol K); dfH(NH3, g) = -45.94 +/- 0.35
kJ/mol. Hence dS = -198.11 +/- 0.10 J/(mol K), dH = -91.88 +/- 0.70 kJ/mol,
dG = -32.81 +/- 0.70 kJ/mol, Kp = 5.6e5 bar^-2.

* Success: delivered dS within +/- 6 J/(mol K) of -198.1 at a gas-phase
  (1 bar or 1 atm) standard state, with sigma 3 / 2 / 2 on the receipts.
* Failure (the host's sigma did not reach the Agent path): dS within +/- 6 of
  -179.8 (= -198.1 + 2 R ln 3), with Gaussian's sigma = 1 used for NH3.
* Not discriminating (reported, not scored as success): the Agent's Gaussian
  NH3 prints sigma = 3 itself (base and fix then agree).
* Falsified premise: outside every band above.
* dG, dH and Kp are reported against the anchor, decomposed into electronic
  and thermal parts; not scored.
* Granted by `claude-researcher-q5-owner-delegated` (a delegated approval,
  not a human decision). Provider: alibaba-token-plan / deepseek-v4-flash-0731.

## O1 stage A (CUHK Slurm 2149853, code b971ee96, ORCA 6.1.1 + Gaussian 16)

40 of 60 commands exit 0 (every ORCA and Gaussian opt+freq, every xTB and
PySCF opt); the 20 second-stage Hessians failed before any engine on my own
input paths (xTB writes its reached frame under .chemsmart-runs/; PySCF names
its artifact <label>_gas_phase.h5) -- re-issued as O1 stage B.
* (a) sigma: ORCA 6.1.1 printed the right sigma for all ten; Gaussian printed
  Cs / sigma = 1 for NH3 (host 3); every other Gaussian sigma right.
* (b) printed G vs host under the program's conventions (ORCA: Grimme 100
  cm-1 alpha 4; Gaussian: RRHO; the program's own sigma): 19 of 20 within the
  2e-6 Eh band; ORCA benzene -2.26e-6 Eh (0.0014 kcal/mol) outside it. Band
  missed once; reported, not re-tuned.
* (c) host RRHO G - E, ORCA vs Gaussian, same level: |d| <= 0.013 kcal/mol
  for all ten (band 0.10), with one sigma per molecule.
* (d) 1 atm -> 1 mol/L: +1.8943 kcal/mol for all ten (band met); Grimme -
  RRHO: 0.000 except N2O4 +0.082 (101 cm-1 torsion) and C6H6 / phenolate
  -0.002; Truhlar - RRHO 0.000 (no mode below 100 cm-1); RT ln sigma 0.41 /
  0.65 / 0.82 / 1.47 kcal/mol for sigma 2 / 3 / 4 / 12.

## O1 stage B (CUHK Slurm 2149909, code b971ee96): xTB and PySCF Hessians

20 of 20 exit 0. Read locally on the committed tree:
* PySCF's own sigma (from PySCF's point group) was wrong three times: NH3 1
  (host 3), C6H6 4 (host 12; PySCF reports its Abelian D2h), N2O4 2 (host 4).
* PySCF CO2 and H2 and xTB H2: the host derived NaN (negative axial moment
  from floating-point noise) -- fixed in e1133b82, CO2 S = 213.82 and H2
  130.66 J/(mol K) at 1 atm (CODATA 1 bar: 213.785, 130.680).
* Host RRHO G - E across ORCA / Gaussian / PySCF at one level: within 0.013
  kcal/mol except N2O4 PySCF (-0.050; its 94 cm-1 torsion against 101): band
  0.10 met for all ten.
* xTB printed G - E = host Grimme(50 cm-1, alpha 4) + 0.0036..0.0047
  kcal/mol for nine closed shells; NO2 (doublet) +0.4152 = RT ln 2 + 0.0045:
  xTB's printed free energy omits the electronic spin-degeneracy entropy.

## G1' cycle 1 (CUHK Slurm 2149940, code f073c8a3) -- read from host records

The Agent planned three Gaussian opt+freq nodes (B3LYP, def2TZVP,
empiricaldispersion=gd3bj), host RRHO thermochemistry at 0.986923 atm, and
one expression. All three Gaussian runs terminated normally and the host
typed them failed_native: `gaussian.result.method_mismatch`, because the
route reader merges the dispersion into the functional ("b3lyp-d3bj") and
the result verifier compares that with the requested functional ("b3lyp")
-- a host defect outside Q5, left for after the session (never repair a
live session). The analysis chain still ran on the three results:
S(H2) 130.39, S(N2) 191.457, S(NH3) 192.46 J/(mol K); dS = -197.707
J/(mol K) (anchor -198.11 +/- 0.10: inside the success band); dH = -87.79
kJ/mol (anchor -91.88), dG = -28.85 kJ/mol (anchor -32.81), Kp = 1.13e5
(anchor 5.6e5). NH3's receipt: "rotational symmetry number 3, counted by the
host ...; the program itself stated 1" -- Gaussian printed Cs again, so the
base tree would have delivered dS = -179.4 (the failure band). Settlement
pending (cycle 2 woken).

## G1' cycle 2 and the probe G2 (pre-registered before G1' settled)

Cycle 2 (read from the ledger): the Agent rejected standing by its cycle-1
claims because the host had recorded every result invalid, re-spelled the
projects (dispersion gd3bj, basis def2tzvp) and ran the three nodes again:
failed_native on the same method_mismatch; 2 of 8 engine calls left. The
Agent is fighting a host verifier defect, not the chemistry.

G2 -- the repair's first probe and a clean end-to-end delivery: the same
TASK.md, geometries, envelope and bands as G1', on the committed tree that
carries the verifier fix (method compared without a dispersion suffix).
Pre-registered expectations beyond the G1' bands:
* the three Gaussian nodes validate (no gaussian.result.method_mismatch);
* the goal settles achieved or achieved_with_observations with dS inside
  +/- 6 J/(mol K) of -198.1 and sigma(NH3) = 3 on its receipt;
* if Gaussian again prints Cs for NH3, the receipt says "the program itself
  stated 1"; if it prints C3v, G2 does not discriminate the sigma fix and I
  say so.
G2 is a new observation on a repaired tree, not a re-roll of G1': G1' is
reported as it settles.

## Jobs issued

* 2149853 (r10-q5-a) O1 stage A, CLI, code b971ee96, prereg 1f8e0d51a36a.
* 2149909 (r10-q5-a) O1 stage B (xTB and PySCF Hessians), prereg 1f8e0d51a36a.
* 2149940 (r10-q5-a) goal G1' (g1), code f073c8a3 in code-g1, prereg a401bb5dbee7.

## Status

C1 (b40d583a), C2 (aa9fbd3c), C3 (9ef9d476) committed; O1 stage B running;
G1' about to be issued on a packed tree of the committed code.
