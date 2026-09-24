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

## Status

- step 0: brief read; base verified; CONDUCT, RSL, charter topics, Q10,
  Q16, Q19, Q21, Q22 merges and records read; CUHK gate open.
