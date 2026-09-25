# R10 episode Q33 -- what the host calls stationary, and what it projects

- Base SHA: df78d69dd09d1d384ec684cbaaf2761d202fc57c (verified with `git rev-parse HEAD` as the first action, 2026-09-25).
- Brief: scratchpad/q33/BRIEF.md, sha256 e3ccd8e11efbbafda089a498ab99904b5d98767c71e9d90030a1dd99193d5275.
- Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

When the host says a structure is stationary (R10 Q21 `structure_stationarity`),
and when it removes a held or rotating coordinate before counting modes (R10 Q27
`free_energy_surface` / `_held_coordinate_projection`), does its word agree with
what the chemistry means in each program -- whatever that program's own
convergence criterion (internal-coordinate against Cartesian forces, max against
RMS against norm, force against displacement), whether the optimisation was
free, frozen or constrained, and whatever the symmetry of the rotating group?
Where it does not, repair it in the one function that answers it, and make every
receipt say which criterion and which projection it used.

## Premises from the brief (priors, to verify)

- Q30: the held-point projection of one H-C-C-H dihedral of ethane softened a
  CH3 rock 999.6 -> 723.5 cm-1 (+0.75 J/(K mol) in S).
- Q30: Q27's held-surface gate refused a Gaussian-converged methanol held point
  (Cartesian residual 7.5e-4 Eh/Bohr against 4.5e-4; Gaussian converges on
  internal-coordinate forces).
- Q27: `structure_stationarity` calls a Cartesian-frozen optimisation stationary
  (tests/data/GaussianTests/outputs/frozen_coordinates_opt.log); Gaussian results
  read "stationarity unmeasured" although the Freq archive holds the gradient;
  `reaction_coordinate_mode` never travels an approved DAG.

## Falsifier of the premise (census, provider-free)

Census of every archived result the host judges: CUHK R8, R9 and R10 episode
directories (q1, q2, q3/goals, q4-q16, q17/hc1, q18-q24, q26-q28, q30-q32; code,
packs, tools, private and sealed* directories excluded; no r10/m*), plus the
repository's real fixtures under tests/data. For each result: the host's
stationarity word and basis on the base tree, `free_energy_surface`, and the
program's own convergence record parsed from its raw output; for each held
result with a readable Hessian, the kept modes of the held-coordinate
projection against a rigid-top projection.

- Premise narrowed if the disagreements are the two known cases only.
- Premise falsified if the host's word and each program's own criterion agree
  everywhere except where the program's own record is itself the anomaly.

Instrument: scratchpad/q33/census/census.py (files fetched read-only from CUHK
to scratchpad/q33/census/cuhk; list r10/q33/census/files.txt on the cluster,
3,878 files, 256 MB).

## Census -- READ (base tree df78d69d, provider-free)

Denominator: 1,524 program results the readers open (CUHK 1,234: Gaussian 395,
ORCA 450, PySCF 297 .h5, xTB 53, plus 39 unopenable; repository fixtures 290).
Per result: the host's word and basis, `free_energy_surface`, and the program's
own record parsed from its raw output (Gaussian convergence tables per Link1
job, "Initial Parameters" frozen marks, printed Cartesian and internal forces;
ORCA geometry-convergence tables, Cartesian gradient blocks, "Will constrain
atom" lines; xTB level, econv, gconv, marker, final gradient norm; PySCF
converged flag and hess-stage forces).

Where the program's own record exists at the structure the modes belong to,
the host's word agrees with it everywhere except these classes (the premise's
two known cases are real and are not the only ones):

