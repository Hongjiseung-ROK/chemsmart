# R10 episode Q19 -- when the Agent's own expectation fails

Base SHA: a7bc02e031a703c24a7b9fcf38d8301211f12ed4 (verified with `git rev-parse HEAD` at start).
Brief: scratchpad/q19/BRIEF.md, sha256 521ce13e577ca48d7fd730a50a3affc1d0cbfacc0e46b15861fb5da78c40729e.
Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

When a plan's own acceptance criterion (a `scientific_validation` rule the
Agent planned) fails, is that a finding the goal can deliver -- the failed
receipt and the Agent's recorded reading of it standing in the delivery --
or a delivery the goal has failed? Four host organs answered it on the base
tree, each differently:

- the session's toolchain completion (`_claims_on_a_failed_criterion`)
  named every claim that descends from a failed criterion and never read a
  decision;
- the executor's completion of an approved chain and the certificate for a
  delivery made from registered results (the fourth organ, found here) never
  looked at criteria and minted `passed`;
- the settlement counted a verdict answered only when a decision cited that
  exact receipt, read only the stream it settled, rejected a verdict's result
  whether or not it was answered, and settled an answered verdict plain
  `achieved`, naming nothing.

Answer being tested: one function over the records (`goal.failed_criteria`)
-- a verdict is answered when a recorded decision cites a receipt stating it
(same node and rule, same number, same results; threshold not part of the
identity; a later pass never answers a failure) -- called by every organ.
Answered: a certified delivery carrying the failure as an observation
(`achieved_with_observations`, the charter's word for "a pre-registered
expectation the physics left"). Unanswered: nothing standing on it is
certified, in any cycle, and the reason names it.

## Falsifiers (armed before the census)

- The organs never disagree on a real record apart from L1, o2r, ino3-r11:
  then repair those and end.
- Unifying certifies a goal whose failed criterion no recorded decision
  answered: that is the result, reported.
- The answered-verdict rule needs a settlement word to change meaning:
  owner's decision, reported with the evidence.
- The base replay of any archived word differs on its own run commit: the
  harness is wrong and nothing downstream of it is believed.

## Census (provider-free, 2026-09-25)

Scope: CUHK -- every events.jsonl under /project/xlzhang/jiseung except
r10/m*, r10/q6, r10/q17, r10/q18, any sealed/private/oracle* dir and code
trees (419 streams, 42 with validation receipts, 5 with a failed one). ax41
mirror 2026-09-14 and 2026-09-15 campaigns, claude/ excluded (1,111 streams,
323 with validation receipts, 49 with a failed one; 18 of those are
pre-goal sessions or qualification replays with no goal).

Denominator: 24 goals whose own records hold a failed acceptance criterion
(CUHK 3: o2r, l1-o2r, xtb-ir-acetamide r8; ax41 21: ino3-r11 and 20
general-round goals). suff1-goal-ino3-cont shares ino3-r11's workspace but
its own records hold none.

| answered by | goals | today's organs | unified |
|---|---|---|---|
| nobody, one cycle (r1-floor-r1..3, r1-a-r1..3, s7, s12) | 8 | run path opens a recovery naming the verdict (archived achieved came from pre-c3744879 trees) | same |
| nobody; later cycle replaced the structure (r1-ab-r1..3, r2-s7-r2) | 4 | achieved | same |
| nobody; later cycle rendered no claim (r2-s7-r3) | 1 | recovery (stale) | same |
| nobody; decision discussed, did not cite (acetamide r8) | 1 | returned, names the verdict | same |
| nobody; later cycle rewrote the criterion and delivered from the rejected saddles (h1b) | 1 | **achieved** | returned, names r-dob-sep, r-frac-a, r-frac-b |
| cited, same stream (lad-a1-r1, lad-a0-r2) | 2 | **achieved**, failed criterion not named | achieved_with_observations, names it |
| cited latest of identical re-evaluations (L1, o2r) | 2 | returned (H7) / re-wake then return | achieved_with_observations |
| cited; settled on an H1 typed error; run commit absent (ino3-r11) | 1 | projection only | projection: answered |
| cited; other conditions decide (s4 undelivered id; lad-a1-r2 no completion) | 2 | returned | same |
| nobody; transport / no workflow (r2-s7-r1, h1) | 2 | returned | same |

Base reproduction on the run commit: L1 (71de94b9) and o2r (09450c74)
cycle-2 transcripts reproduce recovery_opened and goal_settled byte for
byte (also on a7bc02e0 for L1). acetamide r8 reproduces on a7bc02e0.
ax41 goals ran on goal_loop.py (8ad09cab, 533b686a, fec78baa, ff7f325b) or
on commits absent from this repository (8dd57bc6, 102413ce, 2cca498e); their
archived words are not reproduced on their own commits (stated, not
claimed). Harness: scratchpad/q19/tools/replay_final.py (settle step),
replay_goal.py (Q16's, transcript).

## Defects found

- The organs' disagreement (above).
- `_recorded_run_receipt` matched `"receipt_sha256": "<d>"` with a space the
  event store never writes: every decision citing a recorded run's receipt
  -- the route the wake prescribes after a run -- is refused. Latent in the
  archive (0 of 66 refused citations were run receipts of a citable kind);
  its test built its stream with json.dumps' spaced separators.
- The doubt branch of the session completion rebound `findings`, erasing the
  failed-criterion findings beside it.

## Repairs (one commit each; every witness shown red on its parent, green on it)

- e59a0f77 one function, every completion organ (session, executor walk,
  delivered-claims certificate) and the settlement's answered-ness.
- 06c414d9 the doubt branch no longer erases failed-criterion findings.
- f0658c67 (for the owner) an answered criterion is carried by the word:
  achieved -> achieved_with_observations for lad-a1-r1, lad-a0-r2.
- 7ce7df21 (shared) a decision may cite a recorded run's receipt.
- bb74c455 goal grain: a number standing on another cycle's unanswered
  criterion is not certified (h1b achieved -> returned_to_human).
- c642982a thermochemistry receipts enter the verdict join.

Census replays at c642982a against a7bc02e0: 3 settle-step words change
(lad-a1-r1, lad-a0-r2, h1b); L1 and o2r transcripts settle
achieved_with_observations at cycle 2 naming their failed criteria.

## Live goal -- pre-registration (written before any live run of this episode)

Reference job first (CLI, slot a, code c642982a): PySCF RKS B3LYP/def2-SVP
single points with stability analysis for O2 at 1.2075 A (calibration: must
reproduce L1's archived E = -150.141807 Eh, external -0.092617 Eh,
real->complex -0.038300 Eh, internal stable, each within 1e-5 Eh) and for
S2 at 1.889 A. The S2 numbers set the live goal's physics bands (E +/-0.0005
Eh; each lowest eigenvalue +/-0.003 Eh), written here in a commit before the
goal is submitted.

Live goal L-S2 (slot b, code c642982a or its successor on this branch,
recorded by the doorway): TASK = L1's task with the molecule changed --
closed-shell singlet S2 at B3LYP/def2-SVP, gas phase, 1.889 A, PySCF; "is
that restricted reference a stable solution ... yes-or-no answer I can
defend, stated for both kinds of orbital rotation, and the electronic
energy of the reference in hartree". Nothing in the task names a criterion,
a validation or an expectation. Envelope: pyscf cpu, 8 cores, 16 GB, node
1800 s, episode 5400 s, 4 engine calls, max-revisions 2, local dispatch,
granted by claude-researcher-q19-owner-delegated (a delegated approval, not
a human decision). Agent: deepseek-v4-flash-0731 via alibaba-token-plan.

- PASS (the repair's claim), read from host records: if the session's plan
  carries an acceptance criterion the physics fails, then (a) no completion
  certifies `passed` over a claim standing on it while it is unanswered;
  (b) if a recorded decision cites a receipt stating the verdict, the goal
  settles achieved_with_observations and a reason names the criterion, the
  number that failed it and the citing receipt; (c) if none cites it, the
  goal returns naming the verdict. No settlement or wake quotes a host
  ContractError.
- The word the science supports (if the reference job confirms an
  instability): the restricted reference is not stable to spin-symmetry
  breaking; a delivery that says so with the energy is achieved or
  achieved_with_observations, with the failed expectation standing in it.
- FAIL: a host-error word; a certified word over an unanswered criterion; a
  returned word that names no finding; a failed criterion missing from an
  achieved_with_observations word.
- Not counted either way: the session plans no acceptance criterion (the
  repair is then not exercised live, reported so); zero provider turns or
  turn_deadline_exceeded (infrastructure). A weak run is reported, never
  re-rolled.

### Reference job s2ref (CUHK Slurm 2153508, code c642982a, digest 905bf301)

Read through the host's own extraction tool from the result files:
- O2 calibration: E = -150.1418068 Eh, internal -3.2e-7 (stable),
  external -0.0926179, real->complex -0.0382998 Eh -- L1's archived
  values reproduced within 1e-6 Eh. PASS.
- S2 at 1.889 A: E = -796.1097378 Eh; internal +1.2e-6 (stable);
  external -0.0584831 Eh (unstable); real->complex -0.0288198 Eh
  (unstable).

### L-S2 physics bands (fixed here, before the goal is submitted)

- E(RKS S2) = -796.1097 +/- 0.0005 Eh.
- internal rotations: stable (|lowest| < 1e-4 Eh).
- RKS->UKS (external): unstable, lowest -0.0585 +/- 0.003 Eh.
- real->complex: unstable, lowest -0.0288 +/- 0.003 Eh.
- The scientific answer: the restricted reference of singlet S2 is not a
  stable solution -- stable to real restricted rotations, unstable to spin
  symmetry breaking and to complex rotations -- the same answer as O2's,
  under a perturbation of the molecule.

## Status

- step 0: brief read, base verified, charter/lessons/CONDUCT read.
- step 1 (census, provider-free): done (above).
- step 2 (repairs): done, seven commits (b568eab3 repairs c642982a's
  regression on a host built without __init__).
- step 3: reference job 2153508 done (above); live goal L-S2 next, on
  code b568eab3.
