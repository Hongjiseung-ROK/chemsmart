# R10 episode Q24 -- every word the host signs, checked against the function that signs it

- Base SHA: ec41a57c28838841aaab710a0f099c256820cdd9 (verified with `git rev-parse HEAD` as the first action, 2026-09-25).
- Brief: scratchpad/q24/BRIEF.md, sha256 d960edafb648a476...
- Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

Does every word the host signs -- a settlement and its reasons, a
completion receipt's status, the executor's analysis status, a
certificate, a `qualified` row, a terminal word -- follow from the records
it signs over, on every path that can reach it? Where two host functions
answer one question (a reader and the signer), does a mechanical parity
check over real records find each divergence, and can it live in the
suite so the divergence cannot come back?

Starting instance (R10 Q21, g2-hooh, CUHK 2153668): `achieved` signed with
the reason "cycle 2: workflow completed; no completion gate certified this
delivery", and `qualified` rows written from it.

## Priors checked in the base tree before the census (2026-09-25)

- executor.py:1344-1357 `_run_analysis_phase`: `executed_all = all(...)`
  over zero settled nodes is True, so a bundle whose toolchain has no
  analysis node reports `analysis_status="completed"`; `ledger` is empty,
  so no completion receipt is minted (1373) and no partial envelope is
  written (1427). The same arithmetic holds for a chain whose every node
  is `blocked_unsupported`.
- driver.py:6565 `chainless` needs the executor's status empty AND no
  completion receipt; the two witnesses disagree for an empty chain and
  the permissive reading wins. driver.py:2550 `_achieved` admits
  "completed". driver.py:571-576 `_achieved_word` writes "no completion
  gate certified this delivery" and still returns an achieved word.
- tool_runtime.py:13244 `evaluate_approved_toolchain_completion` may mint a
  `partial` receipt (claims on a failed criterion) without raising; the
  executor then keeps `"completed"` (second shape of the same word).
- tests/agent/test_a_host_word_is_true_of_what_it_read.py:305 (Q10's
  witness) stubs the executor's status as `""` for "a bundle with no
  analysis chain": a hand-built state production did not produce for
  g2-hooh (CONDUCT 4).
- The replay harness Q19/Q22 used (scratch q22/tools/replay_final.py)
  re-derives `analysis_status` from the stream, so it cannot reproduce
  an empty-chain word either: the instrument restates the signer.

## Falsifiers (armed before the census)

- F1: the census finds g2-hooh the only false word: repair it, build the
  parity check, end.
- F2: an archived word does not replay byte-for-byte on the commit that
  produced it: the harness is wrong and nothing downstream of it is
  believed for that goal.
- F3: a word I call false is defensible from the records (say so).
- F4: a repair changes what a settlement word means: `shared:` commit,
  said loudly, for the owner.

## Oracle (independent of the signer, from records only)

- certified: the completion receipt the delivery stands on (the latest
  `analysis_completion_evaluated` of the stream the settlement names) has
  status `passed`.
- `achieved` / `achieved_with_observations` is true only over a certified
  delivery with every declared observable delivered at the goal grain or
  refused with a host verification (charter, settlement-and-terminal-
  records); a goal that declared nothing and carried no chain is counted
  separately, not called false.
- the executor's `analysis_status` is true when "completed" stands on a
  passed receipt of this toolchain, "partial" on a partial one or a
  recorded refusal, "" on a bundle with no chain.
- a `qualified` row is true when its node validated in a run the goal
  recorded AND the goal's word is a true achieved word.

## Census (provider-free, 2026-09-25)

Scope. CUHK /project/xlzhang/jiseung, named roots only (scratch
q24/roots.txt): r8/{base,gaussian,integration,orca,pyscf,xtb},
r9/{base,gaussian,master,orca,pyscf,xtb}, r10/q1-q5, q7-q16, q18-q23
(q3 as q3/goals; excluded r10/q6/goals, r10/q3/{private,plans,sealed*},
r10/q17 -- a running sealed study -- and every r10/m*), and the
2026-09-15..21 campaign directories. 116 ledgers listed, 114 goal
workspaces (2 dry-run evidence copies launched nothing). Fetched without
engine scratch (files <= 8 MB): scratch q24/cuhk, 452 MB. ax41 mirror
2026-09-14 (campaign + research): 195 ledgers. 309 goals, 276 settled.
Tools: scratch q24/tools (inventory.py, classify.py, words.py,
replay_settle.py, find_commit.py, goal_code.py).

