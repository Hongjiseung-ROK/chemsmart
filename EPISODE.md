# R10 episode q31 -- every setting a project states reaches the input the program reads

Base SHA: b96e63eebe19fa9a5523a3635ea00b94454663e5 (verified with
`git rev-parse HEAD` as the first action, 2026-09-25). Model:
claude-opus-5-5[1m]. Episode id `q31`. Brief sha256 prefix a9375c2a4eaef0e0.

## The question (as currently understood)

For every setting an Agent-authored or human project can state, and for every
program and job type the Agent can run, does the setting reach the native input
the program reads, with the stated value, in the place the program honours?
Where it does not: repair at the owning layer. Then a mechanical guard that
fails the next such defect before any engine runs.

## Census C0 -- method (pre-registered before any repair)

Instrument: scratch `q31/census/census.py` (sha256 40006b37...), HOME fenced
to a fresh home holding the configuration `chemsmart config` gives a new user
(as tests/conftest.py builds it). For each (program, job type, field) where the
field belongs to the settings class that owns the job type's project section:

1. the project is the job type's base project plus the field at a non-default,
   valid value, written in the job type's own section;
2. the public CLI writes the input: `run --fake --no-scratch <program>
   --project ... <jobtype> [coordinate options]`;
3. ORACLE A (reader-independent): the written input is compared with the one
   the same base project writes without the field. Byte-identical = the
   setting never reached the input;
