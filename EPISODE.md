# R10 episode Q18 -- an open-shell singlet the model can ask for without knowing any program

Base: `0ac28beccad766aa743945c4a693de7a5c0e4cec` (verified with `git rev-parse HEAD`
as the first action of the episode, 2026-09-24).

## The question as currently understood

Can the Agent ask for an open-shell (broken-symmetry) singlet as a typed
electronic-state request that the hub translates into each program's own
mechanism (ORCA, Gaussian, PySCF), states in the review, and refuses where no
native equivalent exists? Does the host then record which reference actually
ran and whether spin symmetry actually broke (<S**2>, the program's stability
answer), so the Agent can tell a real diradical from a collapsed closed shell?

## Falsifiers of the premise (armed before any census or run)

- F1 (census): if the archived goals contain no open-shell-singlet /
  broken-symmetry request other than R10 Q15's g1, repair that route and end.
- F2 (portability): if a typed request cannot mean one thing across programs,
  say exactly what is portable and what is not.
- F3 (the brief's prior about Gaussian): if a restricted `b3lyp ... guess=mix`
  route converges an unrestricted broken-symmetry solution, the prior
  "probably inert" is false.

## Census (2026-09-24, provider-free, model-authored text and tool arguments only)

Scope: public transcripts under /project/xlzhang/jiseung (r8, r9, r10/q1..q17
without q3 and q6/goals, the top-level R8-era campaign directories; 102 goal
workspaces) and the ax41 mirror (~/developer/chemsmart-hetzner-mirror, 712
workspace entries). Boundary incident: the first cluster sweep over `r10/`
also downloaded 9 files under r10/m and r10/m1 (the master's sealed
directories); none produced a census hit and none was opened; they were
deleted locally and on the cluster when the master's boundary arrived, and
the census was re-run without them (102 workspaces, same 17 with hits).

F1 is FALSIFIED as stated -- Q15 g1 is not the only case:
- Q15 g1 (Bergman, p-benzyne): FlipSpin 1,6 written three native ways in ORCA
  (`joboption`, `input_string`, `additional_route_parameters`; ORCA's input
  check aborted each), then Gaussian `additional_route_parameters: guess=mix`
  on restricted routes. The Gaussian nodes were never launched: the launch
  gate refused them on the ORCA input-check abort recorded for the same node
  id in planning (a stale, cross-program check; see defects found and left).
  So F3 cannot be read from Q15's records; O0 answers it.
- R8-era twisted ethylene (pyscf-agent-knowledge-20260919 g2-ethylene): the
  session wrote "Broken-symmetry UKS single point at 90 deg ... not selectable
  through the job-level state" and delivered the restricted 97.3 kcal/mol
  barrier against the experimental ~65.
- ax41 NOVEL-3 ino2-dinickel-exchange (2026-09-05/06): `reference: uhf` +
  `additional_route_parameters: FlipSpin 1,2` passed validation and preview
  and died at ORCA's input parse; the session then substituted the M=3 UKS
  determinant for the Ms=0 broken-symmetry state. Its own spin populations
  show a local spin change (Ni1 0.04, Ni2 1.68; <S**2> 2.79) rather than
  antiparallel sites, and the J it delivered (|J| 1040-1690 cm-1, against a
  susceptibility bracket of <= ~4 cm-1) rests on that substitution.
- R10 Q17 hc1 dA-o2gap (S1, U1, P1): sessions named a broken-symmetry UKS
  singlet as the correct description of O2 a1Delta_g and had no route to it
  (zero-engine tasks, so a limitation, not a loss).
- R10 q1 gdev1, q13 o2r and dans, q16 l1-o2r: sessions searched the capability
  surface for "unrestricted broken symmetry initial guess" project settings
  and found none (the tasks did not require one).
- Considered and rejected on scientific grounds (not a capability gap):
  R8-era ozone (BS-UMP2 would change the requested level), R9 g2-stability.

## Design under test (to be revised by O0)

One typed stage field, `broken_symmetry: true`, with one meaning in every
program: an unrestricted determinant at Ms = 0 (bound multiplicity 1) started
from a guess whose alpha HOMO and LUMO are mixed 50:50, so the SCF can reach a
spin-polarised (broken-symmetry) solution where one lies below the
spin-symmetric one. Each writer translates it into its own program's
mechanism and says so; the readers state the reference that ran; the host
states, from <S**2> as the program printed it, whether spin symmetry broke.

## Oracle O0 (native mechanisms, no ChemSmart) -- pre-registered expectations

Geometries (fixed, Angstrom): H2 at 0.74 and 2.00; ethylene planar and 90 deg
twisted (C=C 1.339, C-H 1.086, HCC 121.5); p-benzyne as a regular hexagon
(C-C 1.395, C-H 1.085, H removed on C1 and C4). HF (not p-benzyne) and B3LYP in
its Gaussian (VWN3) form (Gaussian B3LYP, ORCA B3LYP/G, PySCF b3lypg),
def2-SVP spherical, tight SCF, no RI, fine grids. Variants: restricted;
restricted + guess=mix (Gaussian); unrestricted without a symmetry-breaking
guess; unrestricted with each program's mixing guess (Gaussian guess=mix, ORCA
GuessMix 45, PySCF alpha HOMO/LUMO 45 deg rotation, and PySCF's own default
init_guess_breaksym=1); stability following (Gaussian stable=opt from R and
from U, ORCA STABPerform, PySCF R -> U external then internal); ORCA
BrokenSym 1,1 from the triplet; the triplets.

