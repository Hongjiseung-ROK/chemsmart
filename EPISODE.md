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

## O1 -- READ (CUHK 2153713, COMPLETED 5 min 19 s, 10/10 exit 0, code 83b9bfbd)

Read through the host's own readers and derivation (scratch
q27/proto/analyse_o1.py on the fetched outputs), against P1-P6:
- P1 met: every Gaussian archive Hessian reproduces its printed spectrum to
  <= 0.0088 cm^-1.
- P2 met: G(held 0, projected) - G(ts0, mode 1 removed) = -0.0031; G(held
  180) - G(ts180) = +0.0063 kcal/mol (band +-0.02).
- P3 FALSIFIED as registered, for a reason the pre-registration did not
  foresee: `freq=projected` written into the modred route reaches only
  Gaussian's first job step (overlay 7/45=1); the frequency step Gaussian
  generates after an optimisation (`#N Geom=AllCheck ... Freq`) drops
  `Projected`, and g_p90 printed six ordinary modes (454.19 cm^-1
  torsion included), identical to g_m90's. The hub can write the token,
  and through an opt+freq job it silently does nothing.
- P4: its observable held (g_p0 keeps -612.87, g_p180 keeps -236.46
  cm^-1), but not by the predicted mechanism: no projection ran.
- P5 met: Gaussian-host dG(90, activation convention) +0.344 vs ORCA-host
  +0.346 kcal/mol (diff -0.002, band +-0.10); also dG(held 0) 7.959 vs
  7.954, dG(held 180) 0.340 vs 0.347.
- P6: PySCF `hess` at the Gaussian held-90 geometry measured |g| 6.06e-3
  and a residual of 1.2e-4 Eh/Bohr once the torsion is removed (dE/dphi
  -0.00505 Eh/rad, as ORCA -5.06e-3 and Gaussian -5.055e-3): derived. Same
  geometry, same functional form (b3lyp -> b3lypg, VWN3), no D3: PySCF vs
  Gaussian electronic energy +7.6e-7 Eh, projected thermal Gibbs
  correction -0.0002, projected G +0.0003 kcal/mol.
- Host held-coordinate projection vs gradient tangent on O1's own
  Hessians: at held 0 the tangent keeps -612.87 and removes the 3778
  stretch; at held 180 it keeps -236.46 and drops a stretch to 3549.86;
  at held 90 the two agree to 0.4 cm^-1.

## PRE-REGISTRATION -- oracle O1b (written after O1, before submission)

Why: P3 did not measure Gaussian's projection at all. O1b runs it as a
standalone job (`sp` with route parameter `freq=projected`, so the route
is `# b3lyp def2svp empiricaldispersion=gd3bj freq=projected`) at the
structures O1's modred runs reached (archive input orientation, scratch
q27/oracle-o1b/g_m{0,90,180}_reached.xyz).
- P3': held 90: Gaussian prints 5 modes equal within 0.5 cm^-1 to the
  host's gradient-tangent projection of g_m90's Hessian and gradient
  [956.89, 1376.46, 1396.89, 3724.35, 3727.85].
- P4': held 0 and 180: by symmetry the gradient (A1 in C2v, Ag in C2h)
  cannot contain the torsion (A2, Au), so a gradient-tangent projection
  keeps the imaginary torsion: Gaussian prints a mode within 5 cm^-1 of
  -612.9 (0 deg) / -236.5 (180 deg) and loses a real one (host tangent at
  180: [-236.46, 1241.61, 1519.77, 3549.86, 3798.39], within 5 cm^-1
  each) -- or refuses/warns. FALSIFIER: the saddles' five real modes
  within 1 cm^-1, which would make Gaussian's option a valid translation
  of a held coordinate at those points.
- Observed and reported, not banded: whether Gaussian's own thermochemistry
  section uses the projected modes.

## O1b -- READ (CUHK 2153717, COMPLETED 44 s, 3/3 exit 0; prereg 949e5cb087e4)

Route written by the hub: `# b3lyp def2svp empiricaldispersion=gd3bj
freq=projected` (single point). Gaussian's own projected analysis:
- P3' met: held 90 printed [956.87, 1376.28, 1396.71, 3724.21, 3727.69]
  against the host's gradient-tangent prediction [956.89, 1376.46,
  1396.89, 3724.35, 3727.85] (within 0.2 cm^-1); Gaussian's own G equals
  the host's held-coordinate projected G to 0.001 kcal/mol (dG(90) +0.344
  both).
- P4' met: held 0 printed [-612.87, 957.80, 1322.23, 1464.25, 3733.46]
  (host tangent to 0.04 cm^-1: the torsion kept, the 3778 stretch
  removed); held 180 printed [-236.46, 1241.61, 1519.76, 3549.91,
  3798.40] (to 0.05 cm^-1). The falsifier did not fire: Gaussian's option
  is not a translation of a held coordinate at those points.
- Observed: Gaussian's own "Sum of electronic and thermal Free Energies"
  counts the kept real modes: 5.381 kcal/mol below the host's projected G
  at held 0 (native dG(0) +2.578 vs +7.959) and 1.742 below at held 180
  (native dG(180) -1.402 vs +0.340).