4. ORACLE B (the host's own readers): the Agent's `validate_project_yaml`
   receipt, then the preview verifier (`validate_preview_workspace`) over the
   same public run -- which settings it compares and what it reads back;
5. each not-written or red case is then judged by hand: not applicable to the
   job type (correctly unwritten), dropped (defect), false red (verifier
   defect), refused with a sentence (fine), crash (defect), or written in a
   form the program misreads (defect).

Falsifier of the premise: every applicable setting reaches its input in the
honoured place (then only the guard is left to build).

## Census C0 -- READ on the base tree (b96e63ee; results sha256 2da1bd90...)

Denominator: 783 (program, job type, setting) cases -- Gaussian 225 (8 job
types incl. link), ORCA 381 (8 incl. neb), PySCF 162 (6), xTB 15 (3).
Oracle A: 584 written, 89 not written, 110 CLI refused or failed.

PREMISE HOLDS (the class is not closed). Found, by class:

- Command default overrides the project (Click option default is a value):
  - ORCA `ts`: `--tssearch-type` defaults to `optts`, so a project's
    `tssearch_type: scants` runs OptTS (advertised to the Agent; the preview is
    red on it, expected scants observed optts).
  - ORCA `irc`: `adapt_scale_displ`, `sd_parabolicfit`, `interpolate_only`,
    `do_sd_corr`, `sd_corr_parabolicfit` default to False and are applied
    unconditionally; the writer writes each only when True -- so no project
    value (true or false) ever reaches `%irc`. Not advertised, so no preview
    compares them.
- Validated, accepted, never written (ORCA, all job types): `forces` (no
  EnGrad), `gbw: false`, `light_elements_basis` (advertised to the Agent; the
  preview is red on each, so the Agent cannot satisfy them).
- Written in a form the program misreads: ORCA `scf_tol: 1e-10` -> `1e-10SCF`
  (human path; the Agent path refuses scf_tol since Q28); ORCA IRC
  `monitor_internals` -> a bare `True` line inside `%irc` (and the CLI's
  `--monitor-internals` is never applied); Gaussian link `link_route` written
  with no `#`.
- A check that is red for the wrong reason (the preview verifier): Gaussian
  `dieze_tag` (compares `p` with the reader's `#p`), Gaussian `forces` (the
  reader does not read `force`), Gaussian `numfreq` (`freq=numer` is read as
  freq), and optimiser-only settings on stages that do not optimise
  (Gaussian `geom_maxiter` and `additional_opt_options_in_route`, ORCA
  `opt_convergence` on irc/sp/td): correctly unwritten, reported red; every
  Gaussian `link` preview is red (IRC fields compared on a non-IRC link).
- A check that never looks: the receipt records advertised fields only, so a
  non-advertised setting an Agent states validates and is never compared.
- Crash after validation: Gaussian `heavy_elements_basis` (advertised; its
  pair `heavy_elements` is not), Gaussian link with `ab_initio` or
  `semiempirical`.
- Gaussian link replaces a project's IRC values with hard defaults (brief
  prior; the link CLI's `x if x is not None else 512` pattern).

Not defects (principled): PySCF refuses every inapplicable combination with a
sentence; xTB 15/15 reach; loader-level overrides (freq off on irc/scan) are
reported to the Agent as `declared_settings_overridden`.

Also found while repairing: the ORCA `%irc` block iterated a set, so one
project wrote three line orders in three processes (PYTHONHASHSEED 1/2/3:
three digests of one input). Across all 800 census inputs, two processes
(seeds 11, 22) now write byte-identical Gaussian/ORCA/PySCF inputs.

## Repairs (one commit per defect; LOUD ones say so)

c421d2da CLI defaults -> None (14 options); 293fc7b9 %irc block (switches,
Monitor_Internals, order); acc01de5 Gaussian print level; 07b4c771 (shared)
Gaussian reader reads force / freq=numer; b323a3b1 preview asks the writer's
table (settings_not_written_for); 6b5bca0f + d986e8b5 (shared) ORCA forces ->
EnGrad on sp; cc8a7d44 gbw: false refused; 8b7225a2 ORCA light basis compared
with the route basis; 2a7aa27a scf_tol preset only (+ f7df2e99, the reader
regression it exposed); 192491e7 Gaussian per-element basis refused not
crashed; f037967d + 375eb7f4 Gaussian link (IRC controls kept, ab initio no
crash, route `#`, preview); c30a76cf ScanTS form (Q20's relay: CLI key/shape,
no Calc_Hess); a0a2a3be dead %irc table deleted; bba64472 PySCF preview
compares declared fields; 9569bc64 semiempirical aux/extrapolation refused;
bf050808 ORCA solvent file name; ac179b93 (shared) the signature-scan guard
deleted (it passed over all 14 options and over Q28's 512).

Guard (4c50547d, tests/agent/test_a_stated_setting_reaches_the_input.py):
the Click-level registry test and the census over the 28 executable stages
(49 s). WITNESS on a pristine export of the base b96e63ee: 15 of 28 stages
red plus the registry (14 options) -- forces x13, solventfilename x7,
light_elements_basis x7, heavy_elements_basis crash x7, dieze_tag x7,
numfreq x6, opt_convergence/geom_maxiter/additional_opt_options false reds
x9, tssearch_type x1, the five IRC switches "never written, compared by
nothing" -- and green on the repaired tree and on the merge with
r10-integration 3f3331c0 (788 passed with Q20's dispersion tests).

Census C0 re-read on the repaired tree: every remaining not-written cell is
refused with a sentence, reported overridden, or declared unwritten by the
writer's table; the preview red cells left are ORCA NEB (not executable).

## Oracles O1 (ORCA 6.1.1) and O2 (Gaussian 16 C.02) -- PRE-REGISTRATION

Written before submission. CLI only (`chemsmart run`, no Agent), code = this
branch after the merge (commit named in code-commit.txt), 4 cores / 8 GB
each, B3LYP/def2-SVP. Judged by what the program prints back, not by what
was written.

O1 (ORCA):
- O1a ScanTS from the project (`ts: {tssearch_type: scants, freq: true,
  scants_modred: {coords: [[3, 2]], dist_start: 2.10, dist_end: 1.10,
  num_steps: 11}}`) on a bent HCN: PREDICT ORCA runs the relaxed scan,
  starts OptTS from its highest point and converges; Freq shows exactly one
  imaginary mode in [-1250, -1000] cm-1; the saddle's H-C in [1.10, 1.25] A
  and H-N in [1.30, 1.50] A. FAIL: an abort at the scan's first step (Q20's
  CUHK 2153578) or no saddle.
- O1b OptTS from an HCN/HNC saddle guess (freq: true): one imaginary mode in
  [-1250, -1000] cm-1.
- O1c IRC forward from O1b's saddle with every %irc switch stated false,
  MaxIter 40, InitHess calc_anfreq and Monitor_Internals over H-C and H-N:
  PREDICT ORCA accepts the block (no input error), reports the stated values
  where it prints its IRC settings, prints the monitored distances each
  step, and ends at a minimum (HCN or HNC). FAIL: an input error on the
  block, or a printed setting that contradicts the input.
- O1d `sp: {forces: true}` on a distorted water: PREDICT ORCA prints a
  CARTESIAN GRADIENT block and writes a .engrad with 9 components whose
  energy equals the single point's to 1e-8 Eh, max |g| > 1e-3 Eh/bohr.
O2 (Gaussian):
- O2a `opt` + `freq` on a distorted water with defgrid superfinegrid,
  scf_convergence tight, dispersion gd3bj, SMD water and route word nosymm
  (Q27's class: does Gaussian's generated frequency step keep every typed
  word?). H0 PREDICTED: both job steps print IRadAn 7, the GD3BJ dispersion
  energy, the SMD terms and "Symmetry turned off by external request". A
  step that lacks one FALSIFIES H0 and is a translation defect to repair.
  Physics: three real modes, bend 1550-1750 and stretches 3600-4000 cm-1.
- O2b `sp: {forces: true}`: Gaussian prints its Forces (Hartrees/Bohr) block.

## Jobs issued

- 2026-09-25: O1, CUHK Slurm 2154008 (r10-q31-a), 4 cores, pre-registration
  811ec1606bca, code a39f784b (digest 95a24b3c...); COMPLETED.
- 2026-09-25: O2, CUHK Slurm 2154009 (r10-q31-b), 4 cores, pre-registration
  811ec1606bca, same code; COMPLETED.
- 2026-09-25: O3, CUHK Slurm 2154022 (r10-q31-a), 4 cores, pre-registration
  7fbc2d629ea6, code 6c32ebf9; COMPLETED (both commands exit 0, 17:50).

## O1, O2 -- READ (from the programs' own outputs)

- O1a FAILED as pre-registered-to-fail: ORCA ran scan point 1, recomputing
  the exact Hessian (the input still carried the class default
  `Recalc_Hess 5`), carried it into point 2 (`InHess .... Read`) and stopped:
  "Error (ORCA_GSTEP): could not find the Hessian file!" (hcnscan.carthess).
  The c30a76cf repair (no Calc_Hess) moved Q20's abort from point 1 to
  point 2. Repaired again in 73c4c351 (a ScanTS carries no recalculation);
  re-run as O3a.
- O1b HOLDS: OptTS converged; one imaginary mode, -1122.72 cm-1 (band
  [-1250, -1000]; the charter's ORCA HCN/HNC saddle at this level:
  -1121.7), real modes 2091.3 and 2629.4; H-C 1.1969, H-N 1.3975 A (bands
  [1.10, 1.25], [1.30, 1.50]). CORRECTED: this section first said -1076.84
  cm-1, which my reader took from the output's first frequency block -- the
  Calc_Hess Hessian at the guess -- not the converged saddle's (line 3834,
  and hcnsaddle.hess). O3a's pre-registered comparison was written against
  that misread number.
- O1c: the settings claim HOLDS, the physics prediction FAILED. ORCA's own
  IRC settings block reads back every stated control: "MaxIter .... 40"
  (default 20), "Direction .... Forward-only", "Initial displacement Hessian
  type .... Compute analytically", "Do parabolic fit if SD step is uphill
  .... NO", "Do Correction to SD step .... NO", "Do update to length of SD
  step and correction .... NO" (ORCA's default is YES for all three: no
  project could state NO before 293fc7b9), and the iteration table carries
  the monitored B(H2,C0) and B(H2,N1) columns (Monitor_Internals applied).
  Normal termination, no input error. But the path did not reach a
  minimum: with the step corrections off, the energies zigzag (-93.281486,
  -93.280290, -93.280606, -93.282343 ...) with max|G| ~0.1 Eh/bohr and the
  walk stops at the stated MaxIter 40 ("MAXIMUM NUMBER OF ITERATIONS
  REACHED"), H-N 0.99-1.04 A and H-C 1.96 A (heading to HNC). The
  prediction "ends at a minimum" was wrong; the control O3b tests whether
  the disabled controls are the cause.
- O1d HOLDS: `!  EnGrad` -> CARTESIAN GRADIENT printed; watergrad.engrad has
  3 atoms, 9 components, energy -76.3574137395 = FINAL SINGLE POINT ENERGY
  -76.357413739454; max|g| 0.0360 Eh/bohr. Gaussian's forces on the same
  geometry (O2b) are the negative of ORCA's gradient to 6e-5 Eh/bohr
  (O: 0.036013/0.008027 vs 0.035972/0.007963).
- O2a H0 HOLDS: Gaussian's generated frequency step route is `#N
  Geom=AllCheck Guess=TCheck SCRF=Check GenChk RB3LYP/def2SVP Freq` -- no
  typed word in it -- yet its IOps carry them: 3/75=-7 (superfinegrid; the
  O2b sp without a grid has no 3/75) and 3/124=41 (GD3BJ) in both steps;
  "Nuclear repulsion after empirical dispersion term = 9.0878341267" and
  "SMD-CDS ... = 1.43" identical to the opt's last point; "Symmetry turned
  off by external request" in both; the freq step's SCF equals the opt's
  last to 1e-10 Eh (-76.3704978120). Every typed word the hub writes on an
  opt+freq route reaches the generated frequency step (Q27's class does not
  extend to them). Physics: modes 1609.6, 3770.9, 3842.8 cm-1, all real.
- O2b HOLDS: `# b3lyp def2svp force` -> "Forces (Hartrees/Bohr)" printed.

## Oracle O3 (ORCA) -- PRE-REGISTRATION

Written before submission; code = this branch at the commit named in
code-commit.txt (73c4c351 + this EPISODE.md), 4 cores / 8 GB.
- O3a ScanTS from the same project and bent HCN as O1a, on the repaired
  writer (the %geom block carries only the Scan). PREDICT: the relaxed scan
  runs past its highest point, OptTS from there converges, Freq shows
  exactly one imaginary mode within 5 cm-1 of O1b's -1076.84 cm-1 (band
  [-1250, -1000]), H-C and H-N within 0.005 A of O1b's saddle. FAIL: any
  ORCA abort, or no saddle.