Every one of the 343 recorded runs' approval bundles carries a
scientific_toolchain_plan; 12 carry one with zero analysis nodes, 0 carry
none. So the executor's "" (the only word the driver's chainless guard
accepts) was never produced by an archived local run.

Achieved words over no certified delivery (oracle: the delivery's latest
completion receipt is not `passed`, or declared ids undelivered):

| goal | word | final run | executor word | latest completion | archived reason |
|---|---|---|---|---|---|
| r10/q2 g1-hono | achieved | cycle 2, empty chain | completed | partial (cycle 1 run) | "...certified the delivery" |
| r10/q21 g2-hooh | achieved | cycle 2, empty chain | completed | partial (cycle 2 session) | "no completion gate certified this delivery" |
| r9/gaussian g1 | achieved_w_obs | cycle 2, empty chain | completed | partial; 4 IRC ids undelivered | "...certified the delivery" |
| r9/gaussian g3 | achieved_w_obs | cycle 2, empty chain | completed | partial; 4 IRC ids undelivered | "...certified the delivery" |
| r9/master infra-smoke | achieved | cycle 2, empty chain | completed | partial; 3 ids undelivered | "...certified the delivery" |
| r9/master merged-smoke | achieved | cycle 2, empty chain | completed | partial; 2 ids undelivered | "...certified the delivery" |
| ax41 goal-e2-acetone | achieved | cycle 2, empty chain | completed | partial; 3 ids undelivered | "...certified the delivery" |

Six of the seven are R10 Q10's C1 instances ("a run that carried no
analysis chain"). They are all one shape: a bundle whose toolchain has
zero analysis nodes, for which the executor reports "completed".

Also: 13 ax41 achieved words over declared ids never claimed, with a
passed completion (the pre-E4 standing round, h1b, smoke-methyl --
classes repaired before R10; to be confirmed by replay on the base tree).

### Replays (walk mode: the executor's word from the imported tree's own
`_run_analysis_phase` over the archived bundle's toolchain; HOME fenced)

