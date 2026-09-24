# R10 episode q15 -- one hard question carried across programs (milestone B)

Base SHA: 2c1050c74cc31c76d6f51970b9b03c4e37e7cf50 (verified with
`git rev-parse HEAD` as the first action, 2026-09-24).

## The question (as currently understood)

Through the merged hub, can the CHEMSMART Agent (deepseek-v4-flash-0731,
alibaba-token-plan) carry one hard, scientifically meaningful question from
a structure to an answer comparable with the literature, crossing programs
where the science justifies it, with every stage's evidence and lineage
(identity, electronic state, level of theory, geometry, producer evidence)
intact in host records? Where the route breaks, whose break is it: the
hub's (repair in radius), a program's, the model's, or the science's?

B is judged from host records (ledger, run streams, receipts, native
output), never from the Agent's prose. Several approvals/cycles are
admissible ("multi-DAG"); what B needs is one hard question, carried
across programs by the Agent's own route choice, with lineage traceable
through every handoff.

## The chemistry (chosen before any run)

The Bergman cyclization of (Z)-hex-3-ene-1,5-diyne (C6H4, 6 heavy atoms)
to 1,4-didehydrobenzene (p-benzyne), gas phase. Small, but its electronic
structure is genuinely hard, and it is famous for it:

- the product's singlet ground state is a diradical (65% biradical
  character by CCSD(T) natural orbitals, Kraka & Cremer 1994); restricted
  DFT becomes unstable toward UDFT near p-benzyne (Graefenstein, Hjerpe,
  Kraka, Cremer, JPCA 2000, 104, 1748 -- abstract-level fact from a search
  summary, not read in full); broken-symmetry UB3LYP singlets carry
  <S^2> 0.94-0.99 (Sherer et al. 2008, text read);
- the correlated method decides the sign: at 6-31G(d,p) the reaction
  energy is MP2 -12.3, CCSD +27.2, CCSD(T) +5.5 kcal/mol; the classical
  barrier MP2 23.3, CCSD 37.7, CCSD(T) 29.5 (Kraka & Cremer 1994, Table
  and text, read);
- the basis moves B3LYP's barrier by 3-5 kcal/mol (29.0-29.4 at double
  zeta, 32.3-34.2 at triple zeta, 470 K; Sherer et al. 2008 Table II,
  read from the page) and single-reference CCSD(T) moves the reaction
  enthalpy from 8.0 (6-31G(d,p), 298 K) to 13.76 kcal/mol (cc-pVTZ;
  Luxon, Orms, Kanters, Krylov, Parish, JPCA 2018, 122, 420, abstract
  read).