- O3b CONTROL for O1c: the same forward IRC from O1b's saddle (MaxIter 40,
  InitHess calc_anfreq, Monitor_Internals) with no switch stated. PREDICT:
  ORCA's settings block prints YES for the parabolic fit, the SD correction
  and the step-length update (its defaults), and the path converges before
  iteration 40 with non-increasing energies, ending near HNC (H-N 0.98-1.02
  A). If it also zigzags and stops at 40, O1c's zigzag is NOT attributed to
  the switches.

## O3 -- READ (CUHK Slurm 2154022, pre-registration 7fbc2d629ea6, code 6c32ebf9)

- O3a: the repaired ScanTS input (`! ScanTS Freq B3LYP/G def2-svp`, %geom
  carrying only the Scan) RAN: ORCA scanned H-N 2.10 -> 1.30 A (energies
  rising to -93.27590968 Eh at 1.40 A, falling at 1.30), printed "ScanTS
  option: We are already beyond the maximum, aborting the Relaxed Surface
  Scan", refined point 8 and ran the TS optimisation to convergence;
  normal termination. Saddle: H-C 1.1957, H-N 1.3935, C-N 1.1880 A and
  -93.275909074 Eh, against O1b's OptTS saddle 1.1969, 1.3975, 1.1882 A
  and -93.275909427 Eh (|dr| <= 0.004 A, dE 3.5e-7 Eh); the Hessian at it
  (hcnscan3.hess) has one imaginary mode, -1123.57 cm-1, real 2092.7 and
  2639.3 (O1b: -1122.72, 2091.3, 2629.4). Physics band [-1250, -1000] and
  the geometry prediction HOLD. The pre-registered "within 5 cm-1 of
  -1076.84" is FAILED AS WRITTEN (47 cm-1): that number was my misreading
  of O1b (the guess's Hessian); against O1b's converged saddle the two
  agree to 0.85 cm-1. Both are reported; the corrected comparison is not a
  re-scored prediction.
- O3b (the control for O1c): its input differs from O1c's only by the five
  switch lines (`diff`: lines 10-14, nothing else). ORCA's settings block
  prints its defaults -- "Do parabolic fit if SD step is uphill .... YES",
  "Do Correction to SD step .... YES", "Do parabolic fit to SD correction
  .... YES", "Only interpolate for parabolic fit .... YES", "Do update to
  length of SD step and correction .... YES" -- with the stated MaxIter 40,
  Forward-only and analytic initial Hessian. "THE IRC HAS CONVERGED" at
  step 34 of 40 (max|G| 7.9e-4 Eh/bohr), normal termination, ending at H-N
  1.00 A and H-C 2.18 A (HNC; band [0.98, 1.02] HOLDS), -93.330312 Eh,
  34.14 kcal/mol below the saddle. The clause "non-increasing energies"
  FAILS AS WRITTEN at one step: step 32 lies 2e-6 Eh (0.001 kcal/mol)
  above step 31. The two walks are identical through step 2 (-93.277772)
  and part at step 3, where O1c's first uncorrected step begins its zigzag
  (max|G| 0.09-0.12 Eh/bohr from step 4, no convergence in 40). So O1c's
  zigzag IS attributed to the stated switches, on this one controlled
  pair: the `false` values reached ORCA and changed its walk, which is the
  walk they ask for. Not a defect of the host.

## Census C0 re-read on the final code (73c4c351; results sha256 3b18e2fc...)

Same instrument, same 783 cases: 583 written, 72 not written, 128 refused
or failed. The preview is red on the stated setting in 9 cases (base: 78):
Gaussian `append_additional_info` x8 (written, never read back; the Agent
path refuses the field) and an ORCA NEB light basis beside a semiempirical
method (not executable). Every not-written cell is one of: not applicable
by the writer's table (optimiser controls on sp/td/irc; path controls on a
non-IRC link; ORCA forces on gradient-driven stages; PySCF optimiser
settings off opt), a loader override the session is told (freq on irc and
scan), the command's own job word, a value equal to what the input already
says (ORCA light basis = route basis; Gaussian light basis without heavy
elements; the census link route), or no program field (ORCA title,
invert_constraints without frozen atoms).

