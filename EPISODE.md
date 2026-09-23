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
   honours a value written on the S row. [Later: it does not -- V1 read
   the row as `B` and dropped the scan -- so 85679b4d measures the
   geometry and refuses a start it does not have, naming the edit.]

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

### O3 -- H2O2 with its O-O bond held at 1.60 A (job oracle3, before G2)

B3LYP/def2-SVP. Free minimum from the G2 start (`h2o2.xyz`, torsion 115.0)
and a constrained optimisation of B(1,2) from a copy with O-O exactly
1.600 A, in Gaussian and ORCA (NoRI).
- M2: both hold O-O at 1.6000 +- 0.0005 A in the reached structure; the
  cost E(OO=1.60) - E(min) agrees Gaussian vs ORCA within 0.05 kcal/mol
  and lies in 3-9 kcal/mol (harmonic estimate ~6.8 with k ~ 4.5 mdyn/A,
  anharmonicity lowers it); the free minima's torsions agree within 0.5
  degrees.

### O4 -- formaldehyde's sixth full-TD-DFT root, and ORCA's grid (job oracle3)

O1 result that motivates it (read through ChemSmart's readers, below):
formaldehyde's sixth TD-DFT root is 11.2538 eV (f 0.0102) in Gaussian and
11.2560 (f 0.0100) in ORCA but 11.2333 (f 0.4696, converged) in PySCF,
0.0205 eV apart -- the O1 falsifier's threshold -- while roots 1-5 agree
Gaussian vs PySCF to 6e-4 eV; and ORCA's root 4 sits 0.0059 eV above both
(E1's 0.005 band missed).
- Explanation under test: PySCF's sixth root is the bright pi->pi* that
  full TD-DFT pulls ~0.4 eV below its TDA position, and Gaussian's and
  ORCA's Davidson guesses at nstates=6 did not capture it; the three
  programs solve one Hamiltonian. Holds if with nstates=10 Gaussian and
  ORCA list a root at 11.233 +- 0.005 eV with f >= 0.4 and PySCF lists the
  11.254 root (f ~ 0.010), and the 10-root spectra agree pairwise within
  0.005 eV. Falsified if Gaussian and ORCA still show no such root.
- ORCA's root 4 is grid numerics if ORCA at defgrid3 (NoRI) moves it to
  within 0.002 eV of Gaussian's 9.7621; falsified otherwise.

### G2 -- a Gaussian relaxed scan and a constrained optimisation through the Agent (qualification of gaussian:cpu:scan and gaussian:cpu:modred)

Task (fixed before issue, `goals/g2-scan-modred/TASK.md`): H2O2 from a
geometry at its 115.0 degree torsion; "Using Gaussian at B3LYP/def2-SVP:
(1) map the relaxed H-O-O-H torsion profile from 0 to 180 in 15-degree
steps, report the lowest point and the cis and trans barriers relative
to the fully relaxed minimum; (2) relax it with the O-O bond held at
1.60 A, report the cost relative to the minimum and the torsion there."
Code: the pack after b27e0add (scan start held to the geometry,
constrained family, all Q7 fixes).
- Success: at least one Gaussian `scan` node and one `modred` node
  executed under the approval chain, validated and parsed; the scan's
  relative profile within 0.05 kcal/mol of O2's Gaussian scan at every
  common point (cis 8.30, trans 0.53 kcal/mol above the 120-degree grid
  point); the held O-O 1.6000 +- 0.0005 A in the reached structure and
  its cost within 0.05 kcal/mol of O3's Gaussian value; the torsion of
  the stretched structure within 1 degree of O3's.
- Failure: no scan or modred node executes; a scan surface that is not
  the requested range (the defect 85679b4d refuses) reaches a claim; a
  refusal with no route leaves the task unanswerable.
- Recorded, not scored: whether the session edits the torsion to 0
  before the scan unprompted, or meets scan.start_is_where_the_geometry_is
  and follows its route.

## Results read so far (host records, through ChemSmart's readers)

G2 (Slurm 2150187, code 01c34759, digest fb681a6f on the node, 22:37,
two cycles, no revision, settled `achieved`):
- Cycle 1 ran opt+freq (9.1 s), scan (28.6 s) and modred (8.3 s) in one
  wave; the approved analysis chain rendered four claims provider-free.
  The host qualified gaussian:cpu:scan, gaussian:cpu:modred and
  gaussian:cpu:opt in the goal ledger; records appended (b6b94b91).
- Scan: the hub wrote `D 3 1 2 4 S 12 15.0` under `opt=modredundant`
  (no freq); 13 points at 0.000 .. 180.000. Every total within 1.9e-7 Eh
  of O2's Gaussian scan, relative profile within 1e-4 kcal/mol; cis
  8.2988, trans 0.5343 kcal/mol above the opt minimum (-151.423093111 Eh,
  = O3's to every digit; the 120-degree point is 0.00024 kcal/mol above
  it). PASS.
- Modred: `B 1 2 F` under `opt=modredundant freq`; converged 1, held
  O-O 1.59999982 A, E -151.413821057 Eh (= O3's Gaussian run to every
  digit), cost 5.8183 kcal/mol, torsion 141.538 degrees (O3: 141.54).
  PASS on every G2 band.
- Recorded, not scored: the session set the torsion to 0.0 (set_dihedral,
  115.0 -> 0.0) and the O-O to 1.60 (set_bond_length) before planning,
  unprompted; it never met scan.start_is_where_the_geometry_is. Refusals
  it met and recovered from: 'deg' on `scan_coordinate_values` (declared
  dimension 1), an expression unit, and a `gaussian_output` requirement.
- Found by the run, left (outside what the milestone needs): a Gaussian
  scan point cannot be carried forward. The first plan put an sp on the
  scan's minimum through a geometry edge; the scan-minimum rule admits
  ORCA scans only (execution.py `is_validated_scan_minimum_geometry_edge`),
  so the node blocked approval and the session dropped it. In cycle 2
  `bind_scan_point_geometry` failed with a raw `KeyError: 'geometry_file'`
  (tool_runtime.py `_bind_scan_point_geometry` indexes a key Gaussian's
  `scan_point_records` -- index only -- does not carry). The session
  measured the lowest point's torsion on the opt minimum (120.64 degrees)
  and stated why in its decision. `about_relaxed_scans` tells every
  program's session both routes exist.
- Found by the run, left: project validation told the session "this
  gaussian/modred project already requests a frequency calculation.
  Declare vibrational_frequencies on this same scientific node", and it
  did, while the modred reader declares no vibrational family (54cb1354;
  ORCA's never did). The guidance reads the freq flag, not the reader.

G1 (Slurm 2150077, code 7111e2a6, digest 4d7248e7 on the node, 25:54,
three cycles, one revision admitted, settled `achieved`):
- Cycle 1 opt+freq (10.6 s) reached E = -191.544925639 Eh, 0 imaginary
  modes -- O1's acro_opt to every digit. Cycle 2: `td-lr` and `td-tda`
  on the reached structure; the executed projects use only the shared
  words (`response_method: tddft|tda`, `state_manifold: singlet`), and
  the hub wrote `TD(singlets,nstates=6,root=1)` / `TDA(...)`. All twelve
  roots and strengths equal O1's Gaussian runs to the printed digit
  (max |dE| 0.0 eV, max |df| 0.0). SUCCESS on every G1 band.
- Host qualified gaussian:cpu:td (td-lr, td-tda) and gaussian:cpu:opt
  in the goal ledger; release record appended (ddb27003).
- Seen in the stream (not scored): the cycle-1 planning session first
  wrote `gas: {pbe0, def2-svp}` + `td: {nstates, response_method,
  state_manifold, states}`; both td projects were refused at validation
  (550db183's refusal); after an id-reuse refusal it wrote the level into
  `td:` and validated. On the base tree the same project validated and
  would have died in the writer at preview.

O3 (Slurm 2150078): free minima G -151.423093111 / O -151.423096824 Eh,
HOOH 120.64 / 120.76 degrees; O-O held at 1.6000 A in both (1.59999982 /
1.60000008); cost 5.8183 (G) / 5.8186 (O) kcal/mol; stretched torsion
141.54 / 141.35 degrees. M2 PASS.

O4 (Slurm 2150078):
- Explanation HOLDS: with nstates=10 Gaussian lists 11.2336 eV f 0.4698
  and ORCA 11.2367 f 0.4699 as root 6 (the bright root PySCF found at
  11.2333, f 0.4696), with 11.2538 / 11.2565 f 0.010 as root 7; PySCF's
  10 roots agree with Gaussian's within 4e-4 eV throughout. At nstates=6
  Gaussian's and ORCA's Davidson solvers missed a root PySCF did not:
  one Hamiltonian, not a translation defect. The O1 falsifier fired on
  an artefact of the requested root count, and the explanation was tested
  before any Agent TD result was judged.
- Grid explanation only PARTLY holds: ORCA at defgrid3 moves formaldehyde
  root 4 from 9.7680 to 9.7648 eV against Gaussian's 9.7621 -- 0.0027 eV,
  outside the pre-registered 0.002. ORCA's TD kernel printed a
  Lebedev-194 angular grid even at defgrid3; the residual is unexplained
  and is recorded as such (numerics not demonstrated at matched tight
  settings).

O2 + V1 (Slurm 2150076):
- S1 PASS: both scans report 13 points at 0, 15, ..., 180.
- S2 PASS: relative profiles agree within 0.0014 kcal/mol at every
  point; totals within 7e-6 Eh (Gaussian B3LYP vs ORCA B3LYP/G, NoRI).
- S3 PASS: lowest grid point 120 degrees; cis 8.2986 (G) / 8.2991 (O),
  trans 0.5340 / 0.5334 kcal/mol above it.
- M1 PASS: both modreds hold 90.00 degrees (90.0001 ORCA); totals
  -151.421889474 (G) and -151.421893002 (O), 3.5e-6 Eh apart; each
  equals its own scan's 90-degree point to 1.2e-7 (G) and 1.2e-6 Eh (O).
- V1: Gaussian read `D 3 1 2 4 0.0 S 2 15.0` as `D 3 1 2 4 0.0000 B`,
  set the torsion to 0.0 and ran a plain optimisation -- the scan
  silently dropped. A value on the scan row is not a start; the hub
  cannot translate `start` into Gaussian's input, so it measures the
  geometry and refuses instead (85679b4d).
- Found by reading back: ORCA names the held dihedral 4-2-1-3 where
  Gaussian names 3-1-2-4 -- one torsion, either end first.

O1 (Slurm 2150076, code 7111e2a6, digest 4d7248e7, all 22 TD runs exit 0):
- Acrolein, full TD-DFT, the same YAML in three programs: Gaussian
  [3.6243, 6.5343, 7.0517, 7.5042, 8.1764, 8.5038] eV, PySCF within
  3e-4 eV of it root by root, ORCA-NoRI within 0.0028; f of the bright
  pi->pi* 0.3812/0.3812/0.3813. E1 PASS.
- Acrolein TDA: max pairwise 0.0030 eV; f 0.4961/0.4961/0.4963. E2 PASS.
- E3 PASS: TDA >= TD-DFT for every root in every program; n->pi* (A'')
  +0.0265 eV, bright pi->pi* (A') +0.439 eV.
- E4 PASS (ORCA RIJCOSX vs NoRI <= 0.002 eV). E5 PASS: Gaussian 50-50
  gives 3 singlets identical to its singlet run and triplets
  [2.9781, 3.1960, 5.6484] vs PySCF [2.9780, 3.1952, 5.6477] and ORCA
  [2.9760, 3.1960, 5.6470]. E6 PASS: SCF G -191.54492564, P -191.54496779,
  O-NoRI -191.54499556 Eh.
- Formaldehyde: E1 MISSED as recorded under O4 (root 6 PySCF vs G/O
  0.0205 eV; ORCA root 4 0.0059 eV); TDA agrees to 5e-4 eV (G vs P) and
  0.005 (O); E3, E5, E6 pass.
- Found by reading back, not asked: in ORCA's singlet_triplet runs
  `excitation_energies` lists singlets then triplets while
  `oscillator_strengths` lists states in energy order, so the two vectors
  are not parallel: acrolein's f = 0.3810 is paired with the T2 energy
  3.196 eV and the bright S2 (6.536 eV) with f = 0. Gaussian's two
  vectors are parallel (energy order). ORCA reader, outside this radius.
- PySCF serves `excitation_energies` in Eh (declared) and
  `singlet_excitation_energies` in eV; Gaussian and ORCA serve eV. The
  unit travels with the value, so arithmetic stays canonical.

## Jobs issued

| Slurm | slot | what | code | pre-registration |
|---|---|---|---|---|
| 2150076 | r10-q7-a | cli/oracle1: O1 + O2 + V1 (26 CLI runs, one raw g16) | 7111e2a6 | 934ac3012b56 |
| 2150077 | r10-q7-b | goals/g1-td: Gaussian TD-DFT + TDA on acrolein | 7111e2a6 | 934ac3012b56 |
| 2150078 | r10-q7-a | cli/oracle3: O3 + O4 (8 CLI runs) | 7111e2a6 | c93b714f29ff |
| 2150187 | r10-q7-a | goals/g2-scan-modred: Gaussian scan + modred on H2O2 | 01c34759 | aa3d50212db4 |

## Status

- step 0: base verified; premises 1-5 reproduced locally.
- step 1: seven commits (4b5cf161 .. de7c78ea) -- the shared td
  vocabulary, the scan/modred preview, the modred declaration, the td
  validation refusal and the td section view; execution flags for td,
  scan, modred committed before packing (test_every_executable_program_
  jobtype_has_a_qualification_record is red until the runs are recorded
  or the flags withdrawn).
- step 2: O1/O2/V1/O3/O4 read; 85679b4d (scan start refused with its
  edit), b27e0add (Gaussian constrained family), 8d07d2c7 (ORCA strength
  paired with its state) from what the oracles showed.
- step 3: G1 and G2 settled achieved; gaussian:cpu:td, scan and modred
  recorded (ddb27003, b6b94b91); the ladder test is green again.
  Milestone A claimed; nothing further started.