Why crossing programs is scientifically justified here (not staged): in
this hub, typed wavefunction-stability answers are served for PySCF (and
Gaussian's lowest eigenvalue), not for ORCA; ORCA serves the CCSD T1
diagnostic, PySCF does not; ORCA's DFT with RIJCOSX is the cheap geometry
and Hessian engine; canonical CCSD(T) runs in ORCA and PySCF, so an
implementation cross-check of a (T) correction worth ~20 kcal/mol on an
unstable reference is a real scientific check. A single-program route
(PySCF can do every stage) is legitimate and would not be B.

### Reference (what it measures, its uncertainty)

- Roth, Hopf, Horn, Chem. Ber. 1994, 127, 1765 (doi
  10.1002/cber.19941270929; English abstract read via Crossref): the
  energy profile of the Bergman rearrangement from the NO and O2
  dependence of the trapping rate of the diradical; dHf(p-benzyne) =
  138.0 +- 1.0 kcal/mol.
- Kraka & Cremer, JACS 1994, 116, 4929 (full text read), note added in
  proof quoting Roth et al.: reaction enthalpy 8.5 +- 1.0 kcal/mol,
  activation enthalpy 28.2 +- 0.5 kcal/mol.
- Sherer, Kirschner et al. 2008 (PMC2854586, Table I read from the raw
  page): "radical trap rates, MeOH, CHD", T = 470 K, dH++ 28.2 +- 0.5,
  dG++ 33.0 +- 0.8, dHr 8.5 +- 1.0 kcal/mol (ref 110 = Roth).
- What it measures: dH++ is an Eyring enthalpy from trapping kinetics at
  about 470 K (not 298 K; Kraka's CCSD(T) thermal terms move dH++ by -1.7
  kcal/mol between 0 and 298 K, so the temperature is not decoration);
  dHr is derived from dHf(p-benzyne) at 298 K. The phase of Roth's
  kinetics is as the sources state; a solvent effect on this non-polar
  cyclization is assumed below 0.5 kcal/mol.

## TASK (as posed to the Agent; programs named, stages and programs not dictated)

goals/g1/TASK.md, reproduced in the goal directory. It asks for the
activation enthalpy at 470 K and the reaction enthalpy at 298.15 K in the
gas phase, at a level the Agent can defend, with the connectivity of the
transition state shown, and what each number rests on. Starting
structure: the enediyne only (C2v, from a standard geometry, not
optimised by me at any level used by the Agent).

## Physics bands (never tuned after a result)

- B1 saddle: exactly one imaginary mode, |nu| in [250, 1000] cm-1; the
  forming C1...C6 distance in [1.85, 2.15] A (CCSD(T)/6-31G(d,p): 1.993).
- B2 connectivity: one side relaxes to the enediyne (C1...C6 in
  [3.9, 4.7] A; 4.412 at CCSD(T)), the other to p-benzyne (C1-C6 in
  [1.35, 1.46] A and C2...C5 in [2.60, 2.85] A; 1.382 and 2.725 at
  CCSD(T)); each relaxed end has no imaginary mode.
  CORRECTION (2026-09-24, written after O1's DFT results and before G1
  was submitted; the band above stays the pre-registered one): I misread
  Kraka & Cremer's figure. 1.382 A is the radical-carbon-C(H) distance;
  the newly formed C1-C6 bond in p-benzyne is a C(H)-C(H) bond, 1.426 A
  at CCSD(T)/6-31G(d,p). O1's closed-shell RB3LYP-D3BJ/def2-TZVP
  p-benzyne has C1-C6 1.477 A and C2...C5 2.702 A (the known RKS bond
  alternation, 1.338/1.477), so a restricted p-benzyne misses B2 as
  written while being unambiguously the bonded ring. G1 is reported
  against B2 as written AND against the reading "C1-C6 below 1.60 A with
  C2...C5 in [2.60, 2.85] A identifies the p-benzyne ring", both stated.
- B3 activation enthalpy at 470 K: PASS in [25.7, 31.2] kcal/mol
  (28.2 +- 0.5 experiment, +- 1.5 for a CCSD(T)/TZ-class level, +- 1
  for the thermal model); a DFT-only value in (31.2, 35] is "comparable,
  method-limited" and is recorded as such, not as agreement.
- B4 reaction enthalpy at 298 K: PASS in [4.5, 14.5] kcal/mol AND the
  delivered uncertainty or limitation names the diradical/reference
  problem of p-benzyne (stability, <S^2>, T1, or a stated multireference
  limit). A number in the band with no such statement is "in band,
  unqualified".
- B5 lineage: for every delivered number, host records name the geometry
  node, the level (functional literal as the program applied it, basis,
  RI/density fitting, dispersion, frozen core), the state (0, 1), and the
  producer of every handed-on structure and Hessian.

## Falsifiers of the premise ("the merged hub now carries such a route")

- Positive: the Agent completes the task across programs by its own route
  and every stage is traceable from host records (B1-B5 read by me).
- A break at a layer the round believed repaired (producer edge across
  programs, Hessian into IRC, basis or functional identity, typed
  stability/T1, host words) is the finding: repaired in radius with a
  witness red on the base, or reported with its evidence.
- A single-program route is the Agent's legitimate choice and is not B.
- A failure for the model's reasons (no saddle found, wrong state,
  invented numbers) or the science's (a quantity no level in the hub can
  reach, e.g. a broken-symmetry singlet) is reported as that, never
  re-rolled.

## Plan

1. Provider-free rehearsal of the expected route through the host (plan,
   producer edges across programs, compile/preview, handoff and command
   synthesis on archived real outputs), and a CLI heartbeat of every
   writer the route leans on. Repair hub breaks in radius, each with a
   witness red on the base.
2. One CLI oracle job (no Agent) at matched levels for my own reference
   numbers (pre-registered here before submission).
