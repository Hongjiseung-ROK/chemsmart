# R10 episode Q27 -- a free energy along a coordinate the scientist holds

- Base SHA: 9297d6baab07d3afe1f9f031e5c842a2a602d640 (verified with `git rev-parse HEAD` as the first action, 2026-09-25).
- Brief: scratchpad/q27/BRIEF.md, sha256 f1bc6c5d67c978498aed1d0fcf04e67fcfef7588a46ecf121b8c0b214608d5b2.
- Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

When a scientist asks for a free energy at a held coordinate (H-O-O-H held
at 90 deg, a point of a relaxed scan, a point of an IRC), can the Agent get
an honest one through the hub -- a typed request that each program answers
its own measured way -- instead of the refusal R10 Q21's gate
(`thermochemistry.free_energy_needs_a_stationary_point`) now gives? And does
the receipt say what the number is: which coordinate was projected, how many
modes were kept, which rotor treatment the kept modes had?

## Census (premise falsifier) -- narrowed to the H2O2 task

scratch q27/census/census.py over Q24's read-only fetch of the named CUHK
roots (r8, r9, r10 q1-q5, q7-q16, q18-q23, 2026-09-15..21 campaigns; the
fetch excludes r10/q6/goals, r10/q3 sealed/private/plans, r10/q17, r10/m*)
and every ax41 mirror cut: 388 unique task texts, 22 name a free energy and
a held/driven/path word; read one by one, only the H2O2 task (sha
622f1f43..., Q21 g1-hooh and g2-hooh, reused by Q24 g2r) asks for a free
energy at a held structure. ax41 h3 (1,2-dichloroethane) asks for ZPE at
stationary points only; ax41 cycle 042 for an electronic barrier from a
relaxed scan. Per the brief: narrowed to that task. The capability is
general; its validation is on H2O2.

## What the programs offer (read in session)

- Gaussian 16 (gaussian.com/freq): `Freq=Projected` -- "For a point on a
  mass-weighted reaction path (IRC), compute the projected frequencies for
  vibrations perpendicular to the path"; `TProjected` switches to it only
  when the RMS force >= 1e-3 Eh/Bohr; reference Baboul97. Baboul &
  Schlegel, J. Chem. Phys. 107, 9413 (1997), read in full: projected
  H = (I - n n^T) H (I - n n^T), n the mass-weighted tangent, taken from the
  gradient (Eq. 3) -- "if the gradient is small ... can lead to some
  uncertainty" -- or from the path displacement (Eq. 5).
  `Freq=HinderedRotor` (Ayala & Schlegel refs) exists; not used here.
- ORCA 6.1 manual (%freq keywords): no projection of a gradient or a
  coordinate; only ProjectTR.
- PySCF 2.13/2.14 `hessian.thermo.harmonic_analysis(mol, hess,
  exclude_trans, exclude_rot, imaginary_freq, mass)`: no projection beyond
  translations and rotations.

## Provider-free findings on archived output (before any cluster run)

- Every ORCA Freq run through chemsmart keeps `<stem>.hess`; its matrix
  reproduces the printed spectrum to 0.005 cm^-1. A Gaussian Freq archive
  entry carries the Hessian and the gradient (input orientation): 0.009
  cm^-1. PySCF results/hessian: 0.0000.
- ORCA's `.engrad` after `Opt Freq` pairs the final coordinates and energy
  with the previous cycle's gradient (1.6e-4 A away): no gradient at the
  Hessian's structure.
- At the 0/180-deg held points (the cis/trans saddles) the gradient nearly
  vanishes and is orthogonal to the torsion (cos 4e-5, |g| 3.6e-4 / 5.2e-5):
  the gradient-tangent projection keeps the imaginary torsion (-610.65 cm^-1
  at 0 deg) and removes a stretch/bend mixture. The held coordinate's own
  mass-weighted normal leaves exactly the saddle's five real modes.
- At 90 deg the curvature of the held surface (-lambda d2 phi, lambda
  -5.06e-3 Eh/rad) moves no kept mode by more than 2.1 cm^-1 (ZPE < 0.001
  kcal/mol): the rectilinear projection is adopted and stated.
- Defect found and repaired (9a531c44): a named reaction coordinate was
  replaced by the 100 cm^-1 cutoff (not removed) when the job label was not
  `ts`, while the receipt said "excluded"; explains Q24's unresolved dG(trans)
  -0.079 (g1-hooh opt180) vs 0.345 (g2r OptTS): replayed byte-for-byte.
- Host projection on the goals' ORCA outputs (b419dc77): G(held 0) -
  G(cis saddle, mode removed) = +0.0014; G(held 180) - G(trans saddle) =
  -0.0004 kcal/mol; G(held 90) - G(eq) = +0.346 (activation convention, eq
  keeps 6 modes) and +0.672 (profile convention, torsion removed at eq too).

## Design (committed)

- 9a531c44 thermochemistry: named reaction coordinate removed whatever the
  job label.
