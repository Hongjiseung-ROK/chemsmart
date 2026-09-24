# R10 episode Q13 -- what the programs print that the Agent never sees

Base SHA: 4db49c22b6dfab29a4ceca9eba4b59245bda0b7e (verified with `git rev-parse HEAD` at start).
Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

Which quantities Gaussian, ORCA, PySCF and xTB print that bear on the science
the Agent is asked to do reach it as neither typed evidence nor a pointer to
where they sit? For each one that matters: can the hub serve it under the same
reader contract as every other selector, or, failing that, can the Agent be
told truthfully that the output holds it? Does serving it change what the
Agent concludes?

Two failure shapes are hunted:
- a printed quantity the science needs that no reader serves;
- a host statement of absence ("not determined") about something the output
  determines.

## Falsifier of the premise (from the brief)

Census the archived real outputs under /project/xlzhang/jiseung/ (sealed goals
r10/q6/goals and r10/q3 excluded; the master's r10/m* excluded) and tests/data.
If the quantities that matter are only the few named in the brief (PySCF
real->complex stability and the stability eigenvalues, Gaussian <R**2> and
molar volume, ORCA Hirshfeld spin populations), serve those and end. If a live
goal shows serving them changes nothing the Agent concludes, that is the
result.

## Census (provider-free, 2026-09-24)

Scope: 1,459 files pulled from /project/xlzhang/jiseung (miniforge3, the
deployed checkout, r10/q6/goals, r10/q3, r10/m*, r10/q13 excluded; slurm
outputs excluded) plus the worktree's tests/data. Program identified from each
file's own banner: 324 Gaussian logs, 273 ORCA outputs, 409 PySCF logs (plus
their .h5), 126 xTB outputs. Each printed block was counted once per file and
checked against the live readers (`RESULT_READERS[...].accessors`).
Script and tables: scratchpad q13/census (census.py, census.json); bundle on
CUHK /project/xlzhang/jiseung/r10/q13/census/.

Judged by one question: would a scientist use it to answer, or to question,
a task of the kind the Agent receives (reaction/BDE/pKa/redox energetics,
spin states and stability, excitations, spectra, solvation, bonding)?

Printed, unserved, and it matters (serve):
| quantity | program | files | parsed? | who asked |
|---|---|---|---|---|
| real->complex stability verdict | PySCF log | 26 | no; the record says "not determined" | gdev1 (Q1) settled with "a complex-rotation analysis would be needed for the remainder" while its log printed real->complex UNSTABLE, lowest eig -0.0383 |
| lowest stability-matrix eigenvalues (internal, real->complex, external) | PySCF log | 26-28 | no | r9/pyscf g2-stability declared both as observables; settled unreachable_from_evidence while the log printed them (out:2595-2599) |
| lowest stability-matrix eigenvalue | Gaussian | 11 | no (verdict only) | same science as PySCF's, other program |
| <R**2> electronic spatial extent | Gaussian | 267 (every population analysis) | no | Q10 LG1 (seeded) |
| molar volume (`volume` keyword) | Gaussian | 2 (+5 SMD logs print a solvent's 0.000 under the same words: a trap) | no | Q6 ar04/ar10 (sealed; quoted by Q10) |
| T1 diagnostic of coupled cluster | ORCA | 16 (DLPNO and canonical) | no | none recorded; it is the standard single-reference check of every CCSD(T) number |
| SMD-CDS (non-electrostatic) energy | Gaussian | 14 (tests/data SMD logs) | no | the solvation charter topic states "No archived Gaussian log carries the printed terms" -- false of tests/data |
| Mayer bond orders, Mayer free valence | ORCA | 238 (printed by default) | YES, never served | bond order questions; xTB WBO is served |
| Hirshfeld spin populations | ORCA, Gaussian | 0 open-shell outputs archived (closed shells print 0.000) | YES, never served | the brief; no archived open-shell output exercises it |

Printed, unserved, and derivable or low value (not served; reported):
thermochemistry components (ZPE, H, S, G corrections; 78 G / 57 ORCA / 50 xTB:
`derive_thermochemistry` computes them from served frequencies with stated
conventions), rotational constants and symmetry numbers, point group, nuclear
repulsion, energy components and virial ratio (ORCA), SCF cycle counts and
optimiser criteria values, APT charges (88), Fermi-contact couplings (50),
Raman activities (50), CD rotatory strengths (29), quadrupole and higher
multipoles (Gaussian 267, xTB 121; frame-dependent), polarizability (Gaussian
freq 89 -- some print "Exact polarizability: 0.000 ..." beside an approximate
one, a trap; xTB's alpha(0) is the D4 model's, not a response property),
Gaussian CM5 (charter: deliberately undeclared), "Low frequencies" line.

Premise verdict: partly falsified. The brief's few are not the whole class:
the census adds the Gaussian stability eigenvalue, ORCA's T1 diagnostic,
Gaussian's SMD-CDS term (where a charter sentence states an absence the
archive contradicts) and a second class -- quantities CHEMSMART's own parsers
already read and no reader serves (ORCA Mayer bond orders and free valence,
Hirshfeld spin populations). And one named item is thinner than stated: no
archived open-shell output prints a nonzero Hirshfeld spin population.