3. One live goal (g1). A second system only for a general claim.

## Oracle O1 -- PRE-REGISTRATION (written before submission)

A CLI reference job (no Agent, no provider) on the code of this commit
(chemsmart/ unchanged from the base). It is also the engine rehearsal of
the writers and readers the route leans on: ORCA opt/ts/irc with the
saddle's Hessian, PySCF stability at ORCA geometries (a cross-program
geometry through the CLI), canonical CCSD(T) in both programs.
Commands: `cli/o1/commands.txt` (14 `chemsmart run` lines, 32 cores,
100 GB). Guesses built by me with RDKit/MMFF and by linear
interpolation (enediyne -> a regular hexagon at 0.79, C1...C6 2.008 A);
the Agent never sees them. DFT: B3LYP-D3(BJ)/def2-TZVP (ORCA writes
B3LYP/G; whether ORCA applies RIJCOSX is read from its output).
CCSD(T)/cc-pVTZ, frozen core (ORCA default; PySCF `frozen_core: auto`).

Predictions (bands never tuned after a result):
- O-A saddle: converges from the guess; exactly one imaginary mode,
  |nu| in [250, 1000] cm-1; C1...C6 in [1.85, 2.15] A.
- O-B IRC: the two directions move C1...C6 oppositely: one end below
  1.7 A (toward p-benzyne), the other above 2.5 A (toward the
  enediyne); ORCA's default step limit may stop both short of a minimum.
- O-C stability (PySCF RKS, B3LYP-D3BJ/def2-TZVP): enediyne stable in
  every question asked; saddle stable (prediction, after Graefenstein et
  al.'s RDFT-stable TS); p-benzyne RKS -> UKS unstable (a negative
  lowest external eigenvalue).
- O-D B3LYP electronic barrier (ORCA) in [31, 38] kcal/mol (Sherer's
  B3LYP/triple-zeta dH++(470 K) 32.3-34.2, and dH++(470) is about
  dE++ - 1.6 from Kraka's ZPE and thermal terms).
- O-E closed-shell RB3LYP reaction energy in [5, 25] kcal/mol (weak; an
  upper bound to a broken-symmetry value).
- O-F CCSD(T)/cc-pVTZ // B3LYP: dE++ in [28, 34], dE_R in [6, 17]
  kcal/mol.
- O-G ORCA and PySCF CCSD(T) totals agree within 1e-5 Eh on each
  geometry when neither applied RI to the reference; a larger gap on
  p-benzyne alone would say the two programs converged different RHF
  solutions (a program fact, not a hub one).
- O-H ORCA's T1 for p-benzyne exceeds the enediyne's and the saddle's;
  prediction T1(p-benzyne) > 0.015.

## Live goal G1 -- PRE-REGISTRATION (written before submission)

- Task: goals/g1/TASK.md, sha256 5d430a8837725b06cdf78290a0ba920755ff4009474855b398fb33220045cf2f;
  workspace enediyne.xyz sha256 e18b5b9fe987f0650ff9fe993a6429b073e0ffc938b9e1ff63b57ea57e34633e
  (the RDKit/MMFF structure; the only workspace file).
- Agent: deepseek-v4-flash-0731 via alibaba-token-plan; knowledge documents
  off (Q3's default); approval `claude-researcher-q15-owner-delegated` (a
  delegated approval, never a human decision).
- Envelope (make_goal.py): orca, pyscf, gaussian, xtb on cpu; 32 cores,
  100 GB, node 3 h, episode 11 h, reserve 30 min, 30 engine calls, 0
  excursion calls, 3 revisions. Local dispatch (one node at a time).
- Code: the tree of this commit (chemsmart/ unchanged from the base unless
  a repair lands before submission; the job prints the digest it verified).

What is read, from host records only (ledger, run streams, receipts, native
output), against the bands B1-B5 above:
- R1 route: which programs the Agent used for which stage and why (its
  recorded decisions); whether it crossed programs; whether each crossing
  had a scientific reason on the record. A single-program route is
  recorded as its choice, and B is then not claimed.
- R2 lineage per handoff: producer node, handoff receipt, atom order,
  state (0, 1), and the level each program applied (functional literal,
  RI/density fitting, dispersion, basis, frozen core). An ORCA saddle
  handed to a PySCF stage is a surface change (RIJCOSX in ORCA, exact
  exchange in PySCF; O1's ORCA output shows RIJCOSX with def2/J applied
  by default) and is read as such.
- R3 the numbers: dH++(470 K) against B3, dH_R(298 K) against B4, the
  saddle against B1, connectivity against B2; each against O1 at matched
  level where one exists.
- R4 the host's words: settlement, anomalies raised (e.g.
  scf.reference_unstable on p-benzyne if stability is asked), and
  whether each word is true of what it read.
