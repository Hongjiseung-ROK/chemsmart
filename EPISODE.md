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

## Jobs issued

(none yet)

## Status

- 2026-09-24: base verified; chemistry and references chosen and read;
  rehearsal next.