- E1 (F3): Gaussian restricted + guess=mix prints `E(RB3LYP)`/`E(RHF)` and an
  energy equal to the plain restricted run within 1e-6 Eh on every system.
- E2: unrestricted with a spin-symmetric guess collapses (<S**2> < 1e-3, E
  equal to the restricted energy within 1e-6 Eh) in all three programs on all
  five systems.
- E3: with a mixing guess, H2 at 2.00, twisted ethylene and p-benzyne break
  (<S**2> > 0.1, E below the restricted energy by more than 1 kcal/mol; more
  than 10 kcal/mol for twisted ethylene); H2 at 0.74 and planar ethylene
  collapse (<S**2> < 1e-3, E equal to restricted within 1e-6 Eh).
- E4: where all three programs break, E agrees within 1e-5 Eh (HF) and 2e-4 Eh
  (B3LYP), <S**2> within 0.01. A larger difference is a different solution
  (F2: the particular solution is not portable), reported as such.
- E5: PySCF's default breaksym and the explicit HOMO/LUMO mix reach the same
  energy within 1e-6 Eh.
- E6: ORCA BrokenSym 1,1 and GuessMix reach the same energy within 1e-5 Eh.

## O0 read (CUHK 2153330, complete)

- E1 FALSIFIED as written (and the brief's "inert" prior narrowed):
  restricted + guess=mix stays restricted everywhere (labels RHF/RB3LYP, no
  U solution) and equals the plain restricted energy on H2 (both), planar
  ethylene and p-benzyne (9e-9 Eh), but NOT at the 90-degree twist: there
  Gaussian's plain R lands on a higher restricted solution (HF -77.770459)
  or fails to converge (B3LYP, l502), and R + guess=mix breaks spatial
  symmetry to the lower restricted solution ORCA's plain RHF/RKS finds
  (-77.801915 / -78.374467). Not inert; still never unrestricted.
- E2 held except Gaussian's twisted-ethylene convergence failures (U
  B3LYP, l502).
- E3 held for H2 at 2.00 and p-benzyne in Gaussian and ORCA; H2 at 0.74
  and planar B3LYP ethylene collapse. Planar HF ethylene breaks weakly in
  both programs (<S**2> 0.0335, -0.021 kcal/mol): UHF's known pi
  instability, a measurement the host must report and not a collapse.
- E4 held where one solution is reached: H2 2.00 B3LYP 4e-9 Eh, HF 1e-10,
  p-benzyne 1.1e-7 Eh (<S**2> 0.9703 both). At the 90-degree twist
  Gaussian's U + guess=mix reaches a DIFFERENT solution (B3LYP -78.379601,
  26 kcal/mol above ORCA's -78.421139 and above its own triplet; HF 58
  kcal/mol above): the particular solution is not portable (F2), and
  <S**2> (1.001) alone does not reveal it.
