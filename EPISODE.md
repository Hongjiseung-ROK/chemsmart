# R10 Q7 -- Gaussian's excited states and scans through the hub

Base SHA: 0c73b0d8490de50fe7a79ee766c63a61026f8915 (verified `git rev-parse HEAD` at start)
Episode id: q7
Branch: worktree-agent-aee3b9aae0e478272

## Question (as currently understood)

Can the CHEMSMART Agent run Gaussian's excited states (`td`), relaxed
scans (`scan`) and constrained optimisations (`modred`) without knowing
Gaussian -- the hub owning the route, the checkpoint and the reading --
and do their results read back as the same physical quantities ORCA and
PySCF give for the same request (Fundamental 1)?

"The same request" is taken literally: one set of project keys that ORCA
and PySCF already accept, sent to Gaussian unchanged.

## Premises checked before any change (reproduced on the base tree)

1. CORRECTED (brief: "Gaussian td borrows a level that dies in the
   writer"). A Gaussian `td` stage borrows *no* level. The loader reseeds
   a `td:` section from stage defaults, so `gas: {functional, basis}` +
   `td: {nstates: 6}` builds a route with no method and the public CLI
   dies in the writer (`ValueError: Error: No computational method
   provided.`, traceback, `chemsmart run --fake ... gaussian td`), while
   `validate_project_yaml` calls it `valid` (GaussianTDDFTJobSettings has
   no `validate`). This is `negative.a_gaussian_td_stage_borrows_no_level_of_theory`
   in the research graph. Where a level *is* claimed borrowed and dies is
   `solv:` + `td:`: `molecular_project_section_sources(td)` answers
   `('solv', 'td')` to the Agent's project observation while the loader
   applies only `td:` -- the Agent is told the solv level feeds td, and
   the writer dies. ORCA shares both (same loader).
2. NEW. A `solv:`-only Gaussian project with no `td:` section writes
   `# freq b3lyp 6-31g* TD(singlets,nstates=3,root=1)`: the td stage
   inherits the shared default `freq: true` in the no-gas branch (the
   `td:` branch turns it off explicitly), i.e. an excited-state frequency
   job nobody asked for.
3. NEW. Gaussian's td speaks its own vocabulary (`states: singlets|triplets|50-50`,
   always full TD, `TDA` unreachable through typed settings) where ORCA
   and PySCF both take `response_method: tda|tddft` and `state_manifold`.
   The same request cannot be sent to the three programs unchanged.
4. CONFIRMED (brief). Gaussian `modred` declares `vibrational_frequencies`
   and `ir_intensities`; ORCA's modred declares no vibrational family by
   decision. The Gaussian writer also forces `freq` onto every modred
   route inside a property getter (`self.freq = True` in `_get_dieze_tag`),
   whatever the project (and the review) said.
5. NOTED, not in scope unless it bites: Gaussian's 6-31G(d) is Cartesian
   (6D; 34 basis functions for CH2O in the R8 log), ORCA's and PySCF's
   are spherical -- one literal, two basis sets for Pople d-polarised sets.
   Every oracle below uses def2 sets (spherical in all three).

## Falsifiers of the premise (from the brief)

If a live Agent goal for each of td, scan, modred runs and reads back
correctly on this tree with no defect, the capability was there and only
its records were missing.

## Plan

A. Provider-free, in radius: (i) Gaussian td takes `response_method`
   and `state_manifold` (the ORCA/PySCF keys) and writes TD/TDA and the
   manifold itself; (ii) a Gaussian stage that names no method is refused
   when its project is validated, naming the section rule; (iii) Gaussian
   modred declares no vibrational family and computes the Hessian its
   project asks for. Shared (`shared:` commits) only where no route in
   radius exists: premise 1's solv+td disagreement and premise 2.
B. Oracle O1/O2 (CLI, same committed tree, pre-registered below before
   they run).
C. Live Agent goals G1 (td), G2 (scan), G3 (modred): execution flags
   committed before packing, reverted if the runs do not earn them.

## Found on the way (provider-free, before any job)

6. The Agent could never preview a Gaussian scan: the input reader
   called a written scan `modred` and the settings declared the
   phase's `freq: true` the route dropped -> preview red on `jobtype`
   and `freq` (cb1acd9a, f412dac0). A modred declared `freq: false` was
   red the other way (the getter forced freq).
7. OPEN. A Gaussian scan ignores the requested `start`: the hub renders
   {start, stop, points} as `S <points-1> <(stop-start)/(points-1)>`
   and Gaussian walks from the value the bound geometry already has
   (the R8 human-CLI scan from a -60 degree start ran -60..120). ORCA's
   absolute range honours `start`. Same request, different surface
   unless the geometry sits at `start`. V1 below asks whether Gaussian
   honours a value written on the S row.

## Pre-registration

(written before each job is issued; never edited after its result)

### O1 -- one td request, three programs (CLI oracle, job oracle1)