## Gates (final code: aaf3d5f3 = q31 6c32ebf9 + r10-integration df78d69d)

- Full suite on a pristine export of aaf3d5f3 (chemsmart imported from the
  export): 23 failed == the round baseline (test_structures x19,
  PyscfSettings x1, aggregation x1, pyscf dispersion x2), 4863 passed; no
  failure under tests/agent. (Earlier: a39f784b, 23 failed, 4852 passed.)
- ruff, black --check, isort --check clean on the 16 Python files q31's
  own commits touch.
- The census guard on the merge with Q30's scan/thermochemistry work: 40
  passed with Q30's hindered-rotor tests.

## Found and left

- `append_additional_info` (Gaussian) is written and never read back by
  the input reader; the Agent path refuses it (Q28), the human path has no
  preview. Left.
- A Gaussian link over an IRC target is still compared against fields its
  reader does not read (the IRC leaf of the second route); link is not
  executable for the Agent. Left.
- ORCA readers stop a block at a nested `end`: `_orca_geom_values`
  (utils/mixins.py) ends %geom at the Scan sub-block's `end`, so a
  `fullScan` after it is not read back; the %irc reader ends at the first
  `end` (the writer now puts Monitor_Internals last for it). Left: shared
  file, no Agent loss.
- `run orca ts` rewrites every "ts" inside a label (`label.replace`), R10
  Q20's note. Left: not a setting.