Milestone B is claimed only if R1 shows an Agent-chosen cross-program
route with a scientific reason, R2 holds on every handoff, and B1-B3 pass
(B4 read as stated).

## Jobs issued

- 2026-09-24: O1, CUHK Slurm 2152790 (r10-q15-a), CLI oracle, 32 cores,
  code 943882de (tree digest 85752dd3), pre-registration digest
  47fcb74af3be.
- 2026-09-24: G1, CUHK Slurm 2152875 (r10-q15-b), live goal, 32 cores,
  code tree digest 85752dd3 (chemsmart/ identical to 943882de; HEAD
  5343f551), pre-registration digest 5acc431bcad8. Submitted after O1's
  commands 1-3 (ORCA opt, saddle, p-benzyne) and while its IRC ran
  ("Initial displacement Hessian type .... Read").
- 2026-09-25: G2, CUHK Slurm 2153334 (r10-q15-a), live goal, g1's task
  byte-identical, 32 cores; code 8869a23e (tree digest b572f5bd, verified
  on chpc-cn073), pre-registration digest 185315206e8a.
- Census (read-only grep of every run stream under r10/q1..q17): the
  executor's input-check launch refusal fired twice in R10, both in g1 and
  both on a Gaussian node quoting ORCA's lines -- 2 of 2 false.

## O1 -- partial READ (commands 1-3; ORCA 6.1.1 output read by me)

- ORCA wrote `B3LYP/G` (LDAOpt VWN-3) and applied RIJCOSX with def2/J by
  default ("RI is on but no J-basis has been assigned").
- Enediyne: E -230.990780691 Eh, lowest mode 105.5 cm-1, C1...C6 4.390 A.
- Saddle (from the 0.79 interpolation, 7 cycles): E -230.939192699 Eh,
  one imaginary mode 529.9i cm-1, C1...C6 1.928 A, C2...C5 2.713 A:
  O-A PASS. dE++ 32.37 kcal/mol: O-D PASS.
- Restricted p-benzyne: E -230.953235105 Eh, no imaginary mode, C1-C6
  1.477 A, C2...C5 2.702 A; dE_R 23.56 kcal/mol: O-E PASS (upper end).
- My own harmonic terms (rrho.py, unscaled): dH++(470 K) 30.48 and
  dH++(298 K) 30.99 kcal/mol; dH_R(298 K, restricted) 23.08 kcal/mol.
  B3LYP-D3(BJ)/def2-TZVP alone therefore lands inside B3's band; B3
  does not by itself distinguish a DFT route from a correlated one.
- IRC (commands 4-5), both reading the saddle's Hessian ("Initial
  displacement Hessian type .... Read"): forward converged (HURRAY) into
  p-benzyne, C1-C6 1.481 A, E -230.953195 Eh (0.03 kcal/mol from the
  restricted minimum); backward stopped at ORCA's 21-step default, 18.3
  kcal/mol below the saddle at C1...C6 2.88 A, far from the enediyne
  minimum (4.39 A). O-B PASS; the reactant side needs a relaxation of the
  endpoint to show connectivity.
- PySCF stability at the ORCA geometries (commands 6-8; host reader
  `read_pyscf_h5`): enediyne stable in all three questions (lowest RKS ->
  UKS +0.0585 Eh); saddle stable but barely (RKS -> UKS +0.0047 Eh);
  p-benzyne RKS -> UKS UNSTABLE (-0.0643 Eh), internal and real ->
  complex stable. O-C PASS.