1. Held, called stationary (host `stationary`, the program froze something):
   - fixtures `GaussianTests/outputs/Pd_insertion_ts_r.log`: a `ts` search whose
     checkpoint carried two frozen Pd-C bonds (`geom=check`; Gaussian's own
     Initial Parameters table marks R(2,28) and R(4,28) "frozen"; the reader
     reads only an echoed ModRedundant section, which this log has not);
     Cartesian gradient 0.0120 Eh/Bohr; 120 modes, a TS free energy served.
   - `GaussianTests/outputs/frozen_coordinates_opt.log` (the brief's case): 10
     atoms frozen in Cartesian space; Gaussian prints their forces as exactly
     zero, so even its archive gradient cannot show the structure stationary.
   - CUHK: none.
2. Converged by its own criterion, called not stationary:
   - `XTBTests/outputs/p_benzyne_opt_alpb_toluene`: `--opt loose` ("GEOMETRY
     OPTIMIZATION CONVERGED"; gradient norm 1.18e-3 <= loose gconv 4e-3 Eh/Bohr);
     the host compares its largest component 5.51e-4 with geomeTRIC's 4.5e-4
     and says not stationary (free_energy_surface none; an energy from it is
     annotated "not a stationary point" in every expression).
   - held-surface gate (Q27): Gaussian methanol held at 115 deg
     (r10/q30/cli/o1-gau/g_meoh_heldp115.log, the brief's case): Cartesian
     residual 7.53e-4 against 4.5e-4 while Gaussian's own Freq-step check on the
     held surface says converged (predicted energy change on that surface
     -6.2e-4 kcal/mol, measured with the host's Hessian).
3. The program's own check at the modes' structure unread (host `unmeasured`):
   Gaussian freq-only jobs print their own convergence table: fixtures
   `projected_frequencies/g_sp90_gas_phase.log` (max force 3.17e-3, NO) and CUHK
   q27 O1b g_sp0 (9e-6, YES), g_sp90 (NO), g_sp180 (4.16e-4, YES).
4. A search that ended with no verdict said to be "handed its geometry"
   (`unmeasured/fixed_geometry`): 6 Gaussian + 1 ORCA fixtures, 1 Gaussian + 6
   ORCA CUHK (error terminations, killed runs); none carries modes. ORCA
   `phenol_fixed_atoms.out` (Cartesian freeze, converged) reads the same.
5. Measured, no program verdict at that structure (host `not_stationary`,
   agreement): PySCF hess at handed geometries 10 (0.003-0.034 Eh/Bohr), xTB
   GFN2 hess at a GFN-FF geometry 1 (norm 0.087). Correct.

The trap a naive repair would build: the host's Cartesian criterion (largest
component <= 4.5e-4, geomeTRIC's) is not the internal-coordinate criterion
Gaussian and ORCA converge on. Program-converged minima whose largest Cartesian
component exceeds it: Gaussian 3 (bromochloromethane fixture 4.91e-4 with
internal max force 2.93e-4; q30 ethane 8.14e-4 with 3.74e-4; q5 HCOOH 5.39e-4
with 3.83e-4), ORCA 9 (last gradient block 4.7e-4 - 1.2e-3). Reading Gaussian's
archive gradient against 4.5e-4 would refuse every one of them.

Gaussian's Freq step judges the structure with the exact Hessian; its
displacement rows fail while its force rows pass on 5 fixtures (iron quintet,
NHC, a conformer, a Fe modred, ethane held 5 deg; predicted energy change
1e-8 - 1.3e-5 Eh): forces are stationarity, displacements are step control.

## Projection census -- READ (R10 Q30 oracle O1, CUHK 2153801/2153802)

78 results (ORCA and Gaussian; H2O2, methanol, ethane; equilibrium and held
points). For each, the held dihedral's mass-weighted normal (A, Q27's
projection) against the rotor's rigid turn (B, the direction
`internal_rotors` removes), both with rigid motions removed
(scratchpad q33/census/projection_census.py):
- overlap cos^2(A, B): H2O2 0.997-1.000; methanol 0.64-0.72; ethane 0.28-0.30.
- kept-mode vibrational free energy A - B (298.15 K): H2O2 <= 0.006 kcal/mol;
  methanol -0.30 to -0.39; ethane -0.89 to -1.03 (lowest kept mode 643-726
  against 829-898 cm-1).
- one-dihedral-held structures on the rigid-turn surface: residual gradient
  up to 1.8e-3 (methanol) and 4.9e-3 Eh/Bohr (ethane), a predicted relaxation
  of at most 0.0067 and 0.081 kcal/mol (the strain one held dihedral leaves in
  a methyl top); on their own held surface at most 6.2e-4 kcal/mol.
- the profile rotor (Q30's T2 machinery, host functions): S(T2) - S(T1) with
  A: H2O2 -0.016/-0.011, methanol +0.029/+0.042, ethane +0.745/-- (ORCA/
  Gaussian; Q30's numbers reproduced exactly); with B: -0.018/-0.012,
  -0.102/-0.091, -0.381/--. B meets Q30's pre-registered P4 band (0.5 J/(K mol))
  on all three; A fails it on ethane. (B is applied to Q30's band after the
  fact, and says so.)

## Repair (as built; one commit per defect, witnesses red on the base)

1. What a program held is read from its own record: Gaussian's "Initial
   Parameters" table (frozen internal coordinates from any source, and atoms
   frozen in all three Cartesian coordinates), ORCA's "Will constrain atom"
   lines (atoms held in all three). A structure that held anything is not a
   stationary point of the full surface.
2. A structure is judged by the check of the program that judged it
   (`ConvergenceCheckV1`, one reader function per program): Gaussian's force
   rows at the structure the modes belong to (its frequency step's check with
   the exact Hessian), ORCA's printed verdict, xTB's verdict at the level it
   ran. Order: atom; held/frozen; driven; a search's own non-convergence (it
   outranks the last check: po3-r19); the program's check; a gradient no
   program judged, against the host's criterion (geomeTRIC's, PySCF's own);
   a search's marker; else unmeasured (a search that ended unjudged says so
   instead of "handed its geometry").
3. A held surface is judged by the check of the program that held it; the
   Cartesian residual is measured and stated. A structure stationary on the
   full surface is stationary on any surface through it (no second,
   foreign threshold).
4. A named dihedral that turns a group with more than one atom off the bond
   is removed as that group's rigid turn (the direction `internal_rotors`
   removes), with the overlap and the strain on the turn's surface stated.