## The control already on disk (read from host records, CUHK)

gdev1 (R10 Q1, Slurm 2149848, code e687b9cf): singlet O2 as a closed shell,
B3LYP/def2-SVP, 1.2075 A, PySCF. Settled achieved_with_observations. The
session's finding: "(i) internal -- stable ... with real->complex rotations
not determined by PySCF; (ii) external -- unstable to RKS->UKS". Its recorded
uncertainties: "internal real->complex rotations were recorded as not
determined by PySCF (anomaly e41265...) ... a complex-rotation analysis would
be needed for the remainder." The same run's log prints
"rhf_real2complex: lowest eigs of H = [-0.0383 ...]" and "wavefunction has an
real -> complex instability". The host's false absence became the Agent's
stated uncertainty.

## Jobs issued

### stab1 -- CLI reference (slot a), code 0a77574f (tree digest 67373b31)

The eight stability fixtures of the 2026-09-19 rounds regenerated through the
ordinary CLI by the driver that listens (same projects, inputs, states), plus
reference.py (PySCF's own recomputation) beside each. Expectation, written
before the run, from the archived 2.14.0 logs of the same inputs:
- every record carries analyses.real_to_complex (except ROHF H atom, where no
  external analysis runs) and not_determined is empty where it is answered;
- each recorded lowest eigenvalue equals the number its own log prints, to
  the printed precision (8 significant digits);
- O2 singlet RKS: internal stable (|lowest| < 1e-5), real->complex unstable
  (-0.040 .. -0.036 Eh), RKS->UKS unstable (-0.095 .. -0.090 Eh);
  O2 singlet RHF: real->complex unstable (-0.052 .. -0.046), RHF->UHF
  unstable (-0.135 .. -0.127); O2 triplet UKS: real->complex stable
  (0.20 .. 0.22), UKS->GKS unstable (-0.031 .. -0.027); water RKS: all
  stable (real->complex 0.25 .. 0.28, external 0.22 .. 0.25); scf_maxiter 2:
  internal unstable at scf_converged false; hess: as the singlet sp.
- falsified if a record says real->complex not determined while its own log
  prints the verdict, or a recorded eigenvalue disagrees with its log.

### stab1 read (CUHK 2151881, COMPLETED)

Eight runs through the CLI on code 0a77574f (tree digest 67373b31 verified
on the node). All eight records carry what the log printed: 0 disagreements
between each record's lowest_eigenvalues and its own log's printed arrays;
real->complex present in 7 (absent only in the ROHF H atom, where no external
analysis runs), not_determined empty in all 8. Every value inside its
pre-registered band (singlet RKS: internal 1.97e-6, real->complex -0.03830,
RKS->UKS -0.09262; RHF: -0.04903 / -0.13108; triplet UKS: real->complex
+0.2123, UKS->GKS -0.02928; water: +0.2650 / +0.2377; unconverged: internal
-4.0e-4 at scf_converged false). Receipts validated (7) and failed
(the scf_maxiter 2 run, as archived). Premise confirmed: the writer can hold
what PySCF's analysis said.

## Replay before the live goals (provider-free)

The two archived control results (gdev1 rks-stab-sp; r9 g2-stability
pyscf-sp-stab), read through the reader of the base export (4db49c22) and of
this tree (c799cc9d); script scratchpad q13/replay/replay_reader.py:
- base: real->complex "not determined" with PySCF's excuse only; no
  eigenvalue selector exists.
- this tree: the same absence, now followed by "this run's own PySCF log
  prints it: o2_sp_gas_phase.out:2347: rhf_real2complex: lowest eigs of H =
  [-0.03829977 ...] | :2348: ... has an real -> complex instability", and for
  r9 g2 the lines Q10 cited (out:2595-2600), in the extraction absence and in
  the sensor's not_determined reason. Archived records are pointed at, never
  re-read for a value.

## Pre-registration of the live goals (written before either is submitted)

Both goals re-run an archived control's exact TASK.md, workspace geometry
(sha256-identical) and envelope shape on code c799cc9d, so the difference is
the tree. Agent: deepseek-v4-flash-0731 via alibaba-token-plan; approval
granted by claude-researcher-q13-owner-delegated (delegated, never a human
decision). One run each: two observations, not rates.

### o2r -- gdev1's task (singlet O2 as a closed shell, B3LYP/def2-SVP, 1.2075 A)

Control: gdev1 (Slurm 2149848, code e687b9cf): achieved_with_observations;
its finding and recorded uncertainty say real->complex was "not determined
by PySCF" and "a complex-rotation analysis would be needed for the remainder".
Envelope identical to gdev1's (pyscf cpu; 8 cores, 16 GB; node 1800 s;
episode 5400 s; 4 engine calls; 2 revisions).
- Physics bands: E(RKS) -150.14190 .. -150.14170 Eh; internal stable with
  |lowest| < 1e-5 Eh; real->complex unstable, lowest -0.040 .. -0.036 Eh;
  RKS->UKS unstable, lowest -0.095 .. -0.090 Eh.