- On the producing commit, 7/7 reproduce the archived word and reasons
  byte for byte: g1-hono e3fdaaca, g2-hooh aeddf64c, merged-smoke
  567f61da, infra-smoke 28a3ea6b (r9/base digest c88a0a72 matched),
  r9 g1 3ec0d656, r9 g3 45d8ca96 (release.json's commits), e2-acetone
  a4f20506. F2 does not fire for the class.
- On the base tree ec41a57c, 7/7 still sign achieved /
  achieved_with_observations. Q10's repair changed only the sentence
  ("cycle 2: workflow completed; no completion gate certified this
  delivery"), never the word.
- The same base tree with Q19/Q22's harness derivation (executor word ""
  when the stream holds no analysis event) opens a recovery for 7/7 --
  which is what Q10's replays reported. The instrument restated the
  signer's input and so showed a repair production never received; Q10's
  witness (test_a_host_word_is_true_of_what_it_read.py:305) stubbed the
  same "" word.

Corrected premise: the brief's "reopened through an empty chain" is
wrong. The class Q10 closed was never closed in production: its six
instances were empty chains, and the guard keys on a word they never
produce. g2-hooh is the seventh instance, not a regression.

### Other signed words (census, base ec41a57c)

- Base replay of all 287 settled goals (walk mode): 7 achieved words
  signed with "no completion gate certified" -- exactly the empty-chain
  class. 34 archived achieved words (ax41 general and standing rounds:
  15 unclaimed outputs, 10 pre-E4 undelivered declarations, 9 unanswered
  verdicts) already replay to recovery_opened: historical, repaired
  before R10. Transitions into achieved words are known repairs (Q16 H2:
  q9 g1, q3 g2; Q19: lad-a0-r2, lad-a1-r1; r8 goal-irc2, r9 g5).
- unreachable_from_evidence: 17 words; 3 hold a refused id also claimed
  -- ino3-r17 and po3-r19 refuse a precision and deliver the value (the
  settlement rule's one legitimate ending); r8/orca goal-ts stands on a
  verification the r8 tree wrote into the stream (Q10's C4, historical).
- Completion receipts: 95 `passed` receipts carry limitation ids. The
  charter has the receipt state them and the settlement word differ; every
  settlement path reads the limitation list (`undelivered_declared_ids`).
  Defensible, not false. 23 sessions ended `complete` over such a receipt:
  the driver documents the terminal word as the session's posture and the
  receipt as the certification; defensible.
- Executor node words: 5 in-session walks settled their first node of a
  kind failed, "the executor and the tool contract have drifted apart";
  the preceding event is `capability_loaded` on the executor's own turn
  (the session host's discovery gate answered "issue the call again").
  False; repaired (d4309cb5).
- Recovery rows: 4 carried "analysis_status": "completed" after an empty
  chain into the next wake (g2-h2co-foreign-saddle c2, q9 g1 c2, r9/xtb
  g3 c2, ax41 po3-r18 c2). False; repaired at the executor (ccd7db8d).
- Qualification: 25 ledger `qualified` rows under the seven false
  achieved words (g1-hono 5, g2-hooh 6, r9 g1 2, g3 3, infra-smoke 3,
  merged-smoke 3, e2-acetone 3). release.json cites r9 g1/g3 and
  e2-acetone, already annotated by the master; none cites g1-hono or
  g2-hooh. The Mac's host store (~/.chemsmart/agent/qualification.jsonl,
  read by `chemsmart agent capabilities`) holds 733 rows, 648 of them a
  test's goal `g` (orca:cpu:sp gets 651 host references) and others from
  unfenced replays of the false-achieved goals (gaussian:cpu:ts from r9
  g1/g3, orca:cpu:ts from g1-hono): the store's path is bound at import,
  so no HOME fence redirects it.

## Repairs (one commit each; witness red before, green after)

- 6d05103d shared: four goal-loop test stand-ins made faithful (a run
  that reports "completed" carries the receipt the walk mints, or the goal
  is woken for what it still owes); green on base and after.
- 3400bb39 driver: certification is read from the run's own receipts
  (chainless = no completion receipt and no analysis node run);
  `_delivery_certified` is the one answer every settlement path calls.
  Replay: 7 archived words move achieved -> recovery_opened, 279 identical.
- ccd7db8d executor: a walk in which no node ran reports "".
- d4309cb5 executor: `_call` answers the host's "schema_loaded" by
  issuing the call again; a node failure quotes the host's reply.
- a3823766 tool_runtime: expression events record their input bindings.

## Live goal g2r -- PRE-REGISTRATION (written before submission)

Question: on the repaired tree, does the g2-hooh route end on the word
its records support, and would the base tree sign achieved over the same
records?

- Task, geometry and envelope byte-identical to R10 Q21's g2-hooh:
  TASK.md sha256 622f1f43d9cc607c..., h2o2.xyz d59a387b922e2634...; ORCA
  cpu, 8 cores, 16 GB, node 1800 s, episode 7200 s, reserve 1800 s, 12
  engine calls, 2 revisions, local dispatch. granted_by
  claude-researcher-q24-owner-delegated (a delegated approval, never a
  human decision). Code: a3823766 (packed from the commit that carries
  this pre-registration). Agent: deepseek-v4-flash-0731 via
  alibaba-token-plan; one run, one observation of that model.
- S1 (host, the word follows the records): over the finished goal's
  records `signed_word_violations` returns [] -- no achieved word over a
  newest completion that is partial or absent while observables were
  declared, and no `qualified` row under a word its records deny.
- S2 (host, the g2-hooh point, if exercised): a cycle whose approved
  toolchain holds no analysis node reports "" and does not settle
  achieved; with budget left it opens a recovery whose row names the
  completion the delivery stands on, and the woken session is told so;
  without budget it returns to the human with that sentence.
- S3 (host): no in-session walk node settles failed "drifted apart".
- F: an achieved word at an empty-chain step; signed_word_violations
  non-empty; a "drifted apart" node reason.
- Neutral: no cycle approves a toolchain with no analysis node (S2 not
  exercised live; reported as the route the Agent took).
- Replay after the goal: its settle steps replayed provider-free on base
  ec41a57c (the executor's word from base's own walk) and on the run
  commit; where S2 is exercised the base is expected to sign achieved.
- Physics bands (R10 Q21's, fixed before either hooh goal; not tuned):
  equilibrium H-O-O-H in [108, 125] deg; dE(trans, 180) in [0.2, 2.5];
  dE(cis, 0) in [5.5, 11]; dE(90 held - eq) in [0.1, 2.0] kcal/mol; where
  delivered on stationary structures dG(trans) in [-0.5, 2.5] and dG(cis)
  in [5.0, 11] kcal/mol. Reference, same level: g1-hooh 120.66 deg, dE
  0.561 / 8.290 / 0.760, dG(TS) -0.079 / 7.953 kcal/mol.
- Not counted: zero provider turns or turn_deadline_exceeded
  (infrastructure). A weak run is reported, never re-rolled.

## Parity checks over the archive (reader against signer, provider-free)

| question | signer | reader | archived divergences | base ec41a57c | repaired |
|---|---|---|---|---|---|
| is the delivery certified? | `_settle` / `_delivery_settlement` | `signed_word_violations` (records only) | 7 (+21 reader blindness, below) | 7 of 271 replayed | 0 of 271 (run path) |
| what did the analysis walk do? | executor word | its run stream's receipts | 12 runs (empty chains) | 12 | 0 (walk says "") |
| which verdicts are unanswered? | `_settle` (run stream alone) | wake / planning path (goal grain) | 0 of 102 run-path settle steps | 0 | 0 |
| why did a node fail? | executor node reason | host reply before it | 5 ("drifted apart" after `capability_loaded`) | reproduced | 0 (d4309cb5) |
| which rows qualify? | `_record_goal_qualification` | the word it follows | 25 rows under 7 false words | same | none written |

Error of my own instrument, found by cross-checking: run over the archive
as signed, `signed_word_violations` flagged 28 goals, 21 of them older
planning-path words whose ledgers name no session stream
(`session_stream_recorded` did not exist yet); it read a run's partial
completion as the newest because it could not see the session's passed
one. Base re-signs all 21 identically and the inventory oracle (which
infers session streams) finds nothing there. The suite's ledgers always
name their sessions; the archive census uses the inventory oracle. The
replayed planning path writes no ledger row, so the repaired tree's "0 of
271" is a statement about the run path.

## Live goal g2r -- ISSUED

- CUHK Slurm 2153691 (slot r10-q24-a), goal g2r, submitted 2026-09-25
  05:29 +08:00 by slot_submit; pre-registration digest e752cdc94d77; code
  commit ed187305, tree digest 2e4edf47999757a8 (426 files, 0
  AppleDouble); workspace holds h2o2.xyz only (ls checked).

## Suite

- tests/agent/test_a_signed_word_stands_on_its_records.py (9 tests):
  on ec41a57c the six witnesses are red (certification at the run path
  after an empty and an all-blocked chain, the executor's word for both
  shapes, a node failed after the host's schema_loaded reply, an
  expression that cannot be replayed from its event) and the three
  controls green; on HEAD all nine green.
- tests/agent on a pristine export of fdf62230: 3186 passed, 0 failed
  (HOME fenced with the program configuration copied in, so no test
  writes the developer's qualification store).
- Full suite on the same export: 23 failed, 4740 passed; the failing set
  equals the round baseline's (test_structures x19, pyscf dispersion x2,
  PyscfSettings, aggregation), none under tests/agent.

## Cluster gate

- Closed at about 05:43 HKT, while g2r (2153691) was in its first cycle
  (it keeps running under Slurm; its records are read when the gate
  reopens). Reopened 07:16 KST; g2r had COMPLETED at 06:19:55 HKT (50 min
  29 s, exit 0:0).

## Live goal g2r -- READ (CUHK 2153691, code ed187305, digest 2e4edf47; prereg e752cdc94d77)

Read from host records: read_goal.py (slot job 2153701, the login node
killed it at its 1 GB cap), the ledger, both session streams, the cycle-1
run stream, the public transcripts. deepseek-v4-flash-0731, one run, one
observation of that model. 2 cycles, 1 revision, 5 engine calls of 12.

- Route. Cycle 1 (approved): opt-eq, ts-d0, ts-d90, ts-d180 (ORCA saddle
  searches seeded at 0, 90 and 180 deg -- the session rejected modred
  because modred results carry no frequency selectors), and scan-dih
  (failed_native: GSTEP could not impose its constraints). The chain
  claimed dg-torsion-0deg 7.953, dg-torsion-180deg 0.345 and
  dg-torsion-90deg 7.952 kcal/mol; completion partial (the scan), the
  host marked falsified_expectation for 180 deg (band 2-7) and 90 deg
  (band 0.5-4.0); recovery opened. Cycle 2 (analysis-only revision): the
  session read that ts-d90's energy equals ts-d0's, measured its
  H-O-O-H at 0.047 deg (a diagnostic declared after the evidence), wrote
  that the delivered 90-deg value was the cis barrier mislabelled,
  claimed the number under a new id, rejected a constrained ts, scan
  interpolation and a constrained opt with their mechanisms, and refused
  dg-torsion-90deg -- first unverified (a selector route), then verified
  through a blocked node of its analysis-only plan. Its completion
  bccbb436 passed with limitation declared_observable:dg-torsion-90deg.
- Settled achieved_with_observations: "the host completion gate
  certified the delivery; ... falsified_expectation:dg-torsion-180deg",
  "delivered in an earlier cycle: dg-torsion-90deg (delivered in cycle
  1)", the four findings, the uncertainties; 4 `qualified` rows (orca
  opt; orca ts x3).
- Against the pre-registration: S1 met as written (the reader returned
  []); S2 not exercised -- no engine cycle approved an empty toolchain
  (Neutral, as pre-registered); R2 was exercised live instead: the
  analysis-only walk over one blocked node reported "" (the base says
  "completed"); S3 met (no "drifted apart"); F not triggered as written.
- ERROR (found beyond the pre-registration): the word is false. It
  certifies dg-torsion-90deg as delivered from the cycle-1 claim, over
  the goal's own later, host-verified refusal, over the limitation on the
  very certificate it cites, and it drops the cycle-1 anomaly on that
  number. The number it certifies is the cis barrier (7.95 kcal/mol)
  presented as the 90-degree free energy; physically, G at a held 90 deg
  structure is not defined, as the session said. My pre-registered
  reader passed it: it asked only whether the newest completion passed.
  The base ec41a57c and the run commit sign the archived word byte for
  byte (replayed; cycle 1's settle step also identical on both).
- Physics (Q21's bands, fixed before either hooh goal): eq H-O-O-H
  120.66 deg [108, 125] met; dE(trans) 0.560 [0.2, 2.5] met; dE(cis)
  8.290 [5.5, 11] met; dE(90 held) not computed (no route held 90 deg);
  dG(trans) 0.345 [-0.5, 2.5] met (a first-order saddle, -245.8 cm-1);
  dG(cis) 7.953 [5.0, 11] met (-610.8 cm-1). G(eq) -151.419966 Eh and
  G(cis saddle) -151.407292 Eh equal g1-hooh's to all printed digits
  (two independent runs). dG(trans) differs from g1-hooh's -0.079: same
  treatment (RRHO, alpha 4, unscaled), same dE; g1-hooh's trans structure
  (an opt that stopped on the saddle) carries +0.000228 Eh ZPE and
  +5.5e-6 Eh/K entropy against g2r's saddle search. Unresolved here.

## Repairs found by the live goal (witness red before, green after)

- bdd1333e driver: a goal settled on a verified refusal carries in its
  word what the rest of its delivery found (10 of 17 archived
  unreachable words omitted anomalies, falsified expectations or
  findings their delivery held).
- 41f607d4 driver (LOUD, for the owner): a declared observable's latest
  typed word governs it -- a verified refusal supersedes the claim an
  earlier cycle made; an id declared with a tolerance is excluded (a
  refusal of a claimed requirement is a refused precision). A first draft
  without that exclusion wrote a false "supersedes" clause on ax41
  po3-r19; the census replay caught it before the commit.
- g2r's final settle step on 41f607d4: unreachable_from_evidence,
  "dg-torsion-90deg -- ... [analysis node 'dg90-producer-blocked' is
  declared blocked_unsupported ...]; this refusal supersedes the claim
  cycle 1 rendered under this id (7.952416658321963 kcal/mol)", then the
  delivered part (falsified_expectation:dg-torsion-180deg, the four
  findings, the uncertainties). The widened reader flags the archived
  word and passes the repaired loop witness.
- 287 archived settle steps on 41f607d4: no word moves; 16 refusal words
  gain their delivered part's lines; 0 superseding clauses; the reader
  finds 0 violations in 271 replayed ledgers.
- Consequence for qualification (owner's call): the repaired word writes
  no `qualified` rows; g2r's 4 rows (validated opt and ts nodes) were
  written under the false achieved word and stand in its ledger and the
  CUHK host store.

## Status

- step 0: brief read; base verified; CONDUCT, RSL, charter topics, Q10,
  Q16, Q19, Q21, Q22 merges and records read; CUHK gate open.
- step 1 (census of achieved words, empty-chain class, producing-commit
  and base replays): done.
- step 2 (repairs R1, R2, R4, expression bindings): committed.
- step 3: live goal g2r pre-registered, packed (ed187305) and issued as
  CUHK Slurm 2153691.
- step 4: gates on fdf62230 done (tests/agent green; full suite = the
  round baseline); r10-integration has not moved since ec41a57c.
- step 5: g2r read from host records and replayed (above); two repairs it
  found committed (bdd1333e, 41f607d4).
- step 6: r10-integration had moved to 05d556d7 (R10 Q23's merge);
  merged at 23cbf03b with no conflict. On the merged tree: tests/agent
  3203 passed, 0 failed; g2r's final settle step replays
  unreachable_from_evidence with the superseded claim named; the 287
  archived settle steps are identical to the pre-merge repaired replay;
  0 reader violations; 0 achieved words with an uncertified reason.