- E6 held: ORCA BrokenSym 1,1 = GuessMix = STABPerform to 1e-10 Eh.
- E5 FALSIFIED, and the PySCF translation changed by it (O0 complete):
  PySCF's default init_guess_breaksym=1 leaves H2 at 2.00 (HF and B3LYP) and
  p-benzyne on the restricted solution; the explicit alpha HOMO/LUMO
  45-degree mix of PySCF's own guess orbitals breaks H2 (to 1.2e-8 Eh of
  Gaussian) and the twist, but COLLAPSES on p-benzyne (<S**2> 1.6e-10): which
  orbitals are "HOMO" and "LUMO" of a guess is a program fact. Following the
  restricted solution's own RHF/RKS -> UHF/UKS instability (PySCF's stability
  analysis, then internal instabilities until stable) reached the solution
  Gaussian and ORCA reach on every system: H2 2.00 -1.01848665 Eh, twist90
  -78.42113868, p-benzyne -230.70472508 (1.0e-6 Eh of ORCA, <S**2> 0.97027),
  and leaves a stable restricted solution restricted.

## O0b read (CUHK 2153375)

- H1 half-held: `nosymm` repairs Gaussian's HF mix at the 90-degree twist
  (-77.9014399735 = ORCA) but not B3LYP (-78.3796007 again): the exactly
  degenerate guess orbitals, not Gaussian's symmetry, are the cause.
- H2 held: at 85 degrees the three programs reach one solution (B3LYP
  -78.42233080/-78.42233085/-78.42233086, HF to 4e-9 Eh; <S**2> 0.978).
- H3 held: Gaussian `guess=mix stable=opt` reaches ORCA's solution at 90
  degrees (B3LYP 6.5e-8 Eh). H4 held.
- Consequence for the translation: ORCA GuessMix alone reached the lowest
  solution everywhere; Gaussian guess=mix everywhere but an exactly
  degenerate geometry; PySCF only by stability following. Each program is
  translated by the mechanism measured to work there, the review says which,
  and the result says whether it broke.

## Oracle O0b (pre-registered before submission)

Gaussian with `nosymm`, with `guess=mix stable=opt`, and an 85-degree twist
(degeneracy lifted) in all three programs.
- H1: at 90 deg, Gaussian `U guess=mix nosymm` reaches ORCA's broken-symmetry
  energy (-78.421139 B3LYP, -77.901440 HF) within 1e-6 Eh; if not, the
  degeneracy and not Gaussian's symmetry is the cause.
- H2: at 85 deg, Gaussian `U guess=mix` (symmetry on), ORCA GuessMix and the
  PySCF mix reach one solution within 2e-4 Eh (B3LYP) / 1e-5 Eh (HF).
- H3: `guess=mix stable=opt` reaches ORCA's solution at 90 deg.
- H4: `nosymm` leaves H2 2.00 and p-benzyne unchanged within 1e-7 Eh.

## Oracle O1 -- the typed request through the live CLI (pre-registered)

