# R10 episode Q16 -- where goals are lost

Base SHA: 2c1050c74cc31c76d6f51970b9b03c4e37e7cf50 (verified with `git rev-parse HEAD` at start).
Brief: scratchpad/q16/BRIEF.md, sha256 9a94083b35c2a26c4420dab3355bf2dfb9135f5b176de0f859b7b5ad7a1b3ff7.
Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

When a CHEMSMART goal ends short of `achieved`, what ended it -- the science,
the model, a program, infrastructure, or the host's own loop? For every
host-caused class: the mechanism, and whether the host can stop losing goals
that way without changing what an approval grants or what a settlement word
means.

## Census (provider-free, 2026-09-24)

Scope read: 95 CUHK goal ledgers (r8, r9, r10 except r10/q6 which is sealed;
the 2026-09-15..21 campaigns under /project/xlzhang/jiseung; r10/m* read) and
188 ax41 ledgers (`~/developer/chemsmart-hetzner-mirror/2026-09-14/campaign`,
claude/ excluded; 4 are byte-identical copies of one goal, so 184 goals).
880 planning-session streams, 10,228 provider turns.

Denominator: 279 goals; 145 settled achieved / achieved_with_observations;
134 ended short (57 CUHK, 77 ax41). First cause of each, read from ledgers,
streams, run streams and job logs (scratch q16/census/classification*.py):

| era | n | HOST | INFRA | MODEL | DELIB. | CAPAB. | SCIENCE | OPER. | PROGRAM | unres. |
|---|---|---|---|---|---|---|---|---|---|---|
| CUHK R8-R10 | 26 | 9 | 1 | 3 | 2 | 7 | 2 | 1 | 1 | 0 |
| CUHK pre-R8 | 31 | 6 | 11 | 2 | 5 | 2 | 2 | 3 | 0 | 0 |
| ax41 | 77 | 27 | 11 | 12 | 6 | 6 | 7 | 1 | 0 | 7 |
| all | 134 | 42 | 23 | 17 | 13 | 15 | 11 | 5 | 1 | 7 |