- PASS (capability, host records): the run's own records -- extraction
  receipt or the scf.reference_unstable anomaly -- carry real->complex as
  determined (unstable) with its number in band, and no host-written word
  calls it not determined.
- PASS (what the Agent concludes; reported for this model): the session's
  finding/recorded decision states the real->complex answer as determined.
  FAIL: it again states real->complex undetermined, or needing a further
  analysis, while the evidence it holds determines it.
- Reported, not scored: whether it extracts the eigenvalues; whether it
  interprets real->complex (e.g. the real (pi*)^2 determinant is not the
  proper a1-Delta_g component) or only lists it.
- Not counted: zero provider turns; turn_deadline_exceeded (infrastructure).

### dans -- r9 g2-stability's task (DANS, CAM-B3LYP/def2-SVP, 36 atoms)

Control: r9 g2-stability (Slurm 2145043): settled unreachable_from_evidence
after the session declared the lowest internal and external eigenvalues as
observables and could extract only the words. Envelope scaled down from r9's
64 cores to 16 cores / 48 GB (the brief's low HPC demand); node 7200 s,
episode 4 h, 3 engine calls, 2 revisions.
- Physics bands (from r9's own log): E -878.08489 .. -878.08486 Eh; internal
  lowest 0.53 .. 0.58; real->complex lowest 0.108 .. 0.119 (stable); RKS->UKS
  lowest 0.040 .. 0.044 (stable).
- PASS (capability): if the session declares numeric stability observables,
  they are delivered from extraction receipts of the new selectors and the
  goal does not settle unreachable_from_evidence on them; real->complex is
  reported answered (stable).
- Neutral (reported): the session declares no numeric observable -- then
  the result is what it concludes from the words, compared to r9's.
- FAIL: a numeric stability observable is refused or settled unreachable
  while the new selectors resolve it on the run's own result.

### Submitted (2026-09-24, code 09450c74 = chemsmart/ of c799cc9d, tree digest 0dd950b2)

- o2r: CUHK Slurm 2152079 (slot r10-q13-a), pre-registration digest
  1fd060a2885c; TASK.md byte-identical to gdev1's, o2.xyz sha256 ac5abff5...
  identical to gdev1's.
- dans: CUHK Slurm 2152080 (slot r10-q13-b), pre-registration digest
  1fd060a2885c; TASK.md byte-identical to r9 g2-stability's,
  dans-opt-geom.xyz sha256 cf59ed6d... identical to r9's.

### A finding while the goals run: PySCF's three eigenvalues are three normalisations

Water RKS B3LYP/def2-SVP, local PySCF 2.13, against tdscf's own A and B:
internal lowest 1.15100 = 4 x lowest(singlet A+B) 0.28775; real->complex
0.26504 = lowest(singlet A-B) exactly; external 0.23765 (triplet block). So
the numbers compare within one question (across molecules, and against
PySCF's -1e-5 line), never across questions: "internal 0.556 vs external
0.042" (r9's DANS) is not "external is closer to instability" by a factor 13;
by the textbook matrices it is 0.139 vs 0.042. The reader serves PySCF's own
numbers (the verdict rule is PySCF's, on them); the declaration says so.

### gstab1 -- Gaussian CLI reference (queued behind the goals), code 09450c74

Gaussian 16 on the molecules of PySCF's stability fixtures, B3LYP/def2-SVP,
through the ordinary CLI with the analysis keyword on the route channel:
O2 singlet `stable`, O2 singlet `stable=opt`, O2 triplet `stable`, water
`stable`, water `volume`. Expectation (written before the run):
- O2 singlet: an RHF -> UHF-type instability printed as its own sentence
  (the archive holds none; the parser knows only "internal", "external" and
  "stable under the perturbations considered", so an RHF -> UHF verdict would
  be read as no verdict at all -- the defect this run tests for), lowest
  stability eigenvalue negative. If Gaussian's matrix is the triplet A+B in
  Eh, the value lies in -0.10 .. -0.08 (PySCF's external: -0.0926); any other
  factor is reported, not scored.
- stable=opt: the instability, then a re-optimised wavefunction ending
  "stable under the perturbations considered".
- O2 triplet and water: stable; water's lowest eigenvalue positive.
- water volume: 100 .. 230 bohr^3 per molecule (15 .. 35 cm^3/mol); every
  log prints <R**2> (17 .. 21 au for water at this level).

## o2r read from host records (CUHK 2152079, COMPLETED 19:34)

Code 09450c74 imported from the goal's code dir (digest 0dd950b2 verified).
Cycle 1 planned and ran one PySCF sp with scf_stability (9.8 s, validated);
the run's sensor recorded scf.reference_unstable with unstable_questions
[external, real_to_complex] and unstable_rotation_spaces
[RHF/RKS -> UHF/UKS, real -> complex], nothing not determined. Cycle 2's
woken session (13 provider turns, all deepseek-v4-flash-0731) extracted the
new selectors in typed receipts and recorded decision o2-rks-stability-verdict.
- Physics, every number in its pre-registered band: E(RKS)
  -150.14180675 Eh; internal lowest -3.2e-7 Eh (stable); real->complex
  lowest -0.0382999 Eh (unstable); RKS->UKS lowest -0.0926179 Eh (unstable).
- PASS (capability): the host's records carry real->complex as determined,
  with its number; no host word calls it not determined.
- PASS (what the Agent concludes): an unrequested finding
  "f-real-complex-unstable" -- "PySCF's separate real-to-complex analysis
  also prints 'unstable', with lowest eigenvalue -0.0383 Eh, so the RKS
  point has a descent direction into a complex-orbital solution as well" --
  on host-checked relations (word == 'unstable', eigenvalue < 0), and the
  recorded uncertainty "The reference is also unstable in the
  real-to-complex direction (-0.0383 Eh), which would not be cured by
  spin-broken real orbitals alone; the physically faithful treatment of the
  true 1-Delta-g state requires a multi-configurational or spin-adapted
  approach". The control (gdev1, same task, base-era tree) said instead
  "real->complex rotations not determined by PySCF ... a complex-rotation
  analysis would be needed for the remainder". Cycle 1 already planned on
  "the sign of the lowest eigenvalue ... in each sector" (internal,
  real-to-complex, external): the served selectors reached the plan, not
  only the reading.
- Settlement: returned_to_human, "cycle 2, planning session: planned
  termination requires the latest workflow draft" -- a host contract error
  at session end (event_store.py:1096; the loop's required receipt comes
  from the host's workflow_drafts, the check from the stream's
  workflow_receipts). The completion before it was partial because the
  session encoded its yes/no answer as a validation rule it expected to
  fail ("external eigenvalue >= 0"), so every claim stood on a failed
  criterion (7 critical findings). Neither is about the served quantities;
  both are reported, neither is repaired here (outside the radius).

## dans read from host records (CUHK 2152080, COMPLETED 20:05)

Code 09450c74 (digest 0dd950b2 verified on the node). Cycle 1 planned two
PySCF single points with stability at the supplied geometry -- CAM-B3LYP
(the task's level) and, on the session's own initiative, PBE0 as a
functional check -- both validated (1915 s engine wall at 16 cores).
Cycle 2, an admitted analysis-only revision, extracted all three stability
words and all three eigenvalues from both results (receipts 1f1cfd93,
6d8b0bd2), composed the declared observable rks-stability-lowest-eig as the
minimum over the three (a typed expression) = +0.042085 Eh, and the goal
settled **achieved**: "the host completion gate certified the delivery".
- Physics, in band: E -878.08487506 Eh (r9's own -878.084875059); internal
  +0.5559, real->complex +0.1135, RKS->UKS +0.0421 Eh; PBE0 RKS->UKS
  +0.0472 (not pre-registered; reported).
- PASS (capability): the numeric stability observable the r9 control
  (2145043) settled unreachable_from_evidence over is delivered from
  extraction receipts of the new selectors; real->complex is answered
  (stable) and used.
- The Agent's side, read, not scored: its findings compare the three
  eigenvalues directly ("minimum over the internal, external and
  real-to-complex directions") -- harmless here, since PySCF's internal
  root is 4x the textbook one and the minimum is the external root either
  way -- and it converts an eigenvalue spread to kcal/mol (0.0052 Eh "~3.2
  kcal/mol"), reading a curvature as an energy difference. Its
  "relaxed-spin-square" observable is defined as the <S^2> of "the solution
  the stability analysis reaches" but is bound to the RKS reference's
  spin_square (0 by construction): the analysis follows no instability.
  All three are the model's reading, reported as such.

## gstab1 read (CUHK 2152098, COMPLETED; Gaussian 16 C.02 via the CLI)

Every pre-registered outcome held:
- O2 singlet `stable`: "The wavefunction has an RHF -> UHF instability.",
  lowest eigenvalue -0.0926178 Eh (band -0.10 .. -0.08) -- equal to PySCF's
  RHF/RKS -> UHF/UKS root at the same level (-0.0926172, stab1) to 1e-6 Eh.
  The base reader read that sentence as NO verdict: history [], verdict
  absent, reference diagnostics None, no scf.reference_unstable. Defect
  confirmed and repaired (a54aaadf).
- `stable=opt`: the same instability, then UB3LYP -150.188149645 Eh
  (<S**2> 1.0033 before annihilation) and "stable under the perturbations
  considered". Found and left: a single-job `stable=opt` route parses as
  ChemSmart's `link` job type and the log's jobtype reads None (the
  supported path is the link job type).
- O2 triplet and water: stable; water lowest +0.2376504 (PySCF external
  +0.2376507); water's lowest singlet root 0.2877508 = PySCF internal / 4.
- water `volume`: 178.644 bohr^3 per molecule (15.942 cm^3/mol), band held;
  <R**2> 19.0148 au (band 17 .. 21).

## Served this episode (all on archived real bytes, each with a witness red before)

PySCF: scf_stability_real_to_complex, scf_stability_{internal,external,
real_to_complex}_lowest_eigenvalue (0a77574f writer, 2d927932 reader,
c799cc9d pointer for records that never heard). Gaussian:
electronic_spatial_extent (54831cfb), wavefunction_stability_lowest_eigenvalue
and _rotation_space with the RHF -> UHF verdict (a54aaadf),
solvation_nonelectrostatic_energy + solvation_model + solvent for SMD
(e6385774), molecular_volume (c1c4b13f, after the shared VOLUME name
2435d55a). ORCA: t1_diagnostic (ff79f778), mayer_bond_orders and
mayer_free_valence (55f82b86; red on a lexical guard until b50b025f -- a
masked pytest exit, reported).

### hspin1 -- CLI reference (slot a), code 09450c74, pre-registered before submission

The brief named "ORCA's Hirshfeld spin populations" as printed and never
served; the census found no archived open-shell Hirshfeld output (every one
is a closed shell printing 0.000 spin). Four doublets through the route
channel's print directive, B3LYP/def2-SVP: ORCA `Hirshfeld` and Gaussian
`pop=hirshfeld` on the planar methyl radical (C-H 1.079 A) and the hydroxyl
radical (O-H 0.970 A). Expectation: each program prints a nonzero Hirshfeld
spin column; the per-atom spins sum to 1.00 (2S of a doublet) within 0.01;
the radical centre carries most of it (methyl C 0.8 .. 1.1, hydroxyl O
0.9 .. 1.1); ORCA and Gaussian agree per atom within 0.05 (same functional
form, same partition). Falsified if either program prints no spin column
for a doublet, or the spins do not close on 1.

## hspin1 read (CUHK 2152359, COMPLETED; ORCA 6.1.1 and Gaussian 16)

Every pre-registered outcome held: both programs print the spin column;
methyl radical C 0.839 (ORCA) / 0.838 (Gaussian), each H 0.054; hydroxyl O
0.965 / 0.964; every vector closes on 1.000; the programs agree per atom
within 0.0011. Served as hirshfeld_atomic_spin_populations (1f1ca4ab).

## Status

- Census: done. Live goals o2r and dans read; CLI references stab1, gstab1,
  hspin1 read; every pre-registered band held.
- Integration: r10-integration merged at 4d1f6084 (Q11, Q12, master
  commits; the writer conflict resolved keeping Q12's `__CHEMSMART_CART__`
  substitution beside the stability substitutions; the fixture README
  keeps both new sections). The merged driver still records real -> complex
  (rendered and run on local PySCF 2.13).
- Qualification: release.json records for the four PySCF selectors
  (e37bbeb2), earned by o2r and dans. Gaussian and ORCA selectors served
  this episode are tested on archived and new CLI bytes, not qualified.
- Gates on a pristine export of e37bbeb2: tests/agent 3048 passed, 0 failed;
  touched files ruff/black/isort clean; full suite: see the hand-back.
- Milestone claimed: A.
