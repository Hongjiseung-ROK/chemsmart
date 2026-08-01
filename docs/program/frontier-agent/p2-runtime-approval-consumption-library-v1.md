# P2C Runtime approval-consumption library boundary v1

## Status

Closed as a deterministic, library-only contract after the focused checks
recorded in its receipt. It does not alter Runtime V2 event schemas, reducer,
controller, lifecycle, Click tree, tool loop, command executor, provider
configuration, or any engine/scheduler path. A passing library verdict is not
an execution authorization or proof that the active executor consumes approval.

## Objective

Extract the refusal-only portion of the P2B-v2 fixture into a typed Runtime
module. Given an existing exact ApprovalRequest, typed terminal records, a
digest-only outer invocation, an archived-shaped preflight receipt, and a
current schema document, it must return an allowed or denied verdict without
persisting, consuming, triggering, or adapting any action.

## Inputs

| Input | Required use |
| --- | --- |
| Frozen [P2 Runtime receipt](receipts/p2-runtime-contracts.json) | Preserve the V2 optional-event and no-CLI-change boundary. |
| Frozen [P2B-v2 fixture receipt](receipts/p2-executor-binding-v2-fixture-v1.json) | Reuse only its refusal invariants; do not edit the fixture. |
| Typed Runtime approval request, resolutions, and invalidations | Bind identity, user authority, ordering, expiry, and invalidation. |
| CommandPreflightReceipt | Recompute one canonical digest and require schema/parser/semantic/intent gates. |
| Current full Click-schema document | Recompute and verify declared schema metadata rather than trust a supplied hash. |

## Tools and authority

- Allowed: immutable typed records, local JSON hashing, one in-process schema
  document build at test scope, static import checks, and focused offline tests.
- Prohibited: CLI invocations, command text, external hooks, persistence,
  process launching, provider requests, engines, schedulers, installs, commits,
  pushes, and changes to active Runtime or CLI paths.

## Budget

| Resource | Ceiling | Observed |
| --- | ---: | ---: |
| In-process full-schema document builds | 1 test fixture scope | 1 |
| Focused offline test invocations | 2 | 2 |
| Direct receipt-validator invocations | 1 | 1 |
| CLI, provider, command-executor, engine, scheduler, or network calls | 0 | 0 |
| Active Runtime/CLI/event-schema modifications | 0 | 0 |

## Artifacts

- chemsmart/agent/runtime/approval_consumption.py: isolated pure evaluator with
  no raw command field or action surface.
- tests/agent/runtime/test_approval_consumption.py: exact positive and
  fail-closed negative matrix.
- This document, its receipt, and a dedicated source-hash/non-wiring validator.

## Contract

ExecutorInvocation carries only an approval identifier, approval-binding digest,
tool name, command digest, canonical preflight-receipt digest, full-schema
digest, target, timestamps, and literal library_only mode. Its proposal binding
is derived before the later observed_at fact, so an outer decision can precede
the observation while timing is still checked separately.

evaluate_approval_consumption requires all of the following before returning
approved_library_only:

1. The outer invocation exactly matches the base approval identifier, binding,
   tool, command digest, target, and approval window.
2. The receipt has the known schema version, a valid command digest, and ok
   parser, semantic, and intent gates; its canonical digest is in the base
   request and equals the outer pin.
3. The current schema metadata digest recomputes from the supplied body and
   equals the outer schema pin.
4. Exactly one matching base resolution and one matching outer resolution
   exist; both are user-approved and correctly ordered.
5. The invocation is before expiry and no matching invalidation predates or
   coincides with it.

The evaluator owns no mutable one-shot ledger. It cannot make a record durable
across a restart, resolve races across processes, or cause a real tool call.

## Gates

| Gate | Status | Boundary |
| --- | --- | --- |
| P2C-G1 exact approval and invocation binding | Passed in library tests | Digest, tool, target, and timing drifts fail closed. |
| P2C-G2 preflight and schema verification | Passed in library tests | Receipt gates/digest and recomputed schema metadata must agree. |
| P2C-G3 user lineage/invalidation refusal | Passed in library tests | Missing, duplicate, denied, non-user, stale, and invalidated records fail closed. |
| P2C-G4 no active-path wiring | Passed by static guard | The module is not imported by active agent code. |
| P2C-G5 durable executor enforcement | Unresolved | No persistence, atomic consumption, adapter, process path, or execution exercise exists. |
| P4-HA-01 executor-side approval consumption | Red/unresolved | A pure library verdict is not active executor enforcement. |
| P3-P6 scientific/evaluation/release gates | Red/unchanged | This increment provides no provider, chemistry, held-out, replication, paper, or SOTA evidence. |