- b419dc77 analysis plane: `projected_coordinates` on the request (one-based
  atoms, as modred takes them); readers serve the Cartesian Hessian (ORCA
  .hess, Gaussian archive, PySCF results/hessian); the host checks the named
  set is what the result held, stationarity on that surface (residual
  gradient where recorded, else the constrained search's marker), the
  Hessian's reproduction of the printed spectrum and its structure, and no
  imaginary mode left; the receipt states coordinate, modes kept (5 of 6,
  3N-7), projection kind, Hessian source, surface stationarity, rotor
  treatment.
- (next, shared) agent reachability: derive_thermochemistry and the planned
  thermochemistry node carry `projected_coordinates`; normaliser, executor,
  review table, TUI, receipt matcher; one rule at tool:derive_thermochemistry.

## PRE-REGISTRATION -- oracle O1 (CLI, CUHK; written before submission)

Why: measure what Gaussian's own `freq=projected` does at held points, and
the identity and cross-program agreement of the host's projection.
Gaussian 16 C.02, `functional: b3lyp`, `basis: def2-svp`, `dispersion:
d3bj`, H2O2 from the task's h2o2.xyz with H-O-O-H set to 0/90/180 by
rotating H4 about O-O; 8 cores. Jobs: eq `opt` (+freq); held 0/90/180
`modred [[3,1,2,4]]` (+freq); the same three with route parameter
`freq=projected`; `ts` from held 0 and 180. Also PySCF `hess` (b3lyp/
def2-svp, no dispersion) at the Gaussian held-90 geometry of the archived
fixture (tests/data GaussianTests/constrained_dihedral, B3LYP/def2-SVP).

Predictions (bands fixed now):
- P1: every Gaussian freq archive reproduces its printed spectrum <= 0.5
  cm^-1 (expected <= 0.01).
- P2 (identity): host-projected G(held 0/180) - G(ts, mode 1 removed) within
  +-0.02 kcal/mol each.
- P3: native `freq=projected` at held 90 prints 5 modes equal within 0.1
  cm^-1 to the host's gradient-tangent projection of the same run's archive
  Hessian and gradient (Baboul Eq. 3-4), and within 5 cm^-1 of the host's
  held-coordinate projection.
- P4: native `freq=projected` at held 0 and 180 (gradient ~0 by symmetry)
  does not project the torsion: it keeps an imaginary mode below -200
  cm^-1 (0 deg) / -100 cm^-1 (180 deg), or refuses/warns. FALSIFIER: it
  prints the saddle's five real modes within 1 cm^-1 -> Gaussian's native
  option would be a valid translation for held coordinates.
- P5 (cross-program): Gaussian-host dG(90, activation convention) within
  +-0.10 kcal/mol of ORCA-host 0.346 (different numerics: ORCA RIJCOSX).
- P6 (PySCF, neutral): at a foreign held geometry the host measures the
  residual gradient orthogonal to the torsion; <= 4.5e-4 Eh/Bohr -> derived
  and dG vs Gaussian-host within 0.15; above -> refused naming it. Either
  is the measured way; reported as observed.

## PRE-REGISTRATION -- live goal g1 (written before submission)

Task, geometry and envelope byte-identical to R10 Q21's g1-hooh (TASK.md
sha256 622f1f43d9cc607c..., h2o2.xyz d59a387b922e2634...): ORCA cpu, 8
cores, 16 GB, node 1800 s, episode 7200 s, reserve 1800 s, 12 engine calls,
2 revisions, local dispatch; granted_by claude-researcher-q27-owner-delegated
(a delegated approval, never a human decision). One run, one observation
of deepseek-v4-flash-0731.

- S-host: (a) a free energy derived at a held result without the request
  is refused, and the refusal names `projected_coordinates`; (b) every
  projected receipt states the coordinate with its value, "5 of 6
  vibrational modes kept (3N-7)", the rotor treatment and the Hessian's
  reproduction; (c) where a held 0/180 result and a saddle search both
  exist, their G agree within 0.02 kcal/mol.
- S-agent: the delivered 90-deg free energy comes from a projected receipt
  and the delivery states the treatment or the convention.
- Physics bands (from the archived replay; fixed now, never tuned):
  dG(90) activation convention [0.20, 0.50] (replay 0.346) or profile
  convention [0.55, 0.80] (0.672); dG(0) [7.7, 8.2] (7.95); dG(180) [0.20,
  0.50] (0.347); dE(90) [0.1, 2.0] (0.760).
- F-host: a projected receipt missing any of those statements; a projection
  of a coordinate the result did not hold; the naive G derived at a held
  structure.
- F-agent: a 90-deg Gibbs value delivered that is not a projected receipt's
  (the cis barrier or dE under a G name without saying so).
- Neutral: the Agent never requests the projection (TS searches only,
  unreachable, or dE named as such): then check the affordance was visible
  (tool description, refusal text in its transcript) before attributing it.
- Not counted: zero provider turns or turn_deadline_exceeded
  (infrastructure). A weak run is reported, never re-rolled.

## Status

- step 0: brief read, base verified, governance and prior records (Q21
  cde8c408, Q24 51b65cfa) read; cluster gate open.
- step 1: census done (narrowed); literature read; provider-free replays.
- step 2: 9a531c44, b419dc77, 692b7596 (shared: reachability) committed;
  tests/agent 3213 passed, 20 skipped, 2 xfailed on the working tree.
- Defect found and left (outside radius): `reaction_coordinate_mode` does
  not travel an approved DAG -- absent from the planning node schema and
  the plan parser, and dropped by the toolchain normaliser
  (scientific_toolchain.py normalised AnalysisNodeIntentV1 rebuild); even
  forwarded, the runtime admits it only over a characterisation minted in
  the same session, which an executor walk never has.
- step 3: oracle O1 and live goal g1 pre-registered above; packing next.