HOST = the host's own loop (termination, settlement, park, wake, budget,
admission); CAPABILITY = a hub reader, writer or registry gap outside the
loop (other episodes' radii).

Corrected after Q14 merged (866e1833), on my own reading of the receipts with
Q14's census as evidence: three goals I had as PROGRAM are CAPABILITY. r9/xtb
g3 and ax41 goal-h2 are finished xTB runs a host result rule refused (their
receipts carry only host findings, applied/requested charge and multiplicity
mismatches; goal-h2's three have exit 0 and engine_complete true): I had read
the host's word failed_native as the program's. r10/q12 g1-hi is an input the
request determined ORCA must refuse (the MDCI pair rule, now refused at
compile, 4ed32f97). The contributing "PROGRAM" on r10/q3 g2 and r10/q9 g1 is
the same writer class. A program's own failure now first-causes 1 of 134
(r8 h3, ORCA nodes dead at start-up in 12 s; not reconciled with Q14's E/R).

HOST is the largest single first cause (42/134). 33 of the 42 are in classes
repaired before this episode (cited per goal). Classes the base tree still
produces:

- H1 a partial analysis completion cannot terminate: the loop ends the session
  `planned` bound to the completion receipt; the event store admits `planned`
  only over the latest workflow draft (`planned termination requires the latest
  workflow draft`; before f913f5d7 the same loss read `a required completion
  gate is red`). o2r (R10 Q13), ino3-r11, e4p-cyclohexane-b1, c5-r1: 4 goals.
- H6 (found while replaying o2r) a planning session that raises is projected
  from the previous cycle's streams: the failed cycle's claims and findings
  never reach the workspace record, and the previous run is re-recorded under
  the failed cycle's label. o2r, e4p-cyclohexane-b1.
- H2 an output a delivered claim cites as its uncertainty is counted "computed
  and never rendered as a claim": r10/q3 g2 and r10/q9 g1 settled
  returned_to_human over passed completions; g5-methoxy in part; 8 more goals
  had a revision opened for it.
- H3 a hidden AppleDouble sidecar (`._x.xyz`) admitted as a molecule: the goal
  ends before any session (r10/m1 smoke1).
- H5 a molecule the human placed as SDF is never admitted (r9/xtb g2).
- H4 (Q15's radius, reported) an analysis-only plan resets the execution-wave
  decision, so an approved calculation workflow parks for ever (smoke1b,
  losartan-micropka-r2).
- H7 (found live in L1, then in the archive; left, see below) a failed
  criterion the session answered still makes the toolchain completion
  partial: `_claims_on_a_failed_criterion` never consults the decision that
  cites the failed validation receipt, while the settlement counts exactly
  that citation as the answer (driver unanswered_verdicts, since c3744879,
  2026-09-02; the completion rule came 2026-09-11, f913f5d7) and the wake
  tells the model "standing by the result" is an answer. Behind H1 in o2r
  and ino3-r11 (both would still return once H1 is repaired); live in L1.

Premise falsified as stated: the brief's instances are not the only host
losses (H2, H5, H6 and H4 are further live classes), and the instances named
had earlier members (H1 x3).

## Replays (provider-free)

- o2r cycle 2, transcript replayed through `GoalDriver.resume` +
  `run_live_agent_session` with the provider transport replaced by the
  archived public transcript (scratch q16/tools/replay_goal.py). On the
  commit that ran it (09450c74): settles returned_to_human, reasons
  `["cycle 2, planning session: planned termination requires the latest
  workflow draft"]`, byte-identical to the ledger; 13/13 turns served, no
  receipt translated. With the H1 repair only: the session terminates
  `planned`, the driver records the session stream, admits the analysis-only
  revision and opens the one re-wake (the model's own criterion
  `external_no_spin_instability` failed, so its claims stand on a result the
  host reads as rejected).

- H2, per cycle (scratch q16/tools/replay_cycle_settle.py over the ten
  archived recoveries whose unclaimed ids include an output a delivered
  claim cites as its uncertainty; logs replay/cyc-base.log,
  cyc-repaired.log). Base 2c1050c7 reproduces all ten recovery rows and
  their unclaimed ids exactly. Repaired: five would not have opened --
  r10/q13 dans c1 achieved, r10/q3 g1 c2 achieved, r8 smoke c2
  achieved_with_observations, wave-heartbeat butane-wave-3 c3
  achieved_with_observations, ax41 g2-phosphine c1 achieved; five still
  recover on what remains (g2-hono, g4-formaldehyde-h2, sm2-hcn-hnc,
  g3c-allyl name only their genuinely unclaimed ids; xtb-ir-r10 c4
  recovers on its verdicts with none unclaimed).

## Repairs (committed, each with a witness red on 2c1050c7 and green here)

- ad15e81a H1 loop: a partial completion ends the session `planned` on its
  workflow draft (test_a_partial_delivery_ends_its_session).
- 65fe94e7 H6 driver: a cycle whose planning session raised is projected from
  its own stream (test_a_failed_cycle_is_projected_from_its_own_stream).
- 12b2bbbe H2 driver: an output a delivered claim carries as its uncertainty
  is rendered (test_a_claimed_uncertainty_is_rendered). Settle-step replays:
  base reproduces q3 g2, q9 g1, g5-methoxy byte-for-byte; repaired: q3 g2
  achieved_with_observations, q9 g1 achieved, g5-methoxy still returned
  naming its three genuinely unclaimed ids.
- 7bf1a744 H3 live_session: a hidden file is never admitted as a molecule
  (test_a_hidden_file_is_not_a_molecule).
- 5c275158 (regression of ad15e81a, caught by the full tests/agent run of
  the merged tree, 2 failed / 3062 passed): the bare draft call raised out
  of the partial branch where no draft stands and skipped the review
  block. The fallback is now caught in place in the sibling endings'
  shape. The real host never reaches it (a not-green completion is minted
  only over the latest draft; the delivered-claims certificate is minted
  passed), so the live goals below, packed at 71de94b9, stand on the same
  behaviour.

## Pre-registration (written before any live goal; nothing seen yet)

Two goals on the repaired tree, each re-posing an archived lost goal's task
byte-identical (TASK.md, starting geometry, envelope numbers, max-revisions
2, local dispatch). Agent: deepseek-v4-flash-0731 via alibaba-token-plan.
Granted by claude-researcher-q16-owner-delegated (a delegated approval, not
a human decision).

L1 o2r-rep: R10 Q13 o2r's task (singlet O2 as a closed shell, RKS
B3LYP/def2-SVP, 1.2075 A, PySCF; stability for both kinds of rotation and
the reference energy). pyscf cpu, 8 cores, 16 GB, node 1800 s, episode
5400 s, 4 engine calls.
- Physics bands (from the archived run and Q13's regenerated fixture):
  E(RKS) = -150.1418 +/- 0.0005 Eh; internal: stable (|lowest| < 1e-4 Eh);
  RKS->UKS: unstable, lowest -0.0926 +/- 0.003 Eh; real->complex: unstable,
  lowest -0.0383 +/- 0.003 Eh. The scientific answer: the restricted
  reference is not a stable solution (stable to real restricted rotations,
  unstable to spin symmetry breaking and to complex rotations).
- PASS (the repair's claim, H1/H6): the settlement reason is read from the
  delivery -- no settlement or wake quotes a host ContractError ("cycle N,
  <phase>: ..."), every planning stream that ended has its terminal event,
  and each cycle's claims and findings reach the workspace record under
  that cycle.
- The word the science supports, under unchanged settlement semantics:
  achieved or achieved_with_observations (scf.reference_unstable carried)
  when the three answers and the energy are delivered by their declared
  ids; returned_to_human read from the receipts if the session again
  encodes "stable" as its own acceptance criterion (that criterion fails on
  this physics, and a failed criterion rejects the result it read). Either
  is reported with the transcript; only a host-error word is a FAIL.
- FAIL: a host-error reason; a planning stream left without a terminal
  event; a cycle's claims missing from the workspace record.

L2 q9g1-rep: R10 Q9 g1's task (methanol O-H bond dissociation enthalpy,
298.15 K, level open). orca cpu, 8 cores, 16 GB, node 1800 s, episode
7200 s, 12 engine calls.
- Physics band: DH298(CH3O-H) within 420-450 kJ/mol (100.4-107.6
  kcal/mol) for any defensible DFT or composite level. (The experimental
  value near 437 kJ/mol is recalled, not a registered constant; it sets no
  band.)
- PASS (H2): no recovery_opened and no settlement names as "never rendered"
  an output a delivered claim carries as its uncertainty_reference. Whether
  the session uses an uncertainty reference at all is the model's choice
  and is reported, not scored; if it does not, H2 is not exercised live.
- The word the science supports: achieved / achieved_with_observations when
  the BDE is delivered by its declared id within the envelope; otherwise
  the reason is read and classified.

Not counted either way: a session with zero provider turns or one that dies
on turn_deadline_exceeded (infrastructure). A weak run is reported, never
re-rolled.

## Live results (read from host records; written after both jobs ended)

L1 (Slurm 2152989, 15 min, code 71de94b9). Cycle 1: 15 provider turns, one
PySCF RKS node (12.3 s, validated); the executor's chain claimed the energy
and two verdicts as numbers 0.0, its two stability criteria failed, and a
recovery opened (stale e_ref/rks_e_ref_hartree, undelivered
rks_stable_real/rks_stable_complex, verdicts). Cycle 2: 11 turns,
analysis-only revision admitted; claims: E = -150.14180683 Eh (+/-1e-6),
words stable_ext = "unstable", stable_complex = "unstable", stable_int =
"stable"; findings answer both declared categories; the decision cites the
latest failed validation receipt of each criterion. The completion went
partial (claim_on_failed_criterion x3); the stream ended `planned` with the
H1 reason ("the analysis completion is partial; the delivery stands with
the limitations it names"). Settled returned_to_human: "the session ended
'planned' (...); it recorded analysis but the host completion gate did not
pass". 1 of 4 engine calls, 1 of 2 revisions spent.
- Physics: E(RKS) -150.141807 (band -150.1418 +/- 0.0005); internal lowest
  +2.0e-6 Eh, stable; RKS->UKS lowest -0.092617 Eh (band -0.0926 +/-
  0.003); real->complex lowest -0.038300 Eh (band -0.0383 +/- 0.003). All
  four in band.
- Pre-registration: PASS. No host-error word; both planning streams
  terminal (waiting_for_approval, planned); cycle 1's result and claims and
  cycle 2's claim and three findings are in the workspace record under
  their cycles. The word is the one pre-registered for a session that again
  encodes "stable" as its own criterion. It is not the word the science
  supports: that is H7 (above), which I leave (see Left).
- Replays of L1's own records: cycle 2's transcript through GoalDriver.resume
  on 71de94b9 reproduces the archived recovery_opened and goal_settled
  payloads byte-for-byte (330 and 4247 bytes; 11/11 turns, no digest
  translated); on base 2c1050c7 the same transcript ends returned_to_human
  "cycle 2, planning session: planned termination requires the latest
  workflow draft", evidence {} -- o2r's loss -- and the record gains cycle
  1's result and claims re-labelled `goals/l1-o2r/runs/cycle-2`, a run that
  never existed (H6's run half).

L2 (Slurm 2152990, 22 min). Cycle 1: 17 turns, six ORCA nodes (opt+freq
MeOH and MeO at B3LYP-D3(BJ)/def2-TZVP, H atom sp, PBE0 single points; 237 s
engine wall, all validated); the executor's chain claimed bde-oh-methanol =
413.61 kJ/mol with uncertainty 5.27 measured, uncertainty_reference
bde-method-spread. Recovery opened naming only bde-pbe0 (exported, never
claimed). Cycle 2: 13 turns, claimed bde-pbe0 = 408.34 and the headline with
an RSS uncertainty (5.0); completion passed; ended complete. Settled
achieved; 6 of 12 engine calls spent.
- H2 PASS: the settle step of cycle 1 replayed on 71de94b9 reproduces the
  archived recovery_opened byte-for-byte (unclaimed [bde-pbe0]); on base
  2c1050c7 it names [bde-method-spread, bde-pbe0] -- the delivered claim's
  own measured uncertainty as never rendered.
- Physics band 420-450 kJ/mol: MISSED, 6.4 kJ/mol below its floor.
  Recomputed from the raw ORCA outputs: H(MeO) + E(H) + 5/2RT - H(MeOH) =
  0.157536 Eh = 413.61 kJ/mol (De 447.4, dZPE -39.2, thermal +5.4), so the
  number is the level's own, not the host's arithmetic. The band's premise
  ("any defensible DFT") was mine and wrong for B3LYP here. The session
  recorded in its decision that the value sits ~24 kJ/mol below
  experiment near 437 (Blanksby & Ellison 2003, as the session cites it)
  and called the claim a computed gas-phase enthalpy; its +/-5 kJ/mol does
  not cover that systematic offset, and 6 engine calls went unspent.

## Left, with the owner's question

- H7. The repair that honours citations per receipt in the completion
  (the settlement's own rule) would recover ino3-r11's shape (every failed
  receipt cited) and change no word's definition. It would not recover o2r
  or L1: each evaluated its criterion twice and cited only the latest
  receipt, so the settlement's per-receipt rule would still return them
  ("a validation verdict failed and no recorded decision cites it"). To
  reach achieved_with_observations those need a supersession rule (the
  latest evaluation of a node answers for it) in both organs. Both changes
  decide what "answered" means, which is settlement semantics (Q10/owner),
  so I did not make them.

## Status

- step 1 (census) and step 2 (repairs H1, H6, H2, H3) done; H5 (SDF) and
  H4 (Q15's) left and reported. Step 3: live goals L1, L2.
- Live goals submitted on code commit 71de94b9 (pre-registration digest
  6eb75d76cca0): L1 CUHK Slurm 2152989 (slot r10-q16-a,
  /project/xlzhang/jiseung/r10/q16/goals/l1-o2r), L2 CUHK Slurm 2152990
  (slot r10-q16-b, goals/l2-q9g1). Both ended; results above.
- Merged r10-integration at 2cfdb4ca (Q14's 866e1833 included; clean). Gates
  on the final commit: see the hand-back.