`chemsmart run` on the packed commits c54dd56e..404adffb (code tree digest
recorded by the job), project YAML with `broken_symmetry: true`, B3LYP (the
Gaussian VWN3 form in every program) / def2-SVP, the O0 geometries; ORCA with
NoRI, TightSCF, DefGrid3; PySCF defgrid3 and scf_tol 1e-10; 24 commands.
- T1 (translation = native mechanism): each hub broken-symmetry single point
  equals the same program's O0 native energy -- Gaussian U + guess=mix within
  1e-6 Eh (H2 2.00 -1.01848664, p-benzyne -230.70472415), ORCA GuessMix within
  1e-6 Eh (-1.01848664, -230.70472404), PySCF's followed instability within
  2e-5 Eh (grid (99,590) against O0's level 5: -1.01848665, -230.70472508);
  H2 0.74 and planar ethylene at the program's restricted energy within 1e-6.
- T2 (the host says so): every broken-symmetry result's level carries
  reference uks and broken_symmetry true; the spin-symmetry record reads
  broken for H2 2.00 and p-benzyne (<S**2> 0.705 and 0.970, +-0.01) and
  unbroken for H2 0.74 and planar ethylene (<S**2> < 0.01) in all three
  programs; the plain singlets read rks and the triplets uks, no word.
- T3 (cross-program): p-benzyne broken-symmetry and triplet energies agree
  within 2e-4 Eh across the three programs.
- T4 (the request survives an optimisation): each program's
  broken-symmetry p-benzyne opt ends with <S**2> > 0.1 below its own sp
  energy, and the three reached C1...C4 distances agree within 0.02 A.
- T5: PySCF's scf stage records its restricted solution externally unstable
  for H2 2.00 and p-benzyne and stable for H2 0.74 and planar ethylene.
A failed T1 is a translation defect; a failed T3 or T4 with T1 held is a
program fact (the particular solution is not portable), reported as such.

## O1 read (CUHK 2153479, complete; code 5da66f9c, 24 of 24 commands exit 0)

Read through the host's own readers (result_readers.reader_for), not by eye.
- T1 held: Gaussian and ORCA hub single points equal their O0 native
  energies to the printed digit (H2 2.00, p-benzyne, H2 0.74, planar
  ethylene); PySCF within 2.4e-7 Eh (p-benzyne), 4e-11 (H2).
- T2 held: every broken-symmetry result reads reference uks and
  broken_symmetry true; the word is broken for H2 2.00 (<S**2> 0.7053 in
  all three) and p-benzyne (0.9703), unbroken for H2 0.74 and planar
  ethylene (<S**2> 0); the plain singlet reads rks and the triplets uks,
  with no word.
- T3 held: p-benzyne broken-symmetry energies span 8.0e-7 Eh across the
  three programs, the triplets 9.1e-7 Eh.
- T4 held: each program's broken-symmetry opt ends broken (<S**2> 0.957),
  5.51e-3 Eh below its own sp, the three optimised energies within 5.5e-7
  Eh, C1...C4 2.6816 / 2.6819 / 2.6818 A.
- T5 held: PySCF's restricted start is externally unstable for H2 2.00
  (-0.097 Eh) and p-benzyne (-0.101) and stable for H2 0.74 (+0.318) and
  planar ethylene (+0.098).
- At the fixed hexagon (Gaussian numbers): E(T) - E(BS) 2.56 kcal/mol;
  Yamaguchi-projected 4.95; ratio 1.94 -- inside the G1 ratio band.

## Live goals -- pre-registered before submission

Model under study: deepseek-v4-flash-0731 via alibaba-token-plan (the only
provider credential); approvals delegated (claude-researcher-q18-owner-
delegated), never a human decision. Code: the packed commit named in each
job's output.

G1 -- p-benzyne singlet-triplet splitting (goals/g1/TASK.md, sha256
b3c411a8e3a8c26b...; start: a regular hexagon, not a stationary point; all
four programs; 16 cores, 48 GB, node 2 h, episode 5 h, 16 engine calls).
The task asks for the adiabatic splitting without and with spin projection
and never names broken symmetry, a program keyword or a mechanism.
Reference: triplet 3.8 +- 0.5 kcal/mol above the singlet (Wenthold, Squires,
Lineberger, JACS 1998, 120, 5279, as quoted by the NIST WebBook, read in
this session). Bands (dE_ST = E(T) - E(S), kcal/mol, any hybrid-DFT
broken-symmetry route):
- unprojected [0.5, 6.0]; projected [1.5, 10.0]; projected/unprojected in
  [1.6, 2.5]; <S**2> of the singlet in [0.6, 1.05], of the triplet in
  [2.00, 2.10].
Capability outcomes (from host records, not the report):
- M1: the singlet is requested with `broken_symmetry: true` and no native
  broken-symmetry word (FlipSpin, BrokenSym, guess=mix) is written;
- M2: the compile reply / review of that node carries the translation;
- M3: the singlet result's level says reference uks and broken_symmetry
  true, and the host's spin-symmetry record says broken, <S**2> in band;
- M4: the delivered numbers stand on extraction receipts of those results;
- M5: the goal settles achieved or achieved_with_observations.
Outcome words: success = M1-M5 and both numbers in band; a restricted
singlet (no request) is a behavioural finding about the model, read against
whether the affordance was visible in its transcript; a request the host
reads as unbroken on p-benzyne contradicts O0/O1 and is a defect.

G2 -- the R8-era twisted-ethylene task, byte-identical (sha256 954087be...,
the archived pyscf-agent-knowledge-20260919 g2-ethylene TASK and start;
PySCF and xTB; the archived envelope: 8 cores, 32 GB, node 3000 s, episode
5400 s, reserve 600 s, 6 engine calls). The archived run (CUHK 2140019)
delivered the rigid restricted barrier, 97.3 kcal/mol, having written that a
broken-symmetry singlet was "not selectable". This is an observation on a
different tree, not a controlled A/B.
- Bands: a barrier resting on a broken-symmetry singlet at 90 degrees in
  [55, 76] kcal/mol (rigid or relaxed, B3LYP-class); a restricted one in
  [88, 106]. The twisted singlet's host record: uks, broken, <S**2> in
  [0.95, 1.05], PySCF's restricted start externally unstable.
- Capability outcomes M1-M5 as for G1, PySCF.

## G1 read (CUHK 2153510, complete: achieved_with_observations, 2 cycles, 0 revisions, 4 engine calls)

Read from host records (ledger, run events, the frozen review, the four
ORCA outputs through result_readers), not from the report.
- The first plan asked for the singlet by type. The model's first search
  was in ORCA's words ("... ORCA project YAML section FlipSpin"), and
  about_cross_program_work, which carries the rule sentence naming FlipSpin
  as not the model's to write (1c10090a), ranked first. Four ORCA opt+freq
  nodes, B3LYP-D3BJ and wB97X-D4 / def2-TZVP: BS singlets with
  `broken_symmetry: true` (plus `reference: uhf`), triplets at
  multiplicity 3; no FlipSpin, BrokenSym, GuessMix or guess=mix in any
  project YAML, and no input_string or route words (M1). The frozen review
  carries the ORCA translation sentence on both singlet nodes (M2); ORCA's
  input check passed all four.
- Host records (M3): BS singlets uks, broken_symmetry true, word broken,
  <S**2> 0.9403 (B3LYP) and 0.9879 (wB97X-D4); triplets uks, 2.0067 and
  2.0065. No imaginary mode on any of the four (the session's own
  validation, lowest 380-415 cm-1).
- Delivered (M4: claims <- expressions <- extraction receipts of the four
  outputs, matched by file digest): unprojected dE_ST 2.56 (B3LYP) / 1.88
  (wB97X-D4), mean 2.22 +- 0.5 kcal/mol; Yamaguchi-projected with the
  measured <S**2> 4.82 / 3.71, mean 4.26 +- 0.8; ratio 1.92; ZPE raises
  each by 0.2-0.3. The session named the projected gap as the one to
  compare with the photoelectron measurement (the detachment reaches the
  spin-pure singlet; the BS energy is triplet-contaminated) and stated the
  functional spread, def2-TZVP basis error and the projection model as its
  uncertainties. Settled achieved_with_observations (M5); the two host
  observations are s2_deviation_ge_0.2 on the BS singlets, which is what a
  broken-symmetry singlet is.
- Bands: all held -- unprojected in [0.5, 6.0], projected in [1.5, 10.0],
  ratio in [1.6, 2.5], singlet <S**2> in [0.6, 1.05], triplet in
  [2.00, 2.10]. Against the measurement (3.8 +- 0.5), the projected mean
  4.26 +- 0.8 overlaps; B3LYP alone is 1.0 above it.
- Outcome word (pre-registered): success, on the first plan.
- Found and left: the session's recorded assumption merged two different
  symmetries -- the identity binding's spatial observation (D2h start;
  `break_symmetry` perturbs a geometry by seed) was cited as the reason the
  spin "broken-symmetry seed" (GuessMix from `broken_symmetry: true`) is
  needed. The plan was right; the stated reason was not. Two host words
  one letter apart name unrelated operations.

