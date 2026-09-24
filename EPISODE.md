# R10 episode q11 -- does what one approval admits reach the programs?

Base SHA: 1dbc9984fc7585c8758b62bffc67d6624d245603 (verified with
`git rev-parse HEAD` as the first action, 2026-09-24).

## The question (as currently understood)

When one approval admits a multi-stage route -- producer and consumer,
with the artifacts that pass between them -- does execution match the
approval? Four checks: (1) every admitted input reaches the program in
the form the program reads; (2) every admitted consumer runs when its
producer completes; (3) a later step cannot erase an earlier node's
evidence; (4) the Agent is never told a route exists that the executor
cannot walk.

## Premise replay -- provider-free, host records only (DONE, base tree)

Archive: 1,810 run streams (the CUHK download Q4 made, excluding r10;
the Hetzner mirror; experiments-public; the master's smoke1b copy).
Scripts under the session scratchpad `q11/` (census*.py). 432 frozen
approvals carry at least one launch reservation.

(1) Admitted inputs on launched consumers. 176 structure roles
(`filename`) reached argv. 6 of 6 admitted Hessian roles
(`validated_final_orca_ts_hessian` / `hess_filename`) did NOT: Hetzner
h1 irc_a, h1b irc-a/irc-b, qualification irc-agent-path irc-fwd/irc-rev,
irc-agent-path-2 orca-irc-both; `auxiliary_input_bindings: []` on every
one. Q4 counted 7; I count 6 launched (the 7th binding, r8 goal-ts, was
bound and never launched -- see (2)).

(2) Admitted consumers under the approval that admitted them, per bound
data edge (the producer validated and the host bound the edge):

| window | consumer ran | consumer never ran |
|---|---|---|
| Hetzner 2026-08-14 .. 09-13 | 281 | 2 |
| CUHK 2026-09-15 .. 09-16 | 11 | 10 |
| CUHK 2026-09-17 .. 09-24 | 0 | 92 |

Since the wave barrier (0f19ce36 "a wave runs its own members and
stops", 2026-09-16; 6fa000c9 "require an explicit wave boundary",
09-17) no admitted consumer in any archived stream has run under the
approval that admitted it. `validate_wave` calls a consumer and its
producer in one wave `depends_on` (not dispatchable), the executor's
cohort frontier runs wave members only, and every goal cycle plans and
approves a new workflow -- so an in-approval producer edge is displayed,
approved, bound, and never consumed. Of 198 admitted consumers that
never launched, 95 had a producer that did not validate (correct) and
103 had a validated producer and a bound edge.

Premise NOT falsified. It is broader than the brief's instances: (2)
is not a few goals, it is every goal since 2026-09-17.

## Plan (checks -> layers), each repair shown red on the base first

- C2 the wave contract: a wave may name a consumer with its producer
  when the one owner (`producer_edge_selection_rule`) admits every edge
  into it; the executor runs it after its producer validates and hands
  on. The Agent still chooses: producer alone (read first) or the chain.
- C1 the Hessian edge: review argv, executor synthesis, the ORCA writer
  (a bound Hessian is the Hessian the job reads), runner staging.
- C3 a handoff refused after a validated run: the producer's state
  transitions are recorded before any handoff, and a refused handoff is
  the consumer's word, not the producer's.
- C4 guides: `about_relaxed_scans` and the Gaussian scan-point binding.
- Then the settings-section miss (opt -> modred) and the ORCA IRC
  endpoint edge if budget remains.

## Falsifiers (written before any change)

- C2 is falsified if the replayed archive shows an admitted consumer
  whose producer validated and whose edge was bound running under its
  approval after 2026-09-17 (it does not: 0 of 92).
- C1 is falsified if an executed ORCA IRC with a bound TS Hessian prints
  "Compute numerically" for its initial displacement Hessian on the
  repaired tree, or if ORCA refuses `InitHess Read` with the staged file.
- C3 is falsified if, on the repaired tree, a handoff refusal after a
  validated producer still records the producer as launch-refused.

## Oracle O1 -- PRE-REGISTRATION (written before submission)

Question: does ORCA 6.1.1 read the Hessian ChemSmart now hands an IRC
and a saddle search, and which of `Calc_Hess True` / `InHess Read` does
it honour when the base writer wrote both? A CLI reference job (no
Agent, no provider), code = this branch after 4a9654cc (writer repair).
System: HCN <-> HNC 1,2-H shift saddle, neutral singlet,
B3LYP/def2-SVP (ChemSmart writes ORCA's `B3LYP/G`), 8 cores, 16 GB.
Guess geometry = the archived r8 goal-ts guess. Archived control on the
same system/ORCA (ORCA `b3lyp`, i.e. the VWN-3 form): saddle
-93.224285928 Eh, one imaginary mode 1121.71i cm-1; its IRC printed
"Initial displacement Hessian type .... Compute numerically", 21
forward steps to the HNC side, 11 min 8 s on 8 cores.

Commands (cli/o1/commands.txt): (1) saddle `ts` (Calc_Hess default,
Freq); (2) IRC forward `--hess-filename o1a_saddle.hess`; (3) the same
IRC with no Hessian (control); (4) saddle search from the guess
`--inhess-filename o1a_saddle.hess`; (5) the base writer's form by hand
(InHess Read beside Calc_Hess True) through `orca inp`.

Expected (bands never tuned after a result):
- A (1): converges; exactly one imaginary mode, |nu| in [1000, 1250]
  cm-1.
- B (2): native input carries `inithess read` and
  `Hess_Filename "o1a_saddle.hess"`; ORCA's "Initial displacement
  Hessian type" line is NOT "Compute numerically"; no numerical Hessian
  is computed; engine wall < 1/2 of (3). The path descends to a
  structure with N-H about 1.0 A (HNC side) or C-H about 1.07 A (HCN
  side), never back to the saddle.
- C (3): "Initial displacement Hessian type .... Compute numerically".
- D (4): native input `InHess Read` + `InHessName "o1a_saddle.hess"`,
  no Calc_Hess; the output reads that file as the initial Hessian and
  computes no SCF Hessian before the first step; same saddle as (1):
  |dE| < 1e-6 Eh, |d nu_imag| < 5 cm-1.
- E (5): the open question, no band: an SCF Hessian computed in cycle 1
  and read back from the job's own .001.hess means Calc_Hess wins (every
  base-tree seeded saddle search computed the Hessian it was handed);
  otherwise InHess Read wins (the base form was redundant, not wrong).
Falsifiers of the repair on the engine: (2) prints "Compute
numerically" or refuses the file; (4) computes an SCF Hessian before
its first step.

## O1 -- READ (CUHK Slurm 2151801, code 5823c7f3, digest 72bd4836 verified on the node)

- A saddle: PASS. One imaginary mode, 1122.56i cm-1; E -93.275915023 Eh.
- B IRC handed the saddle's Hessian: native input `inithess read` +
  `Hess_Filename "o1a_saddle.hess"`; ORCA: "Initial displacement Hessian
  type .... Read", "Hessian Filename .... o1a_saddle.hess", no numerical
  Hessian: PASS. Path to the HNC side (N-H 1.005 A, C-N 1.176 A),
  21 steps, 32.75 kcal/mol below the saddle at step 21: PASS.
  Runtime band FAILED: 7 min 14 s against the control's 7 min 48 s
  (ratio 0.93, band < 0.5). My premise that the numerical Hessian
  dominates an IRC's wall time is wrong for a 3-atom molecule: the 21
  path steps dominate.
- C control: "Compute numerically", 21 steps, 33.67 kcal/mol at step 21:
  PASS (the two paths differ by 0.9 kcal/mol at step 21 because their
  initial displacements came from different Hessians).
- D seeded saddle search: "InHess .... Read", the initial Hessian read
  from the file, no SCF Hessian before the first step: PASS. Same saddle:
  |d nu| 0.06 cm-1 PASS; |dE| 1.05e-5 Eh FAILED my 1e-6 band (my band was
  tighter than ORCA's default TS convergence; 0.0066 kcal/mol).
- E (the open question): with `Calc_Hess True` beside `InHess Read`
  ORCA 6.1.1 READ the given Hessian -- no SCF Hessian in cycle 1, and its
  optimisation energies equal D's to 1e-12 Eh. So the base writer's TS
  form was redundant, not wrong; the base TS defect was the silent drop
  of an `inhess_filename` given without `inhess: true`. Q4's unverified
  premise is settled: Calc_Hess does NOT override InHess Read.
- Aside (science, not host): ORCA's default IRC stops at 21 steps here,
  before the HNC minimum (both B and C); "reached its end" is not given.

## Live goals G1 and G2 -- PRE-REGISTRATION (written before submission)

Code: this branch at the commit that records this section (C2 wave
lines, C1 writer + review/synthesis/verification, C3 refused handoff,
C4 Gaussian scan point + guide texts). Agent: deepseek-v4-flash-0731
via alibaba-token-plan; delegated approval
claude-researcher-q11-owner-delegated (never a human decision).

G2 -- the archived r8 goal-ts task, byte-identical (TASK.md sha256
d2714db5..., guess sha256 7079f821...), same envelope numbers (ORCA
only, 8 cores, 32 GB, node 2400 s, episode 6600 s, reserve 600 s, 4
engine calls, 2 revisions). The archived run (Slurm 2142426) is the
control: its cycle-1 approval admitted ts-search -> irc-forward with
the geometry AND the TS Hessian; the IRC never ran under it; cycle 2
re-planned the IRC without the Hessian ("Compute numerically").
Host observations (not behaviour claims):
- C2: if the cycle-1 wave names the IRC with the saddle, both launch
  under one frozen approval in cycle 1; FALSIFIED if a wave naming both
  is not dispatchable, or if the IRC does not launch after the saddle
  validated in that run.
- C1: if the plan admits a Hessian edge into the IRC, its reviewed
  command shows `--hess-filename <producer-hess_filename:sha256=...>`,
  its launched argv carries --hess-filename, its native input `inithess
  read`, and ORCA prints "Initial displacement Hessian type .... Read";
  FALSIFIED by any of those missing, or by a launch refused as "differs
  from human review".
- If the Agent names the saddle alone (its choice), or binds no Hessian,
  that is recorded as the Agent's choice and C2/C1 are "not exercised",
  not passed.
Physics (B3LYP/def2-SVP; ChemSmart writes ORCA B3LYP/G): one imaginary
mode |nu| in [1000, 1250] cm-1; the branch descends to the HCN side
(C-H about 1.07 A) or the HNC side (N-H about 1.00 A).

G1 -- the hard cross-program route (milestone B candidate). HCN <-> HNC,
B3LYP/def2-TZVP; ORCA saddle -> PySCF IRC both directions from the ORCA
saddle -> PySCF relaxation and frequencies of each end. orca+pyscf, 16
cores, 48 GB, node 7200 s, episode 6 h, reserve 30 min, 14 engine calls,
3 revisions. Task text: goals/g1/TASK.md (names the programs and the
observables, never the waves or the edges).
Literature read in this session: Nguyen, Baraban, Ruscic, Stanton,
J. Phys. Chem. A 2015, 119, 10929 (OSTI 1392005 abstract): recommended
HCN -> HNC isomerisation energy at 0 K 5212 +- 30 cm-1 (14.90 kcal/mol),
HEAT-456QP 5236 +- 50 cm-1. Pearson, Schaefer, Wahlgren, J. Chem. Phys.
(IBM Research abstract): CI puts HNC 14.6 kcal/mol above HCN and the
barrier 34.9 kcal/mol (from HNC); SCF 9.5 and 40.2.
Bands (never tuned after a result):
- B1 saddle: exactly one imaginary mode, |nu| in [1000, 1300] cm-1.
- B2 connectivity: one PySCF branch relaxes to HCN (C-H 1.05-1.09 A,
  linear), the other to HNC (N-H 0.98-1.02 A, linear); each relaxed end
  has no imaginary mode (4 real modes for a linear triatomic).
- B3 energies: HNC - HCN electronic in [12, 18] kcal/mol and with ZPE in
  [12, 18] (against 14.90 at 0 K); barrier from HCN in [43, 52]; barrier
  from HNC in [28, 37].
- Milestone B needs, from host records: the ORCA saddle and all the
  PySCF nodes ran under ONE approval (one frozen approval id on every
  launch reservation) and validated, and the delivered numbers are the
  host's. A route the Agent splits over cycles (its choice) is recorded
  as such and is not B.

## Jobs issued

- 2026-09-24: O1, CUHK Slurm 2151801 (r10-q11-a), CLI oracle, 8 cores,
  code 5823c7f3, pre-registration digest a6b905f10825. COMPLETED
  (read above).
- 2026-09-24: G2, CUHK Slurm 2151911 (r10-q11-a), code 20dd195d
  (tree digest 35a90313), pre-registration digest c935847193f7.
- 2026-09-24: G1, CUHK Slurm 2151912 (r10-q11-b), code 20dd195d
  (tree digest 35a90313), pre-registration digest c935847193f7.

## Status

- 2026-09-24: premise replay done on the base tree; plan written.
- 2026-09-24: C2 (5ea8199b), writer (4a9654cc), compiler (f2525546)
  and host wiring (3d3daa36) committed with witnesses red on the base;
  tests/agent green on 5ea8199b (2975 passed).
- 2026-09-24: C3 refused handoff (ed1217ea), C4
  Gaussian scan point (c6b20491) and the two shared text commits
  (cde2c806 wave tool and rules, 1f11e221 relaxed-scan guide).
- 2026-09-24: r10-integration merged (Q10's episode; no conflict).
  Pristine export of the merge: tests/agent 2996 passed / 19 skipped /
  2 xfailed; full suite 23 failed, identical to the round baseline set
  (test_structures 19, test_pyscf_dispersion_conformance 2,
  test_PyscfSettings 1, test_aggregation 1), 4480 passed.
- Waiting on G2 (2151911) and G1 (2151912).