- CCSD(T)/cc-pVTZ, frozen core ("chemical core (12 el)", 28 correlated
  electrons; PySCF `frozen_core: auto` froze 6 orbitals), canonical, both
  programs: enediyne -230.448986832 (ORCA) / -230.448987546 (PySCF);
  saddle -230.401047509 / -230.401047855; p-benzyne -230.428143224 /
  -230.428143139 Eh. Totals agree within 7.1e-7 Eh, references within
  1.2e-8 Eh: O-G PASS. dE++ 30.08, dE_R 13.08 kcal/mol in both: O-F PASS.
  ORCA T1: 0.0128 (enediyne), 0.0164 (saddle), 0.0170 (p-benzyne): O-H
  PASS. Unasked finding: PySCF's RHF reference is RHF -> UHF unstable at
  ALL THREE structures (-0.035, -0.118, -0.243 Eh), the closed-shell
  enediyne included, while the RKS reference is unstable only at
  p-benzyne. An HF-level instability does not discriminate diradical
  character here; the Kohn-Sham one does.
- Oracle numbers (CCSD(T)/cc-pVTZ // B3LYP-D3(BJ)/def2-TZVP, my own
  unscaled harmonic terms): dH++(470 K) 28.19 kcal/mol (experiment 28.2 +-
  0.5); dH++(298 K) 28.69; dH_R(298 K) 12.60 kcal/mol (experiment 8.5 +-
  1.0), i.e. single-reference CCSD(T) on the RKS geometry of an
  RKS-unstable diradical lies 4.1 kcal/mol above experiment, the size
  Luxon et al. report (13.76 at CCSD(T)/cc-pVTZ // CCSD/cc-pVDZ).

## G1 -- observations while it runs (host records, first session)

- The session planned an all-ORCA first workflow: B3LYP/def2-TZVP opt+freq
  of the enediyne, DLPNO-CCSD(T)/def2-TZVPP and /def2-QZVPP single points
  (a two-point CBS route), and a relaxed scan of C1...C6.
- It asked for a broken-symmetry UKS singlet for the saddle, the IRCs and
  p-benzyne: first as `joboption: [BrokenSym 1,1]` (refused by the ORCA
  loader: `joboption` is ORCA's NEB-only option), then as
  `additional_route_parameters: [BrokenSym 1,1]`, which the loader accepts
  and ORCA rejects ("UNRECOGNIZED OR DUPLICATED KEYWORD(S) IN SIMPLE INPUT
  LINE ... BROKENSYM 1,1", caught free by the host's input-check probe).
  It then probed `FlipSpin 1`, `NoUseSym`, `FlipSpin` through the same
  probe. The hub has no typed broken-symmetry setting in any program
  (no `BrokenSym`, `guess=mix` outside the unqualified Gaussian link job,
  or UKS singlet in PySCF, whose reference follows multiplicity), so a
  scientifically correct request has no expression except native
  keywords -- the Fundamental-1 failure the charter names.
- Cycle 1 ended `planned`: the host refused the execution review
  ("every initial workflow node requires a green preview") because the
  session amended its scan node after the last compile and never
  recompiled it (the model's; the refusal is correct but names no node).
  The re-wake was charged a revision and called "the last for this goal";
  its route text offers only claiming from receipts in hand, an
  analysis-only plan, or declaring the observables undeliverable, though
  the cycle had spent no engine call (goal-loop wording; Q16's area).
- Cycle 2 (the Agent's recorded decision `bergman-method-protocol-bs-ccsdt`,
  host records): "the ORCA overlay cannot emit ORCA's %scf FlipSpin
  atom-list block -- input_string is a full-file replacement ... and
  additional_route_parameters appends to the simple input line where ORCA
  6.1.1 rejects 'FlipSpin 1,6'"; it moved the diradical species to
  Gaussian (`guess=mix`), kept the enediyne on ORCA, and planned (U)CCSD(T)
  at def2-TZVPP/def2-QZVPP in Gaussian; CASSCF/NEVPT2 named as the
  unavailable gold standard that bounds its numbers. A cross-program
  route with a recorded scientific reason (R1).
- Plan `bergman-bs-ccsdt`, 11 nodes under one approval: ORCA opt+freq
  (enediyne); Gaussian ts, opt (p-benzyne), irc forward/reverse; six
  Gaussian CCSD(T) single points, with an in-approval ORCA -> Gaussian
  geometry edge (ene-opt -> cc-*-ene). First wave: the three producers.
- The previewed Gaussian inputs are `# opt=(ts,calcfc,noeigentest) freq
  b3lyp def2tzvp guess=mix` and `# opt freq b3lyp def2tzvp guess=mix`: a
  restricted method for a singlet, where Gaussian's Guess=Mix has nothing
  to break. The CCSD(T) nodes are `ccsd(t) ... guess=mix`, likewise
  restricted. The host cannot see this: the intent lives in an untyped
  native passthrough, and the Gaussian reader (result_readers.py
  `_gaussian_functional`) reads `SCF Done: E(RB3LYP)` and strips the R/U
  prefix, so `functional` answers `b3lyp` either way and the surface's
  `reference` is `unknown`. To be settled by Gaussian's own output.

## G1 -- READ (CUHK Slurm 2152875, COMPLETED 22:57:47 HKT after 1 h 17 min; code digest 85752dd3 verified on the node)

- Settlement (ledger): `returned_to_human`, 2 cycles, 1 revision admitted,
  1 engine call: "cycle 2: the run ended in a state no revision can
  answer: pbnz-opt=not_launched, ts-search=not_launched".
- The one node that ran, ORCA `ene-opt` (B3LYP/G def2-TZVP defgrid3, no
  dispersion, opt+freq, 550 s), validated: E -230.977263 Eh, no imaginary
  mode. Its structure crossed to Gaussian inside the approval: two
  `validated_handoff` receipts and two bound data edges, ene-opt ->
  cc-tz-ene and cc-qz-ene, state (0, 1), atom order digest 84fcaa15
  (R2 holds on the only handoff executed). The analysis chain ran on that
  branch: extraction, host RRHO at 298.15 and 470 K. Everything
  downstream of the Gaussian nodes settled failed or skipped.
- HUB BREAK (the finding; repaired in 9cda6569, a `shared:` commit). Both
  Gaussian nodes were refused by the executor with ORCA's input-check
  lines ("orca: UNRECOGNIZED OR DUPLICATED KEYWORD(S) IN SIMPLE INPUT LINE";
  ORCA process ids 1682980/1682981). Those were ORCA's words about the
  earlier ORCA compiles of the same node ids (`FlipSpin 1,6`, 14:37:44).
  `_probe_input_check` returns early for a program with no probe and
  never retired the node's record. The stale abort reached the compile
  replies the model read for the Gaussian nodes (14:46:27, 14:46:30),
  the frozen review (`reviews/cycle-2.json` node_observations), and the
  executor's launch check, which called it "the program's own input check
  refused these exact bytes". Witness
  `test_an_input_check_speaks_only_for_the_compile_it_read`: red on the
  base with g1's lines, green on 9cda6569. This is the round's own gate
  (the probe runs inside allocations since Q9) breaking on the first
  route that re-planned a node across programs.
- Evidence for Q18 (reference / initial guess; from g1's host records):
  - No Gaussian output exists: the two Gaussian nodes never launched.
  - The previewed Gaussian inputs asked a restricted method for a
    singlet: `# opt=(ts,calcfc,noeigentest) freq b3lyp def2tzvp
    guess=mix` and `# opt freq b3lyp def2tzvp guess=mix`; the six
    CCSD(T) nodes `ccsd(t) <basis> guess=mix`. Nothing in the hub adds
    the U prefix, so these would have run restricted.
  - The Agent intended broken symmetry and planned host checks for it:
    validations `val-spin-ts` and `val-spin-pbnz` require <S^2> in
    [0.5, 1.6] (thresholds 0.5 / 1.6 on the extracted `spin_square`).
    Against O1, the saddle's RKS -> UKS eigenvalue is +0.0047 Eh (stable),
    so a true UKS saddle would also have collapsed to <S^2> 0 and failed
    its own check; p-benzyne is RKS -> UKS unstable (-0.064 Eh), where
    broken symmetry is physical.
  - ORCA: the session tried `BrokenSym 1,1` (refused by the loader as
    `joboption`, then by ORCA as a simple-input keyword) and `FlipSpin`
    (refused by ORCA); it recorded that `%scf` blocks are unreachable
    through the ORCA settings (input_string replaces the whole file).
- Model-side record (host records, not graded): cycle 1 ended `planned`
  because an amended scan node was never recompiled, and the review was
  refused. Cycle 2's decision names CASSCF/NEVPT2 as the unavailable gold
  standard, DLPNO-CCSD(T) or CCSD(T) at TZ and QZ as the primary energies
  with the TZ-QZ spread as an uncertainty term, and the composite
  E_CC + H_corr(DFT) at 470 and 298 K. A defensible route.
- B: not earned by g1 (a hub break stopped it). The rest is not read:
  B1-B4 had no delivered numbers.

## Live goal G2 -- PRE-REGISTRATION (written before submission)

Why a second goal: g1 was stopped by a hub defect, not by the model or
the science (its one executed handoff held; both Gaussian producers were
refused on another program's check). G2 is g1's task re-issued
byte-identical on the repaired tree -- the repair's first live probe
(CONDUCT section 4), not a re-roll: g1 stands as its own observation, and
G2 is a second, independent session (N runs are N observations).

- Task and workspace byte-identical to g1 (TASK.md sha256 5d430a88...,
  enediyne.xyz sha256 e18b5b9f...). Envelope numbers identical (make_goal.py
  --goal g2, same arguments). Same Agent, provider, delegated approval.
- Code: this branch at the commit that records this section: 9cda6569
  (the input-check repair) plus r10-integration a7bc02e0 (Q14: MDCI pair
  limit, NumFreq for MP2-class frequencies; Q16: goal-loop repairs),
  merged as 102e476f; tests/agent 3095 passed on it.
- H-G2a (the repair, live): if the session re-plans a probed node under
  another program or recompiles it, the compile reply, the review and the
  launch carry only the check of the node's latest compile. FALSIFIED by a
  launch refusal or a review observation quoting a check of bytes the
  node's current compile did not produce. "Not exercised" if no node is
  re-planned or recompiled after a check.
- Read exactly as g1 was pre-registered: R1-R4 and bands B1-B5 (B2 with
  both readings stated), each number against O1 at matched level where one
  exists. Milestone B is claimed only under the g1 condition (an
  Agent-chosen cross-program route with a recorded scientific reason, R2
  on every handoff, B1-B3 pass, B4 read as stated).
- For Q18, if any Gaussian node runs: its `SCF Done: E(R...)` or
  `E(U...)` label, any `S**2` line, and what the host's `functional`,
  `spin_square` and surface `reference` selectors answered for it.

## G2 -- READ (CUHK Slurm 2153334, COMPLETED 00:14:44 HKT after 51 min; code digest b572f5bd verified on the node)

- Outcome (driver): the goal PARKED at `execution_wave_decision_pending`
  after 2 cycles, 1 revision and 4 engine calls. That is not one of
  GOAL_SETTLEMENTS. The last workflow ("bergman-refusal-v6") holds no
  calculation, so no wave could ever be selected on it.
- H-G2a EXERCISED AND PASS (the repair, live). ORCA's input check aborted
  `modred-pbz` (15:43:42) and `modred-ts` (15:43:44). The session then
  re-planned both in Gaussian. Every later compile reply for them (15:51,
  15:54, 15:57) carries no probe line. The frozen review
  (`reviews/cycle-1.json`) carries none on those nodes. All four Gaussian
  nodes were launched. Under the same sequence on the base tree (g1) the
  compile reply, the review and the launch all carried ORCA's abort and
  the launch was refused.
- Route (R1): cycle 1 was ORCA broken-symmetry first (BrokenSym and
  FlipSpin in several spellings, six probe aborts), then an ALL-GAUSSIAN
  11-node plan: wB97X-D3(BJ)/def2-TZVP opt, modred, scan, ts, irc and sp.
  That is a single-program route (not B even had it run).
- PROGRAM REFUSAL: all four Gaussian nodes died in link 301 after 0.4 s:
  "R6DS8: Unable to choose the S8 parameter, IExCor= 4538 IXCFnc= 57
  ScaHFX= 1.000000 IDFTD=4". Gaussian 16 has no D3(BJ) parameters for
  wB97X. The hub compiled `functional: wb97x` + `dispersion: d3bj` into
  `empiricaldispersion=gd3bj` and previewed it green, and Gaussian has no
  input-check probe. The refusal is predictable from the pair; that is
  the settings-validation layer's to state (not in my radius).
- HOST WORD, FALSE: `ene-opt` (an opt job that died in l301 before any
  SCF) was typed `failed_nonconverged_geometry`; the modred and scan
  nodes were typed `failed_native`. Mechanism:
  chemsmart/agent/terminal_states.py:737-752. Gaussian's native class
  here is `native_runtime`, an "undiagnosed" class, so the derivation
  falls through to the opt's `optimization_not_converged` finding. The
  file's own comment ("A crash is not a convergence statement") states
  the invariant this breaks. The Agent saw through it: its repair-menu
  disposition rejected the restart route because "No geometry walk exists
  to restart from".
- MODEL (host records, the Agent's decision
  `bergman-host-capability-refusal-g2`): it repaired the dispersion
  correctly (wB97X-D) and then refused both observables. Its reasons:
  "the transition state carries substantial diradical character" and no
  loader in the hub can configure a broken-symmetry singlet. It rejected
  closed-shell DFT and RHF-reference CCSD(T), the latter as "poor
  reference for the open-shell singlet". The broken-symmetry gap is real
  (Q18's). The premise about the saddle is false: O1 finds the restricted
  B3LYP saddle RKS -> UKS stable (+0.0047 Eh), Kraka and Cremer find no
  significant biradical character at the TS, and the closed-shell route
  gives dH++(470 K) 28.19 against 28.2 +- 0.5. So refusing dH++ is the
  model's scientific error. Refusing dH_R rests on a real limit (single-
  reference CCSD(T) overshoots by about 4 kcal/mol here) that the
  literature handles with a stated bias rather than a refusal.
- For Q18: no Gaussian node reached an SCF in either goal (g1: never
  launched; g2: all died in l301). There is no `SCF Done` label and no
  <S^2> value from the Agent's runs. g2's routes carried `wb97x ...
  Guess=(Mix,Always)` without a U prefix (the modred and scan nodes). The
  session's own recorded reading is that the Gaussian loader "dispatches
  a neutral singlet as RKS" and has "no spin/guess axis".
- B: not earned by g2. Its failure is the model's (a false premise about
  the saddle, and over-strict standards), enabled by a real hub gap (no
  typed broken symmetry, Q18) and a program refusal the hub could have
  predicted (Gaussian wB97X-D3(BJ)).

## Status

- 2026-09-24: base verified; chemistry and references chosen and read;
  rehearsal next.
- 2026-09-24: rehearsal done provider-free: CLI heartbeat of the ORCA and
  PySCF writers the route leans on; the producer-edge admission matrix
  from `producer_edge_selection_rule` (opt/ts/modred hand structures to
  any program; ORCA scan minimum and PySCF IRC endpoint admitted; ORCA and
  Gaussian IRC endpoints refused in-approval, Q11's frontier); the engine
  rehearsal O1 (14/14 commands exit 0, all eight predictions PASS). No hub
  break found in radius before G1. tests/agent on a pristine export of
  0a3a24b9: 3060 passed; full suite 23 failed (the round baseline set:
  test_structures 19, pyscf dispersion 2, PyscfSettings 1, aggregation 1),
  4614 passed.
- 2026-09-24 (G1 running, cycle 2 wave executing): WAITING ON JOB 2152875.
  On resume read, in order: the ledger and settlement (read_goal.py); the
  Gaussian ts-search and pbnz-opt logs for `SCF Done: E(R...)` vs
  `E(U...)` and any `S**2` line (did guess=mix take effect?); whether the
  later cycles ran the six CCSD(T) nodes and the IRCs, and what each
  handoff receipt says (ORCA -> Gaussian enediyne edge); the thermochemistry
  and expression receipts; the claims and their stated uncertainty and
  level. Then B1-B5 and R1-R4, against O1.
- 2026-09-25: g1 read (above). Repair 9cda6569 (`shared:`, the input-check
  record). r10-integration a7bc02e0 merged (102e476f, no conflict). Gates
  on a pristine export of 1d18208c: full suite 23 failed (the baseline
  set), 4649 passed; tests/agent all green; ruff, black and isort clean on
  the two touched files. G2 (Slurm 2153334) running: WAITING ON JOB
  2153334. On resume: the same reading order as g1, plus H-G2a.