- Two builders of the ORCA scan block: `orca_scan_block` (ScanTS) and the
  scan branch of utils/cli.py `get_setting_from_jobtype_for_orca`. Left:
  shared file; both produce the writer's form.
- ORCA `%scf` is written with `maxiter 200` whenever the block opens
  (scf_convergence, reference, broken symmetry) though no project states it
  (ORCA's default is 125): a value the host adds, not one it drops. For the
  owner.
- Gaussian `forces` on an optimising stage writes `opt ... force`; whether
  Gaussian runs that compound was not measured.
- Gaussian IRC `predictor` requires `recorrect` even for LQA, which has no
  recorrection; refused with a sentence. Left.
- The ORCA SCF preset vocabulary has `medium` where the CLI offers
  `NormalSCF`; not measured against the binary.

## For the owner (LOUD lines, not decided here)

- A person's project now takes effect where a command default replaced it
  (ORCA tssearch_type, the five IRC switches, invert_constraints, forces;
  Gaussian link IRC controls), and several `--no-...` flags now act.
- Refused where accepted before: ORCA `gbw: false`, a numeric ORCA
  `scf_tol`, ORCA `forces` on a td stage, an incomplete Gaussian
  per-element basis, an auxiliary/extrapolation basis beside an ORCA
  semiempirical method, a stated recalc_hess on an ORCA ScanTS.
- ORCA sp `forces: true` now runs EnGrad.
- Whether the host should keep writing `%scf maxiter 200` unstated.

## Status

2026-09-25: repairs, guard and oracles O1/O2/O3 read; merged
r10-integration df78d69d (aaf3d5f3); no job running. Milestone A
(reachability) claimed in the hand-back; no live Agent goal was spent.