- shared: the characterisation records the host's measured gradient
  whatever judged the structure, and names the reading's criterion.

## PRE-REGISTRATION -- oracle O1 (CLI; written before submission)

Question: is Gaussian's own convergence (which the base host refused where
the largest Cartesian component exceeded geomeTRIC's 4.5e-4) adequate for the
free energy the host now serves on it? Re-judge two Gaussian-converged
structures by re-optimising them from where Gaussian's default criterion
stopped, with `opt=tight` (max force 1.5e-5), same level (B3LYP-D3(BJ)/
def2-TZVP, Gaussian 16 C.02, CUHK), and derive through the repaired host:
- M: methanol held at H3-O2-C1-H4 = 115 deg (modred), from the end of R10
  Q30's g_meoh_heldp115 (now fixture meoh_b3lyp_d3bj_tzvp_held115.log): the
  held-surface free energy (projected_coordinates, rigid turn).
- E: ethane staggered (opt), from the end of Q30's g_c2h6_eq (now fixture
  c2h6_b3lyp_d3bj_tzvp_opt.log): the harmonic G and the torsion-projected G.
- controls: the same two restarted with the default criterion (1-2 steps).
Bands (fixed now):
- P1: both tight runs complete ("Optimization completed"); their Freq-step
  maximum internal force <= 1.5e-5 and largest Cartesian component <= 4.5e-4.
- P2 (decisive): |G(default) - G(tight)| <= 0.01 kcal/mol for M's held-surface
  G and for E's harmonic and projected G.
- Falsifier: |dG| > 0.05 kcal/mol on either -> Gaussian's default criterion is
  not adequate for these free energies, the base refusal had a physical
  point, and repair 3 is wrong in substance (it would be reverted).
- Reported, not banded: the geometry change (largest interatomic distance
  change), the electronic energy change, the controls' dG.
