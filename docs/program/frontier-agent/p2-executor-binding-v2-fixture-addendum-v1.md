# P2B-v2 executor approval-lineage fixture addendum

## Status

Closed fixture-only prospective protocol. This append-only P2B-v2 increment
strengthens the already frozen P2B-v1 fixture without changing Runtime V2,
Click semantics, the tool loop, or the command-execution path. It does not
authorize a real command, a chemistry engine, a scheduler, a provider, or an
external evaluation.

## Objective

Specify and test a narrower future executor boundary in which an accepted,
archived-shaped `CommandPreflightReceipt`, a current full Click-schema digest,
and a typed Runtime V2 user-approval lineage must all agree before a test-local
fake-dispatch counter may increment once. The purpose is refusal coverage and
provenance clarity, not a claim that the active executor enforces anything.

## Inputs

| Input | Required use |
| --- | --- |
| Frozen [P2B-v1 receipt](receipts/p2-executor-binding-fixture-protocol-v1.json) | Preserve the original v1 hashes and its unresolved real-executor gate. |
| Frozen [P2 receipt](receipts/p2-runtime-contracts.json) | Keep Runtime V2 additive and preserve the no-CLI-semantic-change boundary. |
| Frozen [P4 harness finding](reviews/p4-harness-findings-v1.json) | Address only the prospective lineage detail behind P4-HA-01. |
| Typed `ApprovalRequest`, `ApprovalResolution`, and `ApprovalInvalidation` | Supply immutable base-binding, actor, resolution, and invalidation facts. |
| `CommandPreflightReceipt` and current `schema_with_metadata(build_chemsmart_cli_schema())` | Supply an in-memory/archived-shaped receipt digest and a verified full-schema digest; neither is a command execution. |

## Tools and authority

- Allowed: deterministic dataclasses, typed Runtime V2 records, local receipt
  hashing, one live-derived schema document at fixture scope, fake-dispatch
  counters, static import checks, source-hash validation, and focused tests.
- Not allowed: editing P2B-v1, Runtime V2, the Click tree, the CLI registry,
  tool catalog, command executor, provider configuration, engine/scheduler
  adapters, or P3–P6 evidence. No credentials, API calls, command strings,
  process handles, engines, schedulers, installs, commits, or pushes enter the
  fixture.

## Budget

| Resource | Ceiling | Observed |
| --- | ---: | ---: |
| Live-derived Click schema documents | 1 fixture scope | 1 fixture scope |
| Valid test-local fake-dispatch observations | 1 | 1 |
| Invalid fixture fake-dispatch observations | 0 | 0 |
| Real command, engine, scheduler, provider, or external-evaluation calls | 0 | 0 |
| Active Runtime/CLI/tool/executor wiring changes | 0 | 0 |

## Artifacts

- An unwired `frontier_executor_binding_v2` module that accepts hashes and
  typed records only.
- A focused test matrix covering accepted lineage, changed request surfaces,
  missing/duplicate/denied/non-user resolutions, time ordering, invalidation,
  receipt gates and digest drift, target drift, invocation/schema drift, and
  one-shot consumption.
- This addendum, a redacted receipt, and a dedicated offline integrity
  validator. The P2B-v1 module, tests, document, validator, and receipt remain
  hash-pinned inputs rather than edited artifacts.

## Fixture contract

`FixtureExecutorBindingV2` extends the existing immutable `ApprovalRequest`
only outside active Runtime V2. It records the existing request binding hash,
command digest, exact preflight digest set, one canonical preflight-receipt
digest, current full Click-schema digest, target, and approval window.

The ledger accepts an ordered immutable `FixtureApprovalLineageV2` containing
typed base resolutions and invalidations plus fixture-only outer resolutions.
It requires exactly one user-approved base resolution and exactly one
user-approved outer resolution. Both must occur after request creation and
before expiry; the invocation must follow both. A matching invalidation at or
before the invocation, duplicated terminal record, non-user actor, malformed
schema metadata, mismatched receipt, mismatched command/target/schema, or
second consumption fails closed.

The receipt digest uses canonical JSON over `CommandPreflightReceipt.to_dict()`
inside this fixture module. It is intentionally not added to production
preflight code. The receipt must have the known schema version and `ok` parser,
semantic, and intent gates. This is distinct from the inspect-tool digest:
the fixture binds the receipt's canonical command digest rather than assuming
two normalization paths are interchangeable.

## Gates

| Gate | Current status | Evidence boundary |
| --- | --- | --- |
| P2B2-G1 canonical preflight binding | Passed in fixture | A valid receipt is canonical-hashed, request-bound, and checked against the invocation. |
| P2B2-G2 typed user lineage and timing | Passed in fixture | Runtime V2 base approval/invalidation records and a fixture outer resolution fail closed on the declared ordering/actor cases. |
| P2B2-G3 one-shot refusal contract | Passed in fixture | One exact test-local fake observation occurs; all negative fixtures record zero. |
| P2B2-G4 active-path preservation | Passed narrowly | A static guard finds no import in the active agent tree; no active source is edited. |
| P2B2-G5 real executor enforcement | Unresolved | No durable ledger, race handling, user-approval UI, active dispatch integration, process invocation, or engine action exists. |

