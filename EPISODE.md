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

## Status

- step 0: brief read; base verified; AGENTS.md, CONDUCT.md, RSL README and the
  four lessons, charter validity-rules.md, merges e089d7ce (Q21), 818fe2b4
  (Q27), ef1eb516 (Q30) and Q30's EPISODE.md read; `structure_stationarity`,
  `free_energy_surface`, `_held_coordinate_projection`, `_internal_rotor_treatment`,
  the thermochemistry kernel's projection and the readers' gradient/Hessian
  functions read. Cluster gate open.
- step 1: census and projection census read (above). Premise narrowed? No:
  widened -- five classes, two of them the brief's.
