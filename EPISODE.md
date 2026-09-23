# R10 episode q4 -- composition integrity

Base SHA: b834057741edb1246d7d2762c374a0e83d4e4f33 (verified with
`git rev-parse HEAD` as the first action, 2026-09-24).

## The question (as currently understood)

Which organ disagreements and verdicts actually break the multi-stage
routes chemists take (scan -> saddle refinement -> IRC -> endpoint
characterisation; a saddle's Hessian into its IRC; the same across
programs), and can each such question be answered by one function
derived from reader and registry declarations, with a guard that
forbids the bypass?

## Falsifier of the premise -- run first, provider-free (DONE)

Replayed every reachable archived plan and run stream through the
b8340577 organs: 1,807 run streams (CUHK cluster excluding r10, read-only
download; Hetzner mirror; experiments-public), 1,325 plan events, 762
distinct plans, 881 data edges, 391 executed data-edge bindings, 78 goal
ledgers. The premise is NOT falsified; real plans were affected:

1. frontier vs review, ORCA scan -> opt/ts: 24 sessions ended "not
   approvable" on an edge the review admitted; 11 such edges executed.
2. review vs post-run handoff, ORCA modred -> ts: r9o-g5 cycle 2 lost the
   in-approval TS launch after 19,578 s of modred (recorded as a launch
   refusal of the node that ran).
3. ORCA TS Hessian -> ORCA IRC: 7 executed bindings; the executed IRC
   argv never carried --hess-filename (the reviewed argv never did
   either), ORCA printed "Initial displacement Hessian type .... Compute
   numerically" every time. LEFT (authority surface + executor + writer +
   runner; see report).
4. geometry.same_structure_comparison_not_made minted 49 anomaly receipts
   and 8 settlements `achieved_with_observations` on it alone.
5. 36 of 37 archived characterisation credits given on surfaces_agree
   None, silently; 12 credited through a consumer that moved the structure.
6. A Hessian inside one approval handed a saddle through the structure
   edge's XYZ judged as a minimum's (latent in goal runs; 833c072f was
   witnessed on an input production never passes).

## Repairs committed (see git log)

R1 one owner for producer-edge admission (+ frontier, waiting reply,
dispatch, native handoff of modred; lint forbids the bypass); authority
unchanged on 881/881 archived edges and 133/133 archived bundles. R3 the
floor is written on the receipt, never minted; signal lint. R4 a curvature
node inherits the approved producer's promise through a structure edge.
R5 characterisation credit only from a structure-keeping consumer, and an
uncompared credit is named in the settlement.

## Live validation -- PRE-REGISTRATION (written before any submission)

Goal q4/g1, CHEMSMART Agent (deepseek-v4-flash-0731 via
alibaba-token-plan), delegated approval
claude-researcher-q4-owner-delegated. System: 1,1'-binaphthyl, C20H14,
20 heavy atoms, neutral singlet, one atropisomer built by RDKit
ETKDGv3/MMFF94 (C2-C1-C1'-C2' = -87.4 deg; atoms 9,10,11,12 one-based).
Task: locate and characterise the lowest-barrier racemization TS with
ORCA; barrier (electronic and dG(298.15 K)); connectivity by an IRC
computed with PySCF from that TS, each branch relaxed and identified.
Envelope: orca+pyscf, 64 cores, 150 GB, node 5 h, episode 11 h, 10
engine calls, 5 revisions.

Oracle (source texts read in this session): Chem. Sci. 2019, 10,
2285-2289 (Europe PMC PMC6399675 full text): Table 2, compound 1
experimental barrier 24.1 kcal/mol (citing Meca, Reha, Havlas, J. Org.
Chem. 2003, 68, 5677), B3LYP-D3/def2-TZVP//B3LYP/6-31G* 24.6 kcal/mol;
Table 1 (B3LYP/6-31G(d)) compound 1 GS dihedral 105 deg, TS 180 deg;
"the anti-pathway is generally favored by more than ~5 kcal/mol";
"for the closed-shell biaryls, the rotational anti-TS is centrosymmetric".
Meca 2003 abstract (Europe PMC): "1,1'-binaphthyl (1) ... The preferred
pathway is found to be anti with centrosymmetric transition state.
Whereas the reaction path of 1 goes downhill from transition to ground
state ...".

Physics bands (never tuned after a result is seen):
- B1 barrier: electronic dE(anti TS - minimum) in [19, 29] kcal/mol;
  dG(298.15 K) in [19, 29] kcal/mol.
- B2 TS: exactly one imaginary mode, |nu| in [15, 250] cm-1;
  C2-C1-C1'-C2' = 180 +- 10 deg (anti). A syn TS (0 +- 10 deg) is a
  route finding, expected >5 kcal/mol above anti; the "lowest-barrier"
  answer then fails B1/B2.
- B3 minimum: |C2-C1-C1'-C2'| in [70, 110] deg.
- B4 connectivity (PySCF IRC from the ORCA TS): the IRC's start spectrum
  carries one imaginary mode; the two branch endpoints, relaxed, have
  dihedrals of opposite sign with magnitudes in [70, 110] deg and
  energies within 0.2 kcal/mol (enantiomers); each branch descends
  without an intermediate.
- Failure: a branch returns to the starting enantiomer or stops off a
  minimum; barrier outside B1; TS not first order.

Host falsifiers (repairs under test; only where the Agent's own route
reaches them -- a different valid route is evidence, not failure):
- F-R1: an admitted modred -> ts (or scan -> opt/ts) edge refused after its
  producer ran, or its consumer called blocking while the review admits it.
- F-R4: a freq/hess handed a saddle through a structure edge, printing
  exactly one imaginary mode, typed failed_wrong_stationary_point.
- F-R5: a credit given on uncompared surfaces with no settlement line.
- Infrastructure (not model behaviour): zero provider turns,
  turn_deadline_exceeded, gate closed.

## Jobs issued

- 2026-09-24: goal q4/g1 submitted as Slurm 2149497 (r10-q4-a), code
  commit 74540fa6 (tree digest b434f280...), pre-registration digest
  c89b82cda1be recorded by slot_submit.

## Status

- 2026-09-24: replay done; R1, R3, R4, R5 committed with witnesses;
  tests/agent green (2758 passed). Live goal g1 pre-registered above.
- 2026-09-24: r10-integration merged (85a81735, no conflict). Pristine
  git-archive export of 85a81735: tests/agent 2760 passed / 19 skipped /
  2 xfailed; full suite 23 failed (tests/test_structures.py 19,
  test_pyscf_dispersion_conformance.py 2, test_PyscfSettings.py 1,
  test_aggregation.py 1 -- none in a touched file), 4240 passed. ruff,
  black, isort clean on every touched file.
- Goal g1 (Slurm 2149497) running: code digest verified on the node,
  cycle-1 planning session live. WAITING ON JOB 2149497.
