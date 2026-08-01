# P3 v2 live-provider close delta v1

## Status and result

Closed on 2026-07-31 after exactly one permitted request. The separate v2
specimen observed a structurally valid call to the fixed harmless function:
HTTP 200, `finish_reason=tool_calls`, one correctly named call, exact
schema-valid arguments, no retained reasoning content, and zero dispatches.
It used 456 prompt and 91 completion tokens, took 2,180 ms, and has a
conservative recorded cost upper bound of USD 0.00055506. The full response,
arguments, prompt, headers, credentials, URLs, and error text were not
retained.

This closes only v2's predeclared direct-endpoint observation. It does not
rewrite the frozen v1 blocked receipt, the frozen P3 page, the fixture-only
single-agent reference, or any P1/P5/P6 historical artifact.

## Inputs and artifact chain

| Input or artifact | Role |
| --- | --- |
| [P3 v2 protocol](p3-live-deepseek-capability-protocol-v2.md) | Pre-call one-variable hypothesis, authority, ceilings, and red gates. |
| [P3 v2 pre-call readiness receipt](receipts/p3-v2-pre-call-readiness-v1.json) | Frozen v1/P1 pinning, 12 focused offline checks, dry run, and credential-only preflight. |
| [P3 v2 provider receipt](receipts/p3-live-provider-capability-v2.json) | Sanitized single-call observation and source hashes. |
| [P3 v2 receipt validator](../../../scripts/review/validate_frontier_live_provider_v2.py) | Deterministic verification of current source hashes, P1/v1 linkage, ceilings, redaction, and completed-path semantics. |
| Frozen v1 receipt | Historical red result; its exact SHA-256 and six source artifacts were checked before v2 profile loading. |

## Gate close

| Gate | Result | Evidence boundary |
| --- | --- | --- |
| V2-G1 immutable delta | Passed | The focused request-contract test proves v1/v2 equality after replacing only `max_tokens` 64 with 256. |
| V2-G2 budget and credential | Passed narrowly | The no-request dry run and in-process credential preflight passed; historic P1 allowance remains historical, not a current balance assertion. |
| V2-G3 non-execution | Passed | Receipt records zero tool dispatches, engines, schedulers, and follow-up requests. |
| V2-G4 structural observation | Passed | One response met the exact returned-model, tool, argument, usage, cost, and timing checks. |
| V2-G5 claim discipline | Passed only as a documentation boundary | The result is kept outside fault scoring, active-provider behavior, chemistry, P5 trials, paper, training, replication, and SOTA. |

The frozen v1 P3-G5 red result remains historically red. V2-G4 does **not**
make the frozen fixture-only P3-G2/P3-G3 qualified gates into observed agent
competence or scientific validation gates.

## Phase-close validation

| Invocation | Result | Classification |
| --- | --- | --- |
| Focused v2 harness + receipt tests | `12 passed in 0.30s` | Offline contract, source-pinning, tamper, and receipt-shape evidence only. |
| v2 dry run | `preflight_ready`, no request | P1/v1 input and fixed envelope check. |
| v2 credential-only preflight | `preflight_ready`, no request | In-process alias resolution only; value not retained. |
| v2 direct request | One request, no retry | Direct-provider structural observation only. |
| v2 receipt validator | Passed | Local provenance/redaction/ceiling/semantic check only. |

No broad test suite, chemistry engine, scheduler, CLI dispatch, dependency
change, commit, push, or publication action was run.

## Claim-evidence ledger

| ID | Claim type | Statement | Evidence | Status |
| --- | --- | --- | --- | --- |
| P3-V2-C1 | protocol observation | The v2 request contract changed only its output ceiling from v1. | Frozen-source comparison in the focused test and v2 source hashes. | Supported. |
| P3-V2-C2 | provider observation | One P1-pinned direct endpoint returned the exact harmless function record within the v2 envelope. | [Redacted v2 receipt](receipts/p3-live-provider-capability-v2.json) and validator. | Supported narrowly. |
| P3-V2-C3 | provider inference | The active ChemSmart provider/tool-loop reliably forms or executes valid tool calls. | Active-path, repeated, and execution evidence. | Unresolved. |
| P3-V2-C4 | scientific inference | The agent is chemically reliable, decomposes tasks better, or is SOTA-worthy. | Held-out P5 outcomes, native/archived science artifacts, controlled comparison, and replication. | Unresolved. |
| P3-V2-C5 | historical correction | V1's structural red result should be relabeled green. | A changed v1 receipt/protocol. | Rejected; v1 remains a red historical observation. |

## Failure and decision ledger

| ID | Failure or decision | Hypothesis / minimal action | Evidence / result | Limitation and rollback boundary |
| --- | --- | --- | --- | --- |
| P3-V2-F1 | V1 reached a 64-token ceiling with invalid arguments. | Test only the output ceiling at 256 in a separately named one-call protocol. | V2 passed the strict structural check at 91 completion tokens. | It does not identify v1's mechanism or authorize any repeated/tuned request. Stop after this receipt. |
| P3-V2-F2 | Pre-call audit found that a malformed green receipt and substituted v1 input could be accepted. | Add completed-path semantic checks plus exact v1 receipt/source pinning. | The 12 focused checks reject both tamper classes before the live call. | Local checks cannot prove external behavior; preserve hashes and do not change v1. |
| P3-V2-D1 | Preserve direct specimen isolation. | Do not pass the returned call to the normal tool loop or any dispatcher. | All non-execution counters are zero. | No tool-execution evidence exists; delete only v2 artifacts to roll back. |
| P3-V2-D2 | Do not treat completion as SOTA, evaluation, or paper evidence. | Add append-only P1/P5/P6 reconciliation with red gates explicit. | V2 is a one-case provider-surface observation, not a trial. | Any promotion requires new held-out, active-path, science, replication, and authority evidence. |

## Supported, qualified, unresolved, and rejected

- Supported: the fixed direct-endpoint v2 structural observation and all
  non-execution, token, time, cost, redaction, and source-pin facts recorded
  in its receipt.
- Qualified: disabled thinking was requested; no reasoning content was
  retained, while the provider did not report a reasoning-token count. The P1
  allowance is a prior observation only.
- Unresolved: normal provider/tool-loop behavior, tool execution, CLI schema
  compatibility, scientific task performance, all P3 fault handling beyond
  fixtures, P5 ablation, replication, training, paper readiness, release, and
  SOTA.
- Rejected: any claim that a single harmless tool-schema response validates a
  chemical calculation, agent safety in deployment, a component effect, or a
  comparative result.

## Next safe action

Keep the provider and all P5/P6 paths blocked. The next material step would
need a separately authorized, preregistered active-path and held-out
evaluation proposal; no further v2 requests are permitted.