- Consequence found and repaired (ab59c347): the host's ordinary
  derivation on the 90-deg log returned a 3N-7 free energy saying nothing;
  a spectrum short of its structure's modes now says what it lacks (also
  an archived frozen-atom Gaussian opt: 12 of 36 modes).

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

## g1 -- READ (CUHK 2153714, COMPLETED 31 min 46 s, code 83b9bfbd, prereg 1d235efdeb8b)

Read from host records (ledger, the two session streams, the cycle-1 run
stream, both public transcripts, the delivered completed-analysis report),
fetched read-only to scratch q27/g1. deepseek-v4-flash-0731; one run, one
observation of that model. 2 cycles, 1 revision (analysis-only), 5 engine
calls of 12. Settled `achieved`.
- Route (the Agent's): cycle 1 planned opt (eq), OptTS from 0 and 180
  deg, modred at 90 deg, a relaxed scan (auxiliary), and thermochemistry
  nodes with `projected_coordinates [[3,1,2,4]]` at 0, 90 and 180 deg and
  none at eq -- in its planning session, before any refusal. Its decision
  names the affordance ("RRHO Gibbs with projected coordinates at true
  saddles"). The approved review (reviews/cycle-1.json) carries the field
  on the three nodes. The scan failed_native (ORCA GSTEP constraint set-up,
  2 of 7 steps; as Q24's g2r); nothing depended on it.
- Cycle 1 run (provider-free executor): all four thermochemistry nodes
  executed; each projected receipt states "dihedral H3-O1-O2-H4 at
  0.00/-180.00/90.00 deg", "5 of 6 vibrational modes kept (3N-7)", the
  Hessian's sidecar and its reproduction (0.0041-0.0051 cm^-1), the
  surface stationarity and the rotor treatment.
- Cycle 2 (wake): tried `reaction_coordinate_mode` on the saddle stages;
  the plan schema refused it (the gap left, above); re-planned with the
  projection; analysis-only revision admitted; re-derived byte-identical G.
  Decision in its own words: "the torsional coordinate was projected out
  (3N-7 modes) at the two true saddles and at the modred point ... while
  the equilibrium kept all 3N-6 modes"; uncertainty: "Harmonic RRHO
  approximation applied to the low-lying torsion (323 cm-1 at
  equilibrium), which is anharmonic". Imprecision: it calls the 90-deg
  difference "a profile-point relative Gibbs"; by the mode counts it states
  it is the activation convention.
- Delivered (completed-analysis report, claims receipt d5975a18...):
  gibbs-rel-90-kcal 0.3459, gibbs-rel-0-kcal = barrier-cis 7.9532,
  gibbs-rel-180-kcal = barrier-trans 0.3454 kcal/mol; the report states
  for each projecting node that it "removes the held coordinate(s)
  [[3, 1, 2, 4]] ... 3N-6 less one mode per coordinate".
- Against the pre-registration: S-host (b) met; (a) and (c) not exercised
  (no naive request at a held result; no held 0/180 result) -- neutral.
  S-agent met. Bands: dG(90) 0.346 in [0.20, 0.50]; dG(0) 7.953 in [7.7,
  8.2]; dG(180) 0.345 in [0.20, 0.50]; dE(90) 0.760 in [0.1, 2.0]. F-host,
  F-agent not triggered as written.
- ERROR found beyond the pre-registration: the expression reading of the
  delivered dG(90) (cycle-1 run stream and cycle-2 session stream)
  annotated it `vibrational_energy_of_a_structure_not_stationary` --
  "describes no state" -- from the held structure's full-surface
  stationarity. Not in the public transcript, not in the report; a false
  host word in the record. Repaired 5411601f (the operand of a projected
  receipt carries no not-stationary sentence); witness red on ae3b0c09,
  green after. (5411601f's body names Q21's control test wrongly; it is
  test_a_zero_point_energy_rebuilt_by_hand_says_what_its_modes_are.)
- Probe (left for the owner): `refusal_read_against_results` over g1's own
  held-90 result still returns verified=True ("so it has no
  gibbs_free_energy whatever its output prints") -- a session that refused
  the 90-deg free energy would be signed unreachable_from_evidence over
  evidence the host now derives it from (scratch q27/proto/probe_refusal.py).

## Gates

- ae3b0c09, pristine export: full suite 23 failed, 4770 passed; the
  failing set equals the round baseline (q24 gate-full-failed.txt); none
  under tests/agent.

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
- step 3: oracle O1 and live goal g1 pre-registered above.
- step 4 (issued): code 83b9bfbd packed (426 files, tree digest
  2f50f12e77c52d0c..., 0 AppleDouble), unpacked at r10/q27/code.
  O1 = CUHK Slurm 2153713 (slot a, 10 CLI calculations, 8 cores / 24 GB);
  g1 = CUHK Slurm 2153714 (slot b, TASK.md 622f1f43..., h2o2.xyz
  d59a387b..., workspace holds h2o2.xyz only). Both submitted by
  slot_submit with pre-registration digest 1d235efdeb8b.