## Failure, hypothesis, and minimal change ledger

| ID | Failure | Hypothesis | Minimal change | Evidence | Result | Limitation | Rollback boundary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P2B2-F1 | P2B-v1 binds synthetic receipt hashes but cannot establish that a typed preflight receipt's canonical digest, command digest, and gates agree with an approval request. | A fixture should bind one archived-shaped receipt and refuse any unsuitable or substituted receipt before fake dispatch. | Add an unwired v2 receipt-hash checker only. | Direct receipt-shape fixtures and focused deterministic cases. | Valid receipt path is accepted only after exact digest/gate/command agreement; declared drifts refuse. | It is not a production receipt-verification API or a command preflight. | Delete this v2 fixture module/addendum if unsuitable; do not alter the frozen v1 protocol. |
| P2B2-F2 | P2B-v1's fixture resolution does not prove actor provenance, typed Runtime V2 timing, invalidation history, or duplicate terminal refusal. | A future executor needs user-only, exact, ordered lineage facts in addition to an outer binding. | Add an in-memory lineage evaluator that consumes no dispatcher. | Typed `ApprovalResolution`/`ApprovalInvalidation` fixtures and zero-counter refusals. | Non-user, duplicate, stale, invalidated, and mistimed lineages fail closed. | No persistent or cross-process atomic consumption is exercised. | Any active lineage storage or executor migration needs separate design, authority, and non-engine integration tests. |
| P2B2-F3 | A supplied 64-character schema string alone does not prove it was derived from current schema content. | The fixture should recompute declared metadata over the supplied schema body and compare it with both invocation and binding pins. | Validate a copied in-memory schema document locally; do not change Click. | A synthetic copied-schema content change produces a distinct verified digest and refusal. | Content drift is caught in the fixture. | It does not prove all non-schema runtime behavior or active enforcement. | Retire only this fixture check if a future versioned executor contract supersedes it. |
| P2B2-F4 | The first closed receipt-wrapper invocation rejected its own phase-close `command` field as prohibited raw content before evaluating the fixture contract. | Validation provenance commands are safe local check identifiers, whereas raw execution command strings must remain prohibited. | Remove only the generic `command` key from the receipt-field denylist; retain `command_string`, secret, prompt, response, argument, and error-text exclusions. | One focused wrapper failure with a generic redaction-field error and review of the receipt schema. | The validator can distinguish permitted validation provenance from prohibited raw execution content. | This repair validates receipt shape only; it does not exercise a command executor. | Restore the stricter key rule only if phase-close evidence moves to a dedicated safe field without breaking receipt provenance. |

## Blockers

- P4-HA-01 remains unresolved at the real executor boundary. A production path
  requires a separately approved versioned data-model migration, durable atomic
  consumption, user-facing approval provenance, concurrency/race review,
  active-path integration, and non-engine tests before any engine-facing work.
- P4-CH-01, P4-ST-01, and P4-RT-02 still require respectively authorized
  native/archived chemistry evidence, controlled repeated held-out outcomes,
  and independent held-out custody. This fixture supplies none of those.
- P1 provider, P3 capability, P5 ablation, and P6 replication/training/paper/
  release/SOTA gates retain their recorded status. No claim is promoted.

## Phase-close validation

Run each focused command once after the protocol artifacts are complete. They
validate only the prospective fixture and its receipt integrity; they do not
establish Runtime, product, scientific, release, replication, training, paper,
or SOTA readiness.

```bash
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/harness/test_frontier_executor_binding_v2.py -q
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/harness/test_frontier_p2_executor_binding_v2_fixture.py -q
```

## Claim-evidence ledger

| ID | Claim type | Statement | Status |
| --- | --- | --- | --- |
| P2B2-C1 | source observation | The P2B-v2 fixture derives an outer binding from a typed request and a canonical acceptable receipt without active-path imports. | Supported by source/static guard and focused fixture tests only. |
| P2B2-C2 | code observation | The declared receipt, lineage, timing, schema, target, and reuse failures leave the fake counter at zero. | Supported by deterministic fixture cases only. |
| P2B2-C3 | inference | The active executor now consumes a durable approval before dispatch. | Rejected; no active integration exists. |
| P2B2-C4 | inference | This fixture authorizes a command, provider, engine, scheduler, chemical result, or held-out evaluation. | Rejected. |
| P2B2-C5 | unresolved uncertainty | A real approval-consumption path is safe under persistence and concurrency. | Unresolved. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P2B2-D1 | Keep the v2 binding outside `ApprovalRequest`. | Adding a field would alter historical request-binding digests without a versioned Runtime migration. | Consider active-model evolution only under separately approved migration design. |
| P2B2-D2 | Require `actor_role == user` in this execution-capable fixture. | The requested program forbids approval bypass and real execution must remain explicitly user-authorized. | Do not generalize to policy/system actors without explicit authority and review. |
| P2B2-D3 | Bind receipt-derived command digest rather than the inspect-tool digest. | The two documented normalization paths differ; treating them as identical would create a false match. | Use a future canonical production digest only after its own compatibility analysis. |
| P2B2-D4 | Treat a fake counter increment as fixture evidence only. | The ledger accepts no dispatcher or execution surface. | Never elevate it to active enforcement or scientific readiness. |