- Inputs (r10/q33/cli/o1 on CUHK; sha256): commands.txt f1cb4e42...,
  gau_tz.yaml a2d413fc... (Q30's gau_tz.yaml), gau_tz_tight.yaml 17a314a8...
  (the same plus `additional_opt_options_in_route: tight`; the writer
  renders `opt=(tight)` and `opt=(modredundant,tight)`, checked with
  `chemsmart run --fake`), meoh_held115_default_end.xyz e415ddcd...,
  c2h6_eq_default_end.xyz 68d25049... (both the reached structures of the
  fixtures, written by scratchpad q33/oracle/write_starts.py; H3-O2-C1-H4 =
  114.9999 deg, H3-C1-C2-H6 = 60.0000 deg). Code 2bcdc763 (digest
  955a1bd7...), 16 cores, 32 GB, 1 h. Analysis afterwards, provider-free,
  through derive_result_thermochemistry on the fetched logs.

## O1 -- READ (CUHK Slurm 2154086, COMPLETED in 2 min 17 s, 4 of 4 exit 0)

Code 2bcdc763 (tree digest 955a1bd7... recomputed on the node, 0 AppleDouble
files), pre-registration digest 6a89c4a16c86 recorded by slot_submit. Read
through the repaired host (scratchpad q33/oracle/analyse_o1.py,
residuals_o1.py; logs fetched read-only to q33/oracle/o1-runs).

| | Gaussian's check (max / rms force) | Cartesian max | held-surface residual | E (Eh) |
|---|---|---|---|---|
| M default (fixture) | 4.33e-4 / 1.53e-4, converged | 7.49e-4 | 7.5e-4 (base gate: refused) | -115.77710081 |
| M tight | 4e-6 / 2e-6, converged | 5.10e-4 | 3.7e-6 | -115.77710179 |
| M restart (control) | 4.32e-4 / 1.53e-4, converged | 6.98e-4 | 7.4e-4 | -115.77710081 |
| E default (fixture) | 3.74e-4 / 1.16e-4, converged | 8.14e-4 | -- | -79.86940037 |
| E tight | 1.2e-5 / 3e-6, converged | 8.2e-6 | -- | -79.86940181 |
| E restart (control) | 3.74e-4 / 1.16e-4, converged | 8.14e-4 | -- | -79.86940037 |

Default minus tight: M dE +0.00062 kcal/mol, geometry 1.10e-3 A, held-surface
G (rigid turn removed) -0.00014 kcal/mol (restart -0.00016); E dE +0.00090,
geometry 1.18e-3 A, harmonic G +0.00056, torsion-projected G +0.00134 (restart
+0.00055, +0.00131).
- P1: met for E. For M the maximum internal force is met (4e-6) and the
  "largest Cartesian component" I wrote is not (5.1e-4): my band was worded
  wrongly for a held point, whose full gradient carries the held torsion's
  constraint force by construction (dE/dphi = 7.8e-4 Eh/rad here). The measure
  the base gate applied, the residual beside the held torsion, is 3.7e-6.
  Reported as an error of the pre-registration, not re-scored.
- P2: met, with room: every |dG| <= 0.0013 kcal/mol against the 0.01 band.
  The falsifier (0.05) is not approached.
- Reading: the free energy the base host refused at Gaussian's default
  convergence (M, residual 7.5e-4) equals the one it would have accepted after
  a tight re-optimisation (residual 3.7e-6) to 1.4e-4 kcal/mol. The refusal
  measured a Cartesian threshold, not the chemistry. The strain one held
  dihedral leaves in the methyl group is intrinsic to the hold: 7.5e-4
  (default) and 4.6e-4 Eh/Bohr (tight) on the turn's surface.

## The profile rotor through the host's own projection (repaired tree)

Q30's T2 rebuilt with `_held_coordinate_projection` itself (scratchpad
q33/census/t2_host.py) on Q30's O1 held points: S(T2) - S(T1) in J/(K mol)
ORCA H2O2 -0.016, methanol -0.102, ethane -0.381 (12 of 12 points served
each); Gaussian H2O2 -0.011, methanol -0.091 (12 of 12, the 115-deg point
the base refused included). Equal to the scratch rigid-turn numbers above,
so the host serves what was measured. Gaussian ethane: 3 points served, 1
refused, 8 never converged (Q30): Gaussian's modred let the held dihedral
drift (5.34 deg held at 5, 55.06 at 55), the reader refuses a hold that
drifted beyond 0.01 deg, and those points then fall to the unheld branch
and its Cartesian residual -- left (below).

