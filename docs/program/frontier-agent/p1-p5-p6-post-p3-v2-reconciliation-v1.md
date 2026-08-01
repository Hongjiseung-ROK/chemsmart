# P1/P5/P6 post-P3 v2 evidence reconciliation v1

## Status and purpose

This append-only reconciliation records the later P3 v2 provider observation
without editing the frozen P1 evidence record, P3 v1 record, P5
preregistration/close, or P6 no-go package. It is a chronology and
claim-scope correction, not a P5 trial, evaluation, training, replication,
paper, release, or SOTA result.

P3 v2 completed later than the frozen P5/P6 closes. Their statements that no
provider execution existed at their respective close times therefore remain
true as time-scoped historical statements. V2 does not change their evidence
requirements or decisions.

## Later observation and permitted interpretation

The hash-linked [P3 v2 receipt](receipts/p3-live-provider-capability-v2.json)
records one direct, isolated, P1-pinned `deepseek-v4-pro` request. It had an
HTTP-200 response, a local structural `tool_calls` finish, one correctly named
call with exact locally valid fixed-schema arguments, 2,180 ms elapsed time,
456 prompt/91 completion tokens, USD 0.00055506 recorded cost upper bound,
and zero dispatches, engines, schedulers, or retries.

It supports only that one redacted provider-surface observation. The v1-v2
contrast is consistent with the output-ceiling hypothesis, but it cannot show
that the 64-to-256 change caused the difference: there is one observation per
envelope, no replication, and no retained semantic payload for diagnosis.

## Reconciled gate state

| Surface | Current state | Reason it remains bounded |
| --- | --- | --- |
| P1 direct endpoint/config surface | Qualified narrow observation | V2 pins one direct specimen but does not exercise active configuration canonicalization, normal provider adapter, tool loop, or CLI. P1 allowance remains historical. |
| P3 v1 historical strict result | Red, unchanged | V1 remains an exhausted 64-token blocked observation. It is not repaired or reclassified. |
| P3 fixture/scientific fault gates | Qualified/unresolved, unchanged | V2 is neither a `FaultTrace` nor a deterministic grade or chemistry task. |
| P4-HA-01 / P4-CH-01 | Red/unresolved | No active executor-side approval consumption or chemical-result artifact was implemented or exercised. |
| P5-RG-01 and evaluation eligibility | Red / false | One direct harmless call does not establish active-path, paired, held-out, execution, scientific, or study capability. No trial was created. |
| P5-G4 / P5-G5 | Blocked | There are still no complete paired trial receipts, intervals, comparator evidence, or independent rerun inputs. |
| P6 results/SOTA/replication/training/publication | No-go unchanged | There is no controlled result, clean replication, eligible trace set, or separate external authority. |

## Claim-evidence ledger

| ID | Claim type | Statement | Required evidence | Status |
| --- | --- | --- | --- | --- |
| P1-V2-C1 | provider observation | One pinned direct endpoint returned the harmless fixed function record within v2's one-call envelope. | V2 receipt and deterministic receipt validation. | Supported narrowly. |
| P1-V2-C2 | causal inference | The higher output ceiling caused v2's valid record. | Replicated controlled contrasts and retained diagnostic evidence. | Unresolved. |
| P5-V2-C1 | evaluation inference | V2 clears provider capability or makes the 2 × 2 × 2 study eligible. | Active-path and identical-condition evidence, external held-out custody, executor/chemical gates, and all preregistered trials. | Rejected as a current inference. |
| P6-V2-C1 | paper/SOTA inference | V2 supports results, SOTA, replication, training, or publication. | Complete P5 study, named comparator, intervals, clean replication, training checklist, and separate authority. | Rejected as a current inference. |
| P56-V2-C2 | chronology observation | Frozen P5/P6 no-provider statements remain true at their own close times. | Their close timestamps/hashes plus the later v2 receipt. | Supported time-scoped. |

## Failure ledger

| ID | Failure | Hypothesis | Minimal change | Evidence and result | Limitation | Rollback boundary |
| --- | --- | --- | --- | --- | --- | --- |
| P1V2-F1 | Frozen P1/P5/P6 artifacts predate v2. | Editing historical sources would erase provenance and break hashes. | Add this hash-linked reconciliation only. | Later v2 timestamp/receipt plus unchanged frozen hashes; chronology is preserved. | A chronology record cannot create a study outcome. | Delete only this delta if invalid; preserve frozen artifacts. |
| P1V2-F2 | A valid direct function record could be overread as active-agent or chemical capability. | Structural validity is not execution, domain correctness, or reliability. | Keep all active-path/P4/P5/P6 gates explicit and red. | V2 has zero dispatches and no trials/chemical artifacts. | It cannot diagnose or reproduce v1's failure mechanism. | Downgrade to unresolved if receipt/hash validation fails; do not reinterpret raw content. |
| P1V2-F3 | A later provider call might be mistaken for current quota evidence. | Historical P1 balance and one cost upper bound do not establish current allowance. | State no refreshed balance or future-spend claim. | P1 and v2 receipt fields are time-scoped. | No current account/usage measurement is made here. | A new quota claim needs a separately bounded usage probe. |

## Decision ledger

| ID | Decision | Evidence basis | Rollback boundary |
| --- | --- | --- | --- |
| P3-V2-D4 | Close v2 after its sole response; prohibit replay or parameter adjustment. | `request_count=1`, `retry_count=0`, completed v2 receipt. | A new measurement needs a new frozen protocol; v1/v2 history stays immutable. |
| P3-V2-D5 | Classify v2 only as a non-executing structural provider observation. | Exact structural booleans, budget fields, and zero-dispatch fields. | If receipt/hash validation fails, downgrade to unresolved rather than reinterpret content. |
| P3-V2-D6 | Reject causal attribution to the 64-to-256 change. | One unreplicated contrast and no retained semantic payload. | Keep the limitation visible in all downstream references. |
| P1-V2-D1 | Add a hash-linked P1 reconciliation without refreshing quota or modifying P1/v1. | P1/v1 linkage and v2 receipt. | Delete only this reconciliation if invalid; preserve frozen records. |
| P56-V2-D1 | Preserve frozen P5/P6 no-go artifacts and record v2 only as later chronology. | P5/P6 earlier closes; v2 zero execution and no trial receipt. | Delete only this delta; never edit preregistration/no-go receipts. |
| P56-V2-D2 | Retain evaluation, training, replication, and release no-go decisions. | Explicit non-promotion boundary and absent P5/P6 evidence. | A future decision needs independently evidenced, separately authorized work. |

## Supported, qualified, unresolved, and rejected

- Supported: the receipt-scoped direct provider observation and the
  time-scoped historical interpretation of P5/P6 records.
- Qualified: the single observation is limited to its model label, endpoint
  identity, sanitized prompt, fixed schema, and 256-token envelope; P1's
  allowance remains historical.
- Unresolved: v1 failure cause/reproducibility; active provider, tool-loop,
  CLI, approval/executor, and science boundaries; P5 outcomes; clean
  replication; training; paper/release readiness; and any SOTA comparison.
- Rejected: reclassifying/retrying v1; claiming causality from the ceiling
  contrast; clearing P5 eligibility; or promoting v2 into results, SOTA,
  replication, training, publication, or current quota evidence.

## Next safe action

Keep the simplest frozen configuration and all P5/P6 paths off. A material
next step requires a separately authorized and preregistered proposal for
active-path, externally held-out evaluation; it must not reuse or replay v2.