## G2 read (CUHK 2153511, complete: achieved_with_observations, 2 cycles, 4 engine calls)

Read from host records (ledger, run events, the frozen review, results
through result_readers), not from the report.
- Cycle 1 (the model's first plan): RKS B3LYP/6-31G* planar and rigid
  90-degree single points with `scf_stability: true`, no broken-symmetry
  request, barrier 99.97 kcal/mol -- in the restricted band [88, 106]. The
  affordance was visible: inspect_program listed `broken_symmetry` among
  PySCF's project-owned parameters in this session. The model's declared
  expectation (55-75, "RKS DFT (e.g. B3LYP) gives rigid-twist values in the
  low-to-mid sixties") was chemically wrong about RKS; the host displayed
  the disagreement and settled nothing on it.
- The host raised scf.reference_unstable on the twisted RKS result
  (RHF/RKS -> UHF/UKS and real -> complex unstable) and the wake carried it.
  The model's visible text: the 90-degree geometry is "a diradicaloid
  singlet; a closed-shell RKS description is not its DFT ground state", and
  the repair is `broken_symmetry: true` ("PySCF's own RKS->UKS instability
  route into the broken-symmetry singlet") at both geometries, one level.
  It had searched "PySCF project parameter broken_symmetry ..." and loaded
  about_cross_program_work, which carries the rule sentence.
- Cycle 2, revision admitted by the host: both single points with
  `broken_symmetry: true`, `scf_stability: true`, no native word anywhere
  (M1). Both compile replies and the frozen cycle-2 review carry the PySCF
  translation sentence (M2). Twisted: uks, broken_symmetry true, <S**2>
  1.0111, word broken, restricted start externally unstable (-0.0955 Eh),
  E -78.4743274138 (M3; <S**2> in [0.95, 1.05]). Planar: uks,
  broken_symmetry true, <S**2> 0, word unbroken, restricted start stable
  (+0.0992 Eh), E equal to the RKS energy to 2e-13 Eh; the host minted
  spin.broken_symmetry_request_unbroken with those numbers -- the honest
  answer for planar ethylene.
- Delivered: 69.907 kcal/mol (claim 227a801b <- expression a3fd0768 <-
  extractions 4dfa0c42 and e7dc4f67 of the two cycle-2 results, matched by
  file digest) (M4), inside the broken-symmetry band [55, 76]; settled
  achieved_with_observations (M5). The archived R8 run on the same TASK
  delivered the restricted 97.3 having written broken symmetry "not
  selectable" (a different tree; not a controlled comparison).
- Other observations the host recorded, all correct: s2_deviation_ge_0.2 on
  the twisted singlet (<S**2> 1.01 against 0), and scf.reference_unstable on
  the twisted UKS itself (UHF/UKS -> GHF/GKS): the model's own
  `scf_stability` asked about the final reference, a different question
  from the followed restricted instability, and both records say which.
- Outcome word (pre-registered): success -- M1-M5 held and the barrier is
  in band. The capability was reached by self-correction from a host
  observation, not on the first plan.

## Jobs issued

- O0: CUHK Slurm 2153330 (r10-q18-a), 4 cores, native inputs, 16 min, prereg
  digest 835945193c43.
- O0b: CUHK Slurm 2153375 (r10-q18-b), 4 cores, native inputs, 3 min, prereg
  digest 6ca6f084cb46.
- O1: CUHK Slurm 2153479, 8 cores, the ordinary CLI on code 5da66f9c (tree
  digest 33bf5023dd70...), prereg digest a27e0cacb045, ~16 min.
- G1: CUHK Slurm 2153505 (r10-q18-a), goal g1, code 33906d52 (tree digest
  535fbe0e00a4...), prereg digest b91d7adc57e9.
- G2: CUHK Slurm 2153506 (r10-q18-b), goal g2, same code and digest.
- Both CANCELLED by me 52 s after start, before any engine call (bootstrap
  and task files only; moved aside as goals/g1-cancelled-2153505 and
  goals/g2-cancelled-2153506): r10-integration had gained Q16's goal-loss
  repairs -- 12b2bbbe, "a quantity a delivered claim carries as its
  uncertainty ... holds no goal open", and G1 asks for an uncertainty on
  every number -- and Q15's stale input-check repair. A goal lost to a
  repaired host defect would say nothing about this capability. Rerun on the
  merged tree, same TASK, start, envelope and bands.
- G1: CUHK Slurm 2153510 (r10-q18-a), goal g1, code 95c85ed0 (the merge;
  tree digest 2d27f643b7db...), prereg digest 3e98e0450372.
- G2: CUHK Slurm 2153511 (r10-q18-b), goal g2, same code and digest.

## Status

- 2026-09-24: episode opened; gate open; census done (F1 falsified as stated).
- 2026-09-25: O0 and O0b read; implementing the typed request (Gaussian and
  ORCA writers and parse-back written; PySCF follows its instability).
- 2026-09-25: typed request, host reading and sensor committed (c54dd56e ..
  33906d52); O1 read, T1-T5 held; r10-integration merged (95c85ed0, no
  conflict); tests/agent 3125 passed on the merge; full suite from a
  pristine export of fdeadcaf: 23 failed, 4679 passed (the 23 are the
  environmental set: InChI/CDX/identifier, dispersion probe, CBS contract,
  PySCF four-stage YAML); live goals G1 and G2 running.
