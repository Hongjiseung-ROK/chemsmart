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

## Status

- step 0: brief read; base verified; CONDUCT, RSL, charter topics, Q10,
  Q16, Q19, Q21, Q22 merges and records read; CUHK gate open.
- step 1 (census of achieved words, empty-chain class, producing-commit
  and base replays): done.