## Failure, hypothesis, and minimal-change ledger

| ID | Failure | Hypothesis | Minimal change | Evidence | Result | Limitation | Rollback boundary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P2C-F1 | P2B-v2's stronger approval/preflight/schema check was fixture-only. | A pure Runtime library can preserve refusal invariants without active-path edits. | Add one isolated evaluator and deterministic test matrix. | Exact hash/receipt/schema/terminal-record fixtures. | Declared mismatches return refusal verdicts. | No active caller invokes the evaluator. | Remove only P2C artifacts if unsuitable; leave P2/P2B frozen artifacts intact. |
| P2C-F2 | A supplied schema digest alone does not prove its body is current. | Recomputing metadata over the schema body catches drift. | Require local schema metadata recomputation. | Content-change and mismatched-pin refusal cases. | Schema drift is refused at library scope. | It does not bind all future runtime behavior. | Replace only with a reviewed versioned schema-binding contract. |
| P2C-F3 | In-memory evaluation cannot provide durable, atomic, cross-process one-shot consumption. | Pretending otherwise would create a false executor-safety claim. | Deliberately omit persistence and state mutation. | Source non-wiring guard and lack of a consumption event. | P2C-G5/P4-HA-01 remain unresolved/red. | A caller could re-evaluate after a restart. | Require separate persistence/migration/concurrency design before active integration. |
| P2C-F4 | The first focused test bound observed_at into the outer decision and simultaneously replaced the outer pin in its schema-drift case. | A proposed surface must exclude the later observation, and schema drift must be tested after the existing outer approval. | Exclude observed_at from the outer digest; retain the original outer pin while changing only the current schema body. | One focused run: 30 passed, 2 failed. | The corrected contract can test chronology and post-approval schema drift independently. | This is still only a pure evaluator. | Revert only this correction if a reviewed future contract explicitly binds a different observation model. |

## Blockers

- An active path would need a versioned persistent consumption record, atomic
  race behavior, verified user-approval provenance, and a typed preflight
  adapter before any action boundary can be considered.
- The current tool loop lacks the complete typed preflight identity needed to
  call this evaluator before a tool-start record or registry call. Wiring it
  now would silently change behavior and is outside this increment.
- This library cannot resolve P4-CH-01, P4-ST-01, P4-RT-02, or any P5/P6 gate.

## Phase-close validation

The close runs only focused library tests, then the dedicated receipt validator.
They validate a deterministic non-executing boundary; they do not validate a
CLI, product, provider, engine, chemistry result, held-out study, replication,
paper, training, release, or SOTA claim.

    env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/runtime/test_approval_consumption.py -q
    env -u PYTHONPATH conda run --no-capture-output -n chemsmart python scripts/review/validate_frontier_p2_runtime_approval_consumption_library.py --repo .

## Claim-evidence ledger

| ID | Claim type | Statement | Status |
| --- | --- | --- | --- |
| P2C-C1 | code observation | The isolated evaluator returns a library-only verdict only after declared hashes, receipt gates, schema, user lineage, time, and invalidation facts agree. | Supported by focused deterministic tests only. |
| P2C-C2 | code observation | Enumerated invalid inputs return a refusal verdict and create no execution surface. | Supported by focused deterministic tests and static guard only. |
| P2C-C3 | inference | The active executor durably consumes approval before acting. | Rejected; no active wiring, persistence, or action path exists. |
| P2C-C4 | inference | This change authorizes an engine, scheduler, provider, command, chemistry result, held-out evaluation, or SOTA claim. | Rejected. |
| P2C-C5 | unresolved uncertainty | A durable concurrent approval-consumption path is safe. | Unresolved. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P2C-D1 | Keep this module unimported by active agent code. | Existing active paths lack a complete typed preflight identity and persistent consumption model. | Consider wiring only after separate migration and active-path design approval. |
| P2C-D2 | Return a verdict rather than mutate a ledger. | A transient one-shot marker would overstate persistence and restart safety. | Replace only with durable reviewed storage and concurrency controls. |
| P2C-D3 | Bind the full schema body through recomputed metadata. | A supplied digest alone is not provenance. | Evolve only with a reviewed versioned schema contract. |
| P2C-D4 | Preserve all external/scientific gates. | No provider, engine, archive, held-out, or replication result was produced. | Require separately typed evidence for each gate. |
