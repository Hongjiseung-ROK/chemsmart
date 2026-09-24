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

## Status

- Census: done (above).
- Next: PySCF stability record keeps PySCF's own answers (writer), then the
  reader serves them; Gaussian/ORCA census items; live goals pre-registered
  below before any is issued.