Tree: the packed commit named in the job's code-commit.txt. Geometry:
Gaussian PBE0/def2-SVP opt+freq of acrolein (s-trans) and formaldehyde
from the rough inputs in cli/oracle1; every TD reads that Gaussian log.
Request (byte-identical YAML for Gaussian, PySCF, and ORCA's
`_default` run): PBE0/def2-SVP, `response_method` tddft|tda,
`state_manifold` singlet, nstates 6. ORCA also run with NoRI (matched
numerics). Manifolds: Gaussian singlet_triplet (50-50, nstates 3), ORCA
singlet_triplet (3), PySCF triplet (3).

Bands (success / failure):
- E1 full TD-DFT: every root energy agrees pairwise among Gaussian,
  PySCF and ORCA-NoRI within 0.005 eV (roots in energy order; a pair of
  roots within 0.01 eV of each other in any program is compared as a
  pair); f within 0.002 absolute (f < 0.05) or 5 % relative.
- E2 TDA: the same bands.
- E3 physics: in each program E(TDA) >= E(TD-DFT) - 0.001 eV root by
  root; for acrolein the TDA shift of the n->pi* root (lowest, A'',
  f < 0.001) is < 0.05 eV and that of the brightest A' root is > 0.05 eV.
- E4 numerics: ORCA default (RIJCOSX) vs NoRI within 0.005 eV per root.
- E5 manifold: Gaussian 50-50 returns 3 singlets + 3 triplets; its
  triplets agree with PySCF's triplet roots and ORCA's triplets within
  0.005 eV; its singlets equal its own singlet run's first 3 within
  0.001 eV.
- E6 reference: SCF energies Gaussian vs PySCF vs ORCA-NoRI within
  3.5e-4 Eh (the lesson's default-numerics spread).
- Falsifier: any root > 0.02 eV apart between programs for the same
  words = the hub translating one request into two calculations; no
  Agent TD goal is judged against the oracle until it is explained.

### O2 -- relaxed torsion scan and constrained optimisation, H2O2 (same job)

B3LYP/def2-SVP (ORCA NoRI). Gaussian scan from an exactly cis geometry
(dihedral 0.000), `S 12 15.0`; ORCA absolute range 0 -> 180, 13 points.
Constrained optimisation of D(3,1,2,4) from an exactly 90-degree
geometry in both programs.
- S1: both scans report 13 points at 0, 15, ..., 180 degrees (+-0.01).
- S2: relative profiles (each to its own lowest point) agree point by
  point within 0.05 kcal/mol; cis and trans barriers within 0.05.
- S3 physics (wide, not the oracle's purpose): minimum between 105 and
  125 degrees; cis barrier > trans barrier; cis 5-12, trans 0.2-2.5
  kcal/mol.
- M1: both modreds hold 90.00 +- 0.01 degrees in the reached structure;
  totals within 3.5e-4 Eh of each other; each program's modred energy
  within 2e-5 Eh of its own scan's 90-degree point.
- V1 (fact-finding, no band): a raw g16 input from the 90-degree geometry
  with the row `D 3 1 2 4 0.0 S 2 15.0` -- does the first scan point sit
  at 0.0 (Gaussian honours a value on an S row) or at 90?

### G1 -- Gaussian TD-DFT and TDA through the Agent (qualification of gaussian:cpu:td)

Task (fixed before issue, `goals/g1-td/TASK.md`): acrolein from the same
rough geometry as O1; "Using Gaussian at PBE0/def2-SVP, relax it to its
ground-state minimum and compute the six lowest singlet vertical
excitations there twice, full TD-DFT and Tamm-Dancoff; identify the
n->pi* and the brightest pi->pi* and how much TDA moves each."
- Success: at least one Gaussian `td` node executed under the approval
  chain, validated and parsed; the Agent's reached geometry's SCF energy
  within 1e-5 Eh of O1's acro_opt; its excitation energies within 0.003 eV
  and f within 0.002 of O1's Gaussian runs of the same response; the
  n->pi*/pi->pi* identification and the TDA shifts as in E3.
- Failure: no td node executes, or a td result reads back as a different
  quantity than O1's (energy other than the SCF reference; roots in eV
  that do not match), or the TDA route is unreachable through typed
  settings.
- Settlement read from the ledger, never from the report.

## Jobs issued

| Slurm | slot | what | code | pre-registration |
|---|---|---|---|---|
| 2150076 | r10-q7-a | cli/oracle1: O1 + O2 + V1 (26 CLI runs, one raw g16) | 7111e2a6 | 934ac3012b56 |
| 2150077 | r10-q7-b | goals/g1-td: Gaussian TD-DFT + TDA on acrolein | 7111e2a6 | 934ac3012b56 |

## Status

- step 0: base verified; premises 1-5 reproduced locally.
- step 1: seven commits (4b5cf161 .. de7c78ea) -- the shared td
  vocabulary, the scan/modred preview, the modred declaration, the td
  validation refusal and the td section view; execution flags for td,
  scan, modred committed before packing (test_every_executable_program_
  jobtype_has_a_qualification_record is red until the runs are recorded
  or the flags withdrawn).
