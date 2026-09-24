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

## Status

- 2026-09-24: base verified; chemistry and references chosen and read;
  rehearsal next.