## Status

- step 0: brief read; base verified; AGENTS.md, CONDUCT.md, RSL README and the
  four lessons, charter validity-rules.md, merges e089d7ce (Q21), 818fe2b4
  (Q27), ef1eb516 (Q30) and Q30's EPISODE.md read; `structure_stationarity`,
  `free_energy_surface`, `_held_coordinate_projection`, `_internal_rotor_treatment`,
  the thermochemistry kernel's projection and the readers' gradient/Hessian
  functions read. Cluster gate open.
- step 1: census and projection census read (above). Premise narrowed? No:
  widened -- five classes, two of them the brief's.
- step 2: repairs committed, one per defect: 3041b7fb (shared:
  characterisation), cfaffd58 (held/frozen), 6ca94a2f (the program's own
  check), b25ea98b (held surface), 2bcdc763 (rigid turn). Each commit's
  witnesses shown red on its parent and green after (per-state files built
  from the tested final tree, which the last commit equals byte for byte);
  tests/agent on the final state: exit 0, no failures.
- step 3: oracle O1 pre-registered (above) and submitted as CUHK 2154086
  (slot a); read (above): P2 met, P1 met with a worded-wrong clause for the
  held point, reported.
- Post-repair census (same instrument, repaired tree): of 1,234 CUHK results,
  195 change basis only (search_converged -> program_check, word unchanged),
  2 go unmeasured -> stationary (q27 O1b g_sp0, g_sp180: Gaussian's check),
  2 unmeasured -> not stationary (q27 O1b g_sp90; one killed ORCA opt, by its
  last check), 6 unfinished searches read "ended before its program judged",
  and Q30's methanol held point goes free-energy surface none -> held_surface.
  No PySCF word changes. No archived delivery stood on a changed word.
- r10-integration has not moved since the base (df78d69d): merge is a no-op.
- Gates on 9c6d053a (code equal to 2bcdc763), pristine git-archive export:
  full suite 23 failed, 4851 passed, 25 skipped, 3 xfailed; the 23 are the
  round baseline's FAILED lines exactly, none under tests/agent (tests/agent
  green within it). ruff, black --check, isort --check clean on the five
  touched Python files; rsl.py check 0 failures (the kernel budget prompt is
  not this episode's). Fixtures added (3), none deleted.

## Left (found, not repaired)

- Gaussian modred holds that drift: Q30's ethane held dihedral ended 0.34 deg
  (5 deg point) and 0.06 deg (55 deg) from its value; the reader refuses a
  hold beyond 0.01 deg (result_readers.py `_gaussian_held_coordinates`), so
  those points fall to the unheld branch and its Cartesian residual.
- The characterisation receipt records `stationarity: unmeasured` for a
  structure its program's own check judged (execution.py, body built from the
  host's gradient only); recording the reading there re-digests new receipts:
  the master's call.
- ORCA frequency-only results stay unmeasured (ORCA prints no check there,
  and its .engrad pairs the previous cycle's gradient).
- `reaction_coordinate_mode` in an approved DAG: in the R10 streams searched
  (q21, q24, q27, q30 goals) the field appears only with value 0; no session
  was seen needing it. Left as the Q27 frontier left it.
- The run sensor's anomaly (tool_runtime.py `_gradient_anomaly`) still names
  geomeTRIC's criterion for an xTB Hessian (an observation, not a verdict),
  and HESS_STATIONARITY_GRADIENT_EH_PER_BOHR is still defined twice.

## Status: ended -- milestone A claimed (the host's stationarity word and
its held-coordinate projection agree with each program's own criterion and
with the rotor treatment; validated by census, witnesses, oracle O1 and the
profile rotor against the scan's)
